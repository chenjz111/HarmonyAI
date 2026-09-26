# Sprint 6 Product Recovery Baseline Audit

**Base:** `3f4db5572c075291e430b541505db011bb9fe100`
**Branch:** `feat/s6-product-recovery`
**Purpose:** Non-blocking record of the product state before Phase B. `CURRENT_FAIL` is audit evidence, not a permanent red CI assertion.

## Requirement baseline

| Requirement | Baseline | Evidence |
|---|---|---|
| PR-001 | CURRENT_PASS | `entry.vue` has the two Owner entries; `pages.json` tabBar contains Home/My only. |
| PR-002 | CURRENT_FAIL | Material success redirects to the standalone summary page. |
| PR-003 | CURRENT_FAIL | `v3-material.vue` explicitly redirects to `v3-summary`. |
| PR-004 | CURRENT_FAIL | No honest indeterminate reading/extracting/summarizing presentation contract exists. |
| PR-005 | CURRENT_FAIL | Summary appears after route change; no progressive reveal exists. |
| PR-006 | CURRENT_FAIL | Document summary exposes per-evidence retention controls. |
| PR-007 | CURRENT_FAIL | Questionnaire summary exposes per-evidence retention controls. |
| PR-008 | CURRENT_PASS | Approved questionnaire has Q1–Q10, five UI pages, two questions per page and all questions required. |
| PR-009 | CURRENT_FAIL | Document-direct continue bypasses optional UserGoal. |
| PR-010 | CURRENT_FAIL | Both normal paths navigate through `v3-basis`. |
| PR-011 | CURRENT_FAIL | Player does not render the collapsed explanation content. |
| PR-012 | CURRENT_FAIL | The presentation model has a collapsed default, but Player has no explanation control. |
| PR-013 | CURRENT_FAIL | No Player explanation toggle exists, so the no-reset interaction cannot be accepted. |
| PR-014 | CURRENT_FAIL | Basis/Player expose user-facing Generation Spec duration language. |
| PR-015 | CURRENT_PASS | Playback progress authority is controller-measured duration with verified asset fallback. |
| PR-016 | CURRENT_FAIL | Internal RAG/abstention wording can reach public presentation. |
| PR-017 | CURRENT_FAIL | Empty analysis sections are not consistently omitted. |
| PR-018 | CURRENT_FAIL | Safe-area handling is distributed across page-local rules and lacks one shared shell/device gate. |
| PR-019 | CURRENT_PASS | Feedback Q1 is required on submit, Q2–Q5 optional, skip legal and Q4 options match Owner baseline. |
| PR-020 | CURRENT_FAIL | Recent supported questionnaire-only profiles repeatedly end in query-dilution `RAG_EMPTY`. |
| PR-021 | CURRENT_PASS | Unsupported/no-answer profiles legally remain empty and do not call the diagnosis provider. |
| PR-022 | CURRENT_PASS | Confirmed/edited state text is downstream primary context; stale removed facts remain provenance only. |
| PR-023 | CURRENT_PASS | Phase 6 authority firewall prevents page-level tone/theme/score medical inference. |
| PR-024 | CURRENT_PASS | Current basis delegates task lifecycle to `music-generation-session`; Player delegates audio lifecycle to `player-controller`. |
| PR-025 | CURRENT_PASS | Policy remains cosine 0.65 / normalized 0.740741 with `text-embedding-v4@1024` and checksum/version gates. |
| PR-026 | CURRENT_PASS | Contract now blocks corpus/grouping runtime work until Medical Review and Owner approval. |
| PR-027 | CURRENT_PASS | Phase A uses static files/local tests only: zero real providers, generation tasks and MP3 output. |
| PR-028 | CURRENT_FAIL | Dual Engineering + Owner real-device Product Acceptance has not yet run. |
| PR-029 | CURRENT_FAIL | No registered `v3-generation` waiting/retry route or `MusicGenerationFlow` exists. |
| PR-030 | CURRENT_PASS | Current Player calls cached/read-only basis and music reads; it has no allow-create, diagnosis or generation start path. |
| PR-031 | CURRENT_FAIL | Retained `v3-basis` still calls allow-create basis and owns start/retry/cancel generation actions. |

## Historical conflicting-test inventory

These tests remain unchanged in Phase A. Their intentional updates belong to the phase that replaces the behavior.

| Test | Historical assertion | Replacement owner |
|---|---|---|
| `frontend/tests/sprint5-v3-owner-flow.test.mjs` | Document-direct continues to mandatory `v3-basis`. | Phase D, PR-009/010/029 |
| `frontend/tests/sprint5-v31-summary-authority.test.mjs` | User-visible two-state retention controls remain present. | Phase C, PR-006/007 |
| `frontend/tests/sprint5-v31-summary-basis-copy.test.mjs` | Questionnaire summary exposes “保留 / 不采用”; standalone basis copy remains user-facing. | Phase C/F, PR-007/014 |
| `frontend/tests/sprint6-phase2-summary-authority.test.mjs` | Both summaries must expose structured evidence toggles. | Phase C, PR-006/007/022 |
| `frontend/tests/sprint6-phase6-basis-wiring.test.mjs` | `v3-basis` owns generation-session wiring. | Phase D, PR-010/029/031 |
| `frontend/tests/sprint6-phase6-route-safety.test.mjs` | `v3-basis` is a required current V3 route. | Phase D, PR-010/029/031 |
| `frontend/tests/sprint6-phase6-authority-firewall.test.mjs` | Includes basis as a registered authority-safe page. | Phase D; preserve firewall while changing route role |

## Phase A safety accounting

- Business runtime files changed: **0**.
- Canonical questionnaire manifest changed: **NO**.
- Protected `stash@{0}` touched: **NO**.
- Real Qwen calls: **0**.
- Real Embedding calls: **0**.
- TokenHub/Minimax calls: **0**.
- Music generation tasks: **0**.
- Generated MP3 files: **0**.
