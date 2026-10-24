import asyncio
import json
from urllib.error import HTTPError

import pytest

from backend.ai_engine.providers import QwenCompatibleProvider
from backend.ai_engine.sprint4_contracts import ProviderError, ProviderErrorCode
from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    ProviderFailureV3,
    QwenUnderstandingProvider,
    UnderstandingProviderChain,
    build_safe_provider_log_fields,
    build_understanding_provider_bundle,
    normalize_claim_metadata,
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
        self.prompts = []

    def complete_json(self, system_prompt, user_prompt):
        self.prompts.append((system_prompt, user_prompt))
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


def test_schema_repair_prompt_receives_safe_field_error_without_source_text():
    invalid = _response()
    invalid["facts"][0]["subject"] = "患者敏感原文"
    backend = _SequenceBackend([invalid, _response()])
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )

    result = provider.complete_json(_request("病历敏感全文不得进入错误提示"))

    assert result.status == "success"
    repair_system_prompt, repair_user_prompt = backend.prompts[1]
    rendered = repair_system_prompt + repair_user_prompt
    assert "facts.0.subject" in rendered
    assert "literal_error" in rendered
    assert "enum" in rendered
    assert "患者敏感原文" not in rendered
    assert "病历敏感全文不得进入错误提示" in repair_user_prompt
    assert "only the JSON structure" in repair_system_prompt


def test_schema_failure_records_missing_extra_and_type_without_values():
    invalid = _response()
    fact = invalid["facts"][0]
    del fact["subject"]
    fact["unexpected"] = "绝不能记录的敏感值"
    fact["negated"] = {"private": "绝不能记录"}
    backend = _SequenceBackend([invalid, invalid])
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

    issues = caught.value.validation_errors
    by_path = {issue["field_path"]: issue for issue in issues}
    assert by_path["facts.0.subject"]["category"] == "missing"
    assert by_path["facts.0.unexpected"]["category"] == "extra"
    assert by_path["facts.0.negated"]["category"] == "type"
    assert by_path["facts.0.negated"]["actual"] == "object"
    assert "绝不能记录" not in repr(issues)
    assert provider.last_run_metadata.validation_errors == issues


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


def test_provider_factory_builds_cloud_from_v31_dashscope_configuration(monkeypatch):
    """The V3.1 acceptance environment configures DASHSCOPE_* + QWEN_MODEL only.

    Understanding must reuse the shared ``V31ProviderConfig`` view, otherwise the
    cloud Provider is never built, fact extraction degrades to an empty chain and
    the confirmed summary silently loses its organised content.
    """

    def _forbidden_transport(url, headers, body, timeout):
        del headers, body, timeout
        raise AssertionError(f"network call attempted: {url}")

    monkeypatch.setattr(
        QwenCompatibleProvider,
        "_http_transport",
        staticmethod(_forbidden_transport),
    )
    environment = {
        "HARMONYAI_REAL_AGENTS": "true",
        "DASHSCOPE_API_KEY": "dashscope-secret-value",
        "DASHSCOPE_BASE_URL": "https://dashscope.example/compatible-mode/v1",
        "DASHSCOPE_WORKSPACE_ID": "ws-acceptance",
        "QWEN_MODEL": "qwen3.8-max-0902",
    }

    bundle = build_understanding_provider_bundle(
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
        environment=environment,
    )

    assert bundle.configured_kinds == ("cloud",)
    assert [item.status for item in bundle.health] == ["configured", "not_configured"]
    cloud = bundle.chain.providers[0]
    assert isinstance(cloud, QwenUnderstandingProvider)
    assert cloud.provider_kind == "cloud"
    assert cloud.model == "qwen3.8-max-0902"
    assert cloud.backend.base_url == "https://dashscope.example/compatible-mode/v1"
    assert cloud.backend.api_key == "dashscope-secret-value"
    assert cloud.backend.model == "qwen3.8-max-0902"
    assert cloud.backend.extra_headers == {"X-DashScope-WorkSpace": "ws-acceptance"}
    assert "dashscope-secret-value" not in repr(bundle.health)


def test_provider_factory_ignores_dashscope_configuration_when_real_agents_disabled():
    """An explicit HARMONYAI_REAL_AGENTS=false must never enable a paid Provider."""

    environment = {
        "HARMONYAI_REAL_AGENTS": "false",
        "DASHSCOPE_API_KEY": "dashscope-secret-value",
        "DASHSCOPE_BASE_URL": "https://dashscope.example/compatible-mode/v1",
        "DASHSCOPE_WORKSPACE_ID": "ws-acceptance",
        "QWEN_MODEL": "qwen3.8-max-0902",
    }

    bundle = build_understanding_provider_bundle(
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
        environment=environment,
    )

    assert bundle.configured_kinds == ()
    assert [item.status for item in bundle.health] == [
        "not_configured",
        "not_configured",
    ]
    with pytest.raises(ProviderFailureV3) as caught:
        bundle.chain.complete_json(_request())
    assert caught.value.error_code == "PROVIDER_UNAVAILABLE"


def test_provider_factory_keeps_explicit_qwen_configuration_over_dashscope():
    """Legacy explicit QWEN_* keeps precedence and its original transport shape."""

    environment = {
        "HARMONYAI_REAL_AGENTS": "true",
        "QWEN_BASE_URL": "https://explicit.example/v1",
        "QWEN_API_KEY": "explicit-secret-value",
        "QWEN_MODEL": "qwen-legacy-model",
        "DASHSCOPE_API_KEY": "dashscope-secret-value",
        "DASHSCOPE_BASE_URL": "https://dashscope.example/compatible-mode/v1",
        "DASHSCOPE_WORKSPACE_ID": "ws-acceptance",
    }

    bundle = build_understanding_provider_bundle(
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
        environment=environment,
    )

    assert bundle.configured_kinds == ("cloud",)
    cloud = bundle.chain.providers[0]
    assert cloud.backend.base_url == "https://explicit.example/v1"
    assert cloud.backend.api_key == "explicit-secret-value"
    assert cloud.backend.model == "qwen-legacy-model"
    assert cloud.backend.extra_headers == {}


def _provider(backend) -> QwenUnderstandingProvider:
    return QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="qwen-plus",
        claim_dictionary_version="medical_v3.test",
        claim_dictionary=_claim_dictionary(),
    )


def _metadata_mismatched_response() -> dict[str, object]:
    """A grounded fact whose dictionary metadata the model guessed wrong."""

    payload = _response()
    payload["facts"][0]["display_name"] = "睡不好"
    payload["facts"][0]["category"] = "sleep_problem"
    return payload


def test_metadata_mismatch_no_longer_discards_a_grounded_fact():
    """display_name/category are dictionary metadata, not model inference.

    The prompt cannot carry per-claim metadata for every approved claim, so a
    model that invents a plausible display_name/category used to fail
    ``claim_metadata_mismatch`` twice and lose the whole extraction. The server
    now backfills them from the approved dictionary.
    """

    backend = _SequenceBackend([_metadata_mismatched_response()])
    provider = _provider(backend)

    result = provider.complete_json(_request())

    assert backend.calls == 1, "an authoritative fix must not cost a repair call"
    assert provider.last_run_metadata.repaired is False
    fact = result.facts[0]
    assert fact.claim_code == "sleep_test"
    assert fact.display_name == "睡眠测试事实"
    assert fact.category == "sleep"
    # source-grounded fields stay exactly as the Provider reported them
    assert fact.value.type == "severity"
    assert fact.value.value == "moderate"
    assert fact.negated is False
    assert fact.subject == "self"
    assert fact.time_window == "past_7_days"
    assert fact.span.start == 0
    assert fact.span.end == 4
    assert fact.extraction_confidence == 0.8
    assert provider.last_metadata_normalizations == (
        "facts.0.display_name",
        "facts.0.category",
    )


def test_async_provider_normalizes_dictionary_metadata_too():
    backend = _SequenceBackend([_metadata_mismatched_response()])
    provider = _provider(backend)

    result = asyncio.run(provider.acomplete_json(_request()))

    assert backend.calls == 1
    assert result.facts[0].display_name == "睡眠测试事实"
    assert result.facts[0].category == "sleep"


def test_correct_provider_metadata_is_left_untouched_and_unrecorded():
    backend = _SequenceBackend([_response()])
    provider = _provider(backend)

    result = provider.complete_json(_request())

    assert backend.calls == 1
    assert result.facts[0].display_name == "睡眠测试事实"
    assert provider.last_metadata_normalizations == ()


def test_value_type_label_is_renormalized_only_for_an_already_approved_value():
    payload = _response()
    payload["facts"][0]["value"] = {"type": "coded_text", "value": "moderate"}
    backend = _SequenceBackend([payload])
    provider = _provider(backend)

    result = provider.complete_json(_request())

    assert backend.calls == 1
    assert result.facts[0].value.type == "severity"
    assert result.facts[0].value.value == "moderate"
    assert provider.last_metadata_normalizations == ("facts.0.value.type",)


def test_value_type_label_is_not_renormalized_when_the_value_is_unapproved():
    """Re-labelling an unapproved value would reinterpret medical meaning."""

    payload = _response()
    payload["facts"][0]["value"] = {"type": "frequency_0_4", "value": 2}
    backend = _SequenceBackend([payload, payload])
    provider = _provider(backend)

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "MODEL_SCHEMA_INVALID"
    assert backend.calls == 2
    assert provider.last_metadata_normalizations == ()
    detail = caught.value.validation_errors[0]
    assert detail["field_path"] == "facts.0.value.type"
    assert detail["error_type"] == "claim_value_type_mismatch"


def test_unapproved_claim_code_is_never_repaired_by_metadata_normalization():
    """Correct-looking metadata must not buy an unapproved claim an approval."""

    payload = _response(claim_code="unsupported")
    payload["facts"][0]["display_name"] = "睡眠测试事实"
    payload["facts"][0]["category"] = "sleep"
    backend = _SequenceBackend([payload, payload])
    provider = _provider(backend)

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    assert caught.value.error_code == "MODEL_SCHEMA_INVALID"
    assert backend.calls == 2
    assert provider.last_metadata_normalizations == ()
    detail = caught.value.validation_errors[0]
    assert detail["field_path"] == "facts.0.claim_code"
    assert detail["error_type"] == "unapproved_claim_code"


def test_metadata_normalization_never_adds_drops_or_reorders_facts():
    payload = _response()
    approved = _metadata_mismatched_response()["facts"][0]
    unapproved = _response(claim_code="unsupported")["facts"][0]
    payload["facts"] = [approved, unapproved]
    backend = _SequenceBackend([payload, payload])
    provider = _provider(backend)

    with pytest.raises(ProviderFailureV3) as caught:
        provider.complete_json(_request())

    # the approved fact was normalized in place, the unapproved one survived
    # to be rejected by index instead of being silently dropped
    assert provider.last_metadata_normalizations == (
        "facts.0.display_name",
        "facts.0.category",
    )
    assert caught.value.validation_errors[0]["field_path"] == "facts.1.claim_code"


def test_normalize_claim_metadata_is_closed_world():
    dictionary = _claim_dictionary()

    assert normalize_claim_metadata("not-a-payload", dictionary) == (
        "not-a-payload",
        (),
    )
    assert normalize_claim_metadata({"facts": "not-a-list"}, dictionary) == (
        {"facts": "not-a-list"},
        (),
    )
    unknown = {"facts": [{"claim_code": "unsupported", "display_name": "猜的"}]}
    normalized, paths = normalize_claim_metadata(unknown, dictionary)
    assert normalized == unknown
    assert paths == ()
    untouched = {"facts": ["not-a-fact"]}
    assert normalize_claim_metadata(untouched, dictionary) == (untouched, ())


def test_prompt_supplies_authoritative_claim_metadata_as_server_owned():
    backend = _SequenceBackend([_response()])
    provider = _provider(backend)

    provider.complete_json(_request())

    system_prompt, user_prompt = backend.prompts[0]
    payload = json.loads(user_prompt)
    assert payload["allowed_claim_metadata"] == [
        {
            "claim_code": "sleep_test",
            "display_name": "睡眠测试事实",
            "category": "sleep",
            "value_type": "severity",
            "allowed_values": ["moderate"],
        }
    ]
    assert "copy display_name, category and value.type verbatim" in system_prompt
    assert "never something to infer from the source text" in system_prompt


def test_repair_prompt_keeps_dictionary_metadata_server_owned():
    payload = _metadata_mismatched_response()
    payload["facts"][0]["claim_code"] = "unsupported"
    backend = _SequenceBackend([payload, _response()])
    provider = _provider(backend)

    provider.complete_json(_request())

    repair_system_prompt = backend.prompts[1][0]
    assert "only the JSON structure" in repair_system_prompt
    assert "server-owned dictionary metadata" in repair_system_prompt
    assert "never a reason to change a code" in repair_system_prompt
