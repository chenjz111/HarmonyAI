"""Sprint 3 document upload API tests."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.routers import document_router


client = TestClient(app)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"demo-image"


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(document_router, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _upload(content=PNG_BYTES, *, consent="true", filename="record.png", media_type="image/png"):
    return client.post(
        "/api/v2/documents",
        data={
            "session_id": "sess_document_v2",
            "document_type": "sleep_emotion_record",
            "consent_confirmed": consent,
        },
        files={"file": (filename, content, media_type)},
    )


def test_document_requires_consent(upload_dir):
    data = _upload(consent="false").json()

    assert data["success"] is False
    assert data["error"]["code"] == "CONSENT_REQUIRED"
    assert list(upload_dir.iterdir()) == []


def test_document_rejects_signature_mismatch(upload_dir):
    data = _upload(content=b"not-a-png").json()

    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_SIGNATURE"
    assert list(upload_dir.iterdir()) == []


def test_document_rejects_file_larger_than_ten_megabytes(upload_dir):
    content = b"\x89PNG\r\n\x1a\n" + b"x" * (document_router.MAX_FILE_SIZE + 1)
    data = _upload(content=content).json()

    assert data["success"] is False
    assert data["error"]["code"] == "FILE_TOO_LARGE"
    assert list(upload_dir.iterdir()) == []


def test_document_rejects_pdf_over_three_pages(upload_dir):
    content = b"%PDF\n" + (b"/Type /Page\n" * 4) + b"%%EOF"
    data = _upload(
        content=content,
        filename="record.pdf",
        media_type="application/pdf",
    ).json()

    assert data["success"] is False
    assert data["error"]["code"] == "PDF_TOO_LONG"
    assert list(upload_dir.iterdir()) == []


def test_document_upload_confirm_list_and_delete(upload_dir, monkeypatch):
    from backend.app.core.ocr import OCRProvider

    monkeypatch.setattr(OCRProvider, "_init_paddle", lambda self: None)
    uploaded = _upload().json()
    assert uploaded["success"] is True
    assert uploaded["data"]["ocr_status"] == "degraded"
    assert uploaded["data"]["ocr_provider"] == "stub"
    assert uploaded["data"]["warnings"] == ["OCR降级: paddleocr_not_available"]

    document_id = uploaded["data"]["document_id"]
    stored_files = list(upload_dir.iterdir())
    assert len(stored_files) == 1

    confirmed = client.patch(
        f"/api/v2/documents/{document_id}/confirmation",
        json={
            "session_id": "sess_document_v2",
            "confirmed": True,
            "document_text": "用户已核对：近一周入睡困难。",
            "redactions_confirmed": True,
        },
    ).json()
    assert confirmed["success"] is True
    assert confirmed["data"]["ocr_status"] == "confirmed"
    assert confirmed["data"]["document_text"] == "用户已核对：近一周入睡困难。"

    listed = client.get("/api/v2/documents/sess_document_v2").json()
    assert listed["success"] is True
    assert listed["data"]["total"] == 1
    assert listed["data"]["documents"][0]["status"] == "confirmed"

    deleted = client.delete(f"/api/v2/documents/{document_id}").json()
    assert deleted["success"] is True
    assert deleted["data"]["status"] == "deleted"
    assert not stored_files[0].exists()


def test_document_can_be_skipped(upload_dir):
    uploaded = _upload().json()
    document_id = uploaded["data"]["document_id"]

    skipped = client.patch(
        f"/api/v2/documents/{document_id}/confirmation",
        json={
            "session_id": "sess_document_v2",
            "confirmed": False,
            "redactions_confirmed": False,
        },
    ).json()

    assert skipped["success"] is True
    assert skipped["data"]["ocr_status"] == "skipped"


def test_upload_failure_is_sanitized_and_removes_file(upload_dir, monkeypatch):
    def fail_session(*_args, **_kwargs):
        raise RuntimeError("mysql://root:secret@localhost/harmony")

    monkeypatch.setattr(document_router, "_ensure_session", fail_session)
    data = _upload().json()

    assert data["success"] is False
    assert data["error"]["code"] == "UPLOAD_FAILED"
    assert data["error"]["message"] == "材料上传失败，请稍后重试"
    assert "secret" not in str(data)
    assert list(Path(upload_dir).iterdir()) == []
