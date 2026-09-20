"""Sprint 6 Phase 4 — Evidence Kernel + Authority Firewall (API-level).

These tests drive the formal ``POST /api/v3/diagnoses`` entry with the real
service / pipeline / dominance / Agent3 / persistence path and a *fake
transport* only (no network, no provider keys). They pin the discoveries Phase 4
is required to close:

* P4-T1 approved-but-not-current-run chunk
* P4-T2 previous-run chunk replay
* P4-T3 unknown/stale fact
* P4-T4 direction mismatch
* P4-T5 duplicate refs
* P4-T6 duplicate syndrome code (no raw IntegrityError, clean transaction)
* P4-T7 adapter-bypassing provider still caught by the shared validator
* P4-T8 unsupported medical rationale cannot reach presentation
* P4-T9 provider order does not control the headline
* P4-T10 relative_support does not affect authority
* P4-T11/T12/T13 kernel determinism / current-run scope / narrative independence
* P4-T14 RAG_EMPTY
* P4-T15 provider technical failure
* P4-T16 idempotency
* P4-T17 legacy row
* P4-T18 no extra AI/network calls
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
from backend.ai_engine.v3.grounding import (
    GROUNDING_STATUS_BUILT,
    GROUNDING_STATUS_LEGACY_UNVERIFIED,
    grounding_status_of,
)
from backend.app.core import agent_config
from backend.app.main import app
from backend.app.models.v3.assessment import FactEvidence as FactEvidenceRow
from backend.app.models.v3.diagnosis import (
    AiProviderRun,
    DiagnosisCandidate,
    DiagnosisRun,
    RagRetrievalRun,
)
from backend.app.models.v3.understanding import FactSourceRef, NormalizedFact
from backend.app.schemas.v3.common import Degradation
from backend.app.schemas.v3.diagnosis import RagHit, RagResult
from backend.app.services.v3 import diagnosis_service
from tests.api import conftest as api_conftest  # noqa: F401  (pytest fixtures)
from tests.api.v3.test_diagnosis_v3 import (
    _diagnosis_body,
    _guest_headers,
    _seed_confirmed_assessment,
    _setup_flow_session,
)
from tests.api.v3.test_diagnosis_v31_pipeline_entry import (
    _confirmed_state_for,
    _manifest,
)

ORGAN_SUPPORT = {"liver": 6.0, "spleen": 5.0}


class _RagStore:
    """RAG store double with a caller-controlled current-run hit set."""

    def __init__(self, hit_ids, *, status="success", corpus_ids=None):
        manifest = _manifest()
        self.manifest = manifest
        self.status = status
        self.hit_ids = list(hit_ids)
        self.approved_chunk_ids = frozenset(
            corpus_ids if corpus_ids is not None else hit_ids
        )
        self.chunk_checksums: dict = {}
        self.chunk_text_checksums: dict = {}

    def query(self, query, *, confirmed_state_text=None):
        del query, confirmed_state_text
        manifest = self.manifest
        hits = [
            RagHit(
                chunk_id=chunk_id,
                source_id=f"src_{chunk_id}",
                source_title=f"approved source {chunk_id}",
                section="approved_section",
                retrieval_score=0.9,
                text=f"approved medical text for {chunk_id}",
                display_summary="approved summary",
                review_status="approved",
            )
            for chunk_id in self.hit_ids
        ]
        return RagResult(
            retrieval_id=f"rag_{uuid.uuid4().hex}",
            status="success" if hits else self.status,
            knowledge_version=manifest.knowledge_version,
            embedding_version=manifest.embedding_version,
            retrieval_score_semantics=manifest.retrieval_score_semantics,
            hits=hits,
            degradation=Degradation(active=False, reason_codes=[]),
        )


class _FakeBackend:
    """Transport double for the real provider adapter."""

    def __init__(self, payloads):
        self.model = "phase4-fake"
        self.payloads = payloads
        self.calls = 0

    async def acomplete_json(self, prompt, user_prompt):
        del prompt, user_prompt
        self.calls += 1
        return self.payloads[min(self.calls - 1, len(self.payloads) - 1)]


class _BypassProvider:
    """Provider double that hands the payload straight back (no adapter)."""

    provider_name = "bypass"
    backend = None
    medical_rule_version = "medical-rules-v3.1-r1"

    def __init__(
        self, payloads, *, allowed_chunk_ids, allowed_syndrome_codes, allowed_fact_ids
    ):
        self.payloads = payloads
        self.calls = 0
        self.allowed_chunk_ids = set(allowed_chunk_ids)
        self.allowed_syndrome_codes = set(allowed_syndrome_codes)
        self.allowed_fact_ids = set(allowed_fact_ids)

    async def acomplete_json(self, **kwargs):
        del kwargs
        self.calls += 1
        return self.payloads[min(self.calls - 1, len(self.payloads) - 1)]


def _candidate(**overrides):
    payload = {
        "syndrome_code": "syndrome_1",
        "display_name": "safe tendency",
        "relative_support": 0.8,
        "supporting_fact_ids": [],
        "contradicting_fact_ids": [],
        "knowledge_chunk_ids": [],
        "reasoning_summary": "tendency reference",
    }
    payload.update(overrides)
    return payload


def _response(candidates):
    return {
        "status": "success",
        "candidate_tendencies": list(candidates),
        "abstained": False,
        "abstain_reason": None,
    }


def _seed_contradicting_fact(db, *, assessment_id: str, suffix: str) -> str:
    fact_evidence_id = f"fev_contra{suffix}"
    fact_row_id = f"nfr_{fact_evidence_id}"
    db.add(
        NormalizedFact(
            fact_row_id=fact_row_id,
            fact_id=f"fact_contra{suffix}",
            owner_type="understanding",
            understanding_id=f"und_p4{suffix}",
            understanding_revision=1,
            questionnaire_submission_id=None,
            fact_code="anger_tendency",
            category="emotion",
            display_name="contradicting display",
            value_json={"type": "boolean", "value": True},
            time_window="recent",
            negated=0,
            subject="self",
            confirmation_status="confirmed",
            extraction_method="deterministic_questionnaire_mapping",
            extraction_confidence=1.0,
        )
    )
    db.add(
        FactSourceRef(
            fact_row_id=fact_row_id,
            source_type="questionnaire",
            source_id=f"q_contra{suffix}",
            span_ref=None,
        )
    )
    db.add(
        FactEvidenceRow(
            fact_evidence_row_id=f"fer_{fact_evidence_id}",
            fact_evidence_id=fact_evidence_id,
            assessment_id=assessment_id,
            assessment_revision=1,
            normalized_fact_row_id=fact_row_id,
            claim_code="anger_tendency",
            category="emotion",
            display_name="contradicting display",
            value_json={"type": "boolean", "value": True},
            time_window="recent",
            direction="contradicting",
            reliability=1.0,
            confirmation_status="confirmed",
        )
    )
    db.commit()
    return fact_evidence_id


class _Harness:
    """One diagnosis request against a configurable fake chain."""

    def __init__(
        self,
        db_session_factory,
        monkeypatch,
        *,
        payloads,
        hit_ids=("chunk_1",),
        corpus_ids=None,
        rag_status="success",
        bypass_adapter=True,
        allowed_syndrome_codes=("syndrome_1",),
        allowed_fact_ids=None,
        seed_contradicting=False,
        organ_support=None,
    ):
        from tests.ai_engine.v3.test_v31_pipeline import _mapping, _rules
        from tests.api.v3 import test_diagnosis_dominance_routing as routing

        organ_support = organ_support or ORGAN_SUPPORT
        self.routing = routing
        self.backend = _FakeBackend(list(payloads))
        self.store = _RagStore(hit_ids, status=rag_status, corpus_ids=corpus_ids)

        headers = _guest_headers()
        db = db_session_factory()
        try:
            session_id, user_pk, session_row = _setup_flow_session(db, headers)
            assessment_id = _seed_confirmed_assessment(
                db,
                user_pk=user_pk,
                session_row=session_row,
                organ_profile_json=routing._organ_profile(organ_support),
                assessment_input_revision=session_row.input_revision,
                revision_input_revision=session_row.input_revision,
            )
            routing._seed_evidence(
                db,
                assessment_id=assessment_id,
                organ_support=organ_support,
                suffix=f"p4{uuid.uuid4().hex[:6]}",
            )
            self.contradicting_fact_id = (
                _seed_contradicting_fact(
                    db, assessment_id=assessment_id, suffix=uuid.uuid4().hex[:6]
                )
                if seed_contradicting
                else None
            )
        finally:
            db.close()

        allowed_facts = (
            set(allowed_fact_ids)
            if allowed_fact_ids is not None
            else self._fact_ids(db_session_factory, assessment_id)
        )
        if bypass_adapter:
            self.provider = _BypassProvider(
                self.backend.payloads,
                allowed_chunk_ids=self.store.approved_chunk_ids,
                allowed_syndrome_codes=allowed_syndrome_codes,
                allowed_fact_ids=allowed_facts,
            )
        else:
            self.provider = DiagnosisProvider(
                backend=self.backend,
                allowed_syndrome_codes=set(allowed_syndrome_codes),
                allowed_fact_ids=set(allowed_facts),
                allowed_chunk_ids=set(self.store.approved_chunk_ids),
                medical_rule_version="medical-rules-v3.1-r1",
            )

        dependencies = type(
            "Deps",
            (),
            {
                "rag_store": self.store,
                "diagnosis_provider": self.provider,
                "tone_mapping": _mapping(),
                "generation_parameter_rules": _rules(),
                "allowed_syndrome_codes": frozenset(allowed_syndrome_codes),
                "medical_rule_version": "medical-rules-v3.1-r1",
                "rag_query_policy": None,
            },
        )()
        monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
        monkeypatch.setattr(
            agent_config, "get_v31_ai_pipeline_dependencies", lambda: dependencies
        )
        monkeypatch.setattr(
            diagnosis_service,
            "_load_confirmed_user_state",
            lambda *args, **kwargs: _confirmed_state_for(session_id),
        )
        monkeypatch.setattr(
            diagnosis_service,
            "get_latest_preference_snapshot",
            lambda *args, **kwargs: None,
        )

        self.client = TestClient(app)
        self.headers = headers
        self.session_id = session_id
        self.assessment_id = assessment_id
        self.db_session_factory = db_session_factory

    @staticmethod
    def _fact_ids(db_session_factory, assessment_id):
        db = db_session_factory()
        try:
            rows = (
                db.query(FactEvidenceRow)
                .filter(FactEvidenceRow.assessment_id == assessment_id)
                .all()
            )
            return {row.fact_evidence_id for row in rows}
        finally:
            db.close()

    def fact_ids(self):
        return sorted(self._fact_ids(self.db_session_factory, self.assessment_id))

    def use(self, payloads):
        """Replace the provider payloads in place (shared by both seams)."""

        self.backend.payloads[:] = list(payloads)
        return self

    def set_hits(self, hit_ids):
        self.store.hit_ids = list(hit_ids)
        return self

    def body(self):
        """Canonical request body (reused by the idempotency replay test)."""

        return _diagnosis_body(self.session_id, self.assessment_id, 1)

    def post(self, *, idempotency_key=None, body=None):
        return self.client.post(
            "/api/v3/diagnoses",
            headers={
                **self.headers,
                "Idempotency-Key": idempotency_key or f"p4-{uuid.uuid4().hex}",
            },
            json=body if body is not None else self.body(),
        )

    def run_row(self, diagnosis_id):
        db = self.db_session_factory()
        try:
            return db.get(DiagnosisRun, diagnosis_id)
        finally:
            db.close()


def _body(response):
    payload = response.json()
    return payload.get("data", payload)


def _kernel_of(harness, response):
    run = harness.run_row(_body(response)["diagnosis_id"])
    return run.presentation_json["evidence_kernel"]


# --------------------------------------------------------------------------- #
# Current-run citation scope (P4-T1 / P4-T2)
# --------------------------------------------------------------------------- #
def test_p4_t1_approved_but_not_current_run_chunk_fails_closed(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate(knowledge_chunk_ids=["chunk_other"])])],
        hit_ids=("chunk_1",),
        corpus_ids=("chunk_1", "chunk_other"),
    )
    response = harness.post()

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "CHUNK_REFERENCE_INVALID"
    db = db_session_factory()
    try:
        assert db.query(DiagnosisCandidate).count() == 0
        failed = db.query(DiagnosisRun).filter(DiagnosisRun.status == "failed").all()
        assert failed, "the failed run must be audited"
        assert all(row.five_tone_read_model_json is None for row in failed)
        assert all(row.primary_tendency_id is None for row in failed)
    finally:
        db.close()


def test_p4_t2_previous_run_chunk_cannot_be_replayed(db_session_factory, monkeypatch):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate(knowledge_chunk_ids=["chunk_1"])])],
        hit_ids=("chunk_1", "chunk_previous"),
        corpus_ids=("chunk_1", "chunk_previous"),
    )
    first = harness.post()
    assert first.status_code == 201, first.text

    # A later run retrieves only chunk_1: the previous run's chunk is no longer
    # citable, so a response that reuses it must fail closed.
    harness.set_hits(["chunk_1"])
    harness.use([_response([_candidate(knowledge_chunk_ids=["chunk_previous"])])])
    second = harness.post()

    assert second.status_code == 502
    assert _body(second)["error"]["code"] == "CHUNK_REFERENCE_INVALID"


# --------------------------------------------------------------------------- #
# Fact references (P4-T3 / P4-T4 / P4-T5)
# --------------------------------------------------------------------------- #
def test_p4_t3_stale_fact_id_is_rejected(db_session_factory, monkeypatch):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate(supporting_fact_ids=["fev_other_revision"])])],
    )
    response = harness.post()

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "FACT_REFERENCE_INVALID"


def test_p4_t4_direction_mismatch_is_rejected(db_session_factory, monkeypatch):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
        seed_contradicting=True,
    )
    harness.use(
        [
            _response(
                [_candidate(supporting_fact_ids=[harness.contradicting_fact_id])]
            )
        ]
    )
    response = harness.post()

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "EVIDENCE_DIRECTION_MISMATCH"


def test_p4_t5_duplicate_references_are_rejected(db_session_factory, monkeypatch):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    harness.use([_response([_candidate(supporting_fact_ids=[fact_id, fact_id])])])
    response = harness.post()

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "DUPLICATE_EVIDENCE_REFERENCE"


# --------------------------------------------------------------------------- #
# Duplicate syndrome code (P4-T6) and adapter bypass (P4-T7)
# --------------------------------------------------------------------------- #
def test_p4_t6_duplicate_syndrome_code_is_a_mapped_failure(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[
            _response(
                [
                    _candidate(display_name="first", relative_support=0.4),
                    _candidate(display_name="second", relative_support=0.7),
                ]
            )
        ],
    )
    response = harness.post()

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "DUPLICATE_SYNDROME_CODE"
    db = db_session_factory()
    try:
        # No raw IntegrityError escaped and the transaction stayed clean.
        assert db.query(DiagnosisCandidate).count() == 0
        assert (
            db.query(DiagnosisRun).filter(DiagnosisRun.status == "success").count() == 0
        )
    finally:
        db.close()


def test_p4_t7_shared_validator_catches_an_adapter_bypassing_provider(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate(knowledge_chunk_ids=["chunk_other"])])],
        hit_ids=("chunk_1",),
        corpus_ids=("chunk_1", "chunk_other"),
        bypass_adapter=True,
    )
    response = harness.post()

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "CHUNK_REFERENCE_INVALID"


# --------------------------------------------------------------------------- #
# Authority firewall (P4-T8 / P4-T9 / P4-T10)
# --------------------------------------------------------------------------- #
def test_p4_t8_provider_severe_free_text_never_reaches_presentation(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    severe_text = "severe disease escalation must never be shown to the user"
    harness.use(
        [
            _response(
                [
                    _candidate(
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                        reasoning_summary=severe_text,
                        display_name="Severe Condition",
                    )
                ]
            )
        ]
    )
    response = harness.post()

    assert response.status_code == 201, response.text
    data = _body(response)
    presentation = data["presentation"]
    assert severe_text not in (presentation["primary_tendency"] or "")
    assert all(severe_text not in item for item in presentation["basis_summaries"])
    assert "Severe Condition" not in (presentation["primary_tendency"] or "")
    assert all("Severe Condition" not in item for item in presentation["basis_summaries"])
    # The raw provider text still exists for provenance/audit only.
    assert data["candidate_tendencies"][0]["reasoning_summary"] == severe_text


def test_p4_t9_provider_order_does_not_control_the_headline(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
        allowed_syndrome_codes=("syndrome_1", "syndrome_2"),
    )
    facts = harness.fact_ids()
    harness.use(
        [
            _response(
                [
                    _candidate(
                        syndrome_code="syndrome_1",
                        display_name="first by order",
                        relative_support=0.10,
                        supporting_fact_ids=[facts[0]],
                        knowledge_chunk_ids=["chunk_1"],
                    ),
                    _candidate(
                        syndrome_code="syndrome_2",
                        display_name="second by order",
                        relative_support=0.90,
                        supporting_fact_ids=[facts[1]],
                        knowledge_chunk_ids=["chunk_1"],
                    ),
                ]
            )
        ]
    )
    response = harness.post()

    assert response.status_code == 201, response.text
    data = _body(response)
    presentation = data["presentation"]
    assert presentation["primary_tendency"] not in {"first by order", "second by order"}
    run = harness.run_row(data["diagnosis_id"])
    read_model = run.five_tone_read_model_json
    assert presentation["primary_tendency"] == read_model["primary_tone"]["display_name"]


def test_p4_t10_relative_support_does_not_change_authority(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    harness.use(
        [
            _response(
                [
                    _candidate(
                        relative_support=0.05,
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                    )
                ]
            )
        ]
    )
    first = harness.post()
    assert first.status_code == 201, first.text

    other = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[
            _response(
                [
                    _candidate(
                        relative_support=0.99,
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                    )
                ]
            )
        ],
    )
    second = other.post()
    assert second.status_code == 201, second.text

    first_run = harness.run_row(_body(first)["diagnosis_id"])
    second_run = other.run_row(_body(second)["diagnosis_id"])
    assert first_run.five_tone_read_model_json["regulation_mode"] == (
        second_run.five_tone_read_model_json["regulation_mode"]
    )
    assert first_run.five_tone_read_model_json["primary_tone"] == (
        second_run.five_tone_read_model_json["primary_tone"]
    )
    assert first_run.five_tone_read_model_json["tone_weights"] == (
        second_run.five_tone_read_model_json["tone_weights"]
    )
    assert _body(first)["presentation"]["primary_tendency"] == (
        _body(second)["presentation"]["primary_tendency"]
    )


# --------------------------------------------------------------------------- #
# Kernel determinism / scope (P4-T11 / P4-T12 / P4-T13)
# --------------------------------------------------------------------------- #
def _normalized_kernel(kernel):
    """Kernel content with run-identity hashes removed (content must be equal)."""

    payload = json.loads(json.dumps(kernel))
    payload.pop("content_checksum", None)
    payload.pop("assessment_id", None)
    payload.get("rag", {}).pop("retrieval_id", None)
    # The two embedded identity hashes cover the assessment/user-state identity,
    # which necessarily differs between two independent runs.
    payload.get("decision", {}).pop("decision_checksum", None)
    payload.get("decision", {}).pop("read_model_checksum", None)
    return payload


def test_p4_t11_kernel_is_identical_when_only_provider_text_changes(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    harness.use(
        [
            _response(
                [
                    _candidate(
                        display_name="alpha",
                        relative_support=0.2,
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                        reasoning_summary="first phrasing",
                    )
                ]
            )
        ]
    )
    first = harness.post()
    assert first.status_code == 201, first.text

    other = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[
            _response(
                [
                    _candidate(
                        display_name="omega",
                        relative_support=0.95,
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                        reasoning_summary="a completely different and stronger phrasing",
                    )
                ]
            )
        ],
    )
    second = other.post()
    assert second.status_code == 201, second.text

    assert _normalized_kernel(_kernel_of(harness, first)) == _normalized_kernel(
        _kernel_of(other, second)
    )


def test_p4_t12_kernel_contains_only_current_revision_and_current_run(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    facts = harness.fact_ids()
    harness.use(
        [
            _response(
                [
                    _candidate(
                        supporting_fact_ids=[facts[0]],
                        knowledge_chunk_ids=["chunk_1"],
                    )
                ]
            )
        ]
    )
    response = harness.post()
    assert response.status_code == 201, response.text

    kernel = _kernel_of(harness, response)
    assert [item["fact_evidence_id"] for item in kernel["confirmed_facts"]] == facts
    assert kernel["rag"]["hit_ids"] == ["chunk_1"]
    assert kernel["assessment_revision"] == 1
    assert kernel["rag"]["status"] == "success"
    assert kernel["grounding_status"] == GROUNDING_STATUS_BUILT
    assert kernel["audit"]["provider_free_text_authoritative"] is False
    assert kernel["audit"]["semantic_entailment_verified"] is False


def test_p4_t13_kernel_carries_no_narrative_or_provider_text(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    narrative = "user edited narrative must never become evidence"
    severe = "provider free text must never become evidence"
    harness.use(
        [
            _response(
                [
                    _candidate(
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                        reasoning_summary=severe,
                    )
                ]
            )
        ]
    )
    response = harness.post()
    assert response.status_code == 201, response.text

    serialized = json.dumps(_kernel_of(harness, response), ensure_ascii=False)
    assert severe not in serialized
    assert narrative not in serialized
    assert "reasoning_summary" not in serialized
    assert "relative_support" not in serialized


# --------------------------------------------------------------------------- #
# RAG_EMPTY / failure / idempotency / legacy (P4-T14..T18)
# --------------------------------------------------------------------------- #
def test_p4_t14_rag_empty_keeps_the_legal_abstain_path(db_session_factory, monkeypatch):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
        hit_ids=(),
        rag_status="empty",
    )
    response = harness.post()

    assert response.status_code == 201, response.text
    data = _body(response)
    assert data["status"] == "abstained"
    assert data["abstain_reason"] == "RAG_EMPTY"
    assert data["candidate_tendencies"] == []
    assert harness.provider.calls == 0
    run = harness.run_row(data["diagnosis_id"])
    assert run.five_tone_read_model_json["regulation_mode"] == "basic_wellness"
    kernel = run.presentation_json["evidence_kernel"]
    assert kernel["rag"]["hit_ids"] == []
    assert kernel["rag"]["status"] == "empty"
    assert kernel["decision"]["regulation_mode"] == "basic_wellness"


def test_p4_t15_provider_failure_writes_no_mode_and_no_kernel(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate(knowledge_chunk_ids=["chunk_other"])])],
        hit_ids=("chunk_1",),
        corpus_ids=("chunk_1", "chunk_other"),
    )
    response = harness.post()

    assert response.status_code == 502
    db = db_session_factory()
    try:
        failed = db.query(DiagnosisRun).filter(DiagnosisRun.status == "failed").all()
        assert failed
        for row in failed:
            assert row.five_tone_read_model_json is None
            assert "evidence_kernel" not in (row.presentation_json or {})
    finally:
        db.close()


def test_p4_t16_idempotent_replay_reuses_the_same_kernel(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    harness.use(
        [
            _response(
                [
                    _candidate(
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                        reasoning_summary="provider phrasing",
                    )
                ]
            )
        ]
    )
    key = f"p4-replay-{uuid.uuid4().hex}"
    body = harness.body()
    first = harness.post(idempotency_key=key, body=body)
    second = harness.post(idempotency_key=key, body=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert harness.provider.calls == 1
    assert _body(first) == _body(second)
    db = db_session_factory()
    try:
        assert db.query(DiagnosisCandidate).count() == 1
        assert db.query(AiProviderRun).count() == 1
        assert db.query(RagRetrievalRun).count() == 1
    finally:
        db.close()


def test_p4_t17_legacy_row_stays_readable_without_a_kernel(
    db_session_factory, monkeypatch
):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    response = harness.post()
    assert response.status_code == 201, response.text

    run = harness.run_row(_body(response)["diagnosis_id"])
    legacy_payload = dict(run.presentation_json)
    legacy_payload.pop("evidence_kernel", None)

    assert grounding_status_of(legacy_payload) == GROUNDING_STATUS_LEGACY_UNVERIFIED
    assert grounding_status_of(run.presentation_json) == GROUNDING_STATUS_BUILT
    # A legacy row is never silently marked as grounded, and its presentation
    # fields remain readable exactly as written.
    assert "evidence_kernel" not in legacy_payload
    assert legacy_payload["primary_tendency"] == run.presentation_json["primary_tendency"]
    assert legacy_payload["basis_summaries"] == run.presentation_json["basis_summaries"]


def test_p4_t18_no_extra_provider_or_embedding_calls(db_session_factory, monkeypatch):
    harness = _Harness(
        db_session_factory,
        monkeypatch,
        payloads=[_response([_candidate()])],
    )
    fact_id = harness.fact_ids()[0]
    harness.use(
        [
            _response(
                [
                    _candidate(
                        supporting_fact_ids=[fact_id],
                        knowledge_chunk_ids=["chunk_1"],
                    )
                ]
            )
        ]
    )
    response = harness.post()

    assert response.status_code == 201, response.text
    # Phase 4 adds zero provider calls (exactly the one diagnosis call) and no
    # embedding call at all (the RAG store double has no embedder and the
    # pipeline never asks for one).
    assert harness.provider.calls == 1
