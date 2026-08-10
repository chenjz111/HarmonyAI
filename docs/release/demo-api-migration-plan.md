# Demo API 迁移方案：V1 → V2

> **目标文件**: `frontend/full-demo.html`
> **当前状态**: 使用 Sprint 2 V1 API（5 个独立端点）
> **目标状态**: 迁移至 Sprint 3 V2 API（统一工作流端点）
> **日期**: 2026-08-05

---

## 一、当前 V1 调用分析

`full-demo.html` 在 `submit()` 函数（第 209-252 行）中顺序调用 5 个 V1 端点：

### V1 调用链

| 步骤 | 端点 | 请求体 | 响应中使用的字段 |
|---|---|---|---|
| 1 | `POST /api/v1/assessment` | `{questionnaire, narrative_text}` | `session_id`, `output.emotion_profile`, `output.analysis_mode`, `confidence` |
| 2 | `POST /api/v1/diagnosis` | `{session_id, assessment}` | `output.syndrome_diagnosis.primary`, `output.search_keywords`, `confidence` |
| 3 | `POST /api/v1/prescription` | `{session_id, diagnosis}` | `output.music_feature`, `output.prompt_template`, `output.evidence` |
| 4 | `POST /api/v1/generation` | `{session_id, prescription}` | `output.audio.url` |
| 5 | `POST /api/v1/feedback` | `{session_id, generation, overall_satisfaction:4}` | `output.decision.action` |

### V1 问卷格式（当前）

```javascript
var q = {
  emotion: '',
  tone: '',
  answer_count: Object.keys(answers).length,
  total_questions: 30,
  answers: answers   // {q_0_0: 3, q_0_1: 4, ...}  扁平 key
};
var assessBody = {questionnaire: q};
if (narr) { assessBody.narrative_text = narr; }
```

---

## 二、对应 V2 接口

### 方案 A（推荐）: 单次工作流调用

V2 的 `POST /api/v2/workflows` **一次调用替代 V1 的全部 5 次调用**。

| V1 步骤 | V2 替代 |
|---|---|
| 步骤 1-5 | **1 次** `POST /api/v2/workflows` ← 全部 5 Agent 内部完成 |
| — | 可选: `POST /api/v2/music`（独立曲库匹配） |
| — | 可选: 独立 Feedback 提交（V2 pre/post 对比） |

#### V2 请求格式

```json
POST /api/v2/workflows
{
  "session_id": "<uuid>",
  "user_id": "demo_user_001",
  "narrative_text": "最近工作压力大...",     // 可选
  "document_id": null,                        // 可选
  "document_text": null,                      // 可选
  "questionnaire_answers": {
    "schema_version": "questionnaire_v2.0",
    "time_window_days": 7,
    "answers": [
      {"question_id": "q01", "value": 3, "type": "frequency_0_4", "score": 3},
      {"question_id": "q02", "value": 4, "type": "frequency_0_4", "score": 4}
      // ... 30 题
    ]
  },
  "assessment_confirmed": true
}
```

#### V2 响应格式（统一信封）

```json
{
  "success": true,
  "data": {
    "assessment": { /* AssessmentV2Response */ },
    "diagnosis": { /* DiagnosisV2 result */ },
    "prescription": { /* PrescriptionV2 result */ },
    "music": { /* MusicV2 result */ },
    "feedback": { /* FeedbackV2 result（如果提供 feedback_payload） */ }
  },
  "meta": { "request_id": "...", "schema_version": "2.0", "timestamp": "..." }
}
```

### 方案 B: 分步 V2 调用（与 V1 风格更接近）

| 步骤 | V2 端点 | 说明 |
|---|---|---|
| 1 | `POST /api/v2/assessments` | 仅评估，不执行后续 Agent |
| 2 | `POST /api/v2/workflows` | 评估确认后执行完整工作流 |
| 3 | `POST /api/v2/music` | 独立曲库匹配（通常工作流已包含） |

---

## 三、关键字段变化

### 3.1 问卷格式：扁平 → 结构化

| 维度 | V1 | V2 |
|---|---|---|
| 格式 | `{q_0_0: 3, q_0_1: 4}` | `[{question_id: "q01", value: 3, type: "frequency_0_4"}]` |
| Schema 版本 | 无 | `"questionnaire_v2.0"` |
| 时间窗口 | 无 | `"time_window_days": 7` |
| 最少题目 | 无校验 | ≥12 题 |
| question_id | q_0_0 (section_index) | q01, q02... (规范化 ID) |

### 3.2 响应信封：裸数据 → V2Response

| V1 | V2 |
|---|---|
| 直接返回 `{session_id, output: {...}, confidence}` | 包裹在 `{success, data: {...}, error, meta}` |
| `output.emotion_profile` | `data.assessment.emotion_profile` |
| `output.syndrome_diagnosis` | `data.diagnosis.syndrome_diagnosis` |
| `output.music_feature` | `data.prescription.music_feature` |
| `output.audio.url` | `data.music.audio_url` 或 `data.music.track` |

### 3.3 情绪画像字段

| V1 字段 | V2 字段 |
|---|---|
| `output.emotion_profile.dimensions` (flat by name) | `emotion_profile.dimension_scores` (dict) |
| `output.emotion_profile.dominant_emotion` | `emotion_profile.primary_states[0]` |
| `output.emotion_profile.dominant_score` | `emotion_profile.dimension_scores[primary]` |
| `output.analysis_mode` | `analysis_mode` (enum, 4 values) |

### 3.4 V2 新增字段

| 字段 | 来源 | 前端展示 |
|---|---|---|
| `degradation.triggered` | Assessment | 降级提示条 |
| `degradation.fallback` | Assessment | 降级原因 |
| `sources_used[]` | Assessment | 数据来源标签（病例/文本/问卷） |
| `safety_flags[]` | Assessment | 安全警告 |
| `assessment_summary` | Assessment | AI 评估摘要 |
| `evidence[]` | Prescription | 每条文献的 claim + sources |
| `music.track.title` | Music | 曲目名称 |
| `music.track.instrument` | Music | 乐器名称 |

---

## 四、修改文件

| 文件 | 修改范围 | 风险 |
|---|---|---|
| `frontend/full-demo.html` | 主要修改：`submit()` + `showResults()` + 问卷数据结构 | 🔴 高 |
| `frontend/common/api-v2.js` | 已有 V2 API 客户端，可能需要适配 | 🟢 低 |

### 4.1 full-demo.html 修改清单

| 函数 | 当前行数 | 修改内容 |
|---|---|---|
| `submit()` | 209-252 | 重写：5 次 fetch → 1 次 fetch + V2 信封解包 |
| `showResults()` | 257-311 | 重写：适配 V2 响应字段路径 |
| 问卷渲染 `render()` | 162-201 | 修改：question_id 从 `q_0_0` 改为 `q01` |
| 预设问题常量 `QUESTIONS` | 132-136 | 修改：添加 question_id mapping |
| API 常量 | 129 | 不需要改（仍是 `localhost:8000`） |

### 4.2 不需要修改的文件

- `backend/` — 所有 V2 端点已就绪
- `frontend/common/api-v2.js` — 已完整实现 V2 客户端
- `frontend/demo.html` — 独立文件，不需要同步修改

---

## 五、迁移风险

| # | 风险 | 等级 | 缓解措施 |
|---|---|---|---|
| 1 | **问卷 question_id 映射错误** | 🔴 | 30 题需要精确映射：q_0_0→q01, q_0_1→q02... 必须对照 `knowledge/questionnaire-v2.json` |
| 2 | **V2 响应路径变更导致渲染崩溃** | 🔴 | `data.assessment.emotion_profile` 嵌套层级不同，需逐字段适配 |
| 3 | **V2 工作流不支持无 session_id 调用** | 🟡 | V1 的 assessment 返回 session_id，V2 需预创建 session（`POST /api/v2/sessions`） |
| 4 | **Feedback 2.0 需要 pre/post state** | 🟡 | 当前 V1 自动提交 feedback，V2 需要用户交互提交 pre_state |
| 5 | **Demo 中 5-Agent loading 的步骤动画可能跳太快** | 🟢 | V2 单次调用替代 5 次调用，loading 动画逻辑需调整 |
| 6 | **V2 统一信封的错误处理** | 🟡 | 需新增 `success: false` 的判断分支 |

---

## 六、推荐迁移策略

### 策略：渐进式迁移

```
Step 1: 创建 session
  POST /api/v2/sessions → 获取 session_id

Step 2: 重构问卷数据格式
  {q_0_0: 3} → [{question_id: "q01", value: 3, type: "frequency_0_4"}]

Step 3: 单次工作流调用
  POST /api/v2/workflows → 获取全部 5 Agent 结果

Step 4: 适配结果渲染
  V2 信封解包 → 逐字段映射到现有 showResults() 逻辑

Step 5: (可选) 添加独立 Feedback 交互
  如果时间允许，添加 pre/post 评分 UI
```

### 最小可行迁移（推荐比赛使用）

保持 V1 的 5 次调用模式在 demo.html 中可用（已测试通过），同时在 full-demo.html 中添加 V2 工作流调用作为"高级模式"。两套并跑，比赛时按需选择。

---

## 七、决策建议

| 方案 | 工作量 | 风险 | 推荐 |
|---|---|---|---|
| **A: 完整迁移到 V2 工作流** | ~4h | 中 | 如果比赛前有时间 |
| **B: V1 API 保持 + 添加 V2 工作流按钮** | ~2h | 低 | ⭐ 推荐 |
| **C: 保持 V1（当前状态）** | 0 | 最低 | 如果时间不足 |

> **当前 V1 API 全部正常工作（392 测试通过），后端 V1 端点仍然注册在 main.py 中。比赛现场使用 V1 demo.html 也是可行的。**
>
> 建议：比赛前优先做方案 B（最小改动），赛后迁移到方案 A。

---

*由 Claude Code 生成，基于 2026-08-05 代码审查。未修改任何业务代码。*
