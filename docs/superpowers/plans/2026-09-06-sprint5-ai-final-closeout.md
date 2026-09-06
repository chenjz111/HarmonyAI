# Sprint 5 V3.1 AI Final Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and validate the AI-owned V3.1 closeout path from confirmed state through production-ready Embedding/Chroma/Qwen Agent2 validation and deterministic Agent3 output without changing the frozen contract.

**Architecture:** Add narrow AI-engine modules behind the existing V3 schemas and Qwen transport. Keep medical decision authority in approved manifests and deterministic rule assets; Qwen proposes only schema-bound candidates, and Agent3 emits a provider-neutral music specification plus the frozen public read model. Production RAG remains gated until #108 supplies Owner-approved chunk data and ingestion metadata.

**Tech Stack:** Python 3, Pydantic V3 schemas, SQLAlchemy V3 audit models, Chroma, HTTP-compatible Embedding and Qwen Providers, pytest, FastAPI integration tests.

**Spec:** `docs/superpowers/specs/2026-09-06-sprint5-ai-final-closeout-design.md`

## Global Constraints

- Base is `origin/integration/sprint4-real-input@83fe2f4` and the frozen V3.1 contract remains unchanged.
- Use only Owner-approved medical assets; do not invent syndrome whitelist entries, RAG chunks, or medical thresholds.
- Production Embedding is `text-embedding-v4`, dense 1024 dimensions; never use `hash-v1` as a production index.
- `HARMONYAI_REAL_AGENTS=true` must be explicit in production; missing real configuration is a readiness/provider failure.
- UserGoal is preference-only and never enters Agent1/Agent2 medical evidence or tone mapping.
- Public output is limited to `FiveToneAnalysisReadModel`; never expose provider, prompt, raw RAG, model, or private reasoning fields.
- Preserve V3.0 compatibility and do not modify DocumentSet/Relevance/ConfirmedUserState persistence ownership or add migrations.
- Every production-code change follows a failing-test-first red/green cycle.

### Task 1: Lock AI closeout boundaries and provider configuration

**Files:**
- Create: `backend/ai_engine/v3/embedding_provider.py`
- Create: `backend/ai_engine/v3/provider_config.py`
- Modify: `backend/app/core/agent_config.py`
- Test: `tests/ai_engine/v3/test_embedding_provider.py`
- Test: `tests/ai_engine/v3/test_v31_provider_config.py`

**Interfaces:**
- Consumes: environment mapping and the existing JSON/HTTP provider conventions.
- Produces: `EmbeddingProvider.embed(text, input_type) -> list[float]`, `AsyncEmbeddingProvider.aembed(text, input_type) -> list[float]`, and `V31ProviderConfig.from_environment(environment) -> V31ProviderConfig`.

- [ ] **Step 1: Write the failing tests** for a 1024-dimensional query/document request, invalid dimensions, missing production variables, explicit test mode, and secret-free diagnostic output.
- [ ] **Step 2: Run the tests to verify the expected failures** with `pytest tests/ai_engine/v3/test_embedding_provider.py tests/ai_engine/v3/test_v31_provider_config.py -q`.
- [ ] **Step 3: Implement the smallest typed embedding adapter** using the approved environment names, distinguish `input_type=query` from `input_type=document`, enforce the configured dimension, and map timeout/auth/rate-limit/invalid-response errors to stable safe failures.
- [ ] **Step 4: Run the targeted tests** and confirm all pass without printing credentials.
- [ ] **Step 5: Commit** with `git add backend/ai_engine/v3 backend/app/core/agent_config.py tests/ai_engine/v3` and `git commit -m "feat(v3.1): add production embedding boundary"`.

### Task 2: Build versioned approved-corpus ingestion and retrieval

**Files:**
- Create: `backend/ai_engine/v3/rag_store.py`
- Create: `backend/ai_engine/v3/rag_ingestion.py`
- Modify: `backend/ai_engine/chroma_store.py`
- Modify: `backend/app/services/v3/knowledge_assets.py`
- Test: `tests/ai_engine/v3/test_rag_store_v31.py`
- Test: `tests/ai_engine/v3/test_rag_ingestion_v31.py`

**Interfaces:**
- Consumes: `KnowledgeChunk`, `IngestionManifest`, `RagHit`, `RagResult`, the Embedding Provider, and the approved #108 corpus payload when released.
- Produces: `VersionedRagStore.ingest(manifest, chunks)`, `VersionedRagStore.query(query, embedding) -> RagResult`, and `validate_production_corpus(manifest, chunks)`.

- [ ] **Step 1: Write failing tests** for collection identity including corpus/model/dimension, approved-status filtering, exact manifest/checksum matching, query/document embedding type, top-k/minimum-score behavior, empty retrieval, stale-index rejection, and `hash-v1` production rejection.
- [ ] **Step 2: Run the RAG tests** and verify they fail because the versioned store and ingestion gate do not yet exist.
- [ ] **Step 3: Implement manifest and chunk validation** without adding medical content. Reject the current #108 pending-production registry for production ingestion, while allowing explicit test fixtures through a test-only path.
- [ ] **Step 4: Implement the Chroma adapter** with injected embeddings, persistent collection names scoped by manifest identity, approved metadata, source/chunk checksums, and safe failure states.
- [ ] **Step 5: Run targeted RAG tests** and verify they pass; ensure existing Chroma demo tests retain their V3/V2 behavior and are not treated as production validation.
- [ ] **Step 6: Commit** with `git add backend/ai_engine/v3 backend/ai_engine/chroma_store.py backend/app/services/v3/knowledge_assets.py tests/ai_engine/v3` and `git commit -m "feat(v3.1): add versioned approved rag store"`.

### Task 3: Implement deterministic Agent2 query and Qwen validation pipeline

**Files:**
- Create: `backend/ai_engine/v3/diagnosis_pipeline.py`
- Create: `backend/ai_engine/v3/diagnosis_provider.py`
- Modify: `backend/app/services/v3/diagnosis_service.py`
- Modify: `backend/app/routers/v3/diagnosis_router.py`
- Test: `tests/ai_engine/v3/test_diagnosis_pipeline_v31.py`
- Test: `tests/ai_engine/v3/test_diagnosis_provider_v31.py`
- Test: `tests/api/v3/test_diagnosis_v31_real_path.py`

**Interfaces:**
- Consumes: confirmed Assessment/ConfirmedUserState snapshot, `RagStore`, `AsyncJsonProvider`, approved syndrome whitelist and mapping assets, and existing diagnosis schemas.
- Produces: `build_diagnosis_query(snapshot) -> RagQuery`, `run_diagnosis_provider(request, rag_result) -> DiagnosisProviderResponse`, and `run_diagnosis(...) -> DiagnosisV3` with existing idempotency and ownership semantics.

- [ ] **Step 1: Write failing tests** for query determinism, approved claim filtering, supporting/contradicting Fact IDs, valid RAG-grounded Qwen candidates, unknown syndrome/Fact/Chunk rejection, duplicate evidence, schema repair once, timeout/rate-limit/auth failures, empty RAG, insufficient evidence abstention, and unavailable-medical-asset behavior.
- [ ] **Step 2: Run the targeted tests** and capture the expected failures before adding production pipeline code.
- [ ] **Step 3: Implement the pure Query Builder** with a version string and canonical hash; do not derive new medical claims or accept client-supplied medical arrays as authority.
- [ ] **Step 4: Implement Qwen Agent2 adapter** by reusing the existing typed provider retry/repair conventions, sending only structured validated data, and validating the response against schema, whitelist, reference identity, evidence direction, version, and medical rules.
- [ ] **Step 5: Wire the pipeline into the existing V3 diagnosis service** while preserving owner/session/revision gates, concurrent idempotency replay/conflict behavior, and `MEDICAL_ASSET_UNAVAILABLE`/abstain semantics.
- [ ] **Step 6: Run targeted AI and API tests** and confirm no user source text appears in ordinary logs or persisted provider metadata.
- [ ] **Step 7: Commit** with `git add backend/ai_engine/v3 backend/app/services/v3/diagnosis_service.py backend/app/routers/v3/diagnosis_router.py tests/ai_engine/v3 tests/api/v3` and `git commit -m "feat(v3.1): ground agent2 diagnosis in approved rag"`.

### Task 4: Implement deterministic Agent3 ToneProfile and public read model

**Files:**
- Create: `backend/ai_engine/v3/agent3.py`
- Create: `backend/ai_engine/v3/safe_expression.py`
- Test: `tests/ai_engine/v3/test_agent3_v31.py`
- Test: `tests/ai_engine/v3/test_safe_expression_v31.py`

**Interfaces:**
- Consumes: validated DiagnosisV3, confirmed state, approved `five-tone-mapping-v3.0.json`, safe-expression rules, optional UserGoal preference, and frozen V3.1 read-model schemas.
- Produces: `build_tone_profile_v31(diagnosis, confirmed_state, rules) -> ToneProfileV31`, `build_generation_spec_v31(...) -> GenerationSpec`, and `build_five_tone_read_model(...) -> FiveToneAnalysisReadModel`.

- [ ] **Step 1: Write failing tests** for five weights summing within tolerance, primary maximum, nullable distinct secondary, diagnosis abstention, no UserGoal medical influence, preference-only parameter adjustment, approved evidence references, required explanations, and forbidden provider/raw-RAG/medical-claim text.
- [ ] **Step 2: Run Agent3 tests** and verify the new functions fail for the expected missing implementation reasons.
- [ ] **Step 3: Implement deterministic mapping** from validated evidence and approved tone rules; use no hard-coded syndrome whitelist and emit no secondary tone until its approved threshold asset is available.
- [ ] **Step 4: Implement provider-neutral GenerationSpec and public read-model assembly** with safe-expression validation and no internal fields.
- [ ] **Step 5: Run targeted Agent3 tests** and then the existing V3 schema/compatibility tests.
- [ ] **Step 6: Commit** with `git add backend/ai_engine/v3 tests/ai_engine/v3` and `git commit -m "feat(v3.1): add deterministic agent3 read model"`.

### Task 5: Add integration evidence, real-mode gates, and closeout documentation

**Files:**
- Modify: `docs/sprint5/s5-v3.1-provider-decision-final.md` only if the recorded implementation status needs a factual update
- Create: `docs/sprint5/s5-v3.1-ai-109-closeout.md`
- Test: `tests/integration/test_s5_v31_ai_closeout.py`

**Interfaces:**
- Consumes: Tasks 1–4, #108 approved corpus output, backend #104/#105 interfaces, and real provider environment when available.
- Produces: an evidence report distinguishing `REAL_VALIDATED`, `MIXED/DEGRADED`, and `NOT_REAL_VALIDATED`.

- [ ] **Step 1: Write failing integration tests** for document-only, document-plus-questionnaire, questionnaire-only, RAG empty/degraded, Qwen failure, diagnosis abstention, Agent3 read-model success, and V3.0 compatibility.
- [ ] **Step 2: Run the integration tests** and verify they fail only where required upstream assets or provider configuration are absent, with stable explicit errors.
- [ ] **Step 3: Add the narrow integration harness** using injected providers and approved fixture metadata; do not copy #108/#110 persistence code.
- [ ] **Step 4: Run the full required verification set:** `pytest tests/api/v3 tests/contract/v3 tests/ai_engine/v3 tests/integration/test_s5_v31_ai_closeout.py -q`, backend compile, `git diff --check`, and secret/raw-input scans.
- [ ] **Step 5: Run real smoke tests** only when approved corpus, credentials, and deployment configuration are available; record exact provider/model/index metadata without secrets.
- [ ] **Step 6: Write the closeout report** with changed files, tests, mode label, remaining upstream blockers, and explicit non-claims.
- [ ] **Step 7: Commit** with `git add docs/sprint5 tests/integration` and `git commit -m "docs(s5): record ai final closeout evidence"`.

### Task 6: Publish the AI Draft PR for review

**Files:**
- Verify: all files changed by the #109 commits

**Interfaces:**
- Consumes: the clean #109 branch and verification report.
- Produces: one Draft PR against `integration/sprint4-real-input`; no merge.

- [ ] **Step 1: Verify scope** with `git status --short`, `git diff --stat origin/integration/sprint4-real-input...HEAD`, and a changed-file allowlist review.
- [ ] **Step 2: Run the final verification commands** again at the exact HEAD that will be pushed.
- [ ] **Step 3: Push only `codex/s5-final-ai-109`** and create one Draft PR with the true mode label and dependency notes.
- [ ] **Step 4: Report** the PR URL, commit SHA, changed-file count, targeted/contract/full test results, `git diff --check`, CI status, and unresolved #108/#110 dependencies.
