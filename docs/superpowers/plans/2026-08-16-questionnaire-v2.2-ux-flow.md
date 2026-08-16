# Questionnaire v2.2 and Assessment UX Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a backward-compatible `questionnaire_v2.2`, simplify the assessment flow to one final confirmation page, remove misleading internal metrics from the user UI, and expand optional feedback without changing the five-Agent or frozen Safety architecture.

**Architecture:** Keep `questionnaire_v2.1` artifacts, scoring and tests byte-for-byte compatible. Add a parallel v2.2 canonical artifact and explicit Pydantic/scoring branches for structured goals, five-level energy, and physical-signal free text. The frontend defaults to v2.2, while Assessment continues to accept v2.0/v2.1. Safety verification is rendered inside the final Assessment confirmation and remains authoritative; normal conflicts stay backend-only.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, Vue 3/uni-app, Node test runner, pytest.

## Global Constraints

- Preserve the five-Agent sequence: Assessment → Diagnosis → Prescription → Music → Feedback.
- Preserve PR #72 safety states and aggregation semantics.
- Do not modify frozen `questionnaire_v2.1` semantics or fixtures.
- Q19/Q20 remain safety-only and do not influence ordinary scoring or music parameters.
- No Sprint 5, Formal 60, emotion-F1, Cloud Qwen, or real music-generation work.
- PR base is `integration/sprint4-real-input`; do not merge the PR.

---

### Task 1: Freeze the new v2.2 contract with failing tests

**Files:**
- Create: `knowledge/questionnaire-v2.2.json`
- Create: `knowledge/questionnaire-scoring-v2.2.json`
- Create: `tests/contract/fixtures/questionnaire-v2.2.contract.json`
- Create: `tests/contract/test_questionnaire_v22_schema.py`
- Modify: `tests/knowledge/test_questionnaire_v2.py`

**Interfaces:**
- Produces schema version `questionnaire_v2.2` with 20 questions.
- Q1 value: `{primary_goal: str, secondary_goal: str|null, custom_goal_text: str|null}`.
- Q14 values: `full|three_quarters|half|quarter|empty`, mapping to `low_energy=0|1|2|3|4`.
- Q16 value: `{selected: list[str], custom_text: str|null}`.

- [ ] Write contract tests that require Q1 primary, limit total selected goals to two, and require custom text when `other` is selected.
- [ ] Write tests for Q14 five-level reverse scoring.
- [ ] Write tests for Q16 `none` exclusivity, custom text preservation, and unchanged Q19/Q20 safety metadata.
- [ ] Run the new tests and confirm they fail because v2.2 does not exist.
- [ ] Add canonical/scoring JSON with only the approved Q1/Q14/Q16 changes.
- [ ] Run contract/knowledge tests and confirm v2.1 remains green.

### Task 2: Add backward-compatible backend validation and scoring

**Files:**
- Modify: `backend/app/schemas/assessment_v2.py`
- Modify: `backend/ai_engine/questionnaire_v2.py`
- Create: `tests/ai_engine/test_questionnaire_v22.py`
- Create: `tests/api/test_questionnaire_v22_submission.py`

**Interfaces:**
- Add `GoalSelection` and `PhysicalSignalsSelection` Pydantic models to `QuestionnaireAnswer.value`.
- Add `questionnaire_v2.2` to `QuestionnaireV2Submission.schema_version` and require exactly 20 answers with a 14-day window.
- Add `score_questionnaire_v22(envelope) -> QuestionnaireScore`.

- [ ] Write failing scorer tests for valid Q1/Q14/Q16 and rejection of invalid goal counts, missing custom text, duplicate/`none`-mixed signals, and invalid safety values.
- [ ] Write failing API boundary tests proving v2.0/v2.1 still validate unchanged and v2.2 is accepted explicitly.
- [ ] Implement minimal schema and scoring branches.
- [ ] Verify Q1 stays in `qualitative.goal` and never creates symptom evidence/dimension scores.
- [ ] Verify Q16 custom text is preserved as supplemental physical narrative and safety text reaches the existing Safety engine.
- [ ] Run targeted backend tests.

### Task 3: Make the frontend questionnaire default to v2.2

**Files:**
- Modify: `frontend/common/questionnaire-data.js`
- Modify: `frontend/common/questionnaire-rules.js`
- Modify: `frontend/pages/questionnaire-v2/questionnaire-v2.vue`
- Create: `frontend/tests/sprint4-questionnaire-v22.test.mjs`

**Interfaces:**
- `questionnaireV22` becomes the page default; `questionnaireV21` remains exported for compatibility.
- Add pure helpers `applyGoalChoice`, `isGoalComplete`, and Q16 serialization helpers.

- [ ] Write failing frontend tests for one required primary, optional secondary, maximum two, custom goal text, Q14 five visual choices, real battery UI, Q16 custom text, and safety-only Q19/Q20 copy.
- [ ] Verify the tests fail against current v2.1 UI.
- [ ] Implement Q1 primary/secondary interaction and custom field.
- [ ] Implement the five-level battery UI without exposing icon identifiers.
- [ ] Implement conditional Q16 free text while retaining `none` mutual exclusion.
- [ ] Add “最后一步 · 安全确认” copy for Q19/Q20 without changing their values or routing semantics.
- [ ] Submit `questionnaire_version/schema_version=questionnaire_v2.2`.

### Task 4: Collapse assessment into one human-readable confirmation

**Files:**
- Modify: `frontend/common/assessment-page-flow.js`
- Modify: `frontend/common/safety-flow.js`
- Modify: `frontend/pages/assessment-result/assessment-result.vue`
- Modify: `frontend/pages.json`
- Modify or retain only as unreachable compatibility code: `frontend/pages/safety-verification/safety-verification.vue`
- Create: `frontend/tests/sprint4-assessment-simplification.test.mjs`

**Interfaces:**
- Normal users see exactly one page titled `确认一下我们对你当前状态的理解`.
- `needs_verification` renders a required safety card on that page and uses the existing safety-verification API.
- The normal confirmation action cannot clear Safety.

- [ ] Write failing tests that ban coverage/confidence percentages, `multi_source`, raw `/4` scores, internal enums/status labels and normal conflict cards.
- [ ] Write failing navigation tests proving ordinary material never visits the standalone verification page.
- [ ] Write failing safety tests proving unresolved verification blocks individualized flow and Q19/Q20 confirmed signals dominate an OCR resolution.
- [ ] Replace technical sections with plain-language state, physical, recent-context and goal summaries plus a collapsed evidence-source explanation.
- [ ] Embed Safety verification at the top only when required.
- [ ] Retain only `基本符合，继续` and `有些地方不对，我要修改` as normal actions.
- [ ] Keep provider/OCR degradation copy honest without showing numerical confidence.

### Task 5: Expand optional Feedback while keeping state change required

**Files:**
- Modify: `backend/app/schemas/feedback_v2.py`
- Modify: `backend/ai_engine/feedback_v2.py`
- Modify: `backend/app/routers/feedback_router.py`
- Modify: `frontend/pages/feedback-v2/feedback-v2.vue`
- Modify: `tests/ai_engine/test_feedback_v2.py`
- Modify: `tests/api/test_feedback_v2_schema.py`
- Create: `frontend/tests/sprint4-feedback-ux.test.mjs`

**Interfaces:**
- `post_state.change_label` remains required.
- Ratings, continue-use, favorite, music preference selections and free text are optional.
- Add `liked_features`, `adjustment_preferences`, and `overall_experience` with empty defaults for backward compatibility.

- [ ] Write failing schema/agent tests for change-only submission and positive/negative preference patches.
- [ ] Write failing frontend tests for required 2×2 change cards and optional remaining fields.
- [ ] Implement optional schema fields without invalidating existing v2.0 records.
- [ ] Update Feedback Agent output to preserve liked elements and requested adjustments only in personal preferences; keep `global_rule_update=false`.
- [ ] Implement large 2×2 cards and three optional feedback sections.

### Task 6: Prove source participation, fallback, and safety regression

**Files:**
- Modify: `tests/ai_engine/test_assessment_v21.py` or create `tests/ai_engine/test_assessment_v22_sources.py`
- Modify: `frontend/tests/sprint4-safety-flow.test.mjs`
- Modify: `docs/questionnaire-v2-design.md`
- Create: `docs/questionnaire-v2.2-spec.md`

**Interfaces:**
- Narrative, OCR text and questionnaire remain Assessment inputs.
- Qwen unavailable uses questionnaire/safety rules; OCR failure permits skip/manual fallback.

- [ ] Add targeted tests for narrative and OCR evidence participation when available.
- [ ] Add fallback tests for unavailable Qwen and failed OCR.
- [ ] Re-run PR #72 safety, comfort-audio, multi-signal and prescription-authority tests.
- [ ] Document v2.2 fields and v2.1 compatibility without rewriting the frozen v2.1 contract.

### Task 7: Final verification and PR

**Files:**
- Update only if current status changed: `HANDOFF.md`

- [ ] Run frontend Node tests.
- [ ] Run H5 production build.
- [ ] Run contract tests.
- [ ] Run targeted backend/API/safety tests, then one final full `pytest tests/ -q`.
- [ ] Run `git diff --check` and scan for secrets, temp files and unrelated changes.
- [ ] Commit coherent stages, push `feat/questionnaire-v2.2-ux-flow`, and create a PR against `integration/sprint4-real-input`.
- [ ] Do not merge; report Android rerun as required.
