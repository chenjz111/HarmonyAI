"""Test-only native router mount; default application source remains closed."""
from tests.integration.s7_backend_stdio import serve_journey


def test_account_journey(tmp_path,monkeypatch):
    serve_journey(tmp_path,monkeypatch,account=True)
