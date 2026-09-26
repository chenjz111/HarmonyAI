# Sprint 6 Product Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Owner approved — Phase A authorized; Phase B and later remain gated

**Goal:** Restore the Final Owner production flow while preserving Sprint 6 backend, evidence, RAG, generation, presentation and playback authority boundaries.

**Architecture:** The material route becomes a single UI state machine over existing APIs. A visible `v3-generation` page hosts `MusicGenerationFlow`, which owns cross-stage ensure/reuse orchestration for Assessment, Diagnosis, Prescription and Generation Spec, then delegates task identity/create/poll/retry/cancel exclusively to `music-generation-session`. Player is read-only and consumes resolved asset/presentation data through a presentation-only collapsed section. Questionnaire RAG is repaired through medically approved focused queries and corpus coverage, never by bypassing the approval firewall or lowering the threshold first.

**Tech Stack:** Vue/uni-app, JavaScript ES modules, Node test runner, FastAPI, SQLAlchemy, Pydantic, Chroma, pytest.

**Spec:** `docs/product/sprint6-product-recovery-contract.md` and `docs/sprint6/product-recovery-requirements-matrix.md`

## Global Constraints

- Authoritative base is `3f4db5572c075291e430b541505db011bb9fe100` on `feat/s6-personalized-music-stability`.
- No database schema or migration change.
- No frontend medical inference and no new unreviewed medical business field.
- No real Qwen, Embedding, TokenHub or Minimax call in routine development/tests. A G3 embedding index build requires a separate explicit Owner authorization and receipt; every gate requires zero unauthorized provider calls.
- No real generation task and no generated MP3.
- Preserve threshold `0.65 / 0.740741` until a separately approved benchmark changes it.
- Preserve `text-embedding-v4@1024` and versioned index identity.
- Corpus additions and focused domain grouping require Medical Review and Owner approval before runtime integration.
- `MusicGenerationFlow` owns cross-stage ensure/reuse orchestration but is not a generation task state machine.
- `music-generation-session`, `music-presentation` and `player-controller` remain their respective single sources of truth.
- Every merge-blocking PR requirement must be explicitly reported at each merge gate.
- Canonical Owner assets are immutable: material `b0a423f64d7e36cf3f02c17458bb4cac94a595cf233a071e002243694da33770`, player `b7b3bf818ab87c9ea19509640472c1def3bea6648c65912b8e8d5987959a80e1`, feedback `0716cbda5457965b092e57d439138f9901d47620635bdad43c878fd0e5cd6f53` under `docs/product/assets/sprint6-recovery/`.

## Review Focus

- Back navigation or retry during material thinking must not submit a second DocumentSet or confirmation; pinned in Phase B state-transition tests.
- Confirmed summary edits that remove an old fact must remain downstream-authoritative; pinned in Phase C and G regression tests.
- Analysis expansion while audio is playing must preserve context identity, current time and task identity; pinned in Phase E controller-invariant test.
- A mixed 9–11 claim questionnaire must retrieve approved support without admitting false-hit/no-answer chunks; pinned in Phase G acceptance pack.
- Android devices that report zero or non-zero CSS safe-area insets must both keep the custom header visible; pinned in Phase H layout contract and Phase I device matrix.

---

## Architecture impact

### Preserved

```text
Backend Authority → Diagnosis/Prescription → Generation Spec → Prompt Compiler
→ Provider → MusicGenerationFlow → music-generation-session
→ music-presentation → player-controller → UI
```

### Changed orchestration

- `v3-material` owns material-page presentation state only; it does not become a medical engine.
- `v3-generation` is the visible public-safe preparation/generation page.
- `MusicGenerationFlow` ensures or reuses confirmed Assessment, Diagnosis, Prescription and Generation Spec, then creates or reconnects to exactly one `music-generation-session`.
- `music-generation-session` stays limited to task identity, create, poll, retry, cancel, idempotency and page lifecycle. It does not call `getMusicBasis` or own medical preparation.
- `v3-summary` and `v3-basis` leave normal navigation. Their source may remain until route-retirement review, but no normal-flow test may depend on them.
- Any retained `v3-basis` is side-effect-free: no allow-create read, analysis creation or generation action.
- `v3-player` gains only local collapsed/expanded presentation state; it uses read-only endpoints and never creates analysis or generation work.
- RAG query decomposition happens under a versioned approved policy; each focused query retains the same manifest, threshold and approval gates.

### Product Recovery target flow

```text
Confirmed state / optional UserGoal
→ v3-generation (public-safe waiting/retry/cancel)
→ MusicGenerationFlow
   → ensure/reuse confirmed Assessment
   → ensure/reuse Diagnosis
   → ensure/reuse Prescription / Generation Spec
   → delegate task lifecycle to music-generation-session
→ successful playable asset identity + resolved presentation payload
→ read-only Player
```

The old standalone analysis page is not a substitute for `v3-generation`.

## Planned file map

### Documentation and gates

- Create/maintain `docs/product/sprint6-product-recovery-contract.md` — product source of truth.
- Create/maintain `docs/sprint6/product-recovery-requirements-matrix.md` — requirement-to-evidence map.
- Create `docs/sprint6/product-recovery-owner-acceptance.md` — device checklist and evidence record.
- Create `docs/sprint6/product-recovery-baseline-audit.md` — non-blocking `CURRENT_PASS` / `CURRENT_FAIL` baseline.
- Preserve the exact PNG files in `docs/product/assets/sprint6-recovery/` and verify their recorded SHA256 values at every design/Owner gate.
- Create `frontend/tests/sprint6-product-recovery-contract.test.mjs` — cross-route product-contract assertions.

### Frontend

- Create `frontend/common/material-recovery-flow.js` — deterministic material-page UI state/reveal helper, no API ownership.
- Modify `frontend/pages/v3-material/v3-material.vue` — single-page upload/recognition/summary UI.
- Modify `frontend/pages/v3-summary/v3-summary.vue` — remove retention UI and prevent it remaining a conflicting reachable experience.
- Modify `frontend/pages/v3-confirm/v3-confirm.vue` — summary-only confirm/edit and navigation to `v3-generation`.
- Modify `frontend/pages/v3-supplement/v3-supplement.vue` — ensure direct document path reaches optional goal.
- Modify `frontend/pages/v3-goal/v3-goal.vue` — route to confirm or `v3-generation` according to the explicit preceding flow.
- Create `frontend/common/music-generation-flow.js` — cross-stage ensure/reuse orchestration and delegation boundary.
- Create `frontend/pages/v3-generation/v3-generation.vue` — public-safe waiting/cancel/retry page.
- Preserve `frontend/common/music-generation-session.js` as the task-lifecycle-only authority; modify it only for independently proven task-lifecycle defects.
- Modify `frontend/pages/v3-basis/v3-basis.vue` — remove all side effects if retained for compatibility.
- Modify `frontend/pages/v3-player/v3-player.vue` — collapsed analysis and actual-duration-only presentation.
- Modify `frontend/common/music-presentation.js` — content visibility/public-safe presentation helpers.
- Create `frontend/common/v31-page-shell.scss` and modify `frontend/App.vue` / affected pages — unified safe area.
- Modify `frontend/pages.json` only when route retirement is proven by navigation tests.

### Backend/RAG

- Create `knowledge/v3/questionnaire-rag-gold-profiles-v1.json` — medically reviewed positive/negative profiles.
- Create `tests/fixtures/questionnaire-rag-similarity-v1.json` — frozen score matrix with provenance/checksum.
- Create the next approved query-policy asset only after review; do not overwrite `rag-query-policy-v3.2-r1`.
- Create the next approved corpus/manifest/index identity only after review; do not mutate the current release in place.
- Modify `backend/ai_engine/v3/diagnosis_pipeline.py` and `rag_store.py` only for the approved focused-query interface and stable hit merge.
- Modify `backend/app/services/v3/diagnosis_service.py` only for public/audit copy separation and persistence of existing audit fields.

---

## Phase A — Product Contract and Test Freeze

**Goal:** Make the Final Owner Baseline executable before business changes begin.

**Allowed files:** `docs/product/**`, `docs/sprint6/**`, new Product Recovery test files.
**Forbidden files:** application pages, backend runtime code, schema, migrations, provider code.
**Dependencies:** Owner approval of this plan and contract.
**Backend impact:** None.
**Frontend impact:** None.
**RAG/medical impact:** Records frozen facts only.
**Rollback:** Revert planning/test-freeze commit if Owner rejects contract wording; no runtime rollback required.

### Task A1: Freeze contract and matrix

**Files:**
- Create: `docs/product/sprint6-product-recovery-contract.md`
- Create: `docs/sprint6/product-recovery-requirements-matrix.md`
- Create: `docs/sprint6/product-recovery-baseline-audit.md`
- Create: `frontend/tests/sprint6-product-recovery-contract.test.mjs`

**Interfaces:**
- Consumes: Final Owner Baseline, Discovery Report and GAP-09 Addendum.
- Produces: PR-001…PR-031, a non-blocking baseline audit and green assertions only for requirements already satisfied at the authoritative base.

- [ ] Record each PR-001…PR-031 baseline state as `CURRENT_PASS` or `CURRENT_FAIL` in the audit with file/route evidence. This report is non-blocking and is not executable test code.
- [ ] Write green Node assertions only for already-satisfied PR-001, PR-008, PR-019, PR-023, PR-024 and PR-025 invariants.
- [ ] Run `cd frontend && node --test tests/sprint6-product-recovery-contract.test.mjs`; Phase A is mergeable only when the test is green.
- [ ] Review every active Sprint 3–6 flow assertion. For each conflict, change the test intent only in the later implementation phase that supplies the replacement behavior; do not make Phase A falsely green.
- [ ] Validate the matrix contains PR-001 through PR-031 exactly once and every row has automated/manual/merge-blocking entries.
- [ ] Commit only contract, matrix, baseline audit and green contract test with message `docs(product-recovery): freeze owner product contract`.

**Acceptance:** Owner approves contract and design-source priority; known unmet behavior exists only as `CURRENT_FAIL` audit entries, not merged red tests.
**Tests:** Static contract test plus Markdown requirement-ID uniqueness check.
**Rollback criterion:** Any ambiguous requirement, missing design mapping or accidental redefinition of Sprint 6 authority.

### Task A2: Freeze canonical design assets

**Files:**
- Create: `docs/product/assets/sprint6-recovery/HarmonyAI就诊资料智能摘要.png`
- Create: `docs/product/assets/sprint6-recovery/HarmonyAI山水疗愈音乐界面.png`
- Create: `docs/product/assets/sprint6-recovery/HarmonyAI聆听反馈界面(3).png`
- Modify: Product Contract and Requirements Matrix asset registries.

- [ ] Verify the three existing canonical files are byte-identical to the Owner originals; do not replace them with screenshots or re-encoded copies.
- [ ] Run `Get-FileHash -Algorithm SHA256` and require exactly `b0a423f64d7e36cf3f02c17458bb4cac94a595cf233a071e002243694da33770`, `b7b3bf818ab87c9ea19509640472c1def3bea6648c65912b8e8d5987959a80e1`, and `0716cbda5457965b092e57d439138f9901d47620635bdad43c878fd0e5cd6f53` in filename order.
- [ ] Add a green asset-manifest test that checks filename, SHA256 and non-zero file length.
- [ ] Stop before Phase B if any canonical file is missing or any digest differs.

**Acceptance:** All three canonical files exist and both registries contain verified SHA256 values.
**Rollback criterion:** Re-encoded, renamed, missing or checksum-mismatched asset.

---

## Phase B — Single-page Material Flow

**Goal:** Resolve GAP-01/02/03 without changing backend contracts.

**Allowed files:** material page, new material UI helper, material-specific frontend tests, necessary route assertions.
**Forbidden files:** backend, API schema, provider, questionnaire manifest, generation/player modules.
**Dependencies:** Phase A approved.
**Backend impact:** Existing upload, DocumentSet, relevance, case-summary and confirmation calls only.
**Frontend impact:** `v3-material` becomes a deterministic UI state machine.
**RAG/medical impact:** None.
**Rollback:** Revert Phase B commit; old page split remains available until merge.

### Task B1: Material state model

**Files:**
- Create: `frontend/common/material-recovery-flow.js`
- Create: `frontend/tests/sprint6-product-recovery-material-flow.test.mjs`

**Interfaces:**
- Produces: `MATERIAL_PHASES = PICKING|UPLOADING|THINKING|REVEALING|SUMMARY_READY|EDITING|FAILED`; `createMaterialRecoveryFlow({schedule,cancelSchedule,onChange})`; actions `beginUpload`, `documentsReady`, `summaryReady(text)`, `beginEdit`, `cancelEdit`, `reset`, `dispose`.
- The helper owns presentation phases and reveal cursor only; API requests remain in the page.

- [ ] Write tests for legal transitions, duplicate begin suppression, reset/dispose timer cleanup, exact progressive reveal completion, and absence of percentage/provider-stage claims.
- [ ] Write the helper with injected scheduling so tests use fake timers and never invent partial summary content.
- [ ] Cycle optional “正在分析资料内容 / 提取关键信息 / 生成资料摘要” labels only as indeterminate timed presentation under `THINKING`; never map them to server completion, 30%/60% or provider substage state.
- [ ] Run `node --test tests/sprint6-product-recovery-material-flow.test.mjs`; require all pass.

### Task B2: Wire `v3-material`

**Files:**
- Modify: `frontend/pages/v3-material/v3-material.vue`
- Test: `frontend/tests/sprint6-product-recovery-material-wiring.test.mjs`

**Interfaces:**
- Consumes the Task B1 flow and existing `apiV3.uploadDocument`, `createDocumentSet`, `getCaseSummary`, `confirmUnderstanding`.
- Produces no new backend payload or contract.

- [ ] Write failing wiring tests: normal success contains zero `redirectTo/navigateTo` references to `v3-summary`; summary actions are inline; re-upload resets the same page.
- [ ] Replace the three-state page with the Task B1 presentation phases while preserving 1–3 upload ownership and failure route behavior.
- [ ] Fetch the complete backend summary before calling `summaryReady`; progressively reveal only that exact text.
- [ ] Keep confirmation revision/input-revision payloads identical to the existing summary page.
- [ ] Run the material tests and `sprint5-v3-p1-gate-coverage.test.mjs`.
- [ ] Commit with message `feat(product-recovery): unify material recognition and summary flow`.

**Acceptance:** On Android, upload → thinking → summary → confirm/edit/re-upload remains on one route and final text equals the backend read model.
**Rollback criterion:** Duplicate DocumentSet creation, changed confirmation contract, loss of 1–3 file behavior, or invented progress.

---

## Phase C — Summary and Evidence UI Recovery

**Goal:** Resolve GAP-04/05/10 while preserving evidence/provenance internally.

**Allowed files:** material/legacy summary/questionnaire-confirm pages and their frontend tests.
**Forbidden files:** DB/schema/migrations, evidence persistence/service semantics, questionnaire canonical JSON.
**Dependencies:** Phase B for document summary placement.
**Backend impact:** None expected.
**Frontend impact:** Removes end-user retention toggles and duplicate fact list.
**RAG/medical impact:** No evidence deletion; confirmed text remains primary context.
**Rollback:** Revert UI/test commit; internal evidence rows never change.

### Task C1: Remove retention controls

**Files:**
- Modify: `frontend/pages/v3-material/v3-material.vue`
- Modify: `frontend/pages/v3-summary/v3-summary.vue`
- Modify: `frontend/pages/v3-confirm/v3-confirm.vue`
- Modify: `frontend/tests/sprint6-phase2-summary-authority.test.mjs`
- Modify: `frontend/tests/sprint5-v31-summary-authority.test.mjs`
- Create: `frontend/tests/sprint6-product-recovery-summary.test.mjs`

**Interfaces:**
- Confirm submits unchanged decision or full `edited_summary_text`; it submits no user-authored evidence-retention changes.

- [ ] Write failing tests forbidding visible “保留 / 不采用”, evidence toggles and duplicate summary fact lists on both flows.
- [ ] Remove toggle markup, decision state and `buildEvidenceChanges` use from user-facing pages.
- [ ] Preserve confirm and non-empty full-text edit guards, expected revisions and provenance returned by APIs.
- [ ] Replace historical assertions with PR-006/PR-007 comments and exact new behavior.
- [ ] Run summary authority, owner-flow and Product Recovery summary tests.

### Task C2: Downstream confirmed-text regression

**Files:**
- Test: existing backend summary/diagnosis input tests; add a Product Recovery regression file only if no exact case exists.

- [ ] Add a questionnaire case where the original facts include A/B and edited summary removes B; assert diagnosis/retrieval current-state input excludes B while provenance retains it.
- [ ] Add the equivalent document case.
- [ ] Add an unedited case proving canonical structured flow remains unchanged.
- [ ] Run only fake/mock backend tests; assert zero provider calls.
- [ ] Commit Phase C with message `fix(product-recovery): simplify confirmed summary interaction`.

**Acceptance:** Users see one concise summary expression and only confirm/full-text edit/re-upload as applicable.
**Rollback criterion:** Provenance loss, stale fact reactivation, empty-edit guard regression or Contract/schema change.

---

## Phase D — Navigation and Generation Orchestration Recovery

**Goal:** Resolve GAP-06 and PR-009 through the approved visible `v3-generation` transition while preserving orchestration/task/player ownership.

**Allowed files:** supplement/goal/confirm/material navigation, new `music-generation-flow.js`, new `v3-generation` page, basis compatibility source, pages/routes tests.
**Forbidden files:** backend API/schema, provider implementations, player-controller, medical rules, cross-stage preparation inside `music-generation-session`.
**Dependencies:** Phase B/C final confirmation entry points.
**Backend impact:** Existing safe ensure/reuse APIs remain unchanged; `getMusicBasis({allowCreate:true})` may be called only by `MusicGenerationFlow`, never by Player/basis/session.
**Frontend impact:** `v3-generation` presents safe waiting/retry states; `MusicGenerationFlow` orchestrates preparation and delegates task lifecycle.
**RAG/medical impact:** None; only orchestration location changes.
**Rollback:** Revert D commits and restore basis navigation; no server data migration.

### Task D1: Add `MusicGenerationFlow`

**Files:**
- Create: `frontend/common/music-generation-flow.js`
- Create: `frontend/tests/sprint6-product-recovery-music-generation-flow.test.mjs`
- Read-only regression target: `frontend/common/music-generation-session.js`

**Interfaces:**
- `createMusicGenerationFlow({api, createSession, onChange})` consumes `api.ensureMusicBasis(): Promise<BasisReadModel>` plus the existing generation task API adapter.
- `start()` ensures/reuses confirmed Assessment, Diagnosis, Prescription and Generation Spec through `ensureMusicBasis`, then creates/connects to one existing `music-generation-session` and calls its `ensureGeneration()`.
- `retry()` retries failed cross-stage preparation only when no task exists; once a task exists it delegates retry to the session.
- `cancel()`, `onHide()`, `onShow()` and `dispose()` delegate task lifecycle to the session.
- The flow exposes public phases `preparing|generating|playable|failed|cancelled`; queued/running/task identity remain verbatim session snapshots.

- [ ] Write failing tests for preparation ensure/reuse, rapid double start, preparation failure/retry, re-entry with persisted task, dispose during preparation and delegation of task cancel/retry.
- [ ] Implement the flow without duplicating queued/running/poll/request-id state; those values must come only from session snapshots.
- [ ] Assert `music-generation-session.js` contains no `getMusicBasis`, Diagnosis, Prescription or preparation hook.
- [ ] Run the new flow tests plus all existing generation-session and R7 tests.

### Task D2: Add visible `v3-generation`

**Files:**
- Create: `frontend/pages/v3-generation/v3-generation.vue`
- Modify: `frontend/pages.json`
- Create: `frontend/tests/sprint6-product-recovery-generation-page.test.mjs`

- [ ] Write failing tests requiring the registered route, `MusicGenerationFlow` wiring and public-safe states only.
- [ ] Render “正在准备你的音乐”, “正在生成你的音乐……”, queued/running presentation, cancel, and failed/retry.
- [ ] Forbid user-visible strings matching RAG, Diagnosis, Prescription, Provider, Qwen, Minimax, TokenHub or internal stage/error payloads.
- [ ] Navigate to Player only after a successful playable asset identity exists.
- [ ] Map failures through approved public presentation; retain technical codes only in internal state/logging boundaries.

### Task D3: Route both paths through optional goal and generation page

**Files:**
- Modify: `frontend/pages/v3-supplement/v3-supplement.vue`
- Modify: `frontend/pages/v3-goal/v3-goal.vue`
- Modify: `frontend/pages/v3-confirm/v3-confirm.vue`
- Modify: `frontend/pages/v3-material/v3-material.vue`
- Modify/Create: owner-flow and navigation graph tests.

- [ ] Write a two-path navigation matrix asserting document-direct and questionnaire-only both encounter optional goal, then `v3-generation`, and neither enters basis.
- [ ] Pass an explicit non-medical next-step token through goal navigation: questionnaire returns to summary confirmation; already-confirmed document continues to generation.
- [ ] Make final confirmation navigate to `v3-generation`; do not instantiate generation/session logic in summary pages.
- [ ] Remove normal navigation references to `v3-basis`.
- [ ] Run session, owner-flow, route-safety and authority-firewall tests.

### Task D4: Enforce read-only Player and side-effect-free basis

**Files:**
- Modify: `frontend/pages/v3-player/v3-player.vue`
- Modify: `frontend/pages/v3-basis/v3-basis.vue`
- Modify/Create: Player/basis authority tests.

- [ ] Write failing tests proving Player never uses `allowCreate`, generation start, Diagnosis/Prescription create paths or AI/RAG calls.
- [ ] Ensure `MusicGenerationFlow` prepares and persists the resolved asset identity and presentation read model before Player navigation, using existing safe flow-state/read-model storage.
- [ ] Keep Player calls read-only: load resolved music and cached analysis only.
- [ ] If basis remains registered, remove `getMusicBasis({allowCreate:true})`, `createMusicGenerationSession`, start/retry/cancel controls and every medical/generation side effect.
- [ ] Add a direct compatibility-entry test proving basis performs zero write/create/generation requests.
- [ ] Commit Phase D with message `feat(product-recovery): add visible generation orchestration flow`.

**Acceptance:** Both paths traverse optional goal and `v3-generation`, then reach Player without basis; rapid taps create one task; retry keeps idempotency; Player/basis are read-only; only public-safe generation states are visible.
**Rollback criterion:** Duplicate generation state, cross-stage work in the session, direct confirm→Player navigation, basis in normal flow, Player creation side effects, or unauthorized provider use.

---

## Phase E — Player Explanation Recovery

**Goal:** Resolve GAP-07 using existing presentation data and design asset.

**Allowed files:** Player page, music-presentation, player wiring tests.
**Forbidden files:** backend/schema, API fact synthesis, player-controller behavior unless a demonstrated controller defect exists.
**Dependencies:** Phase D supplies Player after generation.
**Backend impact:** None.
**Frontend impact:** Adds local collapsed presentation only.
**RAG/medical impact:** None.
**Rollback:** Revert explanation markup; playback remains unchanged.

### Task E1: Add presentation-only explanation

**Files:**
- Modify: `frontend/pages/v3-player/v3-player.vue`
- Modify: `frontend/common/music-presentation.js` only for view-model visibility fields.
- Modify/Create: `frontend/tests/sprint6-phase6-player-wiring.test.mjs`, `sprint6-product-recovery-player-explanation.test.mjs`

**Interfaces:**
- Consumes existing `buildAnalysisViewModel(basis)` output.
- Local `analysisExpanded: boolean` affects markup only.

- [ ] Write failing tests for default collapsed state and required sections.
- [ ] Add toggle markup matching the Owner mountain-water design direction.
- [ ] Add an invariant test that toggle changes no API call count, task/music reference, controller instance, audio context count, current time or playing state.
- [ ] Render only backend-derived presentation fields; forbid theme facts and page fallbacks.
- [ ] Run player-controller, player wiring and music-presentation tests.
- [ ] Commit with message `feat(product-recovery): move analysis explanation into player`.

**Acceptance:** Android visual comparison in collapsed/expanded states while audio continues uninterrupted.
**Rollback criterion:** Any re-analysis, audio reset, progress reset, invented fact or accessibility regression.

---

## Phase F — Duration and Public Copy Recovery

**Goal:** Resolve GAP-08/11/12.

**Allowed files:** presentation/player/basis compatibility UI, diagnosis public projection and focused tests.
**Forbidden files:** audit record removal, Generation Spec contract, provider prompts, threshold/corpus.
**Dependencies:** Phase E Player layout.
**Backend impact:** Audit reason remains stored; public presentation receives safe copy through existing fields.
**Frontend impact:** Hides recommendation duration and empty sections.
**RAG/medical impact:** No inference change.
**Rollback:** Revert presentation changes; audit persistence is untouched.

### Task F1: Separate duration authorities

- [ ] Write tests proving Generation Spec `duration_seconds` remains available to generation but is absent from user-facing recommendation fields.
- [ ] Remove basis/player “聆听时长/调适时长” summary cells driven by Generation Spec.
- [ ] Keep progress total sourced from measured controller duration, falling back only to verified audio-asset duration.
- [ ] Run duration, presentation and player tests.

### Task F2: Separate audit and public copy

**Files:**
- Modify: `backend/app/services/v3/diagnosis_service.py`
- Modify: `frontend/common/music-presentation.js`
- Modify: `frontend/pages/v3-player/v3-player.vue`
- Test: diagnosis read-model and presentation tests.

- [ ] Write a failing backend test where `RAG_EMPTY` keeps its audit reason code but public presentation contains no “检索证据/医学性暂缓/Agent/RAG” wording.
- [ ] Produce approved neutral public copy through existing presentation fields without changing schema.
- [ ] Add `hasContent` flags in presentation; omit empty state interpretation/rationale/design sections.
- [ ] Run backend diagnosis read-model and frontend presentation suites.
- [ ] Commit with message `fix(product-recovery): separate audit details from public music copy`.

**Acceptance:** No recommended duration, internal audit copy or blank analysis card on device.
**Rollback criterion:** Audit reason loss, public claim invention or actual playback duration regression.

---

## Phase G — Questionnaire RAG Recovery

**Goal:** Resolve GAP-09 without lowering the threshold or inventing medical grouping.

**Allowed files before approval:** proposed Gold profiles, frozen similarity fixture, tests and review documentation.
**Allowed files after approval:** new versioned query-policy/corpus/manifest assets, diagnosis pipeline/RAG store and tests.
**Forbidden files:** overwrite of approved v3.2 policy or v3.1 corpus, schema, migrations, provider adapter, questionnaire canonical JSON.
**Dependencies:** Medical Review and Owner approval between G1 and G2.
**Backend impact:** Approved focused subqueries and stable approved-hit merge.
**Frontend impact:** None beyond public-safe behavior from Phase F.
**RAG/medical impact:** New reviewed assets and versioned index.
**Rollback:** Select the previous policy/corpus/index identity; no DB rollback.

### Task G1: Build the offline acceptance pack

**Files:**
- Create: `knowledge/v3/questionnaire-rag-gold-profiles-v1.json`
- Create: `tests/fixtures/questionnaire-rag-similarity-v1.json`
- Create: `tests/ai_engine/v3/test_questionnaire_rag_recovery.py`
- Create: `docs/sprint6/questionnaire-rag-medical-review.md`

- [ ] Encode positive profiles for anger/liver, appetite/digestion, respiratory, kidney and a 9–11 claim mixed production case.
- [ ] Encode unsupported-only and `gq_14/gq_15/gq_17` negative profiles.
- [ ] Record corpus/query/model/checksum provenance in the fixture; never include real user text.
- [ ] Write green fixture-validation tests for profile identity, labels, checksum provenance and the required positive/negative matrix. Record the current supported-profile empty/dilution result in the non-blocking review document rather than merging a red runtime test.
- [ ] Submit the exact proposed domain groups and any new chunk text for Medical Review and Owner approval; stop G execution if not approved.

### Task G2: Implement approved focused queries

**Interfaces:**
- Add an approved policy-defined `focused_query_groups` projection.
- Each generated `RagQuery` keeps manifest/version/top-k/threshold authority.
- Merge key is `chunk_id`; retain highest score and deterministic query provenance order.

- [ ] Write failing tests that profiles produce distinct focused subqueries while user-confirmed/edited state remains downstream authority.
- [ ] Project structured questionnaire claims into focused retrieval only when they remain active in the confirmed-state projection. A fact removed or contradicted by the confirmed edit remains provenance but is excluded from active subqueries and retrieval evidence.
- [ ] Implement focused query construction exactly from the approved asset; no developer-created grouping constants.
- [ ] Query each focused group through existing threshold and approval gates.
- [ ] Merge/dedupe hits deterministically; reject checksum/version/review mismatches exactly as today.
- [ ] Prove unsupported-only and Gold no-answer profiles remain empty.

### Task G3: Version corpus/index only if approved additions are required

- [ ] Add small, medically reviewed chunks for approved unsupported/boundary domains under a new corpus version.
- [ ] Generate a new checksum-bound manifest without modifying the old files.
- [ ] Obtain a separate explicit Owner authorization naming the G3 embedding index build before any real embedding call.
- [ ] Build a new versioned index using `text-embedding-v4@1024` only in that authorized index-build run, never in routine development or CI.
- [ ] Verify and archive a receipt containing authorization reference, model, dimension, embedding version, manifest checksum, chunk count, collection identity and index checksum.
- [ ] Run the offline acceptance pack, existing 83 RAG contract tests and no-answer false-hit gate.
- [ ] Commit approved assets/code with message `fix(product-recovery): focus questionnaire rag retrieval`.

**Acceptance:** Supported profiles retrieve reviewed hits; mixed profile no longer fails through dilution; negatives remain empty; false-hit metrics do not regress.
**Rollback criterion:** Medical approval missing, threshold changed without separate decision, false hits worsen, unsupported profile becomes non-empty, or provider is needed for routine tests.

---

## Phase H — Android Safe-area

**Goal:** Resolve GAP-13 through one shared shell.

**Allowed files:** shared frontend style/App and V3 custom-nav page classes/tests.
**Forbidden files:** native Android manifest/config unless device evidence proves CSS cannot solve it; backend.
**Dependencies:** Stable pages from B–F.
**Backend/RAG impact:** None.
**Rollback:** Revert shared shell and page imports.

### Task H1: Shared safe-area shell

**Files:**
- Create: `frontend/common/v31-page-shell.scss`
- Modify: `frontend/App.vue`
- Modify: V3 custom-nav pages to use the shared shell and remove conflicting top magic padding.
- Create: `frontend/tests/sprint6-product-recovery-safe-area.test.mjs`

- [ ] Write a source contract requiring every registered V3 `navigationStyle: custom` page to use the shared shell.
- [ ] Define top padding using `env(safe-area-inset-top)` with a non-overlapping zero-inset fallback and shared bottom handling.
- [ ] Remove duplicated/conflicting per-page safe-area rules only after visual comparison.
- [ ] Build H5 and inspect 320/360/390/430 widths with zero/non-zero inset fixtures.
- [ ] Commit with message `fix(product-recovery): unify v3 safe-area layout`.

**Acceptance:** Android status bar never covers header/action content across the device matrix.
**Rollback criterion:** Header jumps, double inset, horizontal overflow or tabBar regression.

---

## Phase I — Product Acceptance Gate

**Goal:** Make engineering and Owner real-device acceptance jointly mandatory.

**Allowed files:** tests, acceptance docs and non-provider gate scripts.
**Forbidden files:** business behavior changes during gate execution.
**Dependencies:** A–H merged into the recovery integration branch.
**Backend/frontend/RAG impact:** Verification only.
**Rollback:** Any gate failure returns the owning phase; do not waive it through a test edit.

### Task I1: Engineering gate

- [ ] Run Product Recovery focused frontend tests.
- [ ] Run all frontend tests.
- [ ] Run approved backend assessment/diagnosis/RAG tests with fake providers.
- [ ] Run H5 build and `git diff --check`.
- [ ] Verify no unauthorized real provider call, generation task or MP3 occurred. If an authorized G3 build exists, verify its receipt separately and exclude it from routine-CI call counts.
- [ ] Emit PR-001…PR-031 status; any non-PASS merge-blocking row blocks readiness.

### Task I2: Owner real-device gate

**Files:**
- Create: `docs/sprint6/product-recovery-owner-acceptance.md`

- [ ] Record Android device/build/base SHA and API runtime identity.
- [ ] Execute with-document upload → thinking → progressive summary → confirm/edit/re-upload checks.
- [ ] Execute document-direct and document+questionnaire flows, including optional goal.
- [ ] Execute questionnaire-only Q1–Q10 → goal → summary edit → generation → Player.
- [ ] Verify no normal-flow basis page and no retention controls.
- [ ] Verify collapsed/expanded explanation without playback/task reset.
- [ ] Verify actual duration only, public-safe copy, no empty cards and safe area.
- [ ] Verify Feedback Q1 validation, Q1-only submit and skip.
- [ ] Owner signs PASS for every required manual matrix row.

**Acceptance:** Engineering Acceptance PASS plus Owner Real-device Product Acceptance PASS.
**Rollback criterion:** Any mismatch with a design PNG, any merge-blocking requirement not exercised, or any Phase 6 authority regression.

---

## Team ownership recommendation

| Lane | Recommended owner | Review authority |
|---|---|---|
| Product Contract / matrix | Integration owner | Owner |
| Material single-page flow | Frontend flow owner | Owner design + integration |
| Summary UI | Frontend + Summary Authority owner | Integration |
| Generation orchestration | MusicGenerationFlow + session owner | Architecture reviewer |
| Player explanation/copy | Presentation + Player owners | Owner design |
| RAG profiles/corpus | AI engineer + Medical Knowledge Engineer | Medical Review + Owner |
| Safe area | Frontend device UX owner | Android Owner acceptance |
| Final gate | QA/integration owner | Owner |

No contributor may modify another lane’s authority module without that owner’s review.

## Integration order

1. Phase A contract/test freeze.
2. Phase B material flow.
3. Phase C summary cleanup.
4. Phase D orchestration/navigation.
5. Phase E Player explanation.
6. Phase F duration/public copy.
7. Phase G only after Medical Review approval; G1 before G2/G3.
8. Phase H after final page structure stabilizes.
9. Phase I engineering gate, then Owner device gate.

Stop immediately after any true regression; do not continue cherry-picking later phases.

## PR strategy

- One reviewed PR per Phase A–H; Phase G uses separate G1 asset-review and G2/G3 runtime PRs.
- Every PR targets a dedicated Product Recovery integration branch based on `3f4db5572c075291e430b541505db011bb9fe100`.
- Every PR description lists Requirement IDs, changed routes, provider-call count and exact tests.
- Normal merge commits preserve phase identity; no squash/rebase/amend/force push after approval.
- Old tests may change only when the PR implements the replacement Requirement ID.
- Final integration PR cannot become Ready until all merge-blocking matrix rows have engineering evidence; it cannot merge until required Owner device evidence is attached.

## Merge Gate

Required before each phase merge:

1. Source/base/HEAD identity and clean diff.
2. Ownership and forbidden-file audit.
3. Focused tests plus directly affected regressions.
4. Full frontend/backend scope-appropriate gate.
5. H5 build for frontend phases.
6. `git diff --check`.
7. Zero unauthorized real Qwen/Embedding/Music provider calls and zero generated MP3; any authorized G3 embedding build has a separate Owner authorization and receipt.
8. Requirement-by-requirement status for the PR’s IDs.
9. Medical/Owner approval artifacts where required.

## Owner Real-device Gate

The final release remains blocked until the Owner verifies the three recovered design experiences on Android. CI success, code review, mergeability and build success are necessary but not sufficient. A failure is returned to the phase that owns the Requirement ID; tests must not be weakened to accept the observed incorrect behavior.

## Self-review record

- **Spec coverage:** PR-001…PR-031 map to Phases A–I; all requested PR-001…PR-021 and review-added PR-029…PR-031 are present.
- **Architecture consistency:** No second generation/player state machine, no frontend medical inference, no threshold-first fix.
- **Type consistency:** Cross-stage orchestration is isolated in `createMusicGenerationFlow`; `music-generation-session` retains its existing task-lifecycle interface.
- **Review focus:** All five high-risk conditions have an owning test task.
- **Placeholder scan:** No deferred implementation placeholder is used; medically contingent work has an explicit approval stop gate rather than an unspecified task.
