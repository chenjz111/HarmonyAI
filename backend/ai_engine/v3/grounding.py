"""Sprint 6 Phase 4 — Evidence Kernel + Authority Firewall.

Phase 4 makes the following true without any extra provider/embedding call:

* confirmed user facts are authoritative because the user confirmed them;
* music decisions are authoritative because approved rules produced them;
* RAG references are authoritative because Phase 3 verified the retrieval;
* provider free text is **not** an authority and never becomes user-facing
  presentation.

This module owns the deterministic projection of already-authoritative inputs
(``EvidenceKernelV1``) plus the safe explanation atoms (``SafeExplanationAtomV1``)
that the diagnosis presentation is built from. Nothing here reads the provider's
``reasoning_summary``, ``display_name``, ``relative_support`` or candidate
ordering, and nothing here performs semantic entailment: Phase 4 does not claim
that a retrieved chunk proves a medical sentence.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

EVIDENCE_KERNEL_VERSION = "evidence_kernel_v1"
SAFE_EXPLANATION_ATOM_VERSION = "safe_explanation_atom_v1"
AUTHORITY_FIREWALL_VERSION = "authority_firewall_v1"

GROUNDING_STATUS_BUILT = "built"
GROUNDING_STATUS_LEGACY_UNVERIFIED = "legacy_unverified"

#: Key used to persist the kernel additively inside an existing JSON snapshot.
KERNEL_PRESENTATION_KEY = "evidence_kernel"

#: Minimal, medically non-diagnostic knowledge-context atom (F4-D10). It states
#: that approved knowledge was part of the current context; it never claims the
#: chunk proves the sentence.
KNOWLEDGE_CONTEXT_ATOM_TEXT = "本次结合已审核知识资料作为参考。"


class _KernelModel(BaseModel):
    """Frozen internal model: exact shape, no extra keys, JSON-ready."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceKernelFactV1(_KernelModel):
    """One current-revision user-confirmed fact."""

    fact_evidence_id: str
    claim_code: str
    value: Any = None
    direction: str
    time_window: str | None = None
    confirmation_status: str = "confirmed"


class EvidenceKernelRagHitV1(_KernelModel):
    """One current-run verified retrieval hit."""

    chunk_id: str
    source_id: str
    content_checksum: str | None = None


class EvidenceKernelRagV1(_KernelModel):
    """The exact current-run retrieval context (never the whole corpus)."""

    status: str
    retrieval_id: str | None = None
    knowledge_version: str
    embedding_version: str | None = None
    hit_ids: tuple[str, ...] = ()
    hits: tuple[EvidenceKernelRagHitV1, ...] = ()


class EvidenceKernelDecisionV1(_KernelModel):
    """The single authoritative Phase 1B decision for this run."""

    regulation_mode: str
    dominant_organ: str | None = None
    primary_tone: str | None = None
    secondary_tone: str | None = None
    decision_reason_code: str | None = None
    decision_checksum: str | None = None
    mapping_version: str | None = None
    read_model_schema_version: str | None = None
    read_model_checksum: str | None = None


class EvidenceKernelGenerationV1(_KernelModel):
    """Rule-derived generation parameters (never LLM-chosen)."""

    regulation_mode: str
    primary_tone: str | None = None
    secondary_tone: str | None = None
    bpm: int
    instruments: tuple[str, ...] = ()
    ambience: tuple[str, ...] = ()
    duration_seconds: int
    readiness: str
    spec_schema_version: str | None = None


class EvidenceKernelAuditV1(_KernelModel):
    """Identity/version audit of everything the kernel was built from."""

    kernel_version: str = EVIDENCE_KERNEL_VERSION
    authority_firewall_version: str = AUTHORITY_FIREWALL_VERSION
    knowledge_version: str
    manifest_checksum: str | None = None
    query_builder_version: str | None = None
    mapping_version: str | None = None
    medical_rule_version: str | None = None
    #: Explicit, machine-checkable statements about what Phase 4 does NOT do.
    provider_free_text_authoritative: bool = False
    semantic_entailment_verified: bool = False


class SafeExplanationAtomV1(_KernelModel):
    """A deterministic, structured-authority-derived explanation unit.

    ``fact_refs`` mean "this user-confirmed fact was part of the structured
    context"; ``rag_refs`` mean "this approved current-run knowledge item was
    part of the current knowledge context". Neither claims semantic entailment.
    """

    atom_type: str
    display_text: str
    fact_refs: tuple[str, ...] = ()
    rag_refs: tuple[str, ...] = ()
    rule_refs: tuple[str, ...] = ()


class EvidenceKernelV1(_KernelModel):
    """Immutable-by-construction authority snapshot for one diagnosis run."""

    kernel_version: str = EVIDENCE_KERNEL_VERSION
    assessment_id: str
    assessment_revision: int
    grounding_status: str = GROUNDING_STATUS_BUILT
    confirmed_facts: tuple[EvidenceKernelFactV1, ...] = ()
    rag: EvidenceKernelRagV1
    decision: EvidenceKernelDecisionV1
    generation: EvidenceKernelGenerationV1
    explanation_atoms: tuple[SafeExplanationAtomV1, ...] = ()
    audit: EvidenceKernelAuditV1
    content_checksum: str = ""

    def payload(self) -> dict[str, Any]:
        """Canonical JSON-ready payload (deterministic key order)."""

        return self.model_dump(mode="json")

    def to_storage_payload(self) -> dict[str, Any]:
        """Payload persisted additively inside the diagnosis JSON snapshot."""

        return self.payload()


def canonical_checksum(payload: Any) -> str:
    """Deterministic sha256 over a JSON payload with sorted keys."""

    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return getattr(value, "value", value)


def _fact_models(facts: Sequence[object]) -> tuple[EvidenceKernelFactV1, ...]:
    """Project current-revision facts deterministically (sorted by stable id)."""

    projected: list[EvidenceKernelFactV1] = []
    for fact in facts:
        dumped = _plain(fact)
        if not isinstance(dumped, Mapping):
            continue
        fact_id = dumped.get("fact_evidence_id")
        if not isinstance(fact_id, str) or not fact_id:
            continue
        direction = dumped.get("direction")
        projected.append(
            EvidenceKernelFactV1(
                fact_evidence_id=fact_id,
                claim_code=str(dumped.get("claim_code") or ""),
                value=dumped.get("value"),
                direction=str(_enum_value(direction) or ""),
                time_window=(
                    str(dumped["time_window"])
                    if dumped.get("time_window") is not None
                    else None
                ),
                confirmation_status=str(
                    dumped.get("confirmation_status") or "confirmed"
                ),
            )
        )
    projected.sort(key=lambda item: item.fact_evidence_id)
    return tuple(projected)


def _rag_section(
    rag_result: Any,
    chunk_checksums: Mapping[str, str] | None,
) -> EvidenceKernelRagV1:
    """Project the exact current-run hit set (never the approved corpus)."""

    checksums = {str(key): str(value) for key, value in (chunk_checksums or {}).items()}
    hits = list(getattr(rag_result, "hits", ()) or ())
    projected = [
        EvidenceKernelRagHitV1(
            chunk_id=str(hit.chunk_id),
            source_id=str(getattr(hit, "source_id", "")),
            content_checksum=checksums.get(str(hit.chunk_id)),
        )
        for hit in hits
    ]
    projected.sort(key=lambda item: item.chunk_id)
    return EvidenceKernelRagV1(
        status=str(getattr(rag_result, "status", "unknown")),
        retrieval_id=(
            str(rag_result.retrieval_id)
            if getattr(rag_result, "retrieval_id", None)
            else None
        ),
        knowledge_version=str(getattr(rag_result, "knowledge_version", "")),
        embedding_version=(
            str(rag_result.embedding_version)
            if getattr(rag_result, "embedding_version", None)
            else None
        ),
        hit_ids=tuple(item.chunk_id for item in projected),
        hits=tuple(projected),
    )


def build_safe_explanation_atoms(
    *,
    read_model: Any,
    decision: Any | None = None,
    fact_ids: Sequence[str] = (),
    rag_hit_ids: Sequence[str] = (),
    knowledge_version: str | None = None,
) -> tuple[SafeExplanationAtomV1, ...]:
    """Deterministic safe explanation atoms built from structured authority.

    Preferred sources (F4-D7): the existing read-model ``state_tendency``,
    ``analysis_rationales`` and ``generation.message`` texts, plus the approved
    tone/mode identity. Only one small new string is introduced
    (``KNOWLEDGE_CONTEXT_ATOM_TEXT``) and it makes no medical claim.
    """

    facts = tuple(sorted({str(item) for item in fact_ids if str(item)}))
    rag_refs = tuple(sorted({str(item) for item in rag_hit_ids if str(item)}))
    read_model_version = str(getattr(read_model, "schema_version", "") or "")
    rule_refs: list[str] = []
    if read_model_version:
        rule_refs.append(f"read_model:{read_model_version}")
    reason_code = getattr(decision, "decision_reason_code", None)
    if reason_code:
        rule_refs.append(f"decision:{getattr(reason_code, 'value', reason_code)}")
    if knowledge_version:
        rule_refs.append(f"knowledge_version:{knowledge_version}")
    rule_refs_tuple = tuple(rule_refs)

    atoms: list[SafeExplanationAtomV1] = []
    state_tendency = str(getattr(read_model, "state_tendency", "") or "").strip()
    if state_tendency:
        atoms.append(
            SafeExplanationAtomV1(
                atom_type="state_context",
                display_text=state_tendency,
                fact_refs=facts,
                rule_refs=rule_refs_tuple,
            )
        )

    rationales = list(getattr(read_model, "analysis_rationales", ()) or ())
    if rationales:
        summary = str(getattr(rationales[0], "summary", "") or "").strip()
        if summary:
            atoms.append(
                SafeExplanationAtomV1(
                    atom_type="analysis_rationale",
                    display_text=summary,
                    fact_refs=facts,
                    rule_refs=rule_refs_tuple,
                )
            )

    generation = getattr(read_model, "generation", None)
    generation_message = str(getattr(generation, "message", "") or "").strip()
    if generation_message:
        atoms.append(
            SafeExplanationAtomV1(
                atom_type="generation_readiness",
                display_text=generation_message,
                fact_refs=facts,
                rule_refs=rule_refs_tuple,
            )
        )

    if rag_refs:
        atoms.append(
            SafeExplanationAtomV1(
                atom_type="knowledge_context",
                display_text=KNOWLEDGE_CONTEXT_ATOM_TEXT,
                rag_refs=rag_refs,
                rule_refs=rule_refs_tuple,
            )
        )
    return tuple(atoms)


def authoritative_state_tendency(read_model: Any) -> str | None:
    """State/tendency interpretation from the deterministic read model.

    Phase 4 blocking fix: ``presentation.primary_tendency`` is a *state /
    tendency* field (the H5 client renders it inside 「状态解读」), so it must be
    the read model's authoritative ``state_tendency`` text — never the primary
    tone label, never a provider display name / reasoning summary / support, and
    never the page title.

    Returns ``None`` only when the read model carries no usable state text, in
    which case the existing safe nullable client behaviour applies.
    """

    text = str(getattr(read_model, "state_tendency", "") or "").strip()
    return text or None


def _decision_section(
    decision: Any | None,
    *,
    decision_checksum: str | None,
    mapping_version: str | None,
    read_model: Any,
) -> EvidenceKernelDecisionV1:
    read_model_payload = _plain(read_model)
    return EvidenceKernelDecisionV1(
        regulation_mode=str(_enum_value(getattr(decision, "regulation_mode", "")) or ""),
        dominant_organ=(
            str(_enum_value(getattr(decision, "dominant_organ", None)))
            if getattr(decision, "dominant_organ", None) is not None
            else None
        ),
        primary_tone=(
            str(_enum_value(getattr(decision, "primary_tone", None)))
            if getattr(decision, "primary_tone", None) is not None
            else None
        ),
        secondary_tone=(
            str(_enum_value(getattr(decision, "secondary_tone", None)))
            if getattr(decision, "secondary_tone", None) is not None
            else None
        ),
        decision_reason_code=(
            str(_enum_value(getattr(decision, "decision_reason_code", None)))
            if getattr(decision, "decision_reason_code", None) is not None
            else None
        ),
        decision_checksum=decision_checksum,
        mapping_version=mapping_version,
        read_model_schema_version=str(
            getattr(read_model, "schema_version", "") or ""
        )
        or None,
        read_model_checksum=canonical_checksum(read_model_payload),
    )


def _generation_section(generation_spec: Any) -> EvidenceKernelGenerationV1:
    spec = _plain(generation_spec)
    return EvidenceKernelGenerationV1(
        regulation_mode=str(_enum_value(spec.get("regulation_mode")) or ""),
        primary_tone=(
            str(_enum_value(spec.get("primary_tone")))
            if spec.get("primary_tone") is not None
            else None
        ),
        secondary_tone=(
            str(_enum_value(spec.get("secondary_tone")))
            if spec.get("secondary_tone") is not None
            else None
        ),
        bpm=int(spec.get("bpm", 0)),
        instruments=tuple(str(item) for item in (spec.get("instruments") or ())),
        ambience=tuple(str(item) for item in (spec.get("ambience") or ())),
        duration_seconds=int(spec.get("duration_seconds", 0)),
        readiness=str(spec.get("readiness", "")),
        spec_schema_version=(
            str(spec.get("schema_version")) if spec.get("schema_version") else None
        ),
    )


def build_evidence_kernel(
    *,
    assessment_id: str,
    assessment_revision: int,
    facts: Sequence[object],
    rag_result: Any,
    decision: Any | None,
    read_model: Any,
    generation_spec: Any,
    chunk_checksums: Mapping[str, str] | None = None,
    decision_checksum: str | None = None,
    mapping_version: str | None = None,
    manifest: Any | None = None,
    query_builder_version: str | None = None,
    medical_rule_version: str | None = None,
) -> EvidenceKernelV1:
    """Build the deterministic authority snapshot for one diagnosis run.

    The provider response is intentionally **not** an input: nothing the model
    wrote (text, ordering, relative support) can enter the kernel. Same
    authoritative inputs therefore always produce the same kernel.
    """

    fact_models = _fact_models(facts)
    rag = _rag_section(rag_result, chunk_checksums)
    knowledge_version = str(getattr(rag_result, "knowledge_version", "") or "")
    atoms = build_safe_explanation_atoms(
        read_model=read_model,
        decision=decision,
        fact_ids=[item.fact_evidence_id for item in fact_models],
        rag_hit_ids=rag.hit_ids,
        knowledge_version=knowledge_version,
    )
    kernel = EvidenceKernelV1(
        assessment_id=str(assessment_id),
        assessment_revision=int(assessment_revision),
        confirmed_facts=fact_models,
        rag=rag,
        decision=_decision_section(
            decision,
            decision_checksum=decision_checksum,
            mapping_version=mapping_version,
            read_model=read_model,
        ),
        generation=_generation_section(generation_spec),
        explanation_atoms=atoms,
        audit=EvidenceKernelAuditV1(
            knowledge_version=knowledge_version,
            manifest_checksum=(
                str(getattr(manifest, "manifest_checksum", "") or "") or None
            ),
            query_builder_version=query_builder_version,
            mapping_version=mapping_version,
            medical_rule_version=medical_rule_version,
        ),
    )
    payload = kernel.model_dump(mode="json")
    payload.pop("content_checksum", None)
    return kernel.model_copy(update={"content_checksum": canonical_checksum(payload)})


def presentation_with_kernel(
    presentation_payload: Mapping[str, Any],
    kernel: EvidenceKernelV1 | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Attach the kernel additively to an existing JSON snapshot (no migration)."""

    payload = dict(presentation_payload)
    if kernel is None:
        return payload
    stored = kernel.payload() if hasattr(kernel, "payload") else dict(kernel)
    if not stored:
        return payload
    payload[KERNEL_PRESENTATION_KEY] = stored
    return payload


def grounding_status_of(presentation_payload: Mapping[str, Any] | None) -> str:
    """Internal grounding state of a persisted row (never a public status)."""

    payload = presentation_payload or {}
    kernel = payload.get(KERNEL_PRESENTATION_KEY)
    if isinstance(kernel, Mapping) and kernel.get("kernel_version"):
        return GROUNDING_STATUS_BUILT
    return GROUNDING_STATUS_LEGACY_UNVERIFIED
