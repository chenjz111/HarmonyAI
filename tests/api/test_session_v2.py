"""Sprint 3 session API tests."""

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app


client = TestClient(app)


def test_create_sessions_returns_unique_ids():
    first = client.post(
        "/api/v2/sessions",
        json={"user_id": "demo_user_001", "entry_mode": "full"},
    ).json()
    second = client.post(
        "/api/v2/sessions",
        json={"user_id": "demo_user_001", "entry_mode": "full"},
    ).json()

    assert first["success"] is True
    assert second["success"] is True
    assert first["data"]["session_id"] != second["data"]["session_id"]


def test_session_create_error_does_not_leak_internal_details():
    class FailingDb:
        def add(self, *_args, **_kwargs):
            pass

        def commit(self):
            raise RuntimeError("mysql://root:secret@localhost/harmony")

        def rollback(self):
            pass

    def failing_db():
        yield FailingDb()

    app.dependency_overrides[get_db] = failing_db
    try:
        data = client.post(
            "/api/v2/sessions",
            json={"user_id": "demo_user_001", "entry_mode": "full"},
        ).json()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert data["success"] is False
    assert data["error"]["code"] == "SESSION_CREATE_FAILED"
    assert data["error"]["message"] == "会话创建失败，请稍后重试"
    assert "secret" not in str(data)
