# S4-04 AI Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Each step is independently testable and should be tracked with a checkbox.

**Goal:** 在不破坏 Sprint 2/3 的前提下，完成 Qwen Provider 工程化、问卷三版本支持、自由文本证据提取、Assessment 多源融合、Diagnosis abstain 和 Sprint 4 评估链路。

**Architecture:** 采用“确定性规则 + 受约束 Provider”架构。安全、问卷评分、证据合并、冲突检测、追问决策、候选白名单和 abstain 由本地代码负责；Qwen 只负责结构化提取和候选排序。所有模块通过 `sprint4_contracts.py` 中的 canonical 类型交换数据。

**Tech Stack:** Python 3、现有 `backend.ai_engine` 模块、pytest、JSON Schema 约束、Qwen OpenAI-compatible HTTP 接口、现有 Prompt Engine 和 Mock Provider。

## Global Constraints

- 必须同时保留 `questionnaire_v2.0`、`questionnaire_v2.1` 和 `quick_state_v1`。
- 有效自由文本必须尝试 Qwen；失败要返回 `unavailable`/`degraded`，不能静默当成无输入。
- 每条主要结论必须关联 `source_type` 和 `source_ref`；无依据结论率目标 ≤5%。
- 安全规则必须在 Provider 调用前执行；`blocked_safety` 不进入 Diagnosis、Prescription 或 Music。
- Diagnosis 只能从 `MVP_SYNDROMES` 白名单选择；LLM 不能创建新倾向。
- Evidence Coverage 使用 `(有证据维度数/总维度数) × min(1.0, source_type数/3)`。
- 追问契约最多 6 道；首版决策树默认最多输出 4 道并按优先级去重。
- 不记录 API Key、病例全文、自由描述全文、原始 OCR 全文或 Prompt 原文。
- 不删除 Sprint 2/3 入口，不新增真实音乐生成能力。

---

## Shared Test Fixtures

为避免每个测试文件各自拼装不一致的输入，Task 2、Task 3 和 Task 8 必须提供以下可复用测试构造器：

这些构造器的具体约束固定为：`valid_v21_envelope()` 从 `questionnaire_v2.py` 暴露的 V2.1 题目 ID 生成 20 条合法答案，并同时设置 Q03 与 Q04 以验证 Q04 不 double-count；`valid_quick_state_envelope()` 生成 6 条 0-10 合法答案；`valid_v20_inputs()` 复用现有 V2.0 测试工厂；`successful_provider()` 返回 Task 2 的 `MockProvider`；`provider_that_must_not_be_called()` 的调用即抛出 AssertionError。每个函数都必须返回真实可通过 Schema 校验的对象，而不是空字典或 `None`。

| Helper | 必须返回的内容 |
|---|---|
| `valid_v21_envelope()` | 从 `questionnaire_v2.py` 暴露的 V2.1 题目 ID 生成 20 条合法答案，并同时设置 Q03 与 Q04 以验证 Q04 不 double-count。 |
| `valid_quick_state_envelope()` | 生成 6 条 0-10 合法答案，包含目标字段。 |
| `valid_v20_inputs()` | 复用现有 V2.0 测试工厂，不能改变旧测试数据。 |
| `valid_v21_inputs()` | 返回可直接进入 V2.1 工作流的完整输入。 |
| `successful_provider()` | 返回 Task 2 的 `MockProvider`，成功响应包含可校验的结构化证据。 |
| `provider_that_must_not_be_called()` | 任何调用立即抛出 `AssertionError`，用于验证安全和确认门禁。 |
| `expected_q03_score()` | 从 S4-02 评分 JSON 读取 Q03 单独计入的期望分数，避免测试硬编码错误权重。 |
| `valid_sleep_and_negation_payload()` | 返回包含睡眠证据、否定身体信号、短 quote 和时间范围的合法 Provider JSON。 |
| `three_source_submission()` | 包含有效问卷、自由描述和已确认材料，三类来源均能产出 EvidenceItem。 |
| `conflicting_incomplete_submission()` | 包含问卷/文本冲突、缺少持续时间和生活影响，触发固定追问顺序。 |
| `confirmed_assessment_with_conflict()` | 包含用户已确认、一个可排序候选以及一条反对证据。 |
| `unconfirmed_assessment()` | `requires_user_confirmation=true` 且 `confirmation_status` 不是 `confirmed`。 |

## Task 1: 建立 Sprint 4 canonical 类型和错误码

**Files:**
- Create: `backend/ai_engine/sprint4_contracts.py`
- Test: `tests/ai_engine/test_sprint4_contracts.py`

**Interfaces:**
- Produces: `EvidenceItem`, `Conflict`, `MissingInformation`, `FollowUpQuestion`, `AssessmentRevision`, `ProviderRequest`, `ProviderResponse`, `ProviderError` 的 TypedDict/dataclass 结构。
- Consumes: `docs/sprint4/assessment-contract-v2.1.md` 的枚举和字段定义。

- [ ] **Step 1: Write the failing test**

```python
def test_provider_error_exposes_machine_readable_code_and_retryability():
    from backend.ai_engine.sprint4_contracts import ProviderError

    error = ProviderError(
        reason_code="TIMEOUT",
        retryable=True,
        user_message="文本分析暂时超时，请稍后重试。",
    )

    assert error.reason_code == "TIMEOUT"
    assert error.retryable is True
    assert error.user_message
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest -q tests/ai_engine/test_sprint4_contracts.py::test_provider_error_exposes_machine_readable_code_and_retryability`

Expected: FAIL because `backend.ai_engine.sprint4_contracts` does not exist.

- [ ] **Step 3: Write the minimal implementation**

Implement immutable dataclasses for Provider request/response/error and TypedDict-style canonical evidence records. Use exact enum values from the Assessment V2.1 contract: `questionnaire`, `narrative`, `document`, `user_follow_up`, `user_correction`; do not silently coerce unknown values.

- [ ] **Step 4: Run focused tests**

Run: `pytest -q tests/ai_engine/test_sprint4_contracts.py`

Expected: PASS, including required-field, enum, confidence-range and evidence-source-reference tests.

- [ ] **Step 5: Commit the isolated contract change**

```bash
git add backend/ai_engine/sprint4_contracts.py tests/ai_engine/test_sprint4_contracts.py
git commit -m "feat: add sprint4 canonical AI contracts"
```

## Task 2: 工程化 Qwen Provider，并保留同步兼容入口

**Files:**
- Modify: `backend/ai_engine/providers.py`
- Modify: `backend/ai_engine/sprint4_contracts.py`
- Test: `tests/ai_engine/test_providers.py`
- Test: `tests/ai_engine/test_sprint4_provider.py`

**Interfaces:**
- Consumes: `ProviderRequest` from Task 1.
- Produces: `AsyncJsonProvider.complete_json(request) -> ProviderResponse`, `MockProvider`, `QwenCompatibleProvider` and a named sync adapter for existing V2.0/V2.1 callers.

- [ ] **Step 1: Write failing tests for success and structured failure**

```python
import pytest


@pytest.mark.asyncio
async def test_mock_provider_returns_metadata_and_records_call():
    from backend.ai_engine.providers import MockProvider
    from backend.ai_engine.sprint4_contracts import ProviderRequest

    provider = MockProvider({"items": []})
    response = await provider.complete_json(
        ProviderRequest(
            system_prompt="system",
            user_prompt="user",
            operation="narrative_extraction",
            prompt_version="assessment_v2.1",
        )
    )

    assert response.data == {"items": []}
    assert response.attempts == 1
    assert provider.calls == 1
```

```python
@pytest.mark.asyncio
async def test_timeout_is_classified_and_retried_once():
    from backend.ai_engine.providers import MockProvider
    from backend.ai_engine.sprint4_contracts import ProviderError, ProviderRequest

    provider = MockProvider(error=ProviderError("TIMEOUT", True, "分析超时"))
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete_json(
            ProviderRequest("system", "user", "narrative_extraction", "assessment_v2.1")
        )

    assert exc_info.value.reason_code == "TIMEOUT"
    assert provider.calls == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest -q tests/ai_engine/test_sprint4_provider.py`

Expected: FAIL because the async Provider and Mock Provider do not expose the required interface.

- [ ] **Step 3: Implement the minimal Provider gateway**

Implement:

1. `QwenCompatibleProvider.complete_json` as an async method using the existing OpenAI-compatible `/chat/completions` payload.
2. Retry only `NETWORK`, `5XX`, and `RATE_LIMIT`; allow one short retry for `TIMEOUT`; do not retry schema errors indefinitely.
3. Parse one JSON object, attempt one fenced-content repair, and classify remaining failures as `INVALID_JSON`.
4. Record `provider`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, and `attempts` without recording prompts or sensitive text.
5. Add `SyncJsonProviderAdapter` for existing functions that still call `complete_json(system_prompt, user_prompt)`.

- [ ] **Step 4: Run focused and legacy tests**

Run: `pytest -q tests/ai_engine/test_sprint4_provider.py tests/ai_engine/test_providers.py tests/ai_engine/test_assessment_v2.py`

Expected: PASS; existing Sprint 3 Provider and Assessment tests remain green.

- [ ] **Step 5: Commit**

```bash
git add backend/ai_engine/providers.py backend/ai_engine/sprint4_contracts.py tests/ai_engine/test_providers.py tests/ai_engine/test_sprint4_provider.py
git commit -m "feat: harden qwen provider with async retries"
```

## Task 3: 扩展 Questionnaire V2.1 和 Quick State 分发

**Files:**
- Modify: `backend/ai_engine/questionnaire_v2.py`
- Consume: `knowledge/questionnaire-v2.1.json`
- Consume: `knowledge/questionnaire-scoring-v2.1.json`
- Consume: `knowledge/quick-state-questionnaire-v1.json`
- Test: `tests/ai_engine/test_questionnaire_v2.py`
- Test: `tests/ai_engine/test_questionnaire_v21.py`

**Interfaces:**
- Consumes: S4-02 的问卷内容和评分 JSON。
- Produces: `score_questionnaire_v21(envelope)`, `score_quick_state(envelope)`；旧 `score_questionnaire` 继续接受 V2.0。

- [ ] **Step 1: Write failing version-dispatch tests**

```python
def test_v21_dispatch_scores_twenty_questions_without_using_q04_twice():
    from backend.ai_engine.questionnaire_v2 import score_questionnaire_v21

    result = score_questionnaire_v21(valid_v21_envelope())

    assert result.schema_version == "questionnaire_v2.1"
    assert result.questions_answered == 20
    assert result.dimension_scores["tension_worry"].q04_qualitative is not None
    assert result.dimension_scores["tension_worry"].weighted_score == expected_q03_score()
```

```python
def test_quick_state_requires_six_items_and_0_to_10_values():
    from backend.ai_engine.questionnaire_v2 import score_quick_state

    result = score_quick_state(valid_quick_state_envelope())
    assert result.schema_version == "quick_state_v1"
    assert result.goal
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `pytest -q tests/ai_engine/test_questionnaire_v21.py`

Expected: FAIL because the V2.1 and Quick State functions do not exist.

- [ ] **Step 3: Implement version-aware validators and scorers**

Use the envelope `schema_version` as the only dispatcher. Keep V2.0 validation and output byte-compatible with existing tests. For V2.1, load scoring weights from the JSON file, store Q04 as qualitative metadata, and emit deterministic dimension scores. For Quick State, preserve 0-10 values and mark the result as a transient `quick_state` source.

- [ ] **Step 4: Run all questionnaire tests**

Run: `pytest -q tests/ai_engine/test_questionnaire_v2.py tests/ai_engine/test_questionnaire_v21.py`

Expected: PASS for V2.0 regression, V2.1 validation, Quick State validation, duplicate IDs, missing IDs, invalid ranges and safety fields.

- [ ] **Step 5: Commit**

```bash
git add backend/ai_engine/questionnaire_v2.py tests/ai_engine/test_questionnaire_v2.py tests/ai_engine/test_questionnaire_v21.py
git commit -m "feat: support questionnaire v21 and quick state"
```

## Task 4: 建立 Narrative Schema 和版本化 Prompt

**Files:**
- Create: `backend/ai_engine/narrative_schema.py`
- Create: `prompt/assessment/narrative_extraction_v2.1.json`
- Create: `prompt/assessment/conflict_normalization_v2.1.json`
- Test: `tests/ai_engine/test_narrative_schema.py`

**Interfaces:**
- Consumes: `AsyncJsonProvider` from Task 2 and canonical evidence types from Task 1.
- Produces: `extract_narrative(text, source_type, provider) -> NarrativeExtractionResult`.

- [ ] **Step 1: Write failing extraction tests**

```python
@pytest.mark.asyncio
async def test_extraction_keeps_quote_time_window_and_negation():
    from backend.ai_engine.narrative_schema import extract_narrative

    result = await extract_narrative(
        "最近两周晚上睡不好，但没有胸痛。",
        source_type="narrative",
        provider=MockProvider(valid_sleep_and_negation_payload()),
    )

    assert result.status == "processed"
    assert result.evidence_quotes[0].quote in "最近两周晚上睡不好，但没有胸痛。"
    assert any(item.negated for item in result.items)
```

- [ ] **Step 2: Run the test to verify failure**

Run: `pytest -q tests/ai_engine/test_narrative_schema.py`

Expected: FAIL because `narrative_schema.py` is not present.

- [ ] **Step 3: Implement schema validation and normalization**

Validate the 13 allowed categories, confidence range `[0, 1]`, non-empty quote for `narrative`/`document`, source reference, time window, polarity, negation and safety flags. Reject unknown fields or unknown enum values before returning an EvidenceItem. A Provider failure returns a result with `status=unavailable|degraded`, `reason_code` and no fabricated evidence.

- [ ] **Step 4: Add prompt files and test prompt version propagation**

Each prompt file must declare `prompt_version`, allowed output fields, enum lists, prohibited medical language and one valid JSON example. The extraction result must carry the exact prompt version into `model_metadata`.

- [ ] **Step 5: Run focused tests**

Run: `pytest -q tests/ai_engine/test_narrative_schema.py tests/ai_engine/test_sprint4_provider.py`

Expected: PASS for 13 categories, quote traceability, negation, time windows, invalid JSON, unavailable Provider and prompt-version propagation.

- [ ] **Step 6: Commit**

```bash
git add backend/ai_engine/narrative_schema.py prompt/assessment tests/ai_engine/test_narrative_schema.py
git commit -m "feat: add grounded narrative extraction schema"
```

## Task 5: 实现 Assessment 多源融合、冲突和追问决策树

**Files:**
- Modify: `backend/ai_engine/assessment_v2.py`
- Modify: `backend/ai_engine/sprint4_contracts.py`
- Test: `tests/ai_engine/test_assessment_v2.py`
- Test: `tests/ai_engine/test_assessment_v21.py`

**Interfaces:**
- Consumes: V2.1/Quick State scores from Task 3, narrative results from Task 4 and existing `evaluate_safety`.
- Produces: `run_assessment_v21(submission, provider) -> dict` with `evidence_items`, `conflicts`, `missing_information`, `follow_up_questions`, `evidence_coverage_score`, `revision` and `requires_user_confirmation`.

- [ ] **Step 1: Write failing fusion and gate tests**

```python
def test_assessment_calculates_coverage_from_dimensions_and_source_diversity():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(three_source_submission(), provider=successful_provider())

    assert result["evidence_coverage_score"] == pytest.approx(1.0)
    assert result["requires_user_confirmation"] is True
    assert all(item["source_type"] for item in result["evidence_items"])
```

```python
def test_assessment_uses_deterministic_follow_up_priority_and_caps_initial_output():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(conflicting_incomplete_submission(), provider=successful_provider())

    assert result["status"] == "needs_follow_up"
    assert len(result["follow_up_questions"]) <= 4
    assert result["follow_up_questions"][0]["trigger_reason"] in {
        "duration_unclear", "impact_unclear", "source_conflict"
    }
```

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `pytest -q tests/ai_engine/test_assessment_v21.py`

Expected: FAIL because `run_assessment_v21` and the canonical V2.1 fields are not implemented.

- [ ] **Step 3: Implement source normalization and deterministic questionnaire evidence**

Run safety before Provider calls. Convert V2.1 scores, Quick State, narrative items and confirmed document items into EvidenceItem records. Do not include unconfirmed OCR text. Preserve per-source processing status even when extraction fails.

- [ ] **Step 4: Implement conflict and coverage calculation**

Group evidence by canonical dimension. Mark conflicting values without choosing a winner. Count only valid evidence toward dimension coverage and use the exact three-source formula from the design document.

- [ ] **Step 5: Implement the fixed follow-up decision tree and revisions**

Apply priority `duration → impact → conflict → candidate distinction → physical confirmation → supplementary context`, deduplicate by dimension, emit at most four initial questions, and return `needs_follow_up`. A follow-up answer or user correction creates a new revision and preserves the previous revision in the result metadata.

- [ ] **Step 6: Run the complete Assessment regression suite**

Run: `pytest -q tests/ai_engine/test_assessment_v2.py tests/ai_engine/test_assessment_v21.py`

Expected: PASS for V2.0 legacy behavior, V2.1 evidence, provider failure visibility, safety-first execution, conflicts, missing data, follow-up ordering, revision and confirmation gate.

- [ ] **Step 7: Commit**

```bash
git add backend/ai_engine/assessment_v2.py backend/ai_engine/sprint4_contracts.py tests/ai_engine/test_assessment_v2.py tests/ai_engine/test_assessment_v21.py
git commit -m "feat: add sprint4 evidence fusion and followups"
```

## Task 6: 增强 Diagnosis 候选、支持/反对证据和 abstain

**Files:**
- Modify: `backend/ai_engine/diagnosis_v2.py`
- Create: `prompt/diagnosis/candidate_rank_v2.1.json`
- Test: `tests/ai_engine/test_diagnosis_v2.py`
- Test: `tests/ai_engine/test_diagnosis_v21.py`

**Interfaces:**
- Consumes: confirmed Assessment V2.1 from Task 5 and `MVP_SYNDROMES` local whitelist.
- Produces: `run_diagnosis_v21(assessment, provider) -> dict` with `candidate_tendencies`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `abstained`, `abstain_reason` and `assessment_revision`.

- [ ] **Step 1: Write failing abstain and candidate tests**

```python
def test_diagnosis_returns_supported_candidates_with_supporting_and_contradicting_evidence():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v21

    result = run_diagnosis_v21(confirmed_assessment_with_conflict(), provider=None)

    assert result["abstained"] is False
    candidate = result["candidate_tendencies"][0]
    assert candidate["supporting_evidence_ids"]
    assert candidate["contradicting_evidence_ids"]
```

```python
def test_diagnosis_abstains_before_provider_when_assessment_is_unconfirmed():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v21

    result = run_diagnosis_v21(unconfirmed_assessment(), provider=provider_that_must_not_be_called())

    assert result["abstained"] is True
    assert result["abstain_reason"] == "ASSESSMENT_NOT_CONFIRMED"
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `pytest -q tests/ai_engine/test_diagnosis_v21.py`

Expected: FAIL because the V2.1 candidate and abstain fields are not present.

- [ ] **Step 3: Implement local candidate generation**

Generate candidates only when at least two independent dimensions or one dimension plus an independent text/document evidence item support the whitelist rule. Attach evidence IDs, not raw text, to each candidate.

- [ ] **Step 4: Implement abstain gates and optional Provider ranking**

Return `abstained=true` for safety block, unconfirmed Assessment, low evidence coverage without independent support, or unresolved major conflict. If Provider is available, pass only candidate IDs and compact evidence summaries; reject unknown IDs and unsupported candidates, then retain local ranking on any Provider failure.

- [ ] **Step 5: Run Diagnosis and Prescription compatibility tests**

Run: `pytest -q tests/ai_engine/test_diagnosis_v2.py tests/ai_engine/test_diagnosis_v21.py tests/ai_engine/test_sprint3_v2_stability.py`

Expected: PASS; old `primary_tendency` remains available for legacy callers, while new callers consume `candidate_tendencies`. Withheld Prescription behavior remains unchanged for safety, low confidence and abstained results.

- [ ] **Step 6: Commit**

```bash
git add backend/ai_engine/diagnosis_v2.py prompt/diagnosis/candidate_rank_v2.1.json tests/ai_engine/test_diagnosis_v2.py tests/ai_engine/test_diagnosis_v21.py
git commit -m "feat: add diagnosis evidence and abstention"
```

## Task 7: 建立 60 案例评估脚本和指标实现

**Files:**
- Create: `evals/metrics.py`
- Create: `evals/run_sprint4_eval.py`
- Consume: `evals/sprint4/cases.jsonl`
- Consume: `evals/sprint4/safety-cases.jsonl`
- Test: `tests/evals/test_sprint4_metrics.py`
- Test: `tests/evals/test_run_sprint4_eval.py`

**Interfaces:**
- Consumes: Assessment/Diagnosis results from Tasks 5-6 and JSONL gold labels from S4-02.
- Produces: JSON report with schema rate, processing rate, evidence citation accuracy, unsupported conclusion rate, F1, conflict rate, safety recall, abstain accuracy and Provider error explainability.

- [ ] **Step 1: Write failing metric tests**

```python
def test_evidence_coverage_uses_source_diversity_factor():
    from evals.metrics import evidence_coverage

    assert evidence_coverage(3, 6, {"questionnaire"}) == pytest.approx(0.25)
    assert evidence_coverage(6, 6, {"questionnaire", "narrative", "document"}) == pytest.approx(1.0)
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `pytest -q tests/evals/test_sprint4_metrics.py`

Expected: FAIL because the `evals` metric module is not present.

- [ ] **Step 3: Implement pure metric functions**

Implement pure functions for coverage, exact source citation, unsupported claims, extraction F1, conflict detection, safety recall, abstain classification and provider error explainability. Keep metrics independent of network and real Qwen credentials.

- [ ] **Step 4: Implement the CLI runner with Mock Provider default**

`python evals/run_sprint4_eval.py --cases evals/sprint4/cases.jsonl --safety-cases evals/sprint4/safety-cases.jsonl --output reports/sprint4-eval.json` must run offline, identify each case by ID, and write aggregate results without persisting source text.

- [ ] **Step 5: Run eval tests and a sample report**

Run: `pytest -q tests/evals/test_sprint4_metrics.py tests/evals/test_run_sprint4_eval.py`

Then run: `python evals/run_sprint4_eval.py --cases evals/sprint4/cases.jsonl --safety-cases evals/sprint4/safety-cases.jsonl --output reports/sprint4-eval.json`

Expected: PASS and a report containing all required metrics with no API key requirement.

- [ ] **Step 6: Commit**

```bash
git add evals/metrics.py evals/run_sprint4_eval.py tests/evals
git commit -m "test: add sprint4 understanding evaluation"
```

## Task 8: 集成联调、隐私检查和发布门禁

**Files:**
- Modify: `backend/ai_engine/real_workflow.py` or the current V2 workflow adapter only where required for explicit V2.1 opt-in.
- Modify: `tests/ai_engine/test_real_workflow_v2.py`
- Create: `tests/integration/test_sprint4_ai_understanding.py`
- Create: `docs/sprint4/s4-04-validation-report.md`

**Interfaces:**
- Consumes: Tasks 1-7.
- Produces: An opt-in V2.1 path that preserves Sprint 2/3 paths and a reproducible validation report for the integration PR.

- [ ] **Step 1: Write the integration contract tests**

```python
def test_v21_workflow_requires_confirmation_before_diagnosis():
    result = run_v21_workflow(valid_v21_inputs(), confirmed=False)

    assert result["assessment"]["requires_user_confirmation"] is True
    assert result["diagnosis"] is None
```

```python
def test_legacy_v2_workflow_remains_available():
    result = run_real_workflow_v2(valid_v20_inputs())
    assert result["assessment"]["analysis_mode"] == "questionnaire_only"
```

- [ ] **Step 2: Run integration tests to identify missing wiring**

Run: `pytest -q tests/integration/test_sprint4_ai_understanding.py tests/ai_engine/test_real_workflow_v2.py`

Expected: Any failure must point to an explicit adapter or contract mismatch; do not weaken assertions to make the test pass.

- [ ] **Step 3: Add explicit V2.1 opt-in wiring**

Wire the new Assessment and Diagnosis functions behind a named V2.1 path. Do not change the default V2.0 path, auto-submit Feedback, safety gate or confirmation semantics. Keep Provider and evaluation metadata available to the caller, not to ordinary logs.

- [ ] **Step 4: Run the full validation matrix**

Run:

```bash
pytest -q tests/ai_engine tests/api tests/integration
python evals/run_sprint4_eval.py --cases evals/sprint4/cases.jsonl --safety-cases evals/sprint4/safety-cases.jsonl --output reports/sprint4-eval.json
git diff --check
```

Expected: all existing tests pass, evaluation report is generated offline, safety cases have 100% recall, and `git diff --check` is clean.

- [ ] **Step 5: Write the validation report**

Record exact commands, pass counts, metric values, Provider failure cases, one safety-block case, one abstain case, one conflict case and confirmation-gate evidence. Do not include raw user text.

- [ ] **Step 6: Commit the integration evidence**

```bash
git add tests/integration/test_sprint4_ai_understanding.py tests/ai_engine/test_real_workflow_v2.py docs/sprint4/s4-04-validation-report.md
git commit -m "test: validate sprint4 ai understanding integration"
```

## Definition of Done

- [ ] GitHub #55 的所有交付物都有实现或明确的跨任务依赖。
- [ ] V2.0、V2.1、Quick State 三种输入契约均有测试。
- [ ] 有效自由文本不会静默丢弃；Provider 失败可解释且可降级。
- [ ] 每条主要结论有 evidence ID、来源类型和来源引用。
- [ ] Assessment 支持冲突、缺失、追问和 Revision；用户确认前不进入 Diagnosis。
- [ ] Diagnosis 支持候选列表、支持/反对证据和 abstain。
- [ ] 60 案例评估脚本可离线运行并生成全部指标。
- [ ] Sprint 2/3 回归通过，敏感原文不进入普通日志。
- [ ] 目标分支为 `feat/s4-ai-understanding`，通过 Review 后再进入 `integration/sprint4-real-input`。

## Execution Handoff

该方案建议按 Task 1 → Task 8 顺序执行，每个 Task 独立测试并单独提交；在 Task 5 和 Task 8 设置团队 Review 门。当前阶段只完成设计和方案，不自动开始代码实现、不提交 GitHub PR。
