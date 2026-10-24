"""Phase B review seams, not routes or a second Preference implementation.

Phase A modules are byte-identical explicit dependencies from PR164. Write
helpers participate in the caller transaction; no commit or retry is hidden.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta
from typing import Annotated,Literal
import re
import json
from pydantic import Field,StrictInt,StringConstraints
from sqlalchemy import select
from backend.app.schemas.v3.common import AuthPrincipal,V3BaseModel,Timestamp
from backend.app.schemas.v3.feedback import FeedbackV3,PreStateSnapshot,PostState,FeedbackExperience,AdjustmentPreference
from backend.app.schemas.v3.music import MusicRef
from backend.app.schemas.v3.feedback_v31 import FeedbackConsentFields
from backend.app.services.v3.feedback_consent_policy import resolve_consent_policy,ConsentPolicyUnavailable
from backend.app.services.v3.feedback_request_fingerprint import fingerprint_feedback_request
from backend.app.services.v3.music_library_access import require_library_access,resolve_feedback_context,LibraryAccessDenied,FeedbackContextUnavailable
from backend.app.services.v3.owner_music_state_service import lock_owner_music_state,advance_feedback_epoch
from backend.app.models.v3.music import GenerationTask
from backend.app.models.v3.music_library import MusicPlaybackEvent
from backend.app.models.session import Session as ConversationSession

Opaque=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=64)]
Epoch=Annotated[StrictInt,Field(ge=0,le=9223372036854775807)]


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


class EvidenceMutationRequest(V3BaseModel):
    expected_evidence_epoch:Epoch


class EvidenceMutationResult(V3BaseModel):
    status:Literal['deleted','cleared']
    current_feedback_epoch:Epoch
    feedback_id:Opaque|None=None
    cutoff:Timestamp|None=None


def request_fingerprint(request):
    if type(request) is not FeedbackV31:raise TypeError('validated exact V3.1 DTO required')
    payload=request.model_dump(mode='json')
    # Consent=false has no effective policy claim. Selection order is not intent.
    if not request.learning_consent:payload['consent_policy_version']=None
    for field in ('liked_features','adjustment_preferences'):payload[field]=sorted(payload[field])
    return fingerprint_feedback_request(payload)


@dataclass(frozen=True)
class PolicySnapshot:
    version:str
    body_sha256:str
    approval_ref:str
    effective_at:datetime
    revoked_at:datetime|None


def _utc(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset()!=timedelta(0):
        raise ValueError('server timezone-aware UTC required')


def _active_policy(policy,now_utc):
    _utc(now_utc)
    if type(policy) is not PolicySnapshot:raise ConsentPolicyUnavailable('approved server policy unavailable')
    _utc(policy.effective_at)
    if policy.revoked_at is not None:_utc(policy.revoked_at)
    if (not re.fullmatch('[0-9a-f]{64}',policy.body_sha256) or not policy.approval_ref.strip()
        or len(policy.version)>64 or policy.effective_at>now_utc
        or (policy.revoked_at is not None and policy.revoked_at<=now_utc)):
        raise ConsentPolicyUnavailable('policy inactive, unapproved or revoked')
    return policy.version


def consent_decision(request,policy,now_utc):
    if type(request) is not FeedbackV31:raise TypeError('validated DTO required')
    active=_active_policy(policy,now_utc) if request.learning_consent else None
    return resolve_consent_policy(consent=request.learning_consent,echoed_version=request.consent_policy_version,
        active_version=active,now_utc=now_utc)


class PlaybackProofUnavailable(RuntimeError):pass
class EvidenceEpochConflict(RuntimeError):pass
class FeedbackGone(RuntimeError):pass
class LegacyFingerprintUnavailable(RuntimeError):pass
class FeedbackFingerprintConflict(RuntimeError):pass
class FeedbackContentUnverified(RuntimeError):pass


@dataclass(frozen=True)
class PlaybackProof:
    playback_event_row_id:int
    playback_event_id:str
    internal_user_pk:int
    music_asset_id:str
    source_context_id:str
    session_row_id:int
    occurred_at:datetime


def resolve_feedback_playback_proof(db,*,principal:AuthPrincipal,music_id,source_context_id,playback_event_id,session_id):
    """Read-only, same caller transaction; public event_id != internal row PK.

    First use existing Backend authority, then require the SPECIFIED event and
    task/session. No latest-event, NULL-context or Favorite substitution.
    """
    try:
        require_library_access(db,internal_user_pk=principal.internal_user_pk,music_id=music_id)
        resolve_feedback_context(db,internal_user_pk=principal.internal_user_pk,music_id=music_id,context_id=source_context_id)
    except (LibraryAccessDenied,FeedbackContextUnavailable):raise PlaybackProofUnavailable from None
    event=db.scalar(select(MusicPlaybackEvent).where(
        MusicPlaybackEvent.internal_user_pk==principal.internal_user_pk,
        MusicPlaybackEvent.event_id==playback_event_id,MusicPlaybackEvent.music_asset_id==music_id,
        MusicPlaybackEvent.source_context_id==source_context_id,MusicPlaybackEvent.event_type=='play_started'))
    task=db.scalar(select(GenerationTask).where(GenerationTask.task_id==source_context_id,
        GenerationTask.internal_user_pk==principal.internal_user_pk,GenerationTask.music_asset_id==music_id,
        GenerationTask.status.in_(('succeeded','matched_fallback'))))
    session_row_id=db.scalar(select(ConversationSession.id).where(ConversationSession.session_id==session_id,
        ConversationSession.user_id==principal.internal_user_pk))
    if event is None or task is None or session_row_id is None or task.session_row_id!=session_row_id:
        raise PlaybackProofUnavailable
    return PlaybackProof(event.playback_event_row_id,event.event_id,principal.internal_user_pk,
        music_id,source_context_id,session_row_id,event.occurred_at)


def verify_persisted_feedback_content(row,request):
    """Check the persisted input projection after flush or before exact replay.

    Not a full-row hash reconstruction: favorite, CAS request and public
    session/event aliases are not stored in Feedback. The caller must still
    validate owned proof/receipt and current candidate Schema in one transaction.
    This mapping must come from the DB, never from the incoming body.
    """
    if type(request) is not FeedbackV31:raise FeedbackContentUnverified('validated request required')
    expected={
        'music_asset_id':request.music_ref.music_id,'source_task_id':request.source_context_id,
        'change_label':request.post_state.change_label,
        'pre_state_snapshot_json':request.pre_state_snapshot.model_dump(mode='json'),
        'post_state_json':request.post_state.model_dump(mode='json'),
        'experience_json':request.experience.model_dump(mode='json') if request.experience else None,
        'continue_use':request.continue_use,'liked_features_json':sorted(request.liked_features),
        'adjustment_preferences_json':sorted(request.adjustment_preferences),
        'comment_ciphertext':None,
        'playback_json':request.playback.model_dump(mode='json') if request.playback else None,
        'learning_consent':int(request.learning_consent),
        'consent_policy_version':request.consent_policy_version if request.learning_consent else None,
        'evidence_epoch':request.expected_evidence_epoch,
        'request_fingerprint':request_fingerprint(request),
    }
    try:
        for field,want in expected.items():
            value=row[field]
            if field.endswith('_json'):
                if isinstance(value,str):value=json.loads(value)
                if field in ('liked_features_json','adjustment_preferences_json'):value=sorted(value)
            if json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)!=json.dumps(want,sort_keys=True,ensure_ascii=False,allow_nan=False):
                raise FeedbackContentUnverified('persisted feedback input differs')
    except (KeyError,TypeError,ValueError):raise FeedbackContentUnverified('incomplete or invalid persisted feedback') from None


def replay_decision(*,deleted_at,stored_fingerprint,incoming_fingerprint,persisted_content=None,request=None):
    if deleted_at is not None:raise FeedbackGone('tombstone precedes replay')
    if stored_fingerprint is None:raise LegacyFingerprintUnavailable('legacy intent not provable')
    if stored_fingerprint!=incoming_fingerprint:raise FeedbackFingerprintConflict('idempotency key reused')
    if type(request) is not FeedbackV31 or request_fingerprint(request)!=incoming_fingerprint:
        raise FeedbackContentUnverified('fingerprint equality is not row integrity')
    verify_persisted_feedback_content(persisted_content,request)
    return 'replay'


def lock_expected_epoch(db,*,principal,expected_epoch):
    if type(expected_epoch) is not int or expected_epoch<0:raise EvidenceEpochConflict
    state=lock_owner_music_state(db,internal_user_pk=principal.internal_user_pk)
    if state.feedback_evidence_epoch!=expected_epoch:raise EvidenceEpochConflict
    return state


def clear_evidence(db,*,principal,expected_epoch,now_utc):
    """Isolated transaction contract only: caller owns BEGIN/COMMIT/rollback.

    Preserve profile/current_version_id for history; M1 application stays OFF.
    Same-key clear replay belongs to future route's idempotency receipt protocol.
    """
    _utc(now_utc)
    state=lock_expected_epoch(db,principal=principal,expected_epoch=expected_epoch)
    old=state.preference_clear_cutoff
    if old is not None:
        old=old.replace(tzinfo=now_utc.tzinfo) if old.tzinfo is None else old
        if now_utc<old:raise EvidenceEpochConflict('cutoff must not move backwards')
    state.preference_clear_cutoff=now_utc
    db.flush()
    return advance_feedback_epoch(db,internal_user_pk=principal.internal_user_pk)


def m1_preference_application_enabled():return False


@dataclass(frozen=True)
class EvidenceRecord:
    """Review view constructed from an owned DB row, not an HTTP input DTO."""
    owner:int
    created_at:datetime
    learning_consent:bool
    consent_policy_version:str|None
    deleted_at:datetime|None
    evidence_epoch:int|None


def qualifies_for_future_evidence(record,*,principal,current_epoch,cutoff,policy,now_utc):
    """Future evidence predicate ONLY. M1 application still always disabled.

    Per-row admission epoch is not equal to every later global write epoch.
    Derived-result publish CAS IS exact; cutoff/tombstone/policy deny old rows.
    """
    if (type(record) is not EvidenceRecord or record.owner!=principal.internal_user_pk
        or record.learning_consent is not True or record.deleted_at is not None
        or type(record.evidence_epoch) is not int or type(current_epoch) is not int
        or not 0<=record.evidence_epoch<=current_epoch):return False
    try:
        _utc(record.created_at)
        if record.created_at>now_utc:return False
        if cutoff is not None:
            _utc(cutoff)
            if record.created_at<=cutoff:return False
        active=_active_policy(policy,now_utc)
        resolve_consent_policy(consent=True,echoed_version=record.consent_policy_version,
            active_version=active,now_utc=now_utc)
    except (TypeError,ValueError):return False
    return True
