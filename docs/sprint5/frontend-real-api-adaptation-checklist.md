# V3.1 Frontend Real API 适配清单

> 基于 `integration/sprint4-real-input@4224cb7`（2026-09-08 合并后基线）
>
> 创建日期：2026-09-09
> 负责人：彭翔
> 关联：Sprint 5 Final Closeout → Sprint 5 Real Integration

---

## 完全匹配（无需适配）

以下前端接口对应的后端端点已交付且路径/方法一致：

| 前端方法 | 后端端点 | 链路状态 |
|---|---|---|
| `guestAuth()` | `POST /api/v3/auth/guest` | ✅ 已对接 |
| `createSession()` | `POST /api/v3/sessions` | ✅ 已对接 |
| `getSession()` | `GET /api/v3/sessions/{session_id}` | ✅ 已对接 |
| `selectMode()` | `POST /api/v3/sessions/{session_id}/input-transitions` | ✅ 已对接 |
| `discardDocument()` | `POST /api/v3/sessions/{session_id}/input-transitions` | ✅ 已对接 |
| `getCaseSummary()` | `POST /api/v3/understandings` | ✅ 已对接 |
| `confirmUnderstanding()` | `POST /api/v3/understandings/{id}/confirmations` | ✅ 已对接 |
| `submitNarrative()` | `POST /api/v3/understandings` + confirmations | ✅ 已对接 |
| `submitFeedback()` | `POST /api/v3/feedback` | ✅ 已对接 |
| `addFavorite()` | `PUT /api/v3/favorites` | ✅ 已对接 |
| `removeFavorite()` | `DELETE /api/v3/favorites/{music_id}` | ✅ 已对接 |
| `getFavorites()` | `GET /api/v3/favorites` | ✅ 已对接 |
| `getHistory()` | `GET /api/v3/me/history` | ✅ 已对接 |
| `getPreferences()` | `GET /api/v3/me/preferences` | ✅ 已对接 |
| `createAssessment()` | `POST /api/v3/assessments` | ✅ 已对接 |
| `pollMusicGeneration()` | `GET /api/v3/music/generations/{task_id}` | ✅ 已对接 |
| `cancelMusicGeneration()` | `POST /api/v3/music/generations/{task_id}/cancel` | ✅ 已对接 |
| `fetchAuthorizedAudio()` | `GET /api/v3/music/assets/{music_id}/stream` | ✅ 已对接 |

---

## 已知缺口（待 PR #118 / Agent4 交付后对齐）

### 缺口 1：资料上传 (uploadDocument) — 依赖多文档聚合端点

- **前端现状**：内部调用 `POST /api/v2/documents`（V2 通道）上传文件，再调用 V3 `input-transitions/replace_document` 关联会话。
- **根源**：V3.1 多文档有序聚合（DocumentSet / 1~3 份 + owner-aware upload）端点**尚未交付**。
- **当前处理**：real 模式下逐张上传会如实失败并跳转 v3-material-error。
- **Owner**：蔡子鑫（后端）
- **依赖**：PR #??（多方文档聚合端点 PR）

### 缺口 2：疗愈诉求提交 (submitHealingIntent) — 缺后端保存端点

- **前端现状**：仅存 localStorage，无网络调用。
- **根源**：后端暂无疗愈诉求（治疗期望）保存接口。
- **当前处理**：页面标注"本机暂存"。
- **Owner**：待定（后端）
- **依赖**：需新增 `POST /api/v3/goals` 或扩展 Assessment 提交时携带。

### 缺口 3：评估读取/确认 (getAssessment / confirmAssessment)

- **后端现状**：`assessment_router.py` 只有 `POST /api/v3/assessments`（创建评估），**没有** `GET /api/v3/assessments/{id}`（读取评估结果）和 `POST /api/v3/assessments/{id}/confirmations`（确认评估）。
- **前端现状**：real 模式下 `getAssessment()` 抛 `AGENT_PENDING`；`confirmAssessment()` 抛 `AGENT_PENDING`。
- **当前处理**：v3-confirm 页显示"正在等待评估服务接入"，用户可返回。
- **Owner**：Agent 1 / 后端
- **依赖**：PR #??（评估读取 + 确认端点）— 可能为 PR #118

### 缺口 4：问卷 Schema / 提交 (getQuestionnaireSchema / submitQuestionnaire)

- **后端现状**：问卷 schema 数据源在内但无独立 REST 端点；`POST /api/v3/questionnaire/submissions` 提交端点**尚未交付**。
- **前端现状**：`getQuestionnaireSchema()` 从本地 JSON 文件读取；`submitQuestionnaire()` 在 real 模式下抛 `AGENT_PENDING`。
- **当前处理**：mock/hybrid 模式可完整演示；real 模式要求端到端时需后端支持。
- **Owner**：后端（与 Agent 1 或数据团队联动）
- **依赖**：Issue #110（问卷提交端点）

### 缺口 5：五音调适解析 Read Model (getMusicBasis)

- **后端现状**：`diagnosis_router.py` 有 `POST /api/v3/diagnoses`（创建辨证），但前端需要的**读取**五音分析 Read Model 的端点未暴露（本质是辨证结果的 one-shot 读模型，无独立查询端点）。
- **前端现状**：real 模式下 `getMusicBasis()` 抛 `AGENT_PENDING`。
- **当前处理**：mock/hybrid 模式直接返回 fixture 数据。
- **Owner**：Agent 2 / 后端
- **依赖**：PR #??（五音解析 Read Model 端点）

### 缺口 6：音乐生成 (startMusicGeneration) — 依赖辨证处方

- **后端现状**：`POST /api/v3/music/generations` 已交付，但调用方需要提供 `prescription_id`（辨证处方标识），该能力尚未接入。
- **前端现状**：real 模式下 `startMusicGeneration()` 抛 `AGENT_PENDING`。
- **当前处理**：mock 模式生成固定 fixture 音乐；real 模式需等 Agent 4 处方能力稳定。
- **Owner**：Agent 4 / 后端
- **依赖**：PR #??（Agent4 音乐生成能力）

---

## 无后端端点的前端独立行为

以下操作前端可在无后端端点支撑下独立工作（localStorage 或 fixture）：

| 页面/方法 | 机制 | 备注 |
|---|---|---|
| `getQuestionnaireSchema()` | 从本地 `knowledge/v3/questionnaire-v3.0.1.json` 读取 | 冻结后问卷内容不可改 |
| `submitHealingIntent()` | 暂存 localStorage | 页面标注"本机暂存" |
| `getMusic()` | 从 flow state 读取 mock/fixture | 仅 mock 模式 |
| `v3-goal` skip 逻辑 | 前端合约校验 + 本机暂存 | 不涉及后端 |

---

## 前端文件修改清单（对接时需要）

| 文件 | 改动 |
|---|---|
| `frontend/common/api-v3.js` | 为 6 个缺口接口统一编写 realInputApi 实现（目前均为 AGENT_PENDING） |
| `frontend/pages/v3-basis/v3-basis.vue` | `getMusicBasis()` 真实路径改为 realInputApi 调用 |
| `frontend/pages/v3-confirm/v3-confirm.vue` | `getAssessment()` / `confirmAssessment()` 切换为真实调用 |
| `frontend/pages/v3-player/v3-player.vue` | `getMusic()` 从 flow state → 真实 playlist 端点 |
| `frontend/pages/v3-questionnaire/v3-questionnaire.vue` | `submitQuestionnaire()` 从 mock → real |