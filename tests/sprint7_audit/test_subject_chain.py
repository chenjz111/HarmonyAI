"""R1/R2 audit -- ``subject`` (self / other / unknown) never reaches the chain.

Issue #154 asks for subject isolation at admission, coverage, effective
population, organ aggregation, mode, Diagnosis and public Explanation.

Observed result on the published baseline: ``subject`` exists only on the
extraction layer and is dropped before any of those stages.

Source anchors:

* ``schemas/v3/understanding.py`` line 91
  ``ProviderSource.subject_hint: Literal["self", "other", "unknown"]``
* ``schemas/v3/understanding.py`` line 112
  ``UnderstandingProviderFact.subject: Literal["self", "other", "unknown"]``
* ``assessment_service._fact_evidence()`` lines 584-602 -- copies ten fields
  and none of them is ``subject``
* ``schemas/v3/assessment.py`` lines 63-76 -- ``FactEvidence`` has no
  ``subject`` field, and ``V3BaseModel`` sets ``extra="forbid"``

Consequence for the audit: the subject dimension cannot be isolation-tested
downstream. The finding must be reported as "field is absent from the chain",
never as "subject was handled correctly". Whether the unpublished
``evidence_admission.py`` intercepts it earlier is an open question for INT-2
(Q2 in the audit report).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.v3.assessment import FactEvidence
from backend.app.schemas.v3.understanding import (
    ProviderSource,
    UnderstandingProviderFact,
)
from backend.app.services.v3 import assessment_service

SUBJECT_VALUES = ("self", "other", "unknown")


def _provider_fact_dict(subject: str) -> dict:
    """A provider-produced fact dict, ``subject`` included, as extracted."""

    return {
        "fact_id": "f_subject_probe",
        "fact_code": "flank_discomfort",
        "display_name": "胁肋胀闷不适",
        "category": "body",
        "value": {"type": "frequency_0_4", "value": 3},
        "time_window": "past_7_days",
        "negated": False,
        "subject": subject,
        "source_refs": [{"source_id": "src_doc_1", "source_type": "document"}],
        "extraction": {"confidence": 0.8},
        "confirmation_status": "confirmed",
    }


@pytest.mark.parametrize("subject", SUBJECT_VALUES)
def test_extraction_layer_declares_subject(subject: str) -> None:
    """Observed: the field is real and constrained at extraction time."""

    assert "subject" in UnderstandingProviderFact.model_fields
    assert "subject_hint" in ProviderSource.model_fields

    fact = UnderstandingProviderFact(
        claim_code="flank_discomfort",
        display_name="胁肋胀闷不适",
        category="body",
        value={"type": "frequency_0_4", "value": 3},
        time_window="past_7_days",
        negated=False,
        subject=subject,
        span={"start": 0, "end": 4},
        extraction_confidence=0.8,
    )

    assert fact.subject == subject


def test_provider_fact_rejects_an_unknown_subject() -> None:
    """Observed: the literal is closed -- ``unknown`` is legal, junk is not."""

    with pytest.raises(ValidationError):
        UnderstandingProviderFact(
            claim_code="flank_discomfort",
            display_name="胁肋胀闷不适",
            category="body",
            value={"type": "frequency_0_4", "value": 3},
            time_window="past_7_days",
            negated=False,
            subject="third_party",
            span={"start": 0, "end": 4},
            extraction_confidence=0.8,
        )


def test_fact_evidence_has_no_subject_field() -> None:
    """Observed: the downstream model simply does not carry the dimension."""

    assert "subject" not in FactEvidence.model_fields
    assert "subject_hint" not in FactEvidence.model_fields


def test_fact_evidence_rejects_a_subject_keyword() -> None:
    """Observed: it is not merely unused -- it is rejected outright."""

    with pytest.raises(ValidationError):
        FactEvidence(
            fact_evidence_id="fev_probe",
            assessment_id="asmt_probe",
            assessment_revision=1,
            fact_id="f_probe",
            claim_code="flank_discomfort",
            display_name="胁肋胀闷不适",
            category="body",
            value={"type": "frequency_0_4", "value": 3},
            time_window="past_7_days",
            direction="supporting",
            reliability=0.8,
            source_refs=[{"source_id": "src_doc_1", "source_type": "document"}],
            confirmation_status="confirmed",
            subject="self",
        )


@pytest.mark.parametrize("subject", SUBJECT_VALUES)
def test_fact_evidence_builder_drops_subject(mapping: dict, subject: str) -> None:
    """Observed: the row produced for the same fact is identical for all three.

    ``subject=self``, ``subject=other`` and ``subject=unknown`` collapse into
    the same persisted evidence, so nothing downstream can separate them.
    """

    row = assessment_service._fact_evidence(
        "asmt_probe", _provider_fact_dict(subject), index=0
    )

    assert not hasattr(row, "subject")

    links = assessment_service._organ_links([row], mapping)
    assert links, "the probe claim must still map to an organ"

    comparable = [
        getattr(row, "fact_id"),
        getattr(row, "claim_code"),
        getattr(row, "direction").value,
        getattr(row, "reliability"),
        getattr(row, "time_window"),
        sorted((link.organ.value, link.direction.value) for link in links),
    ]
    assert comparable == [
        "f_subject_probe",
        "flank_discomfort",
        "supporting",
        0.8,
        "past_7_days",
        [("liver", "supporting")],
    ]


def test_subject_does_not_reach_the_decision(assets) -> None:
    """Observed: the decision is a function of the remaining ten fields only.

    The same probe fact yields the same ``basic_wellness`` coverage verdict for
    every subject value because the subject is already gone by then.
    """

    from tests.sprint7_audit.harness import decide, make_evidence

    decisions = [
        decide([make_evidence("f_flank", "flank_discomfort")], assets, coverage=0.25)
        for _ in SUBJECT_VALUES
    ]

    assert {d.regulation_mode for d in decisions} == {"basic_wellness"}
    # V2.1: the single claim never qualifies an organ, so the reason is the
    # legal-candidate gate, not the (now audit-only) coverage gate
    assert {d.decision_reason_code for d in decisions} == {
        "BASIC_NO_LEGAL_ORGAN_CANDIDATE"
    }
