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
    SourceStatus,
    UnderstandingConfirmationRequest,
    UnderstandingRevisionResult,
    UnderstandingSource as UnderstandingSourceSchema,
    UnderstandingV3Request,
    UnderstandingV3Response,
)

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
            "applied_changes": [],
            "affected_fact_ids": [],
        },
        confirmation_decision=None,
        confirmed_at=None,
    )
    db.add(revision)
    return run, source_rows


def create_understanding(
    db: Session,
    principal: AuthPrincipal,
    request: UnderstandingV3Request,
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
    run, source_rows = _persist_run(
        db,
        principal=principal,
        session_row=session_row,
        resolved=resolved,
        idempotency_key=idempotency_key,
    )

    # Persist the flow input mode derived from the material sources.
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
            previous_revision = _revision_from_record(record.resource_id)
            if previous_revision is not None:
                revision_row = _revision(db, understanding_id, previous_revision)
                if revision_row is not None:
                    return _result_from_revision(revision_row), True

    if request.expected_revision != run.current_revision:
        raise RevisionConflict
    session_row = (
        db.query(SessionModel)
        .filter(SessionModel.id == run.session_row_id)
        .one_or_none()
    )
    if session_row is None:
        raise OwnedResourceNotFound
    if request.expected_input_revision is not None:
        if session_row.input_revision != request.expected_input_revision:
            raise InputRevisionConflict
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
    case_summary, applied_changes, affected_fact_ids = _apply_decision(
        request,
        current,
    )
    if request.decision == "reject_source":
        # There is no 'rejected' source status; the closest contract value for
        # a user-rejected material source is 'skipped'.
        for source_row in sources:
            source_row.processing_status = "skipped"
    new_status = _new_revision_status(request.decision, run.status)
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
            "applied_changes": applied_changes,
            "affected_fact_ids": affected_fact_ids,
        },
        confirmation_decision=request.decision,
        confirmed_at=_utc_now() if new_status == "confirmed" else None,
    )
    db.add(revision_row)
    run.current_revision = next_revision
    run.status = _run_status_for_revision(new_status, request.decision)

    if (
        new_status == "confirmed"
        and session_row.flow_contract_version == _FLOW_CONTRACT_V3_OWNER
    ):
        _bind_session_active_understanding(
            db, session_row, understanding_id, next_revision
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
    record.resource_id = f"{understanding_id}:{_REVISION_RECORD_PREFIX}{next_revision}"
    record.status = "succeeded"
    record.response_code = 201
    db.commit()
    return _result_from_revision(revision_row), False


def _apply_decision(
    request: UnderstandingConfirmationRequest,
    current: UnderstandingRevision,
) -> tuple[dict[str, object] | None, list[str], list[str]]:
    decision = request.decision
    if decision == "confirm":
        return (
            current.case_summary_json,
            [],
            [],
        )
    if decision == "confirm_with_changes":
        if request.edited_summary_text is not None:
            return _apply_full_text_edit(current, request)
        return _apply_changes(current, request)
    if decision == "reject_source":
        return None, [], []
    # cannot_confirm: keep the materialized snapshot undecided.
    return current.case_summary_json, [], []


def _apply_full_text_edit(
    current: UnderstandingRevision,
    request: UnderstandingConfirmationRequest,
) -> tuple[dict[str, object] | None, list[str], list[str]]:
    base = current.case_summary_json
    if base is None:
        raise InvalidChange("NO_CASE_SUMMARY", "当前没有可确认的材料摘要。")
    case_summary = json.loads(json.dumps(base))
    case_summary["summary"] = request.edited_summary_text
    case_summary["status"] = "confirmed"
    # Facts are re-extracted from the edited text (empty here until a claim
    # dictionary/provider is wired); the edit itself is recorded as a
    # user_correction so it never impersonates the OCR source.
    return case_summary, ["chg_summary_edit"], []


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


def _result_from_revision(revision_row: UnderstandingRevision) -> UnderstandingRevisionResult:
    presentation = revision_row.presentation_json or {}
    return UnderstandingRevisionResult(
        understanding_id=revision_row.understanding_id,
        previous_revision=revision_row.previous_revision or 1,
        revision=revision_row.revision,
        status=_result_status(revision_row.confirmation_decision),
        applied_changes=list(presentation.get("applied_changes") or []),
        affected_fact_ids=list(presentation.get("affected_fact_ids") or []),
    )


def _bind_session_active_understanding(
    db: Session,
    session_row: SessionModel,
    understanding_id: str,
    revision: int,
) -> None:
    next_input_revision = (session_row.input_revision or 0) + 1
    session_row.active_understanding_id = understanding_id
    session_row.active_understanding_revision = revision
    session_row.input_revision = next_input_revision
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


def _revision_from_record(resource_id: str) -> int | None:
    prefix = f"{_REVISION_RECORD_PREFIX}"
    if ":" not in resource_id or prefix not in resource_id:
        return None
    marker = resource_id.split(":", 1)[1]
    if not marker.startswith(prefix):
        return None
    try:
        return int(marker[len(prefix):])
    except ValueError:
        return None


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
    return UnderstandingV3Response(
        schema_version="understanding_v3.0",
        understanding_id=run.understanding_id,
        revision=run.current_revision
        if revision_row is None
        else revision_row.revision,
        status=revision_row.status if for_revision else run.status,
        case_summary=case_summary,
        voice_transcripts=[],
        normalized_facts=[],
        source_statuses=source_statuses,
        safety_status=run.safety_status,
        safety_signal_refs=[],
        degradation=Degradation.model_validate(run.degradation_json),
    )
