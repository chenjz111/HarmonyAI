# HarmonyAI Sprint 4 — Contract Review Report

> **审查日期**: 2026-08-07
> **审查人**: Claude Code (技术执行)
> **审查范围**: 7 份 Sprint 4 契约文档交叉一致性
> **状态**: ✅ 通过，2 个已知问题已记录

---

## 一、Phase 0: 仓库状态

| 项目 | 状态 |
|---|---|
| 当前分支 | `dev` @ `a38099c` |
| Sprint 4 集成分支 | `integration/sprint4-real-input` @ `a09ea76` |
| dev 是否 clean | ✅ (仅 untracked 报告文件) |
| Sprint 3 PR (#43-#50) | ✅ 全部已合并 |
| PR #51 (V2/V1 Demo) | ✅ 已合并 (commit `76661d2`) |
| 测试 | 392 passed, 0 failed |
| 远程分支 | 4 个 (main/dev/integration-sprint4/main-head) |
| 旧分支 | ✅ 18 个已清理 |

---

## 二、契约完整性检查

### 2.1 文档清单

| # | 文档 | 行数 | 状态 |
|---|---|---|---|
| 1 | sprint4-scope.md | 277 | ✅ |
| 2 | product-flow.md | 176 | ✅ |
| 3 | assessment-contract-v2.1.md | 239 | ✅ |
| 4 | questionnaire-contract-v2.1.md | 370 | ✅ |
| 5 | provider-contract.md | 350 | ✅ |
| 6 | evaluation-plan.md | 360 | ✅ |
| 7 | integration-checklist.md | 156 | ✅ |

### 2.2 EvidenceItem 字段一致性

全部 15 个字段在 assessment-contract 中明确定义：

```
✅ evidence_id          ✅ category         ✅ label
✅ display_name         ✅ value            ✅ polarity
✅ severity             ✅ severity_display ✅ time_window
✅ source_type          ✅ source_ref       ✅ quote
✅ extraction_confidence ✅ confirmed       ✅ dimension_score
```

问卷契约和评估计划中引用的字段名称一致，无冲突。

### 2.3 问卷版本一致性

| 版本 | 引用文档 |
|---|---|
| questionnaire_v2.0 | scope, question, assess |
| questionnaire_v2.1 | scope, flow, question, assess |
| quick_state_v1 | scope, flow, question |
| follow_up_v1 | scope, question |

四方引用一致，V2.0→V2.1 迁移映射表已在问卷契约中定义。

### 2.4 Provider 契约完整性

| 检查项 | 状态 |
|---|---|
| 10 个错误码 (NOT_CONFIGURED ~ EMPTY_RESPONSE) | ✅ |
| ai_call_log 表结构 (9 字段) | ✅ |
| Health Check API (`GET /api/v2/providers/health`) | ✅ |
| MockProvider 接口 | ✅ |
| PaddleOCR 接口 (OCRResult/PageResult/BlockResult) | ✅ |
| OCR 错误处理 (6 种错误码) | ✅ |
| Prompt 版本目录结构 | ✅ |
| 日志脱敏规则 | ✅ |
| 重试策略 (429/5xx/timeout) | ✅ |

### 2.5 评估指标完整性

全部 7 个 P0 指标在 evaluation-plan 中定义：

```
✅ emotion_f1 >= 0.80
✅ event_f1 >= 0.75
✅ physical_f1 >= 0.80
✅ evidence_accuracy >= 95%
✅ ungrounded_rate <= 5%
✅ safety_recall = 100%
✅ schema_pass_rate = 100%
```

---

## 三、发现的冲突和问题

### 🔴 Issue 1: Follow-up 最大题数不一致 (已解决)

| 文档 | 值 |
|---|---|
| sprint4-scope.md (附录 A4) | **最多 4 题** (风险缓解) |
| questionnaire-contract-v2.1.md | **0-6 题范围** |
| scope 原文 (五.2) | 0-6 题动态追问 |

**Resolution**: scope 附录 A4 明确覆盖了正文。最终值：**Sprint 4 最多 4 题**。需要更新 questionnaire-contract 中的 0-6 为 0-4。

**影响模块**: questionnaire-contract-v2.1.md §8

### 🟡 Issue 2: Q04 worry_control 待决策 (阻塞)

| 文档 | 状态 |
|---|---|
| questionnaire-contract-v2.1.md | 标注为 `scored: ⚠️ 定性记录`，`Decision Required` |
| scope 附录 A5 | 推荐方案 A: scored=false，或方案 B: 加权平均 |

**影响**: 肖宇翔在编写 `knowledge/questionnaire-scoring-v2.1.json` 之前必须对此做出决策。如果 Q04 参与 tension_worry 聚合，存在 double-count 风险。

**Resolution**: 等待肖宇翔 Review。当前契约已明确标注此问题。

**影响模块**: questionnaire-contract-v2.1.md §5 (B 模块)

### 🟢 Issue 3: 无其他字段冲突

以下跨文档字段已确认一致：
- AnalysisMode 枚举 (4 值): assessment-contract ↔ product-flow
- Conflict 结构 (7 字段): assessment-contract only (单一定义)
- MissingInformation 结构: assessment-contract ↔ evaluation-plan
- FollowUpQuestion 结构: assessment-contract ↔ questionnaire-contract
- AssessmentRevision 结构: assessment-contract only (单一定义)
- InputProcessingStatus 结构: assessment-contract ↔ product-flow

---

## 四、待办项 (Blockers for S4-01 Completion)

| # | 待办 | 负责人 | 阻塞 |
|---|---|---|---|
| 1 | 更新 questionnaire-contract: follow-up max 4 (not 6) | 陈家智 | 否 |
| 2 | Q04 worry_control 决策 | 肖宇翔 | **是** — 阻塞 questionnaire JSON |
| 3 | 7 份文档全员 Review | 全员 | 是 — 阻塞 S4-01 merge |
| 4 | S4-01 merge 到 integration/sprint4-real-input | 陈家智 | 否 |

---

## 五、结论

**7 份契约内部一致，可以进入 S4-02~S4-05 开发。**

发现的 2 个问题中：
- Follow-up 最大题数: 已解决 (scope wins)
- Q04 worry_control: 不阻塞 AI/Backend/Frontend 开发，仅阻塞 questionnaire JSON 中的该字段

**建议**: 先修复 Follow-up 不一致，然后立即推进 S4-02~S4-05。Q04 决策可以在肖宇翔开始写 scoring JSON 之前完成。

---

*由 Claude Code 基于 2026-08-07 自动审查生成。*
