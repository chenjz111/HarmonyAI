# HarmonyAI V3.1 AI/Backend Authority Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V3.1 document, Assessment, Agent3, preference, and Five-Tone data chain server-authoritative and resistant to stale inputs.

**Architecture:** The current Session input revision is the root of authority. Document relevance is evaluated and persisted for the exact active DocumentSet revision before Understanding, Agent3 executes once against the current confirmed Assessment, and the resulting FiveToneAnalysisReadModel is persisted on the Diagnosis and reused by Prescription.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Pydantic v2, SQLite/MySQL migrations, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-v31-ai-backend-authority-fixes-design.md`

## Global Constraints

- Do not change frontend code, page order, teacher flow, questionnaire assets, or Safety semantics.
- Do not implement MiniMax or add a new provider dependency.
- Real mode must fail readiness when provider configuration or output is unavailable; it must not switch to Mock.
- Do not modify migrations `0001` through `0008`; add `0009` only.
- Do not invent medical evidence, explanations, transport sections, or Five-Tone values.
- Every production change follows RED -> GREEN -> REFACTOR and is committed only after its targeted tests pass.

---

### Task 1: Invalidate stale document authority on replacement

**Files:**
- Modify: `backend/app/services/v3/activity_service.py`
- Modify: `backend/app/services/v3/understanding_service.py`
- Test: `tests/api/v3/test_relevance_downstream_gate.py`
- Test: `tests/api/v3/test_understanding.py`

**Interfaces:**
- Consumes: existing `apply_input_transition(...)` and `require_current_valid_document_set(...)` behavior.
- Produces: replacement transition with no active DocumentSet until a new set is assembled; confirmation-time exact source validation.

- [ ] **Step 1: Add a failing replacement regression test**

```python
def test_replace_document_invalidates_old_set_and_old_understanding(client, seeded_valid_document_flow):
    old = seeded_valid_document_flow
    response = client.post(
        f"/api/v3/sessions/{old.session_id}/input-transitions",
        headers={**old.auth, "Idempotency-Key": "replace-doc"},
        json={"action": "replace_document", "expected_input_revision": old.input_revision},
    )
    assert response.status_code == 201
    assert response.json()["active_document_set_id"] is None

    confirm = client.post(
        f"/api/v3/understandings/{old.understanding_id}/confirmations",
        headers={**old.auth, "Idempotency-Key": "confirm-old"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": old.understanding_revision,
            "expected_input_revision": response.json()["input_revision"],
            "decision": "confirm",
            "changes": [],
            "reprocess_requested": False,
        },
    )
    assert confirm.status_code == 409
```

- [ ] **Step 2: Run the regression test and verify RED**

Run: `pytest tests/api/v3/test_relevance_downstream_gate.py::test_replace_document_invalidates_old_set_and_old_understanding -v`

Expected: FAIL because `replace_document` retains `active_document_set_id` or the old Understanding confirms successfully.

- [ ] **Step 3: Implement atomic invalidation**

In `activity_service.py`, make the replacement transition clear the active set and active Understanding/Assessment bindings while retaining immutable audit rows. Keep the existing CAS update for `input_revision`.

In `understanding_service.py`, confirmation must call the current-set gate again and compare the Understanding's `input_revision`, ordered document IDs, and set revision with current server state.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run: `pytest tests/api/v3/test_relevance_downstream_gate.py tests/api/v3/test_understanding.py -q`

Expected: all pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/services/v3/activity_service.py backend/app/services/v3/understanding_service.py tests/api/v3/test_relevance_downstream_gate.py tests/api/v3/test_understanding.py
git commit -m "fix(v3.1): invalidate stale document authority"
```

### Task 2: Add a reachable relevance evaluator

**Files:**
- Create: `backend/app/services/v3/document_relevance_evaluator.py`
- Modify: `backend/app/services/v3/document_relevance_service.py`
- Modify: `backend/app/services/v3/understanding_service.py`
- Test: `tests/api/v3/test_document_relevance.py`
- Test: `tests/api/v3/test_understanding_ai_extraction.py`

**Interfaces:**
- Produces: `DocumentRelevanceEvaluator.evaluate(*, document_set, documents, input_revision) -> DocumentRelevanceResult`.
- Produces: `ensure_document_set_relevance(db, session, document_set, evaluator) -> DocumentRelevance`.
- Consumes: current active DocumentSet, ordered OCR-bearing documents, existing `record_relevance(...)` persistence.

- [ ] **Step 1: Add failing evaluator tests**

```python
def test_missing_relevance_invokes_evaluator_once(db, current_document_set, fake_evaluator):
    first = ensure_document_set_relevance(db, current_document_set.session, current_document_set.row, fake_evaluator)
    second = ensure_document_set_relevance(db, current_document_set.session, current_document_set.row, fake_evaluator)
    assert first.relevance_id == second.relevance_id
    assert fake_evaluator.calls == 1


def test_real_provider_failure_never_records_valid(db, current_document_set, failing_evaluator):
    with pytest.raises(DocumentRelevanceEvaluationError):
        ensure_document_set_relevance(db, current_document_set.session, current_document_set.row, failing_evaluator)
    assert latest_relevance(db, current_document_set.row.document_set_id) is None
```

- [ ] **Step 2: Run evaluator tests and verify RED**

Run: `pytest tests/api/v3/test_document_relevance.py -k "invokes_evaluator_once or failure_never_records_valid" -v`

Expected: FAIL because the evaluator module/functions do not exist.

- [ ] **Step 3: Implement evaluator and idempotent orchestration**

Define a protocol and explicit errors:

```python
class DocumentRelevanceEvaluator(Protocol):
    def evaluate(
        self,
        *,
        document_set_id: str,
        set_revision: int,
        input_revision: int,
        ordered_ocr_texts: list[str],
    ) -> DocumentRelevanceResult: ...


class DocumentRelevanceEvaluationError(RuntimeError):
    pass
```

`ensure_document_set_relevance` returns an existing latest exact-revision row, rejects absent OCR text, calls the configured evaluator once, validates `DocumentRelevanceResult`, and persists through `record_relevance`. No exception path records `VALID`.

- [ ] **Step 4: Wire Understanding creation to the orchestrator**

Before `_validate_v31_request_sources` admits a document source, call `ensure_document_set_relevance`. Resolve the evaluator through the existing provider/runtime configuration boundary; explicit Mock fixtures may inject a fake evaluator in tests, while unconfigured Real mode raises readiness failure.

- [ ] **Step 5: Run Task 2 tests and verify GREEN**

Run: `pytest tests/api/v3/test_document_relevance.py tests/api/v3/test_understanding_ai_extraction.py tests/api/v3/test_relevance_downstream_gate.py -q`

Expected: all pass, including a test proving no runtime path silently writes `VALID` after provider failure.

- [ ] **Step 6: Commit Task 2**

```bash
git add backend/app/services/v3/document_relevance_evaluator.py backend/app/services/v3/document_relevance_service.py backend/app/services/v3/understanding_service.py tests/api/v3/test_document_relevance.py tests/api/v3/test_understanding_ai_extraction.py tests/api/v3/test_relevance_downstream_gate.py
git commit -m "feat(v3.1): execute document relevance before understanding"
```

### Task 3: Persist the canonical Five-Tone Read Model

**Files:**
- Modify: `backend/app/models/v3/diagnosis.py`
- Modify: `backend/app/core/v3_migrations.py`
- Create: `backend/migrations/v3/sqlite/0009_v3_five_tone_read_model_up.sql`
- Create: `backend/migrations/v3/sqlite/0009_v3_five_tone_read_model_down.sql`
- Create: `backend/migrations/v3/mysql/0009_v3_five_tone_read_model_up.sql`
- Create: `backend/migrations/v3/mysql/0009_v3_five_tone_read_model_down.sql`
- Modify: `backend/app/services/v3/diagnosis_service.py`
- Test: `tests/api/v3/test_v3_migrations.py`
- Test: `tests/api/v3/test_v3_business_migrations.py`
- Test: `tests/api/v3/test_diagnosis_v31_pipeline_entry.py`

**Interfaces:**
- Produces DiagnosisRun fields: `five_tone_read_model_schema_version`, `five_tone_read_model_json`, `five_tone_read_model_checksum`, `five_tone_generated_at`, `preference_profile_id`, `preference_version`.
- Consumes: validated `FiveToneAnalysisReadModel` returned by the existing V3.1 pipeline.

- [ ] **Step 1: Add failing migration and reload tests**

```python
def test_0009_adds_canonical_five_tone_snapshot(sqlite_v3_database):
    columns = sqlite_v3_database.columns("diagnosis_runs")
    assert "five_tone_read_model_json" in columns
    assert "five_tone_read_model_checksum" in columns


def test_diagnosis_persists_and_reloads_exact_five_tone_read_model(client, seeded_confirmed_assessment):
    created = run_diagnosis_request(client, seeded_confirmed_assessment)
    row = load_diagnosis_row(created["diagnosis_id"])
    restored = FiveToneAnalysisReadModel.model_validate(row.five_tone_read_model_json)
    assert restored.model_dump(mode="json") == created["five_tone_analysis"].model_dump(mode="json")
    assert row.five_tone_read_model_checksum == canonical_checksum(restored)
```

- [ ] **Step 2: Run migration/reload tests and verify RED**

Run: `pytest tests/api/v3/test_v3_migrations.py tests/api/v3/test_diagnosis_v31_pipeline_entry.py -k "0009 or persists_and_reloads" -v`

Expected: FAIL because migration `0009` and DiagnosisRun snapshot fields do not exist.

- [ ] **Step 3: Add non-destructive migration `0009` and ORM fields**

Append `0009_v3_five_tone_read_model` to `V3_MIGRATION_VERSIONS`. SQLite and MySQL up scripts add nullable snapshot columns so historical rows remain valid. Down scripts remove only the new columns using the repository's established engine-specific pattern.

- [ ] **Step 4: Persist the validated canonical model atomically**

Serialize with deterministic key ordering and compact separators, compute `sha256:<hex>`, validate with `FiveToneAnalysisReadModel.model_validate`, and save it on the same DiagnosisRun transaction. If validation or persistence fails, do not expose a successful Agent3 result.

- [ ] **Step 5: Run Task 3 tests and verify GREEN**

Run: `pytest tests/api/v3/test_v3_migrations.py tests/api/v3/test_v3_business_migrations.py tests/api/v3/test_diagnosis_v31_pipeline_entry.py -q`

Expected: all pass for SQLite/MySQL migration rendering and model reload.

- [ ] **Step 6: Commit Task 3**

```bash
git add backend/app/models/v3/diagnosis.py backend/app/core/v3_migrations.py backend/migrations/v3/sqlite/0009_v3_five_tone_read_model_up.sql backend/migrations/v3/sqlite/0009_v3_five_tone_read_model_down.sql backend/migrations/v3/mysql/0009_v3_five_tone_read_model_up.sql backend/migrations/v3/mysql/0009_v3_five_tone_read_model_down.sql backend/app/services/v3/diagnosis_service.py tests/api/v3/test_v3_migrations.py tests/api/v3/test_v3_business_migrations.py tests/api/v3/test_diagnosis_v31_pipeline_entry.py
git commit -m "feat(v3.1): persist canonical five-tone read model"
```

### Task 4: Enforce current Assessment and consume the persisted model

**Files:**
- Modify: `backend/app/services/v3/prescription_service.py`
- Modify: `backend/app/services/v3/internal_agent3_service.py`
- Test: `tests/api/v3/test_prescription.py`
- Test: `tests/ai_engine/v3/test_diagnosis_pipeline_v31.py`

**Interfaces:**
- Consumes: DiagnosisRun canonical snapshot fields from Task 3.
- Produces: `load_current_five_tone_read_model(db, diagnosis, session) -> FiveToneAnalysisReadModel`.
- Removes runtime Prescription dependency on `build_prescription_spec(...)`.

- [ ] **Step 1: Add failing stale-Assessment and no-rerun tests**

```python
def test_prescription_rejects_diagnosis_after_assessment_is_superseded(client, seeded_diagnosis):
    supersede_assessment(seeded_diagnosis.assessment_id)
    response = create_prescription_request(client, seeded_diagnosis.diagnosis_id)
    assert response.status_code == 409


def test_prescription_uses_persisted_read_model_without_agent3_rerun(client, seeded_diagnosis, monkeypatch):
    monkeypatch.setattr(internal_agent3_service, "build_prescription_spec", lambda *args: pytest.fail("Agent3 reran"))
    response = create_prescription_request(client, seeded_diagnosis.diagnosis_id)
    assert response.status_code == 201
    assert response.json()["generation_spec"] == seeded_diagnosis.persisted_generation_spec
```

- [ ] **Step 2: Run Task 4 tests and verify RED**

Run: `pytest tests/api/v3/test_prescription.py -k "superseded or without_agent3_rerun" -v`

Expected: stale Assessment returns 201 or Prescription calls `build_prescription_spec`.

- [ ] **Step 3: Implement current-authority checks**

Resolve current Session and Assessment through Diagnosis references. Require current revision, confirmed state, matching `input_revision`, current source bindings, and current relevance for document modes before reading the snapshot.

- [ ] **Step 4: Replace Agent3 regeneration with snapshot consumption**

Validate `diagnosis.five_tone_read_model_json` using `FiveToneAnalysisReadModel`, verify its checksum, then use its exact ToneProfile, GenerationSpec, presentation, explanations, evidence references, and readiness. Remove duration/BPM-derived and fabricated fallback fields from `internal_agent3_service.py`; retain only helpers still used by Diagnosis execution.

- [ ] **Step 5: Run Task 4 tests and verify GREEN**

Run: `pytest tests/api/v3/test_prescription.py tests/ai_engine/v3/test_diagnosis_pipeline_v31.py -q`

Expected: all pass and no Prescription path executes Agent3 twice.

- [ ] **Step 6: Commit Task 4**

```bash
git add backend/app/services/v3/prescription_service.py backend/app/services/v3/internal_agent3_service.py tests/api/v3/test_prescription.py tests/ai_engine/v3/test_diagnosis_pipeline_v31.py
git commit -m "fix(v3.1): consume current canonical Agent3 result"
```

### Task 5: Apply preferences honestly before persistence

**Files:**
- Create: `backend/app/services/v3/agent3_preference_policy.py`
- Modify: `backend/app/services/v3/diagnosis_service.py`
- Modify: `backend/app/services/v3/prescription_service.py`
- Test: `tests/ai_engine/v3/test_agent3_v31.py`
- Test: `tests/api/v3/test_prescription.py`

**Interfaces:**
- Produces: `apply_preference_policy(read_model, preference) -> tuple[FiveToneAnalysisReadModel, list[PreferenceApplication]]`.
- Consumes: latest server-authoritative preference snapshot and medically validated canonical Agent3 output.

- [ ] **Step 1: Add failing preference truthfulness tests**

```python
def test_equal_preference_is_not_reported_as_applied(canonical_read_model, preference_factory):
    preference = preference_factory(bpm_range=(60, 60), instruments=["guqin"])
    updated, events = apply_preference_policy(canonical_read_model, preference)
    assert updated == canonical_read_model
    assert all(event.applied is False for event in events)


def test_allowed_preference_records_real_before_and_after(canonical_read_model, preference_factory):
    preference = preference_factory(bpm_range=(64, 68))
    updated, events = apply_preference_policy(canonical_read_model, preference)
    bpm_event = next(event for event in events if event.field == "bpm")
    assert bpm_event.applied is True
    assert bpm_event.before == canonical_read_model.bpm.value
    assert bpm_event.after == updated.bpm.value
    assert bpm_event.before != bpm_event.after
```

- [ ] **Step 2: Run preference tests and verify RED**

Run: `pytest tests/ai_engine/v3/test_agent3_v31.py -k "preference" -v`

Expected: FAIL because the policy and truthful event model do not exist.

- [ ] **Step 3: Implement the pure preference policy**

The function must be deterministic, side-effect free, and constrained by approved GenerationSpec ranges. It records applied events only for actual changes and rejected/no-op events with explicit reason codes. It never changes evidence, diagnosis, primary tone, or readiness.

- [ ] **Step 4: Integrate before canonical snapshot persistence**

In `diagnosis_service.py`, load the latest server preference, apply policy to the validated Agent3 Read Model, validate the updated model again, then persist it and the exact application events. `prescription_service.py` reports only these persisted events and must not fabricate a fixed before value.

- [ ] **Step 5: Run Task 5 tests and verify GREEN**

Run: `pytest tests/ai_engine/v3/test_agent3_v31.py tests/api/v3/test_prescription.py -q`

Expected: all pass; no-op preferences are not marked applied and accepted preferences contain real before/after values.

- [ ] **Step 6: Commit Task 5**

```bash
git add backend/app/services/v3/agent3_preference_policy.py backend/app/services/v3/diagnosis_service.py backend/app/services/v3/prescription_service.py tests/ai_engine/v3/test_agent3_v31.py tests/api/v3/test_prescription.py
git commit -m "feat(v3.1): apply music preferences truthfully"
```

### Task 6: Integration verification and delivery gate

**Files:**
- Modify only if a test exposes a scoped defect in Tasks 1-5; return to the corresponding RED/GREEN cycle before editing.

**Interfaces:**
- Consumes: all Task 1-5 deliverables.
- Produces: verified, clean local branch ready for code review.

- [ ] **Step 1: Run focused authority-chain tests**

Run:

```bash
pytest tests/api/v3/test_relevance_downstream_gate.py tests/api/v3/test_document_relevance.py tests/api/v3/test_understanding.py tests/api/v3/test_understanding_ai_extraction.py tests/api/v3/test_diagnosis_v31_pipeline_entry.py tests/api/v3/test_prescription.py tests/ai_engine/v3/test_agent3_v31.py tests/ai_engine/v3/test_diagnosis_pipeline_v31.py -q
```

Expected: all pass.

- [ ] **Step 2: Run V3 contract and migration tests**

Run:

```bash
pytest tests/api/v3/test_v3_migrations.py tests/api/v3/test_v3_business_migrations.py tests/ai_engine/v3/test_owner_flow_v31_schemas.py tests/contracts -q
```

Expected: all pass.

- [ ] **Step 3: Run the full backend suite**

Run: `pytest -q`

Expected: all pass. If not, reproduce every failure on the target baseline before classifying it as unrelated.

- [ ] **Step 4: Run repository integrity checks**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and only intentional changes before the final commit; clean after commits.

- [ ] **Step 5: Review the final commit graph and diff scope**

Run:

```bash
git log --oneline --decorate -10
git diff --stat 67fa0c6269aebd5504226ee1b43bd17930f49bdd..HEAD
```

Expected: only backend authority-chain services, model/migration files, and their tests. No frontend, questionnaire, provider-secret, or unrelated files.

- [ ] **Step 6: Stop for final code review**

Do not push, create a PR, or merge until the final diff and verification evidence are reviewed.
