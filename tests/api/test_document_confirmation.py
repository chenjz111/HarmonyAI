from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.routers import document_router


client = TestClient(app)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"confirmation-image"


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(document_router, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _upload():
    return client.post(
        "/api/v2/documents",
        data={
            "session_id": "sess_document_confirmation",
            "document_type": "sleep_emotion_record",
            "consent_confirmed": "true",
        },
        files={"file": ("record.png", PNG_BYTES, "image/png")},
    ).json()["data"]["document_id"]


def test_confirmed_document_requires_redaction_confirmation(upload_dir):
    document_id = _upload()
    response = client.patch(
        f"/api/v2/documents/{document_id}/confirmation",
        json={
            "session_id": "sess_document_confirmation",
            "confirmed": True,
            "document_text": "用户确认文本",
            "redactions_confirmed": False,
        },
    )
    assert response.status_code == 422


def test_document_confirmation_is_scoped_to_session(upload_dir):
    document_id = _upload()
    body = client.patch(
        f"/api/v2/documents/{document_id}/confirmation",
        json={
            "session_id": "another_session",
            "confirmed": True,
            "document_text": "用户确认文本",
            "redactions_confirmed": True,
        },
    ).json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_document_confirmation_returns_append_only_timestamp(upload_dir):
    document_id = _upload()
    body = client.patch(
        f"/api/v2/documents/{document_id}/confirmation",
        json={
            "session_id": "sess_document_confirmation",
            "confirmed": True,
            "document_text": "用户确认文本",
            "redactions_confirmed": True,
        },
    ).json()
    assert body["success"] is True
    assert body["data"]["ocr_status"] == "confirmed"
    assert body["data"]["confirmed_at"]
