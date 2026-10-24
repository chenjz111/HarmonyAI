import pytest


def test_public_expression_rejects_medical_certainty_and_internal_provider_text():
    from backend.ai_engine.v3.safe_expression import UnsafePublicExpression, validate_public_text

    with pytest.raises(UnsafePublicExpression):
        validate_public_text("你的证型是肝郁化火")
    with pytest.raises(UnsafePublicExpression):
        validate_public_text("provider=qwen raw prompt")


def test_public_expression_accepts_bounded_tendency_and_preference_wording():
    from backend.ai_engine.v3.safe_expression import validate_public_text

    assert validate_public_text("当前状态更贴近平稳舒缓方向（调适参考）。") == (
        "当前状态更贴近平稳舒缓方向（调适参考）。"
    )


def test_public_expression_allows_non_diagnostic_disclaimer():
    from backend.ai_engine.v3.safe_expression import validate_public_text

    assert validate_public_text("仅用于音乐调适参考，不构成医学诊断。")
