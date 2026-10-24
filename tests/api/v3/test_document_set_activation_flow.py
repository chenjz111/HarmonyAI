"""V3.1 有资料流程：DocumentSet 激活 + relevance gate 回归测试。

背景（真机根因）：
    POST /api/v3/understandings -> 422 DOCUMENT_SET_NOT_ACTIVE
    因为前端真实上传链只做 POST /api/v2/documents + replace_document（单文档），
    从未调用 canonical 的 POST /api/v3/sessions/{id}/document-sets，
    于是 session.active_document_set_id 一直为 NULL，_validate_v31_request_sources 抛
    DOCUMENT_SET_NOT_ACTIVE。

本文件锁定：
  * canonical 激活路径（1 份 / 3 份资料 → 一个 DocumentSet → active set + revision CAS）
  * relevance 状态机（VALID 放行；INVALID / IRRELEVANT / INSUFFICIENT / 未判定均阻断）
  * owner / session 归属（跨用户、跨 session 一律拒绝，不放宽）
  * revision 与 idempotency（重放不产生重复 active set）
  * 原真机场景不再复现（未建 set 时 gate 仍然生效，证明是接线修复而非放宽校验）

全部使用 fake/local OCR 与 DB fixture；不调用任何真实 Provider（Qwen / Embedding /
TokenHub / Stability 均不触达）。
"""

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.app.core.database import get_db
from backend.app.core.ocr import OCRProvider, OCRResult
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.document import (
    DocumentRelevance,
    DocumentSet,
    DocumentSetItem,
)
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.session import SessionInputRevision
from backend.app.routers import document_router


client = TestClient(app)

OCR_TEXT = "材料中提到近期睡眠恢复不足，白天精力一般。"


def _v3_data(response):
    payload = response.json()
    if "data" not in payload:
        raise AssertionError(
            f"unexpected {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload["data"]


def _error_code(response) -> str:
    return (response.json().get("error") or {}).get("code", "")


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _guest_headers() -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _user_pk(authorization: str) -> int:
    with _seed_db() as session:
        return (
            session.query(UserIdentity)
            .filter(
                UserIdentity.public_user_id
                == _public_user_id(authorization.split(" ")[1])
            )
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


def _select_with_document(headers, session_id) -> int:
    response = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"sel-{uuid.uuid4().hex}"},
        json={
            "expected_input_revision": 1,
            "action": "select_mode",
            "input_mode": "with_document",
        },
    )
    assert response.status_code == 201, response.text
    assert _v3_data(response)["input_revision"] == 2
    return _v3_data(response)["input_revision"]


def _seed_document(
    session,
    *,
    user_pk: int,
    session_id: str,
    ocr_text: str | None = OCR_TEXT,
) -> str:
    """插入一份已 OCR-ready 的资料（不建 set、不激活）。"""
    document_id = f"doc_{uuid.uuid4().hex}"
    session.add(
        Document(
            user_id=user_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename="sample.png",
            file_type="png",
            file_size_bytes=1024,
            storage_path=f"docs/{document_id}",
            status="uploaded",
            ocr_text=ocr_text,
            ocr_confidence="high" if ocr_text else None,
            ocr_error_code=None,
        )
    )
    session.commit()
    return document_id


def _seed_relevance(session, set_id: str, revision: int, outcome: str) -> None:
    session.add(
        DocumentRelevance(
            document_relevance_id=f"drel_{uuid.uuid4().hex}",
            document_set_id=set_id,
            document_set_revision=revision,
            run_id=f"run_{uuid.uuid4().hex}",
            revision=1,
            outcome=outcome,
            reason_code=f"TEST_{outcome}",
            reason="test fixture",
            evaluator="test",
            evaluator_version="1",
            evaluated_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def _post_document_set(headers, session_id, document_ids, expected_revision, key=None):
    return client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={
            **headers,
            "Idempotency-Key": key or f"set-{uuid.uuid4().hex}",
        },
        json={
            "session_id": session_id,
            "expected_input_revision": expected_revision,
            "document_ids": document_ids,
        },
    )


def _post_understanding(headers, session_id, document_ids, key=None, expected_revision=None):
    captured_at = datetime.now(timezone.utc).isoformat()
    if expected_revision is None:
        expected_revision = _session_row(session_id)["input_revision"]
    return client.post(
        "/api/v3/understandings",
        headers={
            **headers,
            "Idempotency-Key": key or f"und-{uuid.uuid4().hex}",
        },
        json={
            "schema_version": "understanding_v3.1",
            "session_id": session_id,
            "expected_input_revision": expected_revision,
            "inputs": [
                {
                    "source_id": f"src_{uuid.uuid4().hex}",
                    "source_type": "document",
                    "processing_status": "ready",
                    "text_ref": document_id,
                    "captured_at": captured_at,
                }
                for document_id in document_ids
            ],
        },
    )


def _session_row(session_id) -> dict:
    with _seed_db() as session:
        row = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        return {
            "input_mode": row.input_mode,
            "input_revision": row.input_revision,
            "active_document_id": row.active_document_id,
            "active_document_set_id": row.active_document_set_id,
            "active_understanding_id": row.active_understanding_id,
            "user_id": row.user_id,
            "row_id": row.id,
        }


def _document_sets(session_id) -> list[dict]:
    with _seed_db() as session:
        row = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        sets = (
            session.query(DocumentSet)
            .filter(DocumentSet.session_row_id == row.id)
            .order_by(DocumentSet.revision)
            .all()
        )
        return [
            {
                "document_set_id": item.document_set_id,
                "revision": item.revision,
                "status": item.status,
                "internal_user_pk": item.internal_user_pk,
                "items": [
                    (link.document_id, link.position)
                    for link in session.query(DocumentSetItem)
                    .filter(DocumentSetItem.document_set_id == item.document_set_id)
                    .order_by(DocumentSetItem.position)
                    .all()
                ],
            }
            for item in sets
        ]


def _relevance_rows(session_id) -> int:
    with _seed_db() as session:
        row = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        set_ids = [
            item.document_set_id
            for item in session.query(DocumentSet)
            .filter(DocumentSet.session_row_id == row.id)
            .all()
        ]
        if not set_ids:
            return 0
        return (
            session.query(DocumentRelevance)
            .filter(DocumentRelevance.document_set_id.in_(set_ids))
            .count()
        )


def _input_revision_rows(session_id) -> list[tuple[int, str]]:
    with _seed_db() as session:
        row = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        return [
            (item.input_revision, item.action)
            for item in session.query(SessionInputRevision)
            .filter(SessionInputRevision.session_row_id == row.id)
            .order_by(SessionInputRevision.input_revision)
            .all()
        ]


@pytest.fixture(autouse=True)
def _reserve_legacy_owner_id():
    """占用 internal_user_pk=1，避免与 legacy 默认 owner 混淆。"""
    _v3_data(client.post("/api/v3/auth/guest"))


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(document_router, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_ocr(monkeypatch):
    def fake_process(self, file_path, file_type):
        return OCRResult(
            text=OCR_TEXT,
            confidence="high",
            provider="paddleocr",
            page_count=1,
            average_confidence=0.97,
            engine_version="test-fixture",
        )

    monkeypatch.setattr(OCRProvider, "process", fake_process)
    return fake_process


def _upload_one(session_id, headers, content=None):
    return client.post(
        "/api/v2/documents",
        headers=dict(headers),
        data={
            "session_id": session_id,
            "document_type": "medical_record",
            "consent_confirmed": "true",
        },
        files={
            "file": (
                "report.png",
                content if content is not None else b"\x89PNG\r\n\x1a\n" + b"fixture",
                "image/png",
            )
        },
    )


# --------------------------------------------------------------------------
# canonical DocumentSet 激活：1 份 / 3 份
# --------------------------------------------------------------------------

def test_single_document_activates_document_set():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    with _seed_db() as session:
        document_id = _seed_document(session, user_pk=user_pk, session_id=session_id)

    response = _post_document_set(headers, session_id, [document_id], 2)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["documents"][0]["document_id"] == document_id
    assert data["input_revision"] == 3

    row = _session_row(session_id)
    assert row["active_document_set_id"] == data["document_set_id"]
    assert row["active_document_id"] == document_id
    assert row["input_revision"] == 3
    sets = _document_sets(session_id)
    assert len(sets) == 1
    assert sets[0]["status"] == "current"
    assert sets[0]["internal_user_pk"] == row["user_id"] == user_pk
    assert sets[0]["items"] == [(document_id, 1)]
    assert (3, "replace_document") in _input_revision_rows(session_id)
    assert _relevance_rows(session_id) == 0, "relevance 由后续消费按 canonical 流程判定"


def test_three_documents_form_one_ordered_set():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    with _seed_db() as session:
        ids = [
            _seed_document(session, user_pk=user_pk, session_id=session_id)
            for _ in range(3)
        ]

    response = _post_document_set(headers, session_id, ids, 2)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert [doc["document_id"] for doc in data["documents"]] == ids, "顺序必须保留"
    sets = _document_sets(session_id)
    assert len(sets) == 1, "3 份资料必须是同一个 set，而不是 3 次 replace"
    assert sets[0]["items"] == [(ids[0], 1), (ids[1], 2), (ids[2], 3)]
    row = _session_row(session_id)
    assert row["active_document_set_id"] == data["document_set_id"]
    assert row["active_document_id"] == ids[0], "active_document_id 按 contract 为首份"
    assert row["input_revision"] == 3
    assert _input_revision_rows(session_id) == [
        (1, "create"),
        (2, "select_mode"),
        (3, "replace_document"),
    ]


def test_set_size_and_duplicate_are_rejected():
    """1~3 份约束在两层都生效：请求 schema（HTTP 422）与服务层（DOCUMENT_SET_* 语义）。"""
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    with _seed_db() as session:
        ids = [
            _seed_document(session, user_pk=user_pk, session_id=session_id)
            for _ in range(4)
        ]

    # schema 层：max_length=3 / unique validator 先于服务层拦截
    too_many = _post_document_set(headers, session_id, ids, 2)
    assert too_many.status_code == 422
    duplicated = _post_document_set(headers, session_id, [ids[0], ids[0]], 2)
    assert duplicated.status_code == 422
    assert _document_sets(session_id) == [], "被拒请求不得留下任何 set"
    assert _session_row(session_id)["active_document_set_id"] is None

    # 服务层：同样的语义有明确错误码（不经 HTTP 也成立）
    from types import SimpleNamespace

    from backend.app.services.v3.document_set_service import (
        InvalidDocumentSet,
        _validate_document_ids,
    )

    with _seed_db() as session:
        session_row = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        # _validate_document_ids 只读取 principal.internal_user_pk
        principal = SimpleNamespace(internal_user_pk=user_pk)
        with pytest.raises(InvalidDocumentSet) as size_error:
            _validate_document_ids(session, principal, session_row, ids)
        assert size_error.value.code == "DOCUMENT_SET_SIZE"
        with pytest.raises(InvalidDocumentSet) as duplicate_error:
            _validate_document_ids(session, principal, session_row, [ids[0], ids[0]])
        assert duplicate_error.value.code == "DOCUMENT_SET_DUPLICATE"


# --------------------------------------------------------------------------
# relevance 状态机（gate 不得放宽）
# --------------------------------------------------------------------------

def _ready_set(headers, session_id, user_pk, count=1):
    with _seed_db() as session:
        ids = [
            _seed_document(session, user_pk=user_pk, session_id=session_id)
            for _ in range(count)
        ]
    response = _post_document_set(headers, session_id, ids, 2)
    assert response.status_code == 201, response.text
    set_id = _v3_data(response)["document_set_id"]
    return ids, set_id


def test_valid_relevance_allows_understanding():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, set_id = _ready_set(headers, session_id, user_pk)
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, "VALID")

    response = _post_understanding(headers, session_id, ids)

    assert response.status_code == 201, response.text
    assert _error_code(response) != "DOCUMENT_SET_NOT_ACTIVE"
    assert _v3_data(response)["source_statuses"][0]["status"] == "ready"
    assert _session_row(session_id)["active_document_set_id"] == set_id


def test_three_document_valid_relevance_allows_understanding():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, set_id = _ready_set(headers, session_id, user_pk, count=3)
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, "VALID")

    response = _post_understanding(headers, session_id, ids)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert len(data["source_statuses"]) == 3
    assert [status["status"] for status in data["source_statuses"]] == ["ready"] * 3


@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        ("INVALID", "DOCUMENT_RELEVANCE_BLOCKED"),
        ("IRRELEVANT", "DOCUMENT_RELEVANCE_BLOCKED"),
        ("INSUFFICIENT", "DOCUMENT_RELEVANCE_INSUFFICIENT"),
    ],
)
def test_non_valid_relevance_blocks_understanding(outcome, code):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, set_id = _ready_set(headers, session_id, user_pk)
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, outcome)

    response = _post_understanding(headers, session_id, ids)

    assert response.status_code == 422, response.text
    assert _error_code(response) == code
    assert _error_code(response) != "DOCUMENT_SET_NOT_ACTIVE"


def test_missing_relevance_is_not_bypassed():
    """未判定 relevance 时 gate 必须阻断（本测试环境无 provider 配置，不触达真实服务）。"""
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, _ = _ready_set(headers, session_id, user_pk)

    response = _post_understanding(headers, session_id, ids)

    assert response.status_code == 422, response.text
    assert _error_code(response) == "DOCUMENT_RELEVANCE_NOT_READY"
    assert _relevance_rows(session_id) == 0, "不得凭空写入 VALID"


def test_understanding_requires_all_active_documents_in_order():
    """前端必须按活动集合的完整有序列表提交 inputs（否则 gate 拒绝）。"""
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, set_id = _ready_set(headers, session_id, user_pk, count=3)
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, "VALID")

    partial = _post_understanding(headers, session_id, ids[:1])
    assert partial.status_code == 422
    assert _error_code(partial) == "INPUT_SOURCE_MISMATCH"

    reordered = _post_understanding(headers, session_id, list(reversed(ids)))
    assert reordered.status_code == 422
    assert _error_code(reordered) == "INPUT_SOURCE_MISMATCH"

    complete = _post_understanding(headers, session_id, ids)
    assert complete.status_code == 201, complete.text


def test_fake_evaluator_records_canonical_relevance_then_allows_understanding():
    """relevance 评测边界用 fake 注入：写入 canonical relevance 行后再校验 gate 放行。

    真实模式下该评测由 Qwen provider 完成；本测试用 fake 证明接线与落库/门控语义，
    不触达任何 Provider。
    """
    from backend.app.schemas.v3.flow_v31 import (
        DocumentRelevanceResult,
        DocumentSetRef,
        RelevanceOutcome,
    )
    from backend.app.services.v3.document_relevance_evaluator import (
        ensure_document_set_relevance,
    )

    captured: dict[str, object] = {}

    class FakeEvaluator:
        model = "fake-relevance-v1"

        def evaluate(
            self, *, document_set_id, set_revision, input_revision, ordered_ocr_texts
        ):
            captured["ordered_ocr_texts"] = list(ordered_ocr_texts)
            captured["input_revision"] = input_revision
            return DocumentRelevanceResult(
                schema_version="document_relevance_result_v3.1",
                relevance_result_id=f"rel_{uuid.uuid4().hex}",
                run_id=f"run_{uuid.uuid4().hex}",
                revision=1,
                document_set_ref=DocumentSetRef(
                    document_set_id=document_set_id, revision=set_revision
                ),
                outcome=RelevanceOutcome.VALID,
                reason_code="FAKE_VALID",
                reason="test fixture evaluator",
                may_enter_summary=True,
                may_form_evidence=True,
                may_enter_agent2=True,
                completed_at=datetime.now(timezone.utc),
            )

    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, set_id = _ready_set(headers, session_id, user_pk, count=2)

    with _seed_db() as session:
        session_row = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        set_row = (
            session.query(DocumentSet)
            .filter(DocumentSet.document_set_id == set_id)
            .one()
        )
        result = ensure_document_set_relevance(
            session, session_row, set_row, evaluator=FakeEvaluator()
        )
        assert result.outcome.value == "VALID"

    assert _relevance_rows(session_id) == 1, "canonical relevance 行必须落库"
    assert captured["ordered_ocr_texts"] == [OCR_TEXT, OCR_TEXT], "按集合顺序取 OCR 文本"
    with _seed_db() as session:
        row = session.query(DocumentRelevance).one()
        assert row.outcome == "VALID"
        assert row.document_set_id == set_id
        assert row.document_set_revision == 1
        assert row.evaluator == "FakeEvaluator"
        assert row.evaluator_version == "fake-relevance-v1"

    understanding = _post_understanding(headers, session_id, ids)

    assert understanding.status_code == 201, understanding.text
    assert _error_code(understanding) != "DOCUMENT_SET_NOT_ACTIVE"


# --------------------------------------------------------------------------
# 原真机场景：未建 set 时 gate 仍生效（证明是接线修复，不是放宽校验）
# --------------------------------------------------------------------------

def test_replace_document_without_set_still_reports_document_set_not_active():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    with _seed_db() as session:
        document_id = _seed_document(session, user_pk=user_pk, session_id=session_id)

    # 旧前端行为：只做 replace_document（单文档），从未创建 DocumentSet
    replace = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"rep-{uuid.uuid4().hex}"},
        json={
            "expected_input_revision": 2,
            "action": "replace_document",
            "document_id": document_id,
        },
    )
    assert replace.status_code == 201, replace.text
    row = _session_row(session_id)
    assert row["active_document_id"] == document_id
    assert row["active_document_set_id"] is None, "replace_document 不创建 set（未放宽）"

    response = _post_understanding(headers, session_id, [document_id])

    assert response.status_code == 422
    assert _error_code(response) == "DOCUMENT_SET_NOT_ACTIVE"
    assert _document_sets(session_id) == []


def test_set_creation_replaces_the_document_set_not_active_failure():
    """同一会话改用 canonical set 后，DOCUMENT_SET_NOT_ACTIVE 不再出现。"""
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    ids, set_id = _ready_set(headers, session_id, user_pk)
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, "VALID")

    response = _post_understanding(headers, session_id, ids)

    assert response.status_code == 201
    assert _error_code(response) != "DOCUMENT_SET_NOT_ACTIVE"


# --------------------------------------------------------------------------
# owner / session 归属
# --------------------------------------------------------------------------

def test_cross_owner_document_is_rejected():
    owner_headers = _guest_headers()
    session_id = _new_flow_session(owner_headers)
    _select_with_document(owner_headers, session_id)

    stranger_headers = _guest_headers()
    stranger_pk = _user_pk(stranger_headers["Authorization"])
    stranger_session = _new_flow_session(stranger_headers)
    with _seed_db() as session:
        stranger_doc = _seed_document(
            session, user_pk=stranger_pk, session_id=stranger_session
        )

    response = _post_document_set(owner_headers, session_id, [stranger_doc], 2)

    assert response.status_code == 422
    assert _error_code(response) == "DOCUMENT_NOT_FOUND"
    assert _document_sets(session_id) == []
    assert _session_row(session_id)["active_document_set_id"] is None


def test_cross_session_document_is_rejected_for_same_owner():
    headers = _guest_headers()
    user_pk = _user_pk(headers["Authorization"])
    session_a = _new_flow_session(headers)
    session_b = _new_flow_session(headers)
    _select_with_document(headers, session_a)
    _select_with_document(headers, session_b)
    with _seed_db() as session:
        doc_in_b = _seed_document(session, user_pk=user_pk, session_id=session_b)

    response = _post_document_set(headers, session_a, [doc_in_b], 2)

    assert response.status_code == 422
    assert _error_code(response) == "DOCUMENT_NOT_FOUND"


def test_stranger_cannot_activate_set_on_owner_session():
    owner_headers = _guest_headers()
    session_id = _new_flow_session(owner_headers)
    user_pk = _user_pk(owner_headers["Authorization"])
    _select_with_document(owner_headers, session_id)
    with _seed_db() as session:
        document_id = _seed_document(session, user_pk=user_pk, session_id=session_id)
    stranger_headers = _guest_headers()

    response = _post_document_set(stranger_headers, session_id, [document_id], 2)

    assert response.status_code == 404
    assert _error_code(response) == "RESOURCE_NOT_FOUND"
    assert _document_sets(session_id) == []


def test_legacy_session_cannot_create_document_set():
    headers = _guest_headers()
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"legacy-{uuid.uuid4().hex}"},
        json={},
    )
    session_id = _v3_data(response)["session_id"]

    created = _post_document_set(headers, session_id, ["doc_any"], 1)

    assert created.status_code == 409
    assert _error_code(created) == "FLOW_CONTRACT_MISMATCH"


def test_stale_expected_input_revision_is_rejected():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    with _seed_db() as session:
        document_id = _seed_document(session, user_pk=user_pk, session_id=session_id)

    response = _post_document_set(headers, session_id, [document_id], 99)

    assert response.status_code == 409
    assert _error_code(response) == "INPUT_REVISION_CONFLICT"
    assert _document_sets(session_id) == []


# --------------------------------------------------------------------------
# revision / idempotency
# --------------------------------------------------------------------------

def test_retry_with_same_idempotency_key_does_not_create_duplicate_set():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    with _seed_db() as session:
        document_id = _seed_document(session, user_pk=user_pk, session_id=session_id)
    key = f"set-retry-{uuid.uuid4().hex}"

    first = _post_document_set(headers, session_id, [document_id], 2, key=key)
    second = _post_document_set(headers, session_id, [document_id], 2, key=key)

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert _v3_data(second)["document_set_id"] == _v3_data(first)["document_set_id"]
    assert len(_document_sets(session_id)) == 1, "重放不得创建重复 active set"
    assert _session_row(session_id)["input_revision"] == 3, "重放不得重复增长 revision"


def test_replacing_set_supersedes_previous_and_bumps_revision_once():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)
    first_ids, first_set = _ready_set(headers, session_id, user_pk)
    with _seed_db() as session:
        _seed_relevance(session, first_set, 1, "VALID")
    assert _post_understanding(headers, session_id, first_ids).status_code == 201

    with _seed_db() as session:
        replacement = _seed_document(session, user_pk=user_pk, session_id=session_id)
    second = _post_document_set(headers, session_id, [replacement], 3)

    assert second.status_code == 201, second.text
    sets = _document_sets(session_id)
    assert len(sets) == 2
    assert sets[0]["status"] == "superseded"
    assert sets[1]["status"] == "current"
    row = _session_row(session_id)
    assert row["active_document_set_id"] == sets[1]["document_set_id"]
    assert row["input_revision"] == 4, "每次激活只增长一次 revision"
    assert row["active_understanding_id"] is None, "新资料集使旧理解失效"


# --------------------------------------------------------------------------
# 真机链路（fake OCR + canonical set）：上传 → owner → set → relevance → understanding
# --------------------------------------------------------------------------

def test_upload_owner_set_relevance_understanding_chain(upload_dir, fake_ocr):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    user_pk = _user_pk(headers["Authorization"])
    _select_with_document(headers, session_id)

    uploaded = _upload_one(session_id, headers)
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["success"] is True
    document_id = body["data"]["document_id"]
    with _seed_db() as session:
        document = (
            session.query(Document)
            .filter(Document.document_id == document_id)
            .one()
        )
        assert document.user_id == user_pk
        assert document.session_id == session_id

    created = _post_document_set(headers, session_id, [document_id], 2)
    assert created.status_code == 201, created.text
    set_id = _v3_data(created)["document_set_id"]
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, "VALID")

    understanding = _post_understanding(headers, session_id, [document_id])

    assert understanding.status_code == 201, understanding.text
    assert _error_code(understanding) != "DOCUMENT_SET_NOT_ACTIVE"
    row = _session_row(session_id)
    assert row["active_document_set_id"] == set_id
    assert row["active_document_id"] == document_id
    assert row["input_revision"] == 3


def test_three_uploaded_documents_chain(upload_dir, fake_ocr):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _select_with_document(headers, session_id)

    ids = []
    for index in range(3):
        response = _upload_one(
            session_id,
            headers,
            content=b"\x89PNG\r\n\x1a\n" + f"fixture-{index}".encode(),
        )
        assert response.status_code == 200, response.text
        ids.append(response.json()["data"]["document_id"])

    created = _post_document_set(headers, session_id, ids, 2)
    assert created.status_code == 201, created.text
    set_id = _v3_data(created)["document_set_id"]
    with _seed_db() as session:
        _seed_relevance(session, set_id, 1, "VALID")

    understanding = _post_understanding(headers, session_id, ids)

    assert understanding.status_code == 201, understanding.text
    assert len(_v3_data(understanding)["source_statuses"]) == 3
    assert len(_document_sets(session_id)) == 1
    assert _session_row(session_id)["input_revision"] == 3
