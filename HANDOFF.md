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
