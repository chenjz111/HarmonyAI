"""Qualified PR164 fingerprint/content checks; no duplicate Proof/CAS authority."""
import json
from backend.app.schemas.v3.feedback_v31 import FeedbackV31, FeedbackSavedV31
from .feedback_request_fingerprint import fingerprint_feedback_request

class EvidenceEpochConflict(RuntimeError): pass
class PlaybackProofUnavailable(RuntimeError): pass
class FeedbackGone(RuntimeError): pass
class LegacyFingerprintUnavailable(RuntimeError): pass
class FeedbackFingerprintConflict(RuntimeError): pass
class FeedbackContentUnverified(RuntimeError): pass

def request_fingerprint(request):
    if type(request) is not FeedbackV31:raise TypeError('validated exact V3.1 DTO required')
    payload=request.model_dump(mode='json')
    # Consent=false has no effective policy claim. Selection order is not intent.
    if not request.learning_consent:payload['consent_policy_version']=None
    for field in ('liked_features','adjustment_preferences'):payload[field]=sorted(payload[field])
    return fingerprint_feedback_request(payload)


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


