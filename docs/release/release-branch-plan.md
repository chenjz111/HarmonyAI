# 发布分支计划 — Release Branch Plan

> **日期**: 2026-08-05
> **当前状态**: dev @ `714f018`, main @ `30b72cf`
> **目标**: 规划 dev → main 合并与版本发布

---

## 一、当前分支状态

```
main (local)     30b72cf  Initial commit
main (origin)    30b72cf  Initial commit
dev (local)      714f018  Merge PR #50 (Sprint 3 完成)
dev (origin)     714f018  Merge PR #50 (Sprint 3 完成)
```

| 指标 | 值 |
|---|---|
| dev 领先 main | **218 commits** |
| Merge base | `30b72cf` (同一个 commit) |
| 合并方式 | **Fast-forward** (main 是 dev 的祖先) |
| 冲突风险 | **零** |

```
main:    30b72cf ───────────────────────────── (stale)
dev:     30b72cf ── ...218 commits... ── 714f018 (current)

Fast-forward merge:
main:    30b72cf ── ...218 commits... ── 714f018 (updated)
```

---

## 二、发布操作（待人工执行）

### Step 1: 确认 dev clean

```bash
git checkout dev
git status                    # 应只有 untracked 报告文件
python -m pytest tests/ -q    # 392 passed
```

### Step 2: 合并 dev → main

```bash
git checkout main
git merge dev                 # Fast-forward，无冲突
```

### Step 3: 打标签

```bash
git tag -a v0.3.0 -m "HarmonyAI Sprint 3 — Competition Release

多模态输入（病例+自由文本+问卷）
V2 统一工作流（单次调用完成5 Agent）
Feedback 2.0（pre/post 情绪对比）
优雅降级（Qwen→本地规则 / OCR→预确认文本）
安全规则引擎（LLM调用前关键词拦截）
392 测试全部通过"

git tag -a v0.3.0-rc1 -m "Release Candidate 1 — 2026-08-05 验收通过"
```

### Step 4: 推送

```bash
git push origin main
git push origin --tags
```

### Step 5: 切回 dev 继续工作

```bash
git checkout dev
```

---

## 三、远程分支清理建议

当前远程有 **11 个分支**，其中多个已完成合并可以清理：

### 可安全删除（已合并到 dev）

| 分支 | 最终 PR | 状态 |
|---|---|---|
| `origin/feat/caizx` | PR #46 | ✅ 已合并 |
| `origin/feat/zhongrc` | PR #49 | ✅ 已合并 |
| `origin/feat/nob` | PR #44 | ✅ 已合并 |
| `origin/feat/free-text-assessment` | PR #43 | ✅ 已合并 |
| `origin/feat/chenjz` | — | ⚠️ 仅初始提交，无实质内容 |

### 可安全删除（旧版/未合并）

| 分支 | 状态 |
|---|---|
| `origin/feature/sprint1-frontend` | PR #13 CLOSED，Sprint 1 内容 |
| `origin/彭翔-feature/sprint1-frontend` | Sprint 1 前端，已被 PR #24 取代 |
| `origin/greenlasso-patch-1` | 用途不明，无活跃 PR |
| `origin/master` | 冗余（GitHub 默认 main） |

### 保留

| 分支 | 原因 |
|---|---|
| `origin/main` | 发布分支 |
| `origin/dev` | 开发分支 |
| `origin/HEAD` → main | GitHub 默认 |

### 清理命令

```bash
# 比赛后执行
git push origin --delete feat/caizx feat/zhongrc feat/nob \
  feat/free-text-assessment feat/chenjz \
  feature/sprint1-frontend 彭翔-feature/sprint1-frontend \
  greenlasso-patch-1 master
```

---

## 四、版本时间线

```
2025-??-??  v0.1.0  main  初始提交 (30b72cf)
2026-07-22  v0.2.0  dev   Sprint 2 完成 (PR #24, e21333d)
2026-08-04  v0.3.0  dev   Sprint 3 完成 (PR #50, 714f018)
2026-08-05  现在          Release Candidate 验收通过
  ↓ 待执行
2026-08-??  v0.3.0  main  比赛发布 (tag v0.3.0)
```

---

## 五、风险与注意事项

| # | 事项 | 说明 |
|---|---|---|
| 1 | **Fast-forward 安全** | main 没有独立提交，merge 不会产生 merge commit |
| 2 | **不要用 `--no-ff`** | 不需要刻意保留 merge commit，直接用 fast-forward |
| 3 | **不要 rebase** | 不要 `git rebase`，dev 历史应该原样保留 |
| 4 | **比赛后 dev 继续开发** | merge 后切回 dev，main 只用于发布 |
| 5 | **GitHub Releases** | 建议在 GitHub 上基于 `v0.3.0` tag 创建 Release，上传架构图作为附件 |

---

## 六、决策建议

| 操作 | 建议时机 |
|---|---|
| dev → main 合并 | **比赛演示当天或前一天** |
| 打 v0.3.0 tag | 合并后立即 |
| 远程分支清理 | **比赛后**（避免误删正在使用的分支） |
| GitHub Release 创建 | 比赛提交前 |

---

*由 Claude Code 生成，基于 2026-08-05 代码审查。未执行任何 merge 或 push 操作。*
