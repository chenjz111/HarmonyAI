"""Provider-backed fact extraction for Understanding (AI layer).

Wires the Issue #89 approved claim dictionary and the Understanding Provider
Chain into the #88 understanding ingestion: OCR/Narrative text becomes
NormalizedFacts. When the provider is unavailable or returns no facts the
extraction yields an empty list — never fabricated facts, never fake
success. Raw OCR/narrative text is only passed to the provider; it is never
logged or persisted in plaintext.
"""

from __future__ import annotations

import os
import re
import uuid

from sqlalchemy.orm import Session

from backend.ai_engine.v3.understanding_provider import (
    ProviderFailureV3,
    UnderstandingProviderChain,
    UnderstandingProviderRequest,
    build_understanding_provider_bundle,
)
from backend.app.models.v3.understanding import (
    FactSourceRef,
    NormalizedFact as NormalizedFactRow,
    UnderstandingSource,
)
from backend.app.schemas.v3.common import SourceType
from backend.app.schemas.v3.understanding import (
    FactExtraction,
    NormalizedFact,
    SourceRef,
)
from backend.app.services.v3.knowledge_assets import load_claim_dictionary


def build_provider_chain() -> UnderstandingProviderChain | None:
    """Build the Cloud/Local understanding chain from approved assets.

    Returns ``None`` when the approved claim dictionary cannot be loaded or
    no provider is configured — callers must then skip extraction instead of
    fabricating facts.
    """
    try:
        version, dictionary = load_claim_dictionary()
        bundle = build_understanding_provider_bundle(
            claim_dictionary_version=version,
            claim_dictionary=dictionary,
            environment=os.environ,
        )
        return bundle.chain
    except Exception:
        return None


def _claim_dictionary_version(chain: UnderstandingProviderChain) -> str:
    """Return the approved claim dictionary version the chain enforces.

    ``QwenUnderstandingProvider`` rejects any request whose
    ``allowed_claim_dictionary_version`` differs from the dictionary version it
    was built with, and it does so before any network call. The request must
    therefore mirror the chain instead of a hardcoded literal: the approved
    asset declares ``schema_version=3.0.0`` while ``manifest_version`` is
    ``medical_v3.0``, and the literal pinned every extraction to a version the
    provider never had — silently disabling AI extraction.
    """

    for provider in getattr(chain, "providers", ()):
        version = getattr(provider, "claim_dictionary_version", None)
        if isinstance(version, str) and version.strip():
            return version.strip()
    return load_claim_dictionary()[0]


def _run_provider(
    chain: UnderstandingProviderChain,
    *,
    source_id: str,
    source_type: str,
    text: str,
) -> list:
    request = UnderstandingProviderRequest(
        request_id=f"req_{uuid.uuid4().hex}",
        schema_version="understanding_provider_v3.0",
        prompt_version="understanding_v3.1",
        source={
            "source_id": source_id,
            "source_type": source_type,
            "subject_hint": "unknown",
            "time_window": "past_7_days",
            "text": text,
        },
        allowed_claim_dictionary_version=_claim_dictionary_version(chain),
        max_facts=30,
    )
    response = chain.complete_json(request)
    return response.facts


def _fact_dicts(
    understanding_id: str,
    *,
    source_id: str,
    source_type: str,
    provider_facts: list,
    method: str,
) -> list[dict]:
    result: list[dict] = []
    for fact in provider_facts:
        result.append(
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
                    SourceRef(
                        source_id=source_id,
                        source_type=source_type,
                    )
                ],
                confirmation_status="unconfirmed",
                extraction=FactExtraction(
                    method=method,
                    confidence=fact.extraction_confidence,
                ),
            ).model_dump(mode="json")
        )
    del understanding_id
    return result


def extract_facts_for_sources(
    chain: UnderstandingProviderChain | None,
    resolved,
) -> tuple[list[dict], list[str]]:
    """Extract NormalizedFacts from ready document/narrative sources.

    Returns (fact dicts, failure_reason_codes). OCR/narrative text is the
    server-resolved authoritative text; client-supplied text is never used.
    Provider failure or an empty result yields no facts (no fake success).
    """
    if chain is None or not getattr(chain, "providers", None):
        return [], ["FACT_EXTRACTION_PROVIDER_NOT_CALLED"]
    fact_dicts: list[dict] = []
    reasons: list[str] = []
    for item in resolved:
        if item.processing_status != "ready":
            continue
        if item.source.source_type.value not in {
            SourceType.document.value,
            SourceType.narrative.value,
        }:
            continue
        if not item.text:
            continue
        try:
            provider_facts = _run_provider(
                chain,
                source_id=item.source.source_id,
                source_type=item.source.source_type.value,
                text=item.text,
            )
            if not provider_facts:
                reasons.append("FACT_EXTRACTION_EMPTY_CLAIMS")
                continue
            method = (
                "qwen"
                if (chain.last_provider_kind or "rule") == "cloud"
                else "rule"
            )
            normalized = _fact_dicts(
                "und",
                source_id=item.source.source_id,
                source_type=item.source.source_type.value,
                provider_facts=provider_facts,
                method=method,
            )
            if normalized:
                fact_dicts.extend(normalized)
            else:
                reasons.append("FACT_EXTRACTION_NORMALIZATION_FILTERED_ALL")
        except ProviderFailureV3 as error:
            failures = list(getattr(chain, "last_failure_codes", None) or [])
            failures.append(error.error_code)
            if error.error_code == "MEDICAL_ASSET_UNAVAILABLE":
                reasons.append("FACT_EXTRACTION_CLAIM_DICTIONARY_MISMATCH")
            elif "MODEL_SCHEMA_INVALID" in failures:
                reasons.append("FACT_EXTRACTION_SCHEMA_INVALID")
            else:
                specific = next(
                    (code for code in failures if code != "PROVIDER_UNAVAILABLE"),
                    error.error_code,
                )
                safe_code = re.sub(r"[^A-Z0-9_]+", "_", specific.upper()).strip("_")
                reasons.append(f"FACT_EXTRACTION_PROVIDER_ERROR_{safe_code}")
        except (AttributeError, TypeError, ValueError):
            reasons.append("FACT_EXTRACTION_NORMALIZATION_FILTERED_ALL")
    return fact_dicts, list(dict.fromkeys(reasons))


def re_extract_facts(
    chain: UnderstandingProviderChain | None,
    edited_text: str,
) -> tuple[list[dict], list[str]]:
    """Re-extract facts from an edited summary (full-text correction).

    Returns (fact dicts, affected fact ids) or raises ProviderFailureV3 /
    returns empty when extraction is impossible — callers must then keep the
    old revision instead of publishing empty facts.
    """
    if chain is None:
        return [], []
    provider_facts = _run_provider(
        chain,
        source_id="user_correction",
        source_type="user_correction",
        text=edited_text,
    )
    method = (
        "qwen"
        if (chain.last_provider_kind or "rule") == "cloud"
        else "rule"
    )
    fact_dicts = _fact_dicts(
        "und",
        source_id="user_correction",
        source_type="user_correction",
        provider_facts=provider_facts,
        method=method,
    )
    affected_ids = [item["fact_id"] for item in fact_dicts]
    return fact_dicts, affected_ids


def persist_normalized_facts(
    db: Session,
    *,
    understanding_id: str,
    understanding_revision: int,
    fact_dicts: list[dict],
    source_rows: list[UnderstandingSource],
) -> None:
    """Write NormalizedFact + FactSourceRef audit rows for an understanding.

    ``fact_source_refs.fact_row_id`` is a foreign key to
    ``normalized_facts.fact_row_id`` and the two mappers declare no
    ``relationship()``, so the ORM UnitOfWork has no dependency edge for them
    and cannot order the INSERTs: with ``PRAGMA foreign_keys=ON`` (the
    production SQLite engine) a single implicit flush may write the child refs
    before their parent facts, and the whole ingestion fails with
    ``sqlite3.IntegrityError: FOREIGN KEY constraint failed``. The parent facts
    are therefore flushed explicitly before any ref is added — the same
    discipline ``ensure_questionnaire_fact_rows`` already follows. The caller
    still owns the transaction; this only fixes the write order.
    """

    del source_rows  # refs carry their own source provenance; signature stable
    pending_refs: list[tuple[str, list[dict]]] = []
    for fact in fact_dicts:
        fact_row_id = f"factrow_{uuid.uuid4().hex}"
        db.add(
            NormalizedFactRow(
                fact_row_id=fact_row_id,
                fact_id=fact["fact_id"],
                owner_type="understanding",
                understanding_id=understanding_id,
                understanding_revision=understanding_revision,
                questionnaire_submission_id=None,
                fact_code=fact["fact_code"],
                category=fact["category"],
                display_name=fact["display_name"],
                value_json=fact["value"],
                time_window=fact["time_window"],
                negated=1 if fact["negated"] else 0,
                subject=fact["subject"],
                confirmation_status=fact["confirmation_status"],
                extraction_method=fact["extraction"]["method"],
                extraction_confidence=fact["extraction"].get("confidence"),
                supersedes_fact_row_id=None,
            )
        )
        pending_refs.append((fact_row_id, list(fact["source_refs"])))
    if not pending_refs:
        return
    # Parents first: every ref below references a fact row already in the DB.
    db.flush()
    for fact_row_id, refs in pending_refs:
        for ref in refs:
            db.add(
                FactSourceRef(
                    fact_row_id=fact_row_id,
                    source_type=ref["source_type"],
                    source_id=ref["source_id"],
                    span_ref=ref.get("span_ref"),
                )
            )
