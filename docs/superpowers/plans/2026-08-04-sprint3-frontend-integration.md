# HarmonyAI Sprint 3 Frontend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从成员前端分支选择性迁移 Sprint 3 八页流程和三个组件，并与真实 v2 API 合同对齐。

**Architecture:** 不合并落后分支的完整历史；从最新 dev 新建分支，只复制页面、组件和必要静态源资源。统一 API 客户端负责 Base URL、错误壳、文件上传和显式 Mock 开关。

**Tech Stack:** Vue 3、uni-app、JavaScript、Node.js、Vite、现有 survey SFC 测试。

## Global Constraints

- 分支名固定为 integration/sprint3-frontend-v2。
- 禁止提交 frontend/unpackage/dist。
- 默认真实 API；Mock 只能由 HARMONYAI_USE_MOCK=true 显式开启。
- 接口和字段以 docs/agent-contract-v2.md 为准。
- 八个页面包含分析加载状态，不额外虚构第九个独立业务页。
- 保留 Sprint 2 页面和旧入口的兼容访问。

---

### Task 1: 创建分支并写 API 合同测试

**Files:**
- Create: `frontend/tests/api-v2-contract.test.mjs`
- Modify: `frontend/common/api-v2.js`

**Interfaces:**
- Consumes: v2 后端接口。
- Produces: createSession、uploadDocument、confirmDocument、submitAssessment、runWorkflow、requestMusic、submitFeedback、getSession。

- [ ] **Step 1: 创建隔离 worktree**

```powershell
git fetch origin
git worktree add -b integration/sprint3-frontend-v2 C:/Users/ASUS/Desktop/HarmonyAI-worktrees/sprint3-frontend origin/dev
```

- [ ] **Step 2: 添加静态合同测试**

```javascript
const source = readFileSync(new URL("../common/api-v2.js", import.meta.url), "utf8")
assert.match(source, /\\/api\\/v2\\/sessions/)
assert.match(source, /\\/api\\/v2\\/documents/)
assert.match(source, /\\/api\\/v2\\/assessments/)
assert.match(source, /\\/api\\/v2\\/workflows/)
assert.match(source, /\\/api\\/v2\\/music/)
assert.match(source, /\\/api\\/v2\\/feedback/)
assert.doesNotMatch(source, /assessment_agent_v2/)
assert.doesNotMatch(source, /USE_MOCK\\s*=\\s*true/)
```

- [ ] **Step 3: 运行测试确认当前客户端不满足**

```powershell
node --test frontend/tests/api-v2-contract.test.mjs
```

Expected: FAIL，因为当前 dev 尚无对齐后的 api-v2.js。

### Task 2: 迁移 API 客户端并显式控制 Mock

**Files:**
- Create: `frontend/common/api-v2.js`
- Create: `frontend/common/sprint3-session.js`
- Test: `frontend/tests/api-v2-contract.test.mjs`

**Interfaces:**
- Consumes: uni.request、uni.uploadFile、uni storage。
- Produces: Task 1 的八个函数和统一 unwrapV2。

- [ ] **Step 1: 实现环境配置**

```javascript
const BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000"
const USE_MOCK = import.meta.env?.HARMONYAI_USE_MOCK === "true"

export function isMockMode() {
  return USE_MOCK
}
```

- [ ] **Step 2: 实现统一 v2 解包**

```javascript
export function unwrapV2(payload) {
  if (payload?.success === true) return payload.data
  const error = new Error(payload?.error?.message || "请求失败")
  error.code = payload?.error?.code || "UNKNOWN_ERROR"
  error.retryable = Boolean(payload?.error?.retryable)
  error.nextActions = payload?.error?.next_actions || []
  throw error
}
```

- [ ] **Step 3: 只实现已冻结端点**

使用 /api/v2/sessions、/documents、/documents/{document_id}/confirmation、/assessments、/workflows、/music、/feedback、/sessions/{session_id}。不得保留 /records、/narrative、/analysis/{id}/status、/prescription/audio。

- [ ] **Step 4: 运行测试并提交**

```powershell
node --test frontend/tests/api-v2-contract.test.mjs
git add frontend/common/api-v2.js frontend/common/sprint3-session.js frontend/tests/api-v2-contract.test.mjs
git commit -m "feat: add Sprint 3 API client"
```

### Task 3: 选择性迁移页面和组件

**Files:**
- Create: `frontend/pages/welcome/welcome.vue`
- Create: `frontend/pages/material/material.vue`
- Create: `frontend/pages/narrative/narrative.vue`
- Create: `frontend/pages/survey-v2/survey-v2.vue`
- Modify: `frontend/pages/result/result.vue`
- Create: `frontend/pages/player-v2/player-v2.vue`
- Create: `frontend/pages/feedback-v2/feedback-v2.vue`
- Create: `frontend/pages/complete/complete.vue`
- Create: `frontend/components/sprint3/error-state.vue`
- Create: `frontend/components/sprint3/image-choice.vue`
- Create: `frontend/components/sprint3/progress-bar.vue`
- Modify: `frontend/pages.json`

**Interfaces:**
- Consumes: Task 2 API client和 session storage。
- Produces: 八页连续流程；AI 分析作为 result 页加载状态。

- [ ] **Step 1: 从成员分支导出指定源文件**

```powershell
git checkout "origin/38-sprint3frontend-重构欢迎页病例上传自由描述与问卷v2" -- frontend/pages/welcome frontend/pages/material frontend/pages/narrative frontend/pages/survey-v2 frontend/pages/result frontend/pages/player-v2 frontend/pages/feedback-v2 frontend/pages/complete frontend/components/sprint3
```

- [ ] **Step 2: 确认没有构建产物**

```powershell
git status --short
git status --short | rg "unpackage|dist"
```

Expected: 第二条命令无输出。

- [ ] **Step 3: 合并 pages.json 路由而非整份覆盖**

保留 dev 的旧页面，新增 welcome、material、narrative、survey-v2、feedback-v2、complete 和 player-v2；result 使用现有路径。启动页改为 welcome，但旧首页仍可访问。

- [ ] **Step 4: 写页面存在性测试**

```javascript
for (const page of [
  "welcome", "material", "narrative", "survey-v2",
  "result", "player-v2", "feedback-v2", "complete",
]) {
  assert.ok(routes.some(route => route.path.includes(page)))
}
```

- [ ] **Step 5: 运行测试并提交迁移**

```powershell
node --test frontend/tests/*.test.mjs
git add frontend/pages frontend/components/sprint3 frontend/pages.json frontend/tests
git commit -m "feat: migrate Sprint 3 user flow"
```

### Task 4: 对齐页面状态与字段

**Files:**
- Modify: `frontend/pages/material/material.vue`
- Modify: `frontend/pages/narrative/narrative.vue`
- Modify: `frontend/pages/survey-v2/survey-v2.vue`
- Modify: `frontend/pages/result/result.vue`
- Modify: `frontend/pages/player-v2/player-v2.vue`
- Modify: `frontend/pages/feedback-v2/feedback-v2.vue`
- Test: `frontend/tests/sprint3-flow-contract.test.mjs`

**Interfaces:**
- Consumes: document_id、document_text、narrative_text、questionnaire_answers。
- Produces: assessment_id、analysis_mode、Music 标准字段和 Feedback V2 请求。

- [ ] **Step 1: 写错误字段扫描测试**

```javascript
const forbidden = [
  "record_id", "assessment_agent_v2", "music_agent_v2",
  "feedback_agent_v2", "/api/v2/records", "/api/v2/narrative",
  "/api/v2/prescription/audio",
]
for (const token of forbidden) assert.equal(source.includes(token), false)
```

- [ ] **Step 2: 对齐上传与确认**

material 页保存 document_id；OCR 成功后展示 extracted_text，用户确认后的文本以 document_text 传入确认接口。失败时提供重新上传、手工补充和跳过。

- [ ] **Step 3: 对齐 Assessment 和 Music**

survey-v2 提交 questionnaire_answers；result 展示 analysis_mode、emotion_profile、physical_profile、extracted_evidence、safety_flags；player-v2 使用 music_id、stream_url、source_type、mode、bpm、duration_seconds、instruments。

- [ ] **Step 4: 对齐 Feedback 2.0**

提交 pre_state、post_state、experience、playback；成功页只展示“个人偏好已更新”，不展示“医学规则已学习”。

- [ ] **Step 5: 运行合同测试并提交**

```powershell
node --test frontend/tests/api-v2-contract.test.mjs frontend/tests/sprint3-flow-contract.test.mjs
git add frontend/pages frontend/tests/sprint3-flow-contract.test.mjs
git commit -m "fix: align Sprint 3 frontend contracts"
```

### Task 5: 构建、人工烟测和 PR

**Files:**
- Verify: `frontend/`
- Update: `frontend/README.md`

**Interfaces:**
- Consumes: Tasks 1-4。
- Produces: 可合并前端 PR。

- [ ] **Step 1: 安装已锁定依赖并运行测试**

```powershell
cd frontend
npm install
node --test tests/*.test.mjs
npm run build:h5
```

Expected: 测试和 H5 构建通过。

- [ ] **Step 2: 检查构建产物未被 Git 跟踪**

```powershell
git status --short | rg "unpackage|dist"
git check-ignore frontend/unpackage/dist/dev/mp-weixin/app.js
```

Expected: 第一条无输出；第二条显示路径已忽略。

- [ ] **Step 3: 使用真实后端烟测**

依次验证欢迎、跳过材料、自由描述、12 题问卷、分析、结果、播放、反馈、完成。再关闭 Qwen 验证 degraded 提示和问卷结果。

- [ ] **Step 4: 完整范围和密钥扫描**

```powershell
git diff --check origin/dev...HEAD
git diff --name-status origin/dev...HEAD
git diff origin/dev...HEAD | rg -n "sk-[A-Za-z0-9._-]{16,}|QWEN_API_KEY="
```

- [ ] **Step 5: 推送、建 PR、普通合并**

```powershell
git push -u origin integration/sprint3-frontend-v2
gh pr create --repo chenjz111/HarmonyAI --base dev --head integration/sprint3-frontend-v2 --title "feat: integrate Sprint 3 competition frontend" --body "Selectively migrates eight Sprint 3 pages and three components; aligns frozen v2 endpoints; real API is default and build artifacts are excluded. Verification: node --test tests/*.test.mjs and npm run build:h5."
$frontendPr = gh pr list --repo chenjz111/HarmonyAI --head integration/sprint3-frontend-v2 --json number --jq '.[0].number'
gh pr merge $frontendPr --repo chenjz111/HarmonyAI --merge
```
