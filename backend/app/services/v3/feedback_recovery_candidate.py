"""Read-only candidate, not registered as an HTTP route or a release feature.

A matching record does not prove equality with an unavailable original body;
absence never proves that an in-flight request will not commit later.
"""
from dataclasses import dataclass
from typing import Literal
from sqlalchemy import select
from backend.app.models.v3.feedback import FeedbackV3
from backend.app.models.v3.music_library import MusicPlaybackEvent
from backend.app.models.v3.music import GenerationTask


@dataclass(frozen=True)
class RecoveryStatus:
    status: Literal['unknown','record_present_unverified','deleted']


def read_recovery_status(db, *, principal, idempotency_key, music_id, source_context_id, playback_event_id):
    if not all(isinstance(value,str) and value and value.strip()==value for value in (idempotency_key,music_id,source_context_id,playback_event_id)):
        return RecoveryStatus('unknown')
    with db.no_autoflush:
        row=db.execute(select(FeedbackV3.deleted_at).join(
            MusicPlaybackEvent,FeedbackV3.playback_event_row_id==MusicPlaybackEvent.playback_event_row_id
        ).join(GenerationTask,FeedbackV3.source_task_id==GenerationTask.task_id
        ).where(FeedbackV3.internal_user_pk==principal.internal_user_pk,
            FeedbackV3.idempotency_key==idempotency_key,
            FeedbackV3.music_asset_id==music_id,FeedbackV3.source_task_id==source_context_id,
            FeedbackV3.request_fingerprint.is_not(None),
            GenerationTask.internal_user_pk==principal.internal_user_pk,
            GenerationTask.session_row_id==FeedbackV3.session_row_id,
            GenerationTask.music_asset_id==music_id,
            MusicPlaybackEvent.internal_user_pk==principal.internal_user_pk,
            MusicPlaybackEvent.music_asset_id==music_id,
            MusicPlaybackEvent.source_context_id==source_context_id,
            MusicPlaybackEvent.event_id==playback_event_id)).one_or_none()
    if row is None:return RecoveryStatus('unknown')
    return RecoveryStatus('deleted' if row.deleted_at is not None else 'record_present_unverified')
