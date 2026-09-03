"""V3.1 questionnaire submission service (Issue #99).

Persists a complete Q1-Q10 submission against the canonical approved manifest,
then atomically binds it as the session's active questionnaire source via an
optimistic input_revision CAS and an immutable session_input_revisions
snapshot (action = submit_questionnaire).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.session import (
    SessionInputRevision,
    V3IdempotencyRecord,
)
from backend.app.models.v3.understanding import QuestionnaireSubmissionV3
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.questionnaire import (
    QuestionnaireSubmissionRequest,
    QuestionnaireSubmissionResponse,
)
from backend.app.services.v3.activity_service import (
    _approved_questionnaire_manifest,
    _QUESTIONNAIRE_COMPLETE,
    _QUESTIONNAIRE_QUESTION_IDS,
)
from backend.app.services.v3.session_service import (
    FLOW_CONTRACT_V3_OWNER,
    FlowContractUnsupported,
    OwnedResourceNotFound,
    get_owned_session_row,
)


_OPERATION = "submit_v3_questionnaire"


class FlowContractMismatch(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class InvalidQuestionnaire(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _validate_complete_answers(answers: list) -> None:
    if len(answers) != _QUESTIONNAIRE_COMPLETE:
        raise InvalidQuestionnaire(
            "QUESTIONNAIRE_INCOMPLETE", "需要完整提交10道状态问卷。"
        )
    answer_ids = {item.question_id for item in answers}
    if answer_ids != _QUESTIONNAIRE_QUESTION_IDS:
        raise InvalidQuestionnaire(
            "QUESTIONNAIRE_INCOMPLETE", "需要完整提交10道状态问卷（唯一题号）。"
        )


def _validate_answers_against_manifest(answers: list, manifest: dict) -> None:
    """Per-question validation: answer type, option codes, value range,
    multi-select bounds and mutual exclusion — against the approved manifest."""
    questions = {q["question_id"]: q for q in manifest.get("questions", [])}
    for answer in answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise InvalidQuestionnaire(
                "QUESTIONNAIRE_UNKNOWN_QUESTION", "未知题号。"
            )
        if answer.answer_type != question["answer_type"]:
            raise InvalidQuestionnaire(
                "QUESTIONNAIRE_ANSWER_TYPE_MISMATCH", "答案类型不匹配。"
            )
        if question["answer_type"] == "frequency_0_4":
            value = answer.value
            if not isinstance(value, int) or not (0 <= value <= 4):
                raise InvalidQuestionnaire(
                    "QUESTIONNAIRE_INVALID_VALUE", "取值超出范围。"
                )
            continue
        # multi_choice_evidence / single_choice_evidence
        selected = (
            answer.value if isinstance(answer.value, list) else [answer.value]
        )
        option_codes = {o["option_code"]: o for o in question.get("options", [])}
        min_sel = question.get("min_selections") or 1
        max_sel = question.get("max_selections") or len(option_codes)
        if len(selected) < min_sel or len(selected) > max_sel:
            raise InvalidQuestionnaire(
                "QUESTIONNAIRE_SELECTION_BOUNDS", "选择数量超出范围。"
            )
        for code in selected:
            if code not in option_codes:
                raise InvalidQuestionnaire(
                    "QUESTIONNAIRE_INVALID_OPTION", "非法选项。"
                )
        for code in selected:
            exclusive = option_codes[code].get("exclusive_with") or []
            if "*" in exclusive and len(selected) != 1:
                raise InvalidQuestionnaire(
                    "QUESTIONNAIRE_MUTUAL_EXCLUSION",
                    "互斥选项不能与其他选项同时选择。",
                )
            for other in selected:
                if other != code and other in exclusive:
                    raise InvalidQuestionnaire(
                        "QUESTIONNAIRE_MUTUAL_EXCLUSION",
                        "互斥选项不能与其他选项同时选择。",
                    )


def _validate_manifest(
    schema_id: str,
    schema_version: str,
    manifest_version: str,
    content_checksum: str,
) -> dict:
    manifest = _approved_questionnaire_manifest()
    if manifest is None:
        raise InvalidQuestionnaire(
            "QUESTIONNAIRE_MANIFEST_UNAVAILABLE", "问卷清单暂不可用。"
        )
    if schema_id != manifest.get("schema_id"):
        raise InvalidQuestionnaire("QUESTIONNAIRE_INVALID_SCHEMA", "问卷 schema 无效。")
    if schema_version != manifest.get("schema_version"):
        raise InvalidQuestionnaire(
            "QUESTIONNAIRE_INVALID_SCHEMA_VERSION", "问卷 schema 版本无效。"
        )
    if manifest_version != manifest.get("manifest_version"):
        raise InvalidQuestionnaire(
            "QUESTIONNAIRE_INVALID_MANIFEST", "问卷 manifest 版本无效。"
        )
    if content_checksum != manifest.get("content_checksum"):
        raise InvalidQuestionnaire(
            "QUESTIONNAIRE_INVALID_CHECKSUM", "问卷内容校验无效。"
        )
    return manifest


def _confirmation_from_record(resource_id: str) -> tuple[str | None, int | None]:
    if ":" not in resource_id:
        return None, None
    submission_id, input_revision_str = resource_id.split(":", 1)
    try:
        input_revision = int(input_revision_str)
    except ValueError:
        input_revision = None
    return submission_id, input_revision


def submit_questionnaire(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    request: QuestionnaireSubmissionRequest,
    idempotency_key: str,
) -> tuple[QuestionnaireSubmissionResponse, bool]:
    session_row = get_owned_session_row(db, principal, session_id)
    if session_row.flow_contract_version != FLOW_CONTRACT_V3_OWNER:
        raise FlowContractMismatch

    request_hash = _request_hash(request.model_dump(mode="json"))
    record = (
        db.query(V3IdempotencyRecord)
        .filter(
            V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
            V3IdempotencyRecord.operation == _OPERATION,
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
            submission_id, input_revision = _confirmation_from_record(
                record.resource_id
            )
            if submission_id is not None:
                submission = (
                    db.query(QuestionnaireSubmissionV3)
                    .filter(
                        QuestionnaireSubmissionV3.questionnaire_submission_id
                        == submission_id
                    )
                    .one_or_none()
                )
                if submission is not None:
                    return (
                        QuestionnaireSubmissionResponse(
                            questionnaire_submission_id=submission.questionnaire_submission_id,
                            schema_id=submission.schema_id,
                            schema_version=submission.schema_version,
                            manifest_version=submission.manifest_version,
                            content_checksum=submission.content_checksum,
                            input_revision=input_revision or session_row.input_revision or 1,
                            status="submitted",
                        ),
                        True,
                    )

    _validate_complete_answers(request.answers)
    manifest = _validate_manifest(
        request.schema_id,
        request.schema_version,
        request.manifest_version,
        request.content_checksum,
    )
    _validate_answers_against_manifest(request.answers, manifest)

    submission_id = f"qsub_{uuid.uuid4().hex}"
    submission = QuestionnaireSubmissionV3(
        questionnaire_submission_id=submission_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=session_row.id,
        schema_id=request.schema_id,
        schema_version=request.schema_version,
        manifest_version=request.manifest_version,
        content_checksum=request.content_checksum,
        time_window_days=7,
        answers_json=[item.model_dump(mode="json") for item in request.answers],
        idempotency_key=idempotency_key,
        submitted_at=_utc_now(),
    )
    db.add(submission)
    db.flush()

    if record is None:
        record = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
            operation=_OPERATION,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(record)

    next_revision = _cas_submit_questionnaire(
        db,
        session_row,
        request.expected_input_revision,
        submission_id,
    )
    db.add(
        SessionInputRevision(
            session_row_id=session_row.id,
            input_revision=next_revision,
            input_mode=session_row.input_mode,
            active_document_id=session_row.active_document_id,
            active_understanding_id=session_row.active_understanding_id,
            active_understanding_revision=session_row.active_understanding_revision,
            active_questionnaire_submission_id=submission_id,
            action="submit_questionnaire",
        )
    )

    record.resource_type = "questionnaire_submission"
    record.resource_id = f"{submission_id}:{next_revision}"
    record.status = "succeeded"
    record.response_code = 201
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return (
        QuestionnaireSubmissionResponse(
            questionnaire_submission_id=submission_id,
            schema_id=request.schema_id,
            schema_version=request.schema_version,
            manifest_version=request.manifest_version,
            content_checksum=request.content_checksum,
            input_revision=next_revision,
            status="submitted",
        ),
        False,
    )


def _cas_submit_questionnaire(
    db: Session,
    session_row: SessionModel,
    expected: int,
    submission_id: str,
) -> int:
    result = db.execute(
        update(SessionModel)
        .where(
            SessionModel.id == session_row.id,
            SessionModel.input_revision == expected,
        )
        .values(
            input_revision=expected + 1,
            active_questionnaire_submission_id=submission_id,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise InputRevisionConflict
    return expected + 1
