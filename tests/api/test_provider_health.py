from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_provider_health_uses_frozen_shape_without_secrets(monkeypatch):
    # Shape/secrecy contract only: real provider/platform availability is a
    # separately authorized check, never a model initialization in offline CI.
    from backend.app.core.ocr import OCRProvider
    monkeypatch.setattr(OCRProvider,'_init_paddle',lambda self:None)
    response = client.get("/api/v2/providers/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert {"qwen", "ocr", "chroma", "database"}.issubset(body["data"])
    assert body["data"]["ocr"]["engine"] == "paddleocr"
    assert body["data"]["ocr"]["available"] is False
    serialized = str(body).lower()
    assert "api_key" not in serialized
    assert "database_url" not in serialized
    assert "password" not in serialized
    assert "using stub" not in serialized
