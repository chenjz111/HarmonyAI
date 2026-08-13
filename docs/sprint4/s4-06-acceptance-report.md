# S4-06 Integration & Automated Acceptance Report（最终权威版）

> 日期：2026-08-12（2026-08-13 夜间收口补充见下）
> 验收修复分支：`fix/s4-06-integration`
> PR HEAD：`4c6c5ed`
> 总状态：`AUTOMATED_ACCEPTANCE_FAILED`

## S4-06 补充（2026-08-13 夜间收口）：emotion value=0 不对称修复

> commit `5988b27`（canonical presence semantics）→ `4b36f90`（presence ≠ salience 分离）→ `4c6c5ed`（收口记录 + morning report + final JSON）。

**结论：`emotion_f1 0.7362 → 0.7407`，仍未达 0.80。** value=0 不对称修复是唯一「只改 evaluator 就带来正向收益」的合法修正，幅度 +0.0045（FN 29→28）。

| Metric | Before (0.7362) | After (0.7407) | Frozen P0 | 状态 |
|---|---:|---:|---:|---|
| emotion_f1 | 0.7362 | 0.7407 | ≥ 0.80 | **FAIL** |
| event_f1 | 0.7500 | 0.7500 | ≥ 0.75 | PASS |
| physical_f1 | 0.8000 | 0.8000 | ≥ 0.80 | PASS |
| safety_recall | 1.0 | 1.0 | = 1.00 | PASS |
| schema_pass_rate | 1.0 | 1.0 | = 1.00 | PASS |
| provider_failure_rate | 0.0 | 0.0 | ≤ 0.05 | PASS |

最终正式 60 重跑机器落盘（`evals/sprint4/results/s4-06-evaluation-final.json`）：60/60 executed、0 ERROR、15 PASS / 45 FAIL，`qwen_formal = AVAILABLE`（`qwen2.5:7b-instruct-q4_K_M`）。全量回归 610/610 passed。

**关键修正（presence ≠ salience）**：
- `_emotion_present`（presence，value≥1=present）→ expected 侧 + 证据 existence 判定。
- `_actual_emotion_present`（label-set salience，问卷 value≥3 才计入 emotion_f1 标签集）→ actual 侧。
- 把「value≥1=present」直接套到标签集会把 F1 塌缩到 0.346（问卷每 case 报 ~6 个 value=2 背景情绪，gold 是叙事派生的 2-3 个 salient 情绪）。

**value 语义是红鲱鱼**：离 0.80 还差 ~12 个错误（当前 TP=60 / FP=14 / FN=28，FP+FN=42）。真正阻塞是两项需 Owner 拍板的决策：
- **D1** 问卷情绪在 gold `emotion_states` 的纳入规则（消除 ~8 FN + ~9 FP 的问卷-叙事优先级歧义）。
- **D2** 是否换更强 Qwen（14B 量化需更大显存 / 云端 API 需预算）（消除 ~15 个叙事漏报 FN）。

手工 Gate 不变：MySQL=`USER_CREDENTIAL_REQUIRED`；OCR=`MANUAL_OCR_POC_PENDING`；Android=`MANUAL_ANDROID_TEST_PENDING`。

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

## Owner 收口决定（2026-08-13）

| 维度 | 最终状态 |
|---|---|
| Engineering Implementation | COMPLETE |
| Automated Engineering Gates | PASS |
| Formal Model Quality Target | NOT_MET |
| Emotion F1 | 0.7407 / target 0.80 |
| Owner Decision | ACCEPTED_KNOWN_MODEL_LIMITATION |
| Emotion optimization | CLOSED |

Owner 接受当前 Qwen2.5-7B Q4 对细腻、隐含情绪表达召回不足这一已知模型限制，但不降低 Frozen threshold、不修改 gold/expected，也不把 0.7407 记为 Formal Evaluation PASS。

7B/14B 观察性对比显示：14B 在当前 8 GB 显存机器上出现 40% Provider error，总耗时约为 7B 的 8.3 倍，未形成可部署提升。详细证据见 `docs/sprint4/s4-06-qwen-model-bakeoff.md`。

PR #65 可在 CI、Contract、Backend、Frontend、H5、diff hygiene 全部维持通过且无工程 blocker 时标记为 `ENGINEERING_READY_TO_MERGE`；该状态与 `FROZEN_MODEL_QUALITY_GATE_PASS` 必须严格区分。MySQL、OCR、Android 仍为人工 Gate，见 `docs/sprint4/s4-06-manual-gates.md`。
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

## Owner 最终处置与合并后状态（2026-08-13，覆盖旧的优化 NEXT_ACTION）

- 权威 Formal 60 结果仍为 `emotion_f1=0.7407 / target>=0.80`，模型质量项为 `NOT_MET`，不得改写为 PASS。
- Owner disposition：`ACCEPTED_KNOWN_MODEL_LIMITATION`；emotion_f1 optimization：`CLOSED`。
- 不再运行 14B、不再 Prompt tuning、不再重跑 Formal 60；相关改进推迟到 Sprint 5 或以后，且本轮不实现 Sprint 5。
- PR #65 已以普通 Merge Commit 合并到 `integration/sprint4-real-input`，merge commit 为 `39b0597c8f6c1f0c4993638e6dc00ef9e0feb9f9`。
- 工程结论：`ENGINEERING_COMPLETE / AUTOMATED_ENGINEERING_GATES_PASS`；这与 Frozen model-quality target `NOT_MET` 同时成立。
- 合并后轻量检查：Backend import PASS、30 个 Contract tests 可发现、diff hygiene/冲突标记 PASS。
- MySQL：`USER_CREDENTIAL_REQUIRED`；已准备只允许 `harmonyai_s4_acceptance` 的非破坏性探针。
- OCR：`MANUAL_OCR_POC_PENDING`；必须使用合法、授权、脱敏的真实材料。
- Android：`MANUAL_ANDROID_TEST_PENDING`；H5 PASS 不等于真机 PASS。
- 人工步骤与结果记录分别见 `docs/sprint4/s4-06-manual-gates.md` 和 `docs/sprint4/s4-06-manual-acceptance-result.md`。
- 当前不得进入 `integration -> dev`、`dev -> main`、tag 或 release。
