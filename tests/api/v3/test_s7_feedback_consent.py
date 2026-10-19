"""PF-1B Phase A: consent is explicit and strictly parsed."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.v3.feedback_v31 import FeedbackConsentFields
from backend.app.services.v3.feedback_consent_policy import (
    ConsentPolicyMismatch,
    ConsentPolicyUnavailable,
    resolve_consent_policy,
)


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


def test_false_does_not_require_policy():
    result = resolve_consent_policy(
        consent=False,
        echoed_version="old-version",
        active_version=None,
        now_utc=datetime(2026, 10, 19, tzinfo=timezone.utc),
    )
    assert (result.learning_consent, result.policy_version, result.consented_at) == (
        False, None, None,
    )


def test_true_requires_exact_active_policy():
    now = datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)
    result = resolve_consent_policy(
        consent=True, echoed_version="policy-r1", active_version="policy-r1", now_utc=now,
    )
    assert (result.learning_consent, result.policy_version, result.consented_at) == (
        True, "policy-r1", now,
    )


@pytest.mark.parametrize("active", [None, "", " ", " policy-r1 "])
def test_true_rejects_missing_or_malformed_active_policy(active):
    with pytest.raises(ConsentPolicyUnavailable):
        resolve_consent_policy(
            consent=True, echoed_version="policy-r1", active_version=active,
            now_utc=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("echoed", [None, "", "old-version", " policy-r1 "])
def test_true_rejects_missing_or_mismatched_echo(echoed):
    with pytest.raises(ConsentPolicyMismatch):
        resolve_consent_policy(
            consent=True, echoed_version=echoed, active_version="policy-r1",
            now_utc=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("now", [
    datetime(2026, 10, 19),
    datetime(2026, 10, 19, tzinfo=timezone(timedelta(hours=8))),
])
def test_true_rejects_non_utc_consent_time(now):
    with pytest.raises(ValueError):
        resolve_consent_policy(
            consent=True, echoed_version="policy-r1", active_version="policy-r1",
            now_utc=now,
        )
