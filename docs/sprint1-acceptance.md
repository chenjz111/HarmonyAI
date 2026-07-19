# Sprint 1 验收标准（Acceptance）

> **版本：** V1.0
> **日期：** 2026-07-17
> **作者：** 陈家智（Project Leader & AI Architect）
> **使用场景：** Sprint 1+2 联合会议的前 70 分钟（议程见 sprint2-plan.md 第七章）
> **配套：** 打印附录 A 签字表，现场逐项打勾

---

## 第一章：验收原则（会上先讲这三条）

1. **验收"可交接性"，不验收"工作量"。** 唯一的问题是："你的东西，别人现在能不能接着开发？"
2. **Issue 写什么就验什么。** 验收逐条对照 Issue #8-#12 的原始 checkbox，不加码、不放水——规则双向受约束。
3. **现场演示，不许 PPT。** 代码就运行，接口就打开浏览器，页面就真机点击，知识就打开 JSON。

### Sprint 1 结束的定义（一句话）

> HarmonyAI 已完成架构设计和开发规范，**可以正式进入五 Agent 开发**。

五个总条件：架构明确 ✓ 技术路线明确 ✓ 开发规范明确 ✓ 每人环境可运行 ✓ 所有人知道自己 Sprint 2 第一天做什么 ✓

---

## 第二章：两级验收制

| 级别 | 含义 | 不通过的后果 |
|------|------|-------------|
| **★ 硬门槛** | "别人能否接着开发"的底线 | 该项不过 → Sprint 2 顺延，先补齐 |
| **补课项** | 重要但不阻塞下游 | 不卡 Sprint 2，显式列入 Sprint 2 第一周补课清单（写进对应 Sprint 2 Issue） |

> 禁止第三种状态："差不多了""下周就好"。每一项只能是 通过 / 补课 / 砍掉 三选一，当场记录。

---

## 第三章：分人验收清单

### 3.1 陈家智 —— Project Leader & AI Architect（对照 Issue #8）

| # | 验收项 | 级别 | 验收方式 |
|---|--------|------|---------|
| 1 | 四份 Architecture 文档（knowledge / prompt / agent / mvp-definition）V0.1 完整 | ★ | 现场讲解 10 分钟 |
| 2 | README：新成员 10 分钟内知道项目做什么 | ★ | 让一位成员现场读，复述项目定位 |
| 3 | GitHub 规范：仓库 / dev+5 feat 分支 / Issue / 看板 / ADR×6 | ★ | 打开 GitHub 现场看 |
| 4 | Sprint 2 计划（docs/sprint2-plan.md）+ 本验收文档 | ★ | 已就绪 |
| 5 | **四问测试**（见第四章，不许翻文档） | ★ | 现场问答 |

### 3.2 钟睿宸 —— AI Engineering Lead（对照 Issue #10）

> Sprint 1 验收的不是 Agent，而是**整个 AI 技术路线可行的证明**。

| # | 验收项 | 级别 | 验收方式 |
|---|--------|------|---------|
| 1 | Qwen2.5-7B 本地可调用，返回 JSON 格式正确 | ★ | 现场运行 `model.invoke(...)` |
| 2 | LangGraph Demo：①→②→③→④ 四步串行跑通 | ★ | 现场运行 `python demo.py` |
| 3 | LangGraph 条件边：confidence < 0.4 → 触发提醒 | 补课 | demo 中演示分支 |
| 4 | Chroma + BGE-M3：可写入 + **真实查询**（演示 3 条知识检索，不是只装好） | 补课 | 现场检索 |
| 5 | Prompt Engine 雏形：template_id + parameters → 完整 Prompt 字符串 | ★ | 现场运行，哪怕输出很简单 |

### 3.3 蔡子鑫 —— Backend Platform Engineer（对照 Issue #11）

> Sprint 1 后端不验业务逻辑，只验"骨架立住了、别人能接"。

| # | 验收项 | 级别 | 验收方式 |
|---|--------|------|---------|
| 1 | FastAPI 启动，`localhost:8000/docs` 能打开 | ★ | 现场打开浏览器 |
| 2 | 三个接口骨架可调用：`POST /api/assess`、`GET /api/prescription/{session_id}`、`POST /api/feedback`（返回 todo/示例 JSON 均可） | ★ | Swagger 里现场调 |
| 3 | 返回 JSON 与 agent-schemas.md 一致，含 agent_id / confidence / reason / timestamp 通用字段 | 补课 | 对照 schema 抽查 |
| 4 | MySQL 6 张表：users / sessions / emotion_assessments / syndrome_diagnoses / prescriptions / feedbacks | ★ | `SHOW TABLES;` 截图或现场执行 |

### 3.4 彭翔 —— Client Engineer（对照 Issue #12）

> 只验流程，不验美观。**按 Issue #12 原文验 4 个页面**（"个人中心"不在 Sprint 1 范围，属 Sprint 2+，验收时不得要求）。

| # | 验收项 | 级别 | 验收方式 |
|---|--------|------|---------|
| 1 | Figma 3 页：首页 / 问卷 / 播放（已勾选 ✅，复核） | ★ | 打开 Figma |
| 2 | uni-app 骨架可编译，微信开发者工具可预览（已勾选 ✅，复核） | ★ | 真机/模拟器演示 |
| 3 | 4 页面流程走通：首页 → 问卷 → 处方+播放器 → 反馈（静态数据可接受） | ★ | 现场点击全流程 |
| 4 | 问卷页可交互（30 题可滑动/点击，提交发送到后端） | 补课 | 现场操作 |
| 5 | 播放器能播（音频 URL → 播放/暂停/进度条） | 补课 | 现场操作 |
| 6 | 页面有 loading / success / error 三态 | 补课 | 抽查一个页面 |

### 3.5 肖宇翔 —— Medical Knowledge Engineer（对照 Issue #9）

> 验收的不是"论文多"，是"知识有标准、别人看得懂"。

| # | 验收项 | 级别 | 验收方式 |
|---|--------|------|---------|
| 1 | `knowledge/v1/literature.json` ≥12 篇，每篇含摘要/来源/年份/credibility_level/适用证型 | ★ | 现场打开 JSON |
| 2 | 3 个 Mapping JSON：emotion-to-syndrome / syndrome-to-tone / tone-to-instrument | ★ | 现场打开，抽查权重和=1.0 |
| 3 | Level 配额：A≥2 / B≥3 / C≥3 达标；**D≥2 未达标** | 补课 | 对照 quota_status 字段 |
| 4 | knowledge/ 目录结构别人看得懂 | ★ | 让钟睿宸现场说出他将怎么读取 |

**如实说明：** 文献库与映射 JSON v0.1 由陈家智代整理（肖宇翔 本周有事），**签收核验责任在 肖宇翔**，签收 + Level D 补齐 + 4 个证型缺口已列入 Sprint 2 Issue #18——验收会上照此口径陈述，不含糊为"已完成"。

---

## 第四章：对陈家智的四问测试（不许翻文档）

> 由任一队友当场提问。答不上来 = 架构还没真正掌握 = 本项不通过。
> 参考答案要点如下，**以 agent-schemas.md 实际字段为准**（回答时用真实字段名，不用简化版）。

**问 1：Assessment Agent 输入是什么？**
要点：`input_type`（questionnaire / medical_record）+ 问卷 30 题 Likert 5 级数组；输出 `emotion_profile` 五维（anxiety/depression/anger/fear/overthinking，各含 score/label/severity）+ `dominant_emotion`。

**问 2：Diagnosis Agent 输出什么？**
要点：`syndrome_diagnosis.primary`（syndrome_id / name / element / organ / severity_level 1-5 / severity_name）+ `secondary[]` + `confidence`。注意是 primary/secondary 结构，不是单一 syndrome 字段。

**问 3：Prompt Engine 输入有哪些参数？**
要点：Tone（主辅调+weight）、Emotion 标签、Instrument 组合、Ambient、BPM、Duration、Weight、Constraint（scale_constraint / no_lyrics 等），按 prompt-architecture.md 第 3 章参数体系组装。

**问 4：Music Agent 挂了怎么办？**
要点：按 agent-architecture.md 异常降级——降级到本地曲库（Local Music Library）→ 闭环继续不中断 → confidence 相应下调并写日志。（这正是 Sprint 2 曲库版 Music Agent 的架构依据。）

---

## 第五章：总验收 —— 认知对齐测试

验收会最后，每人回答同一个问题：

> **"如果明天让你开始写 Sprint 2，你知道自己第一天应该写什么吗？"**

通过标准：五个人都能明确回答（应与 Sprint 2 Issue #14-#18 的 Day 2-3 任务吻合），且五个回答能拼成同一个五 Agent 系统。

**Sprint 1 的最终产物不是代码，而是一个已对齐认知、对齐架构、对齐规范的团队。**

---

## 第六章：验收通过后的三个动作（当场执行）

1. **文档升版仪式**：宣布四份 Architecture 文档 V0.1 → **V1.0**，此后任何改动走 RFC 流程（docs/rfc/）
2. **关闭 Issue #8-#12**：通过项打勾关闭；补课项迁移到对应 Sprint 2 Issue（#14-#18）并注明"Sprint 1 补课"
3. **确定 Sprint 2 Day 1 日期**，无缝进入 Sprint 2 Planning 环节

---

## 附录 A：打印版签字表

| 负责人 | 硬门槛（★）交付 | 验收方式 | 通过 | 补课项记录 |
|--------|----------------|---------|:----:|-----------|
| 陈家智 | Architecture 四件套 + README + GitHub 规范 + Sprint 2 计划 + 四问测试 | 现场讲解 + 问答 | ☐ | |
| 钟睿宸 | Qwen 调用 + LangGraph Demo + Prompt Engine 雏形 | 运行 `python demo.py` | ☐ | |
| 蔡子鑫 | FastAPI+Swagger + 3 接口骨架 + MySQL 6 表 | 浏览器 /docs + SHOW TABLES | ☐ | |
| 彭翔 | 4 页面流程可走通（静态可接受） | 真机/录屏演示 | ☐ | |
| 肖宇翔 | 12 篇文献 + 3 个 Mapping JSON + 目录可读 | 打开 JSON 展示 | ☐ | |
| **全员** | 认知对齐测试（第五章） | 逐人回答 | ☐ | |

验收人签字：＿＿＿＿＿＿　日期：＿＿＿＿＿＿
