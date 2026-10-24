import pytest


def test_extraction_f1_metrics_use_case_level_micro_counts():
    from evals.metrics import emotion_f1, event_f1, physical_f1

    pairs = [
        ({"a", "b"}, {"a", "c"}),
        ({"a"}, {"a"}),
    ]

    assert emotion_f1(pairs) == pytest.approx(2 * 2 / (3 + 3))
    assert event_f1(pairs) == pytest.approx(2 * 2 / (3 + 3))
    assert physical_f1(pairs) == pytest.approx(2 * 2 / (3 + 3))


def test_grounding_accuracy_checks_source_ref_and_quote_against_input():
    from evals.metrics import grounding_accuracy

    evidence = [
        {
            "source_type": "narrative",
            "source_ref": "narrative:sentence_1",
            "quote": "sleep poorly",
        },
        {
            "source_type": "document",
            "source_ref": "document:block_1",
            "quote": "not in document",
        },
        {
            "source_type": "questionnaire",
            "source_ref": "questionnaire:q03_tension_worry",
        },
    ]

    assert grounding_accuracy(
        evidence,
        {
            "narrative_text": "I sleep poorly",
            "document_text": "confirmed document",
            "questionnaire_answers": {"q03_tension_worry": 3},
        },
    ) == pytest.approx(2 / 3)
