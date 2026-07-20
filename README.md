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

## AI Engineering Sprint 1 本地演示

当前版本包含一个不依赖外部模型服务的 AI 工程最小闭环：评估节点 → 音乐处方节点 → Prompt Engine。运行环境要求 Python 3.10+。

```powershell
python -m pytest -q
python -m backend.ai_engine.demo
```

外部 Qwen 和 Chroma 服务尚未作为运行时依赖接入；Provider 接口与本地 fallback 已预留，便于后续替换。

### Sprint 2 Day 4 Stub 演示

五个 Agent 的 LangGraph stub 可在不启动模型、数据库或音乐 API 的情况下，演示正常闭环和低可信度安全分支：

```powershell
python -m backend.ai_engine.sprint2_demo
```
