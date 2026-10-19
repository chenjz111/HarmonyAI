"""PF-1B Phase A: canonical fingerprints only expose a digest."""

import re

import pytest

from backend.app.schemas.v3.feedback_v31 import FeedbackConsentFields
from backend.app.services.v3.feedback_request_fingerprint import fingerprint_feedback_request


def test_fingerprint_ignores_mapping_order_and_normalized_default():
    first = {"context": {"music_id": "music-a", "source": "saved"}, "rating": 4}
    second = {"rating": 4, "context": {"source": "saved", "music_id": "music-a"}}
    assert fingerprint_feedback_request(first) == fingerprint_feedback_request(second)
    omitted = FeedbackConsentFields().model_dump(mode="json")
    explicit = FeedbackConsentFields(learning_consent=False).model_dump(mode="json")
    assert fingerprint_feedback_request(omitted) == fingerprint_feedback_request(explicit)


def test_fingerprint_changes_with_payload_and_never_returns_text():
    private_text = "synthetic private content that must never appear in digest"
    baseline = {"context": {"music_id": "music-a"}, "comment": private_text,
                "learning_consent": False}
    digest = fingerprint_feedback_request(baseline)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    assert private_text not in digest
    assert digest != fingerprint_feedback_request({**baseline, "learning_consent": True})
    assert digest != fingerprint_feedback_request({**baseline, "context": {"music_id": "music-b"}})


@pytest.mark.parametrize("payload, error", [
    ({"rating": float("nan")}, ValueError),
    ({"rating": object()}, TypeError),
])
def test_fingerprint_rejects_non_json_payload(payload, error):
    with pytest.raises(error):
        fingerprint_feedback_request(payload)
