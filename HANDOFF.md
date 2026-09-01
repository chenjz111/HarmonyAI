## CURRENT ACTIVE HANDOFF

STATUS:
READY_FOR_REVIEW

### Repo / worktree
- Repository: C:\Users\ASUS\HarmonyAI
- Active isolated worktree: C:\Users\ASUS\HarmonyAI-questionnaire-v2.2

### Current branch
feat/questionnaire-v2.2-ux-flow

### Base
origin/integration/sprint4-real-input@5b9c4968b0e0e0c69e5778a36ff38a456d4e25cf

### Current checkpoint
5e53156 — fix: complete assessment summary and feedback choices

### Latest verified code checkpoint
5e53156 — fix: complete assessment summary and feedback choices

### Owner Decision
实现 questionnaire_v2.2 + Assessment UX simplification，保持 Five-Agent / Safety architecture 不变。

### Completed
- questionnaire_v2.2 canonical/scoring/contract artifacts；questionnaire_v2.1 保持兼容。
- Q1 结构化主目标 + 可选次目标；Q14 五档电量；Q16 结构化多选 + 自定义身体感受。
- Q19/Q20 Frozen Safety 语义未改，并保留为最后独立安全确认区。
- v2.2 前端 payload 已通过 FastAPI/Pydantic/Assessment route，并进入 frozen real Assessment runner。
- Assessment 结果简化为唯一确认页；needs_verification 嵌入本页；confirmed risk 仍进入 Safety Support。
- 材料页不再向用户显示 OCR 置信度百分比；内部 confidence 仍用于质量与降级判断。
- Feedback 使用必填 2×2 变化卡片，其余字段选填，不制造默认分；只更新个人偏好。
- canonical questionnaire_v2.2 与 contract fixture 已增加严格等值守卫。
- 分支已推送；唯一 PR #73 已创建，base=integration/sprint4-real-input。

### Owner completion audit remediation
- Q1 structured user goal now reaches Prescription as a preference: it may adjust BPM/duration, but never changes the diagnosis-selected tone or creates symptom evidence.
- questionnaire_v2.2 ordinary conflict/follow-up metadata remains recorded but no longer creates a second confirmation gate; questionnaire_v2.1 behavior remains unchanged.
- Final Assessment confirmation uses the approved title and two actions; Qwen-unavailable narrative processing is represented as questionnaire-rule fallback.
- Q19/Q20 UI explicitly states that safety answers do not participate in ordinary state or music scoring.
- Feedback 2×2 labels and free-experience heading match the final Owner audit wording; enum values and persistence pipeline are unchanged.
- Added direct multi-signal regression proving a resolved OCR signal cannot clear confirmed questionnaire risk; Frozen Safety implementation was not modified.
- Final confirmation now shows plain-language recent context and music goals; Feedback choices now cover volume, environment sound and other adjustments without changing API enums or global rules.
### In Progress
- PR #73 等待 Owner review；禁止自动 merge。

### Remaining
- Owner review PR #73。
- Android/manual acceptance 如仍需要，由后续人工门禁执行。

### Important architectural constraints
- Five-Agent architecture unchanged
- questionnaire_v2.1 backward compatible
- Q19/Q20 Frozen Safety semantics unchanged
- generic confirmation cannot clear Safety
- SafetySignal aggregation preserved
- evidence coverage not shown as confidence
- no Formal60
- no emotion_f1 tuning
- no Sprint5
- no real AI music generation

### Tests already passed
- Frontend: 82/82 PASS
- H5: PASS (DONE Build complete)
- Contract: 32/32 PASS
- Owner completion targeted backend: 143/143 PASS
- Final affected backend subset: 42/42 PASS
- Safety / Assessment / Feedback prior baseline: 163/163 PASS
- Earlier backend full baseline on this branch: 710 PASS / 5 known environment-only failures
- PR #73 previous CI at cbeb317: SUCCESS; CI for 5e53156 must be checked after push.

### Tests currently failing
NONE in the final targeted acceptance set.

### Known environment-only failures
- tests/api/test_document_v2.py: 3 failures。当前机器安装 PaddleOCR 后返回 failed，旧断言期望 degraded。
- tests/tools/test_manual_acceptance_tools.py: 2 failures。全量测试 import 顺序导致 tools.s4_mysql_acceptance 不可见。
- 上述 5 项是既有环境问题，不是本分支引入的回归。

### Current blocker
NONE。

### Exact next action
1. 查看 PR #73 最新 CI 与 changed files。
2. Owner 决定是否批准；不要自动 merge。
3. 不开始 Sprint5。

### Files currently relevant
- knowledge/questionnaire-v2.2.json
- knowledge/questionnaire-scoring-v2.2.json
- backend/app/schemas/assessment_v2.py
- backend/ai_engine/questionnaire_v2.py
- backend/ai_engine/assessment_v2.py
- frontend/pages/questionnaire-v2/questionnaire-v2.vue
- frontend/pages/assessment-result/assessment-result.vue
- frontend/pages/material/material.vue
- frontend/pages/feedback-v2/feedback-v2.vue
- tests/contract/test_questionnaire_v22_schema.py

### Do NOT touch
- unrelated stash@{0}
- deprecated C:\Users\ASUS\Desktop\ai-music
- Formal60 evaluator/gold
- unrelated Sprint4 code
- Frozen Safety backend semantics

HANDOFF_READY=YES
---
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
- ERROR subset 诊断：15 条中 13 条复现 `NARRATIVE_SCHEMA_ERROR`（缺少 `time_window`、非法 `polarity`、quote 非原文子串），2 条重跑恢复，属于本地 7B structured-output 非确定性；未消耗 Final 60-case。
- 当前恢复点：PR #65 `e19ccb1`，CI SUCCESS、MERGEABLE；MySQL=`USER_CREDENTIAL_REQUIRED`；OCR/Android manual gate=PENDING。

### S4-06 final recovery checkpoint (2026-08-12)

- PR #65 branch: `fix/s4-06-integration`; latest saved evaluation commit before this status update: `7216a1d`.
- Final real-Qwen 60-case run is complete and saved: 60/60 executed, 15 PASS / 40 FAIL / 5 ERROR; threshold FAIL.
- Final automated regression: Full 535/535, Contract 30/30, Frontend 37/37, H5 PASS.
- Remaining gates: emotion F1 0.6760563380 (<0.80), schema pass 0.9166666667 (<1.00), MySQL `USER_CREDENTIAL_REQUIRED`, OCR manual POC pending, Android manual pending.
- Current status remains `AUTOMATED_ACCEPTANCE_FAILED`; do not run another full 60-case or proceed to release from this checkpoint.

### S4-06 最终权威结论（2026-08-12，Claude 收尾）

- PR HEAD：`fix/s4-06-integration@dd92f09`。
- **emotion_f1 0.7044 → 0.7362**（仍 < 0.80，唯一未达标项）；event_f1 0.7500、physical_f1 0.8000、safety_recall 1.0、schema_pass_rate 1.0、provider_failure_rate 0.0（15 个 PROVIDER_ERROR 归零，ERROR 15→0）。
- 全量回归：Full 540/540、Contract 30/30、Frontend 37/37、H5 build PASS。
- 根因：残余缺口 = H 模型质量（low_mood FN=10 / fear_unease FN=5 / emotional_recovery FN=4 / overthinking FN=4）；已修 E adapter、B normalization、C taxonomy。
- 关键陷阱（务必继承）：Qwen emotion 抽取必须过 keyword-grounding gate（quote 含支撑关键词），词法回退项天然通过。曾有一次误改把 gate 移除导致 FP 14→27、emotion_f1 0.7362→0.6590，已回退。
- 环境/手工 Gate：MySQL=`USER_CREDENTIAL_REQUIRED`；OCR=`MANUAL_OCR_POC_PENDING`；Android=`MANUAL_ANDROID_TEST_PENDING`。
- 总状态：**`AUTOMATED_ACCEPTANCE_FAILED`**。残余 blocker 为模型质量，需更强模型或受控改进；不做大规模 Prompt tuning、不改 expected、不 Mock、不降阈值。
- 权威报告：`docs/sprint4/s4-06-evaluation-report.md`、`docs/sprint4/s4-06-acceptance-report.md`。

### S4-06 夜间收口（2026-08-13，Claude 自主执行，已 commit+push）

- PR HEAD：`fix/s4-06-integration@4c6c5ed`（已 push，与 origin 同步）。CI `test` SUCCESS、PR #65 MERGEABLE/CLEAN。
- 新增 3 commit：`5988b27`（canonical emotion presence semantics）、`4b36f90`（restore questionnaire emotion salience，presence ≠ salience）、`4c6c5ed`（收口记录 + morning report + final JSON）。
- **emotion_f1 0.7362 → 0.7407**（value=0 不对称修复，FN 29→28，TP=60 / FP=14 / FN=28）。仍未达 0.80。其余 P0 全 PASS（event 0.7500 / physical 0.8000 / safety 1.0 / schema 1.0 / provider_failure 0.0）。
- 关键陷阱（务必继承）：**presence ≠ salience**。`_emotion_present`（value≥1=present）只用于 expected 侧与证据 existence；`_actual_emotion_present`（问卷 value≥3）用于 emotion_f1 标签集。把「value≥1=present」套到标签集会把 F1 塌缩到 0.346。
- 结论：value 语义是**红鲱鱼**。真正阻塞 = ① ~15 叙事漏报 FN（成语/英文/隐含表达，需更强 Qwen）② ~8 FN + ~9 FP 问卷-叙事优先级歧义（gold 对问卷情绪的纳入非 value 确定性函数）。
- **需 Owner 拍板两项（阻塞上 0.80）**：D1 问卷情绪在 gold 的纳入规则；D2 是否换更强 Qwen（14B 量化 / 云端 API）。Provider 冻结的是**接口**不是模型，换更强 Qwen 合法；红线 = 禁止 Mock 代 Qwen、禁止 DeepSeek 代 Formal Qwen。
- 全量回归 610/610 passed；Contract 30/30；Frontend 37/37；H5 build PASS。
- 手工 Gate 不变：MySQL=`USER_CREDENTIAL_REQUIRED`；OCR=`MANUAL_OCR_POC_PENDING`；Android=`MANUAL_ANDROID_TEST_PENDING`。
- 权威报告：`docs/sprint4/s4-06-morning-report.md`、`docs/sprint4/s4-06-evaluation-report.md`（含 value=0 addendum）、`docs/sprint4/s4-06-acceptance-report.md`。

### S4-06 Owner acceptance checkpoint（2026-08-13）

- PR #65 branch：`fix/s4-06-integration`；bake-off checkpoint：`815e093`。
- Sprint 4 权威 Formal 60：Qwen2.5-7B Q4，60/60 executed，0 ERROR，`emotion_f1=0.7407`，Frozen target `>=0.80`，状态 `NOT_MET`。
- Owner disposition：`ACCEPTED_KNOWN_MODEL_LIMITATION`。
- **Sprint 4 emotion_f1 optimization is CLOSED.**
- Future model-quality improvement：`DEFERRED_TO_SPRINT_5_OR_LATER`。除非 Owner 明确重新开启，后续 Agent 不得继续把 0.7407 调到 0.80、修改 gold/expected/threshold、继续下载模型或重跑 Formal 60。
- 观察性 15-case：7B F1 0.6552 / 0 errors / 132.40s；14B F1 0.6471（仅 9 个可比较输出）/ 6 errors / 1096.55s。当前硬件保留 7B。
- Engineering Implementation：`COMPLETE`；Automated Engineering Gates：`PASS`；Formal Model Quality：`NOT_MET`。不得写成 `Frozen Evaluation PASS`。
- Manual gates：MySQL=`USER_CREDENTIAL_REQUIRED`；OCR=`MANUAL_OCR_POC_PENDING`；Android=`MANUAL_ANDROID_TEST_PENDING`。
- NEXT_ACTION：完成 PR #65 文档/CI 收口并标记 `ENGINEERING_READY_TO_MERGE`；随后按 `docs/sprint5/` 规划进入下一 Sprint，不在 PR #65 实现 Sprint 5 功能。

### S4-06 merge 与人工验收准备（2026-08-13）

- PR #65 已以普通 Merge Commit 合并到 `integration/sprint4-real-input`；merge commit：`39b0597c8f6c1f0c4993638e6dc00ef9e0feb9f9`。
- 合并后轻量检查：Backend import PASS；Contract 30 tests 可发现；diff hygiene 与冲突标记检查 PASS。
- Owner 最终决定不变：`emotion_f1=0.7407` 为 `ACCEPTED_KNOWN_MODEL_LIMITATION`，优化 `CLOSED`；不得继续 14B、Prompt tuning 或 Formal 60。
- 工程自动化状态：`ENGINEERING_COMPLETE / AUTOMATED_GATES_PASS`；不得写成 Frozen model-quality PASS。
- 人工 Gate：MySQL=`USER_CREDENTIAL_REQUIRED`；OCR=`MANUAL_OCR_POC_PENDING`；Android=`MANUAL_ANDROID_TEST_PENDING`。
- 新准备分支：`fix/s4-06-manual-acceptance-prep`，只包含安全的人工验收工具、清单与结果模板。
- `NEXT_ACTION`：用户先在本机创建/确认隔离库 `harmonyai_s4_acceptance` 并本地设置 `DATABASE_URL`，运行 `python -m tools.s4_mysql_acceptance`；随后准备脱敏 OCR 材料与 HBuilderX Android 真机。
- 禁止：在聊天/Git 中提供数据库密码、固定提交 LAN IP、伪造 OCR/Android PASS、进入 Sprint 5 实现。

### S4-06 MySQL 人工验收完成（2026-08-13）

- 在 `docs/s4-06-mysql-manual-pass` 分支完成 MySQL 人工验收，状态由 `USER_CREDENTIAL_REQUIRED` → **`PASS`**。
- MySQL 8.0.44；隔离库 `harmonyai_s4_acceptance`（utf8mb4）。
- 探针 `python -m tools.s4_mysql_acceptance` 输出 `pass=true`：connection / migration（首次+幂等）/ reconnect persistence / Session·Revision·Evidence·FollowUp·Feedback·AICallLog 持久化 / AI log privacy / cleanup safety 全部通过。
- 真实 API→MySQL 链路：创建评估(200) → 确认 partially_accurate(200) → revision 1→2、`confirmation_level` 落库 → 验收行已清理（0 残留）。
- OCR=`MANUAL_OCR_POC_PENDING`；Android=`MANUAL_ANDROID_TEST_PENDING`（HBuilderX 已在本机安装，待真机）。
- 未记录用户名/密码/DATABASE_URL/敏感路径；未改 production code；未重跑 emotion_f1/Formal 60；未进入 Sprint 5。

### Sprint 4 双轨 Safety 状态机修正（2026-08-15）

- 工作分支：`fix/s4-safety-state-machine`；基线：`integration/sprint4-real-input@eab241f5df6befbd88d0908e1900f359a5cee195`。
- 五 Agent 架构未变；Safety 仍为 Assessment 内部确定性模块。
- 新状态分离：`assessment_status` / `confirmation_status` / `safety_status`。OCR 风险默认 `needs_verification`；Q19/Q20 当前风险保持 confirmed safety。
- 新增专用 Safety Verification revision/API；普通评估确认不能清除 Safety；Safety 分支保留问卷 Evidence 与 coverage。
- 新增 Safety Verification 与 Safety Support 前端页面。心理风险支持用户主动获取人工审核、非个性化、非处方、非自动播放的安抚音频；急性身体风险不提供该入口。
- Safety clear/resolved 时，低 evidence 或 Diagnosis abstain 改为 `emotion_based` / `wellness` 保守降级，不再形成普通用户死路。
- 验证：Safety/Prescription/HTTP 针对性回归 186 passed；新增端到端 5/5；Contract 30/30；Frontend 66/66；H5 PASS。
- 当前机器一次 Full：684 passed / 5 failed。5 个失败均为既有环境/顺序问题：已安装 PaddleOCR 使 3 个旧“引擎不可用”测试返回真实 `failed`，其余 2 个由 Paddle 导入的顶层 `tools` 包污染导致本地 `tools.s4_mysql_acceptance` 顺序性导入失败；本次 Safety 受影响测试全部通过。
- Formal60：未运行；MySQL：PASS；OCR POC：`MANUAL_OCR_POC_PENDING`；Android：`MANUAL_ANDROID_TEST_PENDING`。
- ADR：`docs/adr/ADR-0008-dual-track-safety-service-model.md`。
- NEXT_ACTION：Review 本分支 PR 与 CI；不要合并前开始 Sprint 5；不要重跑 emotion_f1/Formal60。

### Sprint 5 V3 Contract Freeze checkpoint（2026-08-24）

- 权威业务基线：`origin/integration/sprint4-real-input@08ac591c58edb611c784f673edf61b134b9aedbb`。
- Contract PR：#75，分支 `docs/sprint5-v3-contract-draft3`，包含计划检查点 `ad01157b9ccaff4b56306cee1d8110995debb176`；该检查点 CI PASS、PR MERGEABLE。
- Owner 已确认双门禁；三份 V3 合同在 PR #75 分支标记为 `FROZEN`（该历史检查点当时尚未合并到 integration，后续已完成合并）。
- 已完成 Owner-authorized AI / Backend proxy review closure；不得将其表述为钟睿宸或蔡子鑫本人签字。
- 医学内容门禁保持独立：肖宇翔仍须批准最终10题、Claim、Organ、Five-Tone 与 Knowledge Manifest；获批前不得启用 production 医学链路。
- Sprint 5 可执行计划：`docs/superpowers/plans/2026-08-24-harmonyai-v3-sprint5.md`。
- GitHub：Milestone `Sprint 5 - HarmonyAI V3`；#76 负责 PR #75 Final Gate，#77 继续医学内容；#78～#80 在 PR #75 合并后仅解锁不依赖医学内容的 foundation，#81 继续等待各线集成。
- `NEXT_ACTION`：完成 PR #75 Final Gate 并按 Owner 决定合并；随后先实现 executable Schema、Auth/Migration 与 Provider foundation。医学 Assessment/Diagnosis/Prescription 仍等待 #77 approved manifests。

### Sprint 5 V3 executable foundation checkpoint（2026-08-24）

- 权威集成基线：origin/integration/sprint4-real-input@cafca2ac2592fe699e71a215246f5602eb8b863b。
- PR #75 已以普通 Merge Commit 71103c0aeaf19dcbf3193eab53cad3ab5cf6cdcf 合并，V3 结构合同已冻结；不得自行改变 Owner 流程或五 Agent 边界。
- PR #82 已以普通 Merge Commit 3e0d5c4255f0ab61d75d6604f1dabad7b4506196 合并：V3 executable schemas、跨 Agent 合同验证、Diagnosis safety gate；Contract 64/64 PASS（含后续基础测试时复核）。
- PR #83 已以普通 Merge Commit cafca2ac2592fe699e71a215246f5602eb8b863b 合并：guest auth、AuthPrincipal ownership、V3 session bootstrap、统一 API envelope、per-user idempotency、SQLite/MySQL versioned migration foundation。
- PR #83 本地门禁：V3/针对性V2回归 21/21 PASS、Contract 64/64 PASS、compileall PASS、GitHub CI SUCCESS。全 API 的 3 个 OCR 失败可在未含本分支的 integration 基线复现，源于已安装 PaddleOCR 对合成无效图片返回 failed，不属于 PR #83 回归。
- Issues #77～#81 均保持 OPEN。#77 医学内容仍为 production blocker；10题正文、Claim Dictionary、Organ/Five-Tone Mapping 和 Knowledge Manifest 未经肖宇翔批准前不得启用医学链路。
- NEXT_ACTION：继续不依赖医学内容的 Provider foundation 与 Owner 验收准备；#81 最终集成必须等待 #77～#80 的可合并成果，不得提前宣布完成。
### Sprint 5 Provider foundation 与 Owner 验收准备（2026-08-24）

- 当前权威 integration：`cef9d2660beb1f9ab6a6f677718d4854aa548288`。
- PR #85（Understanding Provider Foundation）已合并：typed sync/async、Qwen adapter、Cloud→Local→Rule、单次Schema repair、Claim/version/value/span/time-window gate、safe health/log；CI SUCCESS。
- PR #86（Music Provider Foundation）已合并：typed sync/async、capability gate、Provider task终态/取消权威、私有任务到公共MusicTask脱敏映射、明确reviewed local fallback；CI SUCCESS。
- 定向证据：Understanding Provider `17/17`，其兼容集合 `59/59`；Music Provider `14/14`，其V3/Sprint4兼容集合 `61/61`。
- 新增计划内Owner文件：`docs/sprint5/sprint5-acceptance-report.md`、`docs/sprint5/sprint5-manual-gates.md`。当前只允许 `PREPARATION_IN_PROGRESS`，不是最终验收。
- #77 医学production content仍BLOCKED；#78～#80和#81保持OPEN。Agent1/2/3生产实现、真实Music Provider、Feedback闭环、V3前端和Five-Agent E2E均未完成。
- NEXT_ACTION：先让肖宇翔完成#77审核资产；可并行继续不依赖医学内容的Generation persistence/API与Feedback persistence基础。全部功能线会师前不运行Sprint5 final full gate，不合并integration→dev。

### PR #91 final review checkpoint（2026-09-01）

- Agent2 capability: `BLOCKED_BY_MEDICAL_ASSET`。
- Implemented: owner/session/confirmed-assessment gate, deterministic ElementProfile derivation, insufficient-evidence abstention, `MEDICAL_ASSET_UNAVAILABLE` gate。
- Not implemented: production Query Builder, approved RAG Retriever, Qwen diagnosis Provider, syndrome whitelist validation。
- Reason: repository中没有已批准的 RAG ingestion manifest 或 syndrome whitelist；本 PR 不伪造医学资产或 Provider 执行结果。
- PR #91 同时补齐 Agent1/Agent2 V3 幂等重放与冲突保护，以及 Diagnosis 的 Assessment、Revision、Session 归属校验。

### PR #91 final review follow-up（2026-09-02）

- 当前范围明确为：**基础能力完成，真实 Provider 集成待后续任务**。
- Agent2 仅定位为基础框架/降级实现（`BLOCKED_BY_MEDICAL_ASSET`），不应描述为 Agent2 已完整完成或 `REAL_RAG_QWEN`。
- 真实 RAG + Qwen 仍待后续医学资产任务：已批准的 RAG ingestion manifest、Retriever 索引/版本配置、syndrome whitelist/规则资产，以及对应 Qwen Provider 凭据、模型/超时配置。当前没有启用条件，因此保持诚实降级，不伪造医学命中或证型。
- Assessment/Diagnosis 幂等占位已前移到业务写入之前；唯一约束竞争时回滚并回查胜者结果。相同 key + 相同 payload 返回首次结果（HTTP 200 replay），不同 payload 返回 `IDEMPOTENCY_KEY_REUSED`，不会因唯一约束泄漏 500 或新增业务记录。
- 源码已检索并清理 PR #91 未合并类状态表述；PR #91 当前 HEAD 为 `0aa5e0e57fdcffe3da0a66844c3c402a5d435785`，目标为 `integration/sprint4-real-input`。
