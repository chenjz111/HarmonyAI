"""Deterministic questionnaire evidence for Agent 1.

The questionnaire is an approved source of structured facts.  Claim names,
types, and question bindings are loaded from the signed claim dictionary;
this module only translates submitted answers into the existing normalized
fact contract and never infers an unlisted medical claim.
"""

from __future__ import annotations

from hashlib import sha256

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from backend.app.models.v3.understanding import (
    FactSourceRef,
    NormalizedFact as NormalizedFactRow,
    QuestionnaireSubmissionV3,
)
from backend.app.schemas.v3.common import QuestionnaireAnswer
from backend.app.services.v3.knowledge_assets import load_claim_dictionary


_QUESTIONNAIRE_ANSWER_ADAPTER = TypeAdapter(QuestionnaireAnswer)


class QuestionnaireEvidenceInvalid(ValueError):
    """Raised when a completed questionnaire cannot be mapped safely."""


def _stable_fact_id(submission_id: str, claim_code: str) -> str:
    digest = sha256(f"{submission_id}:{claim_code}".encode("utf-8")).hexdigest()
    return f"qfact_{digest}"


def _answers_by_question(submission: QuestionnaireSubmissionV3) -> dict[str, object]:
    answers: dict[str, object] = {}
    for raw_answer in submission.answers_json or []:
        try:
            answer = _QUESTIONNAIRE_ANSWER_ADAPTER.validate_python(raw_answer)
        except ValidationError as error:
            raise QuestionnaireEvidenceInvalid from error
        if answer.question_id in answers:
            raise QuestionnaireEvidenceInvalid
        answers[answer.question_id] = answer
    return answers


def build_questionnaire_facts(
    submission: QuestionnaireSubmissionV3,
) -> list[dict]:
    """Map selected, non-zero questionnaire answers to normalized facts."""
    answers = _answers_by_question(submission)
    _version, claims = load_claim_dictionary()
    facts: list[dict] = []
    for claim in claims.values():
        for option_ref in claim.questionnaire_option_refs:
            question_id, separator, option_code = option_ref.partition(":")
            answer = answers.get(question_id)
            if answer is None:
                raise QuestionnaireEvidenceInvalid

            if not separator:
                if claim.value_type != "frequency_0_4" or answer.answer_type != "frequency_0_4":
                    raise QuestionnaireEvidenceInvalid
                value = int(answer.value)
                if value == 0:
                    continue
                fact_value = {"type": "frequency_0_4", "value": value}
            else:
                if answer.answer_type != "multi_choice_evidence":
                    raise QuestionnaireEvidenceInvalid
                if option_code not in answer.value:
                    continue
                if claim.value_type != "boolean":
                    raise QuestionnaireEvidenceInvalid
                fact_value = {"type": "boolean", "value": True}

            facts.append(
                {
                    "fact_id": _stable_fact_id(
                        submission.questionnaire_submission_id,
                        claim.claim_code,
                    ),
                    "fact_code": claim.claim_code,
                    "display_name": claim.display_name,
                    "category": claim.category,
                    "value": fact_value,
                    "time_window": "past_7_days",
                    "negated": False,
                    "subject": "self",
                    "source_refs": [
                        {
                            "source_id": submission.questionnaire_submission_id,
                            "source_type": "questionnaire",
                            "span_ref": None,
                        }
                    ],
                    "confirmation_status": "confirmed",
                    "extraction": {
                        "method": "deterministic_questionnaire_mapping",
                        "confidence": (
                            value / 4.0
                            if fact_value["type"] == "frequency_0_4"
                            else 1.0
                        ),
                    },
                }
            )
    return facts


def ensure_questionnaire_fact_rows(
    db: Session,
    submission: QuestionnaireSubmissionV3,
    facts: list[dict],
) -> dict[str, str]:
    """Persist questionnaire facts once and return fact_id -> row id."""
    row_ids: dict[str, str] = {}
    for fact in facts:
        row = (
            db.query(NormalizedFactRow)
            .filter(
                NormalizedFactRow.questionnaire_submission_id
                == submission.questionnaire_submission_id,
                NormalizedFactRow.fact_id == fact["fact_id"],
            )
            .one_or_none()
        )
        if row is None:
            row = NormalizedFactRow(
                fact_row_id=f"factrow_{sha256(fact['fact_id'].encode('utf-8')).hexdigest()[:32]}",
                fact_id=fact["fact_id"],
                owner_type="questionnaire",
                understanding_id=None,
                understanding_revision=None,
                questionnaire_submission_id=submission.questionnaire_submission_id,
                fact_code=fact["fact_code"],
                category=fact["category"],
                display_name=fact["display_name"],
                value_json=fact["value"],
                time_window=fact["time_window"],
                negated=0,
                subject="self",
                confirmation_status="confirmed",
                extraction_method=fact["extraction"]["method"],
                extraction_confidence=fact["extraction"]["confidence"],
                supersedes_fact_row_id=None,
            )
            db.add(row)
            db.flush()
            db.add(
                FactSourceRef(
                    fact_row_id=row.fact_row_id,
                    source_type="questionnaire",
                    source_id=submission.questionnaire_submission_id,
                    span_ref=None,
                )
            )
        row_ids[fact["fact_id"]] = row.fact_row_id
    db.flush()
    return row_ids
