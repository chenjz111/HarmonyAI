"""Smoke-tool diagnostics — accurate HTTP status without secret leakage.

The Owner smoke ran with 5 credits and the adapter (by design) hides raw HTTP
statuses behind stable error codes, so the failure could only be *suspected* to
be a balance rejection. These tests pin the minimal fix: the smoke tool itself
records the exact status code, content type, body size and JSON-envelope shape
while never capturing the API key, request body or response body text.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_PATH = REPO_ROOT / "tools" / "stability_music_smoke.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("stability_music_smoke_tool", SMOKE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = _load_smoke_module()


class _FakeResponse:
    def __init__(self, *, status_code: int, content: bytes, content_type: str, text: str = ""):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}
        self.text = text


def test_diagnostic_poster_records_accurate_http_status_only():
    secret = "sk-test-stability-secret"
    body = json.dumps({"name": "insufficient_balance", "message": f"key {secret}"})
    captured: dict[str, object] = {}

    def fake_inner(url, *, headers, data, files, timeout):
        captured.update({"headers": headers, "data": data, "files": files})
        return _FakeResponse(
            status_code=402,
            content=body.encode(),
            content_type="application/json",
            text=body,
        )

    poster = smoke._DiagnosticPoster(inner=fake_inner)
    poster("https://example.invalid", headers={}, data={}, files={}, timeout=(1, 2))
    fields = poster.safe_fields()

    assert fields["http_status"] == 402  # exact status is preserved
    assert fields["content_type"] == "application/json"
    assert fields["response_bytes"] == len(body.encode())
    assert fields["response_is_json"] is True
    assert fields["transport_error"] is None

    rendered = json.dumps(fields)
    assert secret not in rendered
    assert "insufficient_balance" not in rendered
    # only safe keys are exported
    assert set(fields) == {
        "http_status",
        "content_type",
        "response_bytes",
        "response_is_json",
        "transport_error",
        "post_count",
    }


def test_diagnostic_poster_records_transport_error_type_only():
    def failing_inner(url, *, headers, data, files, timeout):
        raise requests.Timeout("connect timeout for https://api.stability.ai")

    poster = smoke._DiagnosticPoster(inner=failing_inner)
    with pytest.raises(requests.Timeout):
        poster("https://example.invalid", headers={}, data={}, files={}, timeout=(1, 2))

    fields = poster.safe_fields()
    assert fields["transport_error"] == "Timeout"
    assert fields["http_status"] is None
    assert "connect timeout" not in json.dumps(fields)


def test_check_mode_sends_no_request_and_passes_with_complete_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("MUSIC_PROVIDER", "stability")
    monkeypatch.setenv("MUSIC_PROVIDER_MODEL", "stable-audio-2.5")
    monkeypatch.setenv("STABILITY_API_KEY", "sk-test-stability-secret")
    monkeypatch.setattr(smoke.sys, "argv", ["stability_music_smoke.py", "--check"])

    def _must_not_post(*args, **kwargs):  # pragma: no cover - guard
        raise AssertionError("check mode must not perform any HTTP request")

    monkeypatch.setattr(smoke.requests, "post", _must_not_post)

    assert smoke.main() == 0
    output = capsys.readouterr().out
    assert "no POST will be sent" in output
    assert "readiness=READY" in output
    assert "model,prompt,duration,steps,cfg_scale" in output
    assert "sk-test-stability-secret" not in output


def test_check_mode_fails_without_key(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setenv("MUSIC_PROVIDER", "stability")
    monkeypatch.setenv("MUSIC_PROVIDER_MODEL", "stable-audio-2.5")
    monkeypatch.delenv("STABILITY_API_KEY", raising=False)
    monkeypatch.setattr(smoke.sys, "argv", ["stability_music_smoke.py", "--check"])

    assert smoke.main() == 2
    output = capsys.readouterr().out
    assert "STABILITY_API_KEY_present=False" in output
