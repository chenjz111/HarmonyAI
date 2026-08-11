# Sprint 4 收尾验收与发布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Sprint 4 的资产校验、预测结果生成接口、严格评估、发布门禁和验收报告，使 60 个正式案例可以被真实执行并产生可审计结论。

**Architecture:** 在现有 `evals.metrics` 和 `evals.run_sprint4_eval` 之上增加独立的资产校验、预测适配器和发布校验层。预测适配器只负责把案例转换为标准 `predicted`，评估层只消费预测文件并计算指标，验收编排层负责运行门禁与生成报告；缺少预测、Provider 未配置或 Schema 无效时显式阻塞，不把 0 分伪装成模型结果。

**Tech Stack:** Python 3.10+, pytest, JSON/JSONL, 现有 `backend.ai_engine` Assessment/Provider 接口，现有 `evals.metrics`。

## Global Constraints

- 不修改 Frozen Contract、20 题问卷、评分规则或 60 个原始标注案例。
- 正常日志不得包含用户原文、OCR 原文、Prompt 或 API 密钥。
- Safety 案例必须进入 Safety Gate；安全召回低于 100% 时发布状态为 `blocked`。
- `evidence_coverage_score` 只表示维度覆盖；source diversity 作为独立字段和独立指标。
- 评估输入缺少 `predicted`、案例数量不符或预测 Schema 无效时必须抛出明确错误。
- 每个实现任务遵循 TDD：先写失败测试，再实现最小代码，再运行相关测试和回归测试。
- 文档和评估产物放在 `docs/sprint4/`、`evals/sprint4/` 或运行时指定的 artifacts 目录，不创建 `docs/superpowers/`。

---

### Task 1: 正式资产一致性校验

**Files:**
- Create: `evals/sprint4/asset_validation.py`
- Create: `tests/evals/test_sprint4_asset_validation.py`

**Interfaces:**
- Produces `validate_assets(questionnaire_path, scoring_path, cases_path, safety_cases_path) -> dict[str, object]`。
- 返回字段：`question_count`、`case_count`、`safety_case_count`、`total_case_count`、`questionnaire_schema_version`、`errors`。
- 校验失败抛出 `AssetValidationError`，错误消息只包含文件路径、字段名和计数，不包含案例原文。

- [ ] **Step 1: Write the failing tests**

```python
def test_validate_assets_accepts_frozen_20_55_5_assets():
    report = validate_assets(
        questionnaire_path=ROOT / "knowledge/questionnaire-v2.1.json",
        scoring_path=ROOT / "knowledge/questionnaire-scoring-v2.1.json",
        cases_path=ROOT / "evals/sprint4/cases.jsonl",
        safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
    )
    assert report["question_count"] == 20
    assert report["case_count"] == 55
    assert report["safety_case_count"] == 5
    assert report["total_case_count"] == 60
    assert report["errors"] == []


def test_validate_assets_rejects_duplicate_case_ids(tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        '{"case_id":"C001","input":{},"expected":{}}\n'
        '{"case_id":"C001","input":{},"expected":{}}\n',
        encoding="utf-8",
    )
    with pytest.raises(AssetValidationError, match="duplicate case_id"):
        validate_assets(
            questionnaire_path=ROOT / "knowledge/questionnaire-v2.1.json",
            scoring_path=ROOT / "knowledge/questionnaire-scoring-v2.1.json",
            cases_path=cases,
            safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
        )
```

- [ ] **Step 2: Run the tests to verify the missing validator fails**

Run: `pytest tests/evals/test_sprint4_asset_validation.py -q`

Expected: FAIL because `evals.sprint4.asset_validation` does not exist.

- [ ] **Step 3: Implement the minimal validator**

Implement `_read_json`, `_read_jsonl`, `_require_count`, and duplicate-ID checks. Require `questionnaire_v2.1`, exactly 20 questions, exactly 55 normal cases, exactly 5 safety cases, `input` and `expected` on every case, and `safety_expected == "block"` on every safety case. Return the count report only after all checks pass.

- [ ] **Step 4: Run the focused and contract tests**

Run: `pytest tests/evals/test_sprint4_asset_validation.py tests/contract/test_frozen_contracts.py -q`

Expected: all focused tests pass and the existing Frozen Contract tests remain green.

- [ ] **Step 5: Commit the task**

```powershell
git add evals/sprint4/asset_validation.py tests/evals/test_sprint4_asset_validation.py
git commit -m "feat: validate Sprint 4 evaluation assets"
```

### Task 2: 预测结果契约与可注入生成器

**Files:**
- Create: `evals/sprint4/prediction_schema.py`
- Create: `evals/sprint4/generate_predictions.py`
- Create: `tests/evals/test_sprint4_predictions.py`

**Interfaces:**
- `PredictionAdapter` protocol：`predict(case: Mapping[str, object]) -> Mapping[str, object]`。
- `validate_prediction(prediction) -> None`：校验 `status`、`evidence_items`、`candidate_tendencies`、`abstained`、`safety_flags` 和错误字段。
- `generate_predictions(cases_path, safety_cases_path, output_path, adapter) -> dict[str, object]`：输出独立 JSONL，不覆盖原始标注集。
- 无真实 Adapter 时使用 `UnavailableAdapter`，每个案例输出 `status="unavailable"`、`reason_code="PREDICTION_PROVIDER_REQUIRED"`，并且不复制用户原文。

- [ ] **Step 1: Write the failing tests**

```python
def test_prediction_schema_rejects_missing_status():
    with pytest.raises(PredictionValidationError, match="status"):
        validate_prediction({"evidence_items": []})


def test_generator_writes_one_sanitized_prediction_per_case(tmp_path):
    output = tmp_path / "predictions.jsonl"
    report = generate_predictions(
        cases_path=ROOT / "evals/sprint4/cases.jsonl",
        safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
        output_path=output,
        adapter=UnavailableAdapter(),
    )
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert report["case_count"] == 55
    assert report["safety_case_count"] == 5
    assert len(rows) == 60
    assert all(row["predicted"]["status"] == "unavailable" for row in rows)
    assert all("narrative_text" not in row["predicted"] for row in rows)
```

- [ ] **Step 2: Run the tests to verify the generator contract fails**

Run: `pytest tests/evals/test_sprint4_predictions.py -q`

Expected: FAIL because the prediction schema and generator are not present.

- [ ] **Step 3: Implement validation and the adapter boundary**

Define the allowed statuses as `success`, `degraded`, `needs_follow_up`, `blocked_safety`, and `unavailable`. Require list types for evidence and candidate fields, require boolean `abstained`, and allow `reason_code` only as a non-empty string. The generator writes only `case_id`, `type`, `predicted`, and a `prediction_metadata` object containing adapter name and status; it never copies `input` into the output.

- [ ] **Step 4: Run the focused tests**

Run: `pytest tests/evals/test_sprint4_predictions.py -q`

Expected: all prediction tests pass with 60 output rows.

- [ ] **Step 5: Commit the task**

```powershell
git add evals/sprint4/prediction_schema.py evals/sprint4/generate_predictions.py tests/evals/test_sprint4_predictions.py
git commit -m "feat: add Sprint 4 prediction output boundary"
```

### Task 3: 严格评估指标与发布状态

**Files:**
- Modify: `evals/metrics.py`
- Modify: `evals/run_sprint4_eval.py`
- Create: `evals/sprint4/validate_release.py`
- Modify: `tests/evals/test_sprint4_metrics.py`
- Modify: `tests/evals/test_run_sprint4_eval.py`
- Create: `tests/evals/test_sprint4_release.py`

**Interfaces:**
- `evidence_coverage(evidence_dimensions, total_dimensions) -> float`：只计算维度覆盖比例。
- `source_diversity(source_types) -> dict[str, object]`：返回 `count` 和排序后的 `sources`。
- `run_evaluation(..., predictions_path=...)`：要求预测文件覆盖所有案例，否则抛出 `EvaluationInputError`。
- `validate_release(report, asset_report) -> dict[str, object]`：返回 `status`, `p0_failures`, `p1_failures`, `metrics` 和 `asset_summary`。

- [ ] **Step 1: Write the failing tests**

```python
def test_coverage_is_not_multiplied_by_source_diversity():
    assert evidence_coverage(3, 6) == pytest.approx(0.5)
    assert source_diversity({"questionnaire"}) == {
        "count": 1,
        "sources": ["questionnaire"],
    }


def test_evaluation_rejects_cases_without_predictions(tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text('{"case_id":"C001","gold":{}}\n', encoding="utf-8")
    with pytest.raises(EvaluationInputError, match="predicted"):
        run_evaluation(cases_path=cases, safety_cases_path=None)


def test_unavailable_prediction_blocks_release():
    result = validate_release(
        report={"metrics": {"schema_pass_rate": 0.0, "safety_recall": 0.0}},
        asset_report={"total_case_count": 60},
    )
    assert result["status"] == "blocked"
    assert result["p0_failures"]
```

- [ ] **Step 2: Run the tests to observe the old behavior**

Run: `pytest tests/evals/test_sprint4_metrics.py tests/evals/test_run_sprint4_eval.py tests/evals/test_sprint4_release.py -q`

Expected: the new tests fail because coverage currently includes source diversity and missing predictions are silently treated as empty mappings.

- [ ] **Step 3: Implement strict evaluation and P0/P1 classification**

Change the coverage function and call sites, preserve source diversity as a separate report field, validate every prediction before calculating metrics, and collect provider error explainability from `predicted` rather than from the original case. Mark `schema_pass_rate < 1.0`, `safety_recall < 1.0`, missing predictions, invalid assets, and privacy failures as P0.

- [ ] **Step 4: Run focused tests and the full Python suite**

Run: `pytest tests/evals tests/contract tests/integration -q`  
Then run: `pytest tests/ -q`

Expected: focused tests and all existing tests pass; the old source-diversity-multiplier assertion is updated to the Frozen Contract behavior.

- [ ] **Step 5: Commit the task**

```powershell
git add evals/metrics.py evals/run_sprint4_eval.py evals/sprint4/validate_release.py tests/evals
git commit -m "feat: enforce Sprint 4 release metrics"
```

### Task 4: 验收编排与报告

**Files:**
- Create: `evals/sprint4/run_acceptance.py`
- Create: `tests/evals/test_sprint4_acceptance.py`
- Modify: `docs/sprint4/post-integration-release-acceptance-design.md`

**Interfaces:**
- `run_acceptance(repo_root, cases_path, safety_cases_path, predictions_path, report_json, report_markdown) -> dict[str, object]`。
- 输出 Gate 1-4 状态、测试命令摘要、资产摘要、指标、P0/P1 失败和最终 `passed/degraded/blocked`。
- `--skip-command` 只允许测试编排器本身，不改变发布状态；正式运行默认执行 Python 测试、前端契约测试和 H5 构建。

- [ ] **Step 1: Write the failing tests**

```python
def test_acceptance_writes_machine_and_human_reports(tmp_path):
    result = run_acceptance(
        repo_root=ROOT,
        cases_path=ROOT / "evals/sprint4/cases.jsonl",
        safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
        predictions_path=tmp_path / "predictions.jsonl",
        report_json=tmp_path / "acceptance.json",
        report_markdown=tmp_path / "acceptance.md",
        commands=[],
    )
    assert result["status"] == "blocked"
    assert report_json.exists()
    assert report_markdown.exists()
    assert "Gate 1" in report_markdown.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the test to verify the orchestrator is missing**

Run: `pytest tests/evals/test_sprint4_acceptance.py -q`

Expected: FAIL because `evals.sprint4.run_acceptance` does not exist.

- [ ] **Step 3: Implement the orchestrator and report renderer**

Run asset validation first, then prediction/evaluation validation, then injected commands. Record only command name, return code and bounded output summary. Render the same result to JSON and Markdown. A missing predictions file or unavailable adapter must produce `blocked`, while a successful real-service run with documented Provider degradation may produce `degraded`.

- [ ] **Step 4: Run the orchestrator tests**

Run: `pytest tests/evals/test_sprint4_acceptance.py tests/evals -q`

Expected: all report and gate tests pass.

- [ ] **Step 5: Commit the task**

```powershell
git add evals/sprint4/run_acceptance.py tests/evals/test_sprint4_acceptance.py docs/sprint4/post-integration-release-acceptance-design.md
git commit -m "feat: orchestrate Sprint 4 release acceptance"
```

### Task 5: 最终本地验证与交付

**Files:**
- Verify: `evals/sprint4/asset_validation.py`
- Verify: `evals/sprint4/generate_predictions.py`
- Verify: `evals/sprint4/validate_release.py`
- Verify: `evals/sprint4/run_acceptance.py`
- Verify: `docs/sprint4/post-integration-release-acceptance-design.md`

- [ ] **Step 1: Run asset validation against the formal assets**

Run: `python -m evals.sprint4.asset_validation`

Expected: 20 questions, 55 normal cases, 5 safety cases, total 60, no errors.

- [ ] **Step 2: Run the complete Python suite**

Run: `pytest tests/ -q`

Expected: zero failures.

- [ ] **Step 3: Run frontend contract tests and H5 build**

Run from `frontend/`: `node --test tests/*.test.mjs`  
Then: `npm run build:h5`

Expected: all frontend tests pass and H5 build completes.

- [ ] **Step 4: Run acceptance in no-provider mode and record the honest result**

Run: `python -m evals.sprint4.run_acceptance --repo . --cases evals/sprint4/cases.jsonl --safety-cases evals/sprint4/safety-cases.jsonl --predictions artifacts/sprint4/predictions.jsonl --report-json artifacts/sprint4/acceptance-report.json --report-markdown artifacts/sprint4/acceptance-report.md`

Expected: asset and code gates pass, prediction/release gate is `blocked` with `PREDICTION_PROVIDER_REQUIRED`; no report contains user original text.

- [ ] **Step 5: Review the final diff and commit only source, tests and documentation**

Run: `git diff --check` and `git status --short`.

Do not stage generated `artifacts/`, `node_modules/`, caches, or unrelated untracked directories.
