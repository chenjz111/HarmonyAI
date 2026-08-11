# AI 工具交接文档

> **读者：下一个接手的 AI 工具（Codex / Claude / 其他）**
> **读完这个文件即可对齐全部上下文，无需人工解释。**
> 最后更新: 2026-08-09

---

## 1. 项目位置

```
旧路径（废弃）: C:\Users\ASUS\Desktop\ai-music
新路径（唯一）: C:\Users\ASUS\HarmonyAI
仓库地址:      github.com/chenjz111/HarmonyAI
```

**一切操作都在 `C:\Users\ASUS\HarmonyAI` 下进行。**

---

## 2. 必须读取的文件

按顺序读：

1. **`project-memory/harmonyai.md`** — 项目全貌（架构、版本历史、Sprint 3 完成状态、Sprint 4 全部规划、阻塞项、命名红线）
2. **`project-memory/README.md`** — 项目名 → 文件映射表
3. **`docs/sprint4/`** — Sprint 4 全部契约文档（8 份）

---

## 3. 当前分支状态

```
当前分支: dev
dev S4-01 Freeze HEAD: c456f2b662733e9694f749369e7c0e998f515b7f
远程分支: main / dev / integration/sprint4-real-input
```

`integration/sprint4-real-input@c456f2b` 已通过 fast-forward 合并并推送到 `dev`；Contract 状态为 **FROZEN / MERGED**。

```
c6e9260 feat: Sprint 4 contract tests — questionnaire + evidence schema validation
58f26d7 docs: contract review report + fix follow-up max inconsistency
a09ea76 docs: Sprint 4 remaining contracts — questionnaire V2.1, provider, evaluation plan
61e3d33 docs: Sprint 4 contracts — scope, product flow, assessment V2.1, integration checklist
```

这些 commit 包含 Sprint 4 的全部契约文档和 Contract Tests，现已完整进入 `dev`。

---

## 4. 上一棒做了什么

### Sprint 3 收官（8月4-5日）
- 4 个 PR (#47-#50) 同日合并 — 四线集成会师
- PR #51 创建并合并 — V2/V1 双模式比赛 Demo（`frontend/full-demo.html`，759行）
- 版本号统一为 0.3.0
- 全量测试 392 全部通过

### Sprint 4 启动（8月6-8日）
- **8 份契约文档**写入 `docs/sprint4/`（在 `integration/sprint4-real-input` 分支上）
- **30 个 Contract Tests** 写入 `tests/contract/`（同上分支）
- **跨文档一致性审查**完成（`docs/sprint4/contract-review-report.md`）
- 全量测试: **422 passed, 0 failed**（其中 30 个 contract tests）
- **仓库清理**: 18 个旧远程分支 + 3 个遗留 Issue 已关闭
- **记忆系统**: 从 Claude 长时记忆迁移到 `project-memory/` 目录

---

## 5. 当前阻塞项

| # | 阻塞项 | 负责人 | 影响 |
|---|---|---|---|
| — | 无 | — | Q04 已冻结，不再存在 blocker |


---

## 6. Sprint 4 PR 顺序

```
S4-01 (陈家智, ✅) → S4-02 (肖宇翔, 问卷+评估) → S4-03 (蔡子鑫, OCR+后端)
  → S4-04 (钟睿宸, AI) → S4-05 (彭翔, 前端) → S4-06 (陈家智, 集成验收)
```

GitHub Issues: #52(CLOSED) / #53(READY) / #54(READY) / #55(READY) / #56(READY)

---

## 7. 常用命令

```bash
# 后端启动
cd C:\Users\ASUS\HarmonyAI
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 全量测试
python -m pytest tests/ -q    # 422 tests

# Contract tests only
python -m pytest tests/contract/ -v   # 30 tests

# 前端 (uni-app H5)
cd frontend && npm run dev:h5

# Demo 页面（浏览器直接打开）
frontend/full-demo.html             # V2 优先
frontend/full-demo.html?mode=v1     # 强制 V1
frontend/full-demo.html?mode=v2     # 强制 V2
```

---

## 8. 关键约束

### 命名红线
- ❌ 禁用: "治疗""诊断""确诊""患有"
- ✅ 使用: "辅助评估""倾向""音乐调节建议"
- 所有输出必须带 disclaimer

### 技术栈
- Agent 编排: LangGraph StateGraph
- LLM: Qwen2.5-7B-Instruct (OpenAI-compatible)
- 向量库: Chroma + BGE-M3
- 后端: FastAPI (Python 3.10+)
- 前端: uni-app (Vue 3)
- 数据库: SQLite (默认) / MySQL 8.0

### 五音映射（规则引擎，不调 LLM）
```
证型 → tone_id    → bpm  → instruments
jiao  (角调)      → 68   → 古筝、古琴
zhi   (徵调)      → 70   → 琵琶、古琴
gong  (宫调)      → 62   → 编钟、古琴
shang (商调)      → 66   → 二胡、洞箫
yu    (羽调)      → 58   → 箫、古琴
```

---

## 9. 团队分工

| 成员 | 角色 | GitHub | Sprint 4 职责 |
|---|---|---|---|
| 陈家智 | Project Leader & AI Architect | chenjz111 | 契约、集成、验收 |
| 肖宇翔 | Medical Knowledge Engineer | — | 问卷 V2.1、评估集 |
| 钟睿宸 | AI Engineering Lead | — | Qwen Provider、多源融合 |
| 蔡子鑫 | Backend Platform Engineer | — | OCR、数据库、API |
| 彭翔 | Client Engineer | — | uni-app 产品流程 |

---

## 10. 给接手的 AI 的第一句话

> 你已经对齐了 HarmonyAI 项目的全部上下文。S4-01 Contract 已 FROZEN / MERGED，Issue #52 已关闭，Contract Tests 30/30、Full Tests 422/422 通过。#53～#56 当前为 READY，但尚未开始实现。

---

*由 Claude Code 于 2026-08-09 创建。每次换工具前更新此文件。*

## 11. Sprint 4 S4-06 当前状态（2026-08-11）

- integration baseline：`ecd3596f40cc11205c5af28612e647070d5b0cd2`，已包含 #53～#56。
- 当前验收修复分支：`fix/s4-06-integration`。
- Contract：30/30 passed；Full：511/511 passed；Frontend：37/37 passed；H5：PASS；Evaluation runner tests：14/14 passed。
- Safety Gate：5/5 PASS；10 个正式验收场景：10/10 PASS；完整产品链路：PASS。
- SQLite、Provider failure、Privacy、Sprint 3 compatibility：PASS。
- S4-06 小型修复：Assessment V2.1 API 接入 async Qwen Provider factory；普通日志新增 provider/prompt 输入脱敏；均有回归测试。
- Formal Runner 已调用 production workflow；首次真实本地 Qwen 正式结果：60/60 executed、5 PASS、40 FAIL、15 ERROR；Safety 5/5 PASS，threshold FAIL。
- 严格状态：`AUTOMATED_ACCEPTANCE_FAILED`。
- 下一步：只定位 15 个 `PROVIDER_ERROR` subset；确认实现/基础设施修复后最多允许一次 Final 60-case。MySQL 等正确凭证；OCR/Android 保持人工 PENDING。
- 详细证据：`docs/sprint4/s4-06-acceptance-report.md`。

禁止在上述阻塞消除前执行 integration → dev、dev → main、tag v0.4.0、Release 或关闭 #53～#56。

### S4-06 可恢复检查点（2026-08-12）

- PR #65 分支 `fix/s4-06-integration@499a905aca4ead914b3296958a5a9a70b18aed35`：C051/C052/C053 已修复，正式数据 60/60 VALID，`tests/evals/` 16/16 PASS。
- Ollama 0.32.8 与 `qwen2.5:7b-instruct-q4_K_M`（digest `845dbda0ea48`）已安装到 `D:\OllamaModels`；本地健康、同步 Provider、异步 Provider smoke 均 PASS。
- 3-case smoke：C001/C021/S001 均无 Provider/Schema ERROR，S001 safety PASS；两条普通案例仅有 model-quality 指标差异。受影响测试 18/18 PASS。
- Representative mini eval：C001/C021/C031/C041/C046/C051/C010/S001 共 8/8 执行完成、无 Provider/Schema ERROR；S001 safety PASS，普通案例差异归类为 model-quality。
- 首次 formal 60-case：60/60 executed，5 PASS / 40 FAIL / 15 ERROR；Qwen AVAILABLE，safety recall 1.0，schema pass 0.75，Frozen threshold FAIL；机器结果已落盘。
- 下一门禁：只诊断 ERROR subset；MySQL=`USER_CREDENTIAL_REQUIRED`；OCR/Android manual gate=PENDING。
