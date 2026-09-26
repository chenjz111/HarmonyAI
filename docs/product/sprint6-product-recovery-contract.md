# Sprint 6 Product Recovery Product Contract

**Status:** Owner approved — frozen for Phase A
**Authoritative base:** `3f4db5572c075291e430b541505db011bb9fe100`
**Authority date:** 2026-09-26
**Applies to:** HarmonyAI V3.1 normal production flow

## Authority order

1. Final Owner Baseline and Owner decisions from 2026-09-15 through 2026-09-16.
2. Owner final design assets:
   - `HarmonyAI就诊资料智能摘要.png`
   - `HarmonyAI山水疗愈音乐界面.png`
   - `HarmonyAI聆听反馈界面(3).png`
3. Sprint 6 Product Recovery Discovery Report and GAP-09 RAG Diagnostic Addendum.
4. Earlier V3.1 documents as historical references only.
5. Existing code behavior is never allowed to redefine the product contract.

### Canonical design-asset registry

Before any business implementation begins, the Owner-provided source files must be copied byte-for-byte into `docs/product/assets/sprint6-recovery/` and recorded here:

| Canonical path | SHA256 | Status |
|---|---|---|
| `docs/product/assets/sprint6-recovery/HarmonyAI就诊资料智能摘要.png` | `b0a423f64d7e36cf3f02c17458bb4cac94a595cf233a071e002243694da33770` | Verified from original Owner ZIP |
| `docs/product/assets/sprint6-recovery/HarmonyAI山水疗愈音乐界面.png` | `b7b3bf818ab87c9ea19509640472c1def3bea6648c65912b8e8d5987959a80e1` | Verified from original Owner ZIP |
| `docs/product/assets/sprint6-recovery/HarmonyAI聆听反馈界面(3).png` | `0716cbda5457965b092e57d439138f9901d47620635bdad43c878fd0e5cd6f53` | Verified from original Owner ZIP |

Chat/Library display names are not an executable design dependency. The canonical repository files and hashes above are the design authority. Filename normalization, image re-encoding, resizing and optimization are prohibited.

When sources conflict, the earlier item in this list wins. In particular, the standalone mandatory “五音调适解析” flow in `app-v3.1-final-user-flow.md` is obsolete.

## Preserved architecture

Product Recovery must preserve:

- Backend Authority.
- Summary Authority and user-confirmed state authority.
- Evidence Kernel and provenance.
- RAG approval firewall and checksum/version gates.
- Nullable primary tone and all three regulation modes.
- Prompt Compiler V2.
- Generation idempotency.
- `music-generation-session` as the only generation lifecycle authority.
- `music-presentation` as the frontend presentation boundary.
- `player-controller` as the only playback lifecycle authority.
- Honest fallback and no frontend medical inference.

## Product requirements

### Entry and navigation

- **PR-001 — Two entry choices.** Home exposes exactly “我有就诊资料 / 上传资料” and “我没有就诊资料 / 填写问卷”. Primary tabs are exactly Home and My; there is no Music tab.
- **PR-002 — Single-page material flow.** Upload, recognition, AI thinking, progressive summary and summary confirmation occur on `v3-material` without a normal-success intermediate route.
- **PR-003 — No summary-route navigation.** After “开始识别”, normal success must not navigate or redirect to `v3-summary`.
- **PR-004 — Honest AI-processing presentation.** Material processing may use timed, indeterminate reading/extracting/summarizing labels, but they are presentation phases only. They must not claim server-reported percentages, provider completion or real backend substage progress unless such signals actually exist.
- **PR-005 — Progressive summary reveal.** Once a complete backend summary is available, the UI progressively reveals that immutable returned text. Progressive reveal must not stream invented text or delay persistence.

### Summary and questionnaire

- **PR-006 — Document summary actions.** User-visible actions are confirm, full-text edit and re-upload. Per-evidence “保留 / 不采用” controls are prohibited.
- **PR-007 — Questionnaire summary actions.** The recent-state summary permits confirm and full-text edit only. Per-evidence retention controls are prohibited.
- **PR-008 — Canonical questionnaire.** The formal questionnaire is Q1–Q10, five pages, two questions per page and all ten required. User UI exposes no organ mapping, scores or medical terminology.
- **PR-009 — Optional UserGoal on both paths.** Healing intent is a separate optional UserGoal step in both document and questionnaire normal flows. It may be skipped and must never become medical evidence or override confirmed state.
- **PR-022 — Confirmed text authority.** User-confirmed or edited summary text remains downstream primary state context; structured facts remain provenance and cannot override conflicting confirmed text.

### Analysis, generation and playback

- **PR-010 — No mandatory basis page.** Normal production navigation must not require `v3-basis`.
- **PR-029 — Visible generation transition.** After confirmed state and optional UserGoal, normal flow must enter `v3-generation`, a thin public-safe waiting/cancel/retry page. It delegates cross-stage preparation to `MusicGenerationFlow` and task lifecycle to `music-generation-session`; it never displays RAG, Diagnosis, Prescription, Provider or Minimax terminology.
- **PR-011 — Player explanation.** The reusable analysis presentation appears inside Player under “为什么是这首音乐？” / “查看本次音乐的生成依据”.
- **PR-012 — Explanation collapsed by default.** Every Player entry and re-entry starts with the explanation closed unless a future Owner contract explicitly changes persistence.
- **PR-013 — Presentation-only expansion.** Expanding or collapsing explanation must not run Diagnosis, Prescription or Generation; rebuild the player controller/audio context; change task identity; stop audio; or reset playback progress.
- **PR-014 — No recommended duration.** User UI must not show recommended, suggested or regulation duration derived from Generation Spec.
- **PR-015 — Actual playback duration only.** Player may show only controller-measured or verified audio-asset duration and playback progress.
- **PR-016 — Public-safe copy.** Backend audit, RAG, abstention and internal failure wording must not be rendered directly as user-facing copy. Audit reason codes remain preserved internally.
- **PR-017 — No empty analysis section.** A section with no meaningful approved presentation content is not rendered.
- **PR-023 — Frontend authority firewall.** Frontend must not infer tone, instrument, ambience, syndrome, severity, title or treatment meaning from tone/theme/score data.
- **PR-024 — Single lifecycle authorities.** Generation lifecycle remains solely in `music-generation-session`; playback lifecycle remains solely in `player-controller`.
- **PR-030 — Player read-only.** Player consumes a resolved asset identity and prepared analysis/read model. It must not create Diagnosis or Prescription, call an `allowCreate` basis path, start generation to obtain explanation data, or re-run AI/RAG when explanation is opened.
- **PR-031 — Basis compatibility is side-effect-free.** If `v3-basis` remains registered or source-retained, it is read-only compatibility UI only. It must not use `getMusicBasis({allowCreate:true})`, create medical artifacts, start/retry/cancel generation, or appear in normal production navigation.

### Device and feedback

- **PR-018 — Unified safe area.** All V3 custom-navigation pages use one shared safe-area shell and do not overlap Android system status bars.
- **PR-019 — Feedback contract.** Q1 / `post_state` is required when feedback is submitted; Q2–Q5 are optional; skip remains legal. Q4 options remain the four Owner-approved choices.

### Questionnaire RAG

- **PR-020 — Supported questionnaire retrieval.** A questionnaire profile with sufficient approved knowledge support must not systematically become `BASIC_RAG_EMPTY` because multiple claims were diluted into one query vector.
- **PR-021 — Honest unsupported abstention.** A genuinely unsupported-only profile remains eligible for approved `RAG_EMPTY` / abstention; no low-relevance chunk may be forced into the context.
- **PR-025 — Frozen retrieval safety.** Until a separately approved benchmark changes it, source cosine threshold remains `0.65`, runtime normalized threshold remains `0.740741`, embedding remains `text-embedding-v4@1024`, and every hit remains approval/checksum/version gated.
- **PR-026 — Medical review gate.** New corpus text, domain grouping and focused-query semantics require Medical Review and Owner approval before runtime integration.

### Release governance

- **PR-027 — Provider-safe engineering tests.** Routine Product Recovery development and CI use mocks, fake tasks, fixtures and frozen similarity matrices; they make zero real Qwen, Embedding or Music provider calls and generate no MP3. A G3 index build may call the approved embedding provider only after separate explicit Owner authorization and must emit a model/version/manifest/chunk-count receipt. Every gate requires zero **unauthorized** real provider calls.
- **PR-028 — Dual acceptance gate.** Product Recovery closes only after Engineering Acceptance and Owner Real-device Product Acceptance both pass. CI/build success alone is insufficient.

## Normal production flows

### With document

```text
Home
→ v3-material: upload → recognition → thinking → progressive summary → confirm/edit
→ direct continue OR optional canonical questionnaire
→ optional UserGoal
→ final confirmed state
→ v3-generation
→ MusicGenerationFlow: ensure/reuse Assessment → Diagnosis → Prescription / Generation Spec
→ music-generation-session
→ Player with collapsed explanation
→ optional Feedback
```

### Questionnaire only

```text
Home
→ canonical Q1–Q10
→ optional UserGoal
→ recent-state summary confirm/full-text edit
→ v3-generation
→ MusicGenerationFlow: ensure/reuse Assessment → Diagnosis → Prescription / Generation Spec
→ music-generation-session
→ Player with collapsed explanation
→ optional Feedback
```

## Merge-blocking rule

Every requirement marked merge-blocking in the Requirements Traceability Matrix must have:

1. An automated assertion passing on the proposed merge tree.
2. Its manual acceptance evidence recorded when the matrix requires device review.
3. No conflicting active test that encodes an older product contract.
4. Owner approval for any Medical Review or design-asset interpretation gate.
