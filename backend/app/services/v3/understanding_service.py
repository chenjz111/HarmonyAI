"""V3 Understanding run, immutable snapshots, and v3.1 confirmation.

Owner Flow Amendment 001 §3.3 / §4.2: confirmations produce a new immutable
revision atomically; plain `confirm` never calls the LLM; full-text edits
require `reprocess_requested=true` and go through the understanding provider;
structured changes apply a strict field whitelist. Medical content (approved
claim dictionary / AI summary production) stays gated behind Issue #77.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from sqlalchemy.orm import Session

from backend.ai_engine.v3.understanding_provider import (
    ProviderFailureV3,
    UnderstandingProviderChain,
)
from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.activity import V3SessionActivity
from backend.app.models.v3.understanding import V3UnderstandingSnapshot
from backend.app.schemas.v3.activity import SUPPORTED_FLOW_CONTRACT_VERSION
from backend.app.schemas.v3.common import AuthPrincipal, SourceType
from backend.app.schemas.v3.understanding import (
    CaseSummary,
    EditableField,
    FactExtraction,
    NormalizedFact,
    SourceStatus,
    UnderstandingProviderRequest,
    UnderstandingRevisionResult,
    UnderstandingSource,
    UnderstandingV3Request,
    UnderstandingV31ConfirmationRequest,
    UnderstandingV31Response,
    VoiceTranscript,
)
from backend.app.services.v3.activity_service import (
    FlowContractUnsupported,
    OwnedResourceNotFound,
    update_understanding_ref,
)


class UnderstandingNotFound(RuntimeError):
    pass


class RevisionConflict(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class MedicalAssetUnavailable(RuntimeError):
    pass


class ChangeNotAllowed(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


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


def _fact_from_provider(
    understanding_id: str,
    source: UnderstandingSource,
    fact,
    *,
    extraction_method: str,
) -> NormalizedFact:
    return NormalizedFact(
        fact_id=f"fact_{uuid.uuid4().hex}",
        fact_code=fact.claim_code,
        display_name=fact.display_name,
        category=fact.category,
        value=fact.value,
        time_window=fact.time_window,
        negated=fact.negated,
        subject=fact.subject,
        source_refs=[
            {
                "source_id": source.source_id,
                "source_type": source.source_type.value,
            }
        ],
        confirmation_status="unconfirmed",
        extraction=FactExtraction(
            method=extraction_method,
            confidence=fact.extraction_confidence,
        ),
    )


def run_understanding_v3(
    db: Session,
    principal: AuthPrincipal,
    request: UnderstandingV3Request,
    provider_chain: UnderstandingProviderChain | None,
) -> UnderstandingV31Response:
    """Run the understanding provider and persist an immutable revision 1.

    Returns MEDICAL_ASSET_UNAVAILABLE via :class:`MedicalAssetUnavailable`
    when no approved claim dictionary / provider is available (Issue #77).
    """
    _load_owned_session(db, principal, request.session_id)
    activity = _require_owner_flow(_load_activity(db, request.session_id))
    del activity
    if provider_chain is None:
        raise MedicalAssetUnavailable

    understanding_id = _uid("und")
    normalized_facts: list[NormalizedFact] = []
    source_statuses: list[SourceStatus] = []
    provider_kind = "rule"
    try:
        for source in request.inputs:
            provider_request = UnderstandingProviderRequest(
                request_id=_uid("req"),
                schema_version="understanding_provider_v3.0",
                prompt_version="understanding_v3.1",
                source={
                    "source_id": source.source_id,
                    "source_type": source.source_type.value,
                    "subject_hint": "unknown",
                    "time_window": "past_7_days",
                    "text": source.text or "",
                },
                allowed_claim_dictionary_version="medical_v3.0",
                max_facts=30,
            )
            response = provider_chain.complete_json(provider_request)
            provider_kind = provider_chain.last_provider_kind or provider_kind
            method = "qwen" if provider_kind == "cloud" else "rule"
            for fact in response.facts:
                normalized_facts.append(
                    _fact_from_provider(
                        understanding_id,
                        source,
                        fact,
                        extraction_method=method,
                    )
                )
            source_statuses.append(
                SourceStatus(
                    source_id=source.source_id,
                    source_type=source.source_type,
                    status="ready",
                )
            )
    except ProviderFailureV3 as error:
        if error.error_code in {
            "MEDICAL_ASSET_UNAVAILABLE",
            "SOURCE_TOO_LONG",
        }:
            raise MedicalAssetUnavailable from None
        raise

    content = UnderstandingV31Response(
        schema_version="understanding_v3.1",
        understanding_id=understanding_id,
        revision=1,
        status="needs_confirmation",
        case_summary=None,
        voice_transcripts=[],
        normalized_facts=normalized_facts,
        source_statuses=source_statuses,
        safety_status=None,
        safety_signal_refs=[],
        degradation={"active": False, "reason_codes": []},
        flow_contract_version="v3-owner-flow-1",
        safety_policy="deferred_v3",
        safety_evaluation_status="not_run",
    ).model_dump(mode="json")

    db.add(
        V3UnderstandingSnapshot(
            understanding_id=understanding_id,
            revision=1,
            session_id=request.session_id,
            internal_user_pk=principal.internal_user_pk,
            status="needs_confirmation",
            snapshot_json=json.dumps(content, ensure_ascii=False),
            safety_policy="deferred_v3",
            safety_evaluation_status="not_run",
            safety_status=None,
        )
    )
    db.commit()
    return UnderstandingV31Response.model_validate(content)


def _latest_snapshot(
    db: Session,
    principal: AuthPrincipal,
    understanding_id: str,
) -> V3UnderstandingSnapshot:
    snapshot = (
        db.query(V3UnderstandingSnapshot)
        .filter(
            V3UnderstandingSnapshot.understanding_id == understanding_id,
            V3UnderstandingSnapshot.internal_user_pk == principal.internal_user_pk,
        )
        .order_by(V3UnderstandingSnapshot.revision.desc())
        .first()
    )
    if snapshot is None:
        raise UnderstandingNotFound
    return snapshot


def get_understanding_read_model(
    db: Session,
    principal: AuthPrincipal,
    understanding_id: str,
) -> UnderstandingV31Response:
    snapshot = _latest_snapshot(db, principal, understanding_id)
    content = json.loads(snapshot.snapshot_json)
    return UnderstandingV31Response.model_validate(content)


_STRUCTURED_FIELD_WHITELIST = {
    "normalized_fact": {"value", "negated", "subject", "time_window"},
    "case_summary": {"summary", "title"},
    "voice_transcript": {"text"},
    "source": set(),
}


def _apply_structured_changes(
    content: dict[str, object],
    changes,
) -> tuple[list[str], list[str]]:
    applied: list[str] = []
    affected: list[str] = []
    facts = content.get("normalized_facts")
    for change in changes:
        allowed = _STRUCTURED_FIELD_WHITELIST.get(change.target_type)
        if allowed is None or change.field not in allowed:
            raise ChangeNotAllowed
        applied.append(_uid("chg"))
        if change.target_type == "normalized_fact":
            for fact in facts or []:
                if fact["fact_id"] == change.target_id:
                    fact[change.field] = change.new_value
                    fact["confirmation_status"] = "confirmed"
                    fact["extraction"] = {
                        "method": "user_correction",
                        "confidence": fact.get("extraction", {}).get("confidence"),
                    }
                    affected.append(change.target_id)
                    break
            else:
                raise ChangeNotAllowed
        elif change.target_type == "case_summary":
            summary = content.get("case_summary")
            if not isinstance(summary, dict):
                raise ChangeNotAllowed
            summary[change.field] = change.new_value
            affected.append(change.target_id)
        elif change.target_type == "voice_transcript":
            for transcript in content.get("voice_transcripts") or []:
                if transcript["transcript_id"] == change.target_id:
                    transcript[change.field] = change.new_value
                    affected.append(change.target_id)
                    break
            else:
                raise ChangeNotAllowed
    return applied, affected


def _reprocess_edited_summary(
    *,
    session_id: str,
    source_id: str,
    edited_summary_text: str,
    provider_chain: UnderstandingProviderChain | None,
) -> tuple[list[NormalizedFact], str]:
    if provider_chain is None:
        raise MedicalAssetUnavailable
    provider_request = UnderstandingProviderRequest(
        request_id=_uid("req"),
        schema_version="understanding_provider_v3.0",
        prompt_version="understanding_v3.1",
        source={
            "source_id": source_id,
            "source_type": SourceType.user_correction.value,
            "subject_hint": "unknown",
            "time_window": "past_7_days",
            "text": edited_summary_text,
        },
        allowed_claim_dictionary_version="medical_v3.0",
        max_facts=30,
    )
    try:
        response = provider_chain.complete_json(provider_request)
    except ProviderFailureV3 as error:
        if error.error_code in {
            "MEDICAL_ASSET_UNAVAILABLE",
            "SOURCE_TOO_LONG",
        }:
            raise MedicalAssetUnavailable from None
        raise
    method = (
        "qwen"
        if (provider_chain.last_provider_kind or "rule") == "cloud"
        else "rule"
    )
    facts: list[NormalizedFact] = []
    for fact in response.facts:
        facts.append(
            NormalizedFact(
                fact_id=f"fact_{uuid.uuid4().hex}",
                fact_code=fact.claim_code,
                display_name=fact.display_name,
                category=fact.category,
                value=fact.value,
                time_window=fact.time_window,
                negated=fact.negated,
                subject=fact.subject,
                source_refs=[
                    {
                        "source_id": source_id,
                        "source_type": SourceType.user_correction.value,
                    }
                ],
                confirmation_status="confirmed",
                extraction=FactExtraction(
                    method=method,
                    confidence=fact.extraction_confidence,
                ),
            )
        )
    return facts, method


def confirm_understanding_v3_1(
    db: Session,
    principal: AuthPrincipal,
    understanding_id: str,
    request: UnderstandingV31ConfirmationRequest,
    provider_chain: UnderstandingProviderChain | None,
) -> UnderstandingRevisionResult:
    snapshot = _latest_snapshot(db, principal, understanding_id)
    content = json.loads(snapshot.snapshot_json)
    if content["revision"] != request.expected_revision:
        raise RevisionConflict

    activity = _require_owner_flow(_load_activity(db, snapshot.session_id))
    if activity.input_revision != request.expected_input_revision:
        raise InputRevisionConflict

    previous_revision = int(content["revision"])
    new_revision = previous_revision + 1
    applied_changes: list[str] = []
    affected_fact_ids: list[str] = []
    summary_sources = content.get("source_statuses") or []
    source_ids = [item.get("source_id") for item in summary_sources]

    if request.decision == "confirm":
        content["status"] = "confirmed"
    else:
        if request.edited_summary_text is not None:
            source_id = source_ids[0] if source_ids else f"src_{uuid.uuid4().hex}"
            facts, _method = _reprocess_edited_summary(
                session_id=snapshot.session_id,
                source_id=source_id,
                edited_summary_text=request.edited_summary_text,
                provider_chain=provider_chain,
            )
            content["normalized_facts"] = [
                fact.model_dump(mode="json") for fact in facts
            ]
            content["case_summary"] = CaseSummary(
                case_summary_id=_uid("summary"),
                source_document_ids=source_ids or [source_id],
                revision=new_revision,
                status="confirmed",
                title="材料内容摘要",
                summary=request.edited_summary_text,
                editable_fields=[
                    EditableField(
                        field_id="summary",
                        label="资料摘要",
                        value=request.edited_summary_text,
                        value_type="text",
                        required=True,
                    )
                ],
                warnings=[],
            ).model_dump(mode="json")
            applied_changes = [_uid("chg")]
            affected_fact_ids = [
                item["fact_id"] for item in content["normalized_facts"]
            ]
        else:
            applied_changes, affected_fact_ids = _apply_structured_changes(
                content,
                request.changes,
            )
        content["status"] = "confirmed"

    content["revision"] = new_revision

    db.add(
        V3UnderstandingSnapshot(
            understanding_id=understanding_id,
            revision=new_revision,
            session_id=snapshot.session_id,
            internal_user_pk=principal.internal_user_pk,
            status="confirmed",
            snapshot_json=json.dumps(content, ensure_ascii=False),
            safety_policy="deferred_v3",
            safety_evaluation_status="not_run",
            safety_status=None,
        )
    )
    update_understanding_ref(
        db,
        principal,
        snapshot.session_id,
        understanding_id=understanding_id,
        revision=new_revision,
        commit=False,
    )
    db.commit()
    return UnderstandingRevisionResult(
        understanding_id=understanding_id,
        previous_revision=previous_revision,
        revision=new_revision,
        status="confirmed",
        applied_changes=applied_changes,
        affected_fact_ids=affected_fact_ids,
    )
