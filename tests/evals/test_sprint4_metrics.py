import pytest


def test_evidence_coverage_uses_source_diversity_factor():
    from evals.metrics import evidence_coverage

    assert evidence_coverage(3, 6, {"questionnaire"}) == pytest.approx(1 / 6)
    assert evidence_coverage(
        6,
        6,
        {"questionnaire", "narrative", "document"},
    ) == pytest.approx(1.0)
