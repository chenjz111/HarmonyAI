# S4-06 Formal Evaluation Report

> 日期：2026-08-11
> Runner：`evals/run_sprint4_eval.py`
> Machine output：`evals/sprint4/results/s4-06-evaluation.json`
> Formal Qwen：`QWEN_FORMAL_EVAL_ENV_BLOCKED`
> Evaluation threshold：`FAIL`

## 执行摘要

| 项目 | 结果 |
|---|---|
| 60 Cases Loaded | 60/60 |
| 60 Cases Executed | 60/60 |
| PASS | 5 |
| FAIL | 1 |
| ERROR | 54 |
| Safety | 5/5 PASS |
| Silent Skip | 0 |

5 个 PASS 全部来自真实 production safety path。唯一 FAIL 是 `C019`：预期 Follow-Up 为 2–4 题，实际为 0 题。54 个 ERROR 均为 `QWEN_FORMAL_EVAL_ENV_BLOCKED`，没有被计为 PASS 或 skip。

## Qwen 环境检查

当前没有可用的正式 Qwen 环境：

- `QWEN_BASE_URL`：未配置；
- `QWEN_API_KEY`：未配置；
- `QWEN_MODEL`：未配置；
- 本地 Qwen runtime/model：未发现；
- Ollama、LM Studio、llama-server：未发现可用进程或命令。

启动正式模型评估所需的最小步骤：

1. 配置一个真实可访问的 OpenAI-compatible Qwen endpoint；
2. 通过环境变量提供 endpoint、key、model，密钥不得写入仓库；
3. 先调用 Provider Health 确认配置和连通性；
4. 使用同一 runner 重跑完整 55 normal + 5 safety cases；
5. 只有实际推理产生的 structured output 才能进入计分。

未下载多 GB 本地模型，也未使用 Mock Provider 或 expected labels 冒充正式推理。

## Metrics

| Metric | Actual | Frozen P0 threshold | 状态 |
|---|---:|---:|---|
| emotion_f1 | 1.00 | ≥ 0.80 | 不具代表性 |
| event_f1 | 1.00 | ≥ 0.75 | 不具代表性 |
| physical_f1 | 1.00 | ≥ 0.80 | 不具代表性 |
| evidence_citation_accuracy | 1.00 | ≥ 0.95 | 不具代表性 |
| unsupported_conclusion_rate | 0.00 | ≤ 0.05 | 不具代表性 |
| safety_recall | 1.00 | 1.00 | PASS |
| schema_pass_rate | 0.10 | 1.00 | FAIL |
| abstain_accuracy | 1.00 | P1 | 不具代表性 |
| evidence_coverage_score | 1.00 | descriptive | 不具代表性 |
| provider_failure_rate | 0.90 | ≤ 0.05（配置正确时） | FAIL |

除 safety 指标外，1.00 指标只来自唯一可比较的空输入 normal case，不能解释为正式模型质量。54 个 normal cases 没有 Qwen structured output，因此总阈值由 `schema_pass_rate=0.10` 明确判定为 FAIL。

`evidence_coverage_score` 直接聚合 production Assessment 输出；`source_diversity` 单独统计，没有参与 coverage 乘法。

## Runner 修复范围

Runner 现在：

1. 读取现有 `input` / `expected`，不再读取预写的 `predicted` / `gold`；
2. 调用 production `run_real_workflow_v21`，复用 Questionnaire、Narrative/Document、Assessment、Safety 与 Diagnosis；
3. narrative-only case 使用固定中性问卷作为 Frozen Contract 所需的传输脚手架，内容不来自 expected，且不计入该 case 的用户证据指标；
4. 每条 case 明确记录 `PASS`、`FAIL` 或 `ERROR`；
5. Provider exception/degradation、schema invalid 均为 ERROR；Safety miss 为 FAIL；
6. 输出 loaded/executed/pass/fail/error、逐 case 脱敏摘要和 Frozen metrics；
7. 不把 source diversity 混入 evidence coverage；
8. 报告不保存 narrative/document 原文或 evidence quote。

## 数据与 Contract 观察

- 数据真实存在：55 normal + 5 safety = 60。
- 全部记录均有 `case_id`、`type`、`input`、`expected`。
- `C051` 的 `q18_daily_impact` 为 `null`，与 Frozen Questionnaire 必填 0–4 值冲突；正式 Qwen 环境恢复后，该 case 预计会成为输入 schema ERROR，除非数据输入由医学/Contract owner 合法修订。未在本轮修改数据或 expected label。

## 结论

Formal Runner implementation 已完成并有回归测试，但正式 Qwen 环境不可用，60-case Frozen Evaluation threshold 未达标。S4-06 总状态继续为：

`AUTOMATED_ACCEPTANCE_FAILED`
