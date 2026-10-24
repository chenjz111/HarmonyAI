"""Owner-scoped public projection and domain-separated signed pagination."""
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import json

from sqlalchemy import select, func, or_, and_
from backend.app.models.session import Session as ConversationSession
from backend.app.models.v3 import FeedbackV3, Favorite, MusicAsset, MusicPlaybackEvent, OwnerMusicState
from backend.app.schemas.v3.feedback_v31 import FeedbackReadV31, FeedbackPageV31
from .feedback_v31_contract import FeedbackContentUnverified
from .feedback_v31_queries import get_owned_feedback, visible_feedback_query
from .music_library_service import _cursor_secret


class FeedbackCursorStale(ValueError): pass


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def lock_read_epoch(db, owner):
    state = db.scalar(select(OwnerMusicState).where(OwnerMusicState.owner_internal_user_pk == owner)
                      .with_for_update().execution_options(populate_existing=True))
    return int(state.feedback_evidence_epoch) if state is not None else 0


def project_feedback(db, principal, row):
    session_id = db.scalar(select(ConversationSession.session_id).where(
        ConversationSession.id == row.session_row_id, ConversationSession.user_id == principal.internal_user_pk))
    source = db.scalar(select(MusicAsset.source_type).where(MusicAsset.music_asset_id == row.music_asset_id))
    if session_id is None or source is None:
        raise FeedbackContentUnverified('owned historical source unavailable')
    event_id = None
    if row.playback_event_row_id is not None:
        event_id = db.scalar(select(MusicPlaybackEvent.event_id).where(
            MusicPlaybackEvent.playback_event_row_id == row.playback_event_row_id,
            MusicPlaybackEvent.internal_user_pk == principal.internal_user_pk,
            MusicPlaybackEvent.music_asset_id == row.music_asset_id,
            MusicPlaybackEvent.source_context_id == row.source_task_id))
    favorite = db.scalar(select(Favorite.favorite_id).where(Favorite.internal_user_pk == principal.internal_user_pk,
                                                          Favorite.music_asset_id == row.music_asset_id)) is not None
    try:
        return FeedbackReadV31(feedback_id=row.feedback_id, session_id=session_id,
            music_ref={'music_id':row.music_asset_id,'source_type':source},
            source_context_id=row.source_task_id, playback_event_id=event_id,
            pre_state_snapshot=row.pre_state_snapshot_json, post_state=row.post_state_json,
            experience=row.experience_json, continue_use=row.continue_use,
            liked_features=row.liked_features_json, adjustment_preferences=row.adjustment_preferences_json,
            favorite_current=favorite, learning_consent=bool(row.learning_consent),
            consent_policy_version=row.consent_policy_version,
            consented_at=_utc(row.consented_at) if row.consented_at else None,
            evidence_epoch=row.evidence_epoch, submitted_at=_utc(row.created_at),
            comment_visibility='legacy_unrecoverable' if row.comment_ciphertext else 'not_supported')
    except (TypeError, ValueError) as error:
        raise FeedbackContentUnverified('historical feedback projection invalid') from error


def _encode(value):
    payload = json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    signature = hmac.new(_cursor_secret(), b'feedback_v31\0'+payload,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload).decode().rstrip('=')+'.'+base64.urlsafe_b64encode(signature).decode().rstrip('=')


def _decode(cursor):
    try:
        if len(cursor) > 4096:
            raise ValueError
        encoded, signature = cursor.split('.')
        payload = base64.b64decode(encoded+'='*(-len(encoded)%4),altchars=b'-_',validate=True)
        signed = base64.b64decode(signature+'='*(-len(signature)%4),altchars=b'-_',validate=True)
        if not hmac.compare_digest(signed,hmac.new(_cursor_secret(),b'feedback_v31\0'+payload,hashlib.sha256).digest()):
            raise ValueError
        value = json.loads(payload)
        if set(value) != {'v','owner','epoch','music','at','id'} or value['v'] != 1:
            raise ValueError
        return value
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise FeedbackCursorStale from error


def read_page(db, *, principal, limit=20, cursor=None, music_id=None):
    epoch = lock_read_epoch(db,principal.internal_user_pk)
    visible = visible_feedback_query(principal,music_id=music_id)
    total = int(db.scalar(select(func.count()).select_from(visible.subquery())))
    query = visible
    if cursor:
        value = _decode(cursor)
        if value['owner'] != principal.internal_user_pk or value['epoch'] != epoch or value['music'] != music_id:
            raise FeedbackCursorStale
        try:
            boundary = datetime.fromisoformat(value['at'])
        except (ValueError, TypeError) as error:
            raise FeedbackCursorStale from error
        query = query.where(or_(FeedbackV3.created_at < boundary,
            and_(FeedbackV3.created_at == boundary, FeedbackV3.feedback_id < value['id'])))
    rows = list(db.scalars(query.order_by(FeedbackV3.created_at.desc(),FeedbackV3.feedback_id.desc()).limit(limit+1)))
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit-1]
        next_cursor = _encode(dict(v=1,owner=principal.internal_user_pk,epoch=epoch,music=music_id,
                                   at=_utc(last.created_at).isoformat(),id=last.feedback_id))
    return FeedbackPageV31(items=[project_feedback(db,principal,row) for row in rows[:limit]],
                           total=total,next_cursor=next_cursor,current_feedback_epoch=epoch)


def read_detail(db, *, principal, feedback_id):
    lock_read_epoch(db, principal.internal_user_pk)
    return project_feedback(db,principal,get_owned_feedback(db,principal=principal,feedback_id=feedback_id))
