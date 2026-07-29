# Sprint 3 V2 Contract Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Sprint 3 AI Agent V2 增量实现迁移到组长最新冻结的 Assessment、Music 和 Feedback 契约，同时完整保留 Sprint 2 行为。

**Architecture:** 先把最新 `origin/feat/zhongrc` 合入隔离分支，再用 Pydantic 共享 Schema 固定团队接口。AI 内部继续复用已通过测试的确定性问卷、安全规则和模型降级逻辑，只在 V2 边界做规范字段转换；Sprint 2 入口不参与重构。

**Tech Stack:** Python 3.10+、Pydantic 2.13、pytest、LangGraph、现有 Qwen Provider、Chroma 适配层、Git worktree。

## Global Constraints

- 远程 `origin/docs/sprint3-planning` 的 `docs/api-contract-v2.md` 和 `docs/sprint3-team-tasks.md` 是 V2 字段权威来源。
- 保留 `run_real_workflow()` 的签名、默认四星反馈和 Sprint 2 测试语义。
- V2 正式输入使用 `document_id`、`document_text`、`narrative_text`、`questionnaire_answers`。
- V2 Assessment 正式输出使用 `emotion_profile`、`physical_profile`、`life_events`、`assessment_summary`、`extracted_evidence`、`safety_flags`。
- V2 Music 正式输出使用 `music_id`、`title`、`source_type`、`stream_url`、`mode`、`bpm`、`duration_seconds`、`instruments`。
- P0 的 `source_type` 只能为 `matched`，且表示本地曲库匹配。
- V2 Feedback 使用 `music_id`，只更新个人偏好，`global_rule_update=false`。
- 未提供显式 Feedback 时不得访问 Repository。
- 普通日志不得包含完整 `document_text` 或 `narrative_text`。
- 不修改 Frontend、文件上传/OCR Router、数据库迁移和正式 Release Tag。
- 不批量删除任何文件或目录；保留全部无关 `.test-*` 目录。
- 所有生产代码变更必须先有会正确失败的测试。

---

### Task 1: Sync the latest team branch and establish the new baseline

**Files:**
- Merge: `origin/feat/zhongrc` into `codex/sprint3-ai-v2`
- Preserve: all existing `backend/ai_engine/*_v2.py`
- Preserve: all existing `tests/ai_engine/test_*_v2.py`
- Preserve: `docs/superpowers/specs/2026-07-29-sprint3-v2-contract-migration-design.md`

**Interfaces:**
- Consumes: remote commit `74b9dbc` and current local design commit `90b6537`
- Produces: one merge baseline containing current Backend package, new team contracts, and all existing Sprint 3 V2 modules

- [ ] **Step 1: Record the pre-merge state**

Run:

```powershell
git status --short
git rev-parse HEAD
git rev-parse origin/feat/zhongrc
```

Expected: only the known `.test-*` directories and the interrupted, uncommitted handoff document are untracked; HEAD is `90b6537`; remote team branch is `74b9dbc`.

- [ ] **Step 2: Merge the team branch without rewriting history**

Run:

```powershell
git merge --no-ff origin/feat/zhongrc -m "merge: sync latest sprint3 team contracts"
```

Conflict policy:

- for `docs/api-contract-v2.md`, `docs/user-flow-v2.md`, `docs/sprint3-team-tasks.md`, and `docs/questionnaire-v2-spec.md`, keep the remote planning version;
- for Sprint 3 V2 AI modules and tests, keep this branch's additions;
- for Sprint 2 files modified on both sides, preserve the remote hardening changes and re-run all Sprint 2 tests;
- do not resolve a conflict by deleting an entire directory.

- [ ] **Step 3: Verify the merged file set**

Run:

```powershell
git status --short
git diff --name-status 90b6537..HEAD
git diff --check 90b6537..HEAD
```

Expected: no unmerged entries and no whitespace errors.

- [ ] **Step 4: Run a fresh full baseline**

Run:

```powershell
$tmp = Join-Path $env:TEMP ("harmony-new-contract-baseline-" + [guid]::NewGuid().ToString("N"))
& "C:\Users\51178\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  -m pytest -p no:cacheprovider --basetemp $tmp -q
```

Expected: all collected tests pass. If the merge exposes a real regression, stop and use systematic debugging before Task 2.

- [ ] **Step 5: Record the baseline**

Write the merge SHA and test count to `.superpowers/sdd/2026-07-29-sprint3-v2-contract-migration/progress.md`. Do not include `.test-*` directories in a commit.

---

### Task 2: Add canonical Assessment Pydantic schemas and migrate Assessment V2

**Files:**
- Create: `backend/app/schemas/assessment_v2.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/ai_engine/assessment_v2.py`
- Create: `tests/api/test_assessment_v2_schema.py`
- Modify: `tests/ai_engine/test_assessment_v2.py`
- Modify: `tests/ai_engine/test_ai_degradation_v2.py`

**Interfaces:**
- Consumes:
  - `run_assessment_v2(submission: Mapping[str, object], llm: JsonLLMProvider | None = None) -> dict`
  - `score_questionnaire(questionnaire_answers) -> dict`
  - `evaluate_safety(narrative_text, confirmed_ocr_text, questionnaire_safety_flags) -> dict`
- Produces:
  - `AssessmentV2Request`
  - `AssessmentV2Response`
  - canonical `run_assessment_v2()` input/output accepted by those models

- [ ] **Step 1: Write failing schema tests**

Add tests equivalent to:

```python
def test_assessment_v2_request_uses_canonical_names():
    request = AssessmentV2Request.model_validate({
        "session_id": "sess_1",
        "user_id": "user_1",
        "document_id": "doc_1",
        "document_text": "已确认文本",
        "narrative_text": "最近睡眠不稳",
        "questionnaire_answers": complete_questionnaire(),
    })
    assert request.document_text == "已确认文本"
    assert request.questionnaire_answers


@pytest.mark.parametrize("old_name", ["document", "questionnaire"])
def test_assessment_v2_request_rejects_old_v2_names(old_name):
    payload = canonical_request()
    payload[old_name] = payload.pop(
        "document_text" if old_name == "document" else "questionnaire_answers"
    )
    with pytest.raises(ValidationError):
        AssessmentV2Request.model_validate(payload)


def test_assessment_v2_response_requires_new_profiles():
    result = run_assessment_v2(canonical_request(), llm=None)
    validated = AssessmentV2Response.model_validate(result)
    assert validated.analysis_mode == "document_narrative_questionnaire"
    assert "dimension_scores" in validated.emotion_profile.model_dump()
    assert "extracted_evidence" in result
    assert "dimensions" not in result
    assert "context" not in result
    assert "evidence" not in result
```

- [ ] **Step 2: Run the schema tests and verify RED**

Run:

```powershell
$tmp = Join-Path $env:TEMP ("harmony-assessment-schema-red-" + [guid]::NewGuid().ToString("N"))
python -m pytest tests/api/test_assessment_v2_schema.py -p no:cacheprovider --basetemp $tmp -q
```

Expected: collection or assertions fail because `assessment_v2` schemas and canonical fields do not exist.

- [ ] **Step 3: Implement strict Pydantic models**

Use `ConfigDict(extra="forbid")` and define:

```python
class AnalysisMode(str, Enum):
    DOCUMENT_NARRATIVE_QUESTIONNAIRE = "document_narrative_questionnaire"
    DOCUMENT_QUESTIONNAIRE = "document_questionnaire"
    NARRATIVE_QUESTIONNAIRE = "narrative_questionnaire"
    QUESTIONNAIRE_ONLY = "questionnaire_only"


class AssessmentV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    document_id: str | None = None
    document_text: str | None = None
    narrative_text: str | None = None
    questionnaire_answers: dict[str, object] | list[dict[str, object]]


class DegradationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triggered: bool
    reason_code: str | None
    fallback: str | None
```

Also define strict `SourceStatus`, `EmotionCandidate`, `EmotionProfile`, `PhysicalProfile`, `LifeEvents`, `EvidenceItem`, `ConflictItem`, and `AssessmentV2Response`. `AssessmentV2Response.status` accepts only `success`, `degraded`, and `blocked_safety`.

- [ ] **Step 4: Run schema-only tests and verify partial GREEN**

Expected: request tests pass; response test still fails because `run_assessment_v2()` returns the old V2 shape.

- [ ] **Step 5: Write failing Assessment behavior tests**

Parameterize the four canonical combinations:

```python
@pytest.mark.parametrize(
    ("document_text", "narrative_text", "expected_mode"),
    [
        ("病例已确认", "最近压力大", "document_narrative_questionnaire"),
        ("病例已确认", None, "document_questionnaire"),
        (None, "最近压力大", "narrative_questionnaire"),
        (None, None, "questionnaire_only"),
    ],
)
def test_canonical_analysis_modes(document_text, narrative_text, expected_mode):
    result = run_assessment_v2(
        canonical_request(
            document_text=document_text,
            narrative_text=narrative_text,
        ),
        llm=None,
    )
    assert result["analysis_mode"] == expected_mode
    AssessmentV2Response.model_validate(result)
```

Add assertions that:

- `emotion_profile.dimension_scores` equals the deterministic questionnaire scores;
- the two highest non-zero dimensions become `primary_states` in stable score/name order;
- remaining non-zero dimensions become `secondary_states`;
- `tcm_emotion_candidates == []` unless a validated candidate source exists;
- `physical_profile` contains `sleep_disturbance`, `low_energy`, `appetite_change`, and `physical_signals`;
- `life_events.triggers` comes only from validated model context;
- `safety_flags` contains fixed safety flags without raw text;
- blocked safety returns no normal extracted evidence.

- [ ] **Step 6: Run the focused Assessment tests and verify RED**

Run:

```powershell
$tmp = Join-Path $env:TEMP ("harmony-assessment-contract-red-" + [guid]::NewGuid().ToString("N"))
python -m pytest tests/ai_engine/test_assessment_v2.py tests/ai_engine/test_ai_degradation_v2.py `
  -p no:cacheprovider --basetemp $tmp -q
```

Expected: failures show old names (`document`, `questionnaire`, `dimensions`, `context`, `evidence`) and old analysis mode.

- [ ] **Step 7: Implement the canonical Assessment boundary**

Change validation to read:

```python
document_id = _optional_non_blank_text(submission.get("document_id"))
document_text = _optional_non_blank_text(submission.get("document_text"))
narrative_text = _optional_non_blank_text(submission.get("narrative_text"))
questionnaire = submission["questionnaire_answers"]
```

Keep the current internal model prompt contract if it remains useful, then convert the validated internal data once at the response boundary:

```python
result = {
    "agent_id": "assessment_agent",
    "session_id": session_id,
    "user_id": user_id,
    "status": status,
    "analysis_mode": analysis_mode,
    "sources_used": sources_used,
    "emotion_profile": _build_emotion_profile(dimensions),
    "physical_profile": _build_physical_profile(dimensions, physical_signals),
    "life_events": {"triggers": triggers},
    "assessment_summary": summary,
    "extracted_evidence": evidence,
    "conflicts": conflicts,
    "missing_information": missing_information,
    "safety_flags": safety["flags"],
    "degradation": _canonical_degradation(reason_codes),
    "warnings": _warning_messages(reason_codes),
    "disclaimer": _DISCLAIMER,
}
```

Use a fixed Chinese display-label map for questionnaire dimensions. Do not derive a TCM syndrome, organ, tone, or treatment from a single dimension.

Map degradation reasons deterministically:

- `LLM_NOT_CONFIGURED`, `LLM_TIMEOUT`, `LLM_INVALID_JSON`, `LLM_MISSING_FIELDS`, `LLM_SCHEMA_INVALID`, `LLM_PROVIDER_ERROR`, `LLM_UNEXPECTED_ERROR` → fallback `deterministic_questionnaire`;
- `SOURCE_CONFLICT` → fallback `review_required`;
- no reason → `triggered=false`, `reason_code=null`, `fallback=null`.

- [ ] **Step 8: Add privacy and abnormal-model tests**

Add a `caplog` test that uses unique sensitive strings and asserts they do not appear in log messages for:

- successful canonical Assessment;
- Qwen timeout;
- malformed JSON;
- missing model fields;
- safety block.

Keep the existing timeout, illegal JSON, missing-field, unknown-source, and prohibited-medical-field tests, updating only their expected canonical output.

- [ ] **Step 9: Run focused and full tests**

Run the Assessment tests with a fresh basetemp, then the complete suite with a second fresh basetemp.

Expected: both pass and `git diff --check` is clean.

- [ ] **Step 10: Commit**

```powershell
git add backend/app/schemas/assessment_v2.py backend/app/schemas/__init__.py `
  backend/ai_engine/assessment_v2.py tests/api/test_assessment_v2_schema.py `
  tests/ai_engine/test_assessment_v2.py tests/ai_engine/test_ai_degradation_v2.py
git commit -m "feat: migrate assessment v2 to canonical contract"
```

---

### Task 3: Migrate Diagnosis and Prescription consumers

**Files:**
- Modify: `backend/ai_engine/diagnosis_v2.py`
- Modify: `backend/ai_engine/prescription_v2.py`
- Modify: `tests/ai_engine/test_diagnosis_v2.py`

**Interfaces:**
- Consumes: canonical `AssessmentV2Response`
- Produces:
  - `run_diagnosis_v2(assessment: Mapping[str, object], llm=None) -> dict`
  - `run_prescription_v2(diagnosis: Mapping[str, object], knowledge=None) -> dict`

- [ ] **Step 1: Write failing canonical-consumer tests**

Replace Assessment fixtures with:

```python
assessment = {
    "status": "success",
    "emotion_profile": {
        "primary_states": ["紧张担忧", "反复思虑"],
        "secondary_states": [],
        "dimension_scores": {
            "tension_worry": 100,
            "overthinking": 75,
        },
        "tcm_emotion_candidates": [],
    },
    "physical_profile": {
        "sleep_disturbance": 50,
        "low_energy": 25,
        "appetite_change": 0,
        "physical_signals": ["fatigue"],
    },
    "life_events": {"triggers": ["考试压力"]},
    "extracted_evidence": [],
    "sources_used": [{"source": "questionnaire", "status": "used"}],
    "conflicts": [],
    "missing_information": ["document"],
    "degradation": {
        "triggered": False,
        "reason_code": None,
        "fallback": None,
    },
}
```

Assert that Diagnosis:

- reads only `emotion_profile.dimension_scores`;
- propagates canonical sources, conflicts, missing information, and degradation;
- produces no normal tendency when `blocked_safety`;
- does not use a model's numeric `confidence` as the returned medical confidence.

- [ ] **Step 2: Run and verify RED**

Expected: existing Diagnosis reads top-level `dimensions` and returns insufficient information.

- [ ] **Step 3: Implement the minimal consumer migration**

Read dimensions through a strict helper:

```python
emotion_profile = _mapping_or_default(
    assessment_data.get("emotion_profile"),
    {},
)
dimensions = _mapping_or_default(
    emotion_profile.get("dimension_scores"),
    {},
)
```

Rename propagated fields only where the new team contract requires it. Keep the current local candidate whitelist, two-independent-dimension threshold, Chroma/local fallback, warnings, and non-diagnostic disclaimer.

- [ ] **Step 4: Run focused and full tests**

Run `tests/ai_engine/test_diagnosis_v2.py` first, then the full suite with separate fresh basetemps.

- [ ] **Step 5: Commit**

```powershell
git add backend/ai_engine/diagnosis_v2.py backend/ai_engine/prescription_v2.py `
  tests/ai_engine/test_diagnosis_v2.py
git commit -m "feat: consume canonical assessment v2 profiles"
```

---

### Task 4: Migrate Music and Feedback to `music_id`

**Files:**
- Create: `backend/app/schemas/feedback_v2.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/ai_engine/music_agent.py`
- Modify: `backend/ai_engine/feedback_v2.py`
- Modify: `tests/ai_engine/test_music_agent.py`
- Modify: `tests/ai_engine/test_feedback_v2.py`
- Create: `tests/api/test_feedback_v2_schema.py`

**Interfaces:**
- Consumes:
  - Prescription V2 music parameters
  - local catalog records
  - explicit Feedback V2 payload
- Produces:
  - flat canonical Music result
  - `FeedbackV2Request` and `FeedbackV2Response`
  - Feedback records keyed by `music_id`

- [ ] **Step 1: Write failing Music contract tests**

Assert the exact required fields:

```python
result = match_music_v2(prescription, catalog=FIXED_CATALOG)
assert result["music_id"] == "music_gong_001"
assert result["source_type"] == "matched"
assert result["stream_url"].endswith(".wav")
assert result["mode"] == "宫调"
assert result["bpm"] == 58
assert result["duration_seconds"] == 900
assert result["instruments"] == ["古琴", "洞箫"]
assert "track" not in result
assert "track_id" not in result
assert "generation_mode" not in result
```

Also assert `source_type="generated"` is never returned and unsupported generation requests produce `MODE_NOT_AVAILABLE`.

- [ ] **Step 2: Run and verify Music RED**

Expected: failures identify the old nested track and `track_id` fields.

- [ ] **Step 3: Implement the flat Music response**

Map local catalog fields once:

```python
return {
    "agent_id": "music_agent",
    "legacy_alias": "generation_agent",
    "status": "success",
    "music_id": selected["music_id"],
    "title": selected["title"],
    "source_type": "matched",
    "stream_url": selected["stream_url"],
    "mode": selected["mode"],
    "bpm": selected["bpm"],
    "duration_seconds": selected["duration_seconds"],
    "instruments": list(selected["instruments"]),
    "ambient_sounds": list(selected.get("ambient_sounds", [])),
    "rights_note": selected["rights_note"],
    "match_explanation": explanations,
    "fallback_music_id": fallback_music_id,
}
```

Update the fixed catalog fixture to use canonical keys; preserve deterministic matching and catalog BPM validation.

- [ ] **Step 4: Write failing Feedback schema and behavior tests**

Define requests using `music_id`, and assert:

```python
request = FeedbackV2Request.model_validate({
    "session_id": "sess_1",
    "prescription_id": "rx_1",
    "music_id": "music_gong_001",
    "experience": valid_experience(),
})
assert request.music_id == "music_gong_001"

with pytest.raises(ValidationError):
    FeedbackV2Request.model_validate({
        **valid_feedback_request_without_music(),
        "track_id": "local_gong_001",
    })
```

Retain tests for `subjective_change`, `personal_preference_patch`, atomic `save_once`, duplicate submission, `global_rule_update=false`, non-finite scores, and optional `after` values.

- [ ] **Step 5: Run and verify Feedback RED**

Expected: old `track_id` records and missing Pydantic models fail.

- [ ] **Step 6: Implement Feedback schemas and `music_id` storage**

Use strict Pydantic models with `extra="forbid"`. Change V2 record construction and idempotency identity to use `music_id`. Do not adapt `SQLiteFeedbackStore`; continue requiring an injected repository with callable atomic `save_once`.

- [ ] **Step 7: Run focused and full tests**

Run Music, Feedback, and schema tests first; then the full suite with fresh basetemps.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/schemas/feedback_v2.py backend/app/schemas/__init__.py `
  backend/ai_engine/music_agent.py backend/ai_engine/feedback_v2.py `
  tests/ai_engine/test_music_agent.py tests/ai_engine/test_feedback_v2.py `
  tests/api/test_feedback_v2_schema.py
git commit -m "feat: align music and feedback v2 contracts"
```

---

### Task 5: Migrate the V2 workflow and add stability acceptance

**Files:**
- Modify: `backend/ai_engine/real_workflow.py`
- Modify: `tests/ai_engine/test_real_workflow_v2.py`
- Create: `tests/ai_engine/test_sprint3_v2_stability.py`

**Interfaces:**
- Consumes:
  - canonical Assessment request fields
  - canonical Music result
  - explicit Feedback payload and atomic repository
- Produces:
  - `run_real_workflow_v2(..., document_id=None, document_text=None, narrative_text=None, questionnaire_answers=..., assessment_confirmed=..., feedback_payload=None, feedback_repository=None) -> dict`

- [ ] **Step 1: Write failing workflow contract tests**

Call the wished-for signature:

```python
result = run_real_workflow_v2(
    session_id="sess_1",
    user_id="user_1",
    document_id="doc_1",
    document_text="已确认病例",
    narrative_text="最近压力大",
    questionnaire_answers=complete_questionnaire(),
    assessment_confirmed=True,
    llm=FixedJsonLLM(),
    catalog=FIXED_CATALOG,
)
assert result["assessment"]["analysis_mode"] == (
    "document_narrative_questionnaire"
)
assert result["music"]["source_type"] == "matched"
assert result["music"]["music_id"]
```

Keep and strengthen:

- `assessment_confirmed=false` stops before Diagnosis;
- `blocked_safety` stops before Diagnosis;
- `feedback_payload=None` uses a repository double whose any attribute access raises;
- explicit Feedback saves exactly once with `music_id`;
- old `run_real_workflow()` still writes its historical default four-star feedback.

- [ ] **Step 2: Run and verify workflow RED**

Expected: signature and old V2 field assertions fail; Sprint 2 regression tests still pass.

- [ ] **Step 3: Implement the canonical V2 workflow adapter**

Pass only canonical Assessment fields. Read the flat Music result and inject its `music_id` into explicit Feedback input when needed. Preserve `session_id`, `result_id`, Agent statuses, degradations, and stopping gates.

Do not call or probe `feedback_repository` when `feedback_payload is None`.

- [ ] **Step 4: Write the 10-run stability test**

Run the same offline questionnaire-only input 10 times with fixed LLM and catalog. Remove only intentionally unique fields such as `result_id`, then assert:

- all 10 runs finish;
- Agent status sequence is identical;
- Assessment deterministic scores are identical;
- `music_id`, `source_type`, BPM, and instruments are identical;
- no run submits Feedback without an explicit payload.

- [ ] **Step 5: Run focused and full tests**

Run workflow and stability tests, then the complete suite with fresh basetemps.

- [ ] **Step 6: Commit**

```powershell
git add backend/ai_engine/real_workflow.py `
  tests/ai_engine/test_real_workflow_v2.py `
  tests/ai_engine/test_sprint3_v2_stability.py
git commit -m "feat: migrate sprint3 v2 workflow contract"
```

---

### Task 6: Update handoff documentation and run final gates

**Files:**
- Modify: `docs/architecture/sprint3-ai-agent-v2-design.md`
- Modify or replace content in: `docs/sprint3-ai-agent-v2-design.md`
- Create: `.superpowers/sdd/2026-07-29-sprint3-v2-contract-migration/task-6-report.md`

**Interfaces:**
- Consumes: final canonical Pydantic models and passing tests
- Produces: Backend/Frontend/Knowledge handoff package and final verification evidence

- [ ] **Step 1: Update the handoff contract examples**

Document:

- canonical Assessment request and response;
- four `analysis_mode` values;
- all status and degradation fields;
- flat Music response and `source_type=matched` explanation;
- Feedback `music_id`, explicit submission, atomic `save_once`, and `global_rule_update=false`;
- fixed mock request/response for Frontend;
- safety reason codes and non-diagnostic wording for Knowledge;
- Backend responsibilities not implemented in this AI branch.

- [ ] **Step 2: Run final full verification**

Run:

```powershell
$tmp = Join-Path $env:TEMP ("harmony-sprint3-final-" + [guid]::NewGuid().ToString("N"))
python -m pytest -p no:cacheprovider --basetemp $tmp -q
git diff --check 90b6537..HEAD
```

- [ ] **Step 3: Run sensitive-information scans**

Search tracked changes for:

- private key headers;
- access tokens and API keys;
- passwords or DSNs with credentials;
- absolute local paths;
- complete demo case text accidentally copied into logs;
- `.env` values other than safe placeholders.

Use read-only searches and record findings. Do not delete files in bulk.

- [ ] **Step 4: Record final evidence**

The report must include:

- merge baseline and all task commit SHAs;
- focused and full test commands with counts;
- 10-run stability result;
- sensitive scan result;
- `git diff --check` result;
- deferred limitations, including missing transactional `SQLiteFeedbackStore.save_once`;
- exact untracked `.test-*` directories intentionally left untouched.

- [ ] **Step 5: Commit documentation**

```powershell
git add docs/architecture/sprint3-ai-agent-v2-design.md `
  docs/sprint3-ai-agent-v2-design.md `
  .superpowers/sdd/2026-07-29-sprint3-v2-contract-migration/task-6-report.md
git commit -m "docs: update sprint3 v2 integration handoff"
```

- [ ] **Step 6: Request final whole-branch review**

Generate a review package from the merge base recorded after Task 1 through HEAD. The reviewer must check:

- exact agreement with remote V2 contract names;
- no Sprint 2 regression;
- no automatic V2 Feedback;
- safety and confirmation stopping gates;
- Pydantic strictness;
- privacy and degradation handling;
- Music is local `matched`, never described as generated.

Critical and Important findings must be fixed and re-reviewed before presenting merge or push options.
