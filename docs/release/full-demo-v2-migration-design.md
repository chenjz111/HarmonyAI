# full-demo.html V2/V1 双模式迁移设计方案

> **目标文件**: `frontend/full-demo.html`（324 行，独立 HTML）
> **设计原则**: V2 主 Demo + V1 备用 Demo，零外部依赖，比赛安全
> **日期**: 2026-08-05

---

## 一、当前文件结构分析

### 1.1 文件概览

```
full-demo.html (324 lines)
├── <style>  行 7-73    CSS（移动端适配，500px max-width）
├── <body>   行 75-126  HTML（narrative → 问卷 → loading → results）
└── <script> 行 128-323 JS（无框架，纯 fetch + DOM 操作）
```

### 1.2 当前数据流（V1 only）

```
用户输入
  ├── narrative_text (string, max 500)
  └── questions (30题, 3组)
        ├── 情绪状态 (12题)  → answers["q_0_0"] ... answers["q_0_11"]
        ├── 睡眠质量 (8题)   → answers["q_1_0"] ... answers["q_1_7"]
        └── 身体状况 (10题)  → answers["q_2_0"] ... answers["q_2_9"]

submit() 函数:
  ├── 1. fetch POST /api/v1/assessment   {questionnaire, narrative_text}
  ├── 2. fetch POST /api/v1/diagnosis    {session_id, assessment}
  ├── 3. fetch POST /api/v1/prescription {session_id, diagnosis}
  ├── 4. fetch POST /api/v1/generation   {session_id, prescription}
  └── 5. fetch POST /api/v1/feedback     {session_id, generation, overall_satisfaction:4}

showResults() 函数:
  渲染 emotion_profile, syndrome_diagnosis, music_feature, audio.url
```

### 1.3 核心技术约束

| 约束 | 说明 |
|---|---|
| **独立 HTML** | 无法使用 `import` / `export`（ESM 需要服务器或 `type="module"`） |
| **uni-app 不可用** | `api-v2.js` 使用 `uni.request()`，在浏览器中不存在 |
| **无构建步骤** | 不能使用 npm/webpack/vite |
| **fetch 可用** | 浏览器原生 fetch，V1 已在使用 |
| **localStorage 可用** | 可用于 session 持久化（`sprint3-session.js` 的替代） |

> ⚠️ **关键发现**: `frontend/common/api-v2.js` 和 `sprint3-session.js` **无法在独立 HTML 中使用**，因为它们依赖 uni-app API。所有 V2 调用必须用原生 fetch 内联实现。

---

## 二、双模式架构设计

### 2.1 模式选择

```
URL 参数控制（比赛现场无需改代码）:
  full-demo.html              → V2 优先（默认），V2 失败自动降级 V1
  full-demo.html?mode=v2      → 强制 V2
  full-demo.html?mode=v1      → 强制 V1（备用方案）
```

### 2.2 架构全景

```
┌─────────────────────────────────────────────────┐
│                  full-demo.html                   │
│                                                   │
│  ┌──────────┐    ┌──────────────────────┐        │
│  │  Mode    │    │   Shared UI Layer     │        │
│  │  Switch  │───▶│   (narrative + 30Q   │        │
│  │  (v2/v1) │    │    + loading + cards) │        │
│  └──────────┘    └──────────────────────┘        │
│       │                    │                      │
│       ▼                    ▼                      │
│  ┌──────────────┐  ┌──────────────┐              │
│  │  V2 Pipeline │  │  V1 Pipeline │              │
│  │  (NEW)       │  │  (EXISTING)  │              │
│  │              │  │              │              │
│  │ session →    │  │ assess →     │              │
│  │ workflow     │  │ diagnosis →  │              │
│  │  (1 call)    │  │ rx → gen →   │              │
│  │              │  │ feedback     │              │
│  │              │  │  (5 calls)   │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                       │
│         ▼                 ▼                       │
│  ┌──────────────────────────────────────┐        │
│  │        Results Renderer              │        │
│  │  showResultsV2() / showResultsV1()   │        │
│  └──────────────────────────────────────┘        │
│                                                   │
│  Fallback: V2 error → auto-switch to V1          │
└─────────────────────────────────────────────────┘
```

### 2.3 模式切换逻辑

```javascript
// 伪代码 — 实际实现内联在 <script> 中
const DEMO_MODE = (function() {
  var params = new URLSearchParams(location.search);
  if (params.get('mode') === 'v1') return 'v1';
  if (params.get('mode') === 'v2') return 'v2';
  return 'auto';  // V2 优先，失败自动降级
})();

async function runDemo() {
  if (DEMO_MODE === 'v1') {
    return submitV1();  // 现有逻辑，不变
  }
  try {
    return await submitV2();
  } catch (e) {
    if (DEMO_MODE === 'auto') {
      console.warn('V2 failed, falling back to V1:', e.message);
      return submitV1();
    }
    throw e;  // 强制 V2 模式则抛出
  }
}
```

---

## 三、V2 工作流调用设计

### 3.1 完整调用流程

```
Step 1: POST /api/v2/sessions
  Request:  { user_id: "demo_user_001", entry_mode: "full" }
  Response: { session_id: "sess_...", status: "active" }
  ↑ V2 新增：必须先创建 session

Step 2: POST /api/v2/workflows  ← 一次调用替代 V1 的 5 次
  Request: {
    session_id: "<from step 1>",
    user_id: "demo_user_001",
    narrative_text: "最近工作压力大...",    // 可选
    questionnaire_answers: {               // 必填
      schema_version: "questionnaire_v2.0",
      time_window_days: 7,
      answers: [
        { question_id: "q02", value: 3, type: "frequency_0_4", score: 3 },
        // ... 30 题
      ]
    },
    assessment_confirmed: true
  }

  Response: {
    success: true,
    data: {
      assessment: {   ← 替代 V1 的步骤 1
        emotion_profile: { primary_states, secondary_states, dimension_scores, tcm_emotion_candidates },
        analysis_mode: "narrative_questionnaire",
        confidence: 0.85,
        degradation: { triggered: false },
        sources_used: [...],
        safety_flags: [],
        ...
      },
      diagnosis: {    ← 替代 V1 的步骤 2
        syndrome_diagnosis: { primary: { name, element, organ, severity_name } },
        confidence: 0.78,
        ...
      },
      prescription: { ← 替代 V1 的步骤 3
        music_feature: { tone_id, tone_name, bpm, instruments, duration_minutes },
        evidence: [...],
        ...
      },
      music: {        ← 替代 V1 的步骤 4
        track: { title, tone_id, instrument, url, bpm, duration_minutes },
        ...
      },
      // feedback 需要独立提交（V2 的 pre/post 交互）
    },
    meta: { request_id, schema_version: "2.0", timestamp }
  }
```

### 3.2 关键差异：V1 vs V2

| 维度 | V1 | V2 |
|---|---|---|
| HTTP 调用次数 | 5 | 1（+1 session 创建） |
| 问卷格式 | `{q_0_0: 3}` 扁平 | `[{question_id:"q02", value:3, type:"frequency_0_4"}]` |
| 响应格式 | `{session_id, output: {...}}` | `{success, data: {assessment, diagnosis, ...}, meta}` |
| session 创建 | assessment 自动创建 | 需要先 `POST /api/v2/sessions` |
| feedback | 自动提交默认值 | 需独立提交（pre/post state） |
| 降级信息 | `degradation_triggered` bool | `degradation: {triggered, reason_code, fallback}` |
| 情绪维度 key | 中文名（"焦虑"） | dimension_scores dict + tcm_emotion_candidates |

### 3.3 问卷格式映射（核心难点）

V1 的 30 题 `q_0_0` → V2 的 `question_id` 映射：

```javascript
// 映射表（必须在 full-demo.html 中内联定义）
var QUESTION_ID_MAP = {
  // 第1组：情绪状态（12题）
  "q_0_0":  { id: "q02_tension_worry",      type: "frequency_0_4" },
  "q_0_1":  { id: "q03_irritability",       type: "frequency_0_4" },
  "q_0_2":  { id: "q04_low_mood",           type: "frequency_0_4" },
  "q_0_3":  { id: "q05_anhedonia",          type: "frequency_0_4" },
  "q_0_4":  { id: "q06_restlessness",       type: "frequency_0_4" },
  "q_0_5":  { id: "q07_tension_physical",   type: "frequency_0_4" },
  "q_0_6":  { id: "q08_loneliness",         type: "frequency_0_4" },
  "q_0_7":  { id: "q09_emotional_control",  type: "frequency_0_4" },
  "q_0_8":  { id: "q10_fear_anxiety",       type: "frequency_0_4" },
  "q_0_9":  { id: "q11_pessimism",          type: "frequency_0_4" },
  "q_0_10": { id: "q12_impulsivity",        type: "frequency_0_4" },
  "q_0_11": { id: "q13_mental_fatigue",     type: "frequency_0_4" },
  // 第2组：睡眠质量（8题）— 映射到 V2 睡眠相关 question_id
  "q_1_0":  { id: "q14_sleep_onset",        type: "frequency_0_4" },
  "q_1_1":  { id: "q15_sleep_maintenance",  type: "frequency_0_4" },
  "q_1_2":  { id: "q16_early_waking",       type: "frequency_0_4" },
  "q_1_3":  { id: "q17_sleep_depth",        type: "frequency_0_4" },
  "q_1_4":  { id: "q18_dreaming",           type: "frequency_0_4" },
  "q_1_5":  { id: "q19_unrefreshing_sleep", type: "frequency_0_4" },
  "q_1_6":  { id: "q20_daytime_sleepiness", type: "frequency_0_4" },
  "q_1_7":  { id: "q21_sleep_latency",      type: "frequency_0_4" },
  // 第3组：身体状况（10题）— 映射到 V2 身体相关 question_id
  "q_2_0":  { id: "q22_headache",           type: "frequency_0_4" },
  "q_2_1":  { id: "q23_appetite_loss",      type: "frequency_0_4" },
  "q_2_2":  { id: "q24_digestion",          type: "frequency_0_4" },
  "q_2_3":  { id: "q25_constipation",       type: "frequency_0_4" },
  "q_2_4":  { id: "q26_chest_tightness",    type: "frequency_0_4" },
  "q_2_5":  { id: "q27_back_knee_weak",     type: "frequency_0_4" },
  "q_2_6":  { id: "q28_cold_extremities",   type: "frequency_0_4" },
  "q_2_7":  { id: "q29_sweating",           type: "frequency_0_4" },
  "q_2_8":  { id: "q30_dry_mouth",          type: "frequency_0_4" },
  "q_2_9":  { id: "q31_eye_strain",         type: "frequency_0_4" }
};
```

> ⚠️ **需要验证**: 以上 question_id（q02-q31）是基于 `knowledge/questionnaire-v2.json` 的 12 题结构推断的。实际 V2 问卷与 full-demo.html 的 30 题在**题目数量和内容上可能不同**。实现前必须：
> 1. 确认 V2 实际有多少题（12 还是 30）
> 2. 逐一核对每条题目的文字、选项、分值
> 3. 如果数量不匹配，决定是改 demo 题还是改 V2 问卷

### 3.4 buildQuestionnaireV2() 函数设计

```javascript
function buildQuestionnaireV2(answers) {
  var v2answers = [];
  var keys = Object.keys(answers);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var mapping = QUESTION_ID_MAP[key];
    if (mapping) {
      var value = answers[key];
      if (typeof value === 'number' && value >= 1 && value <= 5) {
        v2answers.push({
          question_id: mapping.id,
          value: value,
          type: mapping.type,
          score: value  // V1 1-5 直接映射到 V2 0-4 评分需要调整
        });
      }
    }
  }
  return {
    schema_version: "questionnaire_v2.0",
    time_window_days: 7,
    answers: v2answers
  };
}
```

---

## 四、V1 回退流程

### 4.1 触发条件

```javascript
// 自动降级触发条件
V2_FALLBACK_TRIGGERS = [
  "NETWORK_ERROR",           // fetch 失败（后端未启动）
  "WORKFLOW_FAILED",         // V2 workflow 返回 error
  "WORKFLOW_INPUT_INVALID",  // 问卷格式不兼容
  "SESSION_CREATE_FAILED",   // session 创建失败
  "TIMEOUT",                 // V2 响应超时（>30s）
];
```

### 4.2 降级流程

```
V2 submitV2() 调用
  │
  ├── session 创建成功？
  │   └── NO → 标记降级 → submitV1()
  │
  ├── workflow 调用成功？
  │   └── NO → 标记降级 → submitV1()
  │
  ├── 响应 success === true？
  │   └── NO → 标记降级 → submitV1()
  │
  └── YES → showResultsV2(data)
```

### 4.3 V1 pipeline 保持不变

V1 的 `submit()` 函数完全不动，作为回退路径。它已经过 392 测试验证。

---

## 五、结果渲染适配

### 5.1 V2 → V1 字段映射

```javascript
function showResultsV2(data) {
  // data 是 V2 workflow 的 unwrapped 结果
  var a = data.assessment;
  var d = data.diagnosis;
  var p = data.prescription;
  var m = data.music;

  // 构建 V1 兼容的中间格式，复用现有渲染函数
  var v1compat = {
    session_id: a.session_id,
    output: {
      emotion_profile: {
        dimensions: mapV2DimensionsToV1(a.emotion_profile),
        dominant_emotion: a.emotion_profile.primary_states[0] || "未知",
        dominant_score: Math.max(...Object.values(a.emotion_profile.dimension_scores || {}), 0)
      },
      analysis_mode: a.analysis_mode,
      syndrome_diagnosis: {
        primary: d.syndrome_diagnosis?.primary || {}
      },
      search_keywords: d.search_keywords || [],
      music_feature: p.music_feature || {},
      prompt_template: p.prompt_template || {},
      evidence: p.evidence || [],
      audio: {
        url: m.track?.url || m.audio_url || null
      }
    },
    confidence: a.confidence,
    degradation_triggered: a.degradation?.triggered || false,
    status: a.status
  };

  // 复用现有的 showResults() 渲染逻辑
  showResultsV1Compat(v1compat);
}
```

### 5.2 degradation 提示增强

V2 的 degradation 信息比 V1 更丰富：

```javascript
if (v2data.assessment.degradation?.triggered) {
  var reason = v2data.assessment.degradation.reason_code;
  var fallback = v2data.assessment.degradation.fallback;
  // 显示具体降级原因，而非仅"规则引擎"
  warning.textContent = "当前使用" + (fallback || "本地规则") +
    "（" + (reason || "AI服务不可用") + "）";
}
```

---

## 六、修改文件清单

| # | 文件 | 修改类型 | 行数估计 | 说明 |
|---|---|---|---|---|
| 1 | `frontend/full-demo.html` | **主要修改** | +200 行 | 新增 V2 pipeline + 模式切换 + 降级逻辑 |

**仅修改 1 个文件。** 不需要动后端、api-v2.js、或其他任何文件。

### full-demo.html 修改明细

| 位置 | 操作 | 内容 |
|---|---|---|
| 行 129 `const API` | 保持 | API 地址不变 |
| 行 130 之后 | **新增** | `DEMO_MODE` 检测逻辑（~10 行） |
| 行 132 之后 | **新增** | `QUESTION_ID_MAP` 映射表（~35 行） |
| 行 208 `submit()` 之前 | **新增** | `submitV2()` 函数（~80 行） |
| 行 208 `submit()` | 修改 | 入口改为 `runDemo()` → 分发到 V2 或 V1（~15 行） |
| 行 257 `showResults()` | **新增** | `showResultsV2()` + 中间格式转换（~50 行） |
| 行 313 `resetAll()` | 修改 | 重置 V2 session 状态（~5 行） |
| 错误处理 | **新增** | V2 自动降级到 V1 的 catch 逻辑（~15 行） |

---

## 七、风险分析

| # | 风险 | 等级 | 详细说明 | 缓解措施 |
|---|---|---|---|---|
| 1 | **问卷 question_id 映射不准确** | 🔴 | full-demo.html 的 30 题 vs V2 问卷的 12 题，数量和内容可能不完全匹配 | 实现前先完整对照 `knowledge/questionnaire-v2.json`，生成精确映射表 |
| 2 | **V2 评分尺度不同** | 🔴 | V1 用 1-5 分，V2 用 0-4 分，`score` 字段语义可能不同 | 确认 V2 scoring 规则后再定映射逻辑 |
| 3 | **V2 workflow 不支持 30 题输入** | 🟡 | 如果 V2 只接受 12 题的 V2 问卷，30 题的 V1 demo 数据需要额外映射 | 实现前测试 V2 endpoint 的实际行为 |
| 4 | **V1 作为回退，始终可用** | 🟢 | V1 代码完全不修改，降级路径保证可用 | — |
| 5 | **V2 demo 的 feedback 缺失** | 🟡 | V2 workflow 不自动提交 feedback（需要 pre/post 交互），结果页缺少 feedback 展示 | 接受：比赛 Demo 重点展示 5-Agent 闭环，feedback 在场景 3 单独演示 |
| 6 | **单文件变大** | 🟢 | 从 324 行增加到 ~520 行，仍可维护 | CSS/HTML 不变，仅 JS 增加 |
| 7 | **V2 session 需要数据库** | 🟢 | `/api/v2/workflows` 依赖 `Session` model（SQLite），但 `full-demo.html` 不处理数据库 | 测试已确认 SQLite 零配置可用 |

---

## 八、预计修改时间

| 阶段 | 工作内容 | 时间 |
|---|---|---|
| 1. 问卷映射确认 | 对照 `knowledge/questionnaire-v2.json`，生成 30 题 → V2 精确映射 | 30 min |
| 2. 编写 `submitV2()` | 实现 session 创建 + workflow 调用 + V2 信封解包 | 45 min |
| 3. 编写 `showResultsV2()` | V2 响应 → V1 兼容格式 → 复用现有渲染 | 30 min |
| 4. 模式切换 + 降级逻辑 | DEMO_MODE 检测 + V2→V1 auto-fallback | 20 min |
| 5. 手动测试 | 3 个场景 × 2 个模式 = 6 条路径 | 30 min |
| 6. 测试降级路径 | 故意关后端 → V1 回退；关 Qwen → 降级提示 | 15 min |
| **合计** | | **~3 小时** |

---

## 九、比赛当天操作

```
V2 模式（默认）:
  浏览器打开 full-demo.html → 自动使用 V2 workflow

V1 回退（后端 V2 异常时）:
  浏览器打开 full-demo.html?mode=v1 → 强制使用 V1

零配置切换:
  不需要改代码，不需要重启后端，URL 参数即可切换
```

---

## 十、与其他方案的对比

| 方案 | 改动量 | 风险 | 比赛安全性 | 推荐 |
|---|---|---|---|---|
| A: 原封不动 V1 | 0 | 低 | ⭐⭐⭐ | 保底 |
| B: V2 only | ~150 行 | 中 | ⭐⭐ | 不推荐 |
| **C: V2 + V1 双模式（本方案）** | **~200 行** | **低** | **⭐⭐⭐** | **✅ 推荐** |
| D: 完整重写（Vue 组件化） | 1000+ 行 | 高 | ⭐ | 赛后重构 |

---

## 十一、待确认事项（人工确认）

| # | 事项 | 确认人 |
|---|---|---|
| 1 | V2 问卷实际接受多少题？12 题还是 30 题？| 钟睿宸 |
| 2 | V1 的 30 题与 V2 的 12 题是否可做映射？或需新增 V2 题目？| 肖宇翔 |
| 3 | V2 workflow 的 `assessment_confirmed` 参数在 Demo 中是否应该始终为 `true`？| 陈家智 |
| 4 | 比赛现场是否只演示 V2，还是 V1 也必须可用？| 陈家智 |

---

*由 Claude Code 生成，基于 2026-08-05 完整代码审查。未修改任何代码。*
