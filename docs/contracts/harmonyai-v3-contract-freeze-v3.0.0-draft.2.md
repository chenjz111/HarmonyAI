# HarmonyAI V3 Contract Freeze — v3.0.0-draft.2

> API：`/api/v3`
> 基线：`origin/integration/sprint4-real-input@709e4decef4e7c77ed55f5e548eec7809fc6a281`
> 状态：`PROPOSED_FOR_FREEZE`
> 输入：`harmonyai-v3-contract-freeze.md`、`harmonyai-v3-contract-review.md`
> 配套：`frontend-read-model-contract-v3.md`、`harmonyai-v3-persistence-contract.md`
> 本合同仅用于辅助音乐调养系统，不构成医学诊断或治疗建议。

## 1. Draft.2 修订结果

| Review | 修订 |
|---|---|
| BF-01 | `ToneCode` 固定为 `jiao | zhi | gong | shang | yu`；Profile 统一为 `weights + score_semantics`；补全引用类型 |
| BF-02 | 可见性拆成 Transport 与 Display 两个维度 |
| BF-03 | 新增 Understanding、用户确认/修正与 Safety Resolution |
| BF-04 | Evidence 拆成 `FactEvidence` 与 `OrganEvidenceLink`，冻结聚合算法 |
| BF-05 | 冻结 Query Builder、RAG、Qwen、Schema Validation、Rule Check 与失败矩阵 |
| BF-06 | Agent 3 只输出 `GenerationSpec`；Prompt 归 Agent 4 Provider Adapter |
| BF-07 | Agent 4 使用异步判别联合状态和完整 AudioAsset |
| BF-08 | 统一 Preference Snapshot、WeightedPreference 与 MusicRef |
| BF-09 | 由 Frontend Read Model Contract 关闭 |
| BF-10 | 由 Persistence Contract 关闭 |

上表 BF-01 的 Canonical 枚举以正文 2.1 为唯一权威；任何示例或旧文档中的 `jue` 均无效。

## 2. 通用 Contract

### 2.1 Canonical Types

| 类型 | 定义 |
|---|---|
| `ID` | 非空、有资源前缀的字符串 |
| `Timestamp` | UTC RFC 3339 |
| `Score01` | `number`，范围 `0..1`，必须附带语义 |
| `OrganCode` | `liver | heart | spleen | lung | kidney` |
| `ElementCode` | `wood | fire | earth | metal | water` |
| `ToneCode` | `jiao | zhi | gong | shang | yu` |
| `SourceType` | `document | case_summary | narrative | voice_transcript | questionnaire | user_correction` |
| `SafetyStatus` | `clear | needs_verification | confirmed_mental_health_risk | confirmed_acute_physical_risk` |
| `Severity` | `none | mild | moderate | severe | unknown` |

V3 API、数据库 Canonical 字段和 Provider-neutral 类型禁止 `jue`；当前代码的 `jiao` 保持兼容。

### 2.2 Organ / Element Profile

```json
{
  "status": "available",
  "weights": {
    "liver": 0.18,
    "heart": 0.12,
    "spleen": 0.46,
    "lung": 0.09,
    "kidney": 0.15
  },
  "score_semantics": "relative_evidence_distribution"
}
```

`status=available` 时五个键齐全、各在 `0..1`、总和为 `1 ± 0.001`。证据不足时：

```json
{"status":"insufficient","weights":null,"score_semantics":"relative_evidence_distribution"}
```

`ElementProfile` 使用相同结构，语义为 `relative_element_support`。

### 2.3 Transport 与 Display

| 维度 | 值 | 语义 |
|---|---|---|
| Transport | `CLIENT_REQUIRED` | 返回授权客户端以完成流程，不代表可展示 |
| Transport | `SERVER_INTERNAL` | 不返回普通客户端 |
| Transport | `SENSITIVE_CLIENT_INPUT` | 用户输入，可最小化回显，禁止普通日志 |
| Transport | `SENSITIVE_SERVER_INTERNAL` | 仅服务端受控保存与处理 |
| Display | `USER_VISIBLE` | 可直接展示 |
| Display | `USER_VISIBLE_SUMMARY` | 只展示脱敏友好摘要 |
| Display | `NOT_USER_VISIBLE` | 客户端可持有但不得作为正文展示 |

例如：`assessment_id` 为 `CLIENT_REQUIRED + NOT_USER_VISIBLE`；`presentation.summary` 为 `CLIENT_REQUIRED + USER_VISIBLE`；Provider Prompt 为 `SENSITIVE_SERVER_INTERNAL + NOT_USER_VISIBLE`。

### 2.4 通用 API Envelope

```json
{"ok":true,"data":{},"request_id":"req_xxx","schema_version":"harmonyai_v3.0"}
```

失败响应包含稳定 `error.code`、安全 `message`、`retryable`、`next_actions`。Provider 原始异常、Prompt、Key 不得返回客户端。

### 2.5 Shared Objects

`UserGoal`：

```json
{"primary_goal":"sleep","secondary_goal":"relaxation","custom_goal_text":null}
```

`primary_goal` 必填，`secondary_goal` 可空且不得与主目标相同；目标枚举为 `sleep | relaxation | emotion_regulation | focus | energy | stress_relief | other`。`primary_goal=other` 时 `custom_goal_text` 必填且不超过200字。

`QuestionnaireV3Submission`：

```json
{"schema_version":"questionnaire_v3.0","time_window_days":14,"answers":[{"question_id":"q01","value":2,"answer_type":"frequency_0_4"}],"started_at":"2026-08-22T08:05:00Z","completed_at":"2026-08-22T08:08:00Z"}
```

必须恰好包含发布版10题、question_id唯一、answer_type与题目定义匹配；不得包含Q19/Q20。

`Conflict`：

```json
{"conflict_id":"conf_xxx","fact_ids":["fev_1","fev_2"],"severity":"major","display_summary":"关于睡眠时长的信息存在不一致。","resolution_status":"unresolved"}
```

`MissingInformation`：

```json
{"missing_id":"miss_xxx","field_code":"sleep_duration","display_question":"最近通常能睡多久？","required_for_diagnosis":false}
```

`Degradation`：

```json
{"active":false,"reason_codes":[]}
```

`ProviderHealth`：

```json
{"status":"healthy","checked_at":"2026-08-22T08:00:00Z","capabilities":{},"safe_message":null}
```

Provider原始异常只进入受控运维日志；`safe_message` 才可映射到UI。`ProviderMetadata` 仅允许 provider/model/latency/token/attempts/error_code 等运维字段，属于 SERVER_INTERNAL。

### 2.6 全局约束

1. V3 使用独立 Schema，不原地修改 V2.1/V2.2。
2. 前端不构造 Assessment、Diagnosis、Prescription 或 Music 结果。
3. 下游只读数据库中已确认且版本匹配的上游 Snapshot。
4. Q19/Q20 只从 V3 普通问卷 UI 移除；既有后端 Safety 能力保留，V3 不宣称完成全用户风险筛查。
5. Feedback 只改变个人音乐偏好，不改变 Safety、Evidence、医学知识或五行五音映射。

---

# 3. Information Understanding Layer V3

## 3.1 职责

该层位于输入页面与 Agent 1 之间，负责 OCR/ASR/自由文本标准化、事实抽取、用户确认和版本化；不做五脏聚合、不输出辨证、不生成音乐参数。

## 3.2 Input

```json
{
  "schema_version": "understanding_v3.0",
  "session_id": "sess_xxx",
  "inputs": [
    {"source_id":"doc_xxx","source_type":"document","processing_status":"ready","text_ref":"blobtext_xxx","captured_at":"2026-08-22T08:00:00Z"},
    {"source_id":"nar_xxx","source_type":"narrative","processing_status":"ready","text":"最近睡得不好，白天没有精神。","captured_at":"2026-08-22T08:02:00Z"}
  ]
}
```

`user_id` 由 Auth Context 注入。请求日志禁止记录 `text`。

## 3.3 CaseSummary

```json
{
  "case_summary_id":"summary_xxx",
  "source_document_ids":["doc_xxx"],
  "revision":1,
  "status":"needs_confirmation",
  "title":"材料内容摘要",
  "summary":"材料中提到近期睡眠恢复不足。",
  "editable_fields":[
    {"field_id":"current_sleep","label":"睡眠情况","value":"近期睡眠恢复不足","value_type":"text","required":false}
  ],
  "warnings":["请确认材料描述的是你当前的情况。"]
}
```

## 3.4 VoiceTranscript

```json
{
  "transcript_id":"tr_xxx",
  "audio_id":"audio_xxx",
  "revision":1,
  "status":"needs_confirmation",
  "language":"zh-CN",
  "text":"最近总是睡不好。",
  "segments":[{"segment_id":"seg_1","start_ms":0,"end_ms":2100,"text":"最近总是睡不好。"}],
  "degradation":{"active":false,"reason_codes":[]}
}
```

ASR 失败必须 `status=failed` 并提供文字输入 fallback；不得返回空白“成功”。

## 3.5 NormalizedFact

```json
{
  "fact_id":"fact_xxx",
  "fact_code":"sleep_unrefreshing",
  "display_name":"睡眠后仍感疲惫",
  "category":"sleep",
  "value":{"type":"severity","value":"moderate"},
  "time_window":"past_14_days",
  "negated":false,
  "subject":"self",
  "source_refs":[{"source_id":"nar_xxx","source_type":"narrative","span_ref":"span_xxx"}],
  "confirmation_status":"unconfirmed",
  "extraction":{"method":"qwen","confidence":0.84}
}
```

`value.type` 只允许 `boolean | severity | frequency_0_4 | number | coded_text`。必须保留否定、主体、时间窗；不得补造用户未提供的信息。

## 3.6 Output 与状态

```json
{
  "schema_version":"understanding_v3.0",
  "understanding_id":"und_xxx",
  "revision":1,
  "status":"needs_confirmation",
  "case_summary":{"case_summary_id":"summary_xxx","revision":1,"status":"needs_confirmation","title":"材料内容摘要","summary":"材料中提到近期睡眠恢复不足。","editable_fields":[],"warnings":[]},
  "voice_transcripts":[],
  "normalized_facts":[],
  "source_statuses":[{"source_id":"doc_xxx","source_type":"document","status":"ready"}],
  "safety_status":"clear",
  "safety_signal_refs":[],
  "degradation":{"active":false,"reason_codes":[]}
}
```

状态：`queued | processing | needs_confirmation | confirmed | degraded | failed`。`degraded` 表示至少一个来源失败但仍有可确认来源；`failed` 表示无可用来源。

## 3.7 User Confirmation / Revision

```json
{
  "expected_revision":1,
  "decision":"confirm_with_changes",
  "changes":[
    {
      "target_type":"normalized_fact",
      "target_id":"fact_xxx",
      "field":"value",
      "old_value":{"type":"severity","value":"severe"},
      "new_value":{"type":"severity","value":"mild"},
      "reason":"用户说明实际程度较轻"
    }
  ]
}
```

```json
{
  "understanding_id":"und_xxx",
  "previous_revision":1,
  "revision":2,
  "status":"confirmed",
  "applied_changes":["chg_xxx"],
  "superseded_fact_ids":["fact_xxx"],
  "created_fact_ids":["fact_yyy"]
}
```

`decision`：`confirm | confirm_with_changes | reject_source | cannot_confirm`。采用 optimistic concurrency，revision 不匹配返回 `REVISION_CONFLICT`。修正产生新 Revision，不覆盖旧数据。默认由 Revision Service 修正事实并重新聚合，**不自动再次调用 Qwen**；只有新增原文且显式 `reprocess_requested=true` 才创建新的 Understanding run。

## 3.8 Safety Resolution

未经确认的病例/OCR/ASR/Narrative Safety signal 使状态进入 `needs_verification`。

| resolution | 处理 | 最终状态 |
|---|---|---|
| `current_self` | 确认当前本人信号 | 对应 confirmed risk |
| `past_resolved` | 标记历史；不清除其他当前信号 | 无其他信号则 clear |
| `other_person` | 标记非本人 | 无其他信号则 clear |
| `recognition_error` | 标记识别错误并审计 | 无其他信号则 clear |
| `cannot_confirm` | 保持未决 | needs_verification |

普通 Assessment Confirmation 不得解除 Safety。confirmed risk 进入 Safety Support，个性化 Prescription/Music 保持 blocked。

---

# 4. Agent 1 — Assessment V3

## 4.1 Input

```json
{
  "schema_version":"assessment_v3.0",
  "session_id":"sess_xxx",
  "understanding_ref":{"understanding_id":"und_xxx","revision":2},
  "questionnaire":{
    "schema_version":"questionnaire_v3.0",
    "time_window_days":14,
    "answers":[{"question_id":"q01","value":2,"answer_type":"frequency_0_4"}]
  },
  "user_goal":{"primary_goal":"sleep","secondary_goal":"relaxation","custom_goal_text":null}
}
```

无病例流程必须有已确认 Narrative/Voice 之一和10题问卷；有病例流程必须有已确认 CaseSummary，Narrative和问卷可选。Backend 从 Understanding Revision 读取事实，客户端不得提交事实数组。

## 4.2 FactEvidence

```json
{
  "fact_evidence_id":"fev_xxx",
  "assessment_id":"asmt_xxx",
  "assessment_revision":1,
  "fact_id":"fact_xxx",
  "claim_code":"sleep_unrefreshing",
  "display_name":"睡眠后仍感疲惫",
  "category":"sleep",
  "value":{"type":"severity","value":"moderate"},
  "time_window":"past_14_days",
  "direction":"supporting",
  "reliability":0.84,
  "source_refs":[{"source_id":"nar_xxx","source_type":"narrative"}],
  "confirmation_status":"confirmed"
}
```

同一 Assessment Revision 中一个用户事实只生成一个 FactEvidence。`reliability` 是事实可靠度，不是医学准确率。

## 4.3 OrganEvidenceLink

```json
{
  "organ_evidence_link_id":"oel_xxx",
  "fact_evidence_id":"fev_xxx",
  "organ":"heart",
  "element":"fire",
  "direction":"supporting",
  "link_strength":0.70,
  "mapping_rule_id":"map_sleep_heart_01",
  "mapping_version":"organ_mapping_v3.0",
  "explanation_summary":"该状态可作为心相关倾向的辅助依据。"
}
```

一个 Fact 可连接多个脏；禁止复制 Fact 表示多脏关系。映射必须来自医学审核规则，Qwen 不得自由创建。

## 4.4 聚合规则

```text
signed_contribution = fact.reliability × link.link_strength × (+1 supporting / -1 contradicting)
organ_net[o] = max(0, Σ signed_contribution[o])
```

若 `Σ organ_net >= 0.20`，权重按总和归一化；否则 Profile 为 `insufficient + weights:null`。`fact_evidence_id + organ + mapping_rule_id` 唯一。

```text
evidence_coverage = 产生至少一个确认Fact的来源类别数 / 已确认可用来源类别数
source_diversity = 产生Fact的不同SourceType数量
```

Coverage 只按 Fact 计算，不按 Link 计算；两者独立保存。问卷单题不得直接决定某脏或某调式。

## 4.5 Output

```json
{
  "schema_version":"assessment_v3.0",
  "agent_id":"assessment_agent",
  "assessment_id":"asmt_xxx",
  "revision":1,
  "status":"needs_confirmation",
  "understanding_ref":{"understanding_id":"und_xxx","revision":2},
  "state_summary":"近期主要表现为思虑增多、睡眠恢复不足和精力下降。",
  "recent_context_summary":"近期压力主要与学习安排有关。",
  "organ_profile":{
    "status":"available",
    "weights":{"liver":0.18,"heart":0.12,"spleen":0.46,"lung":0.09,"kidney":0.15},
    "score_semantics":"relative_evidence_distribution"
  },
  "fact_evidence":[],
  "organ_evidence_links":[],
  "conflicts":[],
  "missing_information":[],
  "evidence_coverage":0.76,
  "evidence_coverage_semantics":"confirmed_available_source_coverage",
  "source_diversity":2,
  "requires_user_confirmation":true,
  "safety_status":"clear",
  "degradation":{"active":false,"reason_codes":[]},
  "presentation":{
    "title":"确认一下我们对你当前状态的理解",
    "summary":"近期主要表现为思虑增多、睡眠恢复不足和精力下降。",
    "body_summaries":["睡眠恢复不足","白天精力下降"],
    "recent_context":"近期压力主要与学习安排有关。",
    "goal_summary":"本次希望帮助入睡并放松紧张"
  }
}
```

`assessment_id/revision/status/safety_status` 为 `CLIENT_REQUIRED + NOT_USER_VISIBLE`；`presentation` 为用户可见；Coverage、Evidence原文与Provider metadata只在服务端。

## 4.6 Assessment Revision

确认请求与 3.7 使用同一 `expected_revision + decision + changes` 结构，`target_type=fact_evidence`。成功必须返回 `previous_revision`、新 `revision`、新 `presentation` 和 `confirmation_status`。修正后重算 Links/Profile；Diagnosis 只能读取新 Revision。普通修正默认不再次调用 Qwen。

---

# 5. Agent 2 — Diagnosis V3

## 5.1 执行链与边界

```text
Confirmed Assessment Revision
→ Diagnosis Query Builder
→ RAG Retriever
→ Qwen Diagnosis Provider
→ JSON Schema Validation（最多1次repair）
→ Medical Rule Check
→ Diagnosis Output
```

Agent 2 只输出辅助辨证倾向和五行 Profile，不输出处方或音乐。

## 5.2 Input

```json
{
  "schema_version":"diagnosis_v3.0",
  "diagnosis_id":"diag_xxx",
  "assessment_ref":{"assessment_id":"asmt_xxx","revision":2,"confirmation_status":"confirmed","safety_status":"clear"},
  "organ_profile":{"status":"available","weights":{"liver":0.18,"heart":0.12,"spleen":0.46,"lung":0.09,"kidney":0.15},"score_semantics":"relative_evidence_distribution"},
  "fact_evidence":[],
  "organ_evidence_links":[],
  "conflicts":[],
  "missing_information":[]
}
```

## 5.3 RagQuery / RagResult

```json
{
  "query_id":"qry_xxx",
  "knowledge_version":"medical_v3.0",
  "organ_codes":["heart","spleen"],
  "claim_codes":["sleep_unrefreshing","overthinking"],
  "supporting_fact_ids":["fev_1","fev_2"],
  "contradicting_fact_ids":["fev_3"],
  "top_k":5,
  "minimum_score":0.55
}
```

```text
RagRetriever.retrieve(query: RagQuery) -> RagResult
AsyncRagRetriever.retrieve(query: RagQuery) -> Awaitable[RagResult]
```

```json
{
  "retrieval_id":"rag_xxx",
  "status":"success",
  "knowledge_version":"medical_v3.0",
  "hits":[
    {
      "chunk_id":"kb_xxx",
      "source_id":"source_xxx",
      "source_title":"审核后的知识来源",
      "section":"相关章节",
      "retrieval_score":0.81,
      "text":"仅供模型使用的审核知识片段",
      "display_summary":"相关知识依据摘要",
      "review_status":"approved"
    }
  ],
  "degradation":{"active":false,"reason_codes":[]}
}
```

只有审核通过且版本匹配的 hit 可进入 Provider。

## 5.4 Qwen Provider

```text
DiagnosisProvider.complete_json(request: DiagnosisProviderRequest) -> DiagnosisProviderResponse
AsyncDiagnosisProvider.complete_json(request: DiagnosisProviderRequest) -> Awaitable[DiagnosisProviderResponse]
DiagnosisProvider.health() -> ProviderHealth
```

Request 只含脱敏 Fact、Organ Link、冲突与审核 RAG hits，不含客户端任意 Prompt。Response：

```json
{
  "status":"success",
  "candidate_tendencies":[
    {
      "syndrome_code":"heart_spleen_deficiency_tendency",
      "display_name":"心脾两虚倾向",
      "relative_support":0.73,
      "supporting_fact_ids":["fev_1","fev_2"],
      "contradicting_fact_ids":["fev_3"],
      "knowledge_chunk_ids":["kb_1"],
      "reasoning_summary":"多条已确认状态证据共同支持该倾向。"
    }
  ],
  "abstained":false,
  "abstain_reason":null
}
```

模型不得输出新事实。Schema repair 最多一次。Medical Rule Check 验证候选白名单、Evidence引用、医学映射版本、Safety gate和非诊断措辞；非法候选删除，全部删除则 abstain。

## 5.5 失败矩阵

| 情况 | 处理 | 结果 |
|---|---|---|
| Cloud Qwen失败 | 尝试已配置 Local Provider | 成功则 degraded |
| Cloud和Local都失败 | 审核本地规则；证据不足则 abstain | 不伪装Qwen成功 |
| RAG失败/为空 | 审核本地规则并标记 degradation | 足够则 degraded，否则 abstain |
| Schema首次失败 | 同Provider repair一次 | 成功继续 |
| Schema再次失败 | Provider fallback/本地规则 | 仍失败则 `MODEL_SCHEMA_INVALID` |
| 证据不足 | 停止普通推理 | `INSUFFICIENT_EVIDENCE` abstain |
| Safety非clear | 禁止普通Diagnosis | `SAFETY_BLOCKED` withheld |

## 5.6 Output

```json
{
  "schema_version":"diagnosis_v3.0",
  "agent_id":"diagnosis_agent",
  "diagnosis_id":"diag_xxx",
  "assessment_ref":{"assessment_id":"asmt_xxx","revision":2},
  "status":"success",
  "abstained":false,
  "abstain_reason":null,
  "candidate_tendencies":[],
  "primary_tendency_id":"cand_xxx",
  "element_profile":{
    "status":"available",
    "weights":{"wood":0.16,"fire":0.24,"earth":0.42,"metal":0.08,"water":0.10},
    "score_semantics":"relative_element_support"
  },
  "rag_result_ref":"rag_xxx",
  "degradation":{"active":false,"reason_codes":[]},
  "presentation":{
    "title":"辅助辨证倾向",
    "primary_tendency":"心脾两虚倾向",
    "basis_summaries":["反复思虑","睡眠恢复不足","精力下降"],
    "knowledge_references":[{"title":"审核后的知识来源","summary":"相关依据摘要"}],
    "disclaimer":"本结果仅用于音乐调养参考，不构成医学诊断。"
  }
}
```

---

# 6. Agent 3 — Prescription V3

## 6.1 Input 与边界

Agent 3 将已保存 Diagnosis、User Goal 和 Preference Snapshot 转成 Provider-neutral `GenerationSpec`，不生成 Provider Prompt。

```json
{
  "schema_version":"prescription_v3.0",
  "diagnosis_id":"diag_xxx",
  "user_goal":{"primary_goal":"sleep","secondary_goal":"relaxation","custom_goal_text":null},
  "preference_snapshot":{
    "profile_id":"pref_xxx",
    "version":4,
    "preferred_instruments":[{"code":"guqin","weight":0.8,"sample_count":6}],
    "disliked_instruments":[{"code":"sharp_dizi","weight":0.7,"sample_count":2}],
    "preferred_bpm_range":{"min":52,"max":64,"weight":0.6},
    "preferred_duration_seconds":{"value":900,"weight":0.5},
    "preferred_ambient":[{"code":"water","weight":0.7,"sample_count":4}]
  }
}
```

## 6.2 ToneProfile

```json
{
  "schema_version":"tone_profile_v3.0",
  "status":"available",
  "weights":{"jiao":0.16,"zhi":0.24,"gong":0.42,"shang":0.08,"yu":0.10},
  "dominant_tone":"gong",
  "score_semantics":"relative_tone_distribution",
  "mapping_version":"five_tone_mapping_v3.0",
  "basis":{"diagnosis_id":"diag_xxx","supporting_fact_ids":["fev_1","fev_2"]}
}
```

Preference 不得改变 Tone weights，只能影响非医学音乐参数。

## 6.3 GenerationSpec

```json
{
  "schema_version":"generation_spec_v3.0",
  "tone_profile":{"schema_version":"tone_profile_v3.0","status":"available","weights":{"jiao":0.16,"zhi":0.24,"gong":0.42,"shang":0.08,"yu":0.10},"dominant_tone":"gong","score_semantics":"relative_tone_distribution","mapping_version":"five_tone_mapping_v3.0","basis":{"diagnosis_id":"diag_xxx","supporting_fact_ids":["fev_1","fev_2"]}},
  "bpm":58,
  "duration_seconds":900,
  "instruments":["guqin","xiao"],
  "ambient_sounds":["water"],
  "structure":{"intro_seconds":60,"main_seconds":720,"outro_seconds":120},
  "energy_curve":"gentle_decline",
  "forbidden_constraints":["sharp_high_frequency"],
  "fallback_policy":{"allow_local_matching":true}
}
```

分段总和等于总时长；BPM为 `40..120`。不得包含自然语言 Prompt、Provider或厂商参数。

## 6.4 Output

```json
{
  "schema_version":"prescription_v3.0",
  "agent_id":"prescription_agent",
  "prescription_id":"rx_xxx",
  "diagnosis_id":"diag_xxx",
  "status":"success",
  "prescription_mode":"syndrome_based",
  "generation_spec":{"schema_version":"generation_spec_v3.0","tone_profile":{"schema_version":"tone_profile_v3.0","status":"available","weights":{"jiao":0.16,"zhi":0.24,"gong":0.42,"shang":0.08,"yu":0.10},"dominant_tone":"gong","score_semantics":"relative_tone_distribution","mapping_version":"five_tone_mapping_v3.0","basis":{"diagnosis_id":"diag_xxx","supporting_fact_ids":["fev_1","fev_2"]}},"bpm":58,"duration_seconds":900,"instruments":["guqin","xiao"],"ambient_sounds":["water"],"structure":{"intro_seconds":60,"main_seconds":720,"outro_seconds":120},"energy_curve":"gentle_decline","forbidden_constraints":["sharp_high_frequency"],"fallback_policy":{"allow_local_matching":true}},
  "personalization":{
    "applied":true,
    "profile_ref":{"profile_id":"pref_xxx","version":4},
    "adjustments":[{"field":"instruments","from":"dizi","to":"guqin","reason_code":"USER_PREFERENCE"}]
  },
  "presentation":{
    "title":"本次音乐生成依据",
    "tone_summary":"本次以宫音为主。",
    "parameter_summaries":["节奏较慢，适合睡前放松","采用古琴和洞箫"],
    "personalization_summary":"已参考你过去的音乐偏好。"
  }
}
```

`status=withheld` 时 `generation_spec=null`。Safety blocked、Assessment未确认或Diagnosis abstained 必须 withheld。

---

# 7. Agent 4 — Music Generation V3

## 7.1 Request 与 Provider Interface

```json
{
  "schema_version":"music_generation_v3.0",
  "request_id":"mgr_xxx",
  "prescription_id":"rx_xxx",
  "idempotency_key":"sha256:...",
  "generation_spec":{"schema_version":"generation_spec_v3.0","tone_profile":{"schema_version":"tone_profile_v3.0","status":"available","weights":{"jiao":0.16,"zhi":0.24,"gong":0.42,"shang":0.08,"yu":0.10},"dominant_tone":"gong","score_semantics":"relative_tone_distribution","mapping_version":"five_tone_mapping_v3.0","basis":{"diagnosis_id":"diag_xxx","supporting_fact_ids":["fev_1","fev_2"]}},"bpm":58,"duration_seconds":900,"instruments":["guqin","xiao"],"ambient_sounds":["water"],"structure":{"intro_seconds":60,"main_seconds":720,"outro_seconds":120},"energy_curve":"gentle_decline","forbidden_constraints":["sharp_high_frequency"],"fallback_policy":{"allow_local_matching":true}},
  "provider_policy":{"mode":"prefer_real_generation","fallback":"local_matching"}
}
```

客户端只提交 `prescription_id`。Agent 4 Adapter 将 GenerationSpec 转成 Provider-specific Prompt；Prompt 不进入普通业务表、不返回客户端。

```text
MusicGenerationProvider.create_task(request: ProviderMusicRequest) -> ProviderTask
MusicGenerationProvider.get_task(provider_task_id: string) -> ProviderTask
MusicGenerationProvider.cancel_task(provider_task_id: string) -> ProviderTask
MusicGenerationProvider.health() -> ProviderHealth
```

异步实现提供同名 async 方法。能力声明：`max_duration_seconds`、`supports_progress`、`supports_cancel`、`supported_instruments`、`supported_formats`。

`ProviderMusicRequest`：

```json
{
  "provider_request_id":"pmr_xxx",
  "generation_spec":{
    "schema_version":"generation_spec_v3.0",
    "tone_profile":{"schema_version":"tone_profile_v3.0","status":"available","weights":{"jiao":0.16,"zhi":0.24,"gong":0.42,"shang":0.08,"yu":0.10},"dominant_tone":"gong","score_semantics":"relative_tone_distribution","mapping_version":"five_tone_mapping_v3.0","basis":{"diagnosis_id":"diag_xxx","supporting_fact_ids":["fev_1","fev_2"]}},
    "bpm":58,
    "duration_seconds":900,
    "instruments":["guqin","xiao"],
    "ambient_sounds":["water"],
    "structure":{"intro_seconds":60,"main_seconds":720,"outro_seconds":120},
    "energy_curve":"gentle_decline",
    "forbidden_constraints":["sharp_high_frequency"],
    "fallback_policy":{"allow_local_matching":true}
  },
  "output_format":"mp3",
  "callback_ref":"cb_xxx"
}
```

Provider Adapter 可在内存中加入厂商Prompt/model参数，但这些字段不属于 `ProviderMusicRequest` 的持久化或公共形式。

`ProviderTask`：

```json
{"provider_task_id":"provider_task_xxx","status":"running","progress_value":50,"asset_locator":null,"error_code":null}
```

## 7.2 AudioAsset / MusicRef

```json
{
  "music_ref":{"music_id":"asset_xxx","source_type":"generated"},
  "title":"宫调·静心",
  "stream_url":"/api/v3/music/assets/asset_xxx/stream",
  "duration_seconds":900,
  "format":"mp3",
  "checksum":"sha256:...",
  "tone_profile":{"schema_version":"tone_profile_v3.0","status":"available","weights":{"jiao":0.16,"zhi":0.24,"gong":0.42,"shang":0.08,"yu":0.10},"dominant_tone":"gong","score_semantics":"relative_tone_distribution","mapping_version":"five_tone_mapping_v3.0","basis":{"diagnosis_id":"diag_xxx","supporting_fact_ids":["fev_1","fev_2"]}},
  "bpm":58,
  "instruments":["guqin","xiao"]
}
```

`source_type=generated | matched | comfort_audio`；普通个性化流程不得返回 comfort audio。

## 7.3 Response 判别联合

```json
{
  "task_id":"task_xxx",
  "status":"running",
  "progress":{"value":50,"semantics":"provider_reported_percent","indeterminate":false},
  "message":"正在生成音乐",
  "poll_after_ms":2000,
  "audio_asset":null,
  "fallback":{"applied":false,"reason_code":null}
}
```

状态：`queued | running | succeeded | matched_fallback | failed | cancelled`。

| status | progress | audio_asset | error | 约束 |
|---|---|---|---|---|
| queued | null/indeterminate | null | null | 可取消取决于Provider能力 |
| running | 可空 | null | null | 必须提供poll_after_ms |
| succeeded | 100 | 必填generated | null | 资产必须ready且可播放 |
| matched_fallback | 100 | 必填matched | null | 必须记录fallback reason |
| failed | null | null | 必填稳定error code | 不返回原始异常 |
| cancelled | null | null | null | 不得继续挂接成功资产 |

`succeeded/matched_fallback` 必须有 AudioAsset；其他状态必须为 `null`。无真实进度时 `indeterminate=true,value=null`，禁止伪造百分比。Provider失败且允许fallback时返回审核曲库匹配，状态 `matched_fallback` 且 `source_type=matched`。

---

# 8. Agent 5 — Feedback V3

## 8.1 Feedback

```json
{
  "schema_version":"feedback_v3.0",
  "session_id":"sess_xxx",
  "music_ref":{"music_id":"asset_xxx","source_type":"generated"},
  "post_state":{"change_label":"slightly_better","tension":null,"fatigue":null},
  "experience":{"overall_rating":null,"music_match_rating":null},
  "continue_use":"maybe",
  "favorite":true,
  "liked_features":["guqin_timbre","gentle_rhythm"],
  "adjustment_preferences":["slower_tempo","shorter_duration"],
  "comment":"古琴部分很舒服。",
  "playback":{"played_seconds":780,"completed":false}
}
```

只有 `post_state.change_label` 必填。互斥组：`slower_tempo/faster_tempo`、`shorter_duration/longer_duration`，前后端均验证。自由反馈禁止普通日志。

## 8.2 UserPreferenceProfile

`WeightedPreference`：

```json
{"code":"guqin","weight":0.8,"sample_count":6,"updated_at":"2026-08-22T09:00:00Z"}
```

```json
{
  "schema_version":"user_music_preference_v3.0",
  "profile_id":"pref_xxx",
  "user_id":"u_xxx",
  "version":5,
  "preferred_instruments":[],
  "disliked_instruments":[],
  "preferred_features":[],
  "disliked_features":[],
  "preferred_ambient":[],
  "preferred_bpm_range":{"min":52,"max":64,"weight":0.6},
  "preferred_duration_seconds":{"value":900,"weight":0.5},
  "favorite_music_refs":[{"music_id":"asset_xxx","source_type":"generated"}],
  "learning":{"feedback_count":7,"minimum_samples_for_application":3}
}
```

## 8.3 Output 与闭环

```json
{
  "feedback_id":"fb_xxx",
  "status":"saved",
  "preference_update":{"applied":true,"previous_version":4,"new_version":5,"changed_fields":["preferred_instruments","favorite_music_refs"]},
  "presentation":{"message":"反馈已保存，后续音乐会在安全边界内参考你的偏好。"}
}
```

只有 Profile transaction 成功才可显示“后续会参考”。下一次 Agent 3 必须读取已持久化 Profile Snapshot。低于最小样本只收集不应用；用户可撤销收藏和重置偏好。

---

# 9. 权威数据链与 API

```text
Document/OCR + Narrative + Voice/ASR
→ Understanding Revision（确认）
→ Assessment Revision（确认）
→ Diagnosis Run（RAG + Provider + Rule Check）
→ Prescription（GenerationSpec）
→ Generation Task / Music Asset
→ Feedback / Favorite / Preference Event
→ 下一次 Prescription 读取 Preference Snapshot
```

| Endpoint | 用途 |
|---|---|
| `POST /api/v3/understandings` | 创建多源理解 |
| `GET /api/v3/understandings/{id}` | 查询状态/Read Model |
| `POST /api/v3/understandings/{id}/confirmations` | 确认/修正并生成Revision |
| `POST /api/v3/assessments` | 创建Agent1 Assessment |
| `POST /api/v3/assessments/{id}/confirmations` | 确认/修正Assessment |
| `POST /api/v3/diagnoses` | 从确认Assessment创建Diagnosis |
| `POST /api/v3/prescriptions` | 从Diagnosis创建GenerationSpec |
| `POST /api/v3/music/tasks` | 创建生成任务 |
| `GET /api/v3/music/tasks/{id}` | 查询生成状态 |
| `POST /api/v3/feedback` | 保存反馈并更新Preference |
| `GET /api/v3/me/profile` | 个人主页Read Model |
| `GET /api/v3/me/music-history` | 音乐历史 |
| `GET/POST/DELETE /api/v3/me/favorites` | 收藏管理 |

所有 `user_id` 来自 Auth Context；V3 production contract 禁止硬编码 `user_id=1`。

# 10. Freeze Gate

- [ ] Owner 确认流程、Fallback 与用户措辞。
- [ ] Medical Knowledge Engineer 确认 Claim Dictionary、Organ Link、聚合阈值和五行五音映射。
- [ ] AI Engineering Lead 确认 Understanding、RAG、Provider、Schema repair 可实现。
- [ ] Backend Platform Engineer 确认 Persistence、事务、迁移和 Auth ownership。
- [ ] Client Engineer 确认 Frontend Read Model 足够，页面不读取 SERVER_INTERNAL。
- [ ] 三份合同字段、状态和版本一致。
- [ ] Final Freeze Review 结论为 `FREEZE` 后，本文状态才能改为 `FROZEN`。
