"""Internal PF-1B consent fragment; not a registered public request DTO."""

from pydantic import StrictBool

from .common import NonEmptyString, V3BaseModel


class FeedbackConsentFields(V3BaseModel):
    learning_consent: StrictBool = False
    consent_policy_version: NonEmptyString | None = None
