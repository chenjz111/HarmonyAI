# S4-06 Integration & Automated Acceptance Report

> 日期：2026-08-12
> 基线：`integration/sprint4-real-input@ecd3596f40cc11205c5af28612e647070d5b0cd2`
> 验收修复分支：`fix/s4-06-integration`
> 正式评测前提交：`24bad5e`
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
| 60-case 正式评估 | FAIL | loaded/executed 60/60；5 PASS；40 FAIL；15 ERROR；真实本地 Qwen AVAILABLE |
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
- FAIL：40
- ERROR：15
- Safety：5/5 PASS
- Formal Qwen：`AVAILABLE`；Ollama 0.32.8 / `qwen2.5:7b-instruct-q4_K_M`
- Threshold：FAIL

正式评测使用本地 OpenAI-compatible Ollama endpoint 与真实 Qwen2.5 7B Q4_K_M 推理；未使用 Mock Provider 或 expected labels。15 个 ERROR 均为 production Assessment 检测到的 `PROVIDER_ERROR`，需要只针对这些失败 subset 继续定位。

5 个 safety cases 真实走 production path，全部在 Diagnosis/Prescription/Music 前阻断。40 个普通 FAIL 主要是 emotion label、abstain、physical、event、conflict 与 follow-up 的 model-quality 差异。

真实指标：emotion F1 0.1987、event F1 0、physical F1 0.6154、citation accuracy 1.0、unsupported rate 0、safety recall 1.0、schema pass 0.75、abstain accuracy 0.30、coverage 1.0、provider failure 0.25。P0 threshold 未达标，总状态保持 `AUTOMATED_ACCEPTANCE_FAILED`。

C051/C052/C053 已按 Contract/Data Owner 决定修订并经 production scorer 验证；正式输入数据 60/60 VALID。

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

1. 保存首次正式 60-case 原始结果，不立即重复全量评测。
2. 仅定位 15 个 `PROVIDER_ERROR` subset；只有确定属于实现/基础设施问题并完成针对性修复后，才允许一次 Final 60-case。
3. model-quality 差异不触发大规模 Prompt tuning。
4. MySQL 等待正确凭证；OCR POC 与 Android 真机 Gate 保持人工 PENDING。

在 Formal Evaluation 达到 Frozen P0 threshold 前，不得进入 v0.4.0 发布；当前严格状态为 `AUTOMATED_ACCEPTANCE_FAILED`。

## Final automated checkpoint (authoritative, 2026-08-12)

- Final real-Qwen evaluation: 60/60 executed; 15 PASS, 40 FAIL, 5 ERROR; Frozen threshold FAIL.
- Final metrics: emotion F1 0.6760563380; event F1 0.8; physical F1 0.8; citation accuracy 1.0; unsupported rate 0.0; safety recall 1.0; schema pass 0.9166666667.
- Automated regression at the final code checkpoint: Full 535/535 PASS; Contract 30/30 PASS; Frontend 37/37 PASS; H5 production build PASS.
- MySQL: `USER_CREDENTIAL_REQUIRED` (service available; complete valid password not provided).
- OCR: `MANUAL_OCR_POC_PENDING`.
- Android: `MANUAL_ANDROID_TEST_PENDING`.
- Overall status: `AUTOMATED_ACCEPTANCE_FAILED`; do not merge/release Sprint 4 as accepted.
