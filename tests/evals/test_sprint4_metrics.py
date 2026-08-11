import pytest


def test_coverage_is_not_multiplied_by_source_diversity():
    from evals.metrics import evidence_coverage, source_diversity

    assert evidence_coverage(3, 6) == pytest.approx(0.5)
    assert source_diversity({"questionnaire"}) == {
        "count": 1,
        "sources": ["questionnaire"],
    }
