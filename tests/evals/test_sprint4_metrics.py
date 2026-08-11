import pytest


def test_evidence_coverage_is_independent_from_source_diversity():
    from evals.metrics import evidence_coverage, source_diversity

    assert evidence_coverage(3, 6) == pytest.approx(0.5)
    assert source_diversity({"questionnaire"}) == {
        "count": 1,
        "sources": ["questionnaire"],
    }
