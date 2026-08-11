# HarmonyAI 项目全貌（供 Claude 回顾用）

> 读取此文件即可快速理解项目历史、架构、当前状态。每次对话开始时引用。
> 最后更新: 2026-08-08

---

## 项目定位

- **名称**: HarmonyAI（和鸣AI）
- **一句话**: 知识驱动的可解释多智能体音乐疗愈平台
- **不是**: 音乐生成项目。APP 是展示形式，音乐是输出结果，核心是"中医知识 → 音乐参数"的决策引擎
- **赛道**: AI+医疗服务 → 中医药传承创新 → 情志健康管理
- **团队**: 五人 + 指导老师。陈家智（Project Leader & AI Architect）、肖宇翔（Medical Knowledge Engineer）、钟睿宸（AI Engineering Lead）、蔡子鑫（Backend Platform Engineer）、彭翔（Client Engineer）
- **仓库**: github.com/chenjz111/HarmonyAI
- **本地路径**: C:\Users\ASUS\HarmonyAI
- **旧项目路径**: C:\Users\ASUS\Desktop\ai-music（Codex 操作的工作目录，已废弃，统一到 HarmonyAI）

---

## 架构

### 三层 + 五 Agent

```
第一层：医学分析层
  ├── ① Assessment Agent — 多源状态评估
  └── ② Diagnosis Agent — 辅助辨证分析

第二层：知识映射层（核心创新）
  └── ③ Prescription Agent — 中医证型 → 音乐参数

第三层：AI 生成层
  ├── ④ Music Agent — 本地曲库匹配（非 AI 生成）
  └── ⑤ Feedback Agent — pre/post 闭环反馈
```

### 技术栈

| 层 | 技术 |
|---|---|
| Agent 编排 | LangGraph (StateGraph, 条件路由) |
| LLM | Qwen2.5-7B-Instruct (OpenAI-compatible /chat/completions) |
| 向量数据库 | Chroma + BGE-M3 |
| 后端 | FastAPI (Python 3.10+) |
| 数据库 | SQLite (默认) / MySQL 8.0 |
| 前端 | uni-app (Vue 3) + 独立 HTML Demo |
| 测试 | pytest (**422 tests**，其中 30 contract) |

### 五音映射（核心规则，不调 LLM）

```
证型 → tone_id → TONE_CONFIG
  jiao (角调): bpm=68, instruments=["古筝","古琴"]
  zhi  (徵调): bpm=70, instruments=["琵琶","古琴"]
  gong (宫调): bpm=62, instruments=["编钟","古琴"]
  shang(商调): bpm=66, instruments=["二胡","洞箫"]
  yu   (羽调): bpm=58, instruments=["箫","古琴"]
```

---

## 版本历史

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1.0 | 2025-07 | 项目初始化、Sprint 1: FastAPI 脚手架 + 前端 |
| v0.2.0 | 2026-07-22 | Sprint 2: 5-Agent 独立端点 + Real Agent + Chroma |
| **v0.3.0** | **2026-08-04** | **Sprint 3: V2 工作流 + 多模态 + Feedback 2.0 + 降级** |
| v0.4.0 | 计划中 | Sprint 4: 真实输入与可信状态理解 |

---

## Sprint 3 完成状态（v0.3.0）

### PR 合并记录
- 8 个 PR (#43-#50) 全部合并到 dev
- PR #43: feat/free-text-assessment — 自由文本评估 (2026-07-27)
- PR #44: feat/nob — 问卷 V2 + 安全规则审核 (2026-08-04)
- PR #45: feat/chenjz-sprint3-lead — Agent Contract V2 + Release Gates (2026-08-04)
- PR #46: feat/caizx — Sprint 3 Backend (2026-08-04)
- PR #47: integration/sprint3-knowledge — 医学知识集成 (2026-08-04)
- PR #48: fix/sprint3-backend-integration — 后端集成修复 (2026-08-04)
- PR #49: integration/sprint3-ai-v2 — AI Agent V2 集成 (2026-08-04)
- PR #50: integration/sprint3-frontend-v2 — 前端竞赛版集成 (2026-08-04)
- PR #51: feat/full-demo-v2-competition — V2/V1 双模式 Demo + 版本修复 + 依赖补全 (合并到 dev @ a38099c)

### 核心能力
- V2 统一工作流: POST /api/v2/workflows 一次调用完成 5 Agent
- 多模态输入: 病例上传(document) + 自由文本(narrative) + 问卷(questionnaire)，4 种 analysis_mode
- Feedback 2.0: pre/post state 对比，10 个反馈维度
- Qwen 降级: 未配置时自动切换到本地规则引擎（不是 Bug，是功能）
- 安全规则引擎: 自杀/自残/胸痛/呼吸困难关键词拦截，LLM 调用前阻断
- 比赛版 Demo: full-demo.html (759 行, V2/V1 双模式, URL 参数切换)
- 版本号统一为 0.3.0（pyproject.toml / .env.example / config.py 三处一致）
- 当时 392 个 Sprint 3 测试全部通过；首次加入 16 个 Sprint 4 contract tests 后为 408 tests（历史记录，当前计数见下方状态表）

### 版本修复（PR #51）
- pyproject.toml: 0.1.0 → 0.3.0
- .env.example: 补充 QWEN_BASE_URL / QWEN_API_KEY / QWEN_MODEL / HARMONYAI_REAL_AGENTS
- requirements.txt: 补充 langgraph>=0.2 / chromadb>=1.2
- backend/app/core/config.py: APP_VERSION 1.0.0 → 0.3.0

### 已知限制
- OCR 是 Stub（永远返回固定 mock 文本）
- 曲库仅 1 首 Demo (jiao-demo.wav)
- 自由文本：没配 Qwen Key 时被静默忽略
- 问卷: 12 题 V2.0，单题基本对应单维度
- 前端完整 Vue App 需要 HBuilderX 构建
- 没有用户确认流程，没有证据追溯

---

## Sprint 4 详细规划（v0.4.0）

### 核心目标
真实输入 + 可信状态理解：OCR 真实识别、自由文本不再静默丢弃、每条结论有证据、信息不足时追问或拒绝判断。

### 产品流程
```
上传材料(可选) → 真实OCR → 确认文本
  → 自由描述(可选) → Qwen提取
  → 20题问卷(必填)
  → Assessment Agent 三源融合
  → 冲突检测 + 缺失信息 + 动态追问(0-4题)
  → 用户确认 → Diagnosis Agent → Prescription → Music → Feedback
  → 每次听前: 6题 Quick State → 听后重复前5题 → delta计算
```

### 问卷体系
| 问卷 | 版本 | 题数 | 用途 |
|---|---|---|---|
| 阶段性完整评估 | questionnaire_v2.1 | 20 | 首次/定期评估 |
| 快速状态 | quick_state_v1 | 6 | 每次听前 (0-10量尺) |
| 动态追问 | follow_up_v1 | 0-4 | Assessment触发 (决策树, 不用LLM) |
| 旧版兼容 | questionnaire_v2.0 | 12 | Sprint 3 兼容 |

### 不做事项
真实音乐生成 API / 扩充曲库 / 修改五音映射 / 用户注册 / 会员支付 / 七日方案 / 可穿戴设备 / 重设计App / Agent改名 / Docker CI/CD / 宣称临床诊断量表

### 集成分支
`integration/sprint4-real-input@c456f2b` 已 fast-forward 合并并推送到 `dev`；S4-01 状态为 FROZEN / MERGED。

### PR 顺序
S4-01(陈家智,contracts) → S4-02(肖宇翔,问卷+eval) → S4-03(蔡子鑫,OCR+backend) → S4-04(钟睿宸,AI) → S4-05(彭翔,frontend) → S4-06(陈家智,集成验收)

### 12天排期
Day1(契约冻结) → Day2(问卷初稿+PaddleOCR POC) → Day3(契约落地) → Day4-5(并行开发) → Day6(第一次联调) → Day7-8(融合追问) → Day9(前端闭环) → Day10(评估日,60cases) → Day11(修复回归) → Day12(Sprint Review)

### 风险评估
| 等级 | 风险 | 缓解 |
|---|---|---|
| 🔴 | PaddleOCR准确率未知 | Day2用5份真实医疗文档POC, <70%降级 |
| 🔴 | 60案例标注20-30小时 | 分批: 30精细+30基础, 自动预标注 |
| 🔴 | 彭翔前端7页面可能超8天 | P0(核心3页)→P1(2页)→P2(2页) |
| 🟡 | 动态追问复杂度高 | Sprint4只用硬编码决策树, 不上LLM追问 |
| ✅ | Q04 worry_control double-count | 已冻结为 `scored=false`、`weight=0`，仅作定性 Evidence |
| ✅ | evidence_coverage算法未定 | 已按“获得有效证据支持的适用关键项 / 适用关键项”冻结；source diversity 仅作描述 |

---

## Sprint 4 实施进度

### S4-01: 契约 (陈家智) — ✅ FROZEN / MERGED

**8 份文档全部就绪**（`docs/sprint4/`）:
1. `sprint4-scope.md` (277行) — 目标、不做事项、12天排期、风险评估
2. `product-flow.md` (176行) — 完整用户旅程、20题/6题/追问关系
3. `assessment-contract-v2.1.md` (239行) — EvidenceItem/Conflict/MissingInformation/FollowUpQuestion/AssessmentRevision/InputProcessingStatus Schema
4. `questionnaire-contract-v2.1.md` (370行) — 20题6模块详细设计、6种题型、评分规则、V2.0兼容映射、动态追问决策树
5. `provider-contract.md` (350行) — Qwen重试策略(429/5xx/timeout)、10错误码、ai_call_log、PaddleOCR接口、MockProvider、健康检查API
6. `evaluation-plan.md` (360行) — 14指标P0/P1/P2、60案例7类型分布、F1/冲突/追问人工评审标准、Day10议程
7. `integration-checklist.md` (156行) — 6个PR合并顺序、每阶段验收项
8. `contract-review-report.md` — 跨文档一致性审查结果

**契约审查结论**: S4-01 Contract 已完成 hardening 并冻结。Q19/Q20 safety、V2.0 q12 迁移、Q04、Evidence value、coverage、Provider 同步/异步与日志隐私规则均已统一；无剩余 Contract blocker。

### S4-01: GitHub Issues — ✅ 完成

| # | 负责人 | 状态 |
|---|---|---|
| #52 | 陈家智 — Sprint 范围与契约 | ✅ CLOSED |
| #53 | 肖宇翔 — 问卷V2.1与评估集 | READY |
| #54 | 蔡子鑫 — 真实OCR与后端基础 | READY |
| #55 | 钟睿宸 — Assessment与Diagnosis增强 | READY |
| #56 | 彭翔 — uni-app真实产品流程 | READY |

### Contract Tests — ✅ 完成

`tests/contract/` 使用 canonical fixtures 验证 questionnaire、assessment/evidence 与 provider 契约，共 **30 passed, 0 skipped, 0 failed**。


- 全量测试: **422 passed, 0 failed**

### 仓库清理 — ✅ 完成
- 删除 18 个旧远程分支 (Sprint 1-3 的 feat/integration/fix 分支)
- 关闭 3 个 Sprint 3 遗留 Issue (#31, #40, #41)
- 远程分支仅保留: main / dev / integration/sprint4-real-input
- 本地旧分支 + uploads/ 残留已删除

### 记忆系统迁移 — ✅ 完成
- 旧记忆碎片(11个.md文件)从 Claude 长时记忆删除
- 统一迁移到 `project-memory/` 目录:
  - `harmonyai.md` (本文件) — 项目全貌
  - `travelshare.md` — TravelShare 项目
  - `README.md` — 映射表(用户说项目名→找文件)

---

## 当前仓库状态 (2026-08-10)

| 项目 | 值 |
|---|---|
| dev S4-01 Freeze HEAD | `c456f2b662733e9694f749369e7c0e998f515b7f` |
| integration/sprint4-real-input HEAD | `c456f2b662733e9694f749369e7c0e998f515b7f` |
| dev领先main | 220 commits |
| 远程分支 | main / dev / integration/sprint4-real-input |
| 测试 | 422 passed, 0 failed；Contract 30 passed |
| Sprint 3 Issues | #43-#51 全部合并, #31/#40/#41 已关闭 |
| Sprint 4 Issues | #52(CLOSED) / #53(READY) / #54(READY) / #55(READY) / #56(READY) |

### 当前阻塞项
| # | 阻塞项 | 负责人 | 影响 |
|---|---|---|---|
| — | 无 | — | Q04 已冻结，不再存在 blocker |


---

## 关键设计原则

1. **Knowledge First** — 所有 AI 推理基于 Knowledge Engine
2. **Explainability** — 所有输出可解释，附带推荐理由与文献出处
3. **Human in the Loop** — 医疗建议允许人工确认
4. **Modular Design** — 所有 Agent 可独立替换
5. **Fail Gracefully** — 任何模型失败系统仍可运行

### 命名红线
- 全文禁用"治疗""诊断""确诊""患有"
- 统一用"辅助评估""倾向""音乐调节建议"
- 所有输出带 disclaimer: "不构成医学诊断或治疗建议"

---

## 团队分工

| 成员 | 角色 | Sprint 4 核心职责 |
|---|---|---|
| 陈家智 | Project Leader & AI Architect | 契约、集成、验收 |
| 肖宇翔 | Medical Knowledge Engineer | 问卷 V2.1、评估集、医学审核 |
| 钟睿宸 | AI Engineering Lead | Qwen Provider、文本提取、多源融合 |
| 蔡子鑫 | Backend Platform Engineer | OCR、数据库、API |
| 彭翔 | Client Engineer | uni-app 完整产品流程 |

---

## 常用命令

```bash
# 后端
cd C:\Users\ASUS\HarmonyAI
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 测试 (全部)
python -m pytest tests/ -q    # 422 tests

# Contract tests only
python -m pytest tests/contract/ -v   # 30 tests

# 前端 (uni-app H5)
cd frontend && npm run dev:h5   # http://localhost:5173

# Demo 页面（独立 HTML，浏览器直接打开）
frontend/full-demo.html          # V2 优先，失败自动降级 V1
frontend/full-demo.html?mode=v1  # 强制 V1 备用
frontend/full-demo.html?mode=v2  # 强制 V2
```

---

## 历史细节

### Sprint 1→2 关键事件
- 07-17: 陈家智代建知识库（nob 请假），三个映射 JSON + 12 篇文献在线核验
- 07-18: 钟睿宸/蔡子鑫零提交零 PR，Git 教学文档紧急输出
- 07-19: 全量替换 nob→肖宇翔（dev 12 文件 34 处 + feat/nob 9 文件）
- 07-20~21: 四人全部提交 Sprint 1 PR (#21~#24)
- 07-22: PR Review 发现三个冲突（ai_engine 重复代码/superpowers 目录/旧 zip PR）→ 全部解决 → 四 PR 一键合入
- 07-23: Day 4 假数据闭环通过
- 07-24~25: Sprint 2 验收通过（彭翔录屏全链路，音乐响了）

### Sprint 3 关键事件
- 07-27: PR #43 合并 (Codex 的 feat/free-text-assessment)
- 07-28: PR #44 合并 (肖宇翔问卷 V2 + 安全规则)
- 07-30: PR #45 合并 (陈家智 Agent Contract V2)
- 07-31: PR #46 合并 (蔡子鑫 Sprint 3 Backend)
- 08-04: PR #47-#50 同日批量合并 (集成冲刺日)
- 08-05: PR #51 创建 (V2/V1 双模式 Demo + 版本修复)
- 08-05~06: Competition Freeze Review → PR #51 合并 → README/main.py 更新
- 08-06: 仓库清理 (18旧分支+3旧Issue) → Sprint 4 规划最终定稿
- 08-06~08: Sprint 4 契约7文档 + Contract Tests + 审查报告
- 08-10: S4-01 Contract FROZEN，经 Final Gate 后 fast-forward 合并到 dev；Issue #52 CLOSED，#53~#56 READY

### 文献分级体系
- **Level A**: PubMed 逐字核验（4 篇）
- **Level B**: 《素问》ctext 原文核验（5 篇）
- **Level C**: 万方/SinoMed 多源交叉验证（3 篇）
- **Level D**: 待补充（预留）
- **Level E**: 用户反馈数据（规划中）
- 发现：焦虑证据人群分歧（癌症阴性 vs 老年阳性）；王丽娜 2022 被验证否决

### 6 个 ADR
- ADR-0001: FastAPI over Spring Boot
- ADR-0002: LangGraph over CrewAI
- ADR-0003: Five Agents over Single Agent
- ADR-0004: Rule Engine + LLM over Pure LLM
- ADR-0005: Keep Fa/Si in Scale
- ADR-0006: Four-Layer Knowledge Base

### 关键设计决策
- **Walking Skeleton**: 联调不是最后一步而是第一步（Sprint 2 核心策略）
- **Music Agent 用曲库检索代替真实生成**（Sprint 2 决定，Sprint 3/4 延续）
- **单曲不做 7 日序列**（MVP 简化）
- **severity 1-5 + 文字并存**（不只用数字）
- **制度只保留两个**: 每晚 21:00 日报 + 每 3 天演示型 Review
- **Codex 的贡献**: full-demo.html(324行原始版)、demo.html、narrative_text 支持、survey.vue 修改
- **Claude 在此基础上**: V2/V1 双模式(+435行)、版本修复、Sprint 4 契约体系、Contract Tests

---

*由 Claude Code 维护。每次重大进展后更新此文件。*

## Sprint 4 S4-06 集成验收状态（2026-08-11）

- 四条功能线 #53～#56 已会师于 `integration/sprint4-real-input@ecd3596f40cc11205c5af28612e647070d5b0cd2`。
- S4-06 修复集中在 `fix/s4-06-integration`，未直接提交 integration。
- 当前自动化证据：Contract 30/30、Full 511/511、Frontend 37/37、H5 PASS、Evaluation runner tests 14/14。
- Safety 5/5、10 个验收场景 10/10、完整产品链路、SQLite、Provider failure、Privacy、Sprint 3 compatibility 均 PASS。
- Assessment V2.1 API 已接入 async Qwen Provider 环境工厂；Provider input/prompt 已纳入普通日志脱敏。
- Formal Runner 已调用 production workflow；首次真实本地 Qwen 正式结果为 60/60 executed、5 PASS、40 FAIL、15 ERROR；Safety 5/5 PASS，Frozen threshold FAIL。
- MySQL 真实环境验收、OCR 真实脱敏材料 POC、Android 真机验收均 PENDING。
- 当前唯一允许的总状态：`AUTOMATED_ACCEPTANCE_FAILED`。
- 发布阻塞：定位 15 个 `PROVIDER_ERROR` subset、必要时执行唯一一次 Final 60-case并达到 Frozen threshold；MySQL/OCR/Android Gate 尚未完成。
- 详细报告：`docs/sprint4/s4-06-acceptance-report.md`。

### 2026-08-12 可恢复检查点

- PR #65 分支 `fix/s4-06-integration@499a905aca4ead914b3296958a5a9a70b18aed35`：C051/C052/C053 已修复，eval tests 16/16，正式数据 60/60 VALID。
- Ollama 0.32.8 与本地 `qwen2.5:7b-instruct-q4_K_M`（digest `845dbda0ea48`）已就绪；模型健康检查及 sync/async Provider smoke 均 PASS。
- 3-case smoke（C001/C021/S001）已完成：真实 Qwen 调用无 Provider/Schema ERROR，S001 safety PASS；普通案例仅有 model-quality 差异；targeted tests 18/18 PASS。
- Representative mini eval 共 8/8 执行完成，无 Provider/Schema ERROR；S001 safety PASS，普通案例差异为 model-quality。
- 首次 formal 60 已落盘：5 PASS / 40 FAIL / 15 ERROR；真实 Qwen AVAILABLE，safety recall 1.0，schema pass 0.75，threshold FAIL。
- 下一门禁仅诊断 ERROR subset；MySQL=`USER_CREDENTIAL_REQUIRED`，OCR/Android manual gate=PENDING。
