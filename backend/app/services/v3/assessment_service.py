"""Agent 1 — Assessment V3 (deterministic aggregation over approved assets).

Consumes the latest confirmed Understanding revision and the complete
questionnaire through the Issue #89 approved claim dictionary and organ
mapping:
  NormalizedFacts -> FactEvidence -> OrganEvidenceLink -> organ_profile.

Fully deterministic — no LLM, no hard-coded medical rules: every organ link
and weight comes from the approved organ-mapping asset (single_mappings,
multi_organ_rules, conflict_rules and combination_rules). With insufficient
evidence the assessment honestly reports an insufficient organ profile (no
fabricated organs) and the frontend/Agent2 consume it as a degradation, never
as fake confidence. V3.1 does not consume or persist UserGoal; Agent 3 owns
personalization.
"""

from __future__ import annotations

from hashlib import sha256
import json
import uuid

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
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
)
from backend.app.schemas.v3.assessment import (
    AssessmentV31Presentation,
    AssessmentV31Request,
    AssessmentV31Response,
    FactEvidence,
    OrganEvidenceLink,
)
from backend.app.schemas.v3.common import (
    AuthPrincipal,
    Conflict,
    Degradation,
    ElementCode,
    EvidenceDirection,
    OrganCode,
    OrganProfile,
)
from backend.app.schemas.v3.understanding import NormalizedFact as NormalizedFactSchema
from backend.app.services.v3.knowledge_assets import load_organ_mapping
from backend.app.services.v3.questionnaire_evidence import (
    QuestionnaireEvidenceInvalid,
    build_questionnaire_facts,
    ensure_questionnaire_fact_rows,
)
from backend.app.services.v3.activity_service import (
    AssessmentInputNotReady as ActivityAssessmentInputNotReady,
    validate_assessment_input_readiness,
)
from backend.app.services.v3.idempotency import (
    IdempotencyConflict,
    IdempotencyInProgress,
    reserve_v3_idempotency,
)


class OwnedResourceNotFound(RuntimeError):
    pass


class AssessmentInputNotReady(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


_OPERATION = "create_v3_assessment"


def _approved_questionnaire_manifest() -> dict | None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "knowledge" / "v3" / "questionnaire-v3.0.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
    source_refs = fact.get("source_refs") or []
    reliability = float(fact.get("extraction", {}).get("confidence") or 0.8)
    if any(ref.get("source_type") == "questionnaire" for ref in source_refs):
        value = fact.get("value") or {}
        if value.get("type") == "frequency_0_4":
            reliability = float(value["value"]) / 4.0
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
        reliability=reliability,
        source_refs=source_refs,
        confirmation_status=fact["confirmation_status"],
    )


def _load_questionnaire_submission(
    db: Session,
    session_row: SessionModel,
    questionnaire_ref,
) -> QuestionnaireSubmissionV3:
    submission = (
        db.query(QuestionnaireSubmissionV3)
        .filter(
            QuestionnaireSubmissionV3.questionnaire_submission_id
            == questionnaire_ref.questionnaire_submission_id,
            QuestionnaireSubmissionV3.internal_user_pk == session_row.user_id,
            QuestionnaireSubmissionV3.session_row_id == session_row.id,
        )
        .one_or_none()
    )
    manifest = _approved_questionnaire_manifest()
    if submission is None or manifest is None:
        raise AssessmentInputNotReady
    for field in ("schema_id", "schema_version", "manifest_version", "content_checksum"):
        if (
            getattr(submission, field) != getattr(questionnaire_ref, field)
            or getattr(submission, field) != manifest.get(field)
        ):
            raise AssessmentInputNotReady
    return submission


def _organ_links(
    evidence: list[FactEvidence],
    mapping: dict,
) -> list[OrganEvidenceLink]:
    single_by_claim = {
        item["claim_code"]: item for item in mapping.get("single_mappings", [])
    }
    multi_by_claim = {
        item["claim_code"]: item
        for item in mapping.get("multi_organ_rules", [])
        if item.get("links")
    }
    links: list[OrganEvidenceLink] = []
    for ev in evidence:
        multi_rule = multi_by_claim.get(ev.claim_code)
        rules = (
            multi_rule.get("links", [])
            if multi_rule is not None
            else ([single_by_claim[ev.claim_code]] if ev.claim_code in single_by_claim else [])
        )
        if not rules:
            continue
        for rule in rules:
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
                    explanation_summary=(
                        rule.get("note")
                        or (multi_rule or {}).get("rule")
                        or "approved multi-organ mapping"
                    ),
                )
            )
    return links


def _shares_source(left: FactEvidence, right: FactEvidence) -> bool:
    left_sources = {(ref.source_type, ref.source_id) for ref in left.source_refs}
    right_sources = {(ref.source_type, ref.source_id) for ref in right.source_refs}
    return bool(left_sources & right_sources)


def _is_questionnaire_evidence(item: FactEvidence) -> bool:
    return any(ref.source_type == "questionnaire" for ref in item.source_refs)


def _select_effective_evidence(
    evidence: list[FactEvidence],
    mapping: dict,
) -> list[FactEvidence]:
    """One effective FactEvidence per claim_code.

    conflict_rules.questionnaire_priority: the questionnaire's deterministic
    score wins and is never overridden by provider-extracted facts — without
    this selection a multi-organ claim present from both the questionnaire and
    a document would be scored twice (once per source). Within one priority
    class the highest-reliability item wins; ties are broken deterministically
    by fact_id.
    """
    if "questionnaire_priority" not in _conflict_rules(mapping):
        return evidence
    by_claim: dict[str, list[FactEvidence]] = {}
    for item in evidence:
        by_claim.setdefault(item.claim_code, []).append(item)
    return [
        max(
            items,
            key=lambda item: (
                _is_questionnaire_evidence(item),
                item.reliability,
                item.fact_id,
            ),
        )
        for items in by_claim.values()
    ]


def _conflict_rules(mapping: dict) -> set[str]:
    return {
        item["rule"]
        for item in mapping.get("conflict_rules", [])
        if item.get("rule")
    }


def _build_conflicts(
    evidence: list[FactEvidence],
    mapping: dict,
) -> list[Conflict]:
    """Materialize approved source-priority conflicts without exposing text."""
    if "questionnaire_priority" not in _conflict_rules(mapping):
        return []

    by_claim: dict[str, list[FactEvidence]] = {}
    for item in evidence:
        by_claim.setdefault(item.claim_code, []).append(item)

    conflicts: list[Conflict] = []
    for claim_code, items in by_claim.items():
        questionnaire_items = [
            item
            for item in items
            if _is_questionnaire_evidence(item)
        ]
        other_items = [
            item
            for item in items
            if not _is_questionnaire_evidence(item)
        ]
        conflicting = [
            item
            for item in questionnaire_items
            if any(
                item.value.model_dump(mode="json")
                != other.value.model_dump(mode="json")
                or item.direction != other.direction
                for other in other_items
            )
        ]
        if not conflicting:
            continue
        fact_ids = sorted(
            {
                item.fact_id
                for item in questionnaire_items + other_items
                if item in conflicting or item in other_items
            }
        )
        direction_conflict = any(
            item.direction != other.direction
            for item in conflicting
            for other in other_items
        )
        digest = sha256(
            f"{claim_code}:{','.join(fact_ids)}".encode("utf-8")
        ).hexdigest()[:32]
        conflicts.append(
            Conflict(
                conflict_id=f"conf_{digest}",
                fact_ids=fact_ids,
                severity="major" if direction_conflict else "minor",
                display_summary="问卷与其他来源的同一事实存在差异，已保留并标记冲突。",
                resolution_status="unresolved",
            )
        )
    return conflicts


def _organ_weights(
    evidence: list[FactEvidence],
    links: list[OrganEvidenceLink],
    mapping: dict,
) -> dict[OrganCode, float] | None:
    """Compute available organ weights from the approved combination rules."""
    evidence = _select_effective_evidence(evidence, mapping)
    effective_ids = {item.fact_evidence_id for item in evidence}
    links = [link for link in links if link.fact_evidence_id in effective_ids]
    links_by_evidence: dict[str, list[OrganEvidenceLink]] = {}
    for link in links:
        links_by_evidence.setdefault(link.fact_evidence_id, []).append(link)
    reliability_by_evidence = {ev.fact_evidence_id: ev.reliability for ev in evidence}
    support: dict[OrganCode, float] = {organ: 0.0 for organ in OrganCode}
    base_link_keys: set[tuple[str, OrganCode]] = set()
    conflict_rules = _conflict_rules(mapping)
    for rule in mapping.get("combination_rules", []):
        organ = OrganCode(rule["organ"])
        claims = set(rule.get("claims") or [])
        present_by_claim: dict[str, tuple[FactEvidence, OrganEvidenceLink]] = {}
        for ev in evidence:
            if ev.claim_code not in claims:
                continue
            if (
                "worry_control_vs_overthinking" in conflict_rules
                and ev.claim_code == "worry_control"
                and any(
                    other.claim_code == "overthinking_tendency"
                    and _shares_source(ev, other)
                    for other in evidence
                )
            ):
                continue
            organ_links = [
                link
                for link in links_by_evidence.get(ev.fact_evidence_id, [])
                if link.organ == organ
            ]
            if not organ_links:
                continue
            link = max(organ_links, key=lambda item: item.link_strength)
            current = present_by_claim.get(ev.claim_code)
            ev_priority = (_is_questionnaire_evidence(ev), ev.reliability)
            current_priority = (
                (_is_questionnaire_evidence(current[0]), current[0].reliability)
                if current is not None
                else None
            )
            if current is None or ev_priority > current_priority:
                present_by_claim[ev.claim_code] = (ev, link)
        if len(present_by_claim) < int(rule.get("min_count", 2)):
            continue
        signed = 0.0
        for ev, link in present_by_claim.values():
            base_link_keys.add((ev.fact_evidence_id, organ))
            direction_signed = 1.0 if link.direction == "supporting" else -1.0
            signed += (
                float(link.link_strength)
                * reliability_by_evidence[ev.fact_evidence_id]
                * direction_signed
            )
        minimum_total_support = float(
            (mapping.get("thresholds") or {}).get("minimum_total_support", 0.0)
        )
        if signed >= minimum_total_support:
            support[organ] = signed
    available = {organ: value for organ, value in support.items() if value > 0}
    if not available:
        return None

    multi_rule_ids = {
        link["mapping_rule_id"]
        for rule in mapping.get("multi_organ_rules", [])
        for link in rule.get("links", [])
    }
    sleep_claims = {"sleep_disturbance", "unrefreshing_sleep"}
    sleep_max: dict[tuple[str, OrganCode], float] = {}
    additional_multi: dict[OrganCode, float] = {organ: 0.0 for organ in available}
    for ev in evidence:
        for link in links_by_evidence.get(ev.fact_evidence_id, []):
            if (
                link.mapping_rule_id not in multi_rule_ids
                or link.organ not in available
                or (ev.fact_evidence_id, link.organ) in base_link_keys
            ):
                continue
            signed = (
                float(link.link_strength)
                * ev.reliability
                * (1.0 if link.direction == EvidenceDirection.supporting else -1.0)
            )
            if (
                "sleep_multi_organ_no_double_count" in conflict_rules
                and ev.claim_code in sleep_claims
            ):
                for source in ev.source_refs:
                    key = (source.source_id, link.organ)
                    sleep_max[key] = max(sleep_max.get(key, 0.0), signed)
            else:
                additional_multi[link.organ] += signed
    for (_source_id, organ), value in sleep_max.items():
        additional_multi[organ] += value
    available = {
        organ: value + additional_multi.get(organ, 0.0)
        for organ, value in available.items()
        if value + additional_multi.get(organ, 0.0) > 0
    }
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
    record, replayed = reserve_v3_idempotency(
        db,
        internal_user_pk=principal.internal_user_pk,
        operation=_OPERATION,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if replayed:
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

    if session_row.flow_contract_version == "v3-owner-flow-1":
        try:
            validate_assessment_input_readiness(db, session_row)
        except ActivityAssessmentInputNotReady as error:
            raise AssessmentInputNotReady from error

        active_understanding = (
            session_row.active_understanding_id,
            session_row.active_understanding_revision,
        )
        requested_understanding = (
            request.understanding_ref.understanding_id,
            request.understanding_ref.revision,
        ) if request.understanding_ref is not None else None
        if session_row.input_mode == "with_document":
            if requested_understanding != active_understanding:
                raise AssessmentInputNotReady
        elif session_row.input_mode == "without_document":
            if request.understanding_ref is not None:
                raise AssessmentInputNotReady
            if request.questionnaire_ref is None:
                raise AssessmentInputNotReady
            if (
                request.questionnaire_ref.questionnaire_submission_id
                != session_row.active_questionnaire_submission_id
            ):
                raise AssessmentInputNotReady
        if request.questionnaire_ref is not None:
            if (
                session_row.active_questionnaire_submission_id is not None
                and request.questionnaire_ref.questionnaire_submission_id
                != session_row.active_questionnaire_submission_id
            ):
                raise AssessmentInputNotReady
            _load_questionnaire_submission(db, session_row, request.questionnaire_ref)
    elif request.understanding_ref is None:
        raise AssessmentInputNotReady

    facts: list[dict] = []
    questionnaire_submission = None
    questionnaire_fact_row_ids: dict[str, str] = {}
    if request.understanding_ref is not None:
        facts.extend(
            load_confirmed_facts(
                db,
                understanding_id=request.understanding_ref.understanding_id,
                revision=request.understanding_ref.revision,
            )
        )
    if request.questionnaire_ref is not None:
        questionnaire_submission = _load_questionnaire_submission(
            db, session_row, request.questionnaire_ref
        )
        try:
            questionnaire_facts = build_questionnaire_facts(questionnaire_submission)
        except QuestionnaireEvidenceInvalid:
            raise AssessmentInputNotReady from None
        questionnaire_fact_row_ids = ensure_questionnaire_fact_rows(
            db, questionnaire_submission, questionnaire_facts
        )
        facts.extend(questionnaire_facts)
    if not facts and request.understanding_ref is None and questionnaire_submission is None:
        raise AssessmentInputNotReady
    assessment_id = f"asmt_{uuid.uuid4().hex}"
    evidence = [
        _fact_evidence(assessment_id, fact, index=index)
        for index, fact in enumerate(facts)
    ]
    mapping = load_organ_mapping()
    effective_evidence = _select_effective_evidence(evidence, mapping)
    links = _organ_links(effective_evidence, mapping)
    weights = _organ_weights(effective_evidence, links, mapping)
    conflicts = _build_conflicts(evidence, mapping)

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
        "已综合近期资料、描述与问卷完成状态评估。"
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
        conflicts=conflicts,
        missing_information=[],
        evidence_coverage=round(min(1.0, len(evidence) / 8.0), 3),
        evidence_coverage_semantics="confirmed_available_source_coverage",
        source_diversity=len(
            {
                (ref.source_type, ref.source_id)
                for ev in evidence
                for ref in ev.source_refs
            }
        ),
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
        understanding_id=(
            request.understanding_ref.understanding_id
            if request.understanding_ref is not None
            else None
        ),
        understanding_revision=(
            request.understanding_ref.revision
            if request.understanding_ref is not None
            else None
        ),
        questionnaire_submission_id=(
            questionnaire_submission.questionnaire_submission_id
            if questionnaire_submission is not None
            else None
        ),
        current_revision=1,
        status="needs_confirmation",
        safety_status=None,
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
            understanding_revision=(
                request.understanding_ref.revision
                if request.understanding_ref is not None
                else None
            ),
            input_revision=request.expected_input_revision,
            status="needs_confirmation",
            confirmation_status="unconfirmed",
            state_summary=state_summary,
            recent_context_summary="",
            organ_profile_json=organ_profile.model_dump(mode="json"),
            evidence_coverage=response.evidence_coverage,
            source_diversity=response.source_diversity,
            conflicts_json=[item.model_dump(mode="json") for item in conflicts],
            missing_information_json=[],
            degradation_json=response.degradation.model_dump(mode="json"),
            presentation_json=response.presentation.model_dump(mode="json"),
        )
    )
    evidence_rows: list[FactEvidenceRow] = []
    for ev in evidence:
        fact_row_id = questionnaire_fact_row_ids.get(ev.fact_id)
        if fact_row_id is None and request.understanding_ref is not None:
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
    record.resource_type = "assessment"
    record.resource_id = assessment_id
    record.status = "succeeded"
    record.response_code = 201
    record.response_json = response.model_dump_json()
    db.commit()
    return response, False
