# S4-06 Integration & Automated Acceptance Report（最终权威版）

> 日期：2026-08-12
> 验收修复分支：`fix/s4-06-integration`
> PR HEAD：`dd92f09`
> 总状态：`AUTOMATED_ACCEPTANCE_FAILED`

## 结果总览

| 验收项 | 状态 | 实际结果 |
|---|---|---|
| Frozen Contract | PASS | 30/30 passed |
| 后端全量回归 | PASS | 540/540 passed；0 failed；1 个既有 StarletteDeprecationWarning |
| 前端回归 | PASS | 37/37 passed（`node --test tests/*.test.mjs`） |
| H5 production build | PASS | `npm run build:h5` 完成 |
| 60-case 正式评估 | **FAIL** | loaded/executed 60/60；15 PASS；45 FAIL；**0 ERROR**；真实本地 Qwen AVAILABLE |
| Safety Gate | PASS | 5/5 safety cases 均先于 Diagnosis/Prescription/Music 阻断 |
| 10 个验收场景 | PASS | 10/10 |
| 完整产品链路 | PASS | Input → Assessment → Confirmation → Diagnosis → Prescription → Music → Feedback |
| SQLite | PASS | migration、旧数据保留、Assessment/Revision/Evidence/Follow-Up/Confirmation、AI log privacy 均通过 |
| MySQL 8 | USER_CREDENTIAL_REQUIRED | 本机 MySQL 8.0.44 可用，但提供的密码不完整且登录失败；未继续猜测凭证 |
| Provider Failure | PASS | Qwen/OCR unavailable、timeout、invalid JSON/schema、retry exhausted、invalid PDF 均安全降级且不假成功 |
| Privacy Probe | PASS | 唯一 marker 未进入普通日志或 AI 日志持久化字段 |
| Sprint 3 Compatibility | PASS | 全量后端回归、旧接口与前端兼容测试通过 |
| OCR Manual POC | PENDING | 仓库无合法、脱敏、人工准备的真实医疗材料 |
| Android | PENDING | 无 Android SDK、ADB、模拟器或连接设备；保持真机手工 Gate |

## 60-case 正式评估结果（最终）

机器输出：`evals/sprint4/results/s4-06-evaluation.json`
可读报告：`docs/sprint4/s4-06-evaluation-report.md`

- Loaded：60/60；Executed：60/60
- PASS：15；FAIL：45；ERROR：0
- Safety：5/5 PASS
- Formal Qwen：`AVAILABLE`；Ollama / `qwen2.5:7b-instruct-q4_K_M`

| Metric | Actual | Frozen P0 threshold | 状态 |
|---|---:|---:|---|
| emotion_f1 | 0.7362 | ≥ 0.80 | **FAIL** |
| event_f1 | 0.7500 | ≥ 0.75 | PASS |
| physical_f1 | 0.8000 | ≥ 0.80 | PASS |
| evidence_citation_accuracy | 1.0000 | ≥ 0.95 | PASS |
| unsupported_conclusion_rate | 0.0000 | ≤ 0.05 | PASS |
| safety_recall | 1.0000 | = 1.00 | PASS |
| schema_pass_rate | 1.0000 | = 1.00 | PASS |
| provider_failure_rate | 0.0000 | ≤ 0.05 | PASS |

**唯一未达标项：`emotion_f1 = 0.7362`（阈值 ≥ 0.80）。** 残余缺口为 emotion 细腻维度（low_mood/fear_unease/emotional_recovery/overthinking）的模型质量（H）召回不足。

## 本轮 S4-06 修复（对比基线 emotion_f1 0.7044）

1. 恢复并修正 `_supplement_grounded_items` 的 keyword-grounding gate：Qwen emotion 抽取须携带含支撑关键词的 quote，否则视为幻觉删除；词法回退项天然通过。
2. 删除过激 quote 过滤（calm_wellbeing 含"有时候"、fear_unease 含"烦躁不安"）。
3. good_state handler 不再删除既有 low_mood，只补充 negated 证据。
4. 放开 calm_wellbeing/fear_unease 词法回退；拓宽中文关键词。
5. 修正 evaluator taxonomy：从 `_EMOTION_LABELS` 移除 `worry_control`（frozen contract：scored=false，weight=0）。
6. 显式注入 Qwen 环境变量，15 个 PROVIDER_ERROR 归零（provider_failure_rate 0.25→0.0，schema_pass_rate 0.75→1.0）。

未修改 Frozen Contract、expected labels、核心 Agent 架构或产品流程。

## 十个正式验收场景

| # | Scenario | Actual | 状态 |
|---|---|---|---|
| 1 | 20 题完整问卷 | success，20 answers，15 evidence | PASS |
| 2 | 6 题 Quick State | 5 个数值字段 + 1 个 goal | PASS |
| 3 | Questionnaire + Narrative + Document | source diversity=3，三源均处理 | PASS |
| 4 | 多来源 Conflict | 1 conflict，2 follow-ups | PASS |
| 5 | MissingInformation → Follow-Up | missing duration，duration follow-up | PASS |
| 6 | Confirmation/Correction/Revision | 真实 API revision/confirmation 测试 3/3 | PASS |
| 7 | Qwen unavailable | narrative unavailable，assessment needs_follow_up | PASS |
| 8 | OCR unavailable/failed | failed，OCR_FAILED，空 text | PASS |
| 9 | Safety blocked | diagnosis/prescription/music 均为空 | PASS |
| 10 | Diagnosis abstained | prescription/music 均为空 | PASS |

## 完整产品链路证据

自动执行一条真实服务链路：有效问卷 → Assessment success → Confirmation confirmed → Diagnosis success/non-abstained → Prescription success → Music matched → Feedback success。未确认 assessment、needs-follow-up、Safety blocked、Diagnosis abstained、缺失后端处方均不会进入音乐流程。

## 环境与手工 Gate

- MySQL：检测到 MySQL 8.0.44 CLI 与运行中的服务，但无本轮隔离 `DATABASE_URL`，且密码不完整。真实 migration/integration 保持 `USER_CREDENTIAL_REQUIRED`。未 reset root、未删除现有 DB、未清空业务数据。
- OCR Manual POC：没有合规脱敏材料，状态 `MANUAL_OCR_POC_PENDING`。
- Android：`ANDROID_HOME`/`ANDROID_SDK_ROOT` 未设置，ADB 不存在，状态 `MANUAL_ANDROID_TEST_PENDING`。H5 build PASS 不等于 Android 真机 PASS。

## 结论与下一步

在 `emotion_f1` 达到 Frozen P0 阈值 0.80 前，S4-06 严格状态为 **`AUTOMATED_ACCEPTANCE_FAILED`**，不得进入 v0.4.0 发布。

残余 blocker 为模型质量（H）：需要更强的模型（如非量化 / 更大参数 / 专为情绪细分的微调）或受控 Prompt/数据改进才能召回 low_mood、fear_unease、emotional_recovery、overthinking 等细腻维度。不进行大规模无边界 Prompt tuning，不修改 expected 只为过线，不 Mock 代替 Qwen。

MySQL 等待正确凭证；OCR POC 与 Android 真机 Gate 保持人工 PENDING。
