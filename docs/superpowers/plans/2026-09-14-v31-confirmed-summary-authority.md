# V3.1 Confirmed Summary Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every production behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make document and questionnaire summaries meaningful, editable, and authoritative through diagnosis while preserving provenance.

**Architecture:** Deterministic source-grounded composition produces initial summaries. Immutable revision projection makes full-text edits suppress stale active facts without deleting provenance. Diagnosis uses persisted confirmed text and current-revision evidence only.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Pydantic, Vue/uni-app, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-14-v31-confirmed-summary-authority-design.md`

## Global Constraints

- Work only in `C:\Users\ASUS\HarmonyAI-h5-async-acceptance` on the already-verified branch.
- Do not checkout, reset, switch worktrees, push, or merge.
- Do not modify Frozen V3.1 Contract, canonical questionnaire JSON, DB schema, migrations, medical rules, RAG evidence, or TokenHub state machine.
- Do not call Qwen, Embedding, TokenHub, or Stability; tests use fake/mock only.
- Do not modify or stage `frontend/manifest.json` or `uploads/`.
- Use only anonymous synthetic medical fixtures and never log full OCR.

---

### Task 1: Source-grounded document summary

**Files:**
- Create: `backend/app/services/v3/document_summary.py`
- Modify: `backend/app/services/v3/understanding_service.py`
- Test: `tests/api/v3/test_understanding_summary_authority.py`

- [ ] Write failing tests proving clinical-section priority, PII/branding exclusion, and source grounding.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement deterministic clinical section extraction and wire `_build_case_summary` across ordered documents.
- [ ] Run focused tests to green.

### Task 2: Provider-independent Understanding edit projection

**Files:**
- Modify: `backend/app/services/v3/understanding_service.py`
- Test: `tests/api/v3/test_understanding_summary_authority.py`

- [ ] Write failing tests proving edit save succeeds without Provider, removed facts leave the active revision, old facts remain in the previous revision, empty guard/revision/idempotency remain.
- [ ] Run and confirm failures.
- [ ] Replace Provider re-extraction with conservative current-revision fact projection based on the confirmed text.
- [ ] Run focused tests to green.

### Task 3: Assessment summary composition and edit authority

**Files:**
- Modify: `backend/app/services/v3/assessment_service.py`
- Test: `tests/api/v3/test_assessment_summary_authority.py`

- [ ] Write failing tests for all three input modes, questionnaire fact composition, document summary inheritance, and stale-fact suppression after edit.
- [ ] Run and confirm failures.
- [ ] Compose initial summaries from confirmed CaseSummary and/or questionnaire display names.
- [ ] On full-text edit, copy only facts represented by the final text; keep the prior revision untouched.
- [ ] Run focused tests to green.

### Task 4: Diagnosis and retrieval current-state input

**Files:**
- Modify: `backend/app/services/v3/diagnosis_service.py`
- Modify only existing internal diagnosis query/provider plumbing needed to carry confirmed state text.
- Test: `tests/api/v3/test_diagnosis_summary_authority.py`
- Test: relevant `tests/ai_engine/v3/` diagnosis tests.

- [ ] Write failing tests proving questionnaire/document removed facts are absent from actual diagnosis/retrieval input, edited text is present, provenance remains, and unedited facts remain active.
- [ ] Run and confirm failures.
- [ ] Add persisted confirmed state text to the internal assessment snapshot/query/provider context without public Contract or schema changes; use only current-revision active facts.
- [ ] Run focused tests to green.

### Task 5: Frontend binding and flow regressions

**Files:**
- Modify: `frontend/pages/v3-summary/v3-summary.vue`
- Modify: `frontend/pages/v3-confirm/v3-confirm.vue`
- Modify: `frontend/common/api-v3.js` only if required for read-model normalization.
- Test: `frontend/tests/sprint5-v31-summary-authority.test.mjs`

- [ ] Write failing tests for real summary rendering/prefill, generic-copy removal, full-text-only editing, empty guard, and document-only no duplicate confirmation.
- [ ] Run and confirm failures.
- [ ] Apply minimal binding/error-copy/textarea changes.
- [ ] Run focused frontend tests to green.

### Task 6: Verification and commit

- [ ] Run required backend suites for assessment, document, DocumentSet, relevance, understanding, owner flow, summary edit, and diagnosis input.
- [ ] Run every `frontend/tests/*.test.mjs`.
- [ ] Run H5 build and `git diff --check`.
- [ ] Review the complete diff for privacy, Contract/Schema scope, and protected integration behavior.
- [ ] Stage only intended files and commit `fix(v31): make confirmed summaries meaningful and editable`.
