# Sprint 5 Real 模式真实后端依赖清单

> **版本**: 1.0  
> **基准**: PR #116 `feat/s5-v3.1-frontend-closeout` HEAD `e523ac3`  
> **冻结基线**: `83fe2f4` (integration/sprint4-real-input)  
> **状态**: ⏳ 等待后端接口交付 → 前端如实返回 AGENT_PENDING，不伪造成功

---

## 📋 问题索引

| # | 问题描述 | 状态 | 阻塞页面 | 后端依赖 | 联调优先级 |
|---|----------|------|----------|----------|------------|
| 1 | Real 模式主流程提交问卷→五音解析 | ⏳ | v3-questionnaire, v3-basis | POST /api/v3/questionnaire/submissions + 综合评估 Agent | P0 |
| 2 | 真实 1～3 张资料上传与 DocumentSet | ⏳ | v3-material, v3-summary | owner-aware upload + DocumentSet/Relevance 接口 | P0 |
| 3 | 疗愈诉求后端保存与 UserGoal 接入 | ⏳ | v3-goal | POST /api/v3/healing-intents + UserGoal Read Model | P1 |
| 4 | 近期状态总结动态提示词 | ⏳ | v3-summary | GET /api/v3/narrative/prompts（可选） | P2 |
| 5 | Player 真实播放进度 | ✅ | v3-player | GET /api/v3/music/assets/{id}/stream（已交付） | N/A |

---

## 🔴 P0: 核心流程阻塞

### 1️⃣ Real 模式主流程接通（问卷提交→五音解析）

#### 问题说明
- **现象**: 无资料和"有资料 + 问卷"路径提交问卷后均进入 `AGENT_PENDING`;document_only 进入五音解析时也会等待。
- **影响**: 用户无法完成完整评估流程。
- **前端行为**: 捕获 `AGENT_PENDING`错误后显示“服务升级维护中”，保持已填内容。

#### 后端交付清单

| 端点 | 方法 | 请求体字段 | 期望响应字段 | 备注 |
|------|------|-----------|--------------|------|
| `/api/v3/questionnaire/submissions` | POST | `{ schema_id, schema_version, manifest_version, content_checksum, answers: {q01: number, q02: [code,...], ...} }` | `{ questionnaire_submission_id, status: "completed", submitted_at }` | V3.1 冻结基线未交付 |
| `/api/v3/assessments` | POST | `{ session_id, understanding_ref?, questionnaire_ref?, expected_input_revision }` | `{ assessment_id, revision, status: "needs_confirmation", sections[], editable_items[] }` | **已交付** (PR #106) |
| `/api/v3/assessments/{id}` | GET | - | Same as above | Assessment Read Model |
| `/api/v3/assessments/{id}/confirmations` | POST | `{ expected_revision, decision: "confirm"|"confirm_with_changes", changes? }` | `{ revision, status: "confirmed", confirmed_state }` | 待交付 |

> **注意**: `questionnaire_ref` 依赖问卷提交产物（`questionnaire_submission_id`），全链路需后端 Issue #110。

#### 前端代码位置
- `frontend/common/api-v3.js`:
  - `submitQuestionnaire()` → 捕获 AGENT_PENDING
  - `createAssessment()`: document_only 可调用；问卷路径需等待 `questionnaire_ref` 交付
  - `getAssessment()`, `confirmAssessment()` → AGENT_PENDING
- `frontend/pages/v3-questionnaire/v3-questionnaire.vue`:
  - `methods.submitForm()`: try/catch AGENT_PENDING → 显示等待卡
- `frontend/pages/v3-basis/v3-basis.vue`:
  - `load()`: calls `apiV3.getMusicBasis()` → AGENT_PENDING

---

### 2️⃣ 真实 1～3 张资料上传与 DocumentSet

#### 问题说明
- **现状**: Real 模式使用旧 V2 上传链路 (`POST /api/v2/documents`)，存在 V3 资料归属失败（访客用户独立）、多张上传后 Understanding 只取最后一张。
- **需求**: 蔡子鑫提供干净的 DocumentSet/Relevance 接口后完成完整链路。

#### 后端交付清单

| 端点 | 方法 | 请求体字段 | 期望响应字段 | 备注 |
|------|------|-----------|--------------|------|
| `/api/v3/documents` | POST | `(multipart form-data: file, consent_confirmed=true)` | `{ document_id, ocr_status: "ready"|"failed", uploaded_at, owner_session_id }` | **owner-aware upload**, 替代 V2 直写默认用户 |
| `/api/v3/document-sets` | POST | `{ session_id, document_ids: [docId1, docId2], captured_at }` | `{ document_set_id, status: "building"|"valid", document_ids[], total_documents }` | V3.1 新增契约 |
| `/api/v3/document-sets/{set_id}/relevance` | GET | - | `{ relevance_id, document_id, summary, validation_status: "VALID"|"INVALID"|"IRRELEVANT"|"INSUFFICIENT", extracted_at }` | **每张资料的 Relevance** |
| `/api/v3/understandings` | POST | `{ session_id, inputs: [{ source_type:"document", source_id, processing_status:"ready", text_ref }] }` | `{ understanding_id, revision, status, case_summary }` | **消费整个 VALID DocumentSet** |

#### 前端预期逻辑

```javascript
// 1. 上传 1~3 张资料
const docs = await Promise.all(files.map(f => apiV3.uploadDocument(f.path))) // owner-aware

// 2. 建立 DocumentSet
const set = await apiV3.createDocumentSet(session_id, docs.map(d => d.document_id))

// 3. 获取每张 Relevance
const relevances = await apiV3.getDocumentSetRelevances(set.document_set_id)

// 4. 过滤 VALID
const validDocs = relevances.filter(r => r.validation_status === "VALID").map(r => r.document_id)
if (validDocs.length === 0) {
  // 全部 INVALID → 统一异常页 v3-material-error
  uni.navigateTo({ url: "/pages/v3-material-error/v3-material-error" })
  return
}

// 5. 创建 Understanding（聚合所有 valid documents）
await apiV3.createUnderstanding({ session_id, document_ids: validDocs })
// → 进入摘要确认页 v3-summary
```

#### 前端代码位置
- `frontend/common/api-v3.js`: 
  - `realUploadDocument()` → 暂用 V2，需替换为 `/api/v3/documents`
  - 新增 `createDocumentSet()`, `getDocumentSetRelevances()`
- `frontend/pages/v3-material/v3-material.vue`:
  - 多资料上传循环 → 构建 DocumentSet → 检查 Relevance
- `frontend/pages/v3-summary/v3-summary.vue`:
  - `load()`: 读取 Understanding 的 `case_summary` (消费整个 DocumentSet)

---

## 🟡 P1: 次要阻塞

### 3️⃣ 疗愈诉求接入顺序

#### 问题说明
- **现状**: Real 模式疗愈诉求只保存到本机 `localStorage` (`v3_healing_intent`),不能影响后续音乐设计。
- **需求**: 用户填写 Q1~Q10 → 疗愈诉求选填/跳过 → 近期状态总结确认 → UserGoal 作为音乐设计偏好进入 Agent3。
- **冻结规则**: 疗愈诉求不进入 FactEvidence/OrganEvidence/Agent2 医学语义层。

#### 后端交付清单

| 端点 | 方法 | 请求体字段 | 期望响应字段 | 备注 |
|------|------|-----------|--------------|------|
| `/api/v3/healing-intents` | POST | `{ session_id, primary_goal?, secondary_goal?, custom_goal_text? }` | `{ healing_intent_id, status: "recorded", created_at }` | V3.1 新增契约 |
| `/api/v3/user-goals` | GET | `{ session_id }` | `{ user_goals: [{ goal_type, priority, description, captured_at }] }` | UserGoal Read Model |

> **注意**: UserGoal 必须在 `assessment_confirmation` **之后**才用于 Agent3 音乐设计，不与医学语义混淆。

#### 前端预期逻辑

```javascript
// V3.1 正确顺序（v3-goal 页面）
async function submitHealingIntent(payload) {
  // payload: { primary_goal, secondary_goal, custom_goal_text }
  const res = await apiV3.submitHealingIntent(payload) // real: POST /api/v3/healing-intents
  
  if (!res.healing_intent_id) {
    // 后端尚未交付 → 本机暂存 + 明确标注
    safeSet("v3_healing_intent_pending", JSON.stringify(payload))
    uni.showToast({ title: "疗愈诉求已暂存，稍后会同步到云端", icon: "none" })
    return
  }
  
  // 成功后继续下一步：跳转 v3-summary
  uni.redirectTo({ url: "/pages/v3-summary/v3-summary" })
}
```

#### 前端代码位置
- `frontend/common/api-v3.js`:
  - `submitHealingIntent()`: 当前 real 模式 `localStorage` + `saved_locally: true`
  - 需改为 POST 真实接口
- `frontend/pages/v3-goal/v3-goal.vue`:
  - 表单提交 → API 调用 → 跳转 v3-summary
  - **不进入** fact_evidence/organ_evidence 数据流

---

## 🟢 P2: 非阻塞 UI 优化

### 4️⃣ 近期状态总结动态提示词

#### 问题说明
- **需求**: 老师版流程要求“修改内容”后直接编辑通俗的近期状态总结文本，并保存最终确认版本。
- **现状**: 当前只能修改各项程度 (severity slider),需调整为可编辑总结文本。
- **动态提示词**: 如果后端尚未提供，可以暂不伪造，但要明确依赖。

#### 后端交付清单（可选）

| 端点 | 方法 | 请求体字段 | 期望响应字段 | 备注 |
|------|------|-----------|--------------|------|
| `/api/v3/narrative/prompts` | GET | `{ session_id }` | `{ system_prompt: string, example_prompts: [string] }` | 动态提示词模板，非必需 |

> **降级方案**: 若后端未提供，前端固定文案即可：
> “请对以下摘要进行文字修改，使其更准确反映你的近期情况。”

#### 前端代码位置
- `frontend/pages/v3-summary/v3-summary.vue`:
  - `confirmWithChanges()`: 当前仅传 `changes[]` → 增加 `edited_summary_text`
  - 文本域绑定 `summaryText` (默认 `caseSummary.summary`)

---

## ✅ 已完成/部分完成

### 5️⃣ Player 真实播放进度

#### 现状分析
- **已交付**: `GET /api/v3/music/assets/{music_id}/stream`
- **未实现**: 
  - 实时播放时间 (`currentTime`)
  - 基于真实音频 `onTimeUpdate` 更新进度条
  - 总时长显示
  - 不伪造 seek/buffer 状态
  - 播放/暂停按钮改用 CSS 图形/本地图标 (非 Unicode)

#### 后端依赖
- ✅ 已交付，无需额外接口
- 需前端自行实现播放器状态管理

#### 前端代码位置
- `frontend/pages/v3-player/v3-player.vue`:
  - 新增 `currentTime`, `duration`, `bufferRatio`
  - `audioCtx.onTimeUpdate()` 回调
  - CSS 播放/暂停图标 (SVG inline)

---

## 📌 验收标准

| 问题 | 验收条件 |
|------|---------|
| 1️⃣ 主流程接通 | Real 模式下问卷提交成功，assessment_id 由后端生成，非 AGENT_PENDING |
| 2️⃣ 多资料上传 | 上传 1~3 张，DocumentSet 包含所有有效文档，Understanding 聚合所有 VALID Relevance |
| 3️⃣ 疗愈诉求 | healing_intent_id 后端返回，非 `saved_locally: true`，UserGoal 进入 Agent3 |
| 4️⃣ 总结修改 | 可编辑 summary 文本，保存后后端收到 `edited_summary_text` |
| 5️⃣ Player 进度 | 实时 currentTime、duration、progress bar，播放按钮为 CSS 图标 |

---

## 🔗 关联文档

- **冻结合同**: `docs/product/app-v3.1-teacher-user-flow.md`
- **Read Model**: `frontend-read-model-contract-v3.md`
- **Flow Amendment**: `docs/contracts/harmonyai-v3.1-flow-amendment-draft.md`
- **Backend Issue**: #110 (问卷提交), Owner assignment for DocumentSet (#???蔡子鑫)

---

## 🚧 更新日志

| Date | Version | Changes |
|------|---------|---------|
| 2026-09-07 | 1.0 | Initial draft based on PR #116 review feedback |
