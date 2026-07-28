# Sprint 3 AI Agent 实施计划

> 适用范围：GitHub Issue #34、#35；前置约束：Issue #30、#32、#33。  
> 开发策略：保留 Sprint 2，增量新增 V2 模块。  
> 本文是编码前计划，不代表下列 V2 模块已经实现。

## Goal

为 HarmonyAI 增加可追溯、可降级、可解释的多源 Assessment V2，并将 Diagnosis、Prescription、Music、Feedback 输出升级为比赛版可联调结构，同时保持 Sprint 2 工作流和 v1 兼容。

## Architecture

新增 V2 输入模型、Questionnaire V2 计分器和 Safety Rules；V2 Assessment 通过适配器调用现有 Qwen Provider 和本地规则。Diagnosis/Prescription/Feedback 复用 Sprint 2 已验证能力，增加证据、推荐原因和个人偏好字段。所有节点通过统一 V2 envelope 与后端/前端交互，旧入口继续使用原有 envelope。

## Tech Stack

- Python 3.10+
- AI Engine 使用 `TypedDict`/协议模式承载 V2 状态；Backend API 使用 Pydantic 对外校验。
- LangGraph
- Qwen-compatible Provider
- Chroma KnowledgeStore
- SQLite 测试存储，MySQL 增量迁移由 Backend 负责
- pytest

## Global Constraints

- 不删除或重写 Sprint 2 `real_agents.py`、`real_workflow.py` 的既有可用路径。
- v1 请求和响应保持兼容；V2 使用独立 Schema 或兼容扩展。
- Qwen 不能覆盖 Questionnaire V2 的确定性计分。
- 未确认 OCR 文本不得作为可靠 Assessment 来源。
- 高风险安全规则不依赖 Qwen。
- 用户端只能使用“状态评估”“辅助辨证倾向”“音乐调养建议”。
- Music P0 只能返回 `generation_mode=matched`，不能描述为实时生成。
- Feedback 只更新个人偏好，不自动修改全局医学规则。
- 普通日志不记录病例原文、自由描述原文、身份信息或 API Key。
- 所有修改必须包含对应测试，并保留 Sprint 2 的 36 项回归测试。

## 文件边界

预计新增或修改：

- Create: `backend/ai_engine/questionnaire_v2.py` — Q1—Q12 校验、计分和维度输出。
- Create: `backend/ai_engine/safety_rules.py` — 多来源风险规则与非敏感 reason code。
- Create: `backend/ai_engine/assessment_v2.py` — 三源融合、来源、证据、冲突和降级。
- Modify: `backend/ai_engine/real_agents.py` — 仅增加 V2 兼容入口或委托，不改变旧调用语义。
- Modify: `backend/ai_engine/real_workflow.py` — 增加可选 V2 workflow 入口，不破坏旧入口。
- Create: `backend/ai_engine/diagnosis_v2.py` — Assessment V2 到辅助辨证倾向的解释适配。
- Create: `backend/ai_engine/prescription_v2.py` — 辅助辨证倾向到音乐参数和推荐原因的适配。
- Create: `backend/ai_engine/music_agent.py` — 本地曲库 matched 输出适配。
- Create: `backend/ai_engine/feedback_v2.py` — 听前/听后 delta 和个人偏好补丁。
- Create: `tests/ai_engine/test_questionnaire_v2.py`。
- Create: `tests/ai_engine/test_safety_rules.py`。
- Create: `tests/ai_engine/test_assessment_v2.py`。
- Create: `tests/ai_engine/test_diagnosis_v2.py`。
- Create: `tests/ai_engine/test_ai_degradation_v2.py`。
- Create: `tests/ai_engine/test_feedback_v2.py`。
- Create: `tests/ai_engine/test_music_agent.py`。

## Task 1: Contract freeze and compatibility map

**Files:** `docs/api-contract-v2.md`、`docs/user-flow-v2.md`、`docs/architecture/sprint3-ai-agent-v2-design.md`。

- [ ] 对齐 `assessment_agent`、`music_agent`、旧 `evaluation_agent`/`generation_agent` 别名。
- [ ] 固定状态枚举：`success`、`degraded`、`needs_confirmation`、`blocked_safety`、`failed`。
- [ ] 固定四种 `analysis_mode` 和 `sources_used` 状态。
- [ ] 固定 Evidence、Conflict、Safety、Degradation 字段。
- [ ] 固定 Music 的 `generation_mode=matched`。
- [ ] 固定 Feedback 的 `personal_preference_patch` 与 `global_rule_update=false`。
- [ ] 向 Backend 和 Frontend 提供 JSON 示例、错误码和字段映射。

验收：前后端不再各自定义同名字段，且 v1 映射表明确。

## Task 2: Questionnaire V2 deterministic scorer

**Files:** `backend/ai_engine/questionnaire_v2.py`、`tests/ai_engine/test_questionnaire_v2.py`。

- [ ] 校验 Q1—Q12 唯一题号、选项值和必填项。
- [ ] 对 Q2—Q11 校验整数 0—4。
- [ ] 将 Q1 保存为 `mood_metaphor`，不计入核心分数。
- [ ] 将 Q2—Q11 计算为原始分和 `raw * 25` 的归一化分。
- [ ] 将 Q12 普通身体选项和高风险选项分开输出。
- [ ] 为每个维度返回题目来源，保证重复输入得到相同 JSON 结果。
- [ ] 写边界测试、缺题测试、非法值测试和重复性测试。

验收：同一问卷不依赖 Qwen 也能稳定得到相同的分数和安全字段。

## Task 3: Deterministic safety rules

**Files:** `backend/ai_engine/safety_rules.py`、`tests/ai_engine/test_safety_rules.py`。

- [ ] 定义自伤、自杀、严重/持续胸痛、明显呼吸困难的规则关键词和 reason code。
- [ ] 统一检查 `narrative_text`、confirmed OCR text 和 Q12 选择。
- [ ] 返回 `level`、`flags`、`reason_codes` 和是否阻断普通处方。
- [ ] 日志接口只接收 reason code，不输出原文。
- [ ] 为每个高风险类别和普通身体不适增加测试。

验收：关闭 Qwen 时高风险路径仍能触发 `blocked_safety`。

## Task 4: Assessment V2 multi-source fusion

**Files:** `backend/ai_engine/assessment_v2.py`、`tests/ai_engine/test_assessment_v2.py`、`tests/ai_engine/test_ai_degradation_v2.py`。

- [ ] 定义 Pydantic/TypedDict 输入：session、user、confirmed document、narrative、questionnaire。
- [ ] 先运行 Questionnaire scorer 和 Safety Rules。
- [ ] 只把已确认 OCR 文本放入可靠 sources；未确认文本放入 missing/warning。
- [ ] 实现四种来源组合，并生成 `analysis_mode`。
- [ ] 调用现有 Qwen Provider 提取状态、诱因、身体信号和证据摘要。
- [ ] 校验 Qwen JSON 必需字段；失败时丢弃模型输出并退回问卷模式。
- [ ] 对来源冲突生成 `conflicts`，不自动选择医学结论。
- [ ] 输出统一 disclaimer、degradation 和 sources_used。
- [ ] 测试四种组合、Qwen 缺失/超时/非法 JSON、冲突和空文本。

验收：病例、文字、问卷都能被追踪；Qwen 失败不返回 500；问卷分数不被模型覆盖。

## Task 5: Diagnosis and Prescription explainability adapter

**Files:** `backend/ai_engine/diagnosis_v2.py`、`backend/ai_engine/prescription_v2.py`、`tests/ai_engine/test_diagnosis_v2.py`。

- [ ] 将 Assessment 的多维画像转换为主倾向、辅助倾向和依据摘要。
- [ ] 复用 Sprint 2 白名单证型和 Chroma evidence，不允许单题直接决定证型。
- [ ] 将来源、冲突、信息完整度和降级状态传递到输出。
- [ ] 输出调式、BPM、乐器、时长、Prompt 和 recommendation reasons。
- [ ] 知识检索失败时使用已审核本地规则，并保留 warning。
- [ ] 低可信或 `blocked_safety` 状态不得返回普通处方。
- [ ] 增加模型非法 JSON、字段缺失、未知证型和低可信测试。

验收：结果页需要的依据字段齐全，且不会把低可信结果包装成确定结论。

## Task 6: Music Agent and Feedback V2 adapters

**Files:** `backend/ai_engine/music_agent.py`、`backend/ai_engine/feedback_v2.py`、对应测试。

- [ ] 将现有本地曲库结果封装为 `track_id`、title、audio_url、duration、source。
- [ ] 固定返回 `generation_mode=matched`，音频不存在时返回可处理错误和备用曲目。
- [ ] 生成音乐参数和匹配解释，保留处方来源。
- [ ] 定义听前/听后字段和 delta 计算。
- [ ] 生成 `personal_preference_patch`，包括收藏、不喜欢特征和继续使用意愿。
- [ ] 固定 `global_rule_update=false`。
- [ ] 删除或绕开真实工作流自动写入默认 4 星的产品路径，但保留旧单测兼容入口。
- [ ] 测试保存失败、空文字、异常评分、重复提交和个人偏好更新。

验收：用户主动提交后才保存反馈，且反馈不会改变全局医学规则。

## Task 7: V2 workflow adapter and integration contract

**Files:** `backend/ai_engine/real_workflow.py`、`tests/ai_engine/test_real_workflow_v2.py`。

- [ ] 在现有 LangGraph 旁增加 V2 workflow 构建入口。
- [ ] 编排 Assessment → confirmation/safety gate → Diagnosis → Prescription → Music → Feedback。
- [ ] `blocked_safety` 直接结束普通处方路径并返回安全结果。
- [ ] 未确认评估不得进入普通处方。
- [ ] 保留旧 `run_real_workflow()` 的调用方式和测试。
- [ ] 输出 session_id、各 Agent 状态、degradations 和结果 ID。
- [ ] 使用固定 mock provider 和固定本地曲目完成离线集成测试。

验收：V2 四种输入组合均可运行；安全和降级路径机器可读；旧工作流不回归。

## Task 8: Handoff package and review gate

**Files:** `docs/sprint3-ai-agent-v2-design.md`、`docs/sprint3-ai-agent-plan.md`、测试报告或 PR 描述。

- [ ] 输出给 Backend：V2 Schema、错误码、session 关联字段和 mock 请求响应。
- [ ] 输出给 Frontend：来源标签、状态枚举、降级文案、辅助辨证字段和 Music matched 字段。
- [ ] 输出给 Knowledge：问卷维度、安全 reason code、医学文案审核点。
- [ ] 运行 Sprint 2 全量测试和 V2 测试，记录命令与结果。
- [ ] 进行敏感信息扫描和 `git diff --check`。
- [ ] 仅在所有依赖文档冻结后进入编码；每个实现 PR 单独测试和评审。

## Weekly schedule

### 7 月 28 日：契约冻结

- 完成设计说明、输入输出字段、状态枚举、错误码和兼容映射。
- 与问卷、安全规则、Backend、Frontend 负责人完成字段确认。
- 产出固定 JSON 示例和四种输入组合表。

### 7 月 29 日：AI 基础能力准备

- 完成 Questionnaire V2 和 Safety Rules 的代码前接口设计与测试用例清单。
- 完成 Assessment V2 的融合策略、Qwen prompt 输入输出约束和降级矩阵。
- 完成 Diagnosis/Prescription 的解释字段和 Music/Feedback 的接口对齐。

### 7 月 30 日：联调准备

- 完成 V2 workflow 状态图、Mock Provider、固定曲目和三条 E2E 测试数据。
- 与前后端对齐错误码、来源标签和用户可见状态。
- 冻结 P0 范围，剩余内容只能作为 P1。

### 7 月 31 日：编码前签收和实施门禁

- 检查设计、Schema、测试清单和依赖均已确认。
- 记录 Sprint 2 回归基线和 V2 验收标准。
- 形成 PR 拆分顺序：契约 → 问卷/安全 → Assessment → Diagnosis/Prescription → Music/Feedback → E2E。
- 通过门禁后才开始编码和真实联调。

## Definition of Ready

只有以下条件全部满足，AI Agent 工作才进入编码：

- [ ] #30 的 V2 Agent Contract 已确认。
- [ ] Questionnaire V2 的 12 题、维度和计分规则已确认。
- [ ] 安全规则和用户文案已由知识负责人审核。
- [ ] Backend 明确 confirmed OCR 文本和 session 字段。
- [ ] Frontend 明确来源标签、状态和展示字段。
- [ ] 四种输入组合和三条 E2E 场景已有固定测试数据。
- [ ] Sprint 2 的 36 项测试可在当前环境运行。
- [ ] 没有把 v2 拆成会覆盖旧功能的破坏性重写。

## Definition of Done

- [ ] 四种输入组合全部通过。
- [ ] Qwen/OCR 失败和非法输出全部有降级或安全阻断。
- [ ] 结果包含来源、证据、冲突、缺失和非诊断声明。
- [ ] Diagnosis/Prescription 低可信度不继续普通处方。
- [ ] Music 输出明确为本地 `matched`。
- [ ] Feedback 只更新个人偏好，默认评分不自动写入。
- [ ] Sprint 2 全量测试和 V2 测试通过。
- [ ] 前后端可按冻结 Schema 联调。
