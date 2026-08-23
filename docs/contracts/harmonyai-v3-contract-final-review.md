# HarmonyAI V3 Contract Final Review

> Review 日期：2026-08-24
> 基线：`origin/integration/sprint4-real-input@08ac591c58edb611c784f673edf61b134b9aedbb`
> 被审合同：`harmonyai-v3-contract-freeze-v3.0.0-draft.3.md`、`frontend-read-model-contract-v3.md`、`harmonyai-v3-persistence-contract.md`
> Review 角色：陈家智（Project Leader & AI Architect）架构收口；Backend / AI 为 Owner 已授权的 Codex 临时代审，不冒用成员签名
> 结论：`STRUCTURAL_CONTRACT_READY_FOR_SIGNOFF`，尚未标记 `FROZEN`

## 1. Owner 不变项

本次修订没有改变以下已批准设计：

1. 五 Agent 仍为 Assessment、Diagnosis、Prescription、Music、Feedback，不增加第六个 Agent。
2. 用户仍按“材料/无材料 → 表达近况 → 音乐目标 → 五脏问卷 → 综合评估 → 一次最终确认 → 辨证 → 处方 → 生成/匹配 → 播放 → 反馈”完成主流程；页面实现可复用已批准的路由，不新增普通确认页。
3. V3 普通问卷为10题五脏问卷；V2 Q19/Q20 不进入 V3 普通流程，但后端 Safety 能力保留。
4. Safety `clear | resolved` 可进入正常音乐轨；confirmed risk 进入安全支持轨，普通 Assessment 确认不能解除 Safety。
5. Diagnosis 不明确不等于没有音乐。安全且信息充分时，Agent 3 使用 ADR-0007 的 `emotion_based | wellness` 保守模式；只有 Safety、未确认或真实无数据才 withheld。
6. 前端不得构造 Assessment、Diagnosis、Prescription 或 Music；Agent 4 真实生成失败时可以使用明确标记的本地曲库 fallback。

## 2. 首次 Review Block Freeze 复核

| Finding | Final Review | 证据 |
|---|---|---|
| BF-01 Canonical 类型 | `CLOSED` | ToneCode 固定 `jiao/zhi/gong/shang/yu`；Profile 使用判别结构 |
| BF-02 Transport / Display | `CLOSED` | 客户端控制字段与用户可见字段分离 |
| BF-03 Understanding / Revision / Safety | `CLOSED` | Provider、确认、不可变 Revision、专用 Safety Resolution、`resolved` 已定义 |
| BF-04 Fact / Organ Evidence | `CLOSED` | `FactEvidence` 与 `OrganEvidenceLink` 分离；逻辑 ID 跨 Revision 稳定 |
| BF-05 RAG + Qwen | `CLOSED` | Query Builder → Retriever → Provider → Schema/Rule Check 与失败矩阵完整 |
| BF-06 Agent 3 / 4 边界 | `CLOSED` | Agent 3 只输出 GenerationSpec；Prompt 只属于 Agent 4 Adapter |
| BF-07 Music 异步状态 | `CLOSED` | Task 判别联合、取消、fallback、AudioAsset、stream 已定义 |
| BF-08 Preference | `CLOSED` | 不可变 Preference Version、处方 Snapshot 引用与两阶段幂等更新一致 |
| BF-09 Frontend Read Model | `CLOSED` | 输入、目标、问卷、确认、安全、依据、生成、播放器、反馈、个人页完整 |
| BF-10 Persistence / Auth | `CLOSED` | V2 PK 兼容、V3表、Revision、事务、Migration、guest Auth ownership 已定义 |

## 3. Draft.3 Final Review 新发现与处理

| ID | 问题 | 处理 | 状态 |
|---|---|---|---|
| FR-P0-01 | SafetyStatus 遗漏 Sprint4 已批准的 `resolved` | Canonical enum、Safety Resolution、正常轨 gate 全部补齐 | `CLOSED` |
| FR-P0-02 | 主合同错误规定 Diagnosis abstained 必须 withheld | 恢复 ADR-0007 四档处方与保守音乐出口 | `CLOSED` |
| FR-P0-03 | Agent 3 需要 UserGoal，但 Frontend 无 Read Model | 增加既有音乐目标步骤的 Read Model；最多两个、主要/次要、其他自填 | `CLOSED` |
| FR-P0-04 | QuestionnaireFactAdapter 生成 Fact 无数据库 owner | NormalizedFact 使用 Understanding / Questionnaire 二选一 owner | `CLOSED` |
| FR-P0-05 | V3 禁止固定 user_id，但没有可执行游客启动 | 增加 guest bootstrap、Auth Context 与客户端 token 边界 | `CLOSED` |
| FR-P0-06 | Fact Revision 文案一处创建新逻辑ID、一处要求稳定ID | 统一为逻辑ID稳定、物理row新增、supersedes row链 | `CLOSED` |
| FR-P0-07 | SafetySupport 使用不存在的 `blocked` enum | 改为 mental / acute 两种真实状态；acute 不提供安抚音频 | `CLOSED` |

## 4. 自动一致性检查

本次检查覆盖：

- 三份合同所有 `json` 代码块可解析；
- Markdown fence 成对；
- `git diff --check`；
- Canonical Tone / Safety / guest auth / questionnaire owner / stable revision / music goal / frontend authority 残留冲突搜索；
- 禁止残留：`safety_status=blocked`、`Diagnosis abstained 必须 withheld`、`questionnaire_submission_json`、旧 superseded/created logical fact IDs。

当前结果：`PASS`。

## 5. 仍需完成的 Freeze Gate

这些不是合同结构缺陷，但在正式把状态改为 `FROZEN` 前不能跳过：

1. **Medical final signoff**：最终10题 Questionnaire Manifest、Claim Dictionary、Organ Mapping阈值/组合规则、五行五音映射与 Knowledge Manifest 需要 Medical Knowledge Engineer 审核并标记 approved/checksum。
2. **Client final signoff**：确认新增 Music Goal、guest bootstrap、Safety resolved/mental/acute 与保守音乐 Read Model 可直接实现，不读取 SERVER_INTERNAL。
3. **AI/Backend executable gate**：建立最小 Contract fixtures / Schema validation / migration skeleton 后，验证字段与状态可以落地；这是实现前第一批任务，不等于开始完整业务功能。
4. 四方结论和 Owner 决定必须记录在 PR #75；在此之前三份文档继续保持 `PROPOSED_FOR_FINAL_REVIEW`。

## 6. Final Decision

```text
STRUCTURAL P0 BLOCKERS: 0
OWNER FLOW CONFLICTS: 0
CONTRACT CONSISTENCY: PASS
MEDICAL PRODUCTION ARTIFACTS: PENDING FINAL SIGNOFF
CLIENT FINAL SIGNOFF: PENDING

FINAL DECISION: READY_FOR_FINAL_SIGNOFF
FROZEN: NO
```

下一步不是让五个人直接写业务代码。先提交本轮合同修订，在 PR #75 上完成 Medical / Client final signoff；同时由 Owner 准备可执行 Contract Gate。签署完成后再把合同状态改为 `FROZEN`，随后启动 Sprint5 第一批开发。
