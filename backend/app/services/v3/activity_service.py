"""V3 session activity state transitions (Amendment 001 §4.1).

Implements select_mode / replace_document / discard_document with
ownership, idempotency, and database-level input_revision optimistic
concurrency: the revision is advanced with a single atomic
``UPDATE ... WHERE input_revision = expected`` so two requests carrying
the same stale revision cannot both succeed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.activity import V3SessionActivity
from backend.app.models.v3.session import V3IdempotencyRecord
from backend.app.schemas.v3.activity import (
    SUPPORTED_FLOW_CONTRACT_VERSION,
    InputTransitionRequest,
    InputTransitionResult,
    SessionActivityState,
)
from backend.app.schemas.v3.common import AuthPrincipal


_TRANSITION_OPERATION = "input_transition"


class FlowContractUnsupported(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class TransitionNotAllowed(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class OwnedResourceNotFound(RuntimeError):
    pass


class DocumentNotOwned(RuntimeError):
    pass


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


def _parse_ref(value: str | None) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _activity_to_state(
    activity: V3SessionActivity | None,
    session_id: str,
) -> SessionActivityState:
    if activity is None:
        return SessionActivityState(
            session_id=session_id,
            flow_contract_version=None,
            input_mode=None,
            input_revision=1,
            active_document_id=None,
            understanding_ref=None,
            questionnaire_ref=None,
        )
    return SessionActivityState(
        session_id=activity.session_id,
        flow_contract_version=activity.flow_contract_version,
        input_mode=activity.input_mode,
        input_revision=activity.input_revision,
        active_document_id=activity.active_document_id,
        understanding_ref=_parse_ref(activity.understanding_ref),
        questionnaire_ref=_parse_ref(activity.questionnaire_ref),
    )


def _load_owned_session(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> SessionModel:
    session = db.query(SessionModel).filter(
        SessionModel.session_id == session_id,
        SessionModel.user_id == principal.internal_user_pk,
        SessionModel.flow_version == "v3",
    ).one_or_none()
    if session is None:
        raise OwnedResourceNotFound
    return session


def _load_activity(
    db: Session,
    session_id: str,
) -> V3SessionActivity | None:
    return db.query(V3SessionActivity).filter(
        V3SessionActivity.session_id == session_id
    ).one_or_none()


def _require_owner_flow(activity: V3SessionActivity | None) -> V3SessionActivity:
    if (
        activity is None
        or activity.flow_contract_version != SUPPORTED_FLOW_CONTRACT_VERSION
    ):
        raise FlowContractUnsupported
    return activity


def get_session_activity(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> SessionActivityState:
    _load_owned_session(db, principal, session_id)
    return _activity_to_state(_load_activity(db, session_id), session_id)


def _transition_result(
    db: Session,
    session_id: str,
    action: str,
) -> InputTransitionResult:
    state = _activity_to_state(_load_activity(db, session_id), session_id)
    return InputTransitionResult(
        action=action,
        input_revision=state.input_revision,
        state=state,
    )


def apply_input_transition(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    request: InputTransitionRequest,
    *,
    idempotency_key: str,
) -> tuple[InputTransitionResult, bool]:
    _load_owned_session(db, principal, session_id)
    activity = _require_owner_flow(_load_activity(db, session_id))

    payload = {
        "session_id": session_id,
        "action": request.action,
        "expected_input_revision": request.expected_input_revision,
        "input_mode": request.input_mode,
        "document_id": request.document_id,
    }
    request_hash = _request_hash(payload)
    operation = f"{_TRANSITION_OPERATION}:{request.action}"

    record = db.query(V3IdempotencyRecord).filter(
        V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
        V3IdempotencyRecord.operation == operation,
        V3IdempotencyRecord.idempotency_key == idempotency_key,
    ).one_or_none()
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded":
            if record.response_json:
                # Exact replay: same key + same request must return the
                # identical stored result even if later transitions moved
                # the session state forward.
                stored = InputTransitionResult.model_validate(
                    json.loads(record.response_json)
                )
                db.rollback()
                return stored, True
            # Fallback for legacy records without a stored payload.
            result = _transition_result(db, session_id, request.action)
            db.rollback()
            return result, True
        # A non-terminal record means the previous attempt never completed;
        # drop it and run the transition fresh.
        db.delete(record)
        db.flush()
        record = None

    if activity.input_revision != request.expected_input_revision:
        db.rollback()
        raise InputRevisionConflict

    if request.action == "select_mode":
        if activity.input_mode is not None:
            db.rollback()
            raise TransitionNotAllowed
        new_mode = request.input_mode
        new_document = activity.active_document_id
        new_understanding_ref = activity.understanding_ref
    elif request.action == "replace_document":
        document = db.query(Document).filter(
            Document.document_id == request.document_id,
            Document.user_id == principal.internal_user_pk,
            Document.session_id == session_id,
        ).one_or_none()
        if document is None:
            db.rollback()
            raise DocumentNotOwned
        new_mode = "with_document"
        new_document = request.document_id
        new_understanding_ref = None
    else:  # discard_document
        new_mode = "without_document"
        new_document = None
        new_understanding_ref = None

    # Atomic compare-and-set: only one request carrying the same
    # expected_input_revision can win the revision bump.
    updated = db.execute(
        sa_update(V3SessionActivity)
        .where(
            V3SessionActivity.session_id == session_id,
            V3SessionActivity.input_revision == request.expected_input_revision,
        )
        .values(
            input_revision=request.expected_input_revision + 1,
            input_mode=new_mode,
            active_document_id=new_document,
            understanding_ref=new_understanding_ref,
        )
    )
    if updated.rowcount != 1:
        db.rollback()
        raise InputRevisionConflict

    result = _transition_result(db, session_id, request.action)
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
    try:
        db.flush()
        record.resource_type = "session"
        record.resource_id = session_id
        record.status = "succeeded"
        record.response_code = 200
        record.response_json = json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result, False


def update_understanding_ref(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    *,
    understanding_id: str,
    revision: int,
    expected_input_revision: int,
    commit: bool = True,
) -> int:
    """Record the confirmed Understanding reference and bump input_revision.

    The compare-and-set uses the caller's original ``expected_input_revision``
    — never a freshly re-read value — so a confirmation that raced with
    discard/replace cannot resurrect a deactivated source: if the session
    moved on, the atomic UPDATE matches zero rows and
    :class:`InputRevisionConflict` is raised with the whole transaction
    rolled back (including any pending Understanding snapshot).
    Returns the new input_revision. When ``commit=False`` the caller owns
    the transaction.
    """
    _load_owned_session(db, principal, session_id)
    _require_owner_flow(_load_activity(db, session_id))
    ref_json = json.dumps(
        {"understanding_id": understanding_id, "revision": revision},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    updated = db.execute(
        sa_update(V3SessionActivity)
        .where(
            V3SessionActivity.session_id == session_id,
            V3SessionActivity.input_revision == expected_input_revision,
        )
        .values(
            input_revision=expected_input_revision + 1,
            understanding_ref=ref_json,
        )
    )
    if updated.rowcount != 1:
        db.rollback()
        raise InputRevisionConflict
    if commit:
        db.commit()
    return expected_input_revision + 1
