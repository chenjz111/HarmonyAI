"""Explicit H5 candidate composition, not a production-origin activation."""
from tests.integration.s7_backend_stdio import serve_journey


def test_h5_account_journey(tmp_path,monkeypatch):
    serve_journey(tmp_path,monkeypatch,browser=True)
