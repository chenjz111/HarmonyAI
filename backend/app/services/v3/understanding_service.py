"""V3 information-understanding ingestion, confirmation and revision service.

Non-conflicting Section A surface:

  * POST /api/v3/understandings            — multi-source ingestion; OCR failures
                                             are surfaced explicitly as source
                                             status = failed and never become a
                                             confirmed reference.
  * GET  /api/v3/understandings/{id}       — read model (owned only).
  * POST /api/v3/understandings/{id}/confirmations
                                           — optimistic-revision confirmation /
                                             correction, always materializing a
                                             new immutable revision.

Source text is never persisted or logged in plaintext (no at-rest key is
configured): only an irreversible sha256 hash is stored. Raw provider errors
are never returned to clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.session import (
    SessionInputRevision,
    V3IdempotencyRecord,
)
from backend.app.models.v3.understanding import (
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
    UnderstandingRun,
    UnderstandingSource,
)
from backend.app.schemas.v3.common import (
    AuthPrincipal,
    Degradation,
    SourceType,
)
from backend.app.schemas.v3.understanding import (
    CaseSummary,
    NormalizedFact as NormalizedFactSchema,
    SourceStatus,
    UnderstandingConfirmationRequest,
    UnderstandingRevisionResult,
    UnderstandingSource as UnderstandingSourceSchema,
    UnderstandingV31Request,
    UnderstandingV31Response,
    UnderstandingV3Request,
    UnderstandingV3Response,
)
from backend.app.services.v3.understanding_extraction import (
    build_provider_chain,
    extract_facts_for_sources,
    persist_normalized_facts,
    re_extract_facts,
)
from backend.ai_engine.v3.understanding_provider import ProviderFailureV3

_OPERATION_CREATE = "create_v3_understanding"
_OPERATION_CONFIRM_PREFIX = "confirm_v3_understanding"

_RUN_STATUSES = (
    "needs_confirmation",
    "confirmed",
    "degraded",
    "failed",
)
_DOCUMENT_SOURCE_TYPES = frozenset({"document", "case_summary"})
_WITH_DOCUMENT_TYPES = frozenset(
    {"document", "case_summary", "voice_transcript"}
)
_SUMMARY_MAX_CHARS = 140
_REVISION_RECORD_PREFIX = "rev:"


class OwnedResourceNotFound(RuntimeError):
    pass


class RevisionConflict(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class InvalidChange(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_FLOW_CONTRACT_V3_OWNER = "v3-owner-flow-1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _text_hash(text: str) -> str:
    return f"sha256:{sha256(text.strip().encode('utf-8')).hexdigest()}"


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _derive_input_mode(inputs: list[UnderstandingSourceSchema]) -> str:
    for source in inputs:
        if source.source_type.value in _WITH_DOCUMENT_TYPES:
            return "with_document"
    return "without_document"


@dataclass(frozen=True)
class _ResolvedSource:
    source: UnderstandingSourceSchema
    processing_status: str
    text: str | None = None
    document_id: str | None = None
    questionnaire_submission_id: str | None = None
    failure_reason: str | None = None


def _resolve_document(
    db: Session,
    principal: AuthPrincipal,
    session_row: SessionModel,
    source: UnderstandingSourceSchema,
) -> _ResolvedSource:
    document_id = source.text_ref
    document = (
        db.query(Document)
        .filter(
            Document.document_id == document_id,
            Document.user_id == principal.internal_user_pk,
            Document.session_id == session_row.session_id,
            Document.status != "deleted",
        )
        .one_or_none()
    )
    if document is None:
        return _ResolvedSource(source, "failed", failure_reason="DOCUMENT_NOT_FOUND")
    if document.ocr_error_code or not (document.ocr_text or "").strip():
        return _ResolvedSource(
            source,
            "failed",
            document_id=document_id,
            failure_reason="OCR_FAILED",
        )
    return _ResolvedSource(
        source,
        "ready",
        text=document.ocr_text,
        document_id=document_id,
    )


def _resolve_questionnaire(
    db: Session,
    principal: AuthPrincipal,
    source: UnderstandingSourceSchema,
) -> _ResolvedSource:
    submission_id = source.text_ref
    submission = (
        db.query(QuestionnaireSubmissionV3)
        .filter(
            QuestionnaireSubmissionV3.questionnaire_submission_id == submission_id,
            QuestionnaireSubmissionV3.internal_user_pk
            == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if submission is None:
        return _ResolvedSource(
            source,
            "failed",
            questionnaire_submission_id=submission_id,
            failure_reason="QUESTIONNAIRE_SUBMISSION_NOT_FOUND",
        )
    return _ResolvedSource(
        source,
        "ready",
        questionnaire_submission_id=submission_id,
        text=json.dumps(
            submission.answers_json,
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


def _resolve_inline(
    source: UnderstandingSourceSchema,
) -> _ResolvedSource:
    text = (source.text or "").strip()
    if not text:
        return _ResolvedSource(source, "failed", failure_reason="EMPTY_SOURCE_TEXT")
    return _ResolvedSource(source, "ready", text=text)


def _resolve_source(
    db: Session,
    principal: AuthPrincipal,
    session_row: SessionModel,
    source: UnderstandingSourceSchema,
) -> _ResolvedSource:
    if source.source_type.value == "questionnaire":
        if source.text_ref is None:
            return _ResolvedSource(
                source,
                "failed",
                failure_reason="QUESTIONNAIRE_REQUIRES_REF",
            )
        return _resolve_questionnaire(db, principal, source)
    if source.source_type.value in _DOCUMENT_SOURCE_TYPES:
        if source.text_ref is None:
            return _ResolvedSource(
                source,
                "failed",
                failure_reason="DOCUMENT_REQUIRES_REF",
            )
        return _resolve_document(db, principal, session_row, source)
    if source.text is not None:
        return _resolve_inline(source)
    return _ResolvedSource(source, "failed", failure_reason="UNRESOLVED_TEXT_REF")


def _run_status_and_reasons(
    resolved: list[_ResolvedSource],
) -> tuple[str, list[str]]:
    reasons = [
        item.failure_reason
        for item in resolved
        if item.failure_reason is not None
    ]
    usable = [item for item in resolved if item.processing_status == "ready"]
    if not usable:
        return "failed", reasons or ["NO_USABLE_SOURCE"]
    if len(usable) < len(resolved):
        return "degraded", reasons
    return "needs_confirmation", reasons


def _build_case_summary(
    resolved: list[_ResolvedSource],
    revision: int,
) -> dict[str, object] | None:
    documents = [
        item
        for item in resolved
        if item.processing_status == "ready"
        and item.source.source_type.value in _DOCUMENT_SOURCE_TYPES
    ]
    if not documents:
        return None
    summary_text = (documents[0].text or "").strip()
    truncated = summary_text[:_SUMMARY_MAX_CHARS]
    if len(summary_text) > _SUMMARY_MAX_CHARS:
        truncated = f"{truncated}…"
    return CaseSummary(
        case_summary_id=f"summary_{uuid.uuid4().hex}",
        source_document_ids=[
            item.document_id or item.source.source_id for item in documents
        ],
        revision=revision,
        status="needs_confirmation",
        title="材料内容摘要",
        summary=truncated or "已成功识别材料内容。",
        editable_fields=[],
        warnings=[],
    ).model_dump(mode="json")


def _revision_status_for(run_status: str) -> str:
    if run_status == "failed":
        return "degraded"
    return run_status


def _persist_run(
    db: Session,
    *,
    principal: AuthPrincipal,
    session_row: SessionModel,
    resolved: list[_ResolvedSource],
    idempotency_key: str,
) -> tuple[UnderstandingRun, list[UnderstandingSource]]:
    understanding_id = f"und_{uuid.uuid4().hex}"
    run_status, reason_codes = _run_status_and_reasons(resolved)
    is_new_flow = session_row.flow_contract_version == _FLOW_CONTRACT_V3_OWNER
    run = UnderstandingRun(
        understanding_id=understanding_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=session_row.id,
        current_revision=1,
        status=run_status,
        # New-flow sessions defer V3 safety (deferred_v3 / not_run / null);
        # legacy sessions keep a concrete safety status.
        safety_status=None if is_new_flow else "clear",
        flow_contract_version=session_row.flow_contract_version,
        input_revision=session_row.input_revision,
        safety_policy="deferred_v3" if is_new_flow else None,
        safety_evaluation_status="not_run" if is_new_flow else None,
        degradation_json={
            "active": run_status in {"degraded", "failed"},
            "reason_codes": reason_codes,
        },
    )
    db.add(run)
    db.flush()

    source_rows: list[UnderstandingSource] = []
    for item in resolved:
        source_rows.append(
            UnderstandingSource(
                source_id=item.source.source_id,
                understanding_id=understanding_id,
                source_type=item.source.source_type.value,
                processing_status=item.processing_status,
                document_id=item.document_id,
                audio_id=None,
                questionnaire_submission_id=item.questionnaire_submission_id,
                text_ciphertext=None,
                text_hash=_text_hash(item.text) if item.text else None,
                captured_at=_as_utc(item.source.captured_at),
            )
        )
    db.add_all(source_rows)

    case_summary = _build_case_summary(resolved, revision=1)
    revision = UnderstandingRevision(
        understanding_id=understanding_id,
        revision=1,
        previous_revision=None,
        status=_revision_status_for(run_status),
        case_summary_json=case_summary,
        presentation_json={
            "case_summary": case_summary,
            "sources": [
                {
                    "source_id": row.source_id,
                    "source_type": row.source_type,
                    "processing_status": row.processing_status,
                }
                for row in source_rows
            ],
            "normalized_facts": [],
            "applied_changes": [],
            "affected_fact_ids": [],
        },
        confirmation_decision=None,
        confirmed_at=None,
    )
    db.add(revision)
    return run, source_rows, revision


def _validate_v31_request_sources(
    session_row: SessionModel,
    request: UnderstandingV31Request,
) -> None:
    """Owner Flow Amendment 001 §4.2/§5 — an ingestion request must match the
    session's authoritative input state (input_mode + active_document_id),
    not only the input_revision. Without this check a stale or forged request
    could silently flip the selected mode or consume replaced material."""
    if session_row.input_mode is None:
        raise InvalidChange("INPUT_MODE_NOT_SELECTED", "尚未选择输入方式。")
    if session_row.input_mode == "with_document":
        active_document_id = session_row.active_document_id
        for source in request.inputs:
            if (
                active_document_id is None
                or source.source_type.value != "document"
                or source.text_ref != active_document_id
            ):
                raise InvalidChange(
                    "INPUT_SOURCE_MISMATCH",
                    "资料与会话当前输入状态不一致，请基于最新上传的资料重试。",
                )
        return
    for source in request.inputs:
        if source.source_type.value != "narrative" or source.text is None:
            raise InvalidChange(
                "INPUT_SOURCE_MISMATCH",
                "当前为无资料模式，仅支持文字描述输入。",
            )


def create_understanding(
    db: Session,
    principal: AuthPrincipal,
    request: UnderstandingV3Request | UnderstandingV31Request,
    idempotency_key: str,
) -> tuple[UnderstandingV3Response, bool]:
    session_row = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_id == request.session_id,
            SessionModel.user_id == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if session_row is None:
        raise OwnedResourceNotFound
    is_new_flow = session_row.flow_contract_version == _FLOW_CONTRACT_V3_OWNER
    if isinstance(request, UnderstandingV31Request):
        if not is_new_flow:
            raise InvalidChange(
                "FLOW_CONTRACT_MISMATCH",
                "该会话不支持 understanding_v3.1 请求。",
            )
        if session_row.input_revision != request.expected_input_revision:
            raise InputRevisionConflict
        _validate_v31_request_sources(session_row, request)
    elif is_new_flow:
        # A v3.0-shaped ingestion on a v3-owner-flow-1 session would mutate
        # session state the session contract owns elsewhere; only v3.1 speaks
        # the new-flow input contract.
        raise InvalidChange(
            "FLOW_CONTRACT_MISMATCH",
            "新流程会话仅接受 understanding_v3.1 请求。",
        )

    request_hash = _request_hash(request.model_dump(mode="json"))
    record = (
        db.query(V3IdempotencyRecord)
        .filter(
            V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
            V3IdempotencyRecord.operation == _OPERATION_CREATE,
            V3IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded" and record.resource_id:
            run = _owned_run(db, principal, record.resource_id)
            if run is not None:
                return _read_model(db, run), True

    resolved = [_resolve_source(db, principal, session_row, src) for src in request.inputs]
    run, source_rows, revision = _persist_run(
        db,
        principal=principal,
        session_row=session_row,
        resolved=resolved,
        idempotency_key=idempotency_key,
    )

    # AI fact extraction: OCR/Narrative text through the Understanding
    # Provider against the approved claim dictionary. An unavailable provider
    # or an empty result leaves normalized_facts empty — never fabricated.
    fact_dicts, _extraction_reasons = extract_facts_for_sources(
        build_provider_chain(),
        resolved,
    )
    presentation = dict(revision.presentation_json or {})
    presentation["normalized_facts"] = fact_dicts
    revision.presentation_json = presentation
    persist_normalized_facts(
        db,
        understanding_id=run.understanding_id,
        understanding_revision=1,
        fact_dicts=fact_dicts,
        source_rows=source_rows,
    )

    # Legacy sessions keep deriving input_mode from the run. New-flow sessions
    # own input_mode exclusively through input-transitions (Amendment 001 §5):
    # an ingestion request must match the authoritative state instead of
    # silently rewriting it without an input_revision bump.
    if not is_new_flow:
        session_row.input_mode = _derive_input_mode(request.inputs)

    if record is None:
        record = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
            operation=_OPERATION_CREATE,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(record)
    record.resource_type = "understanding"
    record.resource_id = run.understanding_id
    record.status = "succeeded"
    record.response_code = 201
    db.commit()
    return _read_model(db, run), False


def get_understanding(
    db: Session,
    principal: AuthPrincipal,
    understanding_id: str,
    *,
    revision: int | None = None,
) -> UnderstandingV3Response:
    run = _owned_run(db, principal, understanding_id)
    if run is None:
        raise OwnedResourceNotFound
    target = None
    for_revision = False
    if revision is not None:
        if revision < 1 or revision > run.current_revision:
            raise OwnedResourceNotFound
        target = _revision(db, understanding_id, revision)
        if target is None:
            raise OwnedResourceNotFound
        for_revision = True
    return _read_model(db, run, revision_row=target, for_revision=for_revision)


def confirm_understanding(
    db: Session,
    principal: AuthPrincipal,
    understanding_id: str,
    request: UnderstandingConfirmationRequest,
    idempotency_key: str,
) -> tuple[UnderstandingRevisionResult, bool]:
    run = _owned_run(db, principal, understanding_id)
    if run is None:
        raise OwnedResourceNotFound

    operation = f"{_OPERATION_CONFIRM_PREFIX}:{understanding_id}"
    request_hash = _request_hash(request.model_dump(mode="json"))
    record = (
        db.query(V3IdempotencyRecord)
        .filter(
            V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
            V3IdempotencyRecord.operation == operation,
            V3IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded" and record.resource_id:
            previous_revision, previous_input_revision = _confirmation_from_record(
                record.resource_id
            )
            if previous_revision is not None:
                revision_row = _revision(db, understanding_id, previous_revision)
                if revision_row is not None:
                    return _result_from_revision(
                        db,
                        run,
                        revision_row,
                        input_revision=previous_input_revision,
                    ), True

    if request.expected_revision != run.current_revision:
        raise RevisionConflict
    session_row = (
        db.query(SessionModel)
        .filter(SessionModel.id == run.session_row_id)
        .one_or_none()
    )
    if session_row is None:
        raise OwnedResourceNotFound
    if (
        request.schema_version == "understanding_v3.1"
        and request.decision in {"reject_source", "cannot_confirm"}
    ):
        raise InvalidChange(
            "UNSUPPORTED_DECISION",
            "该流程版本请通过输入切换丢弃或重新上传资料。",
        )
    if request.reprocess_requested and request.edited_summary_text is None:
        raise InvalidChange(
            "REPROCESS_NOT_SUPPORTED",
            "重新处理需要提供修改后的摘要文本。",
        )

    current = _revision(db, understanding_id, run.current_revision)
    if current is None:
        raise OwnedResourceNotFound
    sources = (
        db.query(UnderstandingSource)
        .filter(UnderstandingSource.understanding_id == understanding_id)
        .all()
    )

    next_revision = run.current_revision + 1
    (
        case_summary,
        applied_changes,
        affected_fact_ids,
        new_fact_dicts,
    ) = _apply_decision(
        request,
        current,
    )
    if request.decision == "reject_source":
        # There is no 'rejected' source status; the closest contract value for
        # a user-rejected material source is 'skipped'.
        for source_row in sources:
            source_row.processing_status = "skipped"
    new_status = _new_revision_status(request.decision, run.status)
    # On a successful confirmation the CaseSummary is confirmed and its
    # revision aligns with the new Understanding revision (no inner state
    # left behind on the old revision / needs_confirmation).
    if new_status == "confirmed" and isinstance(case_summary, dict):
        case_summary["status"] = "confirmed"
        case_summary["revision"] = next_revision
    revision_row = UnderstandingRevision(
        understanding_id=understanding_id,
        revision=next_revision,
        previous_revision=run.current_revision,
        status=new_status,
        case_summary_json=case_summary,
        presentation_json={
            "case_summary": case_summary,
            "sources": [
                {
                    "source_id": row.source_id,
                    "source_type": row.source_type,
                    "processing_status": row.processing_status,
                }
                for row in sources
            ],
            # Carry the normalized facts forward; a full-text edit replaces
            # them via _apply_full_text_edit on the current revision. On a
            # successful confirmation every fact is confirmed together with
            # the outer status so Agent 1 consumes a coherent snapshot.
            "normalized_facts": _confirmed_facts_for(
                new_fact_dicts
                if new_fact_dicts is not None
                else (current.presentation_json or {}).get("normalized_facts") or [],
                confirmed=new_status == "confirmed",
            ),
            "applied_changes": applied_changes,
            "affected_fact_ids": affected_fact_ids,
        },
        confirmation_decision=request.decision,
        confirmed_at=_utc_now() if new_status == "confirmed" else None,
    )
    db.add(revision_row)
    if new_fact_dicts is not None:
        persist_normalized_facts(
            db,
            understanding_id=understanding_id,
            understanding_revision=next_revision,
            fact_dicts=_confirmed_facts_for(
                new_fact_dicts,
                confirmed=new_status == "confirmed",
            ),
            source_rows=sources,
        )
    run.current_revision = next_revision
    run.status = _run_status_for_revision(new_status, request.decision)

    new_input_revision: int | None = None
    if (
        new_status == "confirmed"
        and session_row.flow_contract_version == _FLOW_CONTRACT_V3_OWNER
        and session_row.input_mode == "with_document"
    ):
        _validate_bind_matches_active_input(db, session_row, understanding_id)
        new_input_revision = _cas_bind_understanding(
            db,
            session_row,
            understanding_id,
            next_revision,
            request.expected_input_revision,
        )

    if record is None:
        record = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(record)
    record.resource_type = "understanding_revision"
    resource_id = f"{understanding_id}:{_REVISION_RECORD_PREFIX}{next_revision}"
    if new_input_revision is not None:
        resource_id += f":in:{new_input_revision}"
    record.resource_id = resource_id
    record.status = "succeeded"
    record.response_code = 201
    db.commit()
    return (
        _result_from_revision(
            db, run, revision_row, input_revision=new_input_revision
        ),
        False,
    )


def _confirmed_facts_for(
    fact_dicts: list[dict],
    *,
    confirmed: bool,
) -> list[dict]:
    """Return normalized fact dicts with the confirmation status applied."""
    result = [dict(item) for item in fact_dicts]
    if confirmed:
        for fact in result:
            fact["confirmation_status"] = "confirmed"
    return result


def _apply_decision(
    request: UnderstandingConfirmationRequest,
    current: UnderstandingRevision,
) -> tuple[
    dict[str, object] | None,
    list[str],
    list[str],
    list[dict] | None,
]:
    decision = request.decision
    if decision == "confirm":
        return (
            current.case_summary_json,
            [],
            [],
            None,
        )
    if decision == "confirm_with_changes":
        if request.edited_summary_text is not None:
            return _apply_full_text_edit(current, request)
        return (*_apply_changes(current, request), None)
    if decision == "reject_source":
        return None, [], [], None
    # cannot_confirm: keep the materialized snapshot undecided.
    return current.case_summary_json, [], [], None


def _apply_full_text_edit(
    current: UnderstandingRevision,
    request: UnderstandingConfirmationRequest,
) -> tuple[dict[str, object] | None, list[str], list[str], list[dict]]:
    base = current.case_summary_json
    if base is None:
        raise InvalidChange("NO_CASE_SUMMARY", "当前没有可确认的材料摘要。")
    case_summary = json.loads(json.dumps(base))
    case_summary["summary"] = request.edited_summary_text
    case_summary["status"] = "confirmed"
    # A full-text edit must re-derive facts from the edited summary, not copy
    # the old Evidence. When the Understanding provider is unavailable the
    # edit cannot be confirmed: publishing empty facts as a confirmed
    # revision would fabricate a clean result.
    fact_dicts, affected_fact_ids = _re_extract_facts(request.edited_summary_text)
    return case_summary, ["chg_summary_edit"], affected_fact_ids, fact_dicts


def _re_extract_facts(edited_text: str) -> tuple[list[dict], list[str]]:
    """Controlled fact re-extraction over the edited summary text.

    Re-runs the Understanding provider against the approved claim dictionary
    and returns (new fact dicts, affected fact ids). When the provider is
    unavailable the edit cannot be confirmed: a stable error is raised and
    the old revision is kept instead of publishing empty facts.
    """
    chain = build_provider_chain()
    if chain is None:
        raise InvalidChange(
            "FACT_EXTRACTION_UNAVAILABLE",
            "事实提取服务暂不可用，无法确认修改后的摘要，请稍后重试。",
        )
    try:
        fact_dicts, affected_ids = re_extract_facts(chain, edited_text)
    except ProviderFailureV3:
        raise InvalidChange(
            "FACT_EXTRACTION_UNAVAILABLE",
            "事实提取服务暂不可用，无法确认修改后的摘要，请稍后重试。",
        ) from None
    if not fact_dicts:
        raise InvalidChange(
            "FACT_EXTRACTION_UNAVAILABLE",
            "暂无法从修改后的摘要中提取有效事实，请稍后重试。",
        )
    return fact_dicts, affected_ids


def _apply_changes(
    current: UnderstandingRevision,
    request: UnderstandingConfirmationRequest,
) -> tuple[dict[str, object] | None, list[str], list[str]]:
    base = current.case_summary_json
    if base is None:
        raise InvalidChange("NO_CASE_SUMMARY", "当前没有可确认的材料摘要。")
    case_summary = json.loads(json.dumps(base))
    applied: list[str] = []
    affected: list[str] = []
    for index, change in enumerate(request.changes, start=1):
        change_id = f"chg_{index}"
        if change.target_type == "case_summary":
            if change.target_id != case_summary.get("case_summary_id"):
                raise InvalidChange("CASE_SUMMARY_NOT_FOUND", "摘要与修正目标不匹配。")
            if change.field not in {"title", "summary"}:
                raise InvalidChange(
                    "UNSUPPORTED_FIELD",
                    "该摘要字段不支持在线修正。",
                )
            if not isinstance(change.new_value, str):
                raise InvalidChange("INVALID_VALUE", "摘要修正值必须是文本。")
            case_summary[change.field] = change.new_value
            applied.append(change_id)
            continue
        if change.target_type == "normalized_fact":
            raise InvalidChange(
                "FACT_NOT_FOUND",
                "当前理解尚未包含可修正的事实条目。",
            )
        raise InvalidChange(
            "UNSUPPORTED_CHANGE",
            "该修正目标类型暂不支持。",
        )
    return case_summary, applied, affected


def _new_revision_status(decision: str, _run_status: str) -> str:
    if decision == "confirm":
        return "confirmed"
    if decision == "confirm_with_changes":
        return "confirmed"
    if decision == "reject_source":
        return "degraded"
    return "needs_confirmation"


def _run_status_for_revision(revision_status: str, decision: str) -> str:
    if decision == "reject_source":
        return "failed"
    return revision_status


def _result_status(decision: str | None) -> str:
    if decision == "reject_source":
        return "rejected"
    if decision in {"confirm", "confirm_with_changes"}:
        return "confirmed"
    return "needs_confirmation"


def _result_from_revision(
    db: Session,
    run: UnderstandingRun,
    revision_row: UnderstandingRevision,
    *,
    input_revision: int | None = None,
) -> UnderstandingRevisionResult:
    presentation = revision_row.presentation_json or {}
    return UnderstandingRevisionResult(
        understanding_id=revision_row.understanding_id,
        previous_revision=revision_row.previous_revision or 1,
        revision=revision_row.revision,
        status=_result_status(revision_row.confirmation_decision),
        applied_changes=list(presentation.get("applied_changes") or []),
        affected_fact_ids=list(presentation.get("affected_fact_ids") or []),
        input_revision=input_revision,
        # Reconstruct from the recorded revision so an idempotent replay returns
        # the first success's snapshot, not the session's later state.
        understanding=_read_model(
            db, run, revision_row=revision_row, for_revision=True
        ),
    )


def _validate_bind_matches_active_input(
    db: Session,
    session_row: SessionModel,
    understanding_id: str,
) -> None:
    """Amendment 001 §5 — binding a confirmed understanding as the session's
    active input is only valid when the run's ready sources are exactly the
    session's active document. The input_revision CAS alone would still bind
    material that was created before the active document was replaced."""
    ready_rows = (
        db.query(UnderstandingSource)
        .filter(
            UnderstandingSource.understanding_id == understanding_id,
            UnderstandingSource.processing_status == "ready",
        )
        .all()
    )
    ready_document_ids = {row.document_id for row in ready_rows}
    if (
        any(row.source_type not in _DOCUMENT_SOURCE_TYPES for row in ready_rows)
        or ready_document_ids != {session_row.active_document_id}
    ):
        raise InvalidChange(
            "INPUT_SOURCE_MISMATCH",
            "资料与会话当前输入状态不一致，请重新上传后再确认。",
        )


def _cas_bind_understanding(
    db: Session,
    session_row: SessionModel,
    understanding_id: str,
    revision: int,
    expected: int | None,
) -> int:
    """Atomically CAS the session input_revision and bind the confirmed
    understanding reference. Fails with InputRevisionConflict if the session's
    input_revision no longer matches ``expected`` (no read-then-write race)."""
    if expected is None:
        raise InvalidChange("INPUT_REVISION_REQUIRED", "该流程需要输入版本。")
    result = db.execute(
        update(SessionModel)
        .where(
            SessionModel.id == session_row.id,
            SessionModel.input_revision == expected,
        )
        .values(
            input_revision=expected + 1,
            active_understanding_id=understanding_id,
            active_understanding_revision=revision,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise InputRevisionConflict
    next_input_revision = expected + 1
    db.add(
        SessionInputRevision(
            session_row_id=session_row.id,
            input_revision=next_input_revision,
            input_mode=session_row.input_mode,
            active_document_id=session_row.active_document_id,
            active_understanding_id=understanding_id,
            active_understanding_revision=revision,
            active_questionnaire_submission_id=session_row.active_questionnaire_submission_id,
            action="confirm_source",
        )
    )
    return next_input_revision


def _confirmation_from_record(resource_id: str) -> tuple[int | None, int | None]:
    """Parse (revision, input_revision) from a confirmation record resource_id.

    Format: ``{understanding_id}:rev:{revision}`` or
    ``{understanding_id}:rev:{revision}:in:{input_revision}``.
    """
    prefix = _REVISION_RECORD_PREFIX
    if prefix not in resource_id:
        return None, None
    tail = resource_id.split(prefix, 1)[1]
    revision_str = tail
    input_revision = None
    if ":in:" in tail:
        revision_str, input_str = tail.split(":in:", 1)
        try:
            input_revision = int(input_str)
        except ValueError:
            input_revision = None
    try:
        revision = int(revision_str)
    except ValueError:
        revision = None
    return revision, input_revision


def _owned_run(
    db: Session,
    principal: AuthPrincipal,
    understanding_id: str,
) -> UnderstandingRun | None:
    return (
        db.query(UnderstandingRun)
        .filter(
            UnderstandingRun.understanding_id == understanding_id,
            UnderstandingRun.internal_user_pk == principal.internal_user_pk,
        )
        .one_or_none()
    )


def _revision(
    db: Session,
    understanding_id: str,
    revision: int,
) -> UnderstandingRevision | None:
    return (
        db.query(UnderstandingRevision)
        .filter(
            UnderstandingRevision.understanding_id == understanding_id,
            UnderstandingRevision.revision == revision,
        )
        .one_or_none()
    )


def _read_model(
    db: Session,
    run: UnderstandingRun,
    *,
    revision_row: UnderstandingRevision | None = None,
    for_revision: bool = False,
) -> UnderstandingV3Response:
    if revision_row is None:
        revision_row = _revision(db, run.understanding_id, run.current_revision)
    sources = (
        db.query(UnderstandingSource)
        .filter(UnderstandingSource.understanding_id == run.understanding_id)
        .all()
    )
    snapshot_sources = None
    if revision_row is not None:
        snapshot_sources = (revision_row.presentation_json or {}).get("sources")
    case_summary = None
    if revision_row is not None and revision_row.case_summary_json is not None:
        case_summary = CaseSummary.model_validate(revision_row.case_summary_json)
    if isinstance(snapshot_sources, list) and snapshot_sources:
        source_statuses = [
            SourceStatus(
                source_id=item["source_id"],
                source_type=item["source_type"],
                status=item["processing_status"],
            )
            for item in snapshot_sources
        ]
    else:
        source_statuses = [
            SourceStatus(
                source_id=row.source_id,
                source_type=row.source_type,
                status=row.processing_status,
            )
            for row in sources
        ]
    normalized_facts: list[NormalizedFactSchema] = []
    if revision_row is not None:
        presentation = revision_row.presentation_json or {}
        for item in presentation.get("normalized_facts") or []:
            normalized_facts.append(NormalizedFactSchema.model_validate(item))
    common = dict(
        understanding_id=run.understanding_id,
        revision=run.current_revision
        if revision_row is None
        else revision_row.revision,
        status=revision_row.status if for_revision else run.status,
        case_summary=case_summary,
        voice_transcripts=[],
        normalized_facts=normalized_facts,
        source_statuses=source_statuses,
        safety_signal_refs=[],
        degradation=Degradation.model_validate(run.degradation_json),
    )
    if run.flow_contract_version == _FLOW_CONTRACT_V3_OWNER:
        return UnderstandingV31Response(
            schema_version="understanding_v3.1",
            flow_contract_version=_FLOW_CONTRACT_V3_OWNER,
            safety_policy="deferred_v3",
            safety_evaluation_status="not_run",
            safety_status=None,
            **common,
        )
    return UnderstandingV3Response(
        schema_version="understanding_v3.0",
        safety_status=run.safety_status,
        **common,
    )
