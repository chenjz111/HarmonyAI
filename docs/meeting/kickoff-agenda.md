# HarmonyAI Kickoff Meeting 议程

> **日期：** 2026-07-15（今晚 21:00）
> **时长：** 30 分钟
> **主持：** 陈家智（Project Leader & AI Architect）
> **参会：** nob、钟睿宸、蔡子鑫、彭翔

---

## 会议目标

1. 统一项目认知——HarmonyAI 到底是什么、不是什么
2. 每个人清楚自己的职责和交付物
3. Sprint 1 目标对齐——7 天后我们要交付什么
4. 确定每日同步机制

---

## 第一部分：项目为什么做（5 分钟）——陈家智

### 一句话定位

> **HarmonyAI 不是一个音乐生成项目，而是一个基于知识驱动的可解释多智能体音乐疗愈系统。**

### 核心信息

- 不是"焦虑 → AI 生成音乐"的黑箱
- 而是"焦虑 → 中医辨证 → 五行 → 五音 → BPM → 乐器 → Prompt → 音乐"的可解释链
- APP 是展示形式，AI 音乐是输出结果，核心技术是中间的决策引擎

### 五个原则（放 README 第一页）

1. **Knowledge First** — 所有 AI 推理基于知识库
2. **Explainability** — 所有输出必须能解释
3. **Human in the Loop** — 关键节点允许人工确认
4. **Modular Design** — 所有 Agent 可独立替换
5. **Fail Gracefully** — 任何环节失败系统仍能运行

### 合规红线

| ❌ 禁止 | ✅ 使用 |
|--------|--------|
| 治疗 | 调理 / 干预 / 辅助改善 |
| 诊断 | 评估 / 辨证分析 |
| 病人 | 用户 |

---

## 第二部分：各角色职责确认（10 分钟）——每人 2 分钟

### 陈家智 — Project Leader & AI Architect

> "我不写业务代码。我定标准，你们执行。我 Review 所有 PR 的架构。"

**Sprint 1 交付物：**
- `knowledge-architecture.md` ✅ V0.1 已完成
- `prompt-architecture.md`
- `agent-architecture.md`
- `mvp-definition.md`
- GitHub 仓库 + 看板 + Issue

### nob — Medical Knowledge Engineer

> "你是整个系统的知识源头。没有你的文献，AI 就是瞎猜。"

**Sprint 1 交付物：**
- `knowledge/v1/` 10-16 篇文献（Level A/B/C/D 各至少 2 篇）
- `knowledge/v1/mapping/` 3 个映射 JSON：
  - `emotion-to-syndrome.json`（情绪→证型）
  - `syndrome-to-tone.json`（证型→调式权重）
  - `tone-to-instrument.json`（调式→乐器推荐）
- 每条知识标注 credibility_level + source

### 钟睿宸 — AI Engineering Lead

> "你是把知识变成 Prompt、把 Prompt 变成音乐的那个人。"

**Sprint 1 交付物：**
- LangGraph Demo（五 Agent 串联跑通）
- Qwen2.5-7B 本地部署 + API
- Prompt Engine 雏形（Template + Parameters → Prompt）
- Chroma + BGE-M3 向量库搭建

### 蔡子鑫 — Backend Platform Engineer

> "你的 API 是前端和 AI 之间的桥梁。Schema 就是你的合约。"

**Sprint 1 交付物：**
- FastAPI 项目脚手架
- Swagger 文档（接口与 Agent Schema 一致）
- MySQL 6 张表：
  - users / sessions / emotion_assessments / syndrome_diagnoses / prescriptions / feedbacks
- Redis 会话管理

### 彭翔 — Client Engineer

> "用户只看到你的界面。他们不知道后面有多少 Agent。"

**Sprint 1 交付物：**
- Figma 3 页：首页 / 问卷 / 音乐播放
- uni-app 项目骨架
- 4 页面完整流程：首页→问卷→评估→播放→反馈

---

## 第三部分：Sprint 1 目标（10 分钟）

### Sprint 1 Goal

> **7 天后，一个用户能从"填问卷"到"听到 AI 生成的五音疗愈音乐"并"给出反馈"。**

### Sprint 1 完整流程（Must Have）

```
首页 → 30题问卷 → 评估结果页 → 辨证结果页 → 音乐处方页 → 播放器 → 反馈页
```

### Sprint 1 各人 Must Have

| 人员 | Must Have（完不成 = Sprint 失败） |
|------|----------------------------------|
| 陈家智 | 3 份 Architecture 文档 + GitHub 看板可用 |
| nob | 8 条核心映射 + 10 篇文献入库 |
| 钟睿宸 | LangGraph Demo 跑通 ①→②→③→④ 四步 |
| 蔡子鑫 | API 能接收问卷、返回处方 JSON |
| 彭翔 | uni-app 4 页面能走通完整流程 |

### Sprint 1 Nice to Have

| 人员 | Nice to Have |
|------|-------------|
| 陈家智 | ADR 独立文档 |
| nob | 20 篇文献 |
| 钟睿宸 | ⑤反馈Agent闭环 |
| 蔡子鑫 | Docker 部署脚本 |
| 彭翔 | 播放器进度条动画 |

### Sprint 1 坚决不做（Out of Scope）

- ❌ OCR（病例上传识别）
- ❌ 语音输入
- ❌ 微信登录
- ❌ 可穿戴设备接入
- ❌ RAG 多轮 Agent
- ❌ 真实音乐生成 API（先用 Mock 音频 + 本地曲库）
- ❌ 用户注册/登录系统（先用 test user）
- ❌ 推送通知

---

## 第四部分：工作节奏（5 分钟）

### 每日同步

- **时间：** 每天晚上 21:00
- **时长：** 最多 15 分钟
- **形式：** 微信群 / 腾讯会议
- **内容：** 每人 1 分钟——今天做了什么 / 阻塞在哪 / 明天做什么

### 分支策略

```
main        ← 保护分支，只通过 PR 合并
  └─ dev    ← 集成分支
       ├─ feat/chenjz   ← 陈家智（文档 + 架构）
       ├─ feat/nob       ← nob（知识库）
       ├─ feat/zhongrc   ← 钟睿宸（AI 引擎）
       ├─ feat/caizx     ← 蔡子鑫（后端）
       └─ feat/pengx     ← 彭翔（前端）
```

### 提交流程

1. 在自己的 feature 分支开发
2. 完成后提 PR 到 dev
3. 陈家智 Review 架构 → 通过后合并
4. Sprint 结束 dev → main

---

## 会议记录

> 实际会议记录见 `docs/meeting/meeting-20260715-kickoff.md`

---

## 附录：会前阅读材料

| 文档 | 路径 | 读者 |
|------|------|------|
| 项目计划书 | `docs/项目计划书.md` | 全员 |
| 团队分工书 | `docs/团队分工书.md` | 全员 |
| 系统架构 | `docs/architecture/system-architecture.md` | 全员（重点看第1章和第2章） |
| Knowledge Architecture | `docs/knowledge-architecture.md` | nob + 钟睿宸（必读） |
| JSON Schema | `docs/architecture/agent-schemas.md` | 钟睿宸 + 蔡子鑫（必读） |
| 开发手册 | `docs/development-handbook.md` | 全员（重点看 Principles 和 DoD） |
