# PR #91 Agent Idempotency and Ownership Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Resolve PR #91's merge blockers by adding real V3 idempotent replay to Agent 1 and Agent 2, enforcing Diagnosis ownership and session binding, and documenting Agent 2 as BLOCKED_BY_MEDICAL_ASSET.

**Architecture:** Keep all work on feat/s5-ai-owner-flow-foundation. Reuse V3IdempotencyRecord: scope by owner, operation and key; hash canonical request JSON; atomically store the first resource ID and response snapshot; replay it with HTTP 200; reject a changed payload. Add session_id to DiagnosisV31Input, then validate Session + AssessmentV3 + AssessmentRevisionV3 in one owner-scoped join before reading Assessment data. Do not connect fake RAG or Qwen paths because approved medical assets are absent.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, SQLAlchemy, SQLite test database, pytest.

**Spec:** PR #91 final review requirements supplied on 2026-09-01; docs/contracts/harmonyai-v3-contract-freeze-v3.0.0-draft.2.md; docs/contracts/harmonyai-v3-persistence-contract.md.

## Global Constraints

- Branch remains feat/s5-ai-owner-flow-foundation; update PR #91 only.
- Base remains integration/sprint4-real-input.
- Do not rebase, force-push, create another PR, or change Frozen Contract semantics outside the reviewed V3.1 request binding.
- Do not track temporary files, caches, databases, test output, generated artifacts, or unrelated changes.
- Same owner + operation + key + canonical payload returns the first result with HTTP 200 and creates no new business row.
- Same owner + operation + key + changed payload returns IDEMPOTENCY_KEY_REUSED and creates no row.
- Cross-user, cross-session and inconsistent Assessment references return RESOURCE_NOT_FOUND.
- Diagnosis accepts only confirmed Assessment V3.1 rows with matching revisions, flow_contract_version=v3-owner-flow-1, safety_policy=deferred_v3 and safety_status=null.
- Agent 2 capability is BLOCKED_BY_MEDICAL_ASSET. Do not invent a syndrome whitelist, RAG hits or Qwen output.
- Ordinary logs must not include user source text, questionnaire answers, OCR text or Provider prompts.

---

### Task 1: Lock Agent 1 idempotency with failing tests

**Files:**
- Modify: tests/api/v3/test_assessment_v3.py

**Interfaces:**
- Consumes: POST /api/v3/assessments, AssessmentV3, V3IdempotencyRecord.
- Produces: replay, payload-conflict and row-count regression tests.

- [ ] **Step 1: Add row-count support**

Import AssessmentV3 and V3IdempotencyRecord. Add a helper that opens db_session_factory(), resolves the authenticated user with _user_pk(), counts that user's AssessmentV3 rows, and closes the session.

~~~python
def _assessment_count(db_session_factory, headers):
    db = db_session_factory()
    try:
        user_pk = _user_pk(db, headers)
        return db.query(AssessmentV3).filter(
            AssessmentV3.internal_user_pk == user_pk
        ).count()
    finally:
        db.close()
~~~

- [ ] **Step 2: Write the replay test**

Create and confirm an Understanding with existing helpers. POST one Assessment body twice with key asmt-replay. Assert first=201, replay=200, both data objects and assessment_id are identical, AssessmentV3 count is one, and one succeeded idempotency record exists for operation create_v3_assessment.

- [ ] **Step 3: Write the changed-payload conflict test**

Reuse the first key but change expected_input_revision or understanding_ref.revision. Assert HTTP 422, error.code=IDEMPOTENCY_KEY_REUSED, and AssessmentV3 count remains one.

- [ ] **Step 4: Verify RED**

Run:

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-red-assessment tests/api/v3/test_assessment_v3.py -k "replay or idempotency" -q
~~~

Expected: the replay creates another Assessment or returns 201, and the changed payload is not rejected as an idempotency conflict.

---

### Task 2: Implement Agent 1 idempotency

**Files:**
- Modify: backend/app/services/v3/assessment_service.py
- Modify: backend/app/routers/v3/assessment_router.py
- Test: tests/api/v3/test_assessment_v3.py

**Interfaces:**
- Consumes: V3IdempotencyRecord and _request_hash(request.model_dump(mode="json")).
- Produces: create_assessment returning (AssessmentV31Response, replayed); IdempotencyConflict.

- [ ] **Step 1: Define the operation and conflict**

Import timedelta and V3IdempotencyRecord. Define _OPERATION="create_v3_assessment", IdempotencyConflict, and the same timezone-normalization helper used by session_service.py.

- [ ] **Step 2: Check idempotency before validation or UUID generation**

Query V3IdempotencyRecord by principal.internal_user_pk, operation and key. Remove only one expired record. Reject a non-expired record whose request_hash differs. For a succeeded record with resource_type=assessment, resource_id and response_json, validate response_json as AssessmentV31Response and return it with replayed=True.

~~~python
request_hash = _request_hash(request.model_dump(mode="json"))
record = db.query(V3IdempotencyRecord).filter(
    V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
    V3IdempotencyRecord.operation == _OPERATION,
    V3IdempotencyRecord.idempotency_key == idempotency_key,
).one_or_none()
if record is not None and record.request_hash != request_hash:
    raise IdempotencyConflict
if record is not None and record.status == "succeeded" and record.response_json:
    return AssessmentV31Response.model_validate_json(record.response_json), True
~~~

- [ ] **Step 3: Persist the record atomically**

Create a processing record only if absent. After flushing Assessment, Revision, FactEvidence and OrganEvidence rows, set resource_type=assessment, resource_id=assessment_id, status=succeeded, response_code=201 and response_json=response.model_dump_json(). Use the existing single db.commit() for both business and idempotency rows.

- [ ] **Step 4: Map the conflict**

In assessment_router.py catch IdempotencyConflict and return HTTP 422, code IDEMPOTENCY_KEY_REUSED, message 相同的幂等键已被不同的请求使用。. Keep replay status=200.

- [ ] **Step 5: Verify GREEN**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-green-assessment tests/api/v3/test_assessment_v3.py -q
~~~

- [ ] **Step 6: Commit**

~~~powershell
git add backend/app/services/v3/assessment_service.py backend/app/routers/v3/assessment_router.py tests/api/v3/test_assessment_v3.py
git commit -m "fix(v3): make assessment creation idempotent"
~~~

---

### Task 3: Define and test the Diagnosis session boundary

**Files:**
- Modify: backend/app/schemas/v3/diagnosis.py
- Modify: tests/api/v3/test_diagnosis_v3.py
- Modify: tests/ai_engine/v3/test_owner_flow_v31_schemas.py

**Interfaces:**
- Consumes: DiagnosisV31Input, AssessmentRefV31.
- Produces: required DiagnosisV31Input.session_id and ownership regression coverage.

- [ ] **Step 1: Add session_id to Diagnosis V3.1 only**

~~~python
class DiagnosisV31Input(V3BaseModel):
    schema_version: Literal["diagnosis_v3.1"]
    session_id: NonEmptyString
    diagnosis_id: NonEmptyString
    assessment_ref: AssessmentRefV31
~~~

Update _diagnosis_body() to serialize its existing session_id argument. Update V3.1 schema fixtures; do not change legacy DiagnosisV3Input.

- [ ] **Step 2: Seed real Assessment ownership**

Update _seed_confirmed_assessment() to add AssessmentV3 before AssessmentRevisionV3. Populate internal_user_pk, session_row_id, current_revision=1, status=confirmed, flow_contract_version=v3-owner-flow-1, input_revision=1, safety_policy=deferred_v3, safety_status=None and safety_evaluation_status=not_run.

- [ ] **Step 3: Keep a valid-owner success test**

The existing insufficient-evidence test must pass only when principal, request.session_id, AssessmentV3 and AssessmentRevisionV3 all match.

- [ ] **Step 4: Add cross-user and cross-session tests**

Cross-user: create Assessment under user A and call as user B. Cross-session: create sessions A and B for the same user, bind Assessment to A, send request.session_id=B. Assert HTTP 404, RESOURCE_NOT_FOUND and DiagnosisRun count zero.

- [ ] **Step 5: Add mismatch and confirmation tests**

Independently test:
- assessment_ref.revision differs from AssessmentV3.current_revision or Revision row;
- assessment_ref.input_revision differs from AssessmentV3 and AssessmentRevisionV3;
- AssessmentV3 or AssessmentRevisionV3 is unconfirmed.

Each case returns the same 404 envelope and creates no DiagnosisRun.

- [ ] **Step 6: Verify RED**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-red-ownership tests/api/v3/test_diagnosis_v3.py -k "user or session or revision or unconfirmed or abstains" -q
~~~

Expected: old revision-only lookup accepts an invalid reference or fails for a non-contract reason.

---

### Task 4: Implement the owner-scoped Assessment join

**Files:**
- Modify: backend/app/services/v3/diagnosis_service.py
- Modify: backend/app/routers/v3/diagnosis_router.py
- Test: tests/api/v3/test_diagnosis_v3.py

**Interfaces:**
- Consumes: DiagnosisV31Input.session_id, AssessmentV3, AssessmentRevisionV3, SessionModel.
- Produces: one safe owner/session/revision lookup; all failures raise OwnedResourceNotFound.

- [ ] **Step 1: Replace independent lookups with one joined query**

Join AssessmentV3 to SessionModel by session_row_id and AssessmentRevisionV3 by assessment_id+revision. Filter:

~~~python
AssessmentV3.assessment_id == ref.assessment_id
AssessmentV3.internal_user_pk == principal.internal_user_pk
SessionModel.user_id == principal.internal_user_pk
SessionModel.session_id == request.session_id
AssessmentV3.current_revision == ref.revision
AssessmentV3.input_revision == ref.input_revision
AssessmentRevisionV3.input_revision == ref.input_revision
AssessmentV3.status == "confirmed"
AssessmentRevisionV3.status == "confirmed"
AssessmentRevisionV3.confirmation_status == "confirmed"
AssessmentV3.flow_contract_version == "v3-owner-flow-1"
AssessmentV3.safety_policy == "deferred_v3"
AssessmentV3.safety_status.is_(None)
~~~

If one_or_none() returns none, raise OwnedResourceNotFound. Remove the Diagnosis InputRevisionConflict branch because it can leak that a resource exists.

- [ ] **Step 2: Use only joined rows downstream**

Use session_row.id and assessment_revision.organ_profile_json from the joined tuple. Do not query by bare input_revision or bare assessment_id later.

- [ ] **Step 3: Verify GREEN**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-green-ownership tests/api/v3/test_diagnosis_v3.py -q
~~~

- [ ] **Step 4: Commit**

~~~powershell
git add backend/app/schemas/v3/diagnosis.py backend/app/services/v3/diagnosis_service.py backend/app/routers/v3/diagnosis_router.py tests/api/v3/test_diagnosis_v3.py tests/ai_engine/v3/test_owner_flow_v31_schemas.py
git commit -m "fix(v3): bind diagnosis to owned assessment session"
~~~

---

### Task 5: Add Agent 2 idempotency

**Files:**
- Modify: tests/api/v3/test_diagnosis_v3.py
- Modify: backend/app/services/v3/diagnosis_service.py
- Modify: backend/app/routers/v3/diagnosis_router.py

**Interfaces:**
- Consumes: owner-scoped input from Task 4 and V3IdempotencyRecord.
- Produces: operation create_v3_diagnosis, replayed DiagnosisV3, IdempotencyConflict.

- [ ] **Step 1: Write replay and conflict tests**

For replay, submit the same insufficient-evidence Diagnosis twice with one key. Assert 201 then 200, identical data and diagnosis_id, exactly one DiagnosisRun and one succeeded idempotency record.

For conflict, reuse the key with a changed diagnosis_id or assessment_ref.input_revision. Assert 422 IDEMPOTENCY_KEY_REUSED and DiagnosisRun count remains one.

- [ ] **Step 2: Verify RED**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-red-diagnosis-idem tests/api/v3/test_diagnosis_v3.py -k "idempot" -q
~~~

- [ ] **Step 3: Implement the existing V3 lifecycle**

Define _OPERATION="create_v3_diagnosis". Hash the complete request. Handle a single expired record, hash conflict and succeeded response replay before generating diagnosis_id. Persist resource_type=diagnosis, resource_id, status=succeeded, response_code=201 and result.model_dump_json() in the same commit as DiagnosisRun.

- [ ] **Step 4: Map the conflict**

Catch IdempotencyConflict in diagnosis_router.py and return HTTP 422 with IDEMPOTENCY_KEY_REUSED. Preserve replay HTTP 200.

- [ ] **Step 5: Verify GREEN**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-green-diagnosis-idem tests/api/v3/test_diagnosis_v3.py -q
~~~

- [ ] **Step 6: Commit**

~~~powershell
git add backend/app/services/v3/diagnosis_service.py backend/app/routers/v3/diagnosis_router.py tests/api/v3/test_diagnosis_v3.py
git commit -m "fix(v3): make diagnosis creation idempotent"
~~~

---

### Task 6: State Agent 2's real capability

**Files:**
- Modify: backend/app/services/v3/diagnosis_service.py
- Modify: tests/api/v3/test_diagnosis_v3.py
- Modify: HANDOFF.md
- Update: PR #91 body

**Interfaces:**
- Consumes: current medical asset manifest and MEDICAL_ASSET_UNAVAILABLE behavior.
- Produces: truthful capability label BLOCKED_BY_MEDICAL_ASSET.

- [ ] **Step 1: Correct the module description**

Describe the implemented pipeline as owned confirmed Assessment gate -> deterministic ElementProfile -> honest abstain/medical-asset block. Remove the claimed Query Builder -> RAG -> Qwen execution chain.

- [ ] **Step 2: Prove no fake pipeline runs**

Extend the medical-asset test to assert HTTP 503, MEDICAL_ASSET_UNAVAILABLE, retryable=false, and zero DiagnosisRun, AiProviderRun and RagRetrievalRun rows.

- [ ] **Step 3: Add the HANDOFF checkpoint**

Record exactly:

~~~text
Agent2 capability: BLOCKED_BY_MEDICAL_ASSET
Implemented: ownership/session/confirmed-assessment gate, deterministic ElementProfile derivation, insufficient-evidence abstention, MEDICAL_ASSET_UNAVAILABLE gate.
Not implemented: production Query Builder, approved RAG Retriever, Qwen diagnosis Provider, syndrome whitelist validation.
Reason: no approved RAG ingestion manifest or syndrome whitelist is present.
~~~

- [ ] **Step 4: Verify the boundary**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-agent2-boundary tests/api/v3/test_diagnosis_v3.py -k "asset_unavailable or abstains" -q
~~~

- [ ] **Step 5: Commit**

~~~powershell
git add backend/app/services/v3/diagnosis_service.py tests/api/v3/test_diagnosis_v3.py HANDOFF.md
git commit -m "docs(v3): mark agent2 blocked by medical assets"
~~~

---

### Task 7: Run all verification gates

**Files:**
- Verify only; change files only for failures caused by this branch.

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces: exact evidence for PR #91.

- [ ] **Step 1: Run focused tests**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-targeted tests/api/v3/test_assessment_v3.py tests/api/v3/test_diagnosis_v3.py tests/ai_engine/v3/test_owner_flow_v31_schemas.py -q
~~~

Record exact pass count and names for replay, conflict, cross-user, cross-session, revision mismatch and unconfirmed Assessment.

- [ ] **Step 2: Run V3 ownership regressions**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-v3 tests/api/v3/test_v3_ownership.py tests/api/v3/test_owner_flow.py tests/api/v3/test_v3_api_envelope.py -q
~~~

- [ ] **Step 3: Run Contract tests**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-contract tests/contract -q
~~~

- [ ] **Step 4: Run privacy tests**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-privacy tests/api/test_privacy_logging.py tests/api/test_s4_06_privacy_probe.py -q
~~~

- [ ] **Step 5: Run the full Python suite**

~~~powershell
py -m pytest -p no:cacheprovider --basetemp C:\Users\51178\AppData\Local\Temp\harmonyai-pr91-full tests -q
~~~

- [ ] **Step 6: Verify patch hygiene**

~~~powershell
git diff --check origin/integration/sprint4-real-input...HEAD
git status --short
git diff --name-only origin/integration/sprint4-real-input...HEAD
~~~

Confirm no pytest directory, cache, database, generated result, temporary file or unrelated path is tracked.

---

### Task 8: Update original PR #91 and wait for CI

**Files:**
- Update GitHub metadata for PR #91 only.

**Interfaces:**
- Consumes: verified commits and exact test output.
- Produces: updated original PR; normal push; CI SUCCESS.

- [ ] **Step 1: Correct PR #91 scope**

Replace any RAG+Qwen-complete claim with:

~~~text
Agent2 foundation/degraded gate — BLOCKED_BY_MEDICAL_ASSET.
This PR does not execute production RAG or Qwen diagnosis because no approved RAG ingestion manifest or syndrome whitelist is available. It preserves honest insufficient-evidence abstention and MEDICAL_ASSET_UNAVAILABLE behavior.
~~~

Also summarize Agent 1/2 idempotency and Diagnosis owner/session validation.

- [ ] **Step 2: Push normally**

~~~powershell
git push origin feat/s5-ai-owner-flow-foundation
~~~

Do not use force, force-with-lease, rebase or a new branch.

- [ ] **Step 3: Verify PR identity**

Record PR #91 base, head branch, latest full commit SHA and exact Changed Files count.

- [ ] **Step 4: Wait for required checks**

Wait until GitHub Actions reports SUCCESS. If CI fails, inspect and reproduce the exact failure, add a regression test where applicable, fix on the same branch and push a normal follow-up commit.

- [ ] **Step 5: Publish final evidence**

Report:

~~~text
Latest commit: full SHA
PR #91 HEAD: full SHA
Changed Files: exact count
Targeted tests: exact passed count
Contract tests: exact passed count
New replay/conflict/ownership tests: exact passed count and names
git diff --check: PASS
GitHub CI: SUCCESS
Agent2 capability: BLOCKED_BY_MEDICAL_ASSET
~~~

Never report REAL_RAG_QWEN unless approved medical assets are added in separately approved scope and real Query Builder, Retriever and Qwen calls are verified end to end.
