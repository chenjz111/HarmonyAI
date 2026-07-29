# Sprint 3 V2 新契约兼容迁移设计

## 1. 背景与目标

组长在远程提交 `0d24fff`、`5d0f2cc` 中统一了 Sprint 3 契约。当前本地 Sprint 3 实现完成了确定性问卷、安全门禁、多源融合、辅助辨证、处方、本地曲库匹配、显式反馈和 V2 workflow，但字段仍基于较早版本。

本次迁移目标是：

- 以远程 `docs/api-contract-v2.md` 和 `docs/sprint3-team-tasks.md` 为 V2 唯一标准；
- 保留 Sprint 2 的 `run_real_workflow()`、默认反馈和既有测试行为；
- 将尚未合入团队分支的 V2 实现直接迁移到新字段，不长期保留两套 V2 输出；
- 给 Backend 和 Frontend 提供可校验、可联调的共享 Schema；
- 保持离线演示、确定性安全规则和 Qwen 降级能力。

## 2. 分支同步策略

先把最新 `origin/feat/zhongrc` 合入 `codex/sprint3-ai-v2`，不 rebase、不改写现有 Sprint 3 提交历史。

合并时遵守以下边界：

- 保留远程新增的 `backend/app`、API 文档和团队计划；
- 保留本分支新增的 V2 AI 模块和测试；
- 若契约文档冲突，以远程 `origin/docs/sprint3-planning` 的新字段为准；
- 不修改或删除无关 `.test-*` 目录；
- 不顺带修改 Frontend、上传/OCR Router、数据库迁移等其他负责人模块。

## 3. Canonical V2 输入

Assessment V2 的 AI 层输入固定为：

```text
session_id: str
user_id: str
document_id: str | null
document_text: str | null
narrative_text: str | null
questionnaire_answers: QuestionnaireSubmission
```

约束：

- `document_text` 只能由 Backend 在 OCR 已经由用户确认后传入；
- AI 层不再接收未经确认的 OCR 原文；
- `questionnaire_answers` 必须包含 Q1—Q12，AI 层重新校验和计分；
- 旧 V2 的 `document.confirmed_text` 和 `questionnaire` 不作为正式 V2 输入继续输出到团队；
- Sprint 2 入口继续使用原参数，不受本次迁移影响。

四种 `analysis_mode` 固定为：

- `document_narrative_questionnaire`
- `document_questionnaire`
- `narrative_questionnaire`
- `questionnaire_only`

## 4. Canonical Assessment V2 输出

Assessment V2 输出至少包含：

```text
agent_id
session_id
user_id
status
analysis_mode
sources_used
emotion_profile
physical_profile
life_events
assessment_summary
extracted_evidence
conflicts
missing_information
safety_flags
degradation
warnings
disclaimer
```

字段映射：

- 原 `dimensions` 迁入 `emotion_profile.dimension_scores`；
- `primary_states` 和 `secondary_states` 根据确定性维度分数及固定展示标签生成，Qwen 不得覆盖分数；
- `tcm_emotion_candidates` 只接受通过 Schema 和白名单校验的辅助候选；无可靠候选时返回空数组；
- 原 `context.physical_signals` 迁入 `physical_profile.physical_signals`；
- 睡眠、精力、食欲等身体相关维度同时进入 `physical_profile` 的对应分数字段；
- 原 `context.triggers` 迁入 `life_events.triggers`；
- 原 `state_summary.summary` 迁入 `assessment_summary`；
- 原 `evidence` 改名为 `extracted_evidence`；
- 原 `safety.flags` 改名为 `safety_flags`。

`status` 保留 `success`、`degraded`、`blocked_safety`。安全阻断必须发生在 Diagnosis 之前。

降级对象固定提供：

```text
triggered: bool
reason_code: str | null
fallback: str | null
```

如果内部同时检测到多个原因，使用确定的优先级选取主 `reason_code`，其余原因转为不含原文的 `warnings`，避免向前端暴露两套降级格式。

## 5. Diagnosis、Prescription 与 Workflow

Diagnosis V2 改为读取：

- `emotion_profile.dimension_scores`
- `extracted_evidence`
- `sources_used`
- `conflicts`
- `missing_information`
- `degradation`

它继续输出主倾向、辅助倾向和证据摘要，不把模型自报置信度当作医学可信度。

Prescription V2 继续使用本地白名单、Chroma 证据和审核过的降级规则。低可信、信息不足或 `blocked_safety` 不得产生普通处方。

`run_real_workflow_v2()` 使用新的 Assessment 输入名称和输出结构；返回值继续包含 `session_id`、`result_id`、各 Agent 状态和降级摘要。`assessment_confirmed=false` 和安全阻断仍直接结束。

## 6. Music V2 新契约

Music V2 输出改为扁平结构：

```text
agent_id
legacy_alias
status
music_id
title
source_type
stream_url
mode
bpm
duration_seconds
instruments
ambient_sounds
rights_note
match_explanation
fallback_music_id
```

约束：

- P0 的 `source_type` 只能是 `matched`；
- `matched` 明确表示本地曲库匹配，不描述为实时生成；
- 旧 V2 的 `track_id`、`generation_mode`、嵌套 `track` 不再作为正式 V2 输出；
- Sprint 2 的 generation 结果不做破坏性修改。

## 7. Feedback V2 新契约

Feedback V2 使用 `music_id` 关联曲目，不再以 `track_id` 作为 V2 正式字段。

保持以下规则：

- 只有显式 `feedback_payload` 才能保存；
- Repository 必须提供原子的 `save_once(record, preference_patch) -> bool`；
- 重复提交返回幂等结果；
- 只更新个人偏好；
- `global_rule_update` 永远为 `false`；
- 旧版反馈兼容逻辑留给 V1/API 适配层，不能伪造缺失的听前听后数据。

`SQLiteFeedbackStore` 在提供事务型 `save_once` 适配前，不直接接入 V2 持久化。

## 8. Schema 边界

在最新团队代码结构上新增或扩展：

- `backend/app/schemas/assessment_v2.py`
- `backend/app/schemas/feedback_v2.py`

Schema 负责：

- 校验字段名称、状态枚举、来源枚举和嵌套对象；
- 拒绝未知的模型字段替代正式契约；
- 验证 AI 模块输出可被 Backend 直接序列化；
- 为 Frontend mock 提供稳定 JSON 示例。

Schema 不负责上传、OCR、数据库事务或 HTTP Router。

## 9. 错误与隐私

必须覆盖：

- Qwen 未配置、超时、非法 JSON、字段缺失和未知字段；
- OCR 未提供或失败时由 Backend 省略 `document_text`，AI 流程继续；
- 高风险输入由确定性规则阻断；
- 普通日志只记录 `session_id`、Agent 状态和固定 reason code；
- 日志、异常和 Session 摘要不得包含完整 `document_text` 或 `narrative_text`；
- 前端可见提示使用非诊断表达。

## 10. 测试与验收

所有生产代码变更遵循 RED → GREEN → REFACTOR。

测试分为：

1. Schema 契约测试：新输入输出可通过 Pydantic，旧字段不能替代新字段；
2. Assessment 测试：四种来源组合、冲突、安全阻断、Qwen 降级和确定性分数；
3. AI 异常测试：非法 JSON、超时、字段缺失、未知字段、日志无敏感原文；
4. Music/Feedback 测试：新字段、`source_type=matched`、`music_id` 关联、显式反馈和原子幂等；
5. Workflow 测试：确认门禁、安全门禁、无反馈不访问 Repository、旧 Sprint 2 回归；
6. 稳定性测试：固定输入连续运行 10 次，结构和确定性字段一致；
7. 全量回归：运行整个 pytest suite，随后执行 `git diff --check` 和敏感信息扫描。

## 11. 不在本次范围

- Frontend 八页 UI；
- 文件上传、MIME 校验、OCR Provider 和临时文件清理；
- Feedback 数据库迁移和正式 API Router；
- 创建 Tag、合并 dev 或发布比赛版本；
- 把本地匹配音乐升级为实时 AI 生成。

这些内容由对应负责人完成，本分支只交付 AI 模块、共享 Schema、测试和联调文档。
