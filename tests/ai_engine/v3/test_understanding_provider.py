import asyncio
from urllib.error import HTTPError

import pytest

from backend.ai_engine.sprint4_contracts import ProviderError, ProviderErrorCode
from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    ProviderFailureV3,
    QwenUnderstandingProvider,
    UnderstandingProviderChain,
    build_safe_provider_log_fields,
    build_understanding_provider_bundle,
)
from backend.app.schemas.v3.common import ClaimDictionaryEntry, MedicalReview
from backend.app.schemas.v3.understanding import (
    ProviderSource,
    UnderstandingProviderRequest,
    UnderstandingProviderResponse,
)


def _request(text: str = "最近睡得不好") -> UnderstandingProviderRequest:
    return UnderstandingProviderRequest(
        request_id="upr_test",
        schema_version="understanding_provider_v3.0",
        prompt_version="understanding_prompt_v3.0",
        source=ProviderSource(
            source_id="nar_test",
            source_type="narrative",
            subject_hint="self",
            time_window="past_7_days",
            text=text,
        ),
        allowed_claim_dictionary_version="medical_v3.test",
        max_facts=10,
    )


def _response(*, claim_code: str = "sleep_test") -> dict[str, object]:
    return {
        "status": "success",
        "facts": [
            {
                "claim_code": claim_code,
                "display_name": "睡眠测试事实",
                "category": "sleep",
                "value": {"type": "severity", "value": "moderate"},
                "time_window": "past_7_days",
                "negated": False,
                "subject": "self",
                "span": {"start": 0, "end": 4},
                "extraction_confidence": 0.8,
            }
        ],
        "warnings": [],
    }


def _claim_dictionary() -> dict[str, ClaimDictionaryEntry]:
    entry = ClaimDictionaryEntry(
        claim_code="sleep_test",
        display_name="睡眠测试事实",
        category="sleep",
        value_type="severity",
        allowed_values=["moderate"],
        questionnaire_option_refs=[],
        organ_mapping_allowed=False,
        medical_review=MedicalReview(
            status="approved",
            review_version="test-only-v1",
        ),
    )
    return {entry.claim_code: entry}


class _SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        result = self.responses[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result

    async def acomplete_json(self, system_prompt, user_prompt):
        return self.complete_json(system_prompt, user_prompt)


def test_mock_provider_supports_sync_and_async_typed_contract():
    expected = UnderstandingProviderResponse.model_validate(_response())
    provider = MockUnderstandingProvider(expected)

    assert provider.complete_json(_request()) == expected
    assert asyncio.run(provider.acomplete_json(_request())) == expected
    assert provider.health().status == "healthy"
    assert provider.calls == 2


def test_qwen_provider_repairs_schema_once_then_accepts_valid_response():
    backend = _SequenceBackend([_response(claim_code="unsupported"), _response()])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    result = provider.complete_json(_request())

    assert result.status == "success"
    assert result.facts[0].claim_code == "sleep_test"
    assert backend.calls == 2
    assert provider.last_run_metadata.attempts == 2
    assert provider.last_run_metadata.repaired is True


def test_qwen_provider_fails_safely_after_one_invalid_repair():
    backend = _SequenceBackend(
        [_response(claim_code="unsupported"), _response(claim_code="unsupported")]
    )
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "MODEL_SCHEMA_INVALID"
    assert caught.value.retryable is False
    assert "unsupported" not in caught.value.safe_message
    assert backend.calls == 2


def test_cloud_timeout_falls_back_to_local_without_fake_success():
    timeout = ProviderError(
        ProviderErrorCode.READ_TIMEOUT,
        True,
        "raw timeout detail",
    )
    cloud = QwenUnderstandingProvider(
        backend=_SequenceBackend([timeout]),
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )
    local = MockUnderstandingProvider(
        UnderstandingProviderResponse.model_validate(_response()),
        provider_kind="local",
    )
    chain = UnderstandingProviderChain(cloud=cloud, local=local)

    result = chain.complete_json(_request())

    assert result.status == "degraded"
    assert "PROVIDER_TIMEOUT" in result.warnings
    assert local.calls == 1
    assert chain.last_provider_kind == "local"


def test_provider_validation_rejects_span_outside_source_text():
    payload = _response()
    payload["facts"][0]["span"] = {"start": 0, "end": 99}
    backend = _SequenceBackend([payload, payload])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request("睡不好"))

    assert caught.value.error_code == "MODEL_SCHEMA_INVALID"


def test_safe_provider_log_fields_never_include_source_text_or_prompts():
    fields = build_safe_provider_log_fields(
        request=_request("用户原文绝不能进入普通日志"),
        provider_kind="cloud",
        provider="qwen",
        model="qwen-plus",
        status="failed",
        attempts=2,
        latency_ms=50,
        error_code="PROVIDER_TIMEOUT",
    )

    rendered = repr(fields)
    assert "用户原文" not in rendered
    assert "text" not in fields
    assert "prompt" not in fields
    assert "api_key" not in fields
    assert fields["source_length"] == 13
    assert str(fields["source_sha256"]).startswith("sha256:")


def test_not_configured_health_is_safe_and_contains_no_secret():
    provider = MockUnderstandingProvider.not_configured(
        provider_kind="cloud",
        provider_name="qwen",
    )

    health = provider.health()

    assert health.status == "not_configured"
    assert health.safe_message == "AI 理解服务尚未配置。"
    assert "key" not in health.model_dump_json().lower()


def test_qwen_provider_repairs_once_after_backend_invalid_json_error():
    invalid_json = ProviderError(
        ProviderErrorCode.JSON_REPAIR_FAILED,
        False,
        "raw invalid output",
    )
    backend = _SequenceBackend([invalid_json, _response()])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    result = provider.complete_json(_request())

    assert result.status == "success"
    assert backend.calls == 2
    assert provider.last_run_metadata.repaired is True



def test_retryable_invalid_response_is_network_failure_not_schema_repair():
    network_error = ProviderError(
        ProviderErrorCode.INVALID_RESPONSE,
        True,
        "raw network detail",
        cause=OSError("private connection detail"),
    )
    backend = _SequenceBackend([network_error, _response()])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "PROVIDER_UNAVAILABLE"
    assert backend.calls == 1


def test_auth_failure_is_not_repaired_and_uses_stable_error_code():
    auth_error = ProviderError(
        ProviderErrorCode.INVALID_RESPONSE,
        False,
        "raw authentication detail",
        cause=HTTPError("https://example.invalid", 401, "unauthorized", {}, None),
    )
    backend = _SequenceBackend([auth_error, _response()])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "PROVIDER_AUTH_FAILED"
    assert backend.calls == 1

def test_cloud_failed_status_falls_back_to_local():
    cloud = MockUnderstandingProvider(
        UnderstandingProviderResponse(
            status="failed",
            facts=[],
            warnings=["MODEL_SCHEMA_INVALID"],
        ),
        provider_kind="cloud",
    )
    local = MockUnderstandingProvider(
        UnderstandingProviderResponse.model_validate(_response()),
        provider_kind="local",
    )
    chain = UnderstandingProviderChain(cloud=cloud, local=local)

    result = chain.complete_json(_request())

    assert result.status == "degraded"
    assert "MODEL_SCHEMA_INVALID" in result.warnings
    assert local.calls == 1
    assert chain.last_provider_kind == "local"

def test_async_qwen_repair_and_chain_fallback_match_sync_contract():
    invalid_json = ProviderError(
        ProviderErrorCode.INVALID_JSON,
        False,
        "raw invalid output",
    )
    repairing_backend = _SequenceBackend([invalid_json, _response()])
    repairing = QwenUnderstandingProvider(
        backend=repairing_backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    repaired = asyncio.run(repairing.acomplete_json(_request()))

    assert repaired.status == "success"
    assert repairing.last_run_metadata.repaired is True
    timeout = ProviderFailureV3(
        "PROVIDER_TIMEOUT",
        retryable=True,
        safe_message="AI 理解服务响应超时，请稍后重试。",
    )
    cloud = MockUnderstandingProvider(
        None,
        provider_kind="cloud",
        failure=timeout,
    )
    local = MockUnderstandingProvider(
        UnderstandingProviderResponse.model_validate(_response()),
        provider_kind="local",
    )
    chain = UnderstandingProviderChain(cloud=cloud, local=local)

    fallback = asyncio.run(chain.acomplete_json(_request()))

    assert fallback.status == "degraded"
    assert fallback.warnings == ["PROVIDER_TIMEOUT"]
    assert chain.last_provider_kind == "local"

def test_provider_rejects_claim_dictionary_version_mismatch_before_call():
    backend = _SequenceBackend([_response()])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.other",
        claim_dictionary=_claim_dictionary(),
    )

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "MEDICAL_ASSET_UNAVAILABLE"
    assert backend.calls == 0


def test_medical_asset_gate_stops_chain_before_local_or_rule_fallback():
    cloud = QwenUnderstandingProvider(
        backend=_SequenceBackend([_response()]),
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.other",
        claim_dictionary=_claim_dictionary(),
    )
    local = MockUnderstandingProvider(
        UnderstandingProviderResponse.model_validate(_response()),
        provider_kind="local",
    )
    rule = MockUnderstandingProvider(
        UnderstandingProviderResponse.model_validate(_response()),
        provider_kind="rule",
    )
    chain = UnderstandingProviderChain(cloud=cloud, local=local, rule=rule)

    with pytest.raises(ProviderFailureV3) as caught:
        chain.complete_json(_request())

    assert caught.value.error_code == "MEDICAL_ASSET_UNAVAILABLE"
    assert local.calls == 0
    assert rule.calls == 0

def test_provider_rejects_claim_value_outside_approved_dictionary():
    payload = _response()
    payload["facts"][0]["value"] = {"type": "severity", "value": "severe"}
    backend = _SequenceBackend([payload, payload])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "MODEL_SCHEMA_INVALID"
    assert backend.calls == 2

def test_provider_factory_reports_unconfigured_without_enabling_mock_success():
    bundle = build_understanding_provider_bundle(
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
        environment={},
    )

    assert [item.status for item in bundle.health] == [
        "not_configured",
        "not_configured",
    ]
    with pytest.raises(ProviderFailureV3) as caught:
        bundle.chain.complete_json(_request())
    assert caught.value.error_code == "PROVIDER_UNAVAILABLE"


def test_provider_factory_builds_cloud_and_local_without_exposing_keys():
    environment = {
        "QWEN_BASE_URL": "https://cloud.example/v1",
        "QWEN_API_KEY": "cloud-secret-value",
        "QWEN_MODEL": "qwen-plus",
        "LOCAL_QWEN_BASE_URL": "http://127.0.0.1:11434/v1",
        "LOCAL_QWEN_API_KEY": "local-secret-value",
        "LOCAL_QWEN_MODEL": "qwen2.5:7b",
    }

    bundle = build_understanding_provider_bundle(
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
        environment=environment,
    )

    assert bundle.configured_kinds == ("cloud", "local")
    assert [item.status for item in bundle.health] == ["configured", "configured"]
    rendered = repr(bundle.health)
    assert "cloud-secret-value" not in rendered
    assert "local-secret-value" not in rendered
