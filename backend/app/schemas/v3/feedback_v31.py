"""Owner-approved R1 V3.1 DTOs; qualified fields reused from PR164."""
from typing import Annotated, Literal
from pydantic import Field, StrictBool, StrictInt, StringConstraints
from .common import V3BaseModel, NonEmptyString, Timestamp
from .feedback import FeedbackV3

Opaque = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Epoch = Annotated[StrictInt, Field(ge=0, le=9223372036854775807)]

class FeedbackConsentFields(V3BaseModel):
    learning_consent: StrictBool = False
    consent_policy_version: NonEmptyString | None = None

class FeedbackV31(FeedbackV3,FeedbackConsentFields):
    schema_version:Literal['feedback_v3.1']
    source_context_id:Opaque
    playback_event_id:Opaque
    expected_evidence_epoch:Epoch
    comment:None=None  # no reversible new text, empty string is not omission


class FeedbackSavedV31(V3BaseModel):
    feedback_id:Opaque
    status:Literal['saved']
    current_feedback_epoch:Epoch
    replayed:bool
    learning_applied:Literal[False]=False


class EvidenceMutationRequest(V3BaseModel):
    expected_evidence_epoch: Epoch


class EvidenceMutationResult(V3BaseModel):
    status: Literal['deleted']
    current_feedback_epoch: Epoch
    feedback_id: Opaque


class EvidenceClearResult(V3BaseModel):
    status: Literal['cleared'] = 'cleared'
    operation_id: Opaque
    cutoff: 'Timestamp'
    resulting_feedback_epoch: Epoch



from .feedback import PreStateSnapshot, PostState, FeedbackExperience, AdjustmentPreference
from .music import MusicRef

class FeedbackReadV31(V3BaseModel):
    schema_version:Literal['feedback_record_v3.1']='feedback_record_v3.1'
    feedback_id:Opaque
    session_id:Opaque
    music_ref:MusicRef
    source_context_id:Opaque|None
    playback_event_id:Opaque|None
    pre_state_snapshot:PreStateSnapshot|None
    post_state:PostState|None
    experience:FeedbackExperience|None
    continue_use:Literal['yes','maybe','no']|None
    liked_features:list[str]
    adjustment_preferences:list[AdjustmentPreference]
    favorite_current:bool|None
    learning_consent:bool
    consent_policy_version:Opaque|None
    consented_at:Timestamp|None
    evidence_epoch:Epoch|None
    submitted_at:Timestamp
    comment_visibility:Literal['not_supported','legacy_unrecoverable']
    learning_effective:Literal[False]=False


class FeedbackPageV31(V3BaseModel):
    items:list[FeedbackReadV31]
    total:Annotated[int,Field(ge=0)]
    next_cursor:Annotated[str,Field(max_length=4096)]|None
    current_feedback_epoch:Epoch


