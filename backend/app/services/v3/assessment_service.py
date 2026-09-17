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
    FactSourceRef,
    NormalizedFact,
    NormalizedFact as NormalizedFactRow,
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
)
from backend.app.schemas.v3.assessment import (
    AssessmentConfirmationRequest,
    AssessmentV31Presentation,
    AssessmentV31Request,
    AssessmentV31Response,
    FactEvidence,
    OrganEvidenceLink,
)
from datetime import datetime, timezone
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
from backend.app.services.v3.organ_dominance_service import (
    build_organ_aggregation_snapshot,
    conflict_rules_of,
    is_questionnaire_evidence,
    select_effective_evidence,
    shares_source,
)
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


class AssessmentRevisionConflict(RuntimeError):
    pass


_OPERATION = "create_v3_assessment"


def load_revision_evidence(
    db: Session,
    *,
    assessment_id: str,
    revision: int,
    confirmed_only: bool = True,
) -> tuple[list[FactEvidence], list[OrganEvidenceLink]]:
    """One revision's evidence + organ links (single read-only implementation).

    Sprint 6 Phase 1B: the diagnosis/dominance boundary consumes exactly this
    population so the canonical aggregation snapshot is scored from the same
    rows Agent 1 persisted.
    """

    query = db.query(FactEvidenceRow).filter(
        FactEvidenceRow.assessment_id == assessment_id,
        FactEvidenceRow.assessment_revision == revision,
    )
    if confirmed_only:
        query = query.filter(FactEvidenceRow.confirmation_status == "confirmed")
    evidence_rows = query.order_by(FactEvidenceRow.fact_evidence_id).all()
    evidence: list[FactEvidence] = []
    row_by_pk: dict[str, str] = {}
    for row in evidence_rows:
        fact = db.get(NormalizedFact, row.normalized_fact_row_id)
        source_rows = (
            db.query(FactSourceRef)
            .filter(FactSourceRef.fact_row_id == row.normalized_fact_row_id)
            .order_by(FactSourceRef.source_type, FactSourceRef.source_id)
            .all()
        )
        evidence.append(
            FactEvidence(
                fact_evidence_id=row.fact_evidence_id,
                assessment_id=row.assessment_id,
                assessment_revision=row.assessment_revision,
                fact_id=fact.fact_id,
                claim_code=row.claim_code,
                display_name=row.display_name,
                category=row.category,
                value=row.value_json,
                time_window=row.time_window,
                direction=row.direction,
                reliability=row.reliability,
                source_refs=[
                    {
                        "source_type": src.source_type,
                        "source_id": src.source_id,
                        "span_ref": src.span_ref,
                    }
                    for src in source_rows
                ],
                confirmation_status=row.confirmation_status,
            )
        )
        row_by_pk[row.fact_evidence_row_id] = row.fact_evidence_id
    link_rows = (
        db.query(OrganEvidenceRow)
        .filter(OrganEvidenceRow.fact_evidence_row_id.in_(list(row_by_pk)))
        .order_by(OrganEvidenceRow.organ_evidence_link_id)
        .all()
        if row_by_pk
        else []
    )
    links = [
        OrganEvidenceLink(
            organ_evidence_link_id=row.organ_evidence_link_id,
            fact_evidence_id=row_by_pk[row.fact_evidence_row_id],
            organ=row.organ,
            element=row.element,
            direction=row.direction,
            link_strength=row.link_strength,
            mapping_rule_id=row.mapping_rule_id,
            mapping_version=row.mapping_version,
            explanation_summary=row.explanation_summary,
        )
        for row in link_rows
    ]
    return evidence, links


def _assessment_read_model(db: Session, run: AssessmentV3) -> AssessmentV31Response:
    revision = db.query(AssessmentRevisionV3).filter(
        AssessmentRevisionV3.assessment_id == run.assessment_id,
        AssessmentRevisionV3.revision == run.current_revision,
    ).one()
    evidence, links = load_revision_evidence(
        db,
        assessment_id=run.assessment_id,
        revision=run.current_revision,
        confirmed_only=False,
    )
    return AssessmentV31Response(
        schema_version="assessment_v3.1", agent_id="assessment_agent",
        assessment_id=run.assessment_id, revision=revision.revision,
        status=revision.status, understanding_ref=(
            {"understanding_id": run.understanding_id, "revision": run.understanding_revision}
            if run.understanding_id is not None else None
        ),
        state_summary=revision.state_summary,
        recent_context_summary=revision.recent_context_summary or "",
        organ_profile=revision.organ_profile_json,
        fact_evidence=evidence, organ_evidence_links=links,
        conflicts=revision.conflicts_json or [],
        missing_information=revision.missing_information_json or [],
        evidence_coverage=revision.evidence_coverage,
        evidence_coverage_semantics="confirmed_available_source_coverage",
        source_diversity=revision.source_diversity,
        requires_user_confirmation=revision.confirmation_status != "confirmed",
        safety_status=None, degradation=revision.degradation_json,
        flow_contract_version="v3-owner-flow-1",
        input_revision=run.input_revision,
        safety_policy="deferred_v3", safety_evaluation_status="not_run",
        presentation=revision.presentation_json,
    )


def get_assessment(db: Session, principal: AuthPrincipal, assessment_id: str) -> AssessmentV31Response:
    run = db.query(AssessmentV3).filter(
        AssessmentV3.assessment_id == assessment_id,
        AssessmentV3.internal_user_pk == principal.internal_user_pk,
        AssessmentV3.flow_contract_version == "v3-owner-flow-1",
    ).one_or_none()
    if run is None:
        raise OwnedResourceNotFound
    return _assessment_read_model(db, run)


def confirm_assessment(db: Session, principal: AuthPrincipal, assessment_id: str, request: AssessmentConfirmationRequest) -> tuple[AssessmentV31Response, bool]:
    run = db.query(AssessmentV3).filter(
        AssessmentV3.assessment_id == assessment_id,
        AssessmentV3.internal_user_pk == principal.internal_user_pk,
        AssessmentV3.flow_contract_version == "v3-owner-flow-1",
    ).one_or_none()
    if run is None:
        raise OwnedResourceNotFound
    session_row = db.get(SessionModel, run.session_row_id)
    if (
        session_row is None
        or session_row.user_id != principal.internal_user_pk
        or run.current_revision != request.expected_revision
        or run.input_revision != request.expected_input_revision
        or session_row.input_revision != request.expected_input_revision
    ):
        raise AssessmentRevisionConflict
    current = db.query(AssessmentRevisionV3).filter(
        AssessmentRevisionV3.assessment_id == assessment_id,
        AssessmentRevisionV3.revision == run.current_revision,
    ).one()
    if request.decision == "confirm":
        current.status = "confirmed"
        current.confirmation_status = "confirmed"
        current.confirmed_at = datetime.now(timezone.utc)
        run.status = "confirmed"
        db.query(FactEvidenceRow).filter(
            FactEvidenceRow.assessment_id == assessment_id,
            FactEvidenceRow.assessment_revision == run.current_revision,
        ).update({"confirmation_status": "confirmed"}, synchronize_session=False)
        db.commit()
        return _assessment_read_model(db, run), False

    next_revision = run.current_revision + 1
    presentation = dict(current.presentation_json or {})
    summary = request.edited_summary_text or current.state_summary
    organ_profile_json = current.organ_profile_json
    evidence_coverage = current.evidence_coverage
    source_diversity = current.source_diversity
    conflicts_json = current.conflicts_json
    degradation_json = current.degradation_json
    if request.edited_summary_text is not None:
        presentation["summary"] = request.edited_summary_text
        current_model = _assessment_read_model(db, run)
        active_evidence = [
            item
            for item in current_model.fact_evidence
            if item.display_name and item.display_name in summary
        ]
        active_ids = {item.fact_evidence_id for item in active_evidence}
        active_links = [
            item
            for item in current_model.organ_evidence_links
            if item.fact_evidence_id in active_ids
        ]
        mapping = load_organ_mapping()
        weights = _organ_weights(active_evidence, active_links, mapping)
        organ_profile_json = OrganProfile(
            status="available" if weights is not None else "insufficient",
            weights=weights,
            score_semantics="relative_evidence_distribution",
        ).model_dump(mode="json")
        evidence_coverage = round(min(1.0, len(active_evidence) / 8.0), 3)
        source_diversity = len(
            {
                (ref.source_type, ref.source_id)
                for item in active_evidence
                for ref in item.source_refs
            }
        )
        conflicts_json = [
            item.model_dump(mode="json")
            for item in _build_conflicts(active_evidence, mapping)
        ]
        degradation_json = Degradation(
            active=weights is None,
            reason_codes=["INSUFFICIENT_EVIDENCE"] if weights is None else [],
        ).model_dump(mode="json")
    new_revision = AssessmentRevisionV3(
        assessment_id=assessment_id, revision=next_revision,
        previous_revision=current.revision,
        understanding_revision=current.understanding_revision,
        input_revision=current.input_revision, status="confirmed",
        confirmation_status="confirmed", state_summary=summary,
        recent_context_summary=current.recent_context_summary,
        organ_profile_json=organ_profile_json,
        evidence_coverage=evidence_coverage,
        source_diversity=source_diversity,
        conflicts_json=conflicts_json,
        missing_information_json=current.missing_information_json,
        degradation_json=degradation_json,
        presentation_json=presentation,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(new_revision)
    db.flush()
    old_rows = db.query(FactEvidenceRow).filter(
        FactEvidenceRow.assessment_id == assessment_id,
        FactEvidenceRow.assessment_revision == current.revision,
    ).all()
    changes = {item.target_id: item for item in request.changes}
    evidence_by_id = {row.fact_evidence_id: row for row in old_rows}
    if set(changes) - set(evidence_by_id):
        raise AssessmentRevisionConflict
    for target_id, change in changes.items():
        value = evidence_by_id[target_id].value_json or {}
        if (
            change.field != "severity"
            or value.get("type") != "severity"
            or value.get("value") != change.old_value
            or change.new_value not in {"none", "mild", "moderate", "severe"}
        ):
            raise AssessmentRevisionConflict
    new_rows = {}
    for old in old_rows:
        if request.edited_summary_text is not None and (
            not old.display_name or old.display_name not in summary
        ):
            continue
        value = dict(old.value_json)
        change = changes.get(old.fact_evidence_id)
        if change is not None:
            value["value"] = change.new_value
        new = FactEvidenceRow(
            fact_evidence_row_id=f"fer_{uuid.uuid4().hex}",
            fact_evidence_id=old.fact_evidence_id,
            assessment_id=assessment_id, assessment_revision=next_revision,
            normalized_fact_row_id=old.normalized_fact_row_id,
            claim_code=old.claim_code, display_name=old.display_name,
            category=old.category, value_json=value,
            time_window=old.time_window, direction=old.direction,
            reliability=old.reliability, confirmation_status="confirmed",
        )
        db.add(new)
        new_rows[old.fact_evidence_row_id] = new
    db.flush()
    old_links = db.query(OrganEvidenceRow).filter(
        OrganEvidenceRow.fact_evidence_row_id.in_(list(new_rows))
    ).all() if new_rows else []
    for old in old_links:
        db.add(OrganEvidenceRow(
            organ_evidence_link_id=f"oel_{uuid.uuid4().hex}",
            fact_evidence_row_id=new_rows[old.fact_evidence_row_id].fact_evidence_row_id,
            organ=old.organ, element=old.element, direction=old.direction,
            link_strength=old.link_strength, mapping_rule_id=old.mapping_rule_id,
            mapping_version=old.mapping_version,
            explanation_summary=old.explanation_summary,
        ))
    run.current_revision = next_revision
    run.status = "confirmed"
    db.commit()
    return _assessment_read_model(db, run), True


def _approved_questionnaire_manifest() -> dict | None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "knowledge" / "v3" / "questionnaire-v3.0.1.json"
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
    if not facts and "chg_summary_edit" not in ((row.presentation_json or {}).get("applied_changes") or []):
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
    """Compatibility wrapper over the canonical shared-source check."""

    return shares_source(left, right)


def _is_questionnaire_evidence(item: FactEvidence) -> bool:
    """Compatibility wrapper over the canonical questionnaire-source check."""

    return is_questionnaire_evidence(item)


def _select_effective_evidence(
    evidence: list[FactEvidence],
    mapping: dict,
) -> list[FactEvidence]:
    """Compatibility wrapper over the canonical Phase 1B effective selection.

    The one-effective-evidence-per-claim rule (and the approved source-priority
    dedupe it implements) is owned by ``organ_dominance_service`` so Phase 1B
    dominance consumes exactly the population Agent 1 scores.
    """

    return select_effective_evidence(evidence, mapping)


def _conflict_rules(mapping: dict) -> set[str]:
    """Compatibility wrapper over the canonical conflict-rule reader."""

    return conflict_rules_of(mapping)


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
    """Compatibility wrapper over the canonical Phase 1B aggregation snapshot.

    The single scoring pass now lives in ``organ_dominance_service``: it emits
    raw support, effective evidence counts, legal candidates, contributing
    claims and normalized weights together, so Phase 1B dominance consumes
    exactly what Agent 1 scored. Returns ``None`` when no organ qualifies (the
    frozen "insufficient" outcome), otherwise the normalized five-organ weights.
    """

    snapshot = build_organ_aggregation_snapshot(evidence, links, mapping)
    if not snapshot.is_available:
        return None
    return {
        OrganCode(organ): value
        for organ, value in snapshot.normalized_weights_by_organ.items()
    }


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
    summary_parts = []
    if request.understanding_ref is not None:
        confirmed_revision = db.query(UnderstandingRevision).filter_by(
            understanding_id=request.understanding_ref.understanding_id,
            revision=request.understanding_ref.revision,
        ).one()
        text = (confirmed_revision.case_summary_json or {}).get("summary", "").strip()
        if text:
            summary_parts.append(text)
    if questionnaire_submission is not None:
        names = list(dict.fromkeys(item.display_name for item in evidence if _is_questionnaire_evidence(item)))
        summary_parts.append("近7天问卷记录：" + "、".join(names) + "。" if names else "近7天问卷未记录到可用的状态事实。")
    state_summary = "\n".join(summary_parts) or "当前没有可用的状态摘要，请补充或编辑。"
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
                    NormalizedFactRow.understanding_revision <= request.understanding_ref.revision,
                )
                .order_by(NormalizedFactRow.understanding_revision.desc())
                .limit(1)
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
