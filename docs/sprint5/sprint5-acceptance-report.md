# HarmonyAI Sprint 5 Acceptance Report

> 状态：`PREPARATION_IN_PROGRESS`
>
> 权威基线：`origin/integration/sprint4-real-input@cef9d2660beb1f9ab6a6f677718d4854aa548288`
>
> 历史证据日期：2026-08-24；流程验收要求更新：2026-08-26

> 本次文档修订基线：`4a22b5fad75abf839d902fda6f35487d1865a9a8`；[Owner Flow Amendment 001](../contracts/harmonyai-v3-owner-flow-amendment-001.md) 待Owner Review。下列foundation测试与实现进度是原checkpoint，不据此判断成员最新PR完成度；本轮没有重新审查成员代码或执行运行时验收。

本文是陈家智（Project Leader & AI Architect）的可恢复验收记录，不是 Sprint 5 完成声明。只有真实执行并保存证据的项目才能标记 `PASS`；`NOT_RUN`、`PENDING` 与 `BLOCKED` 不得推断为通过。

## 1. 已进入 integration 的稳定基础

| 能力 | PR / Merge commit | 当前结论 | 证据边界 |
|---|---|---|---|
| V3 Contract Freeze | #75 / `71103c0aeaf19dcbf3193eab53cad3ab5cf6cdcf` | PASS | 合同结构已冻结；医学内容另有独立门禁 |
| Executable V3 Schemas | #82 / `3e0d5c4255f0ab61d75d6604f1dabad7b4506196` | PASS | 严格 Pydantic Schema 与跨 Agent 合同测试 |
| Guest Auth / Ownership / Migration Foundation | #83 / `cafca2ac2592fe699e71a215246f5602eb8b863b` | PASS | 受控 guest token、跨用户 404、SQLite/MySQL migration ledger |
| Owner checkpoint | #84 / `e4d75974da5c0d404ace3ced3659620482659472` | PASS | 只更新交接状态，不是功能验收 |
| Understanding Provider Foundation | #85 / `fca4a7171ddb57a76f3ec84f11e715d058c25e07` | PASS | typed sync/async、Cloud→Local→Rule、单次 repair、Claim gate、隐私日志 |
| Music Provider Foundation | #86 / `cef9d2660beb1f9ab6a6f677718d4854aa548288` | PASS | typed provider、capability gate、任务状态、公共任务映射、明确 local fallback |

## 2. 当前自动化证据

这些是各 PR 对应 HEAD 的定向证据，不等于 Sprint 5 最终全量 Gate：

- PR #83：V3 + targeted V2 `21/21`；Contract `64/64`；CI `SUCCESS`。
- PR #85：Understanding Provider targeted `17/17`；Provider + V3 Contract compatibility `59/59`；CI `SUCCESS`。
- PR #86：Music Provider targeted `14/14`；Music Provider + V3 Contract + Sprint 4 music regression `61/61`；CI `SUCCESS`。
- `compileall` 与 `git diff --check` 在上述 PR 收口时均通过。
- Sprint 5 final full backend suite、all frontend tests、H5 build 与 V3 E2E：`NOT_RUN`，因为上层实现尚未会师。

## 3. Sprint 5 Gate Matrix

| Gate | 状态 | 已有能力 | 仍需完成 |
|---|---|---|---|
| Historical contract structure | BASELINE_PASS | draft.3结构曾FROZEN | 新流程修订PENDING_OWNER_REVIEW，不能把旧测试当新合同通过 |
| Medical production content | BLOCKED | 结构与 checksum 规则已冻结 | #77：最终10题、Claim、Organ、Five-Tone、Knowledge Manifest 由肖宇翔批准 |
| V3 Auth / ownership | FOUNDATION_PASS | guest、AuthPrincipal、ownership、idempotency | 注册用户扩展若进入本 Sprint 需另行验收 |
| V3 migrations | FOUNDATION_PASS | SQLite/MySQL 0001 与 checksum ledger | 后续业务表 migration；V3 live MySQL |
| Information Understanding Provider | FOUNDATION_PASS | Qwen adapter、fallback、repair、safe logs | 来源持久化、摘要修正确认、不可变revision及新流程policy；V3专用Safety暂缓 |
| Agent 1 Assessment | BLOCKED | Input/Output Schema 已存在 | 依赖 approved Claim/Organ mapping；聚合、Evidence、确认服务未完成 |
| Agent 2 Diagnosis | BLOCKED | Diagnosis/RAG Schema 已存在 | approved Knowledge Manifest、Retriever、Qwen、Rule Check、abstain 路径 |
| Agent 3 Prescription | BLOCKED | ToneProfile/GenerationSpec Schema 已存在 | approved Five-Tone mapping、偏好快照、权威处方实现 |
| Agent 4 Music | FOUNDATION_PASS | Provider接口、能力/状态/隐私/fallback边界 | 真实厂商 adapter、task/asset persistence、API、受控 stream、真实生成验收 |
| Agent 5 Feedback | NOT_STARTED | Feedback/Preference Schema 已存在 | 两阶段持久化、immutable preference、下一次处方读取 |
| Frontend V3 flow | NOT_STARTED | Frontend Read Model Contract 已冻结 | #80 页面、API client、唯一确认、生成/反馈/个人页 |
| Five-Agent workflow | BLOCKED | 五 Agent 顺序与资源引用已冻结 | 等 #77～#80 后实现 server-authoritative workflow 与 E2E |
| Final automated acceptance | NOT_RUN | 各 foundation PR CI 通过 | Contract + V3 modules + integration + one full backend + all frontend + H5 |
| Final manual acceptance | PENDING | 验收项已列入 manual gates | Desktop H5、Android、OCR、Qwen、Music Provider、MySQL V3 |

## 4. 不可越过的验收不变量

1. 五 Agent 顺序保持 `Assessment → Diagnosis → Prescription → Music → Feedback`。
2. 不改变 Owner 已批准的 V3 用户流程；普通流程只有一次最终 Assessment Confirmation。
3. 未批准医学资产不能进入 production API、RAG、Assessment、Diagnosis 或 Prescription。
4. 按session合同分离：Sprint4/旧V3非clear/resolved继续原门禁；新流程Safety为deferred_v3/not_run/null，不以未执行制造阻断或安全通过，不解除旧风险。
5. Diagnosis abstained且输入有效、满足当前合同其他门禁时，由后端决定emotion_based/wellness；前端不得造处方，也不把未执行筛查写为“安全”。
6. Provider 失败不得伪装生成成功；曲库 fallback 必须标记 `matched_fallback/source_type=matched`。
7. 原文、OCR/ASR文本、Prompt、Key、Provider原始异常和私有 asset locator 不进入普通日志或客户端。
8. Feedback 只改变个人音乐偏好，不改变医学映射、Evidence、Safety 或全局规则。
9. Sprint 4 `emotion_f1` 优化保持 CLOSED；Sprint 5 不恢复 Formal60 调参任务。
10. 有资料上传/摘要确认必填，描述/问卷选填；无资料描述选填、完整10题必填；无音乐目标。
11. OCR失败不进摘要/Agent1；弃用资料服务端切换无资料模式，旧来源不参与后续分析。
12. 摘要文本修正更新事实并确认新revision；最终Assessment确认仍只有一次，最新已确认版本进入Agent2。

## 5. 推荐集成顺序

1. Owner审核本次文档PR；成员合并前不实施与旧合同冲突的生产部分。#77医学资产审批/checksum仍是独立门禁。
2. #78 完成 Understanding Revision、Agent 1、RAG + Agent 2。
3. #79 完成业务 migrations、Agent 4 task/asset API、Feedback/Preference persistence。
4. Agent 3 在 approved Five-Tone mapping 和 immutable Preference Snapshot 上实现。
5. #80 完成只消费 Read Model 的既定 V3 前端流程。
6. #81 实现正常/降级/Revision/closed-loop E2E，加新policy隔离及Sprint4 Safety兼容测试，不实现被暂缓的V3 Safety流程。
7. 只在全部实现会师后运行一次最终自动化 Gate，再执行手工 Gate。

## 6. 当前结论

```text
SPRINT5_FOUNDATION: IN_PROGRESS
MEDICAL_PRODUCTION_CONTENT: BLOCKED
FIVE_AGENT_E2E: NOT_RUN
FINAL_AUTOMATED_ACCEPTANCE: NOT_RUN
FINAL_MANUAL_ACCEPTANCE: PENDING
INTEGRATION_TO_DEV: NOT_READY
```

下一动作：等待 #77 的医学批准，同时继续不加载医学内容的持久化/Provider/验收基础；禁止提前合并 integration → dev、关闭 #81 或宣称 V3 成品完成。

## 7. Owner Flow Amendment 新增验收状态

| 范围 | 本轮状态 | 证据要求 |
|---|---|---|
| 正式流程合同修订 | PENDING_OWNER_REVIEW | 本次docs-only PR，由Owner审核，不自动merge |
| FLOW-01～FLOW-12 | NOT_RUN | 按Amendment第9节逐项记录实现HEAD/测试，不引用旧PASS代替 |
| 新V3专用Safety | DEFERRED / NOT_RUN | 明确限制，不记录Safety PASS；旧版本回归单独验证 |
| Sprint4兼容回归 | NOT_RUN_THIS_CHANGE | 未来适配时验证Q19/Q20、风险状态/路由及普通确认不可清风险 |
| 新版Desktop H5 / Android | PENDING | 两路径、OCR失败/弃用、摘要四操作、无目标、单一最终确认 |

当前仅修订文档；不改业务代码、不合并成员PR、不宣布Sprint5完成。医学内容/API厂商/预算与上线仍依已有Issue和Owner决策推进。
