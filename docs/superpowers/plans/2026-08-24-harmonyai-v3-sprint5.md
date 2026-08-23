# HarmonyAI V3 Sprint 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 Owner 已批准用户流程和五 Agent 架构的前提下，将 HarmonyAI V3 合同实现为可迁移、可降级、可追溯、可端到端验收的 Sprint 5 版本。

**Architecture:** V2.1/V2.2 保持可运行，V3 使用 `/api/v3`、独立 Schema、独立持久化表和新前端页面并行建设。所有下游只读取已确认、版本匹配的上游 Snapshot；Cloud Qwen、真实音乐 Provider 失败时走合同定义的 Local/Rule/Matched fallback，任何 fallback 都不能绕过 Safety。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、SQLAlchemy、SQLite/MySQL、LangGraph、Qwen-compatible Provider、Chroma/RAG、uni-app + Vue 3、Node test runner。

**Spec:** `docs/contracts/harmonyai-v3-contract-freeze-v3.0.0-draft.3.md`、`docs/contracts/harmonyai-v3-persistence-contract.md`、`docs/contracts/frontend-read-model-contract-v3.md`、`docs/contracts/harmonyai-v3-contract-final-review.md`

## Global Constraints

- 本计划只有在 PR #75 合并且三份合同状态改为 `FROZEN` 后才允许执行业务实现步骤；具体医学资产仍受独立 production gate 约束，未批准时只能使用明确标记的测试 fixture 验证结构，不能启用正式医学链路。
- 五 Agent 名称与顺序固定：Assessment → Diagnosis → Prescription → Music → Feedback。
- 不改变 Owner 已批准流程；普通用户只经历一次最终 Assessment Confirmation。
- V3 使用新10题五脏问卷；V2 Q19/Q20 不进入 V3 普通流程，但后端 Safety 能力保留。
- Safety `clear | resolved` 才能进入正常音乐轨；confirmed risk 不得进入个性化 Diagnosis/Prescription/Music。
- Diagnosis abstained 且安全、信息充分时使用 `emotion_based | wellness`；不得直接取消全部音乐。
- 前端不得构造 Assessment、Diagnosis、Prescription、GenerationSpec 或 Music 结果。
- `ToneCode` 只允许 `jiao | zhi | gong | shang | yu`。
- Feedback 只更新个人音乐偏好，不修改医学规则、Safety、Evidence 或五行五音映射。
- V3 禁止硬编码 `user_id=1`；所有资源使用 Auth Context 做 ownership 校验。
- 用户原文、OCR/ASR文本、Prompt、Key和Provider原始异常不得进入普通日志。
- 每个任务使用 TDD：先写失败测试，验证失败，再做最小实现，再跑目标测试。
- 每个 PR 从最新 `origin/integration/sprint4-real-input` 创建；禁止直接向 integration 写功能提交。

---

## File Map

| Unit | Responsibility |
|---|---|
| `backend/app/schemas/v3/` | V3 Pydantic 单一权威传输类型 |
| `backend/app/models/v3/` | V3 SQLAlchemy 表映射，不改变 V2 模型语义 |
| `backend/app/core/v3_migrations.py` | SQLite/MySQL 版本化迁移 ledger |
| `backend/app/services/v3/` | Auth、Revision、Assessment、Diagnosis、Music、Feedback 事务服务 |
| `backend/ai_engine/v3/` | Understanding、Assessment、RAG/Diagnosis、Prescription、Provider adapter |
| `backend/app/routers/v3/` | `/api/v3` 路由，只做校验、授权和服务编排 |
| `knowledge/v3/` | 经过医学审核并带版本/checksum的 Manifest |
| `frontend/common/api-v3.js` | V3 API 唯一客户端封装 |
| `frontend/common/v3-flow-state.js` | V3 路由状态，不包含医学判断 |
| `frontend/pages/v3-*/` | 只消费 Frontend Read Model 的 V3 页面 |
| `tests/contract/v3/` | Schema、状态、枚举、跨层引用 Contract Gate |
| `tests/api/v3/` | Auth、ownership、事务、API降级测试 |
| `tests/ai_engine/v3/` | Provider、Evidence、RAG、Agent1-4 测试 |
| `tests/integration/v3/` | 五 Agent 与三类 fallback E2E |
| `frontend/tests/sprint5-*.test.mjs` | V3页面、序列化、路由与禁止字段测试 |

---

### Task 1: Freeze Gate 与机器可执行 Schema

**Owner:** 陈家智；医学资产由肖宇翔签署。

**Files:**
- Create: `backend/app/schemas/v3/__init__.py`
- Create: `backend/app/schemas/v3/common.py`
- Create: `backend/app/schemas/v3/understanding.py`
- Create: `backend/app/schemas/v3/assessment.py`
- Create: `backend/app/schemas/v3/diagnosis.py`
- Create: `backend/app/schemas/v3/prescription.py`
- Create: `backend/app/schemas/v3/music.py`
- Create: `backend/app/schemas/v3/feedback.py`
- Create: `tests/contract/v3/test_v3_schema_contract.py`
- Create: `tests/contract/v3/test_v3_cross_contract.py`
- Modify: `docs/contracts/harmonyai-v3-contract-freeze-v3.0.0-draft.3.md`
- Modify: `docs/contracts/harmonyai-v3-persistence-contract.md`
- Modify: `docs/contracts/frontend-read-model-contract-v3.md`

**Interfaces:**
- Produces: strict Pydantic types with `extra="forbid"`, including `SafetyStatus`, `NormalizedFactValue`, `OrganProfile`, `ToneProfile`, `MusicRef`, `UserGoal`, all Agent request/response types.
- Consumes: PR #75 FROZEN contracts。approved `knowledge/v3` checksums 是 Task 3 及其上层医学链路的依赖，不是可执行 Schema 的依赖。

- [ ] **Step 1: Verify the double-gate freeze checkpoint**

Verify PR #75 records the Owner double-gate decision and that all three contract headers are `FROZEN`. Confirm proxy technical reviews are labelled as proxy and do not impersonate members or approve clinical content. Confirm Issue #77 remains open and unapproved medical assets remain blocked from production. Do not change frozen field names in this step.

- [ ] **Step 2: Write failing Canonical type tests**

```python
from backend.app.schemas.v3.common import SafetyStatus, ToneCode

def test_v3_canonical_enums_are_frozen():
    assert {item.value for item in ToneCode} == {"jiao", "zhi", "gong", "shang", "yu"}
    assert "resolved" in {item.value for item in SafetyStatus}
    assert "blocked" not in {item.value for item in SafetyStatus}
```

Run: `python -m pytest tests/contract/v3/test_v3_schema_contract.py -q`
Expected: FAIL because `backend.app.schemas.v3` does not exist.

- [ ] **Step 3: Implement strict shared and Agent Schemas**

Set `model_config = ConfigDict(extra="forbid")` on every externally parsed model. Implement discriminated unions for Fact values, Diagnosis status, ToneProfile status and MusicTask status. Do not add fields not present in the FROZEN contract.

- [ ] **Step 4: Write and run cross-contract tests**

```python
def test_abstained_diagnosis_can_feed_conservative_prescription():
    diagnosis = DiagnosisV3.model_validate(ABSTAINED_WITH_SUFFICIENT_ASSESSMENT)
    assert diagnosis.abstained is True
    assert diagnosis.safety_status in {SafetyStatus.clear, SafetyStatus.resolved}
```

Also assert questionnaire Fact owner XOR, stable revision IDs, `UserGoal` maximum two choices, and Agent4 never receives provider Prompt from Agent3.

Run: `python -m pytest tests/contract/v3/ -q`
Expected: all V3 contract tests pass.

- [ ] **Step 5: Commit**

```text
feat: freeze executable HarmonyAI V3 schemas
```

---

### Task 2: Guest Auth、Ownership 与 V3 Migration Foundation

**Owner:** 蔡子鑫；陈家智负责 Gate Review。

**Files:**
- Create: `backend/app/core/v3_migrations.py`
- Create: `backend/migrations/v3/sqlite/0001_v3_foundation_up.sql`
- Create: `backend/migrations/v3/sqlite/0001_v3_foundation_down.sql`
- Create: `backend/migrations/v3/mysql/0001_v3_foundation_up.sql`
- Create: `backend/migrations/v3/mysql/0001_v3_foundation_down.sql`
- Create: `backend/app/models/v3/identity.py`
- Create: `backend/app/models/v3/session.py`
- Create: `backend/app/services/v3/auth_service.py`
- Create: `backend/app/routers/v3/auth_router.py`
- Create: `backend/app/routers/v3/session_router.py`
- Modify: `backend/app/core/database.py`
- Modify: `backend/app/main.py`
- Test: `tests/api/v3/test_guest_auth.py`
- Test: `tests/api/v3/test_v3_ownership.py`
- Test: `tests/api/v3/test_v3_migrations.py`

**Interfaces:**
- Produces: `create_guest_principal() -> GuestAuthResponse`, `get_current_v3_principal() -> AuthPrincipal`, `POST /api/v3/auth/guest`, `POST /api/v3/sessions`.
- Consumes: Task 1 `AuthPrincipal`, `GuestAuthResponse`, `EntryReadModel`.

- [ ] **Step 1: Write failing guest and ownership tests**

Test that a guest call creates distinct `public_user_id` values, expired tokens return 401, a client-supplied `user_id` is ignored, and cross-user resource reads return 404.

Run: `python -m pytest tests/api/v3/test_guest_auth.py tests/api/v3/test_v3_ownership.py -q`
Expected: FAIL with missing V3 auth route/service.

- [ ] **Step 2: Write failing SQLite/MySQL migration tests**

Assert `schema_migrations` stores version/checksum, SQLite enables `PRAGMA foreign_keys=ON`, up is idempotent, and a modified applied migration is rejected. Validate MySQL SQL structure without requiring live credentials; live MySQL remains a separate environment gate.

- [ ] **Step 3: Implement the minimum signed guest token path**

Use the existing JWT settings from `backend/app/core/config.py`. Token subject is `public_user_id`; database foreign keys use `internal_user_pk`. Do not log tokens or return internal PKs.

- [ ] **Step 4: Implement migration ledger and models**

Create only identity/session foundation tables in `0001`. Keep V2 `sessions.id` integer PK and `sessions.session_id` unique business ID.

- [ ] **Step 5: Run target tests**

Run: `python -m pytest tests/api/v3/test_guest_auth.py tests/api/v3/test_v3_ownership.py tests/api/v3/test_v3_migrations.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```text
feat: add V3 guest auth and migration foundation
```

---

### Task 3: Approved Medical Manifests、Questionnaire 与 Fact Adapter

**Owner:** 肖宇翔；陈家智冻结 checksum 和 API identity。

**Files:**
- Create: `knowledge/v3/questionnaire-v3.0.json`
- Create: `knowledge/v3/claim-dictionary-v3.0.json`
- Create: `knowledge/v3/organ-mapping-v3.0.json`
- Create: `knowledge/v3/five-tone-mapping-v3.0.json`
- Create: `knowledge/v3/knowledge-manifest-v3.0.json`
- Create: `backend/ai_engine/v3/questionnaire_adapter.py`
- Create: `backend/app/services/v3/questionnaire_service.py`
- Create: `backend/app/routers/v3/questionnaire_router.py`
- Test: `tests/knowledge/v3/test_v3_medical_manifests.py`
- Test: `tests/ai_engine/v3/test_questionnaire_fact_adapter.py`
- Test: `tests/api/v3/test_questionnaire_v3_api.py`

**Interfaces:**
- Produces: `load_questionnaire_manifest()`, `validate_submission()`, `adapt_questionnaire_submission() -> list[NormalizedFact]`.
- Consumes: Task 1 `QuestionnaireSchemaV3`, `QuestionnaireV3Submission`, `NormalizedFact`.

- [ ] **Step 1: Add signed Medical Review metadata**

Each Manifest must contain `version`, `review_status="approved"`, reviewer identity, review date, source references and SHA-256 checksum calculated from canonical JSON. The code must reject `draft` or checksum mismatch.

- [ ] **Step 2: Write failing manifest tests**

Assert exactly10 questions, `past_7_days`, unique question/option/claim codes, none exclusivity, all claim references exist, every Organ link uses an approved claim, all tone weights use Canonical ToneCode, and every referenced knowledge chunk exists.

- [ ] **Step 3: Write failing adapter tests**

```python
def test_questionnaire_adapter_owns_facts_by_submission():
    facts = adapt_questionnaire_submission(APPROVED_SUBMISSION)
    assert all(f.owner_type == "questionnaire" for f in facts)
    assert all(f.questionnaire_submission_id == "qsub_test" for f in facts)
    assert all(f.extraction.method == "deterministic_questionnaire_mapping" for f in facts)
```

Also test `none` creates no positive Fact and cannot coexist with another option.

- [ ] **Step 4: Implement loader, adapter and API**

`GET /api/v3/questionnaire/schema` returns only public labels/codes. `POST /api/v3/questionnaire/submissions` verifies schema identity/checksum and persists an immutable submission before Fact adaptation.

- [ ] **Step 5: Run target tests and commit**

Run: `python -m pytest tests/knowledge/v3/ tests/ai_engine/v3/test_questionnaire_fact_adapter.py tests/api/v3/test_questionnaire_v3_api.py -q`

Commit:

```text
feat: add reviewed V3 questionnaire and medical manifests
```

---

### Task 4: Information Understanding、Revision 与 Agent 1 Assessment

**Owner:** 钟睿宸；Backend 负责持久化服务。

**Files:**
- Create: `backend/ai_engine/v3/understanding_provider.py`
- Create: `backend/ai_engine/v3/understanding.py`
- Create: `backend/ai_engine/v3/assessment.py`
- Create: `backend/app/models/v3/understanding.py`
- Create: `backend/app/models/v3/assessment.py`
- Create: `backend/app/services/v3/understanding_service.py`
- Create: `backend/app/services/v3/assessment_service.py`
- Create: `backend/app/routers/v3/understanding_router.py`
- Create: `backend/app/routers/v3/assessment_router.py`
- Test: `tests/ai_engine/v3/test_understanding_provider.py`
- Test: `tests/ai_engine/v3/test_assessment_v3.py`
- Test: `tests/api/v3/test_understanding_revision.py`
- Test: `tests/api/v3/test_assessment_revision.py`

**Interfaces:**
- Produces: `UnderstandingProvider.complete_json()`, `run_understanding_v3()`, `build_assessment_v3()`, immutable revision services.
- Consumes: Task 1 Schemas, Task 3 approved Claim/Organ manifests and questionnaire Facts, existing OCR document records.

- [ ] **Step 1: Write failing provider/fallback tests**

Cover Cloud success, timeout, invalid JSON, one schema repair, Local fallback, rule fallback, negation, other-person subject, past time window and no unsupported claims.

- [ ] **Step 2: Implement deterministic Safety before Qwen**

Run the existing Safety detector semantics before ordinary semantic extraction. Merge duplicate signals by source/type without logging text. Qwen unavailability cannot suppress a deterministic Safety signal.

- [ ] **Step 3: Implement Understanding and immutable confirmation**

`confirm_with_changes` keeps logical `fact_id`, inserts new `fact_row_id`, and updates current revision in one transaction. No LLM re-analysis occurs unless new text is supplied with `reprocess_requested=true`.

- [ ] **Step 4: Write failing Agent1 aggregation tests**

Assert one FactEvidence per logical fact per Assessment revision; one Fact can link multiple organs; coverage is independent from source diversity; single question cannot directly determine an organ/tone; insufficient mapping returns `weights=null`.

- [ ] **Step 5: Implement Agent1 and final confirmation**

Merge confirmed Understanding Facts and questionnaire-owned Facts, apply approved Organ Mapping, generate only user-safe `presentation`, and persist full immutable snapshots.

- [ ] **Step 6: Run target tests and commit**

Run: `python -m pytest tests/ai_engine/v3/test_understanding_provider.py tests/ai_engine/v3/test_assessment_v3.py tests/api/v3/test_understanding_revision.py tests/api/v3/test_assessment_revision.py -q`

Commit:

```text
feat: implement V3 understanding and assessment revisions
```

---

### Task 5: Agent 2 RAG + Cloud/Local Qwen Diagnosis

**Owner:** 钟睿宸；肖宇翔审核知识和证型白名单。

**Files:**
- Create: `backend/ai_engine/v3/rag_retriever.py`
- Create: `backend/ai_engine/v3/diagnosis_provider.py`
- Create: `backend/ai_engine/v3/diagnosis.py`
- Create: `backend/app/models/v3/diagnosis.py`
- Create: `backend/app/services/v3/diagnosis_service.py`
- Create: `backend/app/routers/v3/diagnosis_router.py`
- Test: `tests/ai_engine/v3/test_rag_retriever.py`
- Test: `tests/ai_engine/v3/test_diagnosis_provider.py`
- Test: `tests/ai_engine/v3/test_diagnosis_v3.py`
- Test: `tests/api/v3/test_diagnosis_v3_api.py`

**Interfaces:**
- Produces: `RagRetrieverV3.retrieve(RagQuery) -> RagResult`, `DiagnosisProviderV3.complete_json()`, `run_diagnosis_v3()`.
- Consumes: confirmed Assessment revision; approved Knowledge Manifest; Task 1 Diagnosis schemas.

- [ ] **Step 1: Write failing retrieval tests**

Only `approved` chunks with matching manifest/embedding/index versions may enter results. Missing RAG returns a real degraded/abstained path, never fake hits.

- [ ] **Step 2: Write failing provider matrix tests**

Cover Cloud success; 401/403 no same-provider retry; 429/timeout/5xx bounded retry; Local fallback; invalid JSON; one repair; illegal syndrome/evidence/chunk IDs; all candidates removed; Safety withheld.

- [ ] **Step 3: Implement deterministic Query Builder and Retriever**

Query uses claim codes, organ profile and user-safe summary. User document instructions remain data and cannot alter system Prompt. Normal logs contain hashes/versions only.

- [ ] **Step 4: Implement Qwen proposal and local validation**

Execute: Schema validation → syndrome whitelist → Evidence/Chunk ID validation → contradiction check → Medical Rule Check. Qwen cannot create Facts, mappings or knowledge citations.

- [ ] **Step 5: Implement result status union**

`success/degraded` require candidates and `abstained=false`; `abstained` has no candidates; `withheld` is only Safety/upstream-unconfirmed; `failed` is only no valid business/fallback result.

- [ ] **Step 6: Run target tests and commit**

Run: `python -m pytest tests/ai_engine/v3/test_rag_retriever.py tests/ai_engine/v3/test_diagnosis_provider.py tests/ai_engine/v3/test_diagnosis_v3.py tests/api/v3/test_diagnosis_v3_api.py -q`

Commit:

```text
feat: implement grounded V3 diagnosis with Qwen and RAG
```

---

### Task 6: Agent 3 Prescription、Preference Snapshot 与 Agent 4 Provider

**Owner:** 陈家智定义集成 Gate；AI/Backend 分别实现 Agent 3/4。

**Files:**
- Create: `backend/ai_engine/v3/prescription.py`
- Create: `backend/ai_engine/v3/music_provider.py`
- Create: `backend/app/models/v3/music.py`
- Create: `backend/app/services/v3/music_generation_service.py`
- Create: `backend/app/routers/v3/prescription_router.py`
- Create: `backend/app/routers/v3/music_router.py`
- Test: `tests/ai_engine/v3/test_prescription_v3.py`
- Test: `tests/ai_engine/v3/test_music_provider.py`
- Test: `tests/api/v3/test_music_tasks.py`
- Test: `tests/integration/v3/test_v3_music_fallback.py`

**Interfaces:**
- Produces: `build_prescription_v3() -> PrescriptionV3`, `MusicGenerationProvider.submit/poll/cancel`, `MusicGenerationService`.
- Consumes: Diagnosis result, associated confirmed Assessment, UserGoal, immutable Preference Snapshot, provider-neutral GenerationSpec.

- [ ] **Step 1: Write failing four-mode prescription tests**

Assert `syndrome_based`, `candidate_blend`, `emotion_based`, `wellness`; Safety and true no-data withhold; Diagnosis abstain with sufficient safe Assessment produces conservative GenerationSpec.

- [ ] **Step 2: Implement Agent3 without Provider Prompt**

Tone weights use approved medical/fallback mapping only. Preferences may adjust instruments/BPM/duration/ambient within policy but cannot change Tone weights.

- [ ] **Step 3: Write failing Provider/task tests**

Cover synchronous success, asynchronous queued/running/succeeded, timeout, cancel unsupported, invalid audio, Provider failure, matched fallback, idempotent duplicate request and authorized Range stream.

- [ ] **Step 4: Implement provider adapter and local fallback**

Provider-specific Prompt/request exists only inside the adapter. Validate format, duration, checksum and playable status before success. Matched fallback uses `source_type=matched` and cannot claim AI generation.

- [ ] **Step 5: Run target tests and commit**

Run: `python -m pytest tests/ai_engine/v3/test_prescription_v3.py tests/ai_engine/v3/test_music_provider.py tests/api/v3/test_music_tasks.py tests/integration/v3/test_v3_music_fallback.py -q`

Commit:

```text
feat: add V3 prescription modes and music provider fallback
```

---

### Task 7: Agent 5 Preference Closed Loop、Profile、History 与 Favorites

**Owner:** Backend；陈家智验收“反馈真实影响下一次处方”。

**Files:**
- Create: `backend/app/models/v3/feedback.py`
- Create: `backend/app/services/v3/feedback_preference_service.py`
- Create: `backend/app/services/v3/profile_service.py`
- Create: `backend/app/routers/v3/feedback_router.py`
- Create: `backend/app/routers/v3/profile_router.py`
- Test: `tests/api/v3/test_feedback_preference_v3.py`
- Test: `tests/api/v3/test_profile_history_favorites.py`
- Test: `tests/integration/v3/test_preference_closed_loop.py`

**Interfaces:**
- Produces: immutable Preference Versions, `POST /api/v3/feedback`, `/api/v3/me/profile`, history/favorites APIs.
- Consumes: MusicRef, playback authority snapshot, FeedbackV3 and Task6 Prescription preference input.

- [ ] **Step 1: Write failing feedback/idempotency tests**

Assert only `change_label` required; liked/adjustment/comment optional; slower/faster and shorter/longer cannot coexist; duplicate Idempotency-Key cannot increment feedback_count twice.

- [ ] **Step 2: Implement two-stage feedback transaction**

Transaction A saves feedback. Transaction B creates PreferenceEvent + immutable PreferenceVersion and atomically moves current pointer. B failure preserves feedback and returns `applied=false` with idempotent retry.

- [ ] **Step 3: Write failing closed-loop test**

Create at least the contract minimum sample count, assert the next Prescription references the new immutable PreferenceVersion and changes only non-medical music parameters.

- [ ] **Step 4: Implement profile/history/favorites**

History queries `generation_tasks JOIN music_assets`; favorites use unique user/music relation; all endpoints paginate and enforce ownership.

- [ ] **Step 5: Run target tests and commit**

Run: `python -m pytest tests/api/v3/test_feedback_preference_v3.py tests/api/v3/test_profile_history_favorites.py tests/integration/v3/test_preference_closed_loop.py -q`

Commit:

```text
feat: close the V3 feedback personalization loop
```

---

### Task 8: V3 Frontend Flow（不改变 Owner 流程）

**Owner:** 彭翔；陈家智做流程验收。

**Files:**
- Create: `frontend/common/api-v3.js`
- Create: `frontend/common/v3-flow-state.js`
- Create: `frontend/pages/v3-entry/v3-entry.vue`
- Create: `frontend/pages/v3-material/v3-material.vue`
- Create: `frontend/pages/v3-case-summary/v3-case-summary.vue`
- Create: `frontend/pages/v3-expression/v3-expression.vue`
- Create: `frontend/pages/v3-music-goal/v3-music-goal.vue`
- Create: `frontend/pages/v3-questionnaire/v3-questionnaire.vue`
- Create: `frontend/pages/v3-assessment/v3-assessment.vue`
- Create: `frontend/pages/v3-music-basis/v3-music-basis.vue`
- Create: `frontend/pages/v3-generation/v3-generation.vue`
- Create: `frontend/pages/v3-player/v3-player.vue`
- Create: `frontend/pages/v3-feedback/v3-feedback.vue`
- Create: `frontend/pages/v3-profile/v3-profile.vue`
- Modify: `frontend/pages.json`
- Test: `frontend/tests/sprint5-v3-flow.test.mjs`
- Test: `frontend/tests/sprint5-v3-read-model.test.mjs`
- Test: `frontend/tests/sprint5-v3-safety.test.mjs`

**Interfaces:**
- Produces: UI consuming only Frontend Read Models and `api-v3.js`.
- Consumes: Tasks 2-7 `/api/v3` endpoints; no direct Agent internal object.

- [ ] **Step 1: Write failing flow/read-model tests**

Assert existing approved sequence, one final confirmation, music goal maximum two, no SERVER_INTERNAL fields, and Qwen/OCR/ASR unavailable distinctions.

- [ ] **Step 2: Implement guest bootstrap and resumable session**

Store Bearer token securely; never put it in URL/log. All page reloads query server resources by ID/revision rather than rebuilding Agent objects from local storage.

- [ ] **Step 3: Implement input and confirmation pages**

Render case summary, expression, separate music goal and 10-question Schema from backend. Corrections send expected_revision + changes only.

- [ ] **Step 4: Implement safety and music authority gates**

Safety Verification and Safety Support remain distinct. `clear | resolved` may continue; confirmed risk cannot reach personalized music. Frontend never manufactures Prescription when backend withholds.

- [ ] **Step 5: Implement generation/player/feedback/profile pages**

Show indeterminate progress when Provider has none; label matched fallback honestly; use large required feedback change cards; all other feedback remains optional.

- [ ] **Step 6: Run target tests and build**

Run: `cd frontend; node --test tests/sprint5-v3-flow.test.mjs tests/sprint5-v3-read-model.test.mjs tests/sprint5-v3-safety.test.mjs`

Run: `cd frontend; npm run build:h5`
Expected: tests and H5 build pass.

- [ ] **Step 7: Commit**

```text
feat: add HarmonyAI V3 client flow
```

---

### Task 9: Five-Agent Workflow、E2E 与 Degradation Matrix

**Owner:** 陈家智（integration）。

**Files:**
- Create: `backend/ai_engine/v3/workflow.py`
- Create: `backend/app/routers/v3/workflow_router.py`
- Modify: `backend/app/main.py`
- Test: `tests/integration/v3/test_v3_normal_flow.py`
- Test: `tests/integration/v3/test_v3_provider_degradation.py`
- Test: `tests/integration/v3/test_v3_safety_flow.py`
- Test: `tests/integration/v3/test_v3_revision_flow.py`

**Interfaces:**
- Produces: server-authoritative five-Agent orchestration and resumable workflow state.
- Consumes: Tasks 2-8 frozen services and schemas.

- [ ] **Step 1: Write failing normal E2E**

Guest → Session → narrative/questionnaire → confirmed Assessment → Diagnosis → Prescription → generated or matched Music → Feedback → next Preference-aware Prescription.

- [ ] **Step 2: Write failing degradation E2E**

Cover OCR fail, ASR fail, Cloud Qwen fail/Local success, both Qwen fail/rule fallback, RAG fail, Music Provider fail/local match and Diagnosis abstain/conservative music.

- [ ] **Step 3: Write failing Safety/Revision E2E**

Confirmed mental and acute risk cannot enter personalized music; generic confirmation cannot clear Safety; `past_resolved` returns normal track; latest confirmed revision reaches Diagnosis.

- [ ] **Step 4: Implement minimal workflow orchestration**

The workflow only coordinates saved resource refs and statuses. It does not duplicate Agent logic or reconstruct backend objects from frontend payloads.

- [ ] **Step 5: Run integration and targeted regression**

Run: `python -m pytest tests/integration/v3/ -q`

Run: `python -m pytest tests/contract/ tests/api/v3/ tests/ai_engine/v3/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```text
feat: converge HarmonyAI V3 five-agent workflow
```

---

### Task 10: S5 Final Acceptance、Merge Order 与 Sprint Review

**Owner:** 陈家智。

**Files:**
- Create: `docs/sprint5/sprint5-acceptance-report.md`
- Create: `docs/sprint5/sprint5-manual-gates.md`
- Modify: `HANDOFF.md`
- Modify: `project-memory/harmonyai.md`

**Interfaces:**
- Produces: final automated/manual evidence and next-agent checkpoint.
- Consumes: all merged Sprint5 PRs in `integration/sprint4-real-input` or the Owner-approved successor integration branch.

- [ ] **Step 1: Merge in dependency order**

Order: executable Schemas → Auth/Migrations；Medical Manifests parallel；Understanding Provider与Frontend shell可并行准备 → approved Manifests后再接通Assessment/Diagnosis/RAG → Prescription/Music → Feedback/Profile → Frontend convergence → Workflow convergence。Use normal merge commits; do not squash shared implementation history unless Owner explicitly changes policy.

- [ ] **Step 2: Run one final automated gate**

Run Contract + V3 module + integration tests, then one full `python -m pytest tests/ -q`. Run all frontend tests once and H5 build once. Do not repeatedly run the full suite after every small fix.

- [ ] **Step 3: Execute manual gates**

Desktop H5: normal generated path, matched fallback, Diagnosis abstain fallback, Safety mental/acute, revision correction, feedback closed loop. Android and real OCR/music Provider remain explicit `PENDING` until physically tested; never infer PASS from unit tests.

- [ ] **Step 4: Complete acceptance evidence**

Record exact HEAD, commands, counts, Provider configuration, known limits, pending manual gates and rollback point. No clinical efficacy claim; all outcomes are user-reported state or system behavior.

- [ ] **Step 5: Update recoverable handoff and commit**

```text
docs: record Sprint 5 integration and acceptance status
```

Only after Owner review may integration merge to dev. Main/tag/release require a separate explicit Owner decision.

---

## PR / Issue Mapping

| Issue | Planned PR sequence | Start gate |
|---|---|---|
| #76 Owner Contract Freeze | PR #75 + executable Schema PR | Owner双门禁决定 + PR Final Gate |
| #77 Medical Assets | Medical Manifest PR | Contract结构FROZEN；production医学链路仍blocked |
| #78 AI | Understanding Provider foundation → Assessment/Diagnosis/RAG PR | foundation需Contract FROZEN；医学链路需approved manifests |
| #79 Backend | Auth/Migration PR → Music/Feedback platform PR | Contract FROZEN |
| #80 Frontend | V3 flow PR | corresponding APIs stable in integration |
| #81 Owner Integration | Workflow convergence PR → acceptance docs PR | #77-#80 integrated |

## Self-Review

- Spec coverage: all five Agents、Understanding、Auth/Persistence、Frontend、Feedback闭环、Safety、fallback和验收均有独立任务。
- Executable-step scan: every implementation step names its dependency and neighboring interface.
- Type consistency: resource references use ID + revision；Music uses MusicRef；Questionnaire Fact owner uses questionnaire_submission_id；Safety gate consistently accepts only clear/resolved.
- Scope: V2 remains compatible；Sprint5 does not add payment、community、wearables或新 Agent。
