# HarmonyAI V3.1 Frontend Visual Refresh Design

**Date:** 2026-09-11
**Branch:** `feat/s5-v3.1-frontend-visual-refresh`
**Base:** `origin/integration/sprint4-real-input` at `913396e`

## 1. Goal

Rebuild the V3.1 mobile experience to closely match the Owner-provided Chinese ink-and-wash references while preserving the shipped API, database, questionnaire, assessment, generation, player, and feedback contracts.

The UI must remain usable across common mobile widths (320–430 CSS px), safe-area insets, long Chinese content, and H5/Android targets. Reference screenshots guide composition and visual hierarchy; they must not be used as flattened full-page backgrounds with fake hotspots.

## 2. Authority and Owner override

The normal flow follows `docs/product/app-v3.1-teacher-user-flow.md`.

Owner override recorded on 2026-09-11:

- The healing-intent page hides the `other` choice and the free-text supplement section.
- The six structured choices remain available, with a maximum of two selections and a skip action.
- Backend/API compatibility remains intact: no schema or database field is removed; the client submits no `other` choice and sends `custom_goal_text` as empty/null according to the existing facade.

This is the only deliberate difference from the teacher flow. It must be covered by a frontend regression test.

## 3. Final user flow

### 3.1 Shared entry

The app launches directly into the two-card home page. Bottom navigation shows `首页` and `我的`; `播放` is removed. Because uni-app tab items must have a registered route, `我的` opens a minimal placeholder page displaying `功能升级中`; it contains no profile/history implementation in this release.

### 3.2 With-document path

1. Home → `我有就诊资料`.
2. Upload 1–3 images. Each thumbnail has a top-right remove control; an add tile remains visible until three images are selected.
3. The user explicitly taps `开始识别`.
4. If the material is invalid, irrelevant, insufficient, or cannot be recognized, show the standalone material-error page:
   - title: `这份资料暂时无法用于本次分析`
   - message: `未识别到与本次状态评估相关的有效信息，请检查是否上传了合适的就诊资料。`
   - `重新选择资料` returns to upload
   - `我没有合适的资料` performs the authoritative discard transition and then enters the required questionnaire
5. If usable, show the document summary. Actions are `资料摘要基本无误`, `修改资料摘要`, and `重新上传资料`.
6. Editing happens inside the existing summary card. Save continues; cancel restores the original text.
7. After confirmation, show the lightweight questionnaire choice:
   - fill questionnaire → questionnaire → healing intent → recent-state confirmation
   - continue directly → Five-Tone analysis without a duplicate recent-state confirmation

### 3.3 Without-document path

Home → `我没有就诊资料` → five questionnaire pages (two approved questions per page) → healing intent → recent-state confirmation → Five-Tone analysis.

Questionnaire order, wording, option codes, exclusivity, scores, schema identity, and required behavior continue to come from the approved manifest. Long pages scroll vertically. Pages 1–4 use `下一题`; page 5 uses `完成问卷`.

### 3.4 Analysis, generation, player, feedback

- Recent-state editing is inline in the existing summary card.
- Five-Tone analysis renders live state tags, interpretation, evidence, primary/secondary tones, BPM, target duration, instruments, and ambience. It scrolls when content exceeds the viewport.
- The primary action is `生成本次音乐`. Generation progress remains on the analysis page.
- Success goes directly to the player.
- One data-driven player switches between Gong/Shang/Jue/Zhi/Yu themes using the authoritative primary tone. It does not duplicate five page implementations.
- Player duration comes from the downloaded/measured audio data. No mockup duration is hard-coded.
- Player keeps real play/pause, seek/progress, authorized audio fetch, favorite, feedback, and exit behaviors.
- Feedback is optional; submit or skip returns home.

## 4. Visual system

- Warm paper background with low-contrast ink landscape layers and restrained floral/instrument illustrations.
- Deep teal is the main interface color; tone-specific colors are reserved for player themes.
- Cards and controls are real layout elements with readable contrast and 44px minimum touch targets.
- Decorative artwork is isolated from text and controls so content can reflow.
- Body copy uses a readable sans-serif Chinese stack. Display/brush type is limited to short headings.
- Desktop H5 centers a phone-width content column instead of stretching the mobile composition across the viewport.

## 5. Component strategy

Introduce shared visual components/tokens only where they reduce duplication:

- responsive page shell and safe-area footer
- compact HarmonyAI header/back control
- ink card, section heading, and primary/secondary actions
- inline editable summary card
- upload thumbnail/add tile
- questionnaire question/option cards
- tone theme map for player color, title, descriptive copy, and artwork slot

Existing API facade calls and state transitions stay in their current pages. The redesign must not fork or replace backend behavior.

## 6. Error and loading behavior

- Preserve separate network and OCR/material errors without exposing provider details.
- Disable repeated submissions while a request is active.
- Preserve user text after a failed edit submission.
- No real-provider failure may be presented as generated success.
- Empty or unavailable player data shows the existing honest unavailable state.

## 7. Verification

Automated checks will cover:

- both entry paths and reselecting an entry after returning home
- 1–3 upload behavior, removal, and add-tile visibility
- material error page wording, re-upload route, and server-authoritative discard before questionnaire navigation
- inline document-summary and recent-state editing
- five pages/two approved questions per page and required completion
- hidden `other`/free-text healing-intent UI while preserving compatible payload shape
- document-only path skipping duplicate recent-state confirmation
- direct generation-to-player navigation
- five data-driven tone themes, measured duration, favorites, feedback, and exit
- no internal/provider fields rendered
- H5 build plus viewport review at 320, 360, 390, and 430px widths

Backend suites are not rerun unless a frontend change unexpectedly crosses an API boundary.

## 8. Out of scope

- API contract, database schema, migrations, questionnaire medical content, scores, or ordering
- Teacher Flow changes beyond the recorded Owner healing-intent override
- Agent1–Agent5 logic or approved medical assets
- Implementing Profile/History/Favorites pages behind `我的`
- Changing the real TokenHub/MiniMax provider
