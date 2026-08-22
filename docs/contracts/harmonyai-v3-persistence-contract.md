# HarmonyAI V3 Persistence Contract

> 版本：`3.0.0-draft.2`
> 状态：`PROPOSED_FOR_FREEZE`
> 权威主合同：`harmonyai-v3-contract-freeze-v3.0.0-draft.2.md`
> 目标数据库：SQLite（开发/测试）与 MySQL（部署）语义一致。

## 1. 持久化原则

1. V3 新表与现有 V2 表并行；不原地改变 V2.1/V2.2 语义。
2. 所有业务资源必须属于 Auth Context 中的用户；V3 禁止硬编码 `user_id=1`。
3. Revision 只新增不覆盖；下游通过 `(resource_id, revision)` 引用不可变 Snapshot。
4. Fact 与 Organ Link 分表，防止同一用户事实因多脏映射被重复计数。
5. Provider run、RAG run、Generation task 与最终业务结果分离。
6. 用户原文、OCR/ASR、自由反馈为敏感字段：加密/访问控制、禁止普通日志、支持删除。
7. JSON 只承载非关系核心的快照或展示数据；主外键、状态、版本、所有权和查询索引必须为真实列。
8. 所有表包含 `created_at`；可变表包含 `updated_at`。时间统一UTC。

## 2. 类型映射

| Contract 类型 | SQLite | MySQL |
|---|---|---|
| `ID` | `TEXT` | `VARCHAR(64)` |
| `Timestamp` | UTC ISO `TEXT` | `DATETIME(6)` UTC |
| enum | `TEXT + CHECK` | `VARCHAR + CHECK`（不使用MySQL ENUM） |
| `Score01` | `REAL + CHECK` | `DECIMAL(6,5) + CHECK` |
| JSON | `TEXT` 且应用层验证 | `JSON` |
| hash | `TEXT` | `CHAR(71)` 或 `VARCHAR(96)` |

所有迁移必须同时提供 SQLite 与 MySQL 路径。应用层 Pydantic Schema 是 JSON 内容的权威验证器。

## 3. Ownership 与现有表

### 3.1 users

复用现有 `users` 主键，但 V3 API 必须通过认证中间件得到 `user_id`。若游客模式保留，必须创建受控 guest user/session，不允许路由直接写固定用户。

### 3.2 `user_profiles`

| 列 | 类型 | 约束 |
|---|---|---|
| `user_id` | FK | PK → users.id |
| `nickname` | string | NOT NULL，用户可修改 |
| `avatar_storage_key` | string nullable | 不持久化临时签名URL |
| `created_at/updated_at` | timestamp | NOT NULL |

个人主页的 `history_count/favorite_count` 为查询聚合值，不冗余存入本表。

### 3.3 `voice_recordings`

| 列 | 类型 | 约束 |
|---|---|---|
| `audio_id` | ID | PK |
| `user_id/session_id` | FK | NOT NULL |
| `storage_key` | string | NOT NULL |
| `format/duration_ms` | string/int | NOT NULL |
| `status` | string | uploaded/processing/ready/failed/deleted |
| `retention_expires_at` | timestamp nullable | 生命周期 |
| `created_at/updated_at` | timestamp | NOT NULL |

索引：`(user_id,created_at DESC)`。删除账户或用户删除录音时先撤销访问，再删除Blob。

### 3.4 sessions

复用或扩展现有 `sessions`：

| 列 | 类型 | 约束 |
|---|---|---|
| `session_id` | ID | PK |
| `user_id` | FK | NOT NULL → users.id |
| `flow_version` | string | NOT NULL，V3为 `v3` |
| `status` | string | `active/completed/abandoned/blocked` |
| `created_at/updated_at` | timestamp | NOT NULL |

索引：`(user_id, created_at DESC)`。

## 4. Information Understanding Tables

### 4.1 `understanding_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `understanding_id` | ID | PK |
| `user_id` | FK | NOT NULL |
| `session_id` | FK | NOT NULL |
| `current_revision` | integer | NOT NULL, `>=1` |
| `status` | string | queued/processing/needs_confirmation/confirmed/degraded/failed |
| `safety_status` | string | NOT NULL |
| `degradation_json` | JSON | NOT NULL |
| `created_at/updated_at` | timestamp | NOT NULL |

唯一：`(understanding_id, user_id)`。索引：`(session_id)`、`(user_id,status)`。

### 4.2 `understanding_sources`

| 列 | 类型 | 约束 |
|---|---|---|
| `source_id` | ID | PK |
| `understanding_id` | FK | NOT NULL → understanding_runs |
| `source_type` | string | document/case_summary/narrative/voice_transcript |
| `processing_status` | string | NOT NULL |
| `document_id/audio_id` | FK nullable | 对应源资源 |
| `text_ciphertext` | encrypted text nullable | 敏感；普通日志禁止 |
| `text_hash` | string nullable | 去重用，不可逆 |
| `captured_at` | timestamp | NOT NULL |
| `created_at/updated_at` | timestamp | NOT NULL |

索引：`(understanding_id,source_type)`。不得在索引中存原文。

### 4.3 `understanding_revisions`

| 列 | 类型 | 约束 |
|---|---|---|
| `understanding_id` | FK | PK part |
| `revision` | integer | PK part，`>=1` |
| `previous_revision` | integer nullable | 同资源前一版本 |
| `status` | string | needs_confirmation/confirmed/degraded |
| `case_summary_json` | JSON nullable | 通过CaseSummary Schema验证 |
| `presentation_json` | JSON | NOT NULL |
| `confirmation_decision` | string nullable | Contract枚举 |
| `confirmed_at` | timestamp nullable | 仅确认后有值 |
| `created_at` | timestamp | NOT NULL |

唯一：`(understanding_id,revision)`。Revision 行不可 UPDATE；状态变化通过创建下一 Revision 或受控 confirmation fields 完成。

### 4.4 `normalized_facts`

| 列 | 类型 | 约束 |
|---|---|---|
| `fact_id` | ID | PK |
| `understanding_id` | FK | NOT NULL |
| `understanding_revision` | integer | NOT NULL，复合FK |
| `fact_code/category` | string | NOT NULL |
| `display_name` | string | NOT NULL |
| `value_json` | JSON | NOT NULL，判别联合验证 |
| `time_window` | string | NOT NULL |
| `negated` | boolean | NOT NULL |
| `subject` | string | self/other/unknown |
| `confirmation_status` | string | confirmed/unconfirmed/rejected |
| `extraction_method` | string | qwen/rule/user_correction |
| `extraction_confidence` | score nullable | 非医学准确率 |
| `supersedes_fact_id` | FK nullable | 修正链 |
| `created_at` | timestamp | NOT NULL |

唯一：`(understanding_id,understanding_revision,fact_id)`。索引：`(understanding_id,understanding_revision,confirmation_status)`。

### 4.5 `fact_source_refs`

| 列 | 类型 | 约束 |
|---|---|---|
| `fact_id` | FK | PK part |
| `source_id` | FK | PK part |
| `span_ref` | string nullable | 不保存原文 |
| `created_at` | timestamp | NOT NULL |

## 5. Assessment Tables

### 5.1 `assessment_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `assessment_id` | ID | PK |
| `user_id` | FK | NOT NULL |
| `session_id` | FK | NOT NULL |
| `understanding_id` | FK | NOT NULL |
| `understanding_revision` | integer | NOT NULL |
| `current_revision` | integer | NOT NULL |
| `status` | string | needs_confirmation/confirmed/degraded/withheld |
| `safety_status` | string | NOT NULL |
| `questionnaire_schema_version` | string nullable | V3为 questionnaire_v3.0 |
| `questionnaire_submission_json` | JSON nullable | 完整提交快照；按QuestionnaireV3Submission验证 |
| `user_goal_json` | JSON | NOT NULL |
| `created_at/updated_at` | timestamp | NOT NULL |

唯一：`(session_id,assessment_id)`。索引：`(user_id,created_at DESC)`、`(session_id,status)`。

### 5.2 `assessment_revisions_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `assessment_id` | FK | PK part |
| `revision` | integer | PK part |
| `previous_revision` | integer nullable | 修正链 |
| `understanding_revision` | integer | NOT NULL |
| `status/confirmation_status` | string | NOT NULL |
| `state_summary` | text | NOT NULL |
| `recent_context_summary` | text nullable | 用户友好摘要 |
| `organ_profile_json` | JSON | NOT NULL，Profile Schema验证 |
| `evidence_coverage` | score | SERVER_INTERNAL |
| `source_diversity` | integer | `>=0` |
| `conflicts_json/missing_information_json` | JSON | NOT NULL |
| `degradation_json` | JSON | NOT NULL |
| `presentation_json` | JSON | NOT NULL |
| `confirmed_at` | timestamp nullable | 确认后有值 |
| `created_at` | timestamp | NOT NULL |

复合唯一：`(assessment_id,revision)`。Diagnosis FK必须指向该复合键。

### 5.3 `fact_evidence`

| 列 | 类型 | 约束 |
|---|---|---|
| `fact_evidence_id` | ID | PK |
| `assessment_id` | FK | NOT NULL |
| `assessment_revision` | integer | NOT NULL，复合FK |
| `fact_id` | FK | NOT NULL |
| `claim_code/category/display_name` | string | NOT NULL |
| `value_json` | JSON | NOT NULL |
| `time_window/direction` | string | NOT NULL |
| `reliability` | score | NOT NULL |
| `confirmation_status` | string | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(assessment_id,assessment_revision,fact_id)`，保证一个事实只计一次。

### 5.4 `organ_evidence`

该表持久化 `OrganEvidenceLink`，表名按 Owner 冻结为 `organ_evidence`。

| 列 | 类型 | 约束 |
|---|---|---|
| `organ_evidence_link_id` | ID | PK |
| `fact_evidence_id` | FK | NOT NULL → fact_evidence |
| `organ/element/direction` | string | NOT NULL，Canonical enum |
| `link_strength` | score | NOT NULL |
| `mapping_rule_id` | string | NOT NULL |
| `mapping_version` | string | NOT NULL |
| `explanation_summary` | text | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(fact_evidence_id,organ,mapping_rule_id)`。索引：`(organ,mapping_version)`。

## 6. Diagnosis / RAG Tables

### 6.1 `diagnosis_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `diagnosis_id` | ID | PK |
| `user_id/session_id` | FK | NOT NULL |
| `assessment_id` | FK | NOT NULL |
| `assessment_revision` | integer | NOT NULL，复合FK |
| `status` | string | running/success/degraded/abstained/withheld/failed |
| `abstained` | boolean | NOT NULL |
| `abstain_reason` | string nullable | Contract枚举 |
| `primary_tendency_id` | FK nullable | diagnosis_candidates |
| `element_profile_json` | JSON nullable | Profile Schema |
| `degradation_json` | JSON | NOT NULL |
| `presentation_json` | JSON | NOT NULL |
| `provider_run_id` | FK nullable | ai_provider_runs |
| `rag_run_id` | FK nullable | rag_retrieval_runs |
| `created_at/updated_at` | timestamp | NOT NULL |

唯一：`(assessment_id,assessment_revision,diagnosis_id)`。索引：`(session_id,created_at)`、`(status)`。

### 6.2 `diagnosis_candidates`

| 列 | 类型 | 约束 |
|---|---|---|
| `candidate_id` | ID | PK |
| `diagnosis_id` | FK | NOT NULL |
| `syndrome_code/display_name` | string | NOT NULL |
| `relative_support` | score | NOT NULL |
| `reasoning_summary` | text | 用户友好，不含思维链 |
| `rank` | integer | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(diagnosis_id,syndrome_code)`。

### 6.3 `diagnosis_candidate_evidence`

| 列 | 类型 | 约束 |
|---|---|---|
| `candidate_id` | FK | PK part |
| `fact_evidence_id` | FK | PK part |
| `direction` | string | supporting/contradicting |

### 6.4 `rag_retrieval_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `rag_run_id` | ID | PK |
| `diagnosis_id` | FK | NOT NULL |
| `query_hash` | hash | NOT NULL；不保存原Query原文 |
| `knowledge_version` | string | NOT NULL |
| `status` | string | success/degraded/failed/empty |
| `top_k/minimum_score` | numeric | NOT NULL |
| `degradation_json` | JSON | NOT NULL |
| `created_at` | timestamp | NOT NULL |

### 6.5 `rag_retrieval_hits`

| 列 | 类型 | 约束 |
|---|---|---|
| `rag_run_id` | FK | PK part |
| `chunk_id` | string | PK part |
| `source_id/source_title/section` | string | NOT NULL |
| `retrieval_score` | score | SERVER_INTERNAL |
| `display_summary` | text | 脱敏摘要 |
| `text_ciphertext` | encrypted text | SENSITIVE_SERVER_INTERNAL |
| `review_status/knowledge_version` | string | NOT NULL |

只有 `approved` hit 可写入 Provider request snapshot。

### 6.6 `ai_provider_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `provider_run_id` | ID | PK |
| `purpose` | string | understanding/diagnosis/schema_repair |
| `resource_id` | ID | NOT NULL |
| `provider/model` | string | 运维内部 |
| `status/error_code` | string | NOT NULL/nullable |
| `attempts/latency_ms` | integer | NOT NULL |
| `input_tokens/output_tokens` | integer nullable | `>=0` |
| `request_hash/response_hash` | hash nullable | 不存原Prompt/Response |
| `created_at` | timestamp | NOT NULL |

普通表禁止保存 Provider Key、完整 Prompt 或原始异常。

## 7. Prescription / Music Tables

### 7.1 `prescription_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `prescription_id` | ID | PK |
| `user_id/session_id` | FK | NOT NULL |
| `diagnosis_id` | FK | NOT NULL |
| `status` | string | success/degraded/withheld |
| `prescription_mode` | string | syndrome_based/conservative_fallback |
| `tone_profile_json` | JSON nullable | withheld时可空 |
| `generation_spec_json` | JSON nullable | withheld时必须空 |
| `preference_profile_id/version` | FK/int nullable | Snapshot来源 |
| `personalization_json` | JSON | NOT NULL |
| `presentation_json` | JSON | NOT NULL |
| `created_at` | timestamp | NOT NULL |

索引：`(user_id,created_at DESC)`、`(diagnosis_id)`。

### 7.2 `generation_tasks`

| 列 | 类型 | 约束 |
|---|---|---|
| `task_id` | ID | PK |
| `user_id/session_id` | FK | NOT NULL |
| `prescription_id` | FK | NOT NULL |
| `idempotency_key` | string | NOT NULL |
| `status` | string | queued/running/succeeded/matched_fallback/failed/cancelled |
| `provider` | string nullable | 运维内部 |
| `provider_task_id` | string nullable | 运维内部 |
| `progress_value` | integer nullable | `0..100` |
| `progress_indeterminate` | boolean | NOT NULL |
| `message_code` | string | NOT NULL；前端映射安全文案 |
| `fallback_applied` | boolean | NOT NULL |
| `fallback_reason_code` | string nullable | 稳定错误码 |
| `error_code` | string nullable | 不存原始异常 |
| `music_asset_id` | FK nullable | 成功态必须有值 |
| `created_at/updated_at/completed_at` | timestamp | completed_at可空 |

唯一：`(user_id,idempotency_key)`。索引：`(status,updated_at)`、`(prescription_id)`。

状态约束：成功态必须有 `music_asset_id`；非成功态在完成前可空；`matched_fallback` 的Asset必须 `source_type=matched`。

### 7.3 `music_assets`

| 列 | 类型 | 约束 |
|---|---|---|
| `music_asset_id` | ID | PK |
| `owner_user_id` | FK nullable | 生成资产属于用户；公共曲库可空 |
| `generation_task_id` | FK nullable | generated资产必填 |
| `source_type` | string | generated/matched/comfort_audio |
| `catalog_track_id` | string nullable | matched资产使用 |
| `title` | string | NOT NULL |
| `storage_key` | string | NOT NULL；不直接保存临时签名URL |
| `format/duration_seconds` | string/int | NOT NULL |
| `checksum` | string | NOT NULL |
| `tone_profile_json` | JSON nullable | comfort_audio可空 |
| `bpm/instruments_json` | numeric/JSON nullable | 元数据 |
| `playable_status` | string | ready/expired/quarantined/deleted |
| `retention_expires_at` | timestamp nullable | 生命周期 |
| `created_at/updated_at` | timestamp | NOT NULL |

唯一：`(checksum,owner_user_id)` 仅用于去重，不跨用户泄露存在性。`stream_url` 运行时由授权下载端点生成，不持久化。

## 8. Feedback / Preference / Favorite Tables

### 8.1 `feedback_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `feedback_id` | ID | PK |
| `user_id/session_id` | FK | NOT NULL |
| `music_asset_id` | FK | NOT NULL |
| `change_label` | string | NOT NULL |
| `post_state_json/experience_json` | JSON nullable | 选填 |
| `continue_use` | string nullable | yes/maybe/no |
| `liked_features_json` | JSON | NOT NULL default [] |
| `adjustment_preferences_json` | JSON | NOT NULL default []，互斥校验 |
| `comment_ciphertext` | encrypted text nullable | 敏感 |
| `playback_json` | JSON nullable | 服务端校验 |
| `created_at` | timestamp | NOT NULL |

索引：`(user_id,created_at DESC)`、`(music_asset_id)`。

### 8.2 `user_music_preferences`

| 列 | 类型 | 约束 |
|---|---|---|
| `profile_id` | ID | PK |
| `user_id` | FK | NOT NULL UNIQUE |
| `version` | integer | NOT NULL, `>=1` |
| `preferred_bpm_min/max` | integer nullable | min <= max |
| `bpm_weight` | score nullable | 个人偏好强度 |
| `preferred_duration_seconds` | integer nullable | `>0` |
| `duration_weight` | score nullable | 个人偏好强度 |
| `feedback_count` | integer | NOT NULL default 0 |
| `minimum_samples_for_application` | integer | NOT NULL default 3 |
| `created_at/updated_at` | timestamp | NOT NULL |

更新采用 `WHERE version=:expected_version`，成功后 `version+1`。

### 8.3 `user_preference_items`

| 列 | 类型 | 约束 |
|---|---|---|
| `profile_id` | FK | PK part |
| `category` | string | PK part；instrument/feature/ambient |
| `code` | string | PK part |
| `polarity` | string | preferred/disliked |
| `weight` | score | NOT NULL |
| `sample_count` | integer | NOT NULL |
| `updated_at` | timestamp | NOT NULL |

唯一：`(profile_id,category,code,polarity)`。

### 8.4 `preference_events`

| 列 | 类型 | 约束 |
|---|---|---|
| `event_id` | ID | PK |
| `profile_id` | FK | NOT NULL |
| `feedback_id` | FK nullable | 来源反馈 |
| `previous_version/new_version` | integer | NOT NULL |
| `patch_json` | JSON | NOT NULL |
| `created_at` | timestamp | NOT NULL |

该表支持审计、撤销和重建 Profile；事件不得修改全局医学规则。

### 8.5 `favorites`

| 列 | 类型 | 约束 |
|---|---|---|
| `favorite_id` | ID | PK |
| `user_id` | FK | NOT NULL |
| `music_asset_id` | FK | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(user_id,music_asset_id)`。取消收藏删除该关系或使用软删除审计策略，两端必须统一；本合同选择硬删除关系、不删除 Music Asset。

### 8.6 历史记录

不新增重复的“history”事实表。音乐历史从 `generation_tasks JOIN music_assets` 查询，按 `created_at DESC, task_id DESC` 游标分页。只返回当前用户生成资产和其有权访问的公共matched资产。

## 9. 事务边界

1. **Understanding confirmation**：写新 Revision、Fact修正、更新 current_revision 同一事务。
2. **Assessment confirmation**：写新 Assessment Revision、FactEvidence、OrganEvidence、Profile、更新 current_revision 同一事务。
3. **Diagnosis completion**：RAG run、Provider run、Candidates、Evidence links、Diagnosis状态同一最终提交；失败保留run审计但不产生伪success。
4. **Music task completion**：Music Asset ready 后再把 Task 置成功；二者同一事务。
5. **Feedback close-loop**：Feedback、Favorite、Preference Event、Profile version 同一事务；若Profile失败，反馈可保存但响应必须 `preference_update.applied=false`。

## 10. 删除与保留

| 数据 | 默认策略 |
|---|---|
| 原始上传文件/OCR/ASR音频 | 可配置短期保留；用户删除时清除Blob与受控文本 |
| Understanding/Assessment/Diagnosis | 依据产品隐私策略保留；删除账户时级联匿名化或删除 |
| Provider/RAG run | 只留hash、状态、指标；原始Prompt不进入普通表 |
| Generated Music Asset | 按retention期限；收藏可延长但需明确告知 |
| Feedback comment | 用户可删除；禁止普通日志 |
| Medical knowledge | 全局版本化，不因用户删除而改变 |

删除顺序必须先撤销访问，再异步删除Blob；失败任务可重试且幂等。

## 11. Migration / Compatibility

1. 新增 V3 表，不重命名或重用 V2 表承担新语义。
2. Migration 必须有 upgrade、downgrade（若数据不可逆则明确阻止）、SQLite test 和 MySQL test。
3. 部署顺序：新增表 → 部署双版本Backend → V3前端灰度；不得先切换前端。
4. V2数据不会自动伪装成V3 Evidence。若后续迁移，必须独立ETL并标记 `source_version=v2`。
5. 所有唯一约束和复合FK在 SQLite 测试中必须启用 foreign keys 验证。

## 12. Backend Freeze Checklist

- [ ] 所有 Contract ID、Revision、状态都有真实列和约束。
- [ ] `FactEvidence` 与 `OrganEvidenceLink` 分表且不会重复计数。
- [ ] Diagnosis/RAG/Provider run 可独立审计。
- [ ] Prescription 与 Generation Task/Asset 分离。
- [ ] Feedback、Favorite、Preference Event/Profile 形成真实事务闭环。
- [ ] Profile optimistic concurrency 已定义。
- [ ] History由权威表查询，不重复存储。
- [ ] SQLite/MySQL migration和约束语义一致。
- [ ] V3路由不硬编码用户ID，所有查询验证ownership。
- [ ] 原文、Prompt、Key、原始异常不进入普通日志。
