# HarmonyAI Sprint 6 — Baseline Risk Register

> Status: **OPEN REGISTER (Phase 0 baseline)**
> Phase: Sprint 6 Phase 0
> Every risk below is a **known Sprint 5 baseline condition** or a **known Sprint 6 change risk**.
> Owner roles are generic (`Owner`, `Medical`, `AI`, `Backend`, `Frontend`) — assignment to people
> happens in Phase 0 batch planning.
>
> "Phase" = the Sprint 6 phase expected to resolve or first exercise the risk.

---

## R1 — Abstain / wellness fallback fabricates a fixed `gong`

| Field | Content |
|---|---|
| Risk | Every abstained diagnosis is turned into a `wellness` prescription whose tone profile is fabricated as `primary_tone=gong` with weights `{gong: 0.6, others: 0.1}`. The user is shown a single five-tone conclusion that the evidence never supported. |
| Impact | **High — medical-claim integrity.** Users receive a tone "conclusion" derived from no evidence. It also makes the product's most common outcome identical for everyone, destroying personalization. Canonical DB: 15/15 `wellness` prescriptions are `gong`. |
| Phase | Phase 1 (three modes / fallback identity) |
| Owner role | **Owner + Medical** decide the contract; **Backend** implements; **AI** supplies the evidence-based alternatives. |
| Mitigation | Make the fallback produce an explicit non-personalized mode with **no** primary tone; keep the approved deterministic parameters (bpm/duration/instruments) that the diagnosis already produced; add a regression test that asserts an abstained result carries no clinical tone. Distinct from CASE B (genuine `gong`). |
| Evidence | `backend/app/services/v3/prescription_service.py` (`_conservative_wellness_spec`); `docs/sprint6/sprint6-baseline.md` §4 item 1, §4.1 |

## R2 — Near-uniform profile resolved by argmax/tie order into an arbitrary primary tone

| Field | Content |
|---|---|
| Risk | `primary = max(_TONE_CODES, key=(weight, -index))` always yields one tone. With the approved mapping, `gong` and `shang` tie at raw 1.15, so a uniform profile resolves to **`gong`** purely because of tuple order. |
| Impact | **High — product correctness.** "大量结果汇聚为宫" is a structural consequence, not a coincidence. Users with no dominant organ still get a confident single-tone claim. |
| Phase | Phase 1 (mode + tie/mixing rule), with threshold input from **Phase 2** |
| Owner role | **AI** proposes the dominance/ambiguity rule; **Medical** approves the multi-organ semantics; **Owner** fixes the product modes. |
| Mitigation | Introduce an explicit dominance/ambiguity decision: below the margin → `integrated_regulation` with balanced weights and **no** primary tone. Make the tie/mixing rule an explicit, versioned rule-asset decision instead of code tuple order. Cover with CASE D. |
| Evidence | `backend/ai_engine/v3/agent3.py` (`_TONE_CODES`, `_calculate_weights`, `build_tone_profile_v31`); `knowledge/v3/five-tone-mapping-v3.0.json` |

## R3 — Summary edit silently deletes evidence facts (substring retention)

| Field | Content |
|---|---|
| Risk | Re-deriving facts after a user edits the summary keeps only facts whose `display_name` is a **verbatim substring** of the new text. Paraphrasing drops facts; a fully reworded summary can drop all of them, collapsing the organ profile to `insufficient` — which then flows into R1. |
| Impact | **High.** A copy edit can change the medical tone, and can push a user into the fabricated-`gong` path. |
| Phase | Phase 2 (Assessment / questionnaire stability) |
| Owner role | **Backend** implements; **AI** owns the retention rule; **Owner/Medical** approve any user-visible statement about what an edit changes. |
| Mitigation | Make retention explicit and content-independent (or state plainly in the UI what an edit will change). Add a regression test that a paraphrased summary does not silently zero the evidence set. |
| Evidence | `backend/app/services/v3/assessment_service.py` (`confirm_assessment` fact filter), `backend/app/services/v3/understanding_service.py` (edit path) |

## R4 — RAG issues a single oversized query

| Field | Content |
|---|---|
| Risk | One templated sentence containing all organ codes and all claim codes, plus the raw confirmed-state free text appended to the embedding input. No per-organ grouping, no multi-query, no merge/dedupe/rerank. |
| Impact | **High — retrieval recall.** Evidence for a specific organ is diluted by unrelated codes, contributing to the observed 10/20 `empty` rate. |
| Phase | Phase 3 (RAG stability) |
| Owner role | **AI** designs retrieval; **Backend** implements; **Medical** confirms that corpus scope is unchanged. |
| Mitigation | Multi-query per organ/claim → merge → dedupe (optional rerank), keeping the same manifest, threshold semantics and `RagResult` contract. Bound the free-text influence. Replay the gold queries before/after. |
| Evidence | `backend/ai_engine/v3/rag_store.py` (`_query_text`, `query`); `backend/ai_engine/v3/diagnosis_pipeline.py` |

## R5 — Pre-threshold top-K truncation

| Field | Content |
|---|---|
| Risk | `n_results = min(top_k, count)` (top_k = 5) truncates the candidate list **before** the `minimum_score` / `review_status` gate. Ranks 6+ can never rescue an empty result. |
| Impact | **Medium-High — recall ceiling.** With 13 corpus chunks the effective candidate pool is 5, so an `empty` outcome is partly an artifact of ordering rather than of relevance. |
| Phase | Phase 3 (RAG stability) |
| Owner role | **AI** specifies the fix; **Backend** implements; **Medical** reviews any resulting threshold/semantics change. |
| Mitigation | Apply the threshold filter after fetching a candidate pool sized independently of top_k (or filter before truncation), then take top_k from the surviving hits. Add a test that a sub-threshold-only result is still reported `empty`. |
| Evidence | `backend/ai_engine/v3/rag_store.py` (`query`) |

## R6 — Multi-query retrieval latency and embedding cost

| Field | Content |
|---|---|
| Risk | Multi-query multiplies synchronous embedding HTTP calls (one per sub-query, retries enabled), raising acceptance latencies and provider spend; `rag_retrieval_runs.query_hash` has no list semantics. |
| Impact | **Medium.** Slower real-device acceptance and higher cost; audit model may need a canonical list hash or a bumped builder version. |
| Phase | Phase 3 |
| Owner role | **AI + Backend** bound the fan-out and the audit shape; **Owner** accepts latency/cost. |
| Mitigation | Cap the number of sub-queries, reuse the existing store seam (`query_many`) so there is one call site, define merge semantics explicitly, and decide the audit representation before implementation. Measure against the gold set offline first. |
| Evidence | `backend/ai_engine/v3/embedding_provider.py`; `backend/app/models/v3/diagnosis.py` (`rag_retrieval_runs`) |

## R7 — Player may re-create Diagnosis/Prescription on entry

| Field | Content |
|---|---|
| Risk | `v3-player` calls `getMusicBasis()` on load; it is served from the local flow-state cache only when diagnosis + prescription + generation spec are all present. Otherwise it re-issues `POST /diagnoses` + `POST /prescriptions` with a fresh idempotency key, and the failure/duplication is swallowed. |
| Impact | **Medium-High.** Duplicate medical rows and cost from a purely presentational navigation; hard to observe. |
| Phase | Phase 6 (UX flow) — and a defensive fix must land before any new page calls `getMusicBasis()`. |
| Owner role | **Frontend** implements; **Backend** confirms cache-first semantics. |
| Mitigation | Make `getMusicBasis()` cache-first on the prescription id alone, or stop calling it from the player (rendering already tolerates a null basis). Add a request-count assertion test. |
| Evidence | `frontend/common/api-v3.js` (`getMusicBasis`), `frontend/pages/v3-player/v3-player.vue` |

## R8 — Canonical runtime / configuration drift

| Field | Content |
|---|---|
| Risk | Sprint 5 ran against more than one DB/port configuration; `README`/`HANDOFF`/`main.py` still say port 8000 while the accepted run used 8010; the in-repo `DATABASE_URL` default is CWD-relative. |
| Impact | **Medium.** Acceptance evidence becomes incomparable, and results can be produced against the wrong (or an empty) database. |
| Phase | Phase 0 (documented contract) → enforced every phase |
| Owner role | **Owner** owns the contract; **Backend/Frontend** obey it. |
| Mitigation | `docs/sprint6/acceptance-runtime.md` is the single frozen contract: host `127.0.0.1`, acceptance port `8010`, `adb reverse tcp:8010 tcp:8010`, absolute canonical DB, env values outside git, and the rule that `8010` must never be hardcoded into `frontend/common/api-v3.js`. Every acceptance report names its DB path and port. |
| Evidence | `docs/sprint6/acceptance-runtime.md`; `docs/sprint6/sprint6-baseline.md` §2 |

## R9 — Generation provider historical failure rate (3 / 10 in the canonical baseline)

| Field | Content |
|---|---|
| Risk | 3 of 10 generation tasks in the canonical baseline are `failed`. Provider reliability is not yet good enough for a stable listening experience. |
| Impact | **Medium-High — user-visible.** The core "listen to my music" step fails roughly a third of the time in the recorded baseline. |
| Phase | Phase 5 (music/prompt) and Phase 8 (real-device acceptance) |
| Owner role | **AI + Backend** own provider behaviour; **Owner** decides fallback policy. |
| Mitigation | Reduce avoidable prompt-level causes (enum leakage, missing weights, unnormalized ambience) with Prompt Compiler V2; define explicit, honest failure/retry UX; measure the failure rate again on the canonical DB as acceptance evidence. Do not hide failures behind a fake success. |
| Evidence | canonical DB `generation_tasks` = 7 succeeded / 3 failed; `backend/ai_engine/v3/tokenhub_minimax_music_provider.py` |

## R10 — Nullable `primary_tone` will break existing frontend assumptions

| Field | Content |
|---|---|
| Risk | Several layers assume a primary tone always exists. Most notably `frontend/pages/v3-basis/v3-basis.vue` binds `basis.primary_tone.display_name` / `.explanation` **unguarded**, and `frontend/common/api-v3.js` dereferences `spec.tone_profile.primary_tone`. |
| Impact | **High — runtime render failure.** Introducing a permitted `null` tone without hardening these paths crashes the analysis page. |
| Phase | Phase 1 (contract) + Phase 1/6 (frontend hardening) |
| Owner role | **Backend** changes the contract; **Frontend** hardens rendering; **AI** defines the mode semantics. |
| Mitigation | Harden every null-tone path in the same change that makes the field nullable; render an explicit empty/neutral state (the player already does this via `UNKNOWN_TONE_THEME`). Lock with CASE D/E and a frontend test. |
| Evidence | `backend/app/schemas/v3/flow_v31.py` (`ToneProfileV31.primary_tone`, `FiveToneAnalysisReadModel.primary_tone`); `frontend/pages/v3-basis/v3-basis.vue`; `frontend/common/api-v3.js` |

## R11 — Existing Sprint 5 tests pin the old behaviour

| Field | Content |
|---|---|
| Risk | Tests explicitly encode the current fallback/contract: an abstained prescription is asserted to be `primary_tone == "gong"`, `primary_tone` is asserted required by contract tests, and several fixtures embed non-null tone profiles. |
| Impact | **Medium-High.** Sprint 6 changes will produce red tests that look like regressions but are intended behaviour changes; conversely, silently editing them can hide real regressions. |
| Phase | Phase 1 onward (each phase updates the tests it invalidates) |
| Owner role | **Backend/Frontend** update tests; **Owner** approves each behaviour-change justification. |
| Mitigation | For every red test, classify it as *intended change* or *real regression* and cite the corresponding acceptance case (A–H). Rewrite intent-preserving assertions (e.g. "abstained result carries no clinical tone") rather than deleting coverage. Never edit a production schema to match a fixture. |
| Evidence | `tests/api/v3/test_prescription.py` (abstained → `gong`), `tests/contract/v3/test_v31_flow_contract.py` (primary tone required), `tests/ai_engine/v3/test_agent3_v31.py` |

## R12 — `flank_discomfort` wording / claim conflict requires a medical decision

| Field | Content |
|---|---|
| Risk | The approved claim dictionary defines `flank_discomfort` as 「胁肋胀闷不适」 (flank/hypochondriac distension), while the approved questionnaire presents that same claim to users as 「胸口附近有时会觉得闷闷的，想长舒一口气」 (chest-area tightness / wanting to sigh). The two approved assets disagree semantically. |
| Impact | **High — medical-content integrity.** It explains how "胸闷" can map to `flank_discomfort`, and it affects both deterministic questionnaire facts and AI-extracted facts. No prompt or grounding change can be validated while the conflict stands. |
| Phase | Rule Freeze (before Phase 4 grounding work) |
| Owner role | **Medical** decides (reword questionnaire / change claim / add claim / alias mapping); **Owner** records the decision; **Backend/AI** implement. |
| Mitigation | Raise in `rule-freeze-questions.md` Q3 and block prompt/grounding validation on the answer. Do not edit either approved asset before the decision. |
| Evidence | `knowledge/v3/claim-dictionary-v3.0.json` (`flank_discomfort`), `knowledge/v3/questionnaire-v3.0.1.json` (q06 label) |

---

## Register summary

| ID | Risk (short) | Impact | Phase | Owner role(s) |
|---|---|---|---|---|
| R1 | abstain → fixed `gong` | High | 1 | Owner, Medical, Backend |
| R2 | near-uniform argmax → arbitrary tone | High | 1 (thresholds from 2) | AI, Medical, Owner |
| R3 | summary edit substring deletes facts | High | 2 | Backend, AI |
| R4 | RAG single oversized query | High | 3 | AI, Backend |
| R5 | pre-threshold top-K | Medium-High | 3 | AI, Backend |
| R6 | multi-query latency / embedding cost | Medium | 3 | AI, Backend, Owner |
| R7 | player re-creates diagnosis/prescription | Medium-High | 6 | Frontend, Backend |
| R8 | canonical runtime / config drift | Medium | 0 → ongoing | Owner, Backend, Frontend |
| R9 | provider failure 3 / 10 | Medium-High | 5, 8 | AI, Backend, Owner |
| R10 | nullable `primary_tone` breaks frontend | High | 1, 6 | Backend, Frontend |
| R11 | Sprint 5 tests pin old behaviour | Medium-High | 1+ | Backend, Frontend, Owner |
| R12 | `flank_discomfort` claim/wording conflict | High | Rule Freeze | Medical, Owner |
