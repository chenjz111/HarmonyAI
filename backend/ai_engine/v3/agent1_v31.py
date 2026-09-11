"""Pure V3.1 Agent 1 input gates and adapters.

The persistence owner supplies the authoritative ``DocumentSet`` and
per-document Relevance rows to this module.  This module deliberately does
not query or define those tables: it validates their boundary, keeps the
document order/provenance, and exposes only VALID documents downstream.

The questionnaire adapter delegates to the same approved claim dictionary
mapping used by the existing V3 persistence service.  It accepts only the
frozen V3.1 ``QuestionnaireResult`` shape, so a partial or older submission
cannot silently become Agent 1 evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from backend.app.schemas.v3.common import SourceRef, SourceType
from backend.app.schemas.v3.flow_v31 import DocumentSet, QuestionnaireResult
from backend.app.schemas.v3.understanding import NormalizedFact as NormalizedFactSchema
from backend.app.services.v3.questionnaire_evidence import (
    build_questionnaire_facts_from_result,
)


class Agent1InputBlocked(ValueError):
    """Raised when authoritative V3.1 input is not safe to consume."""

    def __init__(self, error_code: str, safe_message: str = "V3.1 输入尚未就绪。") -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


@dataclass(frozen=True)
class ValidDocumentInput:
    """One VALID document source passed to Understanding/Agent 1."""

    document_id: str
    position: int
    content_checksum: str
    relevance_result_id: str
    source_ref: SourceRef


@dataclass(frozen=True)
class ActiveDocumentSetInput:
    """Resolved, revision-bound document input for the downstream chain."""

    document_set_id: str
    document_set_revision: int
    session_input_revision: int
    valid_documents: tuple[ValidDocumentInput, ...]
    excluded_document_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConfirmedAgent1Input:
    """Agent 1 evidence projection bound to one confirmed state."""

    confirmed_user_state: Any
    document_ids: tuple[str, ...]
    facts: tuple[dict[str, Any], ...]


def resolve_active_document_set(
    document_set: DocumentSet | Mapping[str, Any],
    relevance_results: Sequence[Mapping[str, Any] | Any],
    *,
    expected_user_pk: int,
    expected_session_id: str,
    expected_document_set_id: str,
    expected_document_set_revision: int,
    expected_session_input_revision: int,
) -> ActiveDocumentSetInput:
    """Resolve the current 1--3 document set and its per-document gate.

    ``owner_user_pk`` is an adapter field supplied by the persistence owner
    (PR #104).  It is intentionally not added to the frozen transport
    ``DocumentSet`` schema.  Relevance rows must contain a concrete
    ``document_id`` and the exact set revision; absent rows never default to
    VALID.
    """

    payload = _as_mapping(document_set)
    owner_user_pk = _read(payload, "owner_user_pk", _read(payload, "internal_user_pk", None))
    try:
        parsed = DocumentSet.model_validate(
            {key: value for key, value in payload.items() if key not in {"owner_user_pk", "internal_user_pk"}}
        )
    except (TypeError, ValueError) as error:
        raise Agent1InputBlocked("DOCUMENT_SET_NOT_ACTIVE") from error

    if owner_user_pk is None or int(owner_user_pk) != expected_user_pk:
        raise Agent1InputBlocked("DOCUMENT_SET_NOT_OWNED")
    if parsed.session_id != expected_session_id:
        raise Agent1InputBlocked("DOCUMENT_SET_NOT_OWNED")
    if (
        parsed.document_set_id != expected_document_set_id
        or parsed.revision != expected_document_set_revision
        or parsed.session_input_revision != expected_session_input_revision
        or parsed.authority_status != "current"
    ):
        raise Agent1InputBlocked("DOCUMENT_SET_NOT_ACTIVE")

    rows_by_document: dict[str, Mapping[str, Any]] = {}
    for raw_row in relevance_results:
        row = _as_mapping(raw_row)
        document_id = _read(row, "document_id", None)
        result_id = _read(row, "relevance_result_id", _read(row, "document_relevance_id", None))
        row_set_id = _read(row, "document_set_id", None)
        row_revision = _read(row, "document_set_revision", None)
        outcome = _read(row, "outcome", None)
        if not document_id or not result_id or row_set_id != parsed.document_set_id:
            raise Agent1InputBlocked("RELEVANCE_NOT_READY")
        if row_revision != parsed.revision or document_id in rows_by_document:
            raise Agent1InputBlocked("RELEVANCE_NOT_READY")
        if outcome not in {"VALID", "INVALID", "IRRELEVANT", "INSUFFICIENT"}:
            raise Agent1InputBlocked("RELEVANCE_NOT_READY")
        rows_by_document[str(document_id)] = row

    document_ids = [item.document_id for item in parsed.documents]
    if set(rows_by_document) != set(document_ids) or len(rows_by_document) != len(document_ids):
        raise Agent1InputBlocked("RELEVANCE_NOT_READY")
    if any(_read(rows_by_document[item], "outcome", None) == "INSUFFICIENT" for item in document_ids):
        raise Agent1InputBlocked("RELEVANCE_INSUFFICIENT")

    valid_documents: list[ValidDocumentInput] = []
    excluded: list[str] = []
    for item in parsed.documents:
        outcome = _read(rows_by_document[item.document_id], "outcome", None)
        if outcome != "VALID":
            excluded.append(item.document_id)
            continue
        result_id = str(
            _read(rows_by_document[item.document_id], "relevance_result_id", "")
        )
        valid_documents.append(
            ValidDocumentInput(
                document_id=item.document_id,
                position=item.position,
                content_checksum=item.content_checksum,
                relevance_result_id=result_id,
                source_ref=SourceRef(
                    source_id=item.document_id,
                    source_type=SourceType.document,
                    span_ref=None,
                ),
            )
        )
    if not valid_documents:
        raise Agent1InputBlocked("DOCUMENT_SET_NO_VALID_DOCUMENT")
    return ActiveDocumentSetInput(
        document_set_id=parsed.document_set_id,
        document_set_revision=parsed.revision,
        session_input_revision=parsed.session_input_revision,
        valid_documents=tuple(valid_documents),
        excluded_document_ids=tuple(excluded),
    )


def questionnaire_result_to_normalized_facts(
    result: QuestionnaireResult | Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Translate an authoritative 3.0.1 Q1--Q10 result into fact rows."""

    try:
        parsed = QuestionnaireResult.model_validate(result)
        return build_questionnaire_facts_from_result(parsed)
    except Agent1InputBlocked:
        raise
    except (TypeError, ValueError) as error:
        raise Agent1InputBlocked("QUESTIONNAIRE_NOT_READY") from error


def build_confirmed_agent1_input(
    confirmed_user_state,
    *,
    document_input: ActiveDocumentSetInput | None,
    document_facts: Sequence[Mapping[str, Any]],
    questionnaire_result: QuestionnaireResult | Mapping[str, Any] | None,
) -> ConfirmedAgent1Input:
    """Fuse only sources bound to the frozen ConfirmedUserState union.

    Document facts must already have been extracted from the VALID document
    projection returned by :func:`resolve_active_document_set`. Questionnaire
    facts are mapped through the signed 3.0.1 claim dictionary. This function
    never reads or persists UserGoal and never accepts Narrative.
    """

    try:
        state = _validate_confirmed_state(confirmed_user_state)
    except (TypeError, ValueError) as error:
        raise Agent1InputBlocked("CONFIRMED_USER_STATE_NOT_READY") from error

    expected_document = state.source_mode in {
        "document_only",
        "document_plus_questionnaire",
    }
    expected_questionnaire = state.source_mode in {
        "document_plus_questionnaire",
        "questionnaire_only",
    }
    if expected_document != (document_input is not None):
        raise Agent1InputBlocked("CONFIRMED_USER_STATE_SOURCE_MISMATCH")
    if expected_questionnaire != (questionnaire_result is not None):
        raise Agent1InputBlocked("CONFIRMED_USER_STATE_SOURCE_MISMATCH")
    if document_input is not None:
        if state.session_input_revision != document_input.session_input_revision:
            raise Agent1InputBlocked("CONFIRMED_USER_STATE_REVISION_MISMATCH")
        if not document_facts:
            raise Agent1InputBlocked("DOCUMENT_FACTS_NOT_READY")
    elif document_facts:
        raise Agent1InputBlocked("CONFIRMED_USER_STATE_SOURCE_MISMATCH")

    normalized: list[dict[str, Any]] = []
    valid_document_ids = (
        {item.document_id for item in document_input.valid_documents}
        if document_input is not None
        else set()
    )
    for raw_fact in document_facts:
        try:
            fact = NormalizedFactSchema.model_validate(raw_fact)
        except (TypeError, ValueError) as error:
            raise Agent1InputBlocked("DOCUMENT_FACT_INVALID") from error
        if fact.confirmation_status != "confirmed" or not fact.source_refs:
            raise Agent1InputBlocked("DOCUMENT_FACT_NOT_CONFIRMED")
        if any(
            ref.source_type != SourceType.document
            or ref.source_id not in valid_document_ids
            for ref in fact.source_refs
        ):
            raise Agent1InputBlocked("DOCUMENT_FACT_SOURCE_INVALID")
        normalized.append(fact.model_dump(mode="json"))

    if questionnaire_result is not None:
        try:
            result = QuestionnaireResult.model_validate(questionnaire_result)
        except (TypeError, ValueError) as error:
            raise Agent1InputBlocked("QUESTIONNAIRE_NOT_READY") from error
        reference = state.questionnaire_result_ref
        if reference is None or (
            result.questionnaire_result_id != reference.questionnaire_result_id
            or result.revision != reference.revision
            or result.content_checksum != reference.content_checksum
            or result.authority_status != "current"
        ):
            raise Agent1InputBlocked("QUESTIONNAIRE_REFERENCE_MISMATCH")
        expected_mode = (
            "without_document"
            if state.source_mode == "questionnaire_only"
            else "with_document"
        )
        if result.input_mode != expected_mode:
            raise Agent1InputBlocked("QUESTIONNAIRE_SOURCE_MISMATCH")
        normalized.extend(questionnaire_result_to_normalized_facts(result))

    if not normalized:
        raise Agent1InputBlocked("AGENT1_FACTS_NOT_READY")
    return ConfirmedAgent1Input(
        confirmed_user_state=state,
        document_ids=(
            tuple(item.document_id for item in document_input.valid_documents)
            if document_input is not None
            else ()
        ),
        facts=tuple(normalized),
    )


def _validate_confirmed_state(value):
    from backend.app.schemas.v3.flow_v31 import ConfirmedUserState

    state = ConfirmedUserState.model_validate(value)
    if state.authority_status != "current" or state.confirmation_status != "confirmed":
        raise ValueError("confirmed user state is not current")
    return state


def _as_mapping(value: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    result: dict[str, Any] = {}
    for field in (
        "schema_version",
        "document_set_id",
        "session_id",
        "revision",
        "session_input_revision",
        "authority_status",
        "documents",
        "owner_user_pk",
        "internal_user_pk",
        "document_id",
        "relevance_result_id",
        "document_relevance_id",
        "document_set_revision",
        "outcome",
    ):
        if hasattr(value, field):
            result[field] = getattr(value, field)
    return result


def _read(mapping: Mapping[str, Any], key: str, default: Any) -> Any:
    value = mapping.get(key, default)
    return getattr(value, "value", value)
