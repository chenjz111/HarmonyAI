# V3.1 前端真实 API 适配清单（v2 — 基于 PR #118/#120 更新）

> **基线**：`integration/sprint4-real-input@b01c25a801`（原 `4224cb7` → 合并 PR #114 后前进 3 个提交）
>
> 更新日期：2026-09-09
> 负责人：彭翔
> 关联 PR：#121（Draft，不合并）

---

## 说明

本清单追踪前端 `api-v3.js` 的 27 项 API 方法在三种输入路径下的对接状态。标注"静态契约匹配"的项指前端 URL/方法已按后端 Contract 实现，但**尚未完成端到端真机联调**（后端可能在 PR #118/#120 分支上未合入 integration）。

---

## 三条真实输入路径

| 路径 | 描述 | 关键页面流 |
|------|------|-----------|
| **document_only** | 仅凭上传资料完成评估，不填问卷 | entry → v3-material → v3-summary → v3-supplement(直接继续) → v3-goal → v3-confirm → v3-basis → v3-player → v3-feedback |
| **document_plus_questionnaire** | 上传资料 + 填写问卷 | entry → v3-material → v3-summary → v3-supplement(填写问卷) → v3-questionnaire → v3-goal → v3-confirm → v3-basis → v3-player → v3-feedback |
| **questionnaire_only** | 仅填写问卷，无资料 | entry → (无资料入口) → v3-questionnaire → v3-goal → v3-confirm → v3-basis → v3-player → v3-feedback |

---

## 静态契约匹配（19 项 — URL/方法已对齐，待合并后联调）

以下前端 API 与后端 V3 Contract 在路径、HTTP 方法上一致。其中部分端点已在 PR #118/#120 中交付（未合入 integration），前端 `api-v3.js` 已按契约实现但尚未完成真实端到端验证。

| 前端方法 | 后端端点 | 依赖 PR | 涉及路径 |
|----------|---------|---------|---------|
| `guestAuth()` | `POST /api/v3/auth/guest` | 基线已有 | 全部 |
| `createSession()` | `POST /api/v3/sessions` | 基线已有 | 全部 |
| `getSession()` | `GET /api/v3/sessions/{session_id}` | 基线已有 | 全部 |
| `selectMode()` `discardDocument()` | `POST /api/v3/sessions/{session_id}/input-transitions` | 基线已有 | 全部 |
| `uploadDocument()` + `replaceDocument()` | `POST /api/v3/documents` → `POST /api/v3/sessions/{session_id}/document-sets` | **PR #118** | document_only, document_plus_questionnaire |
| `getCaseSummary()` | `POST /api/v3/understandings` | 基线已有 | document_only, document_plus_questionnaire |
| `confirmUnderstanding()` | `POST /api/v3/understandings/{id}/confirmations` | 基线已有 | 全部 |
| `createAssessment()` | `POST /api/v3/assessments` | 基线已有 | 全部 |
| `getDocumentRelevance()` | `GET /api/v3/document-sets/{document_set_id}/relevance` | **PR #118** | document_only, document_plus_questionnaire |
| `submitQuestionnaire()` | `POST /api/v3/sessions/{session_id}/questionnaire` | **PR #118** | document_plus_questionnaire, questionnaire_only |
| `submitHealingIntent()` | `PUT /api/v3/sessions/{session_id}/user-goal` | **PR #118** | 全部 |
| `getHealingIntent()` | `GET /api/v3/sessions/{session_id}/user-goal` | **PR #118** | 全部 |
| `startMusicGeneration()` | `POST /api/v3/music/generations` | **PR #120** | 全部 |
| `pollMusicGeneration()` | `GET /api/v3/music/generations/{task_id}` | 基线 + **PR #120** | 全部 |
| `cancelMusicGeneration()` | `POST /api/v3/music/generations/{task_id}/cancel` | 基线 + **PR #120** | 全部 |
| `fetchAuthorizedAudio()` | `GET /api/v3/music/assets/{music_id}/stream` | 基线 + **PR #120** | 全部 |
| `submitFeedback()` | `POST /api/v3/feedback` | 基线已有 | 全部 |
| `addFavorite()` / `removeFavorite()` / `getFavorites()` | `PUT/DELETE/GET /api/v3/favorites` | 基线已有 | 全部 |
| `getHistory()` / `getPreferences()` | `GET /api/v3/me/history` / `GET /api/v3/me/preferences` | 基线已有 | 全部 |

---

## 已知缺口（8 项 — 尚未交付，需 PR 合入后逐个落地）

### 缺口 1：资料相关性异常识别与处理

- **前端预期**：上传资料完成后，读取 DocumentSet Relevance 结果 → 如果相关性异常（如 IRRELEVANT / INSUFFICIENT）则跳转 `v3-material-error` 异常页。
- **后端现状**：`GET /api/v3/document-sets/{document_set_id}/relevance` 已在 **PR #118** 中实现，但 Relevance 写入由 Understanding 层内部完成，Read Model 的触发时机和前端轮询策略待确认。
- **前端当前行为**：OCR 失败跳转 `v3-material-error?type=ocr`，网络错误跳转 `?type=network`。尚未接入 Relevance 读取来判断是否"相关性异常"。
- **依赖**：PR #118 合入 integration → 前端新增 `getDocumentRelevance()` 读取

### 缺口 2：评估读取 (getAssessment) — 缺端点

- **后端现状**：`assessment_router.py` 有 `POST /api/v3/assessments`（创建），但**无** `GET /api/v3/assessments/{assessment_id}`（读取）。
- **前端**：v3-confirm 页 `onLoad()` 调 `getAssessment()`，real 模式抛 `AGENT_PENDING`。
- **依赖**：待后端新增读取端点或由 createAssessment 同步返回（应随 PR #118 或后续补丁交付）

### 缺口 3：评估确认 (confirmAssessment) — 缺端点

- **后端现状**：`assessment_router.py` 无 `POST/PUT /api/v3/assessments/{assessment_id}/confirmations`。
- **组长裁决**（`79cb5e0`）："绝不借用 Understanding confirmation 伪装成功"——real 模式显式阻塞。
- **当前处理**：v3-confirm 页 `confirmAssessment()` 在 real 模式抛 `AGENT_PENDING`，用户见"正在等待评估服务接入"。
- **依赖**：待后端新增确认端点（应在 PR #118 链路中补全）

### 缺口 4：五音解析 Read Model (getMusicBasis)

- **后端现状**：`POST /api/v3/diagnoses` 已在 PR #118 中升级为真实 V3.1 辨证管线（含 Agent2 grounding），但前端需要的是 **读模型**——一个集合了诊断结果、五音倾向、参数设计的取回端点。
- **前端**：real 模式抛 `AGENT_PENDING`。
- **当前处理**：mock/hybrid 模式返回 fixture 数据。
- **依赖**：PR #118 合入 → **前端新增诊断读取端点**或五音解析汇总端点

### 缺口 5：问卷 Schema 获取 (getQuestionnaireSchema)

- **后端现状**：无 `GET /api/v3/questionnaire/schema` 端点。Schema 由本地 `knowledge/v3/questionnaire-v3.0.1.json` 维护（冻结内容）。
- **前端**：从本地 JSON 读取，不依赖网络。
- **判定**：前端可继续维持本地读取（冻结合同要求不可改），不视为阻塞。

### 缺口 6：音乐处方依赖 (prescription_id) — gateMusicGeneration

- **后端现状**：`POST /api/v3/music/generations` 的请求体需要 `prescription_id`（辨证处方标识），该标识由 Agent2 诊断链路产出（PR #118 中已定义 `PrescriptionV3` 模型），但**整条链路的端到端串接**尚未完成（diagnosis → prescription → generation task）。
- **前端**：`startMusicGeneration()` 在 real 模式抛 `AGENT_PENDING`，未伪造调用。
- **依赖**：PR #118 + #120 合并后链路打通

### 缺口 7：V2 上传通道残留

- **前端现状**：`uploadDocument()` 内部调 `POST /api/v2/documents`（V2 multipart），再调 V3 `replace_document`。
- **后端现状**：PR #118 新增了 V3 `POST /api/v3/documents`，但**未提供 multipart/文件上传通道**——V3 文档端点目前接收 `DocumentCreateRequest`（JSON 体，含 `file_path`/`session_id`），`file_path` 需在服务端可访问。
- **当前**：前端在后端 V3 上传通道就绪前继续用 V2 上传 + V3 DocumentSet bind 的过渡模式。
- **依赖**：PR #118 合入后需对齐 `POST /api/v3/documents` 的 multipart 支持

### 缺口 8：问卷提交联调

- **后端端点**：`POST /api/v3/sessions/{session_id}/questionnaire` 已在 **PR #118** 中实现。
- **前端现状**：`submitQuestionnaire()` 在 real 模式抛 `AGENT_PENDING`，尚未切换到新端点。
- **Payload 格式**：需确认 `QuestionnaireSubmissionRequest` 的 `answers` 字段与前端 `questionnaire-v3.0.1.json` 的 `question_id` + `value` 格式一致。
- **依赖**：PR #118 合入 → 前端切换端点 + payload 对齐测试

---

## 无后端端点、前端独立维护的项目

| 项目 | 机制 | 备注 |
|------|------|------|
| `getQuestionnaireSchema()` | 本地 `knowledge/v3/questionnaire-v3.0.1.json` | 冻结合同约束，可继续独立维护 |
| v3-goal 页面 skip 逻辑 | 前端合约校验 + localStorage | UserGoal 提交为选填（skip=不调用 endoint 即可） |

---

## Agent4 Provider 信息（仅供内部文档参考，不传入用户页面）

| 项目 | 值 |
|------|-----|
| **Provider** | Stability AI **Stable Audio 2.5**（MiniMax 因当前账户权限不可用为备选） |
| **前端原则** | 只按 Provider-neutral 任务/资产接口准备；不将 Provider 名称、技术细节传入用户页面 |
| **后端适配** | `generation_provider_adapter.py` → `minimax_music_provider.py`（PR #120） |
| **当前阻塞** | 完整链路 Agent2 diagnosis → Prescription → Generation Task 未完成端到端串接 |

---

## 前端适配文件修改清单（待 PR #118/#120 合入后执行）

| 文件 | 改动内容 | 依赖 |
|------|---------|------|
| `frontend/common/api-v3.js` | 为 8 个缺口接口逐步从 AGENT_PENDING 切换到 realInputApi | PR #118/#120 逐个 |
| `frontend/pages/v3-questionnaire/v3-questionnaire.vue` | `submitQuestionnaire()` 切换至 `POST /sessions/{sid}/questionnaire` | 缺口 8 |
| `frontend/pages/v3-goal/v3-goal.vue` | `submitHealingIntent()` 从 localStorage → `PUT /sessions/{sid}/user-goal` | 缺口 6? 实际4 |
| `frontend/pages/v3-confirm/v3-confirm.vue` | `getAssessment()` / `confirmAssessment()` 真实端点 | 缺口 2/3 |
| `frontend/pages/v3-basis/v3-basis.vue` | `getMusicBasis()` → real 五音解析读取 | 缺口 4 |
| `frontend/pages/v3-material/v3-material.vue` | 接入 V3 document upload + DocumentSet + Relevance check | 缺口 1/7 |
| `frontend/pages/v3-player/v3-player.vue` | `getMusic()` 从 flow state → 真实 generation result 端点 | 缺口 6 |

---

## Remaining Blockers

1. **PR #118**（feat/s5-v3.1-ai-backend-integration）未合入 integration → 7 项后端能力不可用
2. **PR #120**（feat/s5-v3.1-agent4-minimax）未合入 integration → 真实音乐生成不可用
3. **评估读取与确认端点缺失**（缺口 2/3）— 不在 PR #118 中，需后续补丁
4. **V2 上传通道残留**（缺口 7）— 需 V3 multipart 端点就绪
5. **端到端串接未完成**：diagnosis → Prescription → Generation Task 整链未验证
6. **本 Draft PR (#121) 不合并**，仅作为适配跟踪清单载体