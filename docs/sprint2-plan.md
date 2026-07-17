# Sprint 2 计划书（联调 Sprint）

> **版本：** V0.1（Draft，待 Sprint Planning Meeting Review → V1.0）
> **日期：** 2026-07-17
> **作者：** 陈家智（Project Leader & AI Architect）
> **周期：** 两周（Day 1–Day 14，起始日期在启动会上确定）
> **前置条件：** Sprint 1 Review 完成（见第七章）

---

## 第一章：Sprint 2 唯一目标

> **完成五个 Agent 的第一次完整联调，实现"从用户输入 → 生成音乐 → 用户反馈"的完整闭环。**

```
用户打开APP → 填写问卷 → ①Assessment → ②Diagnosis → ③Prescription
            → ④Music Generation → 播放 → ⑤Feedback → 数据库保存 → 结束
```

**注意：不要求 AI 已经很聪明，只要求五个 Agent 第一次全部跑通。**

任何人的任何开发都不能脱离这条主链。

---

## 第二章：开发策略 —— Walking Skeleton（先假后真）

**联调不是最后一步，而是第一步。** 拒绝 Big-Bang Integration（各写两周最后三天拼命）。

```
Day 1-3   五个 Agent 全部先写成 stub（假的）
          每个接口返回硬编码 JSON，严格符合 docs/architecture/agent-schemas.md
             ↓
Day 4     ★ 里程碑①：假数据全链路闭环跑通（五人围观演示）
             ↓
Day 5-12  逐个把假 Agent 换成真 Agent
          每换一个，全链路回归一次
             ↓
Day 13    集成回归 + 修 bug 缓冲日
             ↓
Day 14    ★ 里程碑②：真实闭环正式验收
```

**为什么可行：** agent-schemas.md 在 Sprint 1 已定义所有 Agent 的 I/O 契约（contract-first），
stub 只是把契约里的示例 JSON 返回出来，半天就能写完一个。

**Day 4 起，我们随时拥有一个"能演示的系统"，它每天都在变得更真。**

---

## 第三章：关键技术决策（本 Sprint 生效）

| # | 决策 | 内容 | 理由 |
|---|------|------|------|
| 1 | Music Agent 用**曲库检索**代替真实生成 | 预置 5 调式 × 2-3 首本地音频，Agent 按处方（调式+BPM）从曲库选曲返回 | 真实音乐 API（SkyMusic 等）是最大外部依赖：账号/计费/延迟/稳定性任一项都可能卡死闭环。AI 生成留到 Sprint 3，本 Sprint 接真 API 仅作 Nice to Have |
| 2 | severity 采用 **1-5 数字 + 文字并存** | `severity_level: int(1-5)`（给 AI）+ `severity_name`（给前端） | Sprint 1 已决策，见 knowledge-architecture.md 第 2.2 节。**遇到类似问题先查 Architecture 文档，文档没有才升级为技术决策** |
| 3 | Feedback Agent 本 Sprint 只做**最小版** | 主观评分（1-5 星 + 可选文字）入库即可 | 行为数据、可穿戴设备均在 Out of Scope |
| 4 | 音乐输出本 Sprint 为**单曲** | 7 日处方序列留到 Sprint 3 | 闭环优先，防止范围蔓延 |

---

## 第四章：五人任务分解

### 4.1 陈家智 —— Project Leader & AI Architect（不写业务代码）

| 职责 | 内容 |
|------|------|
| Architecture Review | 每天检查各模块是否偏离 agent-schemas.md / prompt-architecture.md / knowledge-architecture.md |
| Task Management | 每天推进 GitHub 看板（To Do → In Progress → Review → Done）|
| 联调指挥 | Day 4 假数据闭环、Day 14 正式验收的组织与主持 |
| 老师沟通 | 每 3 天同步：完成度 % + 当前问题 + 下步计划 |
| 技术决策 | 主链上的争议问题拍板，重要决策补 ADR |
| 曲库准备 | 确认 5 调式音频的来源与版权（与彭翔协作） |

### 4.2 钟睿宸 —— AI Engineering Lead（工作量最大）

**第一周：**
- Day 2-3：五个 Agent 的 LangGraph stub 骨架（返回 agent-schemas.md 示例 JSON）
- Day 5-8：**Assessment Agent 换真**：问卷 JSON → Qwen2.5-7B 分析 → emotion_profile
  （示例：输入"最近睡不好" → 输出 anxiety / severity_level 3）
- Day 5-8：**Diagnosis Agent 换真**：规则引擎 + Qwen：emotion → syndrome → wuxing
  （示例：焦虑 → 肝郁化火 → 木 → 角调）

**第二周：**
- Day 9-12：**Prescription Agent 换真**：权重网络 + 知识库检索 → music_feature → Prompt Engine 组装 prompt_tags
- Day 9-12：**Feedback Agent 最小版**：评分写入数据库
- 每天必须提交代码到 feat/zhongrc

### 4.3 蔡子鑫 —— Backend Platform Engineer

**第一周：**
- Day 2-3：五个接口骨架，返回 stub JSON，Swagger 全部可访问：
  `POST /assessment` `POST /diagnosis` `POST /prescription` `POST /generation` `POST /feedback`
- Day 2-3：MySQL 落地 session 全链路记录表（每次闭环存一条完整记录）

**第二周：**
- Day 5-12：接口逐个接真 Agent（与钟睿宸同步节奏）
- 异常与降级处理按 agent-architecture.md 第 3 章执行
- 目标不是"写很多接口"，是**这五个接口真正跑起来**

### 4.4 彭翔 —— Client Engineer

**第一周：**
- 问卷页可真实填写、提交，**真实调用** `POST /assessment`（不是静态数据）

**第二周：**
- 完整流程页：点击开始 → Loading → 等待 → 显示音乐 → 播放 → 评分提交
- 对接全部五个真接口
- Day 14 验收全程录屏（录屏直接作为给老师的汇报素材）

### 4.5 nob —— Medical Knowledge Engineer

**Sprint 2 不再泛查论文**，只做四件有清单的事：
1. 按 `knowledge/v1/核验清单-nob.md` 签收 literature.json 12 篇（15-30 分钟）
2. 补明确缺口：Level D ≥2 篇 + 四个证型（心火上炎/脾虚湿困/肺气虚/肾阴不足）现代文献 + 《山东中医杂志》2024 定位
3. **新核心任务：把文献切成 Chroma 可入库的知识块**（格式与钟睿宸对齐，供 RAG 检索）
4. 维护 `knowledge/v1/mapping/*.json` 作为 AI 直接读取的唯一真源（替换全部"待补充"占位符）

---

## 第五章：团队制度（只保留两个，执行到底）

### 5.1 每日日报（异步，代替每日站会）

每晚 21:00 群里发，模板：

```
【姓名】
今日完成：① ② ③
遇到的问题：①
明日计划：① ②
需要帮助：①
```

### 5.2 每 3 天 Sprint Review（现场演示，不是汇报）

| 角色 | 演示方式 |
|------|---------|
| AI | 运行 `python assessment_demo.py` |
| Backend | 打开 `localhost:8000/docs` 现场调接口 |
| Client | 录屏播放 |
| Knowledge | 打开 JSON / Chroma 检索结果 |

**不允许 PPT。** 每周其中一次 Review 增加 30 分钟 Architecture Review，只讨论三个问题：
1. 有没有偏离五 Agent 主链架构？
2. 实现是否符合 agent-schemas.md 等标准？
3. 有没有需要提前处理的技术风险？

---

## 第六章：Definition of Done（DoD）

任何任务不允许说"我写完了"，必须满足：

- [ ] 代码已提交到本人 feat 分支并向 dev 提 PR
- [ ] 本地可运行，不报错
- [ ] 有必要的注释或 README
- [ ] 已通过自测（附截图或录屏）
- [ ] 涉及接口：Swagger 可访问；涉及文档：已同步到 docs/
- [ ] 经陈家智 Review 后才能标记 Done

---

## 第七章：启动会议程（Day 1，120 分钟）

**Sprint 1 还没验收，不能直接开 Sprint 2。** 启动会 = Sprint 1 验收 + Sprint 2 Planning，验收细则见 `docs/sprint1-acceptance.md`：

| 时间 | 内容 |
|------|------|
| 0:00-0:05 | 宣读验收三原则（验可交接性 / Issue 写什么验什么 / 只演示不 PPT） |
| 0:05-0:55 | **Sprint 1 分人验收**：每人 10 分钟现场演示，对照 sprint1-acceptance.md 第三章逐项打勾（含对陈家智的四问测试）；每项当场三选一：通过 / 补课 / 砍掉 |
| 0:55-1:05 | **认知对齐总验收**：每人回答"明天开始 Sprint 2，你第一天写什么？"；通过则宣布四份 Architecture 文档升 V1.0，关闭 Issue #8-#12 |
| 1:05-1:15 | Sprint 2 宣言：不再写文档，开始写系统；唯一目标 = 五 Agent 跑通；画主链图 |
| 1:15-1:25 | 讲解 Walking Skeleton 策略与 Day 4 / Day 14 两个里程碑 |
| 1:25-1:45 | 分任务：逐人过 Sprint 2 Issue #14-#18（具体到"这周完成哪几个接口"），补课项并入第一周 |
| 1:45-2:00 | 定制度：日报模板 + Review 节奏 + DoD；确定 Sprint 2 起始日期 |

---

## 第八章：节奏表与验收

### 8.1 两周节奏

| 时间 | 里程碑 | 验收方式 |
|------|--------|---------|
| Day 1 | Sprint 1 验收 + Sprint 2 Planning（120min） | 签字表 + 会议纪要 + Issue 分配 |
| Day 2-3 | 五个 stub Agent + 五个接口骨架 + 前端问卷页 | Swagger 可访问 |
| **Day 4** | **★ 假数据全链路闭环跑通** | 五人围观演示 |
| Day 5-8 | Assessment + Diagnosis 换真，曲库就位 | demo 脚本运行 |
| Day 9-12 | Prescription + Music(曲库版) + Feedback 换真，前端接真接口 | 录屏 |
| Day 13 | 集成回归 + 修 bug 缓冲日 | — |
| **Day 14** | **★ 正式验收** | 完整闭环录屏存档 |

### 8.2 最终验收标准（唯一）

五个人坐在一起，打开 APP，输入：

> "我最近总是睡不好，经常焦虑，容易烦躁。"

依次看到：Assessment 成功 → Diagnosis 成功 → Prescription 成功 → Music 成功 → 播放成功 → 评分成功 → 数据库成功。

**这一条完整走通，Sprint 2 就是成功。** 全程录屏存档，作为给老师的汇报素材。

---

## 附录：版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| V0.1 | 2026-07-17 | 初始草稿 | 陈家智 |
| V1.0 | — | Sprint Planning Meeting Review 后定稿 | 陈家智 |
