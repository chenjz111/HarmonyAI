"""Owner binding for the legacy V2 multipart upload path (Android real-device fix).

Regression coverage for the confirmed Android failure chain:

    select_mode(with_document) -> POST /api/v2/documents -> replace_document

`POST /api/v2/documents` persisted ``Document.user_id = 1`` (historical default
owner) while the caller's V3 session was owned by the authenticated guest, so
the follow-up ``replace_document`` failed ownership validation inside
``activity_service._validate_document`` with 422 DOCUMENT_NOT_FOUND and the app
showed the generic "网络或服务暂时不可用" page.

The contract asserted here:

* no Authorization header at all  -> legacy V2 behaviour, owner stays user_id 1
* valid V3 Bearer                 -> document is owned by that principal
* V3 principal + foreign session  -> rejected, nothing written
* Authorization present but bad   -> 401, never a silent fallback to user_id 1

OCR is always the fake local fixture below: no PaddleOCR, no external provider.
"""

import base64
from contextlib import contextmanager
import json
import uuid

from fastapi.testclient import TestClient
from jose import jwt
import pytest

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.ocr import OCRProvider, OCRResult
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.identity import UserIdentity
from backend.app.routers import document_router


client = TestClient(app)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"owner-binding-fixture"
LEGACY_SESSION = "sess_legacy_owner_binding"


def _v3_data(response):
    payload = response.json()
    if "data" not in payload:
        raise AssertionError(
            f"unexpected {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload["data"]


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _guest_headers() -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _reserve_legacy_owner_id():
    """Consume ``internal_user_pk`` 1 before each test.

    In a fresh database the first guest identity gets pk 1, which equals the
    legacy default owner id; "document bound to the authenticated principal" and
    "document hardcoded to the legacy owner" would then be indistinguishable.
    Burning the first identity keeps every test principal at pk >= 2.
    """
    _v3_data(client.post("/api/v3/auth/guest"))


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _principal_pk(authorization: str) -> int:
    with _seed_db() as session:
        return (
            session.query(UserIdentity)
            .filter(UserIdentity.public_user_id == _public_user_id(authorization.split(" ")[1]))
            .one()
            .internal_user_pk
        )


def _new_flow_session(headers) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"seed-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _transition(headers, session_id, key, body):
    return client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )


def _select_with_document(headers, session_id):
    response = _transition(
        headers,
        session_id,
        f"sel-{uuid.uuid4().hex}",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    assert response.status_code == 201, response.text
    assert _v3_data(response)["input_revision"] == 2
    return response


def _upload(session_id, *, headers=None, filename="report.png", content=PNG_BYTES,
            media_type="image/png", consent="true"):
    return client.post(
        "/api/v2/documents",
        headers=dict(headers or {}),
        data={
            "session_id": session_id,
            "document_type": "medical_record",
            "consent_confirmed": consent,
        },
        files={"file": (filename, content, media_type)},
    )


def _document_rows(session_id):
    with _seed_db() as session:
        return [
            {
                "document_id": row.document_id,
                "user_id": row.user_id,
                "ocr_text": row.ocr_text,
                "ocr_confidence": row.ocr_confidence,
            }
            for row in session.query(Document)
            .filter(Document.session_id == session_id)
            .all()
        ]


def _session_rows(session_id):
    with _seed_db() as session:
        return [
            {"user_id": row.user_id, "session_id": row.session_id}
            for row in session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .all()
        ]


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(document_router, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_ocr(monkeypatch):
    """Deterministic local OCR success — no PaddleOCR, no external provider."""

    def fake_process(self, file_path, file_type):
        return OCRResult(
            text="近一周入睡困难，晨起乏力。",
            confidence="high",
            provider="paddleocr",
            page_count=1,
            average_confidence=0.97,
            engine_version="test-fixture",
        )

    monkeypatch.setattr(OCRProvider, "process", fake_process)
    return fake_process


# --------------------------------------------------------------------------
# 1. Legacy compatibility: no Authorization header keeps user_id = 1
# --------------------------------------------------------------------------

def test_legacy_upload_without_authorization_keeps_default_owner(upload_dir, fake_ocr):
    uploaded = _upload(LEGACY_SESSION).json()

    assert uploaded["success"] is True
    assert _document_rows(LEGACY_SESSION)[0]["user_id"] == 1
    assert document_router.LEGACY_USER_ID == 1
    # The legacy helper keeps creating/finding the historical default-owner session.
    assert [row["user_id"] for row in _session_rows(LEGACY_SESSION)] == [1]


# --------------------------------------------------------------------------
# 2. Valid V3 Bearer binds the document to that principal
# --------------------------------------------------------------------------

def test_v3_bearer_binds_uploaded_document_to_principal(upload_dir, fake_ocr):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    principal_pk = _principal_pk(headers["Authorization"])
    assert principal_pk != document_router.LEGACY_USER_ID

    uploaded = _upload(session_id, headers=headers).json()

    assert uploaded["success"] is True
    rows = _document_rows(session_id)
    assert len(rows) == 1
    assert rows[0]["user_id"] == principal_pk
    assert rows[0]["ocr_text"]
    # Session is neither duplicated nor re-owned.
    assert [row["user_id"] for row in _session_rows(session_id)] == [principal_pk]


# --------------------------------------------------------------------------
# 3 + 6. Owner can bind: replace_document succeeds and advances input_revision
# --------------------------------------------------------------------------

def test_v3_owner_can_bind_uploaded_document(upload_dir, fake_ocr):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _select_with_document(headers, session_id)

    uploaded = _upload(session_id, headers=headers).json()
    assert uploaded["success"] is True
    assert uploaded["data"]["ocr_status"] == "confirmed"
    document_id = uploaded["data"]["document_id"]

    replace = _transition(
        headers,
        session_id,
        f"rep-{uuid.uuid4().hex}",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )

    assert replace.status_code == 201, replace.text
    data = _v3_data(replace)
    assert data["input_mode"] == "with_document"
    assert data["input_revision"] == 3
    assert data["active_document_id"] == document_id


# --------------------------------------------------------------------------
# 7. The original Android failure chain no longer produces DOCUMENT_NOT_FOUND
# --------------------------------------------------------------------------

def test_android_upload_chain_no_longer_returns_document_not_found(upload_dir, fake_ocr):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _select_with_document(headers, session_id)

    uploaded = _upload(session_id, headers=headers)
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["success"] is True

    replace = _transition(
        headers,
        session_id,
        f"rep-{uuid.uuid4().hex}",
        {
            "expected_input_revision": 2,
            "action": "replace_document",
            "document_id": body["data"]["document_id"],
        },
    )

    assert replace.status_code != 422
    assert replace.json().get("error", {}).get("code") != "DOCUMENT_NOT_FOUND"
    assert _v3_data(replace)["active_document_id"] == body["data"]["document_id"]


# --------------------------------------------------------------------------
# 4. Foreign / unknown session is rejected and leaves no trace
# --------------------------------------------------------------------------

def test_cross_user_session_upload_is_rejected(upload_dir, fake_ocr):
    owner_headers = _guest_headers()
    session_id = _new_flow_session(owner_headers)
    stranger_headers = _guest_headers()

    response = _upload(session_id, headers=stranger_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert _document_rows(session_id) == []
    assert list(upload_dir.iterdir()) == []


def test_v3_upload_to_unknown_session_is_rejected_without_parallel_session(upload_dir, fake_ocr):
    headers = _guest_headers()
    unknown_session = f"sess_unknown_{uuid.uuid4().hex}"

    response = _upload(unknown_session, headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    # Must not create a legacy (user_id=1) parallel session for an owned caller.
    assert _session_rows(unknown_session) == []
    assert _document_rows(unknown_session) == []
    assert list(upload_dir.iterdir()) == []


# --------------------------------------------------------------------------
# 5. Present-but-unusable Authorization must never fall back to legacy owner
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-jwt",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
        "Token abc123",
    ],
)
def test_unusable_authorization_never_falls_back_to_legacy_owner(
    upload_dir, fake_ocr, authorization
):
    session_id = f"sess_bad_bearer_{uuid.uuid4().hex}"

    response = _upload(session_id, headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert _document_rows(session_id) == []
    assert _session_rows(session_id) == []
    assert list(upload_dir.iterdir()) == []


def test_wellformed_bearer_with_unknown_identity_is_rejected(upload_dir, fake_ocr):
    token = jwt.encode(
        {
            "sub": f"u_guest_{uuid.uuid4().hex}",
            "auth_type": "guest",
            "iat": 0,
            "exp": 4102444800,
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    session_id = f"sess_unknown_identity_{uuid.uuid4().hex}"

    response = _upload(session_id, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert _document_rows(session_id) == []
    assert _session_rows(session_id) == []


def test_expired_bearer_is_rejected(upload_dir, fake_ocr):
    headers = _guest_headers()
    public_user_id = _public_user_id(headers["Authorization"].split(" ")[1])
    expired = jwt.encode(
        {"sub": public_user_id, "auth_type": "guest", "iat": 0, "exp": 1},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    session_id = f"sess_expired_{uuid.uuid4().hex}"

    response = _upload(session_id, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert _document_rows(session_id) == []
    assert _session_rows(session_id) == []
