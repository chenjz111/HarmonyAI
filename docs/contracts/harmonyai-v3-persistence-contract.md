# HarmonyAI V3 Persistence Contract

> 版本：`3.0.0-draft.3`
> 状态：`PROPOSED_FOR_FINAL_REVIEW`
> 权威主合同：`harmonyai-v3-contract-freeze-v3.0.0-draft.3.md`
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

### 3.1 `users` 与 `user_identities`

复用现有 `users.id INTEGER` 作为所有数据库FK的内部用户主键，不改变V2主键。V3新增身份映射：

| 列 | 类型 | 约束 |
|---|---|---|
| `internal_user_pk` | integer FK | PK → users.id |
| `public_user_id` | ID | NOT NULL UNIQUE，API使用 |
| `auth_type` | string | registered/guest |
| `guest_expires_at` | timestamp nullable | guest必填 |
| `created_at/updated_at` | timestamp | NOT NULL |

认证中间件通过该表生成AuthPrincipal。V3禁止硬编码 `user_id=1`。跨用户查询必须先按internal_user_pk过滤。

### 3.2 `user_profiles`

| 列 | 类型 | 约束 |
|---|---|---|
| `internal_user_pk` | integer FK | PK → users.id |
| `nickname` | string nullable | 老用户/游客允许空，Read Model提供安全默认文案 |
| `avatar_storage_key` | string nullable | 不持久化临时签名URL |
| `created_at/updated_at` | timestamp | NOT NULL |

个人主页的history_count/favorite_count为查询聚合值，不冗余存入本表。

### 3.3 `voice_recordings`

| 列 | 类型 | 约束 |
|---|---|---|
| `audio_id` | ID | PK |
| `internal_user_pk` | integer FK | NOT NULL → users.id |
| `session_row_id` | integer FK | NOT NULL → sessions.id |
| `storage_key` | string | NOT NULL |
| `format/duration_ms` | string/int | NOT NULL |
| `status` | string | uploaded/processing/ready/failed/deleted |
| `retention_expires_at` | timestamp nullable | 生命周期 |
| `created_at/updated_at` | timestamp | NOT NULL |

索引：`(internal_user_pk,created_at DESC)`。删除账户或用户删除录音时先撤销访问，再删除Blob。

### 3.4 `sessions` 兼容策略

继续复用现有表结构：整数 `sessions.id` 保持PK，字符串 `sessions.session_id` 保持NOT NULL UNIQUE业务ID。V3只新增：

| 列 | 类型 | 约束 |
|---|---|---|
| `flow_version` | string nullable | V3写 `v3`；V2旧行允许空 |
| `status` | string | active/completed/abandoned/blocked |

现有 `user_id` 列作为internal_user_pk使用并补真实FK到users.id；不得把session_id改成PK。所有新V3表使用 `session_row_id INTEGER FK → sessions.id`，API Read Model继续返回字符串session_id。索引：`(user_id,created_at DESC)`、`(session_id)`。
## 4. Information Understanding Tables

### 4.1 `understanding_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `understanding_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL |
| `session_row_id` | FK | NOT NULL |
| `current_revision` | integer | NOT NULL, `>=1` |
| `status` | string | queued/processing/needs_confirmation/confirmed/degraded/failed |
| `safety_status` | string | NOT NULL |
| `degradation_json` | JSON | NOT NULL |
| `created_at/updated_at` | timestamp | NOT NULL |

唯一：`(understanding_id, internal_user_pk)`。索引：`(session_row_id)`、`(internal_user_pk,status)`。

### 4.2 `understanding_sources`

| 列 | 类型 | 约束 |
|---|---|---|
| `source_id` | ID | PK |
| `understanding_id` | FK | NOT NULL → understanding_runs |
| `source_type` | string | document/case_summary/narrative/voice_transcript/questionnaire |
| `processing_status` | string | NOT NULL |
| `document_id` | FK nullable | 仅 document/case_summary 可用 |
| `audio_id` | FK nullable | 仅 voice_transcript 可用 |
| `questionnaire_submission_id` | FK nullable | 仅 questionnaire 可用 |
| `text_ciphertext` | encrypted text nullable | 敏感；普通日志禁止 |
| `text_hash` | string nullable | 去重用，不可逆 |
| `captured_at` | timestamp | NOT NULL |
| `created_at/updated_at` | timestamp | NOT NULL |

约束：三种资源 FK 至多一个非空，且必须与 `source_type` 一致；narrative 无资源 FK。索引：`(understanding_id,source_type)`。不得在索引中存原文。
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

唯一：`(understanding_id,revision)`。Revision 行不可 UPDATE；包括 confirmation 在内的状态变化都必须创建下一 Revision，禁止原地修改“受控字段”。

### 4.4 `normalized_facts`

每个来源 owner 的 Revision/Snapshot 必须物化完整事实；不能只存增量后依赖应用层回放。Understanding 来源使用不可变 Understanding Revision；确定性问卷来源使用不可变 Questionnaire Submission。

| 列 | 类型 | 约束 |
|---|---|---|
| `fact_row_id` | ID | PK，数据库行身份 |
| `fact_id` | ID | NOT NULL，跨 revision 稳定的逻辑事实 ID |
| `owner_type` | string | understanding/questionnaire |
| `understanding_id` | FK nullable | owner_type=understanding 时必填 |
| `understanding_revision` | integer nullable | 与 understanding_id 组成复合FK |
| `questionnaire_submission_id` | FK nullable | owner_type=questionnaire 时必填 |
| `fact_code/category` | string | NOT NULL |
| `display_name` | string | NOT NULL |
| `value_json` | JSON | NOT NULL，判别联合验证 |
| `time_window` | string | NOT NULL |
| `negated` | boolean | NOT NULL |
| `subject` | string | self/other/unknown |
| `confirmation_status` | string | confirmed/unconfirmed/rejected |
| `extraction_method` | string | qwen/rule/user_correction/deterministic_questionnaire_mapping |
| `extraction_confidence` | score nullable | 非医学准确率 |
| `supersedes_fact_row_id` | FK nullable | 指向上一 revision 的行；修正链 |
| `created_at` | timestamp | NOT NULL |

CHECK 必须保证两种 owner 二选一：`understanding` 要求 Understanding 两列非空且 questionnaire 为空；`questionnaire` 要求 questionnaire 非空且 Understanding 两列为空。唯一：`(understanding_id,understanding_revision,fact_id)`（Understanding owner）与 `(questionnaire_submission_id,fact_id)`（Questionnaire owner）。索引：`(understanding_id,understanding_revision,confirmation_status)`、`(questionnaire_submission_id)`。新 Understanding revision 复制未变化事实并为全部行生成新的 `fact_row_id`；变化事实保留同一逻辑 `fact_id`。Questionnaire Fact 不创建伪 Understanding revision。

### 4.5 `fact_source_refs`

| 列 | 类型 | 约束 |
|---|---|---|
| `fact_row_id` | FK | PK part → normalized_facts.fact_row_id |
| `source_type` | string | PK part；Canonical SourceType |
| `source_id` | ID | PK part；多态资源ID，不声明跨表FK |
| `span_ref` | string nullable | 不保存原文 |
| `created_at` | timestamp | NOT NULL |

### 4.6 `questionnaire_submissions_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `questionnaire_submission_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL |
| `session_row_id` | FK | NOT NULL |
| `schema_id/schema_version/manifest_version/content_checksum` | string | NOT NULL |
| `time_window_days` | integer | NOT NULL，V3冻结为7 |
| `answers_json` | JSON | NOT NULL，按对应 Manifest 验证 |
| `idempotency_key` | string | NOT NULL |
| `submitted_at` | timestamp | NOT NULL |

唯一：`(internal_user_pk,idempotency_key)`。同一键不同 payload hash 返回 `IDEMPOTENCY_CONFLICT`；索引：`(session_row_id,submitted_at)`。
## 5. Assessment Tables

### 5.1 `assessment_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `assessment_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL |
| `session_row_id` | FK | NOT NULL |
| `understanding_id` | FK | NOT NULL |
| `understanding_revision` | integer | NOT NULL，读取已确认Snapshot |
| `questionnaire_submission_id` | FK nullable | → questionnaire_submissions_v3 |
| `current_revision` | integer | NOT NULL |
| `status` | string | needs_confirmation/confirmed/degraded/withheld |
| `safety_status` | string | NOT NULL；CHECK为主合同SafetyStatus |
| `user_goal_json` | JSON | NOT NULL |
| `created_at/updated_at` | timestamp | NOT NULL |

Assessment 不复制问卷 answers；通过 `questionnaire_submission_id` 引用已按 schema identity/checksum 保存的不可变 Submission。唯一：`(session_row_id,assessment_id)`。索引：`(internal_user_pk,created_at DESC)`、`(session_row_id,status)`。

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

每个 Assessment Revision 必须物化完整 Evidence 快照。

| 列 | 类型 | 约束 |
|---|---|---|
| `fact_evidence_row_id` | ID | PK，数据库行身份 |
| `fact_evidence_id` | ID | NOT NULL，跨 revision 稳定的逻辑 Evidence ID |
| `assessment_id` | FK | NOT NULL |
| `assessment_revision` | integer | NOT NULL，复合FK |
| `normalized_fact_row_id` | FK | NOT NULL → normalized_facts.fact_row_id |
| `claim_code/category/display_name` | string | NOT NULL |
| `value_json` | JSON | NOT NULL |
| `time_window/direction` | string | NOT NULL |
| `reliability` | score | NOT NULL |
| `confirmation_status` | string | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(assessment_id,assessment_revision,fact_evidence_id)`，保证同一 revision 中一个逻辑事实只计一次。新 revision 复制全部有效 Evidence 行并生成新的 row ID。

### 5.4 `organ_evidence`

该表持久化 `OrganEvidenceLink`，一个 FactEvidence 可关联多个脏腑，但不能复制 FactEvidence 本身。

| 列 | 类型 | 约束 |
|---|---|---|
| `organ_evidence_link_id` | ID | PK |
| `fact_evidence_row_id` | FK | NOT NULL → fact_evidence.fact_evidence_row_id |
| `organ/element/direction` | string | NOT NULL，Canonical enum |
| `link_strength` | score | NOT NULL |
| `mapping_rule_id` | string | NOT NULL |
| `mapping_version` | string | NOT NULL |
| `explanation_summary` | text | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(fact_evidence_row_id,organ,mapping_rule_id)`。索引：`(organ,mapping_version)`。
## 6. Diagnosis / RAG Tables

### 6.1 `diagnosis_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `diagnosis_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL → users.id |
| `session_row_id` | FK | NOT NULL → sessions.id |
| `assessment_id` | FK | NOT NULL |
| `assessment_revision` | integer | NOT NULL，复合FK |
| `status` | string | running/success/degraded/abstained/withheld/failed |
| `abstained` | boolean | NOT NULL |
| `abstain_reason` | string nullable | Contract枚举 |
| `primary_tendency_id` | FK nullable | → diagnosis_candidates；abstained/withheld时必须空 |
| `element_profile_json` | JSON nullable | Profile Schema |
| `degradation_json` | JSON | NOT NULL |
| `presentation_json` | JSON | NOT NULL |
| `provider_run_id` | FK nullable | ai_provider_runs |
| `rag_run_id` | FK nullable | rag_retrieval_runs |
| `created_at/updated_at` | timestamp | NOT NULL |

唯一：`(assessment_id,assessment_revision,diagnosis_id)`。索引：`(session_row_id,created_at)`、`(status)`。

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

唯一：`(diagnosis_id,syndrome_code)`。写入顺序冻结为：先插入 `diagnosis_runs(primary_tendency_id=NULL)`，再插入 candidates/evidence，最后在同一事务内回填 primary_tendency_id 并提交；避免循环 FK 插入失败。

### 6.3 `diagnosis_candidate_evidence`

| 列 | 类型 | 约束 |
|---|---|---|
| `candidate_id` | FK | PK part |
| `fact_evidence_row_id` | FK | PK part → fact_evidence.fact_evidence_row_id |
| `direction` | string | supporting/contradicting |

### 6.4 `knowledge_manifests`

| 列 | 类型 | 约束 |
|---|---|---|
| `knowledge_manifest_id` | ID | PK |
| `knowledge_version` | string | NOT NULL UNIQUE |
| `embedding_provider/model/version` | string | NOT NULL |
| `distance_metric/score_semantics` | string | NOT NULL |
| `minimum_score` | score | NOT NULL |
| `chunk_count` | integer | NOT NULL |
| `manifest_checksum` | string | NOT NULL UNIQUE |
| `review_status/medical_review_version` | string | NOT NULL |
| `created_at` | timestamp | NOT NULL |

只有 `review_status=approved` 的Manifest可被production Retriever加载；已使用版本不可原地修改。

### 6.5 `knowledge_chunks_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `chunk_row_id` | ID | PK |
| `knowledge_manifest_id` | FK | NOT NULL |
| `chunk_id` | string | NOT NULL |
| `source_id/source_title/section` | string | NOT NULL |
| `text_ciphertext` | encrypted text | NOT NULL |
| `display_summary` | text | NOT NULL |
| `claim_codes_json/organ_codes_json` | JSON | NOT NULL |
| `content_checksum` | string | NOT NULL |
| `review_status` | string | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(knowledge_manifest_id,chunk_id)`。索引：`(knowledge_manifest_id,review_status)`。Embedding/vector存储按Manifest版本隔离，数据库行和向量索引以 `chunk_id + content_checksum` 双向校验。
### 6.6 `rag_retrieval_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `rag_run_id` | ID | PK |
| `diagnosis_id` | FK | NOT NULL |
| `query_hash` | hash | NOT NULL；不保存原Query原文 |
| `query_builder_version` | string | NOT NULL |
| `knowledge_manifest_id` | FK | NOT NULL |
| `knowledge_version/manifest_checksum` | string | NOT NULL |
| `embedding_version` | string | NOT NULL |
| `distance_metric/score_semantics` | string | NOT NULL |
| `status` | string | success/degraded/failed/empty |
| `top_k/minimum_score` | numeric | NOT NULL |
| `degradation_json` | JSON | NOT NULL |
| `created_at` | timestamp | NOT NULL |

`status=success` 必须至少有一个合格 hit；0 hit 只能是 empty/degraded/failed，不能伪装成功。
### 6.7 `rag_retrieval_hits`

| 列 | 类型 | 约束 |
|---|---|---|
| `rag_run_id` | FK | PK part |
| `chunk_id` | string | PK part |
| `source_id/source_title/section` | string | NOT NULL |
| `retrieval_score` | score | SERVER_INTERNAL |
| `display_summary` | text | 脱敏摘要 |
| `text_ciphertext` | encrypted text | SENSITIVE_SERVER_INTERNAL |
| `review_status/knowledge_version` | string | NOT NULL |
| `chunk_content_checksum` | string | NOT NULL；必须匹配Manifest |

只有 `approved` hit 可写入 Provider request snapshot。

### 6.8 `ai_provider_runs`

| 列 | 类型 | 约束 |
|---|---|---|
| `provider_run_id` | ID | PK |
| `purpose` | string | understanding/diagnosis/schema_repair |
| `resource_id` | ID | NOT NULL |
| `provider/model` | string | 运维内部 |
| `prompt_version/response_schema_version` | string | NOT NULL |
| `status/error_code` | string | NOT NULL/nullable |
| `attempts/latency_ms` | integer | NOT NULL |
| `input_tokens/output_tokens` | integer nullable | `>=0` |
| `request_hash/response_hash` | hash nullable | 不存原Prompt/Response |
| `knowledge_version/mapping_version` | string nullable | Diagnosis审计必填 |
| `created_at` | timestamp | NOT NULL |

普通表禁止保存 Provider Key、完整 Prompt 或原始异常。

## 7. Prescription / Music Tables

### 7.1 `prescription_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `prescription_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL → users.id |
| `session_row_id` | FK | NOT NULL → sessions.id |
| `diagnosis_id` | FK | NOT NULL |
| `status` | string | success/degraded/withheld |
| `prescription_mode` | string | syndrome_based/conservative_fallback |
| `tone_profile_json` | JSON nullable | withheld时可空 |
| `generation_spec_json` | JSON nullable | withheld时必须空 |
| `preference_profile_id` | FK nullable | → user_music_preferences |
| `preference_version_id` | FK nullable | → user_music_preference_versions，不可变 Snapshot |
| `personalization_json` | JSON | NOT NULL |
| `presentation_json` | JSON | NOT NULL |
| `created_at` | timestamp | NOT NULL |

索引：`(internal_user_pk,created_at DESC)`、`(diagnosis_id)`。

### 7.2 `generation_tasks`

| 列 | 类型 | 约束 |
|---|---|---|
| `task_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL → users.id |
| `session_row_id` | FK | NOT NULL → sessions.id |
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

唯一：`(internal_user_pk,idempotency_key)`。索引：`(status,updated_at)`、`(prescription_id)`。

状态约束：成功态必须有 `music_asset_id`；非成功态在完成前可空；`matched_fallback` 的Asset必须 `source_type=matched`。

### 7.3 `music_assets`

| 列 | 类型 | 约束 |
|---|---|---|
| `music_asset_id` | ID | PK |
| `owner_internal_user_pk` | FK nullable | 生成资产属于用户；公共曲库可空 |
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

唯一：`(checksum,owner_internal_user_pk)` 仅用于去重，不跨用户泄露存在性。`stream_url` 运行时由授权下载端点生成，不持久化。

## 8. Feedback / Preference / Favorite Tables

### 8.1 `feedback_v3`

| 列 | 类型 | 约束 |
|---|---|---|
| `feedback_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL → users.id |
| `session_row_id` | FK | NOT NULL → sessions.id |
| `music_asset_id` | FK | NOT NULL |
| `change_label` | string | NOT NULL |
| `pre_state_snapshot_json` | JSON nullable | 权威播放器听前快照；不可由客户端改写 |
| `post_state_json/experience_json` | JSON nullable | 选填 |
| `continue_use` | string nullable | yes/maybe/no |
| `liked_features_json` | JSON | NOT NULL default [] |
| `adjustment_preferences_json` | JSON | NOT NULL default []，互斥校验 |
| `comment_ciphertext` | encrypted text nullable | 敏感 |
| `playback_json` | JSON nullable | 服务端校验 |
| `idempotency_key` | string | NOT NULL |
| `preference_update_status` | string | pending/applied/failed/skipped |
| `created_at` | timestamp | NOT NULL |

唯一：`(internal_user_pk,idempotency_key)`。
索引：`(internal_user_pk,created_at DESC)`、`(music_asset_id)`。

### 8.2 `user_music_preferences`

该表只保存用户当前 Profile 指针，不原地覆盖历史版本。

| 列 | 类型 | 约束 |
|---|---|---|
| `profile_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL UNIQUE |
| `current_version_id` | FK nullable | → user_music_preference_versions |
| `created_at/updated_at` | timestamp | NOT NULL |

### 8.3 `user_music_preference_versions`

| 列 | 类型 | 约束 |
|---|---|---|
| `preference_version_id` | ID | PK |
| `profile_id` | FK | NOT NULL |
| `version` | integer | NOT NULL, `>=1` |
| `preferred_bpm_min/max` | integer nullable | min <= max |
| `bpm_weight` | score nullable | 个人偏好强度 |
| `preferred_duration_seconds` | integer nullable | `>0` |
| `duration_weight` | score nullable | 个人偏好强度 |
| `feedback_count` | integer | NOT NULL default 0 |
| `minimum_samples_for_application` | integer | NOT NULL default 3 |
| `created_at` | timestamp | NOT NULL |

唯一：`(profile_id,version)`。每次更新插入新版本，再以 `WHERE current_version_id=:expected_version_id` 原子更新当前指针；处方引用不可变 `preference_version_id`。

### 8.4 `user_preference_items`

| 列 | 类型 | 约束 |
|---|---|---|
| `preference_version_id` | FK | PK part → user_music_preference_versions |
| `category` | string | PK part；instrument/feature/ambient |
| `code` | string | PK part |
| `polarity` | string | preferred/disliked |
| `weight` | score | NOT NULL |
| `sample_count` | integer | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(preference_version_id,category,code,polarity)`。

### 8.5 `preference_events`

| 列 | 类型 | 约束 |
|---|---|---|
| `event_id` | ID | PK |
| `profile_id` | FK | NOT NULL |
| `feedback_id` | FK nullable | 来源反馈 |
| `previous_version_id/new_version_id` | FK nullable/FK | 不可变版本链 |
| `patch_json` | JSON | NOT NULL |
| `created_at` | timestamp | NOT NULL |

该表支持审计、撤销和重建 Profile；事件不得修改全局医学规则。
### 8.6 `favorites`

| 列 | 类型 | 约束 |
|---|---|---|
| `favorite_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL |
| `music_asset_id` | FK | NOT NULL |
| `created_at` | timestamp | NOT NULL |

唯一：`(internal_user_pk,music_asset_id)`。取消收藏删除该关系或使用软删除审计策略，两端必须统一；本合同选择硬删除关系、不删除 Music Asset。

### 8.7 历史记录

不新增重复的“history”事实表。音乐历史从 `generation_tasks JOIN music_assets` 查询，按 `created_at DESC, task_id DESC` 游标分页。只返回当前用户生成资产和其有权访问的公共matched资产。


### 8.8 `idempotency_records`

| 列 | 类型 | 约束 |
|---|---|---|
| `idempotency_record_id` | ID | PK |
| `internal_user_pk` | FK | NOT NULL |
| `operation` | string | NOT NULL |
| `idempotency_key` | string | NOT NULL |
| `request_hash` | hash | NOT NULL |
| `resource_type/resource_id` | string/ID nullable | 成功后绑定 |
| `status` | string | processing/succeeded/failed |
| `response_code` | integer nullable | 可重放状态码 |
| `created_at/expires_at` | timestamp | NOT NULL |

唯一：`(internal_user_pk,operation,idempotency_key)`。相同 key + 相同 hash 重放原结果；相同 key + 不同 hash 返回409。

## 9. 事务边界

1. **Understanding confirmation**：写新 Revision、Fact修正、更新 current_revision 同一事务。
2. **Assessment confirmation**：写新 Assessment Revision、FactEvidence、OrganEvidence、Profile、更新 current_revision 同一事务。
3. **Diagnosis completion**：RAG run、Provider run、Candidates、Evidence links、Diagnosis状态同一最终提交；失败保留run审计但不产生伪success。
4. **Music task completion**：Music Asset ready 后再把 Task 置成功；二者同一事务。
5. **Feedback 两阶段闭环**：阶段一在事务中写 Feedback（及独立 favorite 操作），提交后立即可返回；阶段二以 `feedback_id` 幂等地生成 Preference Event、新的不可变 Preference Version 并更新当前指针。阶段二失败不回滚已保存反馈，响应为 `preference_update.applied=false`，后续 worker 可安全重试。

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
2. V2继续使用现有 `create_all + sprint4 migrations` 路径；V3采用仓库内版本化 SQL migration ledger：每个版本必须提供 `sqlite/up.sql`、`sqlite/down.sql`、`mysql/up.sql`、`mysql/down.sql` 与 migration test。不可逆 downgrade 必须显式拒绝并给出恢复说明。
3. Migration runner 在 `schema_migrations(version,checksum,applied_at)` 记录校验和；已应用版本禁止被修改。
4. SQLite 每个连接必须执行 `PRAGMA foreign_keys=ON`；CI实际验证复合FK、CHECK、唯一约束与级联行为。MySQL 使用 InnoDB，并验证字符集、JSON、索引长度和事务语义等价。
5. 部署顺序：新增表 → 部署双版本 Backend → V3前端灰度；不得先切换前端。
6. V2数据不会自动伪装成V3 Evidence。若后续迁移，必须独立ETL并标记 `source_version=v2`。
7. 首个 V3 migration 必须显式为现有 `sessions.user_id` 补真实 FK，保留 `sessions.id` 整数 PK 和字符串 `session_id` UNIQUE，不得在 SQLite/MySQL 中形成不同主键模型。
## 12. Backend Freeze Checklist

- [ ] 所有 Contract ID、Revision、状态都有真实列和约束。
- [ ] `FactEvidence` 与 `OrganEvidenceLink` 分表且不会重复计数。
- [ ] Diagnosis/RAG/Provider run 可独立审计。
- [ ] Prescription 与 Generation Task/Asset 分离。
- [ ] Feedback 持久化与 Preference 异步更新的两阶段幂等语义已验证。
- [ ] Preference immutable versions 与 current pointer optimistic concurrency 已定义。
- [ ] History由权威表查询，不重复存储。
- [ ] versioned SQL migration ledger 在 SQLite/MySQL 上验证同等约束语义。
- [ ] V3路由不硬编码用户ID，所有查询验证ownership。
- [ ] 游客 bootstrap 原子创建 user/identity，token过期后不能继续访问，Session只从Auth Context取用户。
- [ ] NormalizedFact owner二选一约束覆盖Understanding与Questionnaire，问卷不伪造Understanding revision。
- [ ] 原文、Prompt、Key、原始异常不进入普通日志。
