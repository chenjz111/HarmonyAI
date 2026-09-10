# V3.1 前端真实 API 适配清单（v4 — 复审终版）

> **基线**：`integration/sprint4-real-input@b01c25a801`
> 更新日期：2026-09-10
> 负责人：彭翔
> 关联 PR：#121（Draft，不合并）
> 关联后端 PR：#118（feat/s5-v3.1-ai-backend-integration，open）、#120（feat/s5-v3.1-agent4-minimax，open，旧实现待替换）

---

## 说明与状态定义

本清单仅跟踪**前端适配**状态，不修改冻结用户流程、业务页面、API Contract 或问卷。

三种状态**严格区分、不得混用**：

| 状态 | 含义 |
|------|------|
| **① 后端端点已存在** | 后端（integration 或 PR #118/#120 分支）已提供该 REST 端点，但前端 `api-v3.js` 尚未实现/未切换 |
| **② 前端静态适配完成** | `api-v3.js` 的 `realInputApi` 已真实实现该接口的 URL、HTTP 方法和 Payload（可发起真实请求） |
| **③ 真实联调完成** | 前后端端到端联调已验证通过（目前 **0 项**——PR #118/#120 均未合入 integration） |

> 注：状态②指前端代码层面已按 Contract 实现真实请求；不代表端到端已验证（③）。仅当 ①② 同时成立且后端合入后才能进行 ③。

**统计口径**：所有数量均按 **API 方法数** 统计（`api-v3.js` 导出的方法逐个计数），与表格行数一致。

---

## 三条真实输入路径（页面流）

| 路径 | 描述 | 页面流 |
|------|------|--------|
| **document_only** | 仅凭上传资料完成评估，不填问卷、无疗愈诉求、无第二次近期状态总结 | entry → v3-material → v3-summary → v3-supplement（**直接继续**）→ v3-basis → v3-player →〔反馈本次体验 → v3-feedback → 首页 ｜ 结束本次聆听 → 首页〕 |
| **document_plus_questionnaire** | 上传资料 + 填写问卷 + 疗愈诉求 | entry → v3-material → v3-summary → v3-supplement（**填写问卷**）→ v3-questionnaire → v3-goal → v3-confirm → v3-basis → v3-player →〔反馈本次体验 → v3-feedback → 首页 ｜ 结束本次聆听 → 首页〕 |
| **questionnaire_only** | 仅填写问卷，无资料 + 疗愈诉求 | entry →（无资料入口）→ v3-questionnaire → v3-goal → v3-confirm → v3-basis → v3-player →〔反馈本次体验 → v3-feedback → 首页 ｜ 结束本次聆听 → 首页〕 |

**Player 出口（Feedback 为 Optional）**：
- **反馈本次体验** → v3-feedback → 提交后回首页（也可"暂不反馈"直接回首页）
- **结束本次聆听** → 直接回首页，不经过 v3-feedback

> document_only 在 v3-supplement 选择"直接继续"后经 `createAssessment`（内部分析）直达 v3-basis，**不经过 v3-goal，也不出现第二次近期状态总结确认**。

---

## 状态② 前端静态适配完成（17 个 API 方法）

以下方法在 `api-v3.js` 的 `realInputApi` 中已真实实现 URL + HTTP 方法 + Payload。

| 前端方法 | 后端端点 | 依赖 | 涉及路径 |
|----------|---------|------|---------|
| `guestAuth()` | `POST /api/v3/auth/guest` | integration 已有 | 全部 |
| `createSession()` | `POST /api/v3/sessions` | integration 已有 | 全部 |
| `getSession()` | `GET /api/v3/sessions/{session_id}` | integration 已有 | 全部 |
| `selectMode()` | `POST /api/v3/sessions/{session_id}/input-transitions` | integration 已有 | 全部 |
| `discardDocument()` | `POST /api/v3/sessions/{session_id}/input-transitions` | integration 已有 | 全部 |
| `getCaseSummary()` | `POST /api/v3/understandings` | integration 已有 | document_only, document_plus_questionnaire |
| `confirmUnderstanding()` | `POST /api/v3/understandings/{id}/confirmations` | integration 已有 | 全部 |
| `createAssessment()` | `POST /api/v3/assessments` | integration 已有 | 全部（见缺口 5 的 payload 前置条件） |
| `submitFeedback()` | `POST /api/v3/feedback` | integration 已有 | 全部 |
| `addFavorite()` | `PUT /api/v3/favorites` | integration 已有 | 全部 |
| `removeFavorite()` | `DELETE /api/v3/favorites/{music_id}` | integration 已有 | 全部 |
| `getFavorites()` | `GET /api/v3/favorites` | integration 已有 | 全部 |
| `getHistory()` | `GET /api/v3/me/history` | integration 已有 | 全部 |
| `getPreferences()` | `GET /api/v3/me/preferences` | integration 已有 | 全部 |
| `pollMusicGeneration()` | `GET /api/v3/music/generations/{task_id}` | integration 已有 | 全部 |
| `cancelMusicGeneration()` | `POST /api/v3/music/generations/{task_id}/cancel` | integration 已有 | 全部 |
| `fetchAuthorizedAudio()` | `GET /api/v3/music/assets/{music_id}/stream` | integration 已有 | 全部 |

> **播放器数据来源说明**：`pollMusicGeneration()` 返回的生成任务在 `succeeded` / `matched_fallback` 状态下携带 `audio_asset`（含 `music_ref` / `stream_url` / `duration_seconds`），前端 `persistMusicTask()` 已将其写入 flow state，播放器直接从 flow state 读取并复用**现有受控 stream 接口**（`GET /api/v3/music/assets/{music_id}/stream` + `fetchAuthorizedAudio()`）。**无需为 Player 新增独立"真实结果"端点。**

---

## 状态① 后端端点已存在、前端待适配（7 个 API 方法）

后端端点已在 PR #118/#120 分支提供（未合入 integration），前端 `api-v3.js` 尚未实现真实调用（real 模式仍抛 `AGENT_PENDING` 或本机暂存）。

| 前端方法 | 后端端点（现状） | 提供方 | 涉及路径 |
|----------|-----------------|--------|---------|
| `submitQuestionnaire()` | `POST /api/v3/sessions/{session_id}/questionnaire` | PR #118 | document_plus_questionnaire, questionnaire_only |
| `submitHealingIntent()` | `PUT /api/v3/sessions/{session_id}/user-goal` | PR #118 | document_plus_questionnaire, questionnaire_only |
| `getHealingIntent()` | `GET /api/v3/sessions/{session_id}/user-goal` | PR #118 | document_plus_questionnaire, questionnaire_only |
| `uploadDocument()`（V3 通道） | `POST /api/v3/documents` | PR #118 | document_only, document_plus_questionnaire |
| `replaceDocument()` → DocumentSet | `POST /api/v3/sessions/{session_id}/document-sets` | PR #118 | document_only, document_plus_questionnaire |
| `getDocumentRelevance()` | `GET /api/v3/document-sets/{document_set_id}/relevance` | PR #118 | document_only, document_plus_questionnaire |
| `startMusicGeneration()` | `POST /api/v3/music/generations` | PR #120（旧实现，见 Provider 节） | 全部 |

---

## 已知缺口（后端也未提供的真实缺口）

### 缺口 1：评估读取（getAssessment）
- 后端 `assessment_router.py` 只有 `POST /api/v3/assessments`，**无** `GET /api/v3/assessments/{assessment_id}`。
- 前端：v3-confirm `onLoad()` 调 `getAssessment()`，real 模式抛 `AGENT_PENDING`。
- 依赖：后端新增读取端点（或由 createAssessment 同步返回）。

### 缺口 2：评估确认（confirmAssessment）
- 后端无 `POST/PUT /api/v3/assessments/{assessment_id}/confirmations`。
- 组长裁决（`79cb5e0`）：绝不借用 Understanding confirmation 伪装成功 → real 模式显式阻塞。
- 前端：v3-confirm `confirmAssessment()` 抛 `AGENT_PENDING`，页面显示"正在等待评估服务接入"。
- 依赖：后端新增确认端点。

### 缺口 3：五音解析 Read Model（getMusicBasis）
- 后端 `POST /api/v3/diagnoses` 已在 PR #118 升级为真实 V3.1 辨证管线，但前端需要的是**读取**五音调适解析 Read Model 的端点（诊断结果 + 五音倾向 + 参数设计聚合），未提供。
- 前端：real 模式抛 `AGENT_PENDING`；mock/hybrid 返回 fixture。
- 依赖：后端新增五音解析读取端点。

### 缺口 4：问卷 Schema（getQuestionnaireSchema）
- 后端无 `GET /api/v3/questionnaire/schema` 端点；冻结问卷内容由前端本地 `knowledge/v3/questionnaire-v3.0.1.json` 维护。
- 前端：从本地 JSON 读取（不依赖网络）。
- 判定：冻结合同约束下可继续本地维护，**不视为阻塞**；如需后端托管 schema 需新端点。

### 缺口 5：createAssessment 前置条件
- `createAssessment()` 前端已静态适配（状态②），但仅当 flow state 已有 `understanding_id` 时可直接真实调用；
- document_plus_questionnaire / questionnaire_only 路径因无问卷提交端点（状态① 第 1 项未落地），会抛 `AGENT_PENDING`。
- 依赖：状态①第 1 项（submitQuestionnaire）合入后解锁。

### 缺口 6：V2 上传通道残留
- 前端 `uploadDocument()` 当前走 `POST /api/v2/documents`（V2 multipart）+ V3 `input-transitions/replace_document` 过渡模式。
- PR #118 的 `POST /api/v3/documents` 接收 `DocumentCreateRequest`（JSON，含 file_path/session_id），**未提供 multipart 文件上传通道**。
- 依赖：PR #118 合入后对齐 V3 multipart 支持，或确认服务端 file_path 可访问性。

### 缺口 7：端到端串接（Agent 边界链）
- 生成链路 Agent 边界：
  **Agent2 Diagnosis → Agent3 Prescription/GenerationSpec → prescription_id → Agent4 Generation**
  （`prescription_id` 由 **Agent3** 产出，**不是 Agent2 直接产出**；Agent2 只产出辨证结论。）
- `POST /api/v3/music/generations` 请求体需要 `prescription_id`，该链路依赖 PR #118（PrescriptionV3 / GenerationSpec 模型）与 PR #120（替换后的 Generation Provider），整链未完成端到端验证。
- 依赖：PR #118 + PR #120（替换后）合并并串接验证。

---

## Agent4 Provider 状态

| 项目 | 状态 |
|------|------|
| **MiniMax** | `BLOCKED_BY_PROVIDER_ENTITLEMENT`（当前账户权限不可用） |
| **PR #120**（feat/s5-v3.1-agent4-minimax） | 仍为 MiniMax 实现 → **旧实现待替换**，合入前需确认或等待替换版 |
| **Sprint5 批准目标** | **Stability AI Stable Audio 2.5** |
| **最终适配** | 以蔡子鑫后续提交的分支/PR 为准（前端保持 Provider-neutral 任务/资产接口，不写 Provider 细节进用户页面） |
| **前端原则** | 只按 Provider-neutral 生成任务 + Audio Asset 接口准备 |

---

## 前端适配文件修改清单（待 PR #118/#120 合入后执行）

| 文件 | 改动内容 | 对应状态①/缺口 |
|------|---------|----------------|
| `frontend/common/api-v3.js` | 7 项状态①接口从 AGENT_PENDING/本机暂存 → realInputApi 真实请求 | 状态①全部 |
| `frontend/pages/v3-questionnaire/v3-questionnaire.vue` | `submitQuestionnaire()` 切换至真实端点 | 状态①第 1 项 |
| `frontend/pages/v3-goal/v3-goal.vue` | `submitHealingIntent()` 从 localStorage → `PUT /sessions/{sid}/user-goal` | 状态①第 2/3 项 |
| `frontend/pages/v3-confirm/v3-confirm.vue` | `getAssessment()` / `confirmAssessment()` 真实端点 | 缺口 1/2 |
| `frontend/pages/v3-basis/v3-basis.vue` | `getMusicBasis()` → real 五音解析读取 | 缺口 3 |
| `frontend/pages/v3-material/v3-material.vue` | 接入 V3 document upload + DocumentSet + Relevance | 状态①第 4/5/6 项 |
| `frontend/pages/v3-player/v3-player.vue` | `getMusic()` **优先复用** `pollMusicGeneration()` 已返回的 audio_asset（flow state 已存 stream_url），配合现有受控 stream 接口；仅在不足时才评估新增端点 | 状态①第 7 项（依赖缺口 7 链路） |

---

## Remaining Blockers

1. **PR #118 未合入 integration** → 7 项状态①接口不可落地
2. **PR #120 为旧实现（MiniMax）待替换**，Sprint5 批准目标为 Stability AI Stable Audio 2.5，最终以蔡子鑫提交为准
3. **评估读取与确认端点缺失**（缺口 1/2）— 不在 PR #118 中，需后续补丁
4. **V2 上传通道残留**（缺口 6）— 需 V3 multipart 端点就绪
5. **端到端串接未验证**（缺口 7）— Agent2 Diagnosis → Agent3 Prescription/GenerationSpec → prescription_id → Agent4 Generation 整链
6. **真实联调（状态③）为 0 项** — 所有接口均未完成端到端验证
7. **本 Draft PR (#121) 不合并**，仅作为适配跟踪清单载体
