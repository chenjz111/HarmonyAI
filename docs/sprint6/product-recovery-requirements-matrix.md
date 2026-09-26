# Sprint 6 Product Recovery Requirements Traceability Matrix

**Contract:** `docs/product/sprint6-product-recovery-contract.md`
**Base:** `3f4db5572c075291e430b541505db011bb9fe100`

Legend: **MB** means merge-blocking. Design “—” means the requirement is contractual or architectural and has no dedicated PNG.

Canonical design directory: `docs/product/assets/sprint6-recovery/`. The files below were extracted byte-for-byte from the Owner ZIP and verified before planning approval.

| Canonical asset | SHA256 | Gate state |
|---|---|---|
| `docs/product/assets/sprint6-recovery/HarmonyAI就诊资料智能摘要.png` | `b0a423f64d7e36cf3f02c17458bb4cac94a595cf233a071e002243694da33770` | VERIFIED |
| `docs/product/assets/sprint6-recovery/HarmonyAI山水疗愈音乐界面.png` | `b7b3bf818ab87c9ea19509640472c1def3bea6648c65912b8e8d5987959a80e1` | VERIFIED |
| `docs/product/assets/sprint6-recovery/HarmonyAI聆听反馈界面(3).png` | `0716cbda5457965b092e57d439138f9901d47620635bdad43c878fd0e5cd6f53` | VERIFIED |

| ID | Owner source | Design asset | Current gap | Affected route | Primary affected files | Phase | Automated test | Manual acceptance | MB |
|---|---|---|---|---|---|---|---|---|:---:|
| PR-001 | Final Owner Baseline A | — | Already aligned; protect from regression | `entry`, tabBar | `frontend/pages/entry/entry.vue`, `frontend/pages.json` | A/I | `sprint6-product-recovery-contract.test.mjs` exact entry/tab assertions | Android home/tab inspection | YES |
| PR-002 | Baseline B | 就诊资料智能摘要 | GAP-01 | `v3-material` | `v3-material.vue`, new material flow module | B | single-page state-transition test | Upload 1–3 images through summary on one page | YES |
| PR-003 | Baseline B | 就诊资料智能摘要 | GAP-01 | `v3-material` | `v3-material.vue`, `pages.json` | B | source/navigation spy asserts zero summary-route navigation | Observe no page jump after recognition | YES |
| PR-004 | Baseline B | canonical `HarmonyAI就诊资料智能摘要.png` | GAP-02 | `v3-material` | material flow/presentation | B | indeterminate-stage/no-fake-percent test | Observe honest reading/extracting/summarizing presentation | YES |
| PR-005 | Baseline B | 就诊资料智能摘要 | GAP-03 | `v3-material` | material reveal helper/page | B | fake-timer reveal test preserving exact text | Observe progressive reveal and final exact summary | YES |
| PR-006 | Baseline C | 就诊资料智能摘要 | GAP-04 | `v3-material`, legacy `v3-summary` | material/summary pages, Phase 2 tests | C | markup forbids retention controls | Confirm/edit/re-upload only | YES |
| PR-007 | Baseline F | — | GAP-05 | `v3-confirm` | `v3-confirm.vue`, Phase 2 tests | C | markup forbids retention controls | Confirm/full-text edit only | YES |
| PR-008 | Baseline D | questionnaire final spec | Already aligned | `v3-questionnaire` | questionnaire page/manifest/tests | A/I | 10/5/2/all-required contract test | Complete all five pages; unanswered blocks | YES |
| PR-009 | Baseline E | — | Document-direct path skips goal | supplement/goal/confirm | `v3-supplement.vue`, `v3-goal.vue` | D | both-path navigation matrix | Verify goal or skip appears on both paths | YES |
| PR-010 | Baseline G | canonical `HarmonyAI山水疗愈音乐界面.png` | GAP-06 | supplement/confirm/generation/basis/player | supplement, confirm, generation, basis | D | navigation graph forbids normal `v3-basis` | Both paths reach generation then Player without basis | YES |
| PR-011 | Baseline H/J | 山水疗愈音乐界面 | GAP-07 | `v3-player` | player page, music presentation | E | player explanation wiring test | Compare collapsed/expanded layout to PNG | YES |
| PR-012 | Baseline H | 山水疗愈音乐界面 | GAP-07 | `v3-player` | player page | E | initial collapsed assertion | Fresh Player entry is closed | YES |
| PR-013 | Baseline H | 山水疗愈音乐界面 | GAP-07 | `v3-player` | player page/controller tests | E | toggle invariant test for API/task/audio/progress | Toggle while playing; audio continues | YES |
| PR-014 | Baseline I | 山水疗愈音乐界面 | GAP-08 | basis/player | basis/player/presentation | F | forbidden-copy and Generation Spec duration visibility scan | No recommended-duration wording | YES |
| PR-015 | Baseline I | 山水疗愈音乐界面 | GAP-08 | `v3-player` | player/controller/presentation | F | measured-duration authority test | Progress total matches actual asset | YES |
| PR-016 | Baseline H/J | 山水疗愈音乐界面 | GAP-11 | basis/player | diagnosis public projection, presentation | F | audit/public-copy separation test | No RAG/医学性暂缓 audit language | YES |
| PR-017 | Baseline H | 山水疗愈音乐界面 | GAP-12 | `v3-player` | presentation/player | F | empty-section omission test | No blank cards | YES |
| PR-018 | Baseline device requirement | all three PNGs | GAP-13 | all V3 custom-nav routes | shared page shell, App/pages | H | safe-area import/source contract | Android status-bar matrix | YES |
| PR-019 | Baseline K | 聆听反馈界面(3) | Already aligned | `v3-feedback` | feedback page/tests | A/I | existing Phase 6 feedback tests plus option labels | Q1 validation, Q1-only submit, skip | YES |
| PR-020 | GAP-09 Addendum | — | GAP-09 | diagnosis backend | query policy, RAG store, corpus/tests | G | mixed-profile frozen-similarity acceptance | Approved offline pack and later Owner smoke | YES |
| PR-021 | GAP-09 Addendum | — | Protect abstention | diagnosis backend | RAG acceptance pack | G | unsupported-only and gq_14/15/17 empty | Review abstention copy, no false claim | YES |
| PR-022 | Baseline summary authority | — | Protect confirmed edits | summary/diagnosis | assessment/diagnosis tests | C/G | removed-fact excluded downstream tests | Edit/delete state then inspect public result | YES |
| PR-023 | Sprint 6 authority | — | Protect from regression | basis/player | API/presentation/pages | A/I | authority firewall | Review no invented facts | YES |
| PR-024 | Sprint 6 session/controller authority | — | Protect from dual state machines | generation/player | MusicGenerationFlow/session/controller/pages | D/E | orchestration-vs-task ownership tests | Retry/re-entry/playback smoke | YES |
| PR-025 | GAP-09 frozen facts | — | Protect approved threshold/index | diagnosis backend | policy/manifest/index tests | G | exact threshold/model/checksum assertions | Index receipt review | YES |
| PR-026 | Owner medical governance | — | No runtime asset change before review | diagnosis backend | proposed medical assets | G | approval/checksum gate tests | Medical Review + Owner sign-off attached | YES |
| PR-027 | Provider safety | — | Prevent unauthorized paid/live calls | all | test configuration/scripts/index receipt | A–I | provider deny-list harness; authorized G3 receipt validation | Review logs: zero unauthorized calls/tasks/MP3 | YES |
| PR-028 | Owner closure rule | all three PNGs | Prior gates missed product flow | end-to-end | acceptance docs/tests | I | engineering gate script | Signed Owner Android checklist | YES |
| PR-029 | Owner Plan Review item 1 | canonical `HarmonyAI山水疗愈音乐界面.png` | Missing visible generation transition | `v3-generation` | new generation page, MusicGenerationFlow, pages/routes | D | public-state/wait-retry/navigation test | Observe preparing/generating/cancel/fail-retry then Player | YES |
| PR-030 | Owner Plan Review item 3 | canonical `HarmonyAI山水疗愈音乐界面.png` | Player currently reads basis but must never create | `v3-player` | player page, api read paths, MusicGenerationFlow | D/E | zero-create/zero-AI Player test | Open/toggle explanation with request log unchanged | YES |
| PR-031 | Owner Plan Review item 4 | — | Retained basis currently owns creation/generation | retained `v3-basis` | basis page, routes, compatibility tests | D | basis side-effect-free source/runtime test | Direct compatibility entry cannot create/retry/cancel | YES |

## Gate accounting

- A requirement may move to PASS only when its automated test and required manual acceptance both have evidence.
- “Not exercised” is not PASS.
- A changed historical test must cite the replacement Requirement ID in its assertion message or test comment.
- The merge report must list PR-001 through PR-031 with `PASS`, `FAIL`, or `NOT EXERCISED`; any merge-blocking value other than `PASS` blocks merge.
