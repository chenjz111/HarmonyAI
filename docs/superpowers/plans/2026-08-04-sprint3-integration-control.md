# HarmonyAI Sprint 3 Integration Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已完成但分散的 Sprint 3 成果按文档、知识、后端、AI、前端、发布的顺序稳定集成到 dev。

**Architecture:** dev 是唯一集成基线，每一层使用独立分支和普通 Merge Commit。后端、AI、前端和发布由各自子计划约束，任一层失败都停止向下一层传播。

**Tech Stack:** Git、GitHub CLI、Python 3、pytest、FastAPI、LangGraph、Vue 3、uni-app、Node.js。

## Global Constraints

- 所有 PR 的 Base 必须是 dev。
- 只使用普通 Merge Commit；禁止 Squash、Rebase、force push。
- 不删除包含未合并工作的远程分支。
- Sprint 2 旧接口和演示测试必须保持通过。
- OCR、Qwen 失败时必须降级到问卷或规则流程。
- Music P0 只能声明 source_type=matched。
- 不提交环境变量文件、密钥、密码、真实患者资料和 frontend/unpackage/dist。
- 输出只能称为状态评估或辅助辨证倾向，不称为医学诊断。

---

## 文件结构

- 本计划：`docs/superpowers/plans/2026-08-04-sprint3-integration-control.md`
- 后端计划：`docs/superpowers/plans/2026-08-04-sprint3-backend-integration.md`
- AI 计划：`docs/superpowers/plans/2026-08-04-sprint3-ai-integration.md`
- 前端计划：`docs/superpowers/plans/2026-08-04-sprint3-frontend-integration.md`
- 发布计划：`docs/superpowers/plans/2026-08-04-sprint3-release-validation.md`

### Task 1: 合并队长文档 PR #45

**Files:**
- Review: `docs/agent-contract-v2.md`
- Review: `docs/demo-script-sprint3.md`
- Review: `docs/release-checklist.md`
- Review: `docs/sprint3-final-report.md`
- Review: `docs/sprint3-integration-gate-20260731.md`
- Review: `docs/superpowers/specs/2026-08-04-sprint3-stable-integration-design.md`
- Review: `docs/superpowers/plans/*.md`

**Interfaces:**
- Consumes: PR #45，Base=dev。
- Produces: dev 中冻结的 Sprint 3 合同、设计和实施计划。

- [ ] **Step 1: 刷新并检查 PR 元数据**

```powershell
gh pr view 45 --repo chenjz111/HarmonyAI --json baseRefName,headRefName,mergeable,state,files,statusCheckRollup
```

Expected: Base 为 dev、状态 OPEN、mergeable 为 MERGEABLE、Files changed 只有 docs。

- [ ] **Step 2: 检查敏感信息与差异格式**

```powershell
git fetch origin
git diff --check origin/dev...origin/feat/chenjz-sprint3-lead
git diff origin/dev...origin/feat/chenjz-sprint3-lead | rg -n "sk-[A-Za-z0-9._-]{16,}|QWEN_API_KEY|DATABASE_URL=|BEGIN (RSA|OPENSSH) PRIVATE KEY"
```

Expected: diff check 无输出；敏感信息扫描无输出。

- [ ] **Step 3: 使用普通 Merge Commit 合并**

```powershell
gh pr merge 45 --repo chenjz111/HarmonyAI --merge
```

Expected: PR #45 显示 MERGED，并产生 merge commit。

- [ ] **Step 4: 验证 dev 包含文档提交**

```powershell
git fetch origin
git log -3 --oneline origin/dev
gh pr view 45 --repo chenjz111/HarmonyAI --json state,mergedAt,mergeCommit
```

Expected: state=MERGED，dev 最新历史包含 PR #45 的 merge commit。

### Task 2: 合并医学知识 PR #44

**Files:**
- Review: 以 `gh pr view 44 --json files` 返回的 9 个文件为准。
- Test: `tests/` 中 PR #44 修改或依赖的知识库测试。

**Interfaces:**
- Consumes: 已含 PR #45 的最新 dev。
- Produces: 12 题问卷映射、候选证型和安全边界，供 AI 集成使用。

- [ ] **Step 1: 检查 PR 仍以最新 dev 为 Base**

```powershell
gh pr view 44 --repo chenjz111/HarmonyAI --json baseRefName,mergeable,files,statusCheckRollup
```

Expected: Base=dev，无冲突，无无关业务重构。

- [ ] **Step 2: 在隔离 worktree 运行完整测试**

```powershell
git worktree add C:/Users/ASUS/Desktop/HarmonyAI-worktrees/review-pr44 origin/feat/nob
python -m pytest tests -v
```

Expected: 全部通过；已知基线为 50 passed。

- [ ] **Step 3: 检查医学映射边界**

```powershell
rg -n "选A|选B|选C|选D|选E|直接.*调式|医学诊断" docs backend tests
```

Expected: 不存在“单个答案直接决定脏腑或调式”的实现；免责声明保留。

- [ ] **Step 4: 普通 Merge Commit 合并并验证**

```powershell
gh pr merge 44 --repo chenjz111/HarmonyAI --merge
git fetch origin
gh pr view 44 --repo chenjz111/HarmonyAI --json state,mergeCommit
```

Expected: PR #44 MERGED，dev 获得新的 merge commit。

### Task 3: 执行后端修复计划

**Files:**
- Follow: `docs/superpowers/plans/2026-08-04-sprint3-backend-integration.md`

**Interfaces:**
- Consumes: 最新 dev 与 origin/feat/caizx。
- Produces: 合并后的 v2 session、document、feedback 接口和绿色完整测试。

- [ ] **Step 1: 按后端计划创建、测试并提交 fix/sprint3-backend-integration**
- [ ] **Step 2: 创建后端替代 PR，审查 Files changed 和完整 pytest**
- [ ] **Step 3: 普通 Merge Commit 合并替代 PR**
- [ ] **Step 4: 在 PR #46 留下替代 PR 说明后关闭 PR #46，不删除分支**

### Task 4: 执行 AI 集成计划

**Files:**
- Follow: `docs/superpowers/plans/2026-08-04-sprint3-ai-integration.md`

**Interfaces:**
- Consumes: 最新 dev 与 origin/feat/zhongrc。
- Produces: 三源 Assessment、降级、安全规则和五 Agent V2 工作流。

- [ ] **Step 1: 按 AI 计划创建 integration/sprint3-ai-v2**
- [ ] **Step 2: 解决 3 个冲突并运行完整测试**
- [ ] **Step 3: 创建、审查并以普通 Merge Commit 合并 AI PR**

### Task 5: 执行前端迁移计划

**Files:**
- Follow: `docs/superpowers/plans/2026-08-04-sprint3-frontend-integration.md`

**Interfaces:**
- Consumes: 已稳定的 v2 后端和 AI 合同。
- Produces: 八页比赛流程、真实 API 默认模式和明确 Mock 开关。

- [ ] **Step 1: 按前端计划创建 integration/sprint3-frontend-v2**
- [ ] **Step 2: 迁移源文件、对齐接口并运行测试和构建**
- [ ] **Step 3: 创建、审查并以普通 Merge Commit 合并前端 PR**

### Task 6: 执行发布验收计划

**Files:**
- Follow: `docs/superpowers/plans/2026-08-04-sprint3-release-validation.md`

**Interfaces:**
- Consumes: 完成文档、知识、后端、AI 和前端集成的 dev。
- Produces: 三条端到端证据、比赛演示版本和发布结论。

- [ ] **Step 1: 按发布计划建立 release/sprint3-competition**
- [ ] **Step 2: 完成自动化与人工端到端验收**
- [ ] **Step 3: 只修复发布阻断缺陷并复测**
- [ ] **Step 4: 创建发布 PR；审查通过后普通 Merge Commit 合并**

### Task 7: 汇总 GitHub 状态与群通知

**Files:**
- Update: `docs/sprint3-final-report.md`
- Update: `docs/release-checklist.md`

**Interfaces:**
- Consumes: 所有 merge commit、测试输出和 E2E 证据。
- Produces: 可追溯的 Sprint 3 完成报告与成员通知。

- [ ] **Step 1: 导出 PR、Issue 和 Milestone 状态**

```powershell
gh pr list --repo chenjz111/HarmonyAI --state all --limit 30
gh issue list --repo chenjz111/HarmonyAI --milestone "Sprint 3 - Competition Upgrade" --limit 30
```

- [ ] **Step 2: 更新报告中的实际 SHA、测试数和已知限制**

只写已执行命令产生的结果，不沿用旧数字或预计数字。

- [ ] **Step 3: 检查并提交报告**

```powershell
git diff --check
git add docs/sprint3-final-report.md docs/release-checklist.md
git commit -m "docs: record Sprint 3 release evidence"
```

- [ ] **Step 4: 生成需要陈家智转发的群消息**

消息必须包括：已合并 PR、成员成果是否保留、需要成员确认的具体事项、当前测试结果和下一次截止时间；没有需要确认的事项时明确写“当前无需成员补交代码”。
