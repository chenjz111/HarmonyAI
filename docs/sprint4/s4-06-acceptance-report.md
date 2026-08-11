# S4-06 Integration & Automated Acceptance Report

> 日期：2026-08-11
> 基线：`integration/sprint4-real-input@ecd3596f40cc11205c5af28612e647070d5b0cd2`
> 验收修复分支：`fix/s4-06-integration`
> 总状态：`AUTOMATED_ACCEPTANCE_FAILED`

## 结果总览

| 验收项 | 状态 | 实际结果 |
|---|---|---|
| 四线会师基线 | PASS | #53、#54、#55、#56 均已进入 integration |
| Frozen Contract | PASS | 30/30 passed |
| 后端全量回归 | PASS | 499/499 passed；0 failed；0 skipped；1 个既有 StarletteDeprecationWarning |
| 前端回归 | PASS | 37/37 passed |
| H5 production build | PASS | `npm run build:h5` 完成 |
| 60-case 正式评估 | FAIL | 0/60 可被正式 runner 有效计分；runner 未执行模型推理，详见下文 |
| Safety Gate | PASS | 5/5 safety cases 均先于 Diagnosis/Prescription/Music 阻断 |
| 10 个验收场景 | PASS | 10/10 |
| 完整产品链路 | PASS | Input → Assessment → Confirmation → Diagnosis → Prescription → Music → Feedback |
| SQLite | PASS | migration、旧数据保留、Assessment/Revision/Evidence/Follow-Up/Confirmation、AI log privacy 均通过 |
| MySQL 8 | PENDING | 本机 MySQL 8.0.44 服务存在，但无本轮可用连接配置；静态 DDL/migration 测试通过 |
| Provider Failure | PASS | Qwen/OCR unavailable、timeout、invalid JSON/schema、retry exhausted、invalid PDF 均安全降级且不假成功 |
| Privacy Probe | PASS | 唯一 marker 未进入普通日志或 AI 日志持久化字段 |
| Sprint 3 Compatibility | PASS | 全量后端回归、旧接口与前端兼容测试通过 |
| OCR Manual POC | PENDING | 仓库无合法、脱敏、人工准备的真实医疗材料 |
| Android | PENDING | 无 Android SDK、ADB、模拟器或连接设备；保持真机手工 Gate |

## 本轮小型集成修复

1. `POST /api/v2/assessments` 现在从环境配置注入 Sprint 4 async Qwen Provider；未配置时继续按 Frozen Contract 安全降级。
2. 普通日志脱敏字段补充 `provider_input`、`user_prompt`、`system_prompt`。
3. 新增 Provider API 接线与隐私持久化回归测试。

未修改 Frozen Contract、核心 Agent 架构或产品流程。

## 60-case 正式评估阻塞

数据集包含 55 个 normal cases 与 5 个 safety cases，字段为 `input` / `expected`。当前 `evals/run_sprint4_eval.py` 只消费 `predicted` / `gold`，不会调用 Assessment 或 Diagnosis。因此运行得到的 `schema_pass_rate=0.0`，而若干 `1.0` 指标来自空集合默认值，不能作为真实模型成绩。

此外，本机未配置 Qwen API 环境。55 个 normal cases 主要是 narrative-only，而当前 Assessment V2.1 runtime 还要求 questionnaire envelope。修复需要正式的 runner/provider/data adapter 设计与可用 Provider 环境，超出“小型 integration bug”范围。本轮未修改 expected labels，也未伪造预测结果。

结论：正式 60-case 记为 **0/60 有效通过，FAIL**。独立 Safety Gate 的真实 workflow 执行为 5/5 PASS，但不能替代 60-case runner。

## 十个正式验收场景

| # | Scenario | Expected | Actual | 状态 |
|---|---|---|---|---|
| 1 | 20 题完整问卷 | canonical v2.1 被处理 | success，20 answers，15 evidence | PASS |
| 2 | 6 题 Quick State | quick_state_v1 | 5 个数值字段 + 1 个 goal，共 6 个 UI 问题 | PASS |
| 3 | Questionnaire + Narrative + Document | 三源融合 | source diversity=3，三源均处理 | PASS |
| 4 | 多来源 Conflict | 生成冲突与追问 | 1 conflict，2 follow-ups | PASS |
| 5 | MissingInformation → Follow-Up | 缺少 duration 时追问 | missing duration，duration follow-up | PASS |
| 6 | Confirmation/Correction/Revision | revision 可写、可读并被 workflow 使用 | 真实 API revision/confirmation 测试 3/3 | PASS |
| 7 | Qwen unavailable | 不崩溃、安全降级 | narrative unavailable，assessment needs_follow_up | PASS |
| 8 | OCR unavailable/failed | 不假成功 | failed，OCR_FAILED，空 text | PASS |
| 9 | Safety blocked | 不进入下游 | diagnosis/prescription/music 均为空 | PASS |
| 10 | Diagnosis abstained | 不生成处方或音乐 | prescription/music 均为空 | PASS |

## 完整产品链路证据

自动执行一条真实服务链路：有效问卷 → Assessment success → Confirmation confirmed → Diagnosis success/non-abstained → Prescription success → Music matched (`music-jiao`) → Feedback success。Feedback 保持 `global_rule_update=false`。

另行验证：未确认 assessment、needs-follow-up、Safety blocked、Diagnosis abstained、缺失后端处方均不会进入音乐流程；Workflow 使用最新 revision；前端不构造处方。

## 环境与手工 Gate

- MySQL：检测到 MySQL 8.0.44 CLI 与运行中的 `MySQL` 服务，但 `DATABASE_URL` 未配置，故真实 migration/integration 为 `MYSQL_ENV_PENDING`。自动化仅验证了 MySQL DDL 可生成、无 DROP，以及 SQLite migration 行为。
- OCR Manual POC：没有合规脱敏材料，状态 `MANUAL_OCR_POC_PENDING`。
- Android：`ANDROID_HOME` / `ANDROID_SDK_ROOT` 未设置，ADB 不存在，状态 `MANUAL_ANDROID_TEST_PENDING`。H5 build PASS 不等于 Android 真机 PASS。

## 下一步

1. 先修复正式 evaluation runner，使其真正执行当前 Assessment/Diagnosis，并建立 narrative-only 的合规输入适配；配置可用 Qwen 后重跑 60 cases。
2. 在具备连接凭据的隔离 MySQL 8 环境运行 migration 与基础 API integration。
3. 准备合法脱敏 OCR 材料并完成手工 POC。
4. 在真实 Android 设备完成 S4-06 Manual Gate。

在第 1 项完成前，不得进入 v0.4.0 发布；当前严格状态为 `AUTOMATED_ACCEPTANCE_FAILED`。
