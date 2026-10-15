def test_provider_error_exposes_machine_readable_code_and_retryability():
    from backend.ai_engine.sprint4_contracts import ProviderError

    error = ProviderError(
        reason_code="TIMEOUT",
        retryable=True,
        user_message="文本分析暂时超时，请稍后重试。",
    )

    assert error.reason_code == "TIMEOUT"
    assert error.retryable is True
    assert error.user_message
