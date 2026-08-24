"""Medical-neutral Agent 4 provider and local-fallback foundation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Protocol

from backend.app.schemas.v3.common import (
    ProviderCapabilities as CoreProviderCapabilities,
    ProviderHealth,
)
from backend.app.schemas.v3.music import (
    AudioAsset,
    CancelledMusicTask,
    FailedMusicTask,
    MatchedFallbackMusicTask,
    MusicFallback,
    MusicGenerationV3Request,
    MusicProgress,
    MusicProviderCapabilities,
    MusicTask,
    ProviderMusicRequest,
    ProviderTask,
    QueuedMusicTask,
    RunningMusicTask,
    SucceededMusicTask,
)


class MusicGenerationProvider(Protocol):
    def create_task(self, request: ProviderMusicRequest) -> ProviderTask: ...

    def get_task(self, provider_task_id: str) -> ProviderTask: ...

    def cancel_task(self, provider_task_id: str) -> ProviderTask: ...

    def health(self) -> ProviderHealth: ...

    def capabilities(self) -> MusicProviderCapabilities: ...


class AsyncMusicGenerationProvider(Protocol):
    async def acreate_task(self, request: ProviderMusicRequest) -> ProviderTask: ...

    async def aget_task(self, provider_task_id: str) -> ProviderTask: ...

    async def acancel_task(self, provider_task_id: str) -> ProviderTask: ...

    def health(self) -> ProviderHealth: ...

    def capabilities(self) -> MusicProviderCapabilities: ...


class MusicProviderFailureV3(RuntimeError):
    """Stable failure safe for service-layer mapping; raw causes stay internal."""

    def __init__(
        self,
        error_code: str,
        *,
        retryable: bool,
        safe_message: str,
        cause: BaseException | None = None,
    ) -> None:
        self.error_code = error_code
        self.retryable = retryable
        self.safe_message = safe_message
        self.cause = cause
        super().__init__(f"{error_code}: {safe_message}")


def validate_provider_request_capabilities(
    request: ProviderMusicRequest,
    capabilities: MusicProviderCapabilities,
) -> None:
    """Reject unsupported generation requests before calling a provider."""

    spec = request.generation_spec
    if spec.duration_seconds > capabilities.max_duration_seconds:
        raise MusicProviderFailureV3(
            "GENERATION_DURATION_UNSUPPORTED",
            retryable=False,
            safe_message="当前生成服务不支持所需音乐时长。",
        )
    unsupported_instruments = set(spec.instruments) - set(
        capabilities.supported_instruments
    )
    if unsupported_instruments:
        raise MusicProviderFailureV3(
            "GENERATION_INSTRUMENT_UNSUPPORTED",
            retryable=False,
            safe_message="当前生成服务不支持所需乐器组合。",
        )
    if request.output_format not in capabilities.supported_formats:
        raise MusicProviderFailureV3(
            "GENERATION_FORMAT_UNSUPPORTED",
            retryable=False,
            safe_message="当前生成服务不支持所需音频格式。",
        )


class ProviderTaskTransitionGuard:
    """Enforce monotonic provider task transitions, especially cancellation."""

    _allowed = {
        "queued": {"queued", "running", "succeeded", "failed", "cancelled"},
        "running": {"running", "succeeded", "failed", "cancelled"},
        "succeeded": {"succeeded"},
        "failed": {"failed"},
        "cancelled": {"cancelled"},
    }

    def __init__(self) -> None:
        self._latest: dict[str, ProviderTask] = {}

    def observe(self, task: ProviderTask) -> ProviderTask:
        previous = self._latest.get(task.provider_task_id)
        if previous is not None:
            if task.status not in self._allowed[previous.status]:
                raise MusicProviderFailureV3(
                    "GENERATION_TASK_STATE_INVALID",
                    retryable=False,
                    safe_message="音乐生成任务状态无效。",
                )
            if (
                previous.progress_value is not None
                and task.progress_value is not None
                and task.progress_value < previous.progress_value
            ):
                raise MusicProviderFailureV3(
                    "GENERATION_TASK_PROGRESS_INVALID",
                    retryable=False,
                    safe_message="音乐生成任务进度无效。",
                )
        self._latest[task.provider_task_id] = task.model_copy(deep=True)
        return task


def build_matched_fallback_task(
    *,
    task_id: str,
    request: MusicGenerationV3Request,
    reason_code: str,
    matched_asset: AudioAsset | None,
) -> MatchedFallbackMusicTask:
    """Build an explicit reviewed-catalog fallback, never fake generation."""

    fallback_allowed = (
        request.provider_policy.fallback == "local_matching"
        and request.generation_spec.fallback_policy.allow_local_matching
    )
    if not fallback_allowed:
        raise MusicProviderFailureV3(
            "GENERATION_FALLBACK_NOT_ALLOWED",
            retryable=False,
            safe_message="当前请求不允许使用曲库匹配。",
        )
    if matched_asset is None:
        raise MusicProviderFailureV3(
            "NO_PLAYABLE_ASSET",
            retryable=False,
            safe_message="当前没有可播放的审核音频。",
        )
    if matched_asset.music_ref.source_type != "matched":
        raise MusicProviderFailureV3(
            "GENERATION_FALLBACK_ASSET_INVALID",
            retryable=False,
            safe_message="曲库匹配结果无效。",
        )
    return MatchedFallbackMusicTask(
        task_id=task_id,
        status="matched_fallback",
        progress=MusicProgress(
            value=100,
            semantics="completed",
            indeterminate=False,
        ),
        message="生成服务暂时不可用，已使用审核曲库匹配",
        poll_after_ms=None,
        audio_asset=matched_asset,
        fallback=MusicFallback(applied=True, reason_code=reason_code),
        error_code=None,
    )


_PUBLIC_PROVIDER_ERRORS = {
    "GENERATION_PROVIDER_UNAVAILABLE",
    "GENERATION_PROVIDER_TIMEOUT",
    "GENERATION_PROVIDER_RATE_LIMITED",
    "GENERATION_PROVIDER_AUTH_FAILED",
    "GENERATION_PROVIDER_REJECTED",
}


def map_provider_task_to_music_task(
    *,
    task_id: str,
    provider_task: ProviderTask,
    generated_asset: AudioAsset | None,
    poll_after_ms: int = 2000,
) -> MusicTask:
    """Map a private Provider task to the public task union without leakage."""

    no_fallback = MusicFallback(applied=False, reason_code=None)
    if provider_task.status == "queued":
        progress = None
        if provider_task.progress_value is not None:
            progress = MusicProgress(
                value=provider_task.progress_value,
                semantics="provider_reported_percent",
                indeterminate=False,
            )
        return QueuedMusicTask(
            task_id=task_id,
            status="queued",
            progress=progress,
            message="音乐生成任务已排队",
            poll_after_ms=poll_after_ms,
            audio_asset=None,
            fallback=no_fallback,
            error_code=None,
        )
    if provider_task.status == "running":
        progress = MusicProgress(
            value=provider_task.progress_value,
            semantics=(
                "provider_reported_percent"
                if provider_task.progress_value is not None
                else "provider_progress_unavailable"
            ),
            indeterminate=provider_task.progress_value is None,
        )
        return RunningMusicTask(
            task_id=task_id,
            status="running",
            progress=progress,
            message="正在生成音乐",
            poll_after_ms=poll_after_ms,
            audio_asset=None,
            fallback=no_fallback,
            error_code=None,
        )
    if provider_task.status == "succeeded":
        if generated_asset is None:
            raise MusicProviderFailureV3(
                "GENERATION_ASSET_NOT_READY",
                retryable=True,
                safe_message="生成结果正在准备，请稍后重试。",
            )
        if generated_asset.music_ref.source_type != "generated":
            raise MusicProviderFailureV3(
                "GENERATION_ASSET_INVALID",
                retryable=False,
                safe_message="生成结果无效。",
            )
        return SucceededMusicTask(
            task_id=task_id,
            status="succeeded",
            progress=MusicProgress(
                value=100,
                semantics="completed",
                indeterminate=False,
            ),
            message="音乐已生成",
            poll_after_ms=None,
            audio_asset=generated_asset,
            fallback=no_fallback,
            error_code=None,
        )
    if provider_task.status == "failed":
        error_code = provider_task.error_code
        if error_code not in _PUBLIC_PROVIDER_ERRORS:
            error_code = "GENERATION_PROVIDER_UNAVAILABLE"
        return FailedMusicTask(
            task_id=task_id,
            status="failed",
            progress=None,
            message="音乐生成服务暂时不可用",
            poll_after_ms=None,
            audio_asset=None,
            fallback=no_fallback,
            error_code=error_code,
        )
    return CancelledMusicTask(
        task_id=task_id,
        status="cancelled",
        progress=None,
        message="音乐生成任务已取消",
        poll_after_ms=None,
        audio_asset=None,
        fallback=no_fallback,
        error_code=None,
    )

def build_safe_music_provider_log_fields(
    *,
    request: ProviderMusicRequest,
    provider: str,
    model: str | None,
    status: str,
    latency_ms: int,
    error_code: str | None,
) -> dict[str, object]:
    """Return operational fields without prompt, spec values or asset locators."""

    canonical_spec = json.dumps(
        request.generation_spec.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "provider_request_id": request.provider_request_id,
        "provider": provider,
        "model": model,
        "output_format": request.output_format,
        "spec_sha256": f"sha256:{sha256(canonical_spec).hexdigest()}",
        "status": status,
        "latency_ms": latency_ms,
        "error_code": error_code,
    }


@dataclass
class MockMusicGenerationProvider:
    """Deterministic test provider; it is never a production success fallback."""

    tasks: list[ProviderTask]
    _capabilities: MusicProviderCapabilities
    failure: MusicProviderFailureV3 | None = None

    def __init__(
        self,
        *,
        tasks: list[ProviderTask],
        capabilities: MusicProviderCapabilities,
        failure: MusicProviderFailureV3 | None = None,
    ) -> None:
        if not tasks and failure is None:
            raise ValueError("mock provider requires tasks or a failure")
        self.tasks = [task.model_copy(deep=True) for task in tasks]
        self._capabilities = capabilities
        self.failure = failure
        self.create_calls = 0
        self.get_calls = 0
        self.cancel_calls = 0
        self._guard = ProviderTaskTransitionGuard()

    def _next(self, index: int) -> ProviderTask:
        if self.failure is not None:
            raise self.failure
        task = self.tasks[min(index, len(self.tasks) - 1)].model_copy(deep=True)
        return self._guard.observe(task)

    def create_task(self, request: ProviderMusicRequest) -> ProviderTask:
        validate_provider_request_capabilities(request, self._capabilities)
        task = self._next(self.create_calls)
        self.create_calls += 1
        return task

    async def acreate_task(self, request: ProviderMusicRequest) -> ProviderTask:
        return self.create_task(request)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        task = self._next(self.get_calls)
        self.get_calls += 1
        if task.provider_task_id != provider_task_id:
            raise MusicProviderFailureV3(
                "GENERATION_TASK_NOT_FOUND",
                retryable=False,
                safe_message="音乐生成任务不存在。",
            )
        return task

    async def aget_task(self, provider_task_id: str) -> ProviderTask:
        return self.get_task(provider_task_id)

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        if not self._capabilities.supports_cancel:
            raise MusicProviderFailureV3(
                "GENERATION_CANCEL_UNSUPPORTED",
                retryable=False,
                safe_message="当前生成服务不支持取消任务。",
            )
        self.cancel_calls += 1
        return self._guard.observe(
            ProviderTask(
                provider_task_id=provider_task_id,
                status="cancelled",
                progress_value=None,
                asset_locator=None,
                error_code=None,
            )
        )

    async def acancel_task(self, provider_task_id: str) -> ProviderTask:
        return self.cancel_task(provider_task_id)

    def capabilities(self) -> MusicProviderCapabilities:
        return self._capabilities.model_copy(deep=True)

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy",
            provider_kind="cloud",
            provider="mock_music_provider",
            model="mock",
            checked_at=datetime.now(timezone.utc),
            capabilities=CoreProviderCapabilities(
                structured_json=True,
                max_input_characters=1,
            ),
            safe_message=None,
        )
