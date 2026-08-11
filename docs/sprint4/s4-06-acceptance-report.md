# S4-06 Integration & Automated Acceptance Report

> 日期：2026-08-11
> 基线：`integration/sprint4-real-input@ecd3596f40cc11205c5af28612e647070d5b0cd2`
> 验收修复分支：`fix/s4-06-integration`
> 当前提交（更新前）：`ec9f797a2f21ea957a735f3d0983dc77e7ad57fb`
> 总状态：`AUTOMATED_ACCEPTANCE_FAILED`

## 结果总览

| 验收项 | 状态 | 实际结果 |
|---|---|---|
| 四线会师基线 | PASS | #53、#54、#55、#56 均已进入 integration |
| Frozen Contract | PASS | 30/30 passed |
| 后端全量回归 | PASS | 511/511 passed；0 failed；0 skipped；1 个既有 StarletteDeprecationWarning |
| Evaluation runner tests | PASS | 14/14 passed |
| 前端回归 | PASS | 37/37 passed |
| H5 production build | PASS | `npm run build:h5` 完成 |
| 60-case 正式评估 | FAIL | loaded 60/60；executed 60/60；5 PASS；1 FAIL；54 ERROR |
| Safety Gate | PASS | 5/5 safety cases 均先于 Diagnosis/Prescription/Music 阻断 |
| 10 个验收场景 | PASS | 10/10 |
| 完整产品链路 | PASS | Input → Assessment → Confirmation → Diagnosis → Prescription → Music → Feedback |
| SQLite | PASS | migration、旧数据保留、Assessment/Revision/Evidence/Follow-Up/Confirmation、AI log privacy 均通过 |
| MySQL 8 | PENDING | 本机 MySQL 8.0.44 服务存在，但没有隔离连接配置或 Docker；静态 DDL/migration 测试通过 |
| Provider Failure | PASS | Qwen/OCR unavailable、timeout、invalid JSON/schema、retry exhausted、invalid PDF 均安全降级且不假成功 |
| Privacy Probe | PASS | 唯一 marker 未进入普通日志或 AI 日志持久化字段 |
| Sprint 3 Compatibility | PASS | 全量后端回归、旧接口与前端兼容测试通过 |
| OCR Manual POC | PENDING | 仓库无合法、脱敏、人工准备的真实医疗材料 |
| Android | PENDING | 无 Android SDK、ADB、模拟器或连接设备；保持真机手工 Gate |

## 本轮 S4-06 修复

1. `POST /api/v2/assessments` 从环境配置注入 Sprint 4 async Qwen Provider；未配置时按 Frozen Contract 安全降级。
2. 普通日志脱敏字段补充 `provider_input`、`user_prompt`、`system_prompt`。
3. Formal Evaluation Runner 改为读取既有 `input` / `expected` 并调用 production `run_real_workflow_v21`。
4. Runner 新增逐 case `PASS` / `FAIL` / `ERROR`、真实 executed 计数、Frozen P0 metrics 与脱敏机器报告。
5. Provider exception/degradation 和 schema invalid 明确记为 ERROR；Safety miss 记为 FAIL；不 silent skip。
6. narrative-only case 的中性问卷仅用于满足 Frozen runtime transport contract，不来自 expected，也不计入用户证据 metrics。
7. `evidence_coverage_score` 与 `source_diversity` 保持独立。
8. 新增 runner、metrics、CLI、provider-error 与 scaffold regression tests。

未修改 Frozen Contract、expected labels、核心 Agent 架构或产品流程。

## 60-case 正式评估结果

机器输出：`evals/sprint4/results/s4-06-evaluation.json`
可读报告：`docs/sprint4/s4-06-evaluation-report.md`

- Loaded：60/60
- Executed：60/60
- PASS：5
- FAIL：1
- ERROR：54
- Safety：5/5 PASS
- Formal Qwen：`QWEN_FORMAL_EVAL_ENV_BLOCKED`
- Threshold：FAIL

当前缺少 `QWEN_BASE_URL`、`QWEN_API_KEY`、`QWEN_MODEL`，也未发现本地 Qwen runtime。54 个含有效 narrative/document 的 normal cases 被明确记录为 Qwen 环境 ERROR；没有使用 Mock Provider、expected result 或空集合指标冒充正式推理。

唯一普通 FAIL 为 `C019`：预期 Follow-Up 2–4 题，production pipeline 实际生成 0 题。5 个 safety cases 真实走 production path，全部在 Diagnosis/Prescription/Music 前阻断。

指标中的 emotion/event/physical/citation 等 1.00 仅来自唯一可比较的空输入 normal case，不代表正式 Qwen 质量。P0 `schema_pass_rate=0.10`，低于 Frozen threshold 1.00；`provider_failure_rate=0.90`。因此自动化总状态必须保持 `AUTOMATED_ACCEPTANCE_FAILED`。

另发现 `C051.q18_daily_impact=null` 与 Frozen Questionnaire 必填 0–4 冲突。未修改 case input 或 expected label；在正式 Qwen 环境恢复后，该 case 预计会成为输入 schema ERROR，需要由数据/Contract owner 审核。

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

自动执行一条真实服务链路：有效问卷 → Assessment success → Confirmation confirmed → Diagnosis success/non-abstained → Prescription success → Music matched (`music-jiao`) → Feedback success。Feedback 保持 `global_rule_update=false`。

另行验证：未确认 assessment、needs-follow-up、Safety blocked、Diagnosis abstained、缺失后端处方均不会进入音乐流程；Workflow 使用最新 revision；前端不构造处方。

## 环境与手工 Gate

- MySQL：检测到 MySQL 8.0.44 CLI 与运行中的 `MySQL` 服务，但无本轮隔离 `DATABASE_URL`，且 Docker 不存在。真实 migration/integration 保持 `MYSQL_ENV_PENDING`。
- OCR Manual POC：没有合规脱敏材料，状态 `MANUAL_OCR_POC_PENDING`。
- Android：`ANDROID_HOME` / `ANDROID_SDK_ROOT` 未设置，ADB 不存在，状态 `MANUAL_ANDROID_TEST_PENDING`。H5 build PASS 不等于 Android 真机 PASS。

## 下一步

1. 由用户在安全环境中配置真实 Qwen endpoint/key/model，不将密钥提交仓库。
2. 先确认 Provider Health，再使用同一 runner 重跑完整 60 cases。
3. 由数据/Contract owner 审核 `C051.q18_daily_impact=null`，不得由 runner 私自补值。
4. 之后完成隔离 MySQL、真实脱敏 OCR POC 和 Android 真机 Gate。

在 Formal Evaluation 达到 Frozen P0 threshold 前，不得进入 v0.4.0 发布；当前严格状态为 `AUTOMATED_ACCEPTANCE_FAILED`。
