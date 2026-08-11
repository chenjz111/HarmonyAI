# S4-06 Formal Evaluation Report

> 日期：2026-08-12
> Runner：`evals/run_sprint4_eval.py`
> Machine output：`evals/sprint4/results/s4-06-evaluation.json`
> Formal Qwen：`AVAILABLE`（Ollama / qwen2.5:7b-instruct-q4_K_M）
> Evaluation threshold：`FAIL`

## 执行摘要

| 项目 | 结果 |
|---|---|
| 60 Cases Loaded | 60/60 |
| 60 Cases Executed | 60/60 |
| PASS | 5 |
| FAIL | 40 |
| ERROR | 15 |
| Safety | 5/5 PASS |
| Silent Skip | 0 |

60/60 均通过 production runner 执行。5 个 safety case PASS；40 个普通 case 为 model-quality 差异；15 个 case 因 production Assessment 的 `PROVIDER_ERROR` 记为 ERROR，没有被计为 PASS 或 skip。

## Qwen 运行环境

本次正式评测使用本机真实 Qwen runtime：

- `QWEN_BASE_URL`：本地 OpenAI-compatible endpoint（仅进程环境）；
- `QWEN_API_KEY`：本地非敏感占位值（未提交）；
- `QWEN_MODEL`：`qwen2.5:7b-instruct-q4_K_M`；
- Runtime：Ollama 0.32.8；模型 digest `845dbda0ea48`；
- Provider sync/async smoke、3-case smoke、8-case representative mini 均先行通过基础设施门禁。

已执行的门禁顺序：

1. Provider sync/async smoke；
2. 3-case smoke（两条普通、一条 safety）；
3. 8-case representative mini；
4. 一次正式 55 normal + 5 safety；
5. 真实 structured output 进入计分，Provider/schema degradation 明确记 ERROR。

模型已本地安装；未使用 Mock Provider、expected labels 或伪结果冒充正式推理。

## Metrics

| Metric | Actual | Frozen P0 threshold | 状态 |
|---|---:|---:|---|
| emotion_f1 | 0.1987 | ≥ 0.80 | FAIL |
| event_f1 | 0.0000 | ≥ 0.75 | FAIL |
| physical_f1 | 0.6154 | ≥ 0.80 | FAIL |
| evidence_citation_accuracy | 1.0000 | ≥ 0.95 | PASS |
| unsupported_conclusion_rate | 0.0000 | ≤ 0.05 | PASS |
| safety_recall | 1.00 | 1.00 | PASS |
| schema_pass_rate | 0.7500 | 1.00 | FAIL |
| abstain_accuracy | 0.3000 | P1 | 记录 |
| evidence_coverage_score | 1.0000 | descriptive | 记录 |
| provider_failure_rate | 0.2500 | ≤ 0.05（配置正确时） | FAIL |

真实本地模型已执行全部 60 case；P0 的 emotion/event/physical/schema 指标未达到 Frozen threshold，因此结论为 FAIL。下一步只定位 15 个 ERROR subset，不立即进行第二次完整 60-case。

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
- C051/C052/C053 已按 Contract/Data Owner 决定修订；production scorer 预校验通过，正式输入数据 60/60 VALID。

## 结论

Formal Runner 与真实 Qwen 环境均已运行，但 60-case Frozen Evaluation threshold 未达标。S4-06 总状态继续为：

`AUTOMATED_ACCEPTANCE_FAILED`
