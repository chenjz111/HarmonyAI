# HarmonyAI Sprint 6 — Baseline & Guardrails (Phase 0)

> Status: **FROZEN BASELINE (BEFORE state)**
> Phase: Sprint 6 Phase 0 — Baseline & Guardrails
> Scope: baseline record + acceptance guardrails only. **No Sprint 6 product behaviour is implemented in this phase.**
> This document records what the system **is**, not what Sprint 6 will make it.

---

## 1. Git baseline

| Item | Value |
|---|---|
| Sprint 5 closeout tip | `ebeeaa7254c9888e56cdeaafefd7e903734997da` |
| Sprint 6 branch | `feat/s6-personalized-music-stability` |
| Branch base | the Sprint 5 closeout tip above (branch created from it, verified equal) |
| Sprint 5 branch (archived) | `test/s5-v3.1-final-acceptance` @ `ebeeaa7` (pushed to `origin`, upstream set) |

Sprint 5 closeout consists of four commits on top of `6297c8b`:

| SHA | Message |
|---|---|
| `d2c1fa7b16d6923695c78fe7ab9a08c2e28633ef` | `chore(repo): ignore runtime uploads and generated media` |
| `52e4b6ea67f1862415ccf9dd6a0340cc1b4b134a` | `fix(v31): restore AI fact extraction and fact persistence ordering` |
| `bbf6f953e6d25676c3d74413e62d1fa31a894449` | `fix(v31): preserve diagnosis goal and abstained prescription parameters` |
| `ebeeaa7254c9888e56cdeaafefd7e903734997da` | `fix(v31): make player and basis tone authority explicit` |

---

## 2. Canonical acceptance DB

```
C:\Users\ASUS\HarmonyAI-acceptance-runtime\final-e2e.db
```

**This is the canonical acceptance DB designated by the Owner starting from Sprint 6.**

It is **not** a claim that every historical Sprint 5 acceptance run necessarily used this DB.
Phase -1A found that Sprint 5 ran against more than one configuration (an earlier
`acceptance.env` pointed at the repo-relative `./harmonyai.db`). That history is recorded as
*unresolved for the past* and *resolved from Sprint 6 forward*:

- Sprint 6 canonical baseline DB = `final-e2e.db` (above).
- All future Sprint 6 acceptance evidence must state which DB it was produced from.

---

## 3. Baseline counts (re-read read-only at Phase 0)

Source: `C:\Users\ASUS\HarmonyAI-acceptance-runtime\final-e2e.db`, opened strictly read-only
(`sqlite3` URI `mode=ro`). Nothing was written, migrated or reindexed.

| Fact | Value |
|---|---|
| mtime | `2026-09-15 22:53:37` |
| size | `3,162,112` bytes |

| Table | Count | Breakdown |
|---|---|---|
| `diagnosis_runs` | **25** | `abstained` 15 / `success` 10 |
| `rag_retrieval_runs` | **20** | `empty` 10 / `success` 10 |
| `rag_retrieval_hits` | **12** | (only the 10 successful runs produced hits) |
| `prescription_v3` | **25** | `wellness` 15 / `syndrome_based` 10 |
| `generation_tasks` | **10** | `succeeded` 7 / `failed` 3 |
| `music_assets` | **7** | all `source_type=generated`, `playable_status=ready` |
| `favorites` | **0** | no favorites exist yet |
| `feedback_v3` | **4** | — |

These values match the reference recorded in Phase -1A and the Owner notice, and the DB has
**not changed** since (identical counts and mtime). No DB modification was performed.

### 3.1 Reference values (for comparison)

| Metric | Reference | Observed | Match |
|---|---|---|---|
| `diagnosis_runs` | 25 = 15 abstained + 10 success | same | ✅ |
| RAG runs | 20 = 10 empty + 10 success | same | ✅ |
| `prescription_v3` | 25 = 15 wellness + 10 syndrome_based | same | ✅ |
| `generation_tasks` | 10 = 7 succeeded + 3 failed | same | ✅ |
| `music_assets` | 7 | same | ✅ |

---

## 4. Known Sprint 5 behaviour (the BEFORE baseline)

Everything below is **current, verified behaviour at the Sprint 5 closeout tip**. None of it is
Sprint 6 final behaviour; each item is a known limitation that Sprint 6 phases are expected to
change, and each is tracked in `risk-register.md`.

| # | Known Sprint 5 behaviour | Evidence (path / data) |
|---|---|---|
| 1 | **Wellness / abstain fallback still uses `gong`.** Any abstained diagnosis produces a `degraded` / `wellness` prescription whose tone profile is fabricated as `primary_tone=gong` with weights `{gong: 0.6, others: 0.1}`. | `backend/app/services/v3/prescription_service.py` (`_conservative_wellness_spec`); canonical DB: all 15 `wellness` prescriptions are `gong` |
| 2 | **A near-uniform tone profile can still yield a single primary tone by argmax/tie behaviour.** `primary = max(_TONE_CODES, key=(weight, -index))` over `("jiao","zhi","gong","shang","yu")`. With the approved mapping the raw sums are `gong` 1.15, `shang` 1.15, `zhi` 1.00, `jiao` 0.85, `yu` 0.85 — so a uniform organ profile makes `gong` and `shang` tie, and the tuple order resolves the tie to **`gong`**. | `backend/ai_engine/v3/agent3.py` (`_TONE_CODES`, `_calculate_weights`, `build_tone_profile_v31`); `knowledge/v3/five-tone-mapping-v3.0.json` → `organ_tone_weights.primary` |
| 3 | **RAG currently issues exactly one large query.** All organ codes and all claim codes are concatenated into a single templated sentence, plus the raw confirmed-state free text appended to the embedding input. There is no per-organ grouping, no multi-query, no merge, no dedupe and no rerank. | `backend/ai_engine/v3/rag_store.py` (`_query_text`, `query`); `backend/ai_engine/v3/diagnosis_pipeline.py` (`build_diagnosis_query`) |
| 4 | **RAG currently has a pre-threshold top-K problem.** `n_results = min(top_k, collection.count())` (top_k = 5) truncates the candidate list **before** the `minimum_score` / `review_status` filter, so ranks 6+ can never rescue an empty result. | `backend/ai_engine/v3/rag_store.py` (`query`: `n_results=min(...)` then the threshold gate) |
| 5 | **`primary_tone` is still a required contract field.** `ToneProfileV31.primary_tone: ToneCode` (no default, no `\| None`), and the read model requires `primary_tone: PublicToneExplanation`. A "no primary tone" state is not representable on the transport path. | `backend/app/schemas/v3/flow_v31.py` (`ToneProfileV31`, `FiveToneAnalysisReadModel`) |
| 6 | **Player tone authority `jiao → 角` defect is FIXED.** The legacy `jue` key and the silent `\|\| "gong"` fallback are gone; unknown/missing tones render the empty state (`"--"`), never `gong`. Locked by a regression test. | `frontend/common/v31-tone-theme.js`, `frontend/pages/v3-player/v3-player.vue`, `frontend/tests/sprint5-v31-player-tone-authority.test.mjs` |
| 7 | **`uploads/` and `media/` are root-ignored.** Root-anchored `/uploads/` and `/media/` rules were added so runtime uploads (real medical-record images) and generated media can never be staged accidentally. | `.gitignore` |
| 8 | **Three PaddleOCR fixture failures are accepted pre-existing failures.** They fail identically on a pristine HEAD export, so they are not caused by any Sprint 5 change and do not block closeout. | `tests/api/test_document_v2.py::test_document_accepts_jpeg_signature_and_degrades_honestly`, `::test_valid_multipage_pdf_reaches_ocr_with_real_page_count`, `::test_document_upload_confirm_list_and_delete` |

### 4.1 Additional recorded baseline observations

| Observation | Value |
|---|---|
| Abstention is the dominant outcome in the canonical DB | 15 / 25 diagnoses abstained; 10 / 20 retrievals `empty` |
| Every abstained prescription is `gong` | 15 / 15 `wellness` prescriptions carry `primary_tone=gong` |
| Generation provider reliability | 3 / 10 generation tasks `failed` in the canonical baseline |
| Favorites / preferences | `favorites` = 0; no preference rows — the Favorites/History features start from zero data |
| Migration state | `schema_migrations` = `0001_v3_foundation` … `0009_v3_five_tone_read_model` |

---

## 5. Regression gate baseline

Recorded so later phases can tell "new red" from "known red".

| Gate | Command | Baseline result |
|---|---|---|
| Frontend | `cd frontend && node --test tests/*.test.mjs` | **208 passed / 0 failed** (~33 s) |
| Backend main | `python -m pytest tests/ -q -rfE --tb=line -p no:cacheprovider --deselect tests/tools/test_manual_acceptance_tools.py` (with `PYTHONUTF8=1`) | **3 failed / 1491 passed / 4 deselected / 0 errors** (~88 s) |
| Backend accepted failures | the three PaddleOCR fixture tests listed in §4 item 8 | accepted pre-existing |
| Tools (separate gate) | `python -m pytest tests/tools/test_manual_acceptance_tools.py -q` | **4 passed** |
| Static | `git diff --check` | clean |

Note: the backend gate must be run with Windows Python UTF-8 enabled
(`PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`); otherwise PaddleOCR emits non-UTF-8 bytes on stdout
and pytest's own capture teardown raises `UnicodeDecodeError`, which mis-reports a large number
of spurious "errors".
`tests/tools/test_manual_acceptance_tools.py` must be run as its own step (it spawns child
processes with piped stdio and can stall when batched with the full suite).

---

## 6. What Phase 0 does NOT do

Phase 0 does **not** change any production behaviour. Explicitly untouched:

- five-tone algorithm, `Assessment` algorithm, organ→tone mapping values, prescription fallback
- `primary_tone` schema / `ToneProfileV31`, RAG retrieval, music prompt
- frontend UI, camera/Android manifest, `v3-generation`, favorites/history
- medical knowledge assets, migrations, canonical DB, runtime env, Chroma index

The only code added in Phase 0 is **test-side**: one acceptance fixture and one fixture-contract
test. No production module is modified.
