# HarmonyAI V3 Contract Freeze — v3.0.0-draft.3

> API：`/api/v3`
> 基线：`origin/integration/sprint4-real-input@08ac591c58edb611c784f673edf61b134b9aedbb`
> 状态：`PROPOSED_FOR_FINAL_REVIEW`
> 输入：draft.2、首次 Contract Review、PR #74 医学/前端审查、Owner 授权的 Backend/AI 临时代审
> 配套：`frontend-read-model-contract-v3.md`、`harmonyai-v3-persistence-contract.md`
> 本合同仅用于辅助音乐调养系统，不构成医学诊断或治疗建议。

## 1. Draft.3 修订结果与权威决策

| Review finding | Draft.3 权威处理 |
|---|---|
| BF-01 Canonical类型冲突 | 冻结 `ToneCode=jiao|zhi|gong|shang|yu` 与带 `weights/score_semantics` 的 Organ/Element/Tone Profile |
| BF-02 可见性混用 | 将 Transport 与 Display 分离；ID可传输但不可展示，Provider/医学内部数据不下发 |
| BF-03 Understanding/修正/Safety未闭合 | 冻结 Understanding Provider、完整Revision、专用Safety Resolution与普通确认不可清除Safety |
| BF-04 Evidence/聚合未冻结 | 拆分 FactEvidence 与 OrganEvidenceLink；聚合只使用批准的 Claim/Mapping Manifest，按Fact去重 |
| BF-05 RAG+Qwen不可实现 | 冻结 Query Builder→Retriever→Diagnosis Provider→Schema Validation→Rule Check，以及失败矩阵 |
| BF-06 Agent3/4 Prompt重叠 | Agent3只产出Provider-neutral GenerationSpec；Provider Prompt只在Agent4 Adapter内部生成 |
| BF-07 异步音乐状态不足 | 冻结Music Task判别联合、轮询/取消、AudioAsset、授权stream与matched fallback |
| BF-08 偏好Schema不一致 | 冻结不可变Preference Snapshot；Agent3只读取达到样本阈值的已持久化版本 |
| BF-09 PUBLIC字段不足 | 配套Frontend Read Model覆盖入口、摘要、问卷、确认、安全、生成、播放器、反馈与个人页 |
| BF-10 身份/持久化未冻结 | 配套Persistence Contract冻结AuthPrincipal、V2 PK兼容、Revision Snapshot、事务与Migration |
| 问卷提交/渲染不一致 | 冻结 `QuestionnaireSchemaV3`、判别联合答案、`QuestionnaireFactAdapter` 与 Schema API；医学题目内容使用独立签名 Manifest |
| 7天/14天冲突 | V3统一为 `past_7_days` / `time_window_days=7`；不重写V2时间窗 |
| Claim Dictionary缺失 | 冻结 `ClaimDictionaryV3` 格式、引用与版本规则；最终医学条目必须由 Medical Review批准后才能标记FROZEN |
| RAG不可复现 | 新增 KnowledgeChunk、Ingestion Manifest、Embedding/Index版本、审核过滤和分数语义 |
| Diagnosis状态歧义 | 新增 Provider完整Schema及 `success/degraded/abstained/withheld/failed` 判别约束 |
| API/幂等/事务未闭合 | 冻结Idempotency-Key、恢复查询、上传/取消/流接口及Feedback两阶段事务语义 |
| V3 Eval缺失 | 新增AI Contract Gate与最小固定评测集要求，不沿用emotion_f1作为V3唯一Gate |
Canonical 枚举以正文2.1为唯一权威；任何示例或旧文档中的 `jue` 均无效。`knowledge-architecture.md` 与 `prompt-architecture.md` 的V0.1旧情绪链和“Agent3组装Provider Prompt”仅作历史资料，V3由本文覆盖。
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
| `SafetyStatus` | `clear | needs_verification | resolved | confirmed_mental_health_risk | confirmed_acute_physical_risk` |
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

`AuthPrincipal` 只由认证依赖注入，客户端提交同名字段一律忽略：

```json
{
  "internal_user_pk": 42,
  "public_user_id": "u_xxx",
  "auth_type": "registered",
  "guest_expires_at": null
}
```

`auth_type=registered | guest`。数据库外键使用 `internal_user_pk: integer`；API只返回 `public_user_id`。游客必须先创建受控用户行并具有到期策略，不得退回 `user_id=1`。未认证为401；已认证但读取他人资源统一返回404以避免资源枚举；无权执行本用户操作返回403。

V3 比赛版在没有完整注册系统时使用最小游客启动合同。客户端先调用 `POST /api/v3/auth/guest`，服务端原子创建受控 guest user/identity，并返回：

```json
{
  "access_token":"opaque-or-signed-token",
  "token_type":"Bearer",
  "expires_at":"2026-08-23T08:00:00Z",
  "public_user_id":"u_guest_xxx"
}
```

`access_token` 属于 `SENSITIVE_CLIENT_INPUT + NOT_USER_VISIBLE`，只允许安全存储和 Authorization Header 传输。后续 `POST /api/v3/sessions` 必须从 Auth Context 取得用户；不得接受客户端 `user_id`。完整注册/登录可以后续扩展，但不得用固定用户替代游客身份。

`UserGoal`：

```json
{"primary_goal":"sleep","secondary_goal":"relaxation","custom_goal_text":null}
```

`primary_goal`必填，`secondary_goal`可空且不得与主目标相同；枚举为 `sleep | relaxation | emotion_regulation | focus | energy | stress_relief | other`。`primary_goal=other`时 `custom_goal_text`必填且不超过200字。UserGoal在问卷外的音乐目标步骤采集。

#### QuestionnaireSchemaV3

问卷内容由独立、医学审核、带checksum的Manifest提供，API与前端不得硬编码题目：

```json
{
  "schema_id":"questionnaire_v3",
  "schema_version":"3.0.0",
  "manifest_version":"medical_v3.0",
  "time_window":"past_7_days",
  "time_window_days":7,
  "question_count":10,
  "questions":[
    {
      "question_id":"q01",
      "position":1,
      "prompt":"审核后的题目文案",
      "answer_type":"multi_choice_evidence",
      "required":true,
      "min_selections":1,
      "max_selections":5,
      "options":[
        {"option_code":"flank_discomfort","label":"胁肋部不适","claim_code":"flank_discomfort","is_none":false,"exclusive_with":[]},
        {"option_code":"none","label":"无以上情况","claim_code":null,"is_none":true,"exclusive_with":["*"]}
      ]
    }
  ],
  "claim_dictionary_version":"medical_v3.0",
  "content_checksum":"sha256:...",
  "review_status":"approved"
}
```

`answer_type`只允许 `multi_choice_evidence | single_choice_evidence | frequency_0_4`。发布Manifest必须恰好10题、ID为q01..q10且唯一；所有非none选项必须引用同版本Claim Dictionary。`none`与同题所有其他选项互斥。题目文案、选项和医学映射只有 `review_status=approved` 才可由 `GET /api/v3/questionnaire/schema` 返回。Draft.3不替医学负责人创造题目内容；上方题目/选项仅演示Schema形状，不是生产医学内容。最终Freeze必须附上已批准Manifest及checksum。所有示例 claim、mapping rule、threshold 同样不代表医学批准。

`QuestionnaireV3Submission`：

```json
{
  "questionnaire_submission_id":"qsub_xxx",
  "schema_id":"questionnaire_v3",
  "schema_version":"3.0.0",
  "manifest_version":"medical_v3.0",
  "content_checksum":"sha256:...",
  "time_window_days":7,
  "answers":[
    {"question_id":"q01","answer_type":"multi_choice_evidence","value":["flank_discomfort"]}
  ],
  "started_at":"2026-08-22T08:05:00Z",
  "completed_at":"2026-08-22T08:08:00Z"
}
```

答案是以 `answer_type` 判别的联合：multi为 `list[string]`、single为 `string`、frequency为 `integer 0..4`。提交必须与服务端保存的Manifest版本和checksum一致；不一致返回 `QUESTIONNAIRE_SCHEMA_STALE`，客户端刷新后由用户确认，不得静默改写答案。V3问卷不包含V2的Q19/Q20。

`ClaimDictionaryV3`条目：

```json
{
  "claim_code":"flank_discomfort",
  "display_name":"胁肋部不适",
  "category":"physical_signal",
  "value_type":"boolean",
  "allowed_values":[true,false],
  "questionnaire_option_refs":["q01:flank_discomfort"],
  "organ_mapping_allowed":true,
  "medical_review":{"status":"approved","review_version":"medical_v3.0"}
}
```

Claim Dictionary是Questionnaire、Understanding、Agent1和RAG的单一代码来源。未收录或未批准的claim不得进入Organ mapping或RAG query。Claim条目只定义事实语义，不直接决定脏腑或调式。

`QuestionnaireFactAdapter` 为确定性组件：验证Submission后，每个非none选择生成一个Canonical `NormalizedFact`，并设置 `source_type=questionnaire`、`source_id=questionnaire_submission_id`、`time_window=past_7_days`、`confirmation_status=confirmed`、`extraction.method=deterministic_questionnaire_mapping`。none不生成阳性Fact，但保留Submission快照。问卷 Fact 以 `questionnaire_submission_id` 作为权威 owner，不伪造 Understanding revision；所有来源之后统一进入 `Fact → FactEvidence → OrganEvidenceLink`。

`Conflict`：

```json
{"conflict_id":"conf_xxx","fact_ids":["fact_1","fact_2"],"severity":"major","display_summary":"关于睡眠时长的信息存在不一致。","resolution_status":"unresolved"}
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
{
  "status":"healthy",
  "provider_kind":"cloud",
  "provider":"qwen",
  "model":"qwen-plus",
  "checked_at":"2026-08-22T08:00:00Z",
  "capabilities":{"structured_json":true,"max_input_characters":12000},
  "safe_message":null
}
```

`status=configured | healthy | degraded | down | not_configured`。Provider原始异常只进入受控运维日志；`safe_message`才可映射到UI。`ProviderMetadata`只允许provider/model/latency/token/attempts/error_code/prompt_version/schema_version等运维字段，属于SERVER_INTERNAL。
### 2.6 全局约束

1. V3 使用独立 Schema，不原地修改 V2.1/V2.2。
2. 前端不构造 Assessment、Diagnosis、Prescription 或 Music 结果。
3. 下游只读数据库中已确认且版本匹配的上游 Snapshot。
4. V3使用全新10题五脏问卷，不含V2安全题Q19/Q20；既有后端Safety能力保留。V3风险信号来自病例/OCR、Narrative和ASR Transcript的确定性Safety Detector，系统不得宣称完成全用户风险筛查。
5. Feedback只改变个人音乐偏好，不改变Safety、Evidence、医学知识或五行五音映射。
6. 未通过医学审核的Questionnaire Manifest、Claim Dictionary、Organ Mapping和Knowledge Chunk不得进入production Provider。
7. 旧V2数据不得通过字段重命名伪装为V3 Evidence；V3所有跨层引用都带schema/mapping/knowledge版本。

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

### 3.2.1 固定处理顺序

```text
Source MIME/size validation
→ OCR/ASR（如适用）
→ Deterministic Safety Detector
→ source/subject/time-window normalization
→ Cloud Understanding Provider
→ Local Understanding Provider
→ deterministic/questionnaire-only fallback
→ Schema Validation
→ dedup/conflict detection
→ user confirmation
```

Safety Detector独立于Qwen可用性并先执行；Provider不得降低或清除已识别的Safety signal。资料中的命令、Prompt或系统指令只作为用户资料，不得改变Provider任务。

### 3.2.2 Understanding Provider Contract

```json
{
  "request_id":"upr_xxx",
  "schema_version":"understanding_provider_v3.0",
  "prompt_version":"understanding_prompt_v3.0",
  "source":{
    "source_id":"nar_xxx",
    "source_type":"narrative",
    "subject_hint":"self",
    "time_window":"past_7_days",
    "text":"经过长度限制和最小化后的用户文本"
  },
  "allowed_claim_dictionary_version":"medical_v3.0",
  "max_facts":30
}
```

```json
{
  "status":"success",
  "facts":[
    {
      "claim_code":"sleep_unrefreshing",
      "display_name":"睡眠后仍感疲惫",
      "category":"sleep",
      "value":{"type":"severity","value":"moderate"},
      "time_window":"past_7_days",
      "negated":false,
      "subject":"self",
      "span":{"start":0,"end":8},
      "extraction_confidence":0.84
    }
  ],
  "warnings":[]
}
```

```text
UnderstandingProvider.complete_json(request: UnderstandingProviderRequest)
  -> UnderstandingProviderResponse
AsyncUnderstandingProvider.complete_json(request: UnderstandingProviderRequest)
  -> Awaitable[UnderstandingProviderResponse]
```

Provider输出 `extra=forbid`；claim_code必须存在于请求声明的已批准Claim Dictionary；span必须落在输入范围内；Provider不得输出organ、element、tone、diagnosis或新事实。单来源最大12000 Unicode字符，超长资料按页/段切块，每块保留source/span；不得静默截断。

### 3.2.3 Speech Recognition Provider

```text
SpeechRecognitionProvider.create_task(audio_ref) -> AsrTask
SpeechRecognitionProvider.get_task(task_id) -> AsrTask
```

`AsrTask.status=queued | running | succeeded | failed`；成功必须返回带segment时间戳的VoiceTranscript；失败返回稳定error code和文字输入fallback。用户修正Transcript后创建新revision，再对已确认文本运行Understanding；不得把空转写标记为成功。

### 3.2.4 Understanding Fallback Matrix

| 情况 | 处理 | 输出 |
|---|---|---|
| Cloud成功 | Schema验证并继续 | success |
| Cloud timeout/429/5xx | 尝试Local | Local成功则degraded |
| Cloud 401/403/配置错误 | 不重试Cloud；尝试Local | Local成功则degraded |
| Cloud/Local都失败 | 保留确定性问卷Fact和已确认来源摘要 | degraded；没有可用Fact则failed |
| Provider invalid JSON/Schema | 同Provider只允许一次repair；再失败切换下一Provider | 不伪装success |
| ASR失败 | 提供文字输入/跳过语音 | 其他来源可继续degraded |
| Safety非clear | 停止普通Assessment/Diagnosis | needs_verification或confirmed risk |

Repair是一次独立Provider call，计入attempts和总超时；不得把原始错误响应写入普通日志。
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
  "time_window":"past_7_days",
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
  "affected_fact_ids":["fact_xxx"]
}
```

`decision`：`confirm | confirm_with_changes | reject_source | cannot_confirm`。采用optimistic concurrency，revision不匹配返回 `REVISION_CONFLICT`。修正产生新Revision，不覆盖旧数据；每个Revision保存完整物化CaseSummary、Source状态和Fact集合。逻辑 `fact_id` 跨Revision保持稳定，每个Revision创建新的内部 `fact_row_id`，变化行通过 `supersedes_fact_row_id` 关联；内部 row ID 不返回前端。默认由Revision Service修正事实并重新聚合，**不自动再次调用Qwen**；只有新增原文且显式 `reprocess_requested=true` 才创建新的Understanding run。

## 3.8 Safety Resolution

未经确认的病例/OCR/ASR/Narrative Safety signal 使状态进入 `needs_verification`。

| resolution | 处理 | 最终状态 |
|---|---|---|
| `current_self` | 确认当前本人信号 | 对应 confirmed risk |
| `past_resolved` | 标记历史；不清除其他当前信号 | 无其他信号则 resolved |
| `other_person` | 标记非本人 | 无其他信号则 resolved |
| `recognition_error` | 标记识别错误并审计 | 无其他信号则 resolved |
| `cannot_confirm` | 保持未决 | needs_verification |

普通 Assessment Confirmation 不得解除 Safety。`clear | resolved` 进入正常音乐轨；confirmed risk 进入 Safety Support，个性化 Prescription/Music 保持 blocked。

---

# 4. Agent 1 — Assessment V3

## 4.1 Input

```json
{
  "schema_version":"assessment_v3.0",
  "session_id":"sess_xxx",
  "understanding_ref":{"understanding_id":"und_xxx","revision":2},
  "questionnaire_ref":{
    "questionnaire_submission_id":"qsub_xxx",
    "schema_id":"questionnaire_v3",
    "schema_version":"3.0.0",
    "manifest_version":"medical_v3.0",
    "content_checksum":"sha256:..."
  },
  "user_goal":{"primary_goal":"sleep","secondary_goal":"relaxation","custom_goal_text":null}
}
```

Backend只接受资源引用并从数据库读取已确认Snapshot；客户端不得重复提交NormalizedFact、Questionnaire answers或Evidence数组。`questionnaire_ref` 类型为对象或 `null`：无病例流程必须有已确认Narrative/Voice之一和已验证10题问卷；有病例流程必须有已确认CaseSummary，Narrative和问卷可选。

在聚合前，`QuestionnaireFactAdapter`把问卷选择转换为以 `questionnaire_submission_id` 为owner的Canonical Fact，与Understanding confirmed facts合并。合并顺序固定为：subject/time-window过滤 → claim_code规范化 → 同来源去重 → 跨来源Conflict标记 → FactEvidence生成。问卷Fact不允许绕过Claim Dictionary，也不能由单题直接决定某脏或某调式。
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
  "time_window":"past_7_days",
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
  "organ":"liver",
  "element":"wood",
  "direction":"supporting",
  "link_strength":0.70,
  "mapping_rule_id":"map_flank_discomfort_liver_01",
  "mapping_version":"organ_mapping_v3.0",
  "explanation_summary":"该状态可作为肝相关倾向的辅助依据。"
}
```

一个 Fact 可连接多个脏；禁止复制 Fact 表示多脏关系。映射必须来自医学审核规则，Qwen 不得自由创建。

## 4.4 聚合规则

`OrganMappingManifest`是医学审核资产，至少包含 `mapping_version`、`claim_code`、一个或多个organ link、direction、link_strength、组合规则、`minimum_total_support`、review_status和checksum。未批准Manifest不得聚合；多脏相关事实使用多个Link，不复制Fact。

```text
signed_contribution = fact.reliability × link.link_strength × (+1 supporting / -1 contradicting)
organ_net[o] = max(0, Σ signed_contribution[o])
total_support = Σ organ_net[o]
```

只有当Manifest为approved且 `total_support >= manifest.minimum_total_support` 时，权重才按总和归一化；否则Profile为 `insufficient + weights:null`。阈值不得在Agent代码中写死，变更阈值必须产生新的mapping_version并重跑固定评测集。`fact_evidence_id + organ + mapping_rule_id`唯一。

```text
evidence_coverage = 产生至少一个确认Fact的来源类别数 / 已确认可用来源类别数
source_diversity = 产生Fact的不同SourceType数量
```

Coverage只按Fact计算，不按Link计算；两者独立保存。skipped/failed/unconfirmed来源不进入分母。问卷单题不得直接决定某脏或某调式；睡眠、乏力等多脏事实必须按审核组合规则产生多个Link。
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

确认请求与3.7使用同一 `expected_revision + decision + changes` 结构，`target_type=fact_evidence`。成功必须返回 `previous_revision`、新 `revision`、新 `presentation` 和 `confirmation_status`。每个Revision是完整物化Snapshot：逻辑 `fact_evidence_id` 保持稳定，每个Revision创建新的内部 Evidence row并用 `supersedes_evidence_row_id` 关联；旧Revision及其Fact/Link禁止UPDATE。写入新Revision、重算Links/Profile和更新current_revision必须在同一事务。Diagnosis只能读取新Revision。普通修正默认不再次调用Qwen。

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

## 5.2.1 RAG Knowledge / Ingestion Contract

```json
{
  "chunk_id":"kb_xxx",
  "source_id":"source_xxx",
  "source_title":"审核后的知识来源",
  "section":"相关章节",
  "text":"仅供检索与模型使用的审核知识片段",
  "display_summary":"可展示的依据摘要",
  "claim_codes":["sleep_unrefreshing"],
  "organ_codes":["heart","spleen"],
  "review_status":"approved",
  "medical_review_version":"medical_v3.0",
  "knowledge_version":"medical_v3.0",
  "content_checksum":"sha256:..."
}
```

Ingestion Manifest：

```json
{
  "knowledge_version":"medical_v3.0",
  "embedding_provider":"approved_embedding_provider",
  "embedding_model":"model_name",
  "embedding_version":"embedding_v1",
  "distance_metric":"cosine",
  "retrieval_score_semantics":"one_minus_cosine_distance",
  "minimum_score":0.55,
  "chunk_count":128,
  "manifest_checksum":"sha256:...",
  "review_status":"approved"
}
```

示例中的 `minimum_score=0.55` 仅表达字段类型，不是已批准阈值。生产值必须由医学/AI Review写入已批准Manifest。阈值与 `embedding_version + distance_metric + score_semantics` 绑定；更换embedding必须创建新Manifest并重跑RAG eval，禁止跨索引沿用裸阈值。检索前必须过滤 `review_status=approved` 和请求的knowledge_version。当前 `hash-v1` Chroma demo store只允许test/offline skeleton，不得标记production RAG success。
## 5.3 RagQuery / RagResult

```json
{
  "query_id":"qry_xxx",
  "knowledge_version":"medical_v3.0",
  "ingestion_manifest_checksum":"sha256:...",
  "organ_codes":["heart","spleen"],
  "claim_codes":["sleep_unrefreshing","overthinking"],
  "supporting_fact_ids":["fev_1","fev_2"],
  "contradicting_fact_ids":["fev_3"],
  "top_k":5
}
```

Query Builder只使用已确认FactEvidence、Organ Link和Claim Dictionary code；不得拼接用户原文作为任意检索指令。minimum_score从已批准Ingestion Manifest读取，客户端和Agent不得提交。

```text
RagRetriever.retrieve(query: RagQuery) -> RagResult
AsyncRagRetriever.retrieve(query: RagQuery) -> Awaitable[RagResult]
```

```json
{
  "retrieval_id":"rag_xxx",
  "status":"success",
  "knowledge_version":"medical_v3.0",
  "embedding_version":"embedding_v1",
  "retrieval_score_semantics":"one_minus_cosine_distance",
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

`status=success | empty | degraded | failed`。只有审核通过、knowledge_version和Manifest checksum匹配且达到该Manifest阈值的hit可进入Provider；其余hit丢弃并记录内部reason code。empty不是success，也不得伪造本地知识命中。
## 5.4 Qwen Diagnosis Provider

`DiagnosisProviderRequest`：

```json
{
  "request_id":"dpr_xxx",
  "schema_version":"diagnosis_provider_v3.0",
  "response_schema_version":"diagnosis_provider_response_v3.0",
  "prompt_version":"diagnosis_prompt_v3.0",
  "assessment_ref":{"assessment_id":"asmt_xxx","revision":2},
  "organ_profile":{"status":"available","weights":{"liver":0.18,"heart":0.12,"spleen":0.46,"lung":0.09,"kidney":0.15},"score_semantics":"relative_evidence_distribution"},
  "facts":[
    {"fact_evidence_id":"fev_1","claim_code":"sleep_unrefreshing","value":{"type":"severity","value":"moderate"},"direction":"supporting","time_window":"past_7_days"}
  ],
  "conflicts":[],
  "missing_information":[],
  "rag":{"retrieval_id":"rag_xxx","knowledge_version":"medical_v3.0","chunk_ids":["kb_1"]},
  "allowed_syndrome_codes":["heart_spleen_deficiency_tendency"],
  "max_candidates":3
}
```

Request只含脱敏Fact、冲突摘要和审核RAG hit引用；不得包含客户端任意Prompt、用户身份、Provider Key或未审核知识。

```text
DiagnosisProvider.complete_json(request: DiagnosisProviderRequest)
  -> DiagnosisProviderResponse
AsyncDiagnosisProvider.complete_json(request: DiagnosisProviderRequest)
  -> Awaitable[DiagnosisProviderResponse]
DiagnosisProvider.health() -> ProviderHealth
```

`DiagnosisProviderResponse`：

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

Response使用 `extra=forbid`，候选0..3个，syndrome_code必须在请求白名单；relative_support为0..1辅助支持度，不要求候选总和为1，也不是医学准确率。所有Fact/Chunk ID必须来自Request，模型不得输出新事实。重复syndrome_code去重；Schema Validation、ID Validation、Contradiction Check和Medical Rule Check后若无合法候选，结果必须abstain。

Provider Route Policy：Cloud Qwen为首选，Local Qwen为第二级，审核本地规则为最后一级。单次Diagnosis总预算60秒；每个Provider网络retry最多2次；Schema repair最多1次且计入attempts和总预算。401/403/NOT_CONFIGURED不重试同Provider；429/timeout/5xx按退避策略重试后切换。普通日志只记录hash、版本、耗时、token、attempts和稳定error code。
## 5.5 失败矩阵

| 情况 | 处理 | 最终状态 |
|---|---|---|
| Safety非`clear | resolved` / Assessment未确认 | 不调用RAG或Provider | `withheld`, abstained=false |
| 证据不足 / OrganProfile insufficient | 不调用普通推理 | `abstained`, reason=`INSUFFICIENT_EVIDENCE` |
| Cloud Qwen失败，Local成功 | 继续Schema/Rule Check | `degraded`, degradation含Cloud error |
| Cloud和Local都失败，本地规则有足够证据 | 规则候选必须引用Fact和mapping版本 | `degraded` |
| Cloud和Local都失败，本地规则证据不足 | 不生成候选 | `abstained`, reason=`PROVIDERS_UNAVAILABLE` |
| RAG失败/为空，本地审核规则足够 | 继续但不得伪装RAG命中 | `degraded` |
| RAG失败/为空且规则不足 | 不生成候选 | `abstained`, reason=`KNOWLEDGE_UNAVAILABLE` |
| Schema首次失败 | 同Provider repair一次 | 成功后继续，记录repair |
| Schema再次失败 | 切换下一Provider/规则 | 仍失败为`failed`, code=`MODEL_SCHEMA_INVALID` |
| 全部候选被Rule Check删除 | 不保留非法候选 | `abstained`, reason=`NO_VALID_CANDIDATE` |

状态是判别语义：`success/degraded`必须 `abstained=false` 且至少一个合法候选；`abstained`必须 `abstained=true`、candidate_tendencies=[]、element_profile insufficient；`withheld`只用于Safety或上游未确认；`failed`只用于系统无法产生有效业务结果且没有安全fallback。禁止 `status=success + abstained=true`。
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
  "candidate_tendencies":[{"candidate_id":"cand_xxx","syndrome_code":"heart_spleen_deficiency_tendency","display_name":"心脾两虚倾向","relative_support":0.73,"supporting_fact_ids":["fev_1","fev_2"],"contradicting_fact_ids":[],"knowledge_chunk_ids":["kb_1"],"reasoning_summary":"多条已确认状态证据共同支持该倾向。"}],
  "primary_tendency_id":"cand_xxx",
  "element_profile":{
    "status":"available",
    "weights":{"wood":0.16,"fire":0.24,"earth":0.42,"metal":0.08,"water":0.10},
    "score_semantics":"relative_element_support"
  },
  "rag_result_ref":"rag_xxx",
  "execution_versions":{"prompt_version":"diagnosis_prompt_v3.0","response_schema_version":"diagnosis_provider_response_v3.0","knowledge_version":"medical_v3.0","mapping_version":"organ_mapping_v3.0"},
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


`execution_versions`与ProviderMetadata属于SERVER_INTERNAL，不在普通页面展示。输出必须满足5.5判别约束。
---

# 6. Agent 3 — Prescription V3

## 6.1 Input 与边界

Agent 3 将已保存 Diagnosis、其关联的已确认 Assessment、User Goal 和 Preference Snapshot 转成 Provider-neutral `GenerationSpec`，不生成 Provider Prompt。处方模式沿用已批准 ADR-0007：`syndrome_based | candidate_blend | emotion_based | wellness`。

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

`ToneProfile.status=available | fallback | insufficient`。`syndrome_based/candidate_blend` 使用审核后的证型→五行→五音映射，状态为 `available`。Diagnosis abstained 但 Safety 为 `clear | resolved`、Assessment 已确认且信息充分时，Agent 3 必须进入 `emotion_based` 或 `wellness`，状态为 `fallback`；此时 tone weights 只来自版本化、审核后的非诊断 fallback policy，`mapping_version` 必须标识 fallback 版本，页面不得把它表达为辨证结论。`insufficient` 仅用于完全没有有效状态数据，且不得伪造 weights。

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

`status=withheld` 时 `generation_spec=null`。只有 Safety 非 `clear | resolved`、Assessment未确认、完全没有有效状态数据，或上游权威资源缺失时才 withheld。Diagnosis abstained **不等于**无音乐：若安全且Assessment信息充分，必须按 ADR-0007 生成 `emotion_based` / `wellness` 的保守 `GenerationSpec`；前端不得自行选择模式或构造处方。

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
  "pre_state_snapshot":{"snapshot_id":"qs_xxx","source":"player_session","captured_at":"2026-08-22T08:45:00Z","tension":6,"fatigue":7},
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
  "public_user_id":"u_xxx",
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
Document/OCR + Narrative + Voice/ASR → Understanding Revision（确认）
Questionnaire Submission → QuestionnaireFactAdapter → Questionnaire-owned Canonical Facts
UserGoal + confirmed Understanding + optional/required Questionnaire Facts
→ Assessment Revision（确认）
→ Diagnosis Run（RAG + Provider + Rule Check）
→ Prescription（GenerationSpec + immutable Preference Snapshot ref）
→ Generation Task / Music Asset
→ Feedback / Favorite
→ Preference Event / immutable Preference Version
→ 下一次Prescription读取最新可应用Preference Snapshot
```

## 9.1 API与Schema绑定

| Endpoint | Request / Response | 用途 |
|---|---|---|
| `POST /api/v3/auth/guest` | — → GuestAuthResponse | 创建受控游客身份；返回短期Bearer token |
| `POST /api/v3/sessions` | Entry request → EntryReadModel | 以Auth Context创建业务会话 |
| `POST /api/v3/documents` | multipart → SourceStatusReadModel | 上传JPG/PNG/PDF，返回document_id |
| `GET /api/v3/documents/{id}` | — → SourceStatusReadModel | 查询OCR/材料状态 |
| `POST /api/v3/audio/tasks` | multipart → AsrTask | 创建语音转写任务 |
| `GET /api/v3/audio/tasks/{id}` | — → AsrTask | 查询ASR状态 |
| `GET /api/v3/questionnaire/schema` | version可选 → QuestionnaireSchemaV3 | 获取审核问卷Manifest |
| `POST /api/v3/questionnaire/submissions` | QuestionnaireV3Submission → submission ref | 验证并保存问卷 |
| `POST /api/v3/understandings` | UnderstandingV3Request → UnderstandingV3Response | 创建多源理解 |
| `GET /api/v3/understandings/{id}` | revision可选 → Understanding Read Model | 查询/恢复状态 |
| `POST /api/v3/understandings/{id}/confirmations` | expected_revision + decision + changes → new revision | 确认/修正 |
| `POST /api/v3/understandings/{id}/safety-resolutions` | pending signal resolutions → Safety Read Model | 专用Safety确认 |
| `POST /api/v3/assessments` | AssessmentV3Request → AssessmentV3Response | 创建Agent1结果 |
| `GET /api/v3/assessments/{id}` | revision可选 → Assessment Read Model | 查询/恢复确认页 |
| `POST /api/v3/assessments/{id}/confirmations` | expected_revision + changes → new revision | 确认/修正Assessment |
| `POST /api/v3/diagnoses` | assessment_ref → DiagnosisV3 | 创建Agent2运行 |
| `GET /api/v3/diagnoses/{id}` | — → DiagnosisV3/Read Model | 查询结果 |
| `POST /api/v3/prescriptions` | diagnosis_id → PrescriptionV3 | 创建GenerationSpec |
| `GET /api/v3/prescriptions/{id}` | — → Prescription Read Model | 查询生成依据 |
| `POST /api/v3/music/tasks` | prescription_id → MusicTask | 创建生成任务 |
| `GET /api/v3/music/tasks/{id}` | — → MusicTask union | 查询生成状态 |
| `POST /api/v3/music/tasks/{id}/cancel` | — → MusicTask union | 尝试取消 |
| `GET /api/v3/music/assets/{id}/stream` | Range header → audio stream | 授权播放，不返回storage key |
| `POST /api/v3/feedback` | FeedbackV3 → FeedbackV3Output | 保存反馈并尝试更新偏好 |
| `GET/PATCH /api/v3/me/profile` | Profile patch / Read Model | 个人主页 |
| `POST /api/v3/me/preferences/reset` | expected_version → new version | 重置个人音乐偏好 |
| `GET /api/v3/me/music-history` | cursor/limit → paged items | 历史记录 |
| `GET/POST/DELETE /api/v3/me/favorites` | music_ref → paged/updated state | 收藏管理 |

Provider callback只允许受签名验证的内部路由，例如 `POST /internal/v3/music/providers/{provider}/callbacks`；不得暴露给普通客户端。

## 9.2 Idempotency与并发

所有产生新资源或副作用的POST必须接受 `Idempotency-Key`，服务端按 `(internal_user_pk, endpoint_scope, idempotency_key)` 唯一，并对重复请求返回第一次的同一资源/响应。Confirmation/Safety Resolution还必须校验expected_revision。缺失幂等键返回 `IDEMPOTENCY_KEY_REQUIRED`；相同key不同payload返回 `IDEMPOTENCY_KEY_REUSED`。

Feedback采用明确的两阶段语义：

1. 事务A原子保存Feedback、收藏关系和幂等结果；
2. 事务B用expected profile version更新Preference Event、不可变Preference Version和current profile，冲突最多重试3次；
3. 事务B失败不回滚已保存Feedback，响应 `preference_update.applied=false` 并创建同feedback_id的幂等重试任务；重试不得再次增加feedback_count或重复学习。

## 9.3 Ownership与错误

所有资源查询先按AuthPrincipal限制user scope。未认证401；跨用户资源统一404；本用户无权执行的动作403。客户端提交user_id不参与授权。

稳定错误至少包括：`UNAUTHENTICATED`、`FORBIDDEN`、`RESOURCE_NOT_FOUND`、`REVISION_CONFLICT`、`IDEMPOTENCY_KEY_REQUIRED`、`IDEMPOTENCY_KEY_REUSED`、`QUESTIONNAIRE_SCHEMA_STALE`、`CLAIM_DICTIONARY_UNAVAILABLE`、`SAFETY_BLOCKED`、`INSUFFICIENT_EVIDENCE`、`RAG_UNAVAILABLE`、`PROVIDER_NOT_CONFIGURED`、`PROVIDER_AUTH_FAILED`、`PROVIDER_RATE_LIMITED`、`PROVIDER_TIMEOUT`、`MODEL_SCHEMA_INVALID`、`PREFERENCE_VERSION_CONFLICT`和`NO_PLAYABLE_ASSET`。Provider原始错误不得进入客户端。

所有 `user_id` 来自Auth Context；V3 production contract禁止硬编码 `user_id=1`。

# 10. V3 AI Acceptance Contract

Final Freeze前必须建立固定、版本化的V3 fixtures、Mock Provider响应和审核知识测试集。Contract Gate至少覆盖：

- Questionnaire Schema/Submission/FactAdapter，包括none互斥、stale checksum和10题完整性；
- OCR/Narrative/ASR中的否定、subject、past_7_days、用户修正和跨来源去重；
- unsupported claim count为0，所有Fact/Chunk引用100%存在于输入；
- 只有approved且版本匹配的KnowledgeChunk进入Provider；
- Cloud success、401/403、429、timeout、5xx、invalid JSON、repair failure和Local fallback；
- Evidence不足正确abstain，Safety非`clear | resolved`正确withheld；安全且信息充分的Diagnosis abstain进入ADR-0007保守音乐降级，fallback不得绕过Safety；
- sync/async响应语义、隐私日志、Prompt/Schema/Knowledge版本审计一致；
- Preference低于最小样本只收集不应用，高于阈值后下一次Prescription读取正确immutable snapshot。

最低Gate：Schema validity=100%；invalid Evidence/Chunk reference=0；unsupported claim=0；所有Safety invariant=100%；所有失败矩阵路径与期望status一致。质量指标另外记录grounded claim rate、abstain correctness、retrieval recall@k和fallback rate。Sprint4 emotion_f1不得作为V3唯一验收Gate。
# 11. Freeze Gate

- [ ] Owner 确认流程、Fallback 与用户措辞。
- [ ] Medical Knowledge Engineer 确认 Claim Dictionary、Organ Link、聚合阈值和五行五音映射。
- [ ] AI Engineering Lead 确认 Understanding、RAG、Provider、Schema repair 可实现。
- [ ] Backend Platform Engineer 确认 Persistence、事务、迁移和 Auth ownership。
- [ ] Client Engineer 确认 Frontend Read Model 足够，页面不读取 SERVER_INTERNAL。
- [ ] 三份合同字段、状态和版本一致。
- [ ] Final Freeze Review 结论为 `FREEZE` 后，本文状态才能改为 `FROZEN`。
