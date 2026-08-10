# HarmonyAI（和鸣AI）

> **Knowledge-Driven / Explainable / Multi-Agent Music Therapy Platform**
>
> 知识驱动的可解释多智能体音乐疗愈平台

---

## 一句话定位

HarmonyAI 不是一个音乐生成项目，而是一个**基于知识驱动（Knowledge-Driven）的可解释多智能体音乐疗愈系统**。APP 是展示形式，AI 音乐是输出结果，核心技术是中间那套"中医知识 → 音乐参数 → AI 生成"的决策引擎。

---

## Project Principles

1. **Knowledge First** — 所有 AI 推理基于 Knowledge Engine，不凭空生成
2. **Explainability** — 所有输出必须可解释，附带推荐理由与文献出处
3. **Human in the Loop** — 医疗建议允许人工确认，关键节点不自动决策
4. **Modular Design** — 所有 Agent 可独立替换，音乐平台/LLM/数据库均可插拔
5. **Fail Gracefully** — 任何模型失败系统仍可运行，有降级策略

---

## 系统架构：三层 + 五 Agent

```
第一层：医学分析层
  ├── ① 评估Agent（检测仪）— 采集量化，输出健康画像
  └── ② 辨证Agent（诊断大脑）— 输出中医证型 + 可信度

第二层：知识映射层 🔥 核心创新
  └── ③ 处方Agent（开方子）— 中医语言 → 音乐参数 → Prompt Tag

第三层：AI生成层
  ├── ④ 生成Agent（煎药机）— 调 API，参数 → 音频
  └── ⑤ 反馈Agent（复诊）— 效果评估，闭环优化
```

---

## 团队

| 角色 | 姓名 |
|------|------|
| Project Leader & AI Architect | 陈家智 |
| Medical Knowledge Engineer | 肖宇翔 |
| AI Engineering Lead | 钟睿宸 |
| Backend Platform Engineer | 蔡子鑫 |
| Client Engineer | 彭翔 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 编排 | LangGraph + Supervisor |
| LLM | Qwen2.5-7B-Instruct |
| 向量数据库 | Chroma + BGE-M3 |
| 后端 | FastAPI (Python 3.10+) |
| 数据库 | MySQL 8.0 + Redis |
| 前端 | uni-app (Vue 3) |
| 部署 | Docker |

---

## 项目结构

```
HarmonyAI/
├── docs/          ← 设计文档（架构/ADR/RFC/会议/比赛）
├── schemas/v1.0/  ← JSON Schema（Agent I/O 合约）
├── prompt/v1/     ← Prompt 模板（版本化）
├── knowledge/v1/  ← 四层知识库（版本化）
├── backend/       ← FastAPI
├── frontend/      ← uni-app
├── api/           ← OpenAPI 规范
├── logs/          ← 运行日志
└── deploy/        ← Docker 部署
```

---

## 项目生命周期

```
Idea → RFC → Architecture → Schema → Development → Review → Merge → Release → Feedback
```

---

## License

MIT

---

## Sprint 3 — Competition Version (v0.3.0)

### 核心能力

| 能力 | 说明 |
|---|---|
| 🌐 **Multi-source Assessment** | 病例上传(PDF/JPG) + 自由文本 + 30题问卷，AI 自动分析来源组合 |
| ⚡ **V2 Unified Workflow** | `POST /api/v2/workflows` 一次调用完成全部 5 Agent 协作 |
| 🎵 **Explainable Music Prescription** | 基于中医五音理论的音乐匹配，附带理论依据和文献出处 |
| 🔄 **Feedback Loop** | Feedback 2.0 pre/post 前后状态对比，量化情绪变化，个人偏好优化 |
| 🛡️ **Degradation Strategy** | Qwen 不可用时→本地规则引擎，任何 Agent 失败系统仍可运行 |

### 五 Agent Workflow

```
输入（自由文本 + 问卷 + 可选病例）
  → Assessment Agent（多源情绪评估）
  → Diagnosis Agent（辅助辨证分析）
  → Prescription Agent（音乐处方匹配）
  → Music Agent（本地曲库匹配）
  → Feedback Agent（效果闭环反馈）
```

### V2 API

| 端点 | 说明 |
|---|---|
| `POST /api/v2/assessments` | 多源状态评估（document + narrative + questionnaire） |
| `POST /api/v2/workflows` | 五 Agent 统一工作流（单次调用） |
| `POST /api/v2/music` | 本地曲库匹配 |
| `POST /api/v2/sessions` | 会话管理 |
| `POST /api/v2/documents` | 病例上传 |
| `POST /api/v2/feedback` | Feedback 2.0 (pre/post state) |

### 降级策略

| 条件 | 行为 |
|---|---|
| Qwen 未配置 | 问卷自动使用确定性规则评分 |
| Qwen 超时/失败 | 降级为本地规则引擎，仍产出完整结果 |
| Knowledge Store 不可用 | 使用审核过的本地五音映射规则 |
| OCR 不可用 | 使用用户预确认的文本输入 |

### Demo

```bash
# 启动后端
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 打开 Demo 页面
浏览器打开 frontend/full-demo.html          # V2 优先，失败自动降级 V1
浏览器打开 frontend/full-demo.html?mode=v1  # 强制 V1 备用链路
```

### 测试

```bash
python -m pytest tests/ -q    # 392 passed
```

---

### Chroma 知识库演示

```powershell
python -m backend.ai_engine.chroma_demo
```

该命令写入 `knowledge/demo_chunks.jsonl` 中的 3 条 D 级演示知识块，并对“焦虑 角调”执行真实 Chroma 查询。演示数据仅验证工程链路，不构成医疗建议；后续可将本地确定性 embedding 替换为 BGE-M3。

## AI Engineering Sprint 1 本地演示

当前版本包含一个不依赖外部模型服务的 AI 工程最小闭环：评估节点 → 音乐处方节点 → Prompt Engine。运行环境要求 Python 3.10+。

```powershell
python -m pytest -q
python -m backend.ai_engine.demo
```

外部 Qwen 服务通过可选的 Qwen-compatible Provider 接入；Chroma 已提供本地持久化和真实查询，Provider 未配置时使用本地 fallback。

### Sprint 2 Real Agent 演示

真实 Agent 通过以下环境变量接入 Qwen/OpenAI-compatible `/chat/completions` 接口；未配置时自动使用本地规则 fallback：

```powershell
$env:QWEN_BASE_URL = "https://your-qwen-compatible-endpoint/v1"
$env:QWEN_API_KEY = "your-api-key"
$env:QWEN_MODEL = "Qwen2.5-7B-Instruct"
```

四个现场 Demo 固定使用本地规则/临时存储，保证无网络也可运行；`run_real_workflow` 在配置上述变量时才会调用 Qwen：

```powershell
python -m backend.ai_engine.assessment_demo
python -m backend.ai_engine.diagnosis_demo
python -m backend.ai_engine.prescription_demo
python -m backend.ai_engine.feedback_demo
```

Assessment、Diagnosis、Prescription 和 Feedback 支持真实适配器；模型未配置或请求失败时会输出降级 warning。Generation 当前仍使用本地曲库 stub，不调用外部音乐生成服务。

### Sprint 2 Day 4 Stub 演示

五个 Agent 的 LangGraph stub 可在不启动模型、数据库或音乐 API 的情况下，演示正常闭环和低可信度安全分支：

```powershell
python -m backend.ai_engine.sprint2_demo
```
