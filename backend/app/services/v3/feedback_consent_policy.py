"""Pure, server-owned PF-1B consent policy decision (not a public API)."""

from dataclasses import dataclass
from datetime import datetime, timedelta


class ConsentPolicyUnavailable(ValueError):
    """No well-formed active policy can authorize consent."""


class ConsentPolicyMismatch(ValueError):
    """The echoed policy is not the active policy."""


@dataclass(frozen=True)
class ConsentDecision:
    learning_consent: bool
    policy_version: str | None
    consented_at: datetime | None


def resolve_consent_policy(
    *, consent: bool, echoed_version: str | None,
    active_version: str | None, now_utc: datetime,
) -> ConsentDecision:
    if not consent:
        return ConsentDecision(False, None, None)

    if not active_version or not active_version.strip() or active_version != active_version.strip():
        raise ConsentPolicyUnavailable("active consent policy unavailable")
    if echoed_version != active_version:
        raise ConsentPolicyMismatch("consent policy version mismatch")
    if now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError("consent timestamp must be timezone-aware UTC")
    return ConsentDecision(True, active_version, now_utc)
