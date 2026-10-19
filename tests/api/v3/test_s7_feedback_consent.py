"""PF-1B Phase A: consent is explicit and strictly parsed."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.v3.feedback_v31 import FeedbackConsentFields


def test_consent_defaults_false_and_accepts_literal_booleans():
    assert FeedbackConsentFields().learning_consent is False
    assert FeedbackConsentFields(learning_consent=True).learning_consent is True
    assert FeedbackConsentFields(learning_consent=False).learning_consent is False


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false"])
def test_consent_rejects_coerced_values(value):
    with pytest.raises(ValidationError):
        FeedbackConsentFields(learning_consent=value)


def test_consent_rejects_extra_fields():
    with pytest.raises(ValidationError):
        FeedbackConsentFields(learning_consent=False, unapproved_field="x")
