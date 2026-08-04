"""Document API error responses must not expose internal details."""

from fastapi.testclient import TestClient
import pytest

from backend.app.core.database import get_db
from backend.app.main import app


client = TestClient(app)


class FakeDocument:
    document_id = "doc_private_error"
    status = "uploaded"
    ocr_confirmed = False
    ocr_text = "stub"
    storage_path = None


class FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return FakeDocument()


class FailingCommitDb:
    def query(self, *_args, **_kwargs):
        return FakeQuery()

    def commit(self):
        raise RuntimeError("mysql://root:secret@localhost/harmony")

    def rollback(self):
        pass


def failing_db():
    yield FailingCommitDb()


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "code", "message"),
    [
        (
            "patch",
            "/api/v2/documents/doc_private_error/confirmation",
            {
                "json": {
                    "session_id": "sess_private_error",
                    "confirmed": True,
                    "document_text": "已确认文本",
                    "redactions_confirmed": True,
                }
            },
            "CONFIRM_FAILED",
            "材料确认失败，请稍后重试",
        ),
        (
            "delete",
            "/api/v2/documents/doc_private_error",
            {},
            "DELETE_FAILED",
            "材料删除失败，请稍后重试",
        ),
    ],
)
def test_document_mutation_errors_are_sanitized(
    method,
    path,
    kwargs,
    code,
    message,
):
    app.dependency_overrides[get_db] = failing_db
    try:
        response = getattr(client, method)(path, **kwargs)
    finally:
        app.dependency_overrides.pop(get_db, None)

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == code
    assert data["error"]["message"] == message
    assert "secret" not in str(data)
