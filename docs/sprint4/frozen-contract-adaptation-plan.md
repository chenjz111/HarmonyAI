# Sprint 4 Frozen Contract Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 将既有 Sprint 4 AI Understanding 适配到冻结契约，并交付可 Review 的阶段性 PR。

**Architecture:** 保留现有 V2.0/V2.1 入口，在 Provider、Evidence、Assessment、Questionnaire、Diagnosis 边界增加契约适配与校验。所有模型输出先经确定性 Schema/安全/证据门禁，再交给下游。

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, Pydantic, urllib/async transport, FastAPI 现有后端。

## Global Constraints

- 不修改 Frozen Contract 文档、夹具或契约测试。
- `complete_json()` 与 `acomplete_json()` 必须共享行为规则。
- Follow-Up 最大 4；questionnaire-only 不因单一来源自动判定不足。
- Q16/Q19/Q20 按最新安全语义执行。
- 普通日志不得包含用户原文、Prompt、OCR 文本或其截断/摘要。
- 不纳入 `.pnpm-store/`、`.test-final-merge/`、`guangzhou_news_2026-07-16/`。

### Task 1: 建立同步后的依赖与测试基线

**Files:**
- Modify: `requirements.txt` only if the existing project dependency declaration is incomplete
- Test: `tests/contract/` and the full `tests/` tree

- [ ] 安装项目已有依赖，不新增无关运行时依赖。
- [ ] 运行 `pytest -p no:cacheprovider tests/contract -q`，记录 Frozen 基线。
- [ ] 运行完整测试，记录真实失败及缺失依赖。
- [ ] 不修改 Contract 夹具。

### Task 2: Provider 统一同步/异步契约

**Files:**
- Modify: `backend/ai_engine/providers.py`
- Test: `tests/ai_engine/test_sprint4_provider.py`, `tests/contract/test_frozen_contracts.py`

- [ ] 先新增失败测试：同步和异步返回相同 JSON、错误码一致、重试次数一致。
- [ ] 实现 `complete_json()` 与 `acomplete_json()` 的共享解析/校验/重试核心。
- [ ] 实现 `ProviderErrorCode` 映射：配置、连接/读取超时、429、5xx、非 JSON、repair 失败、Schema 违规、空响应。
- [ ] 实现 Markdown 包裹、外围文本和可恢复截断的 JSON repair；修复后执行 Schema validation。
- [ ] 保留 `MockProvider` 和同步适配器，补齐 metadata。

### Task 3: Provider 日志隐私门禁

**Files:**
- Modify: Provider metadata/logging integration files identified by the baseline
- Test: `tests/contract/test_frozen_contracts.py` and a focused provider privacy test

- [ ] 先测试用户原文、Prompt、OCR 文本及截断文本不出现在普通日志。
- [ ] 只记录契约允许的元数据：请求/会话/Agent、来源、长度、模型、版本、延迟、Token、状态、错误码、重试次数。
- [ ] 测试 Secret 和数据库连接信息也不进入日志。

### Task 4: EvidenceItem、coverage 与 source diversity

**Files:**
- Modify: `backend/ai_engine/assessment_v2.py`, `backend/ai_engine/narrative_schema.py`, `backend/ai_engine/questionnaire_v2.py`
- Test: `tests/ai_engine/test_assessment_v21.py`, `tests/ai_engine/test_narrative_schema.py`, `tests/ai_engine/test_questionnaire_v21.py`

- [ ] 先测试四类 Frozen `value` 及 category/value 组合校验。
- [ ] 统一输出 `evidence_id/category/label/display_name/value/polarity/severity/time_window/source_type/source_ref/quote/confirmed`。
- [ ] 将 coverage 改为适用关键信息覆盖率，单独返回 `source_diversity`。
- [ ] 测试完整 questionnaire-only 可达到 1.0，单一来源不自动触发不足。

### Task 5: Follow-Up、Safety、Correction 与 Revision

**Files:**
- Modify: `backend/ai_engine/assessment_v2.py`, `backend/ai_engine/real_workflow.py`
- Test: `tests/ai_engine/test_assessment_v21.py`, `tests/integration/test_sprint4_ai_understanding.py`

- [ ] 先测试 Follow-Up 决策树最多生成 4 个问题。
- [ ] 测试 Q16 身体信号只记录证据，Q19/Q20 安全分流和互斥值。
- [ ] 测试安全流程阻止 Diagnosis、Prescription 和 Music。
- [ ] 测试 user correction 追加证据、revision 递增且 revision=1 保留。

### Task 6: Diagnosis abstained

**Files:**
- Modify: `backend/ai_engine/diagnosis_v2.py`
- Test: `tests/ai_engine/test_diagnosis_v21.py`, `tests/integration/test_sprint4_ai_understanding.py`

- [ ] 先测试未确认、安全命中、重大冲突、覆盖不足和无候选证据时 `abstained=true`。
- [ ] 生成 `candidate_tendencies`，每项包含 supporting/contradicting evidence IDs。
- [ ] 保持 V2.0 兼容字段，不让 LLM 创建本地白名单之外的倾向。

### Task 7: 回归、报告与发布

**Files:**
- Modify: `docs/sprint4/s4-04-validation-report.md`
- Test: full test tree and Frozen Contract tests

- [ ] 运行 Contract、专项、集成和全量测试。
- [ ] 运行 `compileall`、JSON 解析和 `git diff --check`。
- [ ] 更新阶段性验证报告，明确 #53/#54 未合并前的联调边界。
- [ ] 只提交 Sprint 4 文件，推送 `feat/s4-ai-understanding`。
- [ ] 创建目标为 `integration/sprint4-real-input` 的正式 Draft PR，通知 Review。
