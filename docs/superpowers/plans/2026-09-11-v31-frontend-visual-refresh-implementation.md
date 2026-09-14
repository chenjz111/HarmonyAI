# HarmonyAI V3.1 Frontend Visual Refresh Implementation Plan

> Execute in small test-first slices. Do not modify backend contracts, migrations, approved questionnaire data, medical assets, or provider code.

**Goal:** Deliver the Owner-approved mobile visual refresh and interaction details on top of the merged V3.1 integration flow.

**Architecture:** Keep existing Vue/uni-app pages and `apiV3` transitions. Add a shared responsive visual layer, then update each page without changing authoritative data sources. Use one data-driven player component/theme map for all five tones.

**Tech stack:** Vue 3 SFC, uni-app, H5/Vite, Node test runner.

---

## Task 1: Baseline and regression contract

**Files:**
- Modify: `frontend/tests/sprint5-v3-owner-flow.test.mjs`
- Create: `frontend/tests/sprint5-v31-visual-flow.test.mjs`

1. Correct the frontend test invocation for this repository (`node --test tests/*.test.mjs`).
2. Add failing source-level regression tests for the final routes, button labels, hidden healing-intent fields, material-error branch, inline editors, direct-to-player flow, and measured duration.
3. Run only the two affected frontend test files and confirm failures identify the not-yet-built UI.

## Task 2: Responsive foundation and navigation

**Files:**
- Modify: `frontend/App.vue`
- Modify: `frontend/uni.scss`
- Modify: `frontend/pages.json`
- Create: `frontend/pages/v3-profile/v3-profile.vue`
- Create/modify shared components under `frontend/components/v31/`

1. Add tests for `首页 / 我的`, absence of `播放`, and the upgrade placeholder.
2. Implement responsive tokens, safe-area spacing, centered H5 mobile canvas, shared header/page shell/card/button components, and the registered placeholder `我的` tab page.
3. Verify at 320/360/390/430px and run the affected tests.

## Task 3: Home and upload/error flow

**Files:**
- Modify: `frontend/pages/entry/entry.vue`
- Modify: `frontend/pages/v3-material/v3-material.vue`
- Modify: `frontend/pages/v3-material-error/v3-material-error.vue`

1. Add failing tests for both entry cards, re-entry after returning home, 1–3 thumbnails, top-right remove, add tile, explicit start, and frozen error actions.
2. Implement the approved layouts while keeping `selectMode`, upload, discard, and routing calls unchanged.
3. Verify the entry-reselection regression and material-error transition tests.

## Task 4: Document summary and questionnaire choice

**Files:**
- Modify: `frontend/pages/v3-summary/v3-summary.vue`
- Modify: `frontend/pages/v3-supplement/v3-supplement.vue`

1. Add failing tests for the three summary actions, in-card edit state, save/cancel behavior, and the two questionnaire-choice outcomes.
2. Implement the visual refresh and inline caret/editor behavior without adding a second confirmation.
3. Verify document-only navigation goes directly to Five-Tone analysis.

## Task 5: Questionnaire and Owner healing-intent override

**Files:**
- Modify: `frontend/pages/v3-questionnaire/v3-questionnaire.vue`
- Modify: `frontend/pages/v3-goal/v3-goal.vue`
- Modify: `frontend/tests/sprint5-v31-visual-flow.test.mjs`

1. Add failing tests for five pages, two approved questions per page, labels `下一题`/`完成问卷`, manifest-driven options, and required completion.
2. Add failing tests proving the `other` card and free-text field are absent while six choices, max-two selection, skip, and compatible payload behavior remain.
3. Implement the layouts and Owner override.
4. Run questionnaire, contract, and visual-flow tests only.

## Task 6: Recent-state confirmation and Five-Tone analysis

**Files:**
- Modify: `frontend/pages/v3-confirm/v3-confirm.vue`
- Modify: `frontend/pages/v3-basis/v3-basis.vue`

1. Add failing tests for inline editing, live read-model fields, optional secondary tone, scroll-safe content, generation wording, loading state, and direct player transition.
2. Implement the refreshed pages without fabricating analysis text or music parameters.
3. Verify both questionnaire paths converge correctly.

## Task 7: Five-tone player and feedback

**Files:**
- Modify: `frontend/pages/v3-player/v3-player.vue`
- Modify: `frontend/pages/v3-feedback/v3-feedback.vue`
- Create: `frontend/common/v31-tone-theme.js`

1. Add failing tests for all five tone theme mappings, measured duration, authorized playback, progress, favorite, feedback, and exit.
2. Implement one data-driven player with tone-specific colors/copy/artwork slots.
3. Refresh the optional feedback page without changing its DTO or persistence calls.
4. Run player/feedback/visual-flow tests.

## Task 8: Visual assets and responsive polish

**Files:**
- Create/modify only frontend visual assets under `frontend/static/v31/`
- Modify affected page/component styles

1. Prepare separate decorative assets; do not bake text or controls into page screenshots.
2. Check long Chinese content, keyboard visibility, touch targets, safe areas, and scrolling at the four target widths.
3. Confirm decorative images have no bearing on navigation or state.

## Task 9: Final verification and handoff

1. Run all frontend tests with the repository-compatible glob invocation.
2. Run `npm run build:h5`.
3. Run `git diff --check` and review the final diff for backend/contract/medical-asset changes (there must be none).
4. Launch the H5 preview and manually exercise:
   - document success
   - document error → reupload
   - document error → discard → questionnaire
   - document-only direct path
   - without-document questionnaire path
   - all five player themes
5. Record exact tests, build result, known visual differences, HEAD, and remaining Android/manual gates.
