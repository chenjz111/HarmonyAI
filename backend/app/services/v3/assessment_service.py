"""Agent 1 — Assessment V3 (deterministic aggregation over approved assets).

Consumes the latest confirmed Understanding revision's NormalizedFacts and
maps them through the Issue #89 approved claim dictionary and organ mapping:
  NormalizedFacts -> FactEvidence -> OrganEvidenceLink -> organ_profile.

Fully deterministic — no LLM, no hard-coded medical rules: every organ link
and weight comes from the approved organ-mapping asset (single_mappings +
combination_rules). With insufficient evidence the assessment honestly
reports an insufficient organ profile (no fabricated organs) and the
frontend/Agent2 consume it as a degradation, never as fake confidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy import null
from sqlalchemy.orm import Session

from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import (
    AssessmentRevisionV3,
    AssessmentV3,
    FactEvidence as FactEvidenceRow,
    OrganEvidence as OrganEvidenceRow,
)
from backend.app.models.v3.understanding import (
    NormalizedFact as NormalizedFactRow,
    UnderstandingRevision,
)
from backend.app.models.v3.session import V3IdempotencyRecord
from backend.app.schemas.v3.assessment import (
    AssessmentV31Presentation,
    AssessmentV31Request,
    AssessmentV31Response,
    FactEvidence,
    OrganEvidenceLink,
)
from backend.app.schemas.v3.common import (
    AuthPrincipal,
    Degradation,
    ElementCode,
    EvidenceDirection,
    OrganCode,
    OrganProfile,
)
from backend.app.schemas.v3.understanding import NormalizedFact as NormalizedFactSchema
from backend.app.services.v3.knowledge_assets import load_organ_mapping


class OwnedResourceNotFound(RuntimeError):
    pass


class AssessmentInputNotReady(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


_OPERATION = "create_v3_assessment"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def load_confirmed_facts(
    db: Session,
    *,
    understanding_id: str,
    revision: int,
) -> list[dict]:
    """Load the confirmed NormalizedFacts of an Understanding revision.

    Raises AssessmentInputNotReady when the revision is not confirmed or
    carries no confirmed facts (Agent 1 must never consume unconfirmed or
    fabricated evidence).
    """
    row = (
        db.query(UnderstandingRevision)
        .filter(
            UnderstandingRevision.understanding_id == understanding_id,
            UnderstandingRevision.revision == revision,
            UnderstandingRevision.status == "confirmed",
        )
        .one_or_none()
    )
    if row is None:
        raise AssessmentInputNotReady
    facts: list[dict] = []
    for item in (row.presentation_json or {}).get("normalized_facts") or []:
        parsed = NormalizedFactSchema.model_validate(item)
        if parsed.confirmation_status != "confirmed":
            continue
        facts.append(item)
    if not facts:
        raise AssessmentInputNotReady
    return facts


def _fact_evidence(assessment_id: str, fact: dict, *, index: int) -> FactEvidence:
    del index
    return FactEvidence(
        fact_evidence_id=f"fev_{uuid.uuid4().hex}",
        assessment_id=assessment_id,
        assessment_revision=1,
        fact_id=fact["fact_id"],
        claim_code=fact["fact_code"],
        display_name=fact["display_name"],
        category=fact["category"],
        value=fact["value"],
        time_window=fact["time_window"],
        direction=(
            EvidenceDirection.contradicting
            if fact.get("negated")
            else EvidenceDirection.supporting
        ),
        reliability=float(fact.get("extraction", {}).get("confidence") or 0.8),
        source_refs=fact.get("source_refs") or [],
        confirmation_status=fact["confirmation_status"],
    )


def _organ_links(
    evidence: list[FactEvidence],
    mapping: dict,
) -> list[OrganEvidenceLink]:
    single_by_claim = {
        item["claim_code"]: item for item in mapping.get("single_mappings", [])
    }
    links: list[OrganEvidenceLink] = []
    for ev in evidence:
        rule = single_by_claim.get(ev.claim_code)
        if rule is None:
            continue
        links.append(
            OrganEvidenceLink(
                organ_evidence_link_id=f"oel_{uuid.uuid4().hex}",
                fact_evidence_id=ev.fact_evidence_id,
                organ=OrganCode(rule["organ"]),
                element=ElementCode(rule["element"]),
                direction=EvidenceDirection(rule["direction"]),
                link_strength=float(rule["link_strength"]),
                mapping_rule_id=rule["mapping_rule_id"],
                mapping_version=mapping.get("mapping_version", "organ_mapping_v3.0"),
                explanation_summary=rule.get("note") or "",
            )
        )
    return links


def _organ_weights(
    evidence: list[FactEvidence],
    links: list[OrganEvidenceLink],
    mapping: dict,
) -> dict[OrganCode, float] | None:
    """Compute available organ weights from the approved combination rules."""
    link_by_evidence = {link.fact_evidence_id: link for link in links}
    reliability_by_evidence = {ev.fact_evidence_id: ev.reliability for ev in evidence}
    support: dict[OrganCode, float] = {organ: 0.0 for organ in OrganCode}
    for rule in mapping.get("combination_rules", []):
        organ = OrganCode(rule["organ"])
        claims = set(rule.get("claims") or [])
        present = [
            ev
            for ev in evidence
            if ev.claim_code in claims and ev.fact_evidence_id in link_by_evidence
        ]
        if len(present) < int(rule.get("min_count", 2)):
            continue
        signed = 0.0
        for ev in present:
            link = link_by_evidence[ev.fact_evidence_id]
            direction_signed = 1.0 if link.direction == "supporting" else -1.0
            signed += (
                float(link.link_strength)
                * reliability_by_evidence[ev.fact_evidence_id]
                * direction_signed
            )
        if signed > 0:
            support[organ] = signed
    available = {organ: value for organ, value in support.items() if value > 0}
    if not available:
        return None
    total = sum(available.values())
    weights: dict[OrganCode, float] = {organ: 0.0 for organ in OrganCode}
    for organ, value in available.items():
        weights[organ] = round(value / total, 4)
    return weights


def create_assessment(
    db: Session,
    principal: AuthPrincipal,
    request: AssessmentV31Request,
    *,
    idempotency_key: str,
) -> tuple[AssessmentV31Response, bool]:
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
        if record.status == "succeeded" and record.resource_id and record.response_json:
            return AssessmentV31Response.model_validate_json(record.response_json), True

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
    if session_row.input_revision != request.expected_input_revision:
        raise InputRevisionConflict

    if request.understanding_ref is None:
        # Owner flow: without document the complete questionnaire is
        # mandatory; questionnaire fact adaptation is a separate step, so
        # until then a pure-questionnaire assessment stays not-ready.
        raise AssessmentInputNotReady

    facts = load_confirmed_facts(
        db,
        understanding_id=request.understanding_ref.understanding_id,
        revision=request.understanding_ref.revision,
    )
    assessment_id = f"asmt_{uuid.uuid4().hex}"
    evidence = [_fact_evidence(assessment_id, fact, index=index) for index, fact in enumerate(facts)]
    mapping = load_organ_mapping()
    links = _organ_links(evidence, mapping)
    weights = _organ_weights(evidence, links, mapping)

    if weights is None:
        organ_profile = OrganProfile(
            status="insufficient",
            weights=None,
            score_semantics="relative_evidence_distribution",
        )
    else:
        organ_profile = OrganProfile(
            status="available",
            weights=weights,
            score_semantics="relative_evidence_distribution",
        )

    degraded = weights is None
    state_summary = (
        "已综合近期资料与描述完成状态评估。"
        if not degraded
        else "现有证据不足，暂不能形成五脏状态判断。"
    )
    response = AssessmentV31Response(
        schema_version="assessment_v3.1",
        agent_id="assessment_agent",
        assessment_id=assessment_id,
        revision=1,
        status="needs_confirmation",
        understanding_ref=request.understanding_ref,
        state_summary=state_summary,
        recent_context_summary="",
        organ_profile=organ_profile,
        fact_evidence=evidence,
        organ_evidence_links=links,
        conflicts=[],
        missing_information=[],
        evidence_coverage=round(min(1.0, len(evidence) / 8.0), 3),
        evidence_coverage_semantics="confirmed_available_source_coverage",
        source_diversity=len(evidence),
        requires_user_confirmation=True,
        safety_status=None,
        degradation=Degradation(
            active=degraded,
            reason_codes=["INSUFFICIENT_EVIDENCE"] if degraded else [],
        ),
        flow_contract_version="v3-owner-flow-1",
        input_revision=request.expected_input_revision,
        safety_policy="deferred_v3",
        safety_evaluation_status="not_run",
        presentation=AssessmentV31Presentation(
            title="近期状态评估",
            summary=state_summary,
            body_summaries=[],
            recent_context="",
        ),
    )

    run = AssessmentV3(
        assessment_id=assessment_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=session_row.id,
        understanding_id=request.understanding_ref.understanding_id,
        understanding_revision=request.understanding_ref.revision,
        questionnaire_submission_id=(
            request.questionnaire_ref.questionnaire_submission_id
            if request.questionnaire_ref is not None
            else None
        ),
        current_revision=1,
        status="needs_confirmation",
        safety_status=None,
        user_goal_json=null(),
        flow_contract_version="v3-owner-flow-1",
        input_revision=request.expected_input_revision,
        input_mode=session_row.input_mode,
        safety_policy="deferred_v3",
        safety_evaluation_status="not_run",
    )
    db.add(run)
    db.flush()
    db.add(
        AssessmentRevisionV3(
            assessment_id=assessment_id,
            revision=1,
            previous_revision=None,
            understanding_revision=request.understanding_ref.revision,
            input_revision=request.expected_input_revision,
            status="needs_confirmation",
            confirmation_status="unconfirmed",
            state_summary=state_summary,
            recent_context_summary="",
            organ_profile_json=organ_profile.model_dump(mode="json"),
            evidence_coverage=response.evidence_coverage,
            source_diversity=response.source_diversity,
            conflicts_json=[],
            missing_information_json=[],
            degradation_json=response.degradation.model_dump(mode="json"),
            presentation_json=response.presentation.model_dump(mode="json"),
        )
    )
    evidence_rows: list[FactEvidenceRow] = []
    for ev in evidence:
        fact_row_id = (
            db.query(NormalizedFactRow.fact_row_id)
            .filter(
                NormalizedFactRow.fact_id == ev.fact_id,
                NormalizedFactRow.understanding_id
                == request.understanding_ref.understanding_id,
            )
            .scalar()
        )
        row = FactEvidenceRow(
            fact_evidence_row_id=f"fer_{uuid.uuid4().hex}",
            fact_evidence_id=ev.fact_evidence_id,
            assessment_id=assessment_id,
            assessment_revision=1,
            normalized_fact_row_id=fact_row_id,
            claim_code=ev.claim_code,
            display_name=ev.display_name,
            category=ev.category,
            value_json=ev.value.model_dump(mode="json"),
            time_window=ev.time_window,
            direction=ev.direction.value,
            reliability=ev.reliability,
            confirmation_status=ev.confirmation_status,
        )
        db.add(row)
        evidence_rows.append(row)
    db.flush()
    row_by_evidence_id = {row.fact_evidence_id: row for row in evidence_rows}
    for link in links:
        db.add(
            OrganEvidenceRow(
                organ_evidence_link_id=link.organ_evidence_link_id,
                fact_evidence_row_id=row_by_evidence_id[link.fact_evidence_id].fact_evidence_row_id,
                organ=link.organ.value,
                element=link.element.value,
                direction=link.direction.value,
                link_strength=link.link_strength,
                mapping_rule_id=link.mapping_rule_id,
                mapping_version=link.mapping_version,
                explanation_summary=link.explanation_summary,
            )
        )
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
    record.resource_type = "assessment"
    record.resource_id = assessment_id
    record.status = "succeeded"
    record.response_code = 201
    record.response_json = response.model_dump_json()
    db.commit()
    return response, False
