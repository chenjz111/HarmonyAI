"""Agent 4 music generation task service.

Manages GenerationTask / MusicAsset rows with a monotonic, terminal-only
state machine, per-user idempotency, explicit reviewed fallback, and a
controlled /api/v3/music/assets/{id}/stream surface. Private provider task
ids and asset locators are never returned to clients.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import os
import uuid

from sqlalchemy.orm import Session

from backend.ai_engine.v3.music_provider import (
    MusicGenerationProvider,
    MusicProviderFailureV3,
    build_matched_fallback_task,
    map_provider_task_to_music_task,
)
from backend.app.models.v3.music import GenerationTask, MusicAsset
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.models.v3.session import V3IdempotencyRecord
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.music import (
    AudioAsset,
    CancelledMusicTask,
    FailedMusicTask,
    MatchedFallbackMusicTask,
    MusicFallback,
    MusicGenerationV3Request,
    MusicProgress,
    MusicRef,
    MusicTask,
    ProviderMusicRequest,
    QueuedMusicTask,
    RunningMusicTask,
    SucceededMusicTask,
)
from backend.app.schemas.v3.prescription import GenerationSpec

_OPERATION = "create_music_generation"
_POLL_AFTER_MS = 2000

_TERMINAL_STATUSES = {
    "succeeded",
    "matched_fallback",
    "failed",
    "cancelled",
}

_NO_FALLBACK = MusicFallback(applied=False, reason_code=None)

# Same public provider-error vocabulary as music_provider mapping helpers.
_PUBLIC_PROVIDER_ERRORS = {
    "GENERATION_PROVIDER_UNAVAILABLE",
    "GENERATION_PROVIDER_TIMEOUT",
    "GENERATION_PROVIDER_RATE_LIMITED",
    "GENERATION_PROVIDER_AUTH_FAILED",
    "GENERATION_PROVIDER_REJECTED",
}


class IdempotencyConflict(RuntimeError):
    pass


class OwnedResourceNotFound(RuntimeError):
    pass


class GenerationNotAllowed(RuntimeError):
    pass


class GenerationCancelUnsupported(RuntimeError):
    pass


class AssetNotPlayable(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _normalize_error_code(error_code: str | None) -> str:
    if error_code in _PUBLIC_PROVIDER_ERRORS:
        return error_code
    return "GENERATION_PROVIDER_UNAVAILABLE"


def _resolve_asset_path(storage_key: str | None) -> Path | None:
    """Resolve a stored key to a local file; provider locators stay private."""
    if not storage_key:
        return None
    path = Path(storage_key)
    if not path.is_absolute():
        root = Path(os.environ.get("HARMONY_MEDIA_ROOT", "media"))
        path = root / path
    return path if path.is_file() else None


def _locator_checksum(locator: str) -> str:
    if not locator:
        return f"sha256:{'0' * 64}"
    path = Path(locator)
    if path.is_file():
        return f"sha256:{sha256(path.read_bytes()).hexdigest()}"
    return f"sha256:{sha256(locator.encode('utf-8')).hexdigest()}"


def _message_for_status(status: str) -> str:
    return {
        "queued": "音乐生成任务已排队",
        "running": "正在生成音乐",
        "succeeded": "音乐已生成",
        "matched_fallback": "生成服务暂时不可用，已使用审核曲库匹配",
        "failed": "音乐生成服务暂时不可用",
        "cancelled": "音乐生成任务已取消",
    }[status]


def _audio_asset_from_row(row: MusicAsset) -> AudioAsset:
    return AudioAsset(
        music_ref=MusicRef(
            music_id=row.music_asset_id,
            source_type=row.source_type,
        ),
        title=row.title,
        stream_url=f"/api/v3/music/assets/{row.music_asset_id}/stream",
        duration_seconds=row.duration_seconds,
        format=row.format,
        checksum=row.checksum,
        tone_profile=row.tone_profile_json,
        bpm=row.bpm,
        instruments=row.instruments_json,
    )


def _progress_from_db(task: GenerationTask) -> MusicProgress | None:
    if task.progress_value is not None:
        return MusicProgress(
            value=task.progress_value,
            semantics="provider_reported_percent",
            indeterminate=False,
        )
    return None


def _find_owned_task(
    db: Session,
    principal: AuthPrincipal,
    task_id: str,
) -> GenerationTask:
    task = db.query(GenerationTask).filter(
        GenerationTask.task_id == task_id,
        GenerationTask.internal_user_pk == principal.internal_user_pk,
    ).one_or_none()
    if task is None:
        raise OwnedResourceNotFound
    return task


def _find_owned_asset(
    db: Session,
    principal: AuthPrincipal,
    music_id: str,
) -> MusicAsset:
    asset = db.query(MusicAsset).filter(
        MusicAsset.music_asset_id == music_id,
        (MusicAsset.owner_internal_user_pk == principal.internal_user_pk)
        | (MusicAsset.owner_internal_user_pk.is_(None)),
    ).one_or_none()
    if asset is None:
        raise OwnedResourceNotFound
    return asset


def _find_matched_asset(db: Session, principal: AuthPrincipal) -> MusicAsset | None:
    candidates = (
        db.query(MusicAsset)
        .filter(
            MusicAsset.source_type == "matched",
            MusicAsset.playable_status == "ready",
            (MusicAsset.owner_internal_user_pk == principal.internal_user_pk)
            | (MusicAsset.owner_internal_user_pk.is_(None)),
        )
        .order_by(MusicAsset.created_at)
        .all()
    )
    for candidate in candidates:
        if candidate.bpm is not None and candidate.instruments_json:
            return candidate
    return None


def _spec_for_task(db: Session, task: GenerationTask) -> GenerationSpec:
    prescription = db.query(PrescriptionV3).filter(
        PrescriptionV3.prescription_id == task.prescription_id
    ).one_or_none()
    if prescription is None or prescription.generation_spec_json is None:
        raise RuntimeError("prescription generation_spec unavailable")
    return GenerationSpec.model_validate(prescription.generation_spec_json)


def _persist_generated_asset(
    db: Session,
    principal_pk: int,
    task_id: str,
    provider_task,
    spec: GenerationSpec,
) -> MusicAsset:
    locator = provider_task.asset_locator or ""
    row = MusicAsset(
        music_asset_id=f"asset_{uuid.uuid4().hex}",
        owner_internal_user_pk=principal_pk,
        generation_task_id=task_id,
        source_type="generated",
        title=f"生成音频 {spec.bpm} BPM",
        storage_key=locator,
        format="mp3",
        duration_seconds=spec.duration_seconds,
        checksum=_locator_checksum(locator),
        tone_profile_json=spec.tone_profile.model_dump(mode="json"),
        bpm=spec.bpm,
        instruments_json=spec.instruments,
        playable_status="ready",
    )
    db.add(row)
    db.flush()
    return row


def _persist_task_outcome(
    db: Session,
    task: GenerationTask,
    music_task: MusicTask,
    provider_task_id: str | None,
) -> None:
    task.status = music_task.status
    task.progress_value = (
        music_task.progress.value
        if music_task.progress is not None
        and not music_task.progress.indeterminate
        else None
    )
    task.progress_indeterminate = int(
        music_task.progress.indeterminate if music_task.progress is not None else True
    )
    task.message_code = f"gen.{music_task.status}"
    task.fallback_applied = int(music_task.fallback.applied)
    task.fallback_reason_code = music_task.fallback.reason_code
    task.error_code = music_task.error_code
    task.provider_task_id = provider_task_id
    if music_task.audio_asset is not None:
        task.music_asset_id = music_task.audio_asset.music_ref.music_id
    if music_task.status in _TERMINAL_STATUSES:
        task.completed_at = _utc_now()
    db.flush()


def _apply_provider_task(
    db: Session,
    principal_pk: int,
    task: GenerationTask,
    provider_task,
) -> MusicTask:
    if provider_task.status == "succeeded":
        asset_row = None
        if task.music_asset_id is not None:
            asset_row = db.query(MusicAsset).filter(
                MusicAsset.music_asset_id == task.music_asset_id
            ).one_or_none()
        if asset_row is None:
            asset_row = _persist_generated_asset(
                db,
                principal_pk,
                task.task_id,
                provider_task,
                _spec_for_task(db, task),
            )
        generated = _audio_asset_from_row(asset_row)
        music_task = map_provider_task_to_music_task(
            task_id=task.task_id,
            provider_task=provider_task,
            generated_asset=generated,
        )
    else:
        music_task = map_provider_task_to_music_task(
            task_id=task.task_id,
            provider_task=provider_task,
            generated_asset=None,
        )
    _persist_task_outcome(
        db,
        task,
        music_task,
        provider_task.provider_task_id,
    )
    return music_task


def _try_fallback(
    db: Session,
    principal: AuthPrincipal,
    task_id: str,
    request: MusicGenerationV3Request,
    provider_error_code: str,
) -> MusicTask | None:
    fallback_allowed = (
        request.provider_policy.fallback == "local_matching"
        and request.generation_spec.fallback_policy.allow_local_matching
    )
    if not fallback_allowed:
        return None
    matched_row = _find_matched_asset(db, principal)
    if matched_row is None:
        return None
    matched = _audio_asset_from_row(matched_row)
    return build_matched_fallback_task(
        task_id=task_id,
        request=request,
        reason_code=provider_error_code,
        matched_asset=matched,
    )


def _failed_music_task(task_id: str, error_code: str) -> MusicTask:
    return FailedMusicTask(
        task_id=task_id,
        status="failed",
        progress=None,
        message="音乐生成服务暂时不可用",
        poll_after_ms=None,
        audio_asset=None,
        fallback=_NO_FALLBACK,
        error_code=_normalize_error_code(error_code),
    )


def _music_task_from_db(
    db: Session,
    task: GenerationTask,
) -> MusicTask:
    status = task.status
    if status == "queued":
        return QueuedMusicTask(
            task_id=task.task_id,
            status="queued",
            progress=None,
            message=_message_for_status(status),
            poll_after_ms=_POLL_AFTER_MS,
            audio_asset=None,
            fallback=_NO_FALLBACK,
            error_code=None,
        )
    if status == "running":
        return RunningMusicTask(
            task_id=task.task_id,
            status="running",
            progress=_progress_from_db(task),
            message=_message_for_status(status),
            poll_after_ms=_POLL_AFTER_MS,
            audio_asset=None,
            fallback=_NO_FALLBACK,
            error_code=None,
        )
    if status in {"succeeded", "matched_fallback"}:
        asset_row = db.query(MusicAsset).filter(
            MusicAsset.music_asset_id == task.music_asset_id
        ).one_or_none()
        if asset_row is None:
            return _failed_music_task(task.task_id, "GENERATION_PROVIDER_UNAVAILABLE")
        audio = _audio_asset_from_row(asset_row)
        if status == "matched_fallback":
            return MatchedFallbackMusicTask(
                task_id=task.task_id,
                status="matched_fallback",
                progress=MusicProgress(
                    value=100,
                    semantics="completed",
                    indeterminate=False,
                ),
                message=_message_for_status(status),
                poll_after_ms=None,
                audio_asset=audio,
                fallback=MusicFallback(
                    applied=True,
                    reason_code=task.fallback_reason_code,
                ),
                error_code=None,
            )
        return SucceededMusicTask(
            task_id=task.task_id,
            status="succeeded",
            progress=MusicProgress(
                value=100,
                semantics="completed",
                indeterminate=False,
            ),
            message=_message_for_status(status),
            poll_after_ms=None,
            audio_asset=audio,
            fallback=_NO_FALLBACK,
            error_code=None,
        )
    if status == "failed":
        return FailedMusicTask(
            task_id=task.task_id,
            status="failed",
            progress=None,
            message=_message_for_status(status),
            poll_after_ms=None,
            audio_asset=None,
            fallback=_NO_FALLBACK,
            error_code=task.error_code or "GENERATION_PROVIDER_UNAVAILABLE",
        )
    return CancelledMusicTask(
        task_id=task.task_id,
        status="cancelled",
        progress=None,
        message=_message_for_status("cancelled"),
        poll_after_ms=None,
        audio_asset=None,
        fallback=_NO_FALLBACK,
        error_code=None,
    )


def create_generation_task(
    db: Session,
    principal: AuthPrincipal,
    request: MusicGenerationV3Request,
    provider: MusicGenerationProvider,
) -> tuple[MusicTask, bool]:
    prescription = db.query(PrescriptionV3).filter(
        PrescriptionV3.prescription_id == request.prescription_id,
        PrescriptionV3.internal_user_pk == principal.internal_user_pk,
    ).one_or_none()
    if prescription is None:
        raise OwnedResourceNotFound
    if prescription.status not in {"success", "degraded"}:
        raise GenerationNotAllowed

    request_hash = _request_hash(request.model_dump(mode="json"))
    record = db.query(V3IdempotencyRecord).filter(
        V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
        V3IdempotencyRecord.operation == _OPERATION,
        V3IdempotencyRecord.idempotency_key == request.idempotency_key,
    ).one_or_none()
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded" and record.resource_id:
            existing = _find_owned_task(db, principal, record.resource_id)
            return _music_task_from_db(db, existing), True

    task_id = f"mtask_{uuid.uuid4().hex}"
    if record is None:
        record = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
            operation=_OPERATION,
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(record)

    task = GenerationTask(
        task_id=task_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=prescription.session_row_id,
        prescription_id=request.prescription_id,
        idempotency_key=request.idempotency_key,
        status="queued",
        progress_indeterminate=0,
        message_code="gen.queued",
        fallback_applied=0,
    )
    db.add(task)
    db.flush()

    provider_request = ProviderMusicRequest(
        provider_request_id=f"pr_{task_id}",
        generation_spec=request.generation_spec,
        output_format="mp3",
        callback_ref=None,
    )
    provider_task_id: str | None = None
    try:
        provider_task = provider.create_task(provider_request)
        provider_task_id = provider_task.provider_task_id
        music_task = _apply_provider_task(
            db,
            principal.internal_user_pk,
            task,
            provider_task,
        )
    except MusicProviderFailureV3 as error:
        fallback_task = _try_fallback(
            db,
            principal,
            task_id,
            request,
            error.error_code,
        )
        if fallback_task is not None:
            music_task = fallback_task
        else:
            music_task = _failed_music_task(task_id, error.error_code)
        _persist_task_outcome(db, task, music_task, None)

    record.resource_type = "generation_task"
    record.resource_id = task_id
    record.status = "succeeded"
    record.response_code = 201
    db.commit()
    return _music_task_from_db(db, task), False


def get_generation_task(
    db: Session,
    principal: AuthPrincipal,
    task_id: str,
    provider: MusicGenerationProvider,
) -> MusicTask:
    task = _find_owned_task(db, principal, task_id)
    if task.status in _TERMINAL_STATUSES:
        return _music_task_from_db(db, task)
    if task.provider_task_id is None:
        return _music_task_from_db(db, task)
    try:
        provider_task = provider.get_task(task.provider_task_id)
        music_task = _apply_provider_task(
            db,
            principal.internal_user_pk,
            task,
            provider_task,
        )
        db.commit()
        return music_task
    except MusicProviderFailureV3:
        db.rollback()
        return _music_task_from_db(db, task)


def cancel_generation_task(
    db: Session,
    principal: AuthPrincipal,
    task_id: str,
    provider: MusicGenerationProvider,
) -> MusicTask:
    task = _find_owned_task(db, principal, task_id)
    if task.status in _TERMINAL_STATUSES:
        return _music_task_from_db(db, task)
    if task.provider_task_id is None:
        task.status = "cancelled"
        task.message_code = "gen.cancelled"
        task.completed_at = _utc_now()
        db.commit()
        return _music_task_from_db(db, task)
    try:
        provider_task = provider.cancel_task(task.provider_task_id)
    except MusicProviderFailureV3 as error:
        if error.error_code == "GENERATION_CANCEL_UNSUPPORTED":
            raise GenerationCancelUnsupported from None
        raise
    music_task = _apply_provider_task(
        db,
        principal.internal_user_pk,
        task,
        provider_task,
    )
    db.commit()
    return music_task


def get_playable_asset_stream_path(
    db: Session,
    principal: AuthPrincipal,
    music_id: str,
) -> tuple[MusicAsset, Path]:
    asset = _find_owned_asset(db, principal, music_id)
    if asset.playable_status != "ready":
        raise AssetNotPlayable
    path = _resolve_asset_path(asset.storage_key)
    if path is None:
        raise AssetNotPlayable
    return asset, path
