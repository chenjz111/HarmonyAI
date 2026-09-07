# Sprint 5 V3.1 Real Provider Chain Implementation Plan

> **For agentic workers:** Execute this plan inline in the current worktree. Do not modify frozen contracts, formal questionnaire assets, Teacher Flow, or the persistence/session implementation owned by #104/#105.

**Goal:** Make the AI-owned V3.1 Provider path executable from an authorized `ConfirmedUserState` snapshot through DashScope Embedding, versioned Chroma retrieval, Qwen structured output, deterministic validation, and honest failure states.

**Architecture:** Keep `ConfirmedUserState`, DocumentSet, Relevance, Assessment, Diagnosis, and persistence ownership outside the AI module. Add a secret-free DashScope environment resolver and a real-mode dependency factory that loads only an approved corpus manifest/chunk file, constructs the existing Embedding/Chroma/Qwen adapters, and passes them into the existing provider-neutral pipeline. Preserve V3.0 factories and demo behavior separately.

**Tech Stack:** Python 3, Pydantic, urllib HTTP transport, Chroma client, pytest, existing V3 diagnosis schemas and validation pipeline.

**Spec:** `docs/superpowers/specs/2026-09-06-sprint5-ai-final-closeout-design.md` plus the approved chat design for DashScope environment mapping.

## Global Constraints

- Real mode requires `HARMONYAI_REAL_AGENTS=true`, `DASHSCOPE_API_KEY`, and `DASHSCOPE_WORKSPACE_ID`; values never appear in source, tests, logs, snapshots, or GitHub text.
- Embedding identity is exactly `text-embedding-v4` with dense dimension `1024`; hash embedding and demo chunks are never production inputs.
- Qwen model and corpus manifest/chunk paths are explicit configuration; missing values fail readiness and never select Mock.
- Chroma collection identity includes knowledge version, embedding version, dimension, and manifest checksum.
- RAG empty results abstain; provider/network/configuration errors become explicit failed/degraded states; invalid structured output is repaired at most once and then rejected.
- UserGoal remains outside Agent1/Agent2 medical input; only an approved Agent3 parameter rule may consume it.
- No modification to `backend/app/schemas/v3/flow_v31.py`, `knowledge/v3/questionnaire-v3.0.1.json`, Teacher Flow, #104/#105 persistence, or migrations.

---

### Task 1: Add DashScope configuration and request-header adaptation

**Files:**
- Modify: `backend/ai_engine/v3/provider_config.py`
- Modify: `backend/ai_engine/v3/embedding_provider.py`
- Modify: `backend/ai_engine/v3/diagnosis_provider.py`
- Modify: `backend/ai_engine/providers.py`
- Modify: `backend/app/core/agent_config.py`
- Test: `tests/ai_engine/v3/test_v31_provider_config.py`
- Test: `tests/ai_engine/v3/test_embedding_provider.py`
- Test: `tests/ai_engine/v3/test_diagnosis_provider_v31.py`

**Interfaces:**
- `DASHSCOPE_API_KEY` authenticates both V3.1 Provider adapters.
- `DASHSCOPE_WORKSPACE_ID` becomes the DashScope workspace header without being exposed by diagnostics.
- Existing explicit `EMBEDDING_*`/`QWEN_*` overrides remain available only when they resolve to the same approved V3.1 identity; Real readiness still requires the DashScope credentials.

- [x] Write failing tests for missing DashScope credentials, exact model/dimension, workspace header propagation, and secret-free readiness output.
- [x] Run the focused tests and observe the expected failures.
- [x] Implement the resolver and optional extra-header transport support without changing V3.0 behavior.
- [x] Run the focused tests and confirm no credential value is returned or logged.

### Task 2: Load and ingest the approved corpus through Chroma

**Files:**
- Modify: `backend/ai_engine/v3/rag_ingestion.py`
- Modify: `backend/app/core/agent_config.py`
- Modify: `backend/ai_engine/v3/rag_store.py`
- Test: `tests/ai_engine/v3/test_rag_ingestion_v31.py`
- Test: `tests/ai_engine/v3/test_rag_store_v31.py`
- Test: `tests/ai_engine/v3/test_v31_provider_config.py`

**Interfaces:**
- Add a loader that reads configured manifest/chunk JSON files, validates `review_status`, checksum, model/version, and count, then calls `VersionedRagStore.ingest()`.
- The factory must reject absent or invalid files with a typed readiness failure and must never call `load_demo_chunks()`.

- [x] Write failing tests for absent paths, malformed corpus, unapproved rows, successful approved fixture ingestion, Top-K filtering, and empty retrieval.
- [x] Run the tests and observe the expected failures.
- [x] Implement file loading and factory ingestion using existing `KnowledgeChunk`, `IngestionManifest`, and `VersionedRagStore` types.
- [x] Run RAG tests and verify exact source/chunk references and no demo fallback.

### Task 3: Make the Qwen structured adapter and pipeline failure semantics executable

**Files:**
- Modify: `backend/ai_engine/v3/diagnosis_provider.py`
- Modify: `backend/ai_engine/v3/diagnosis_pipeline.py`
- Modify: `backend/ai_engine/v3/v31_pipeline.py`
- Test: `tests/ai_engine/v3/test_diagnosis_provider_v31.py`
- Test: `tests/ai_engine/v3/test_diagnosis_pipeline_v31.py`
- Test: `tests/ai_engine/v3/test_v31_pipeline.py`

**Interfaces:**
- Qwen receives only the sanitized diagnosis request, Fact IDs, and approved RAG Chunk IDs.
- `execute_v31_ai_pipeline()` remains the orchestration seam and returns explicit success/degraded/abstained outcomes without creating persistence records.

- [x] Write failing tests for Qwen success, one JSON repair, schema failure, timeout/auth failure, empty RAG abstention, and no-config readiness failure.
- [x] Run the tests and observe the expected failures.
- [x] Wire the resolved DashScope Qwen provider into the existing validator and preserve the current medical-reference whitelist.
- [x] Run provider and pipeline tests, including privacy assertions against prompts and raw user text.

### Task 4: Add mock E2E and owner-run Real Smoke harness

**Files:**
- Create: `tests/integration/test_s5_v31_real_provider_chain.py`
- Modify: `tests/integration/test_s5_v31_ai_closeout.py`
- Modify: `docs/sprint5/s5-v3.1-ai-109-closeout.md`

- [x] Write failing E2E tests for authorized state → embedding → Chroma → Qwen → validation and each failure path.
- [x] Implement deterministic fake transport/client/provider fixtures that cannot be mistaken for Real evidence.
- [x] Run the Mock E2E suite and the V3.0 compatibility suite.
- [x] Add a non-secret owner-run Smoke command/documentation that reports `NOT_REAL_VALIDATED` until credentials and approved corpus are supplied.

### Task 5: Final verification and original PR handoff

**Files:**
- Verify: all changed files on `codex/s5-final-ai-109`

- [x] Run the full required pytest set, backend compile, `git diff --check`, and a secret/raw-input scan.
- [x] Verify the exact commit and remote branch before pushing.
- [x] Push only the original PR branch; do not create or merge another PR.
- [x] Report tests, CI, Real Smoke status, and remaining #104/#105/#108 dependencies without claiming production validation prematurely.
