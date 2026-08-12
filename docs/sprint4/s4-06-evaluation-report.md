# S4-06 Formal Evaluation Report（最终权威版）

> 日期：2026-08-12
> Runner：`evals/run_sprint4_eval.py`
> Machine output：`evals/sprint4/results/s4-06-evaluation.json`
> Formal Qwen：`AVAILABLE`（Ollama / qwen2.5:7b-instruct-q4_K_M）
> 本文件为最终权威结果，取代此前所有初跑/中间 checkpoint 数字。

## 执行摘要

| 项目 | 结果 |
|---|---|
| 60 Cases Loaded | 60/60 |
| 60 Cases Executed | 60/60 |
| PASS | 15 |
| FAIL | 45 |
| ERROR | 0 |
| Safety | 5/5 PASS |
| Silent Skip | 0 |

60/60 均通过 production runner 执行，0 ERROR。5 个 safety case 全部在 Diagnosis/Prescription/Music 前阻断。45 个普通 FAIL 中，绝大多数为 emotion 标签的 model-quality 差异（详见 per-label 分析）。

## Qwen 运行环境

- `QWEN_BASE_URL`：本地 OpenAI-compatible endpoint（`http://localhost:11434/v1`，仅进程环境，未提交）；
- `QWEN_API_KEY`：本地非敏感占位值 `ollama`（未提交）；
- `QWEN_MODEL`：`qwen2.5:7b-instruct-q4_K_M`；
- Runtime：Ollama 本地推理；未使用 Mock Provider、expected labels 或伪结果。

## Metrics（最终）

| Metric | Actual | Frozen P0 threshold | 状态 |
|---|---:|---:|---|
| emotion_f1 | 0.7362 | ≥ 0.80 | **FAIL** |
| event_f1 | 0.7500 | ≥ 0.75 | PASS |
| physical_f1 | 0.8000 | ≥ 0.80 | PASS |
| evidence_citation_accuracy | 1.0000 | ≥ 0.95 | PASS |
| unsupported_conclusion_rate | 0.0000 | ≤ 0.05 | PASS |
| safety_recall | 1.0000 | = 1.00 | PASS |
| schema_pass_rate | 1.0000 | = 1.00 | PASS |
| abstain_accuracy | 0.6727 | P1 | 记录 |
| evidence_coverage_score | 1.0000 | descriptive | 记录 |
| provider_failure_rate | 0.0000 | ≤ 0.05 | PASS |

**唯一未达标项：`emotion_f1 = 0.7362`（阈值 ≥ 0.80）。**

## Emotion per-label 混淆分析（55 normal cases）

Micro：TP=60，FP=14，FN=29，Precision=0.8108，Recall=0.6742，F1=0.7362

| Label | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| tension_worry | 18 | 2 | 3 | 0.9000 | 0.8571 | 0.8780 |
| low_mood | 10 | 1 | 10 | 0.9091 | 0.5000 | 0.6452 |
| fear_unease | 7 | 3 | 5 | 0.7000 | 0.5833 | 0.6364 |
| overthinking | 7 | 1 | 4 | 0.8750 | 0.6364 | 0.7368 |
| interest_loss | 7 | 3 | 1 | 0.7000 | 0.8750 | 0.7778 |
| irritability_anger | 6 | 0 | 1 | 1.0000 | 0.8571 | 0.9231 |
| calm_wellbeing | 4 | 3 | 1 | 0.5714 | 0.8000 | 0.6667 |
| emotional_recovery | 1 | 1 | 4 | 0.5000 | 0.2000 | 0.2857 |

残余缺口集中在 FN（漏报）：

- `low_mood` FN=10 —— 最大缺口，模型对隐含低落（非字面"低落/难过"）提取不足；
- `fear_unease` FN=5、`emotional_recovery` FN=4、`overthinking` FN=4 —— 细腻情绪维度召回不足。

这些是**模型质量（H）**问题：Qwen2.5-7B 量化版对中文临床叙述中的细腻情绪维度（calm_wellbeing、emotional_recovery、低动机性 low_mood）语义提取能力有限，词法回退只能命中字面关键词。

## 根因分类（A-I）

| 分类 | 说明 | 状态 |
|---|---|---|
| **H — 模型质量** | 残余 emotion_f1 < 0.80 的主因：Qwen2.5-7B 量化版细腻情绪维度召回不足 | **未解决（剩余 blocker）** |
| E — Adapter | `_supplement_grounded_items` 后处理过滤过激进（keyword gate 语义、calm/fear quote 过滤、good_state handler） | 已修复 |
| B — Normalization | keyword-grounding gate 对 Qwen 幻觉标签的过滤（precision 门） | 已修复（恢复并修正） |
| C — Taxonomy | evaluator `_EMOTION_LABELS` 错误包含 `worry_control`（frozen contract 规定 scored=false） | 已修复 |

## 本轮工程修复（对照基线 0.7044）

1. **恢复并修正 keyword-grounding gate**：Qwen emotion 抽取必须携带含支撑关键词的 quote，否则视为幻觉删除；词法回退项因 quote 即命中关键词天然通过。（中间一次"保护 Qwen 项"的修正错误移除了该门，导致 FP 14→27、emotion_f1 0.7362→0.6590，已回退。）
2. **删除过激 quote 过滤**：`calm_wellbeing` 含"有时候"、`fear_unease` 含"烦躁不安"不再整条丢弃（"有时候很平静"仍是 grounded 证据）。
3. **good_state handler 不再删除既有 low_mood**，只补充 negated 证据，冲突交由 assessment fusion 层解决。
4. **放开 calm_wellbeing/fear_unease 的词法回退**（关键词命中时补标签）。
5. **拓宽词法回退关键词**（tension_worry/calm_wellbeing/emotional_recovery/overthinking/irritability_anger/low_mood/interest_loss/fear_unease 的中文表达）。
6. **修正 evaluator taxonomy**：从 `_EMOTION_LABELS` 移除 `worry_control`（frozen contract：scored=false，weight=0）。
7. **配置修复**：显式注入 `QWEN_BASE_URL/API_KEY/MODEL`，15 个 PROVIDER_ERROR 归零（provider_failure_rate 0.25→0.0，schema_pass_rate 0.75→1.0）。

未修改 Frozen Contract、expected labels、核心 Agent 架构或产品流程。

## 结论

Formal Runner 与真实 Qwen 环境均已运行，60/60 无 ERROR。`emotion_f1 = 0.7362` 未达 Frozen P0 阈值 0.80，其余 P0 指标（event/physical/safety/schema/evidence citation）全部通过。

S4-06 总状态：**`AUTOMATED_ACCEPTANCE_FAILED`**（唯一未达标项为 emotion_f1，根因为模型质量 H）。
