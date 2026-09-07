"""Qwen-backed Agent2 adapter with grounded response validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from backend.ai_engine.v3.diagnosis_pipeline import (
    DiagnosisPipelineFailure,
    validate_diagnosis_provider_response,
)
from backend.ai_engine.sprint4_contracts import ProviderError
from backend.ai_engine.v3.understanding_provider import ProviderFailureV3
from backend.app.schemas.v3.diagnosis import DiagnosisProviderResponse


class DiagnosisProviderFailure(RuntimeError):
    """Safe provider failure without raw prompts or source text."""

    def __init__(self, error_code: str, safe_message: str, *, retryable: bool) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(f"{error_code}: {safe_message}")


class DiagnosisProvider:
    def __init__(
        self,
        *,
        backend,
        allowed_syndrome_codes: set[str],
        allowed_fact_ids: set[str],
        allowed_chunk_ids: set[str],
    ) -> None:
        self.backend = backend
        self.allowed_syndrome_codes = set(allowed_syndrome_codes)
        self.allowed_fact_ids = set(allowed_fact_ids)
        self.allowed_chunk_ids = set(allowed_chunk_ids)

    async def acomplete_json(
        self,
        *,
        request: Mapping[str, object] | Any,
        facts: Sequence[object],
        rag_chunk_ids: Sequence[str],
    ) -> DiagnosisProviderResponse:
        system_prompt = (
            "Return one JSON object matching DiagnosisProviderResponse. "
            "Candidates are advisory and must use only the supplied approved "
            "syndrome, fact, and knowledge-chunk identifiers. Do not create "
            "facts, citations, organs, tones, prescriptions, or diagnoses."
        )
        payload = {
            "request": _safe_model_dump(request),
            "facts": [_safe_model_dump(fact) for fact in facts],
            "rag_chunk_ids": sorted(set(str(item) for item in rag_chunk_ids)),
            "allowed_syndrome_codes": sorted(self.allowed_syndrome_codes),
            "allowed_fact_ids": sorted(self.allowed_fact_ids),
            "allowed_chunk_ids": sorted(self.allowed_chunk_ids),
        }
        for attempt in (1, 2):
            prompt = system_prompt
            if attempt == 2:
                prompt += " Return a corrected object only; this is the single repair attempt."
            try:
                raw = await self.backend.acomplete_json(
                    prompt,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                )
                result = DiagnosisProviderResponse.model_validate(raw)
                return validate_diagnosis_provider_response(
                    result,
                    allowed_syndrome_codes=self.allowed_syndrome_codes,
                    allowed_fact_ids=self.allowed_fact_ids,
                    allowed_chunk_ids=self.allowed_chunk_ids,
                )
            except DiagnosisProviderFailure:
                raise
            except DiagnosisPipelineFailure as error:
                if attempt == 1 and error.error_code == "DIAGNOSIS_SCHEMA_INVALID":
                    continue
                raise DiagnosisProviderFailure(
                    error.error_code,
                    error.safe_message,
                    retryable=False,
                ) from None
            except ValidationError:
                if attempt == 1:
                    continue
                raise DiagnosisProviderFailure(
                    "DIAGNOSIS_SCHEMA_INVALID",
                    "辨证服务返回格式无效。",
                    retryable=False,
                ) from None
            except ProviderFailureV3 as error:
                raise DiagnosisProviderFailure(
                    f"DIAGNOSIS_{error.error_code}",
                    "辨证服务暂时不可用。",
                    retryable=error.retryable,
                ) from None
            except ProviderError as error:
                raise _map_provider_error(error) from None
            except TimeoutError:
                raise DiagnosisProviderFailure(
                    "DIAGNOSIS_PROVIDER_TIMEOUT",
                    "辨证服务响应超时。",
                    retryable=True,
                ) from None
            except (OSError, RuntimeError):
                raise DiagnosisProviderFailure(
                    "DIAGNOSIS_PROVIDER_UNAVAILABLE",
                    "辨证服务暂时不可用。",
                    retryable=True,
                ) from None
        raise AssertionError("diagnosis schema repair loop exhausted")


def diagnosis_provider_from_environment(
    environment: Mapping[str, str],
    *,
    allowed_syndrome_codes: set[str],
    allowed_fact_ids: set[str],
    allowed_chunk_ids: set[str],
) -> DiagnosisProvider | None:
    """Build the Qwen-backed Agent2 adapter only from explicit env values."""

    dashscope_key = environment.get("DASHSCOPE_API_KEY", "").strip()
    workspace_id = environment.get("DASHSCOPE_WORKSPACE_ID", "").strip()
    base_url = (
        environment.get("QWEN_BASE_URL", "").strip()
        or environment.get("DASHSCOPE_BASE_URL", "").strip()
        or ("https://dashscope.aliyuncs.com/compatible-mode/v1" if dashscope_key else "")
    )
    api_key = environment.get("QWEN_API_KEY", "").strip() or dashscope_key
    model = environment.get("QWEN_MODEL", "").strip() or environment.get(
        "DASHSCOPE_QWEN_MODEL", ""
    ).strip()
    if dashscope_key and not workspace_id:
        return None
    if not all((base_url, api_key, model)):
        return None
    from backend.ai_engine.providers import QwenCompatibleProvider

    return DiagnosisProvider(
        backend=QwenCompatibleProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            extra_headers={"X-DashScope-WorkSpace": workspace_id} if workspace_id else None,
        ),
        allowed_syndrome_codes=allowed_syndrome_codes,
        allowed_fact_ids=allowed_fact_ids,
        allowed_chunk_ids=allowed_chunk_ids,
    )


def _map_provider_error(error: ProviderError) -> DiagnosisProviderFailure:
    code = error.error_code
    if code == "NOT_CONFIGURED":
        return DiagnosisProviderFailure(
            "DIAGNOSIS_PROVIDER_NOT_CONFIGURED",
            "辨证服务尚未配置。",
            retryable=False,
        )
    if code in {"CONNECTION_TIMEOUT", "READ_TIMEOUT"}:
        return DiagnosisProviderFailure(
            "DIAGNOSIS_PROVIDER_TIMEOUT",
            "辨证服务响应超时。",
            retryable=bool(error.retryable),
        )
    if code == "RATE_LIMITED":
        return DiagnosisProviderFailure(
            "DIAGNOSIS_PROVIDER_RATE_LIMITED",
            "辨证服务繁忙，请稍后重试。",
            retryable=bool(error.retryable),
        )
    if code in {"INVALID_JSON", "JSON_REPAIR_FAILED", "SCHEMA_VIOLATION", "EMPTY_RESPONSE"}:
        return DiagnosisProviderFailure(
            "DIAGNOSIS_SCHEMA_INVALID",
            "辨证服务返回格式无效。",
            retryable=False,
        )
    return DiagnosisProviderFailure(
        "DIAGNOSIS_PROVIDER_UNAVAILABLE",
        "辨证服务暂时不可用。",
        retryable=bool(error.retryable),
    )


def _safe_model_dump(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
