# MVP Definition（Sprint 1 最小可行产品定义）

> **版本：** V0.1
> **日期：** 2026-07-15
> **作者：** 陈家智（Project Leader & AI Architect）
> **状态：** 待 Kickoff 确认

---

## 文档定位

这份文档**锁定 Sprint 1 的范围**——所有人知道什么必须做、什么坚决不做。

没有这份文档，团队会：
- 不断加需求（"能不能加个 OCR？""能不能加个语音输入？"）
- Sprint 结束时说不清"完成"是什么意思
- 各做各的，最后拼不起来

---

## 第一章：Sprint 1 目标

### 一句话

> **7 天后，一个用户能从"填问卷"到"听到 AI 生成的五音疗愈音乐"并"给出反馈"。**

### 用户故事

```
作为一个感到焦虑的上班族，
我打开 HarmonyAI，
填写一份 30 题的情绪问卷，
系统告诉我"你的证型是肝郁化火"，
推荐了一首角调古筝曲，
我听了 15 分钟后感觉放松了，
给了一个 4 星好评。
```

---

## 第二章：Sprint 1 完整用户流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  首页     │ →  │  问卷页   │ →  │  评估结果  │ →  │  辨证结果  │ →  │  音乐处方  │ →  │  播放器   │
│  Welcome  │    │ 30题Likert│    │ 情绪雷达图 │    │ 证型+可信度│    │ 调式+乐器  │    │ 播放+暂停  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                                                     │
                                                                                     ▼
                                                                              ┌──────────┐
                                                                              │  反馈页   │
                                                                              │ 评分+文字 │
                                                                              └──────────┘
```

### 页面详细说明

| 页面 | 用户看到什么 | 数据来源 | 谁做 |
|------|-------------|----------|------|
| **首页** | 项目名 + 一句话介绍 + 开始按钮 | 静态 | 彭翔 |
| **问卷页** | 30 题 Likert 5 级量表 | 本地 JSON | 彭翔 |
| **评估结果** | 情绪五维雷达图 + 身体指标 | ①评估Agent | 彭翔 + 蔡子鑫 |
| **辨证结果** | 证型名 + 可信度百分比 + 五行归属 | ②辨证Agent | 彭翔 + 蔡子鑫 |
| **音乐处方** | 调式推荐 + 乐器 + BPM + 推荐理由 | ③处方Agent | 彭翔 + 蔡子鑫 |
| **播放器** | 播放/暂停 + 进度条 + 乐器展示 | ④生成Agent | 彭翔 + 蔡子鑫 |
| **反馈页** | 1-5 星评分 + 文字输入 | ⑤反馈Agent | 彭翔 + 蔡子鑫 |

### 完整 API 调用链

```
前端                     后端                      AI
  │                        │                        │
  ├─ POST /api/assess ────→│                        │
  │                        ├─ ①评估Agent ──────────→│
  │                        │←─ emotion_profile ─────┤
  │                        ├─ ②辨证Agent ──────────→│
  │                        │←─ syndrome + conf ─────┤
  │←─ assessment_result ──┤                        │
  │                        │                        │
  ├─ GET /api/prescription→│                        │
  │                        ├─ ③处方Agent ──────────→│
  │                        │←─ daily_plan + prompt ─┤
  │                        ├─ ④生成Agent ──────────→│
  │                        │←─ audio_url ───────────┤
  │←─ prescription_json ──┤                        │
  │                        │                        │
  ├─ POST /api/feedback ──→│                        │
  │                        ├─ ⑤反馈Agent ──────────→│
  │                        │←─ decision + update ───┤
  │←─ feedback_result ────┤                        │
```

---

## 第三章：Must Have（必须完成）

> **这些完不成 = Sprint 失败。每个人只有 3-5 件 Must Have。**

### 陈家智（Project Leader & AI Architect）

| # | Must Have | 验收标准 |
|---|-----------|----------|
| 1 | `knowledge-architecture.md` | 五章完整，nob 确认可据此整理知识库 |
| 2 | `prompt-architecture.md` | 六章完整，钟睿宸确认可据此实现 Prompt Engine |
| 3 | `agent-architecture.md` | 六章完整，钟睿宸 + 蔡子鑫确认可据此实现 |
| 4 | `mvp-definition.md` | 全员确认 Sprint 1 范围 |
| 5 | GitHub 仓库 + 看板 | 5 个 Issue + 5 条 feature 分支 + Projects 看板可访问 |

### nob（Medical Knowledge Engineer）

| # | Must Have | 验收标准 |
|---|-----------|----------|
| 1 | `knowledge/v1/` 10 篇文献 | Level A ≥ 2 篇、B ≥ 3 篇、C ≥ 3 篇、D ≥ 2 篇 |
| 2 | `emotion-to-syndrome.json` | 5 种情绪 → 8 个证型的映射，每条带 credibility_level |
| 3 | `syndrome-to-tone.json` | 8 个证型 → 五音权重，每条带 literature_source |
| 4 | `tone-to-instrument.json` | 5 种调式 → 推荐乐器组合，每条带 experience_source |

### 钟睿宸（AI Engineering Lead）

| # | Must Have | 验收标准 |
|---|-----------|----------|
| 1 | LangGraph Demo | ①→②→③→④ 四步串行跑通，状态机正常 |
| 2 | Qwen2.5-7B 部署 | 本地可调用，返回 JSON 格式正确 |
| 3 | Prompt Engine 雏形 | 输入 template_id + parameters → 输出完整 Prompt 字符串 |
| 4 | Chroma + BGE-M3 搭建 | 向量库可写入/检索，演示 3 条知识检索 |

### 蔡子鑫（Backend Platform Engineer）

| # | Must Have | 验收标准 |
|---|-----------|----------|
| 1 | FastAPI 脚手架 | `/api/assess` + `/api/prescription` + `/api/feedback` 三个端点 |
| 2 | Swagger 文档 | 接口与 Agent Schema 一致，前端可直接参考 |
| 3 | MySQL 6 张表 | users / sessions / emotion_assessments / syndrome_diagnoses / prescriptions / feedbacks |
| 4 | API 能返回处方 JSON | 调用 AI 侧（Mock 也可），返回完整处方 JSON |

### 彭翔（Client Engineer）

| # | Must Have | 验收标准 |
|---|-----------|----------|
| 1 | Figma 3 页 | 首页 / 问卷 / 播放 三页设计稿 |
| 2 | uni-app 项目骨架 | 项目可编译、可在微信开发者工具中预览 |
| 3 | 问卷页可交互 | 30 题可滑动/点击，提交后发送数据到后端 |
| 4 | 播放器能播 | 拿到音频 URL 后能播放、暂停、拖动进度条 |

---

## 第四章：Nice to Have（做了加分，不做不影响）

| # | 内容 | 谁 | 优先级 |
|---|------|-----|--------|
| 1 | 情绪雷达图动画 | 彭翔 | 低 |
| 2 | 播放器进度条动画 | 彭翔 | 低 |
| 3 | ⑤ 反馈Agent 闭环实现 | 钟睿宸 | 低 |
| 4 | Docker 部署脚本 | 蔡子鑫 | 低 |
| 5 | ADR 独立文档抽取 | 陈家智 | 低 |
| 6 | 文献 ≥ 20 篇 | nob | 低 |
| 7 | 反馈数据缓存到 Redis | 蔡子鑫 | 低 |

---

## 第五章：Out of Scope（坚决不做）

> **这些 Sprint 1 绝对不碰。谁说要做，拿这份文档怼回去。**

| # | 不做的东西 | 原因 | 预计 Sprint |
|---|-----------|------|------------|
| 1 | ❌ OCR 病例上传 | 太复杂，需要 PaddleOCR + NER 联调 | Sprint 3+ |
| 2 | ❌ 语音输入 | 需要 ASR，调试周期长 | Sprint 3+ |
| 3 | ❌ 微信登录/注册 | 需要微信开放平台审核 | Sprint 2 |
| 4 | ❌ 可穿戴设备接入 | Apple Watch / 华为 API 对接复杂 | Sprint 4+ |
| 5 | ❌ RAG 多轮 Agent | 知识库先有内容才能做 RAG | Sprint 2 |
| 6 | ❌ 真实音乐生成 API | Sprint 1 用 Mock 音频 + 本地曲库 | Sprint 2 |
| 7 | ❌ 用户画像个性化 | 需要积累反馈数据 | Sprint 3+ |
| 8 | ❌ 推送通知 | 需要微信订阅消息 | Sprint 3+ |
| 9 | ❌ 多语言 / 国际化 | 中文先做好 | 远期 |
| 10 | ❌ 管理员后台 | 不需要 | 远期 |
| 11 | ❌ 数据导出 / 报表 | 不需要 | 远期 |
| 12 | ❌ 性能优化 | 能用就行 | Sprint 3+ |

---

## 第六章：Sprint 1 时间线

```
Day 1 (7/15 周二)
├── 上午：Kickoff Meeting（今晚 21:00）
├── 陈家智完成剩余 Architecture 文档
├── nob 开始找文献
└── 钟睿宸开始搭 LangGraph 环境

Day 2 (7/16 周三)
├── nob 继续文献 + 写第 1 个映射 JSON
├── 钟睿宸 LangGraph Demo v0.1
├── 蔡子鑫 FastAPI 脚手架
└── 彭翔 Figma 首页设计

Day 3 (7/17 周四)
├── 钟睿宸 Prompt Engine 雏形
├── 蔡子鑫 MySQL 建表 + 第 1 个 API
├── 彭翔 uni-app 项目骨架
└── nob 第 2 个映射 JSON

Day 4 (7/18 周五)
├── 钟睿宸 Chroma 向量库搭建
├── 蔡子鑫 全部 3 个 API 端点
├── 彭翔 问卷页 + 评估结果页
└── nob 第 3 个映射 JSON

Day 5 (7/19 周六)
├── 钟睿宸 ①→②→③→④ 联调
├── 蔡子鑫 API 联调
├── 彭翔 播放器 + 反馈页
└── nob 文献入库 Chroma

Day 6 (7/20 周日)
├── 全员联调：前端 → API → AI → 返回
├── 修复联调问题
└── 陈家智架构 Review

Day 7 (7/21 周一)
├── Sprint Review（下午）
├── Demo 演示
├── 收集问题
└── Sprint 2 规划
```

---

## 第七章：Sprint 1 验收标准（DoD）

### 整体验收标准

- [ ] 用户能完成"首页→问卷→评估→辨证→处方→播放→反馈"完整流程
- [ ] 每个 Agent 输出包含全部通用字段
- [ ] 前端页面 4 个（首页 / 问卷 / 处方+播放 / 反馈）
- [ ] 后端 API 3 个（assess / prescription / feedback）
- [ ] MySQL 6 张表有数据
- [ ] AI 侧 ①→②→③→④ 串行跑通
- [ ] 所有代码通过陈家智架构 Review

### 不验收标准

- [ ] UI 好看（V1.0 能用就行）
- [ ] 音频质量高（Mock 就行）
- [ ] 性能快（Sprint 1 不优化）
- [ ] 100% 测试覆盖（Sprint 1 不写测试）

---

## 附录 A：文档版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| V0.1 | 2026-07-15 | 初始版本 | 陈家智 |
| V1.0 | — | Kickoff 确认后定稿 | 团队 |

## 附录 B：参考文档

| 文档 | 路径 |
|------|------|
| 项目计划书 | `docs/项目计划书.md` |
| 团队分工书 | `docs/团队分工书.md` |
| 系统架构 | `docs/architecture/system-architecture.md` |
| Knowledge Architecture | `docs/knowledge-architecture.md` |
| Prompt Architecture | `docs/prompt-architecture.md` |
| Agent Architecture | `docs/agent-architecture.md` |
| Agent JSON Schema | `docs/architecture/agent-schemas.md` |
| 开发手册 | `docs/development-handbook.md` |
