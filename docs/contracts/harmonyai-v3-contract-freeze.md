# HarmonyAI V3 Contract Freeze Document

> **SUPERSEDED**：本文件已由 `harmonyai-v3-contract-freeze-v3.0.0-draft.3.md` 的 FROZEN 合同取代，仅保留历史参考；不得作为 Sprint 5 实现依据。

> 文档版本：`3.0.0-draft.1`
> 目标 API 版本：`/api/v3`
> 审计基线：`origin/integration/sprint4-real-input@709e4decef4e7c77ed55f5e548eec7809fc6a281`
> Freeze 状态：`PROPOSED_FOR_FREEZE`（Owner、Medical、AI、Backend、Client 共同确认后改为 `FROZEN`）
> 适用范围：Agent 1—5 的 V3 输入输出、RAG、音乐生成与用户偏好闭环
> 不构成医学诊断或治疗建议。

## 1. 冻结原则

1. V3 使用独立的 `/api/v3`、`questionnaire_v3.0` 和 V3 Schema；不得原地修改已冻结的 V2.1/V2.2 Contract。
2. 前端只可提交用户输入、用户确认/修正、资源 ID 和操作意图；不得构造 Assessment、Diagnosis、Prescription 或 Music 结果。
3. 下游 Agent 只消费后端保存并校验过的上游版本：`assessment_id + revision`、`diagnosis_id`、`prescription_id`。
4. 所有用户原文、OCR 文本、语音转写、Provider Prompt、RAG 原文片段均为敏感内部数据。
5. 前端只展示本文明确标记为 `PUBLIC` 或 `PUBLIC_SUMMARY` 的字段。
6. 不向前端返回模型思维链、系统 Prompt、Provider 原始异常、API Key、内部检索 Query 或未脱敏原文。
7. `confidence` 必须附带语义；不得把证据覆盖度、模型输出概率或检索分数表述成医学准确率。
8. Q19/Q20 只从 V3 普通问卷 UI 移除；V2.2、安全规则、Safety Support 和后端安全状态机不得删除。
9. V3 Safety 可继续从用户确认后的病例、自由叙述、语音转写和身体描述中触发。由于没有显式 Q19/Q20，产品不得宣称完成了全用户风险筛查。
10. Feedback 只能更新个人音乐偏好，禁止修改全局医学知识、五脏映射、证型规则和 Safety 规则。

## 2. 通用类型与可见性

### 2.1 基础类型

| 类型 | 定义 |
|---|---|
| `ID` | 非空字符串；推荐前缀：`sess_`、`doc_`、`und_`、`asmt_`、`diag_`、`rx_`、`task_`、`asset_`、`fb_` |
| `Timestamp` | UTC RFC 3339 字符串，例如 `2026-08-21T10:30:00Z` |
| `Score01` | `number`，范围 `[0, 1]`，必须附带明确语义 |
| `PercentWeight` | `number`，范围 `[0, 1]`；同一 Profile 的权重和为 `1 ± 0.001` |
| `OrganCode` | `liver | heart | spleen | lung | kidney` |
| `ElementCode` | `wood | fire | earth | metal | water` |
| `ToneCode` | `jue | zhi | gong | shang | yu` |
| `SourceType` | `document | case_summary | narrative | voice_transcript | questionnaire | user_correction` |
| `SafetyStatus` | `clear | needs_verification | confirmed_mental_health_risk | confirmed_acute_physical_risk` |

### 2.2 可见性

| 标记 | 含义 |
|---|---|
| `PUBLIC` | 可直接返回并展示给当前已授权用户 |
| `PUBLIC_SUMMARY` | 只能展示经过脱敏、翻译和用户友好化的摘要 |
| `INTERNAL` | 后端和 Agent 使用，前端不得展示 |
| `SENSITIVE_INTERNAL` | 敏感内部数据；最小化传输、受控保存、禁止普通日志 |

### 2.3 通用 API Envelope

成功响应：

```json
{
  "ok": true,
  "data": {},
  "request_id": "req_xxx",
  "schema_version": "harmonyai_v3.0"
}
```

失败响应：

```json
{
  "ok": false,
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "可安全展示给用户的错误信息",
    "retryable": false,
    "next_actions": ["retry", "use_fallback"]
  },
  "request_id": "req_xxx",
  "schema_version": "harmonyai_v3.0"
}
```

`error.code` 为 `INTERNAL`，`error.message` 和 `next_actions` 为 `PUBLIC`。Provider 原始异常不得进入该 Envelope。

---

# 3. Agent 1 — Assessment V3

## 3.1 职责边界

Agent 1 将用户确认后的病例摘要、自由叙述、语音转写和10道五脏问卷转换为可追溯的事实、五脏 Evidence 与五脏状态画像。Agent 1 不输出医学诊断，不直接决定五音比例。

## 3.2 Input JSON

```json
{
  "schema_version": "assessment_v3.0",
  "session_id": "sess_xxx",
  "user_id": "u_xxx",
  "understanding_id": "und_xxx",
  "sources": [
    {
      "source_id": "summary_xxx",
      "source_type": "case_summary",
      "status": "user_confirmed",
      "text": "用户确认后的病例摘要",
      "source_revision": 1,
      "captured_at": "2026-08-21T10:30:00Z"
    },
    {
      "source_id": "nar_xxx",
      "source_type": "narrative",
      "status": "user_confirmed",
      "text": "用户确认后的最近情况",
      "source_revision": 1,
      "captured_at": "2026-08-21T10:31:00Z"
    }
  ],
  "questionnaire": {
    "schema_version": "questionnaire_v3.0",
    "time_window_days": 14,
    "answers": [
      {
        "question_id": "q01_xxx",
        "value": 2,
        "answer_type": "frequency_0_4"
      }
    ],
    "started_at": "2026-08-21T10:32:00Z",
    "completed_at": "2026-08-21T10:34:00Z"
  },
  "user_goal": {
    "primary_goal": "sleep",
    "secondary_goal": "relaxation",
    "custom_goal_text": null
  }
}
```

### Input 字段

| 字段 | 类型 | 必填 | 来源 | 可见性 | 约束 |
|---|---|---:|---|---|---|
| `schema_version` | literal `assessment_v3.0` | 是 | Backend Contract | INTERNAL | 固定值 |
| `session_id` | `ID` | 是 | Session Service | INTERNAL | 必须属于当前用户 |
| `user_id` | `ID` | 是 | Auth Service 注入 | INTERNAL | 不信任前端任意传值 |
| `understanding_id` | `ID` | 是 | Information Understanding Layer | INTERNAL | 必须已完成输入确认 |
| `sources` | `AssessmentSource[]` | 是 | Understanding Layer | SENSITIVE_INTERNAL | 至少1个可用来源 |
| `questionnaire` | `QuestionnaireV3Submission?` | 有病例流程可选；无病例流程必填 | 前端问卷 | INTERNAL | 恰好10题；不得包含 Q19/Q20 |
| `user_goal` | `UserGoal` | 是 | 用户选择 | PUBLIC | 不得作为医学证据直接决定证型 |

`AssessmentSource.status` 只允许 `user_confirmed | skipped | unavailable`。只有 `user_confirmed` 的文本可以产生 Evidence。

## 3.3 Evidence Schema

```json
{
  "evidence_id": "ev_xxx",
  "organ": "spleen",
  "element": "earth",
  "evidence_type": "sleep",
  "claim_code": "unrefreshing_sleep",
  "display_name": "醒来后仍感疲惫",
  "direction": "supporting",
  "strength": 0.72,
  "strength_semantics": "evidence_support_strength",
  "severity": "moderate",
  "time_window": "past_14_days",
  "source_type": "narrative",
  "source_ref": "nar_xxx",
  "quote": "醒来以后还是很累",
  "confirmed": true,
  "extraction": {
    "method": "qwen",
    "confidence": 0.84
  }
}
```

### Evidence 字段

| 字段 | 类型 | 来源 | 可见性 | 规则 |
|---|---|---|---|---|
| `evidence_id` | `ID` | Backend | INTERNAL | 全局唯一 |
| `organ` | `OrganCode` | Agent 1 + 审核映射 | PUBLIC | 单条 Evidence 只绑定一个脏；多脏关系拆成多条 Evidence |
| `element` | `ElementCode` | 固定五脏—五行映射 | PUBLIC | 必须与 `organ` 一致 |
| `evidence_type` | `emotion | physical | sleep | appetite | energy | life_event | document | lifestyle` | Agent 1 | PUBLIC | 受控枚举 |
| `claim_code` | `string` | 医学审核后的 Claim Dictionary | INTERNAL | 不展示内部枚举 |
| `display_name` | `string` | Claim Dictionary | PUBLIC | 用户友好中文，不得是内部 enum |
| `direction` | `supporting | contradicting` | Agent 1 | PUBLIC | 必须保留反证 |
| `strength` | `Score01` | Evidence Aggregator | INTERNAL | 不是医学准确率 |
| `strength_semantics` | literal `evidence_support_strength` | Contract | INTERNAL | 固定值 |
| `severity` | `none | mild | moderate | severe` | 问卷/文本提取 | PUBLIC | 仅为状态强度描述 |
| `time_window` | `string` | 原始输入 | PUBLIC | 例如 `current`、`past_14_days` |
| `source_type` | `SourceType` | 原始输入 | PUBLIC_SUMMARY | 页面可显示“来自问卷/描述/材料” |
| `source_ref` | `ID` | Backend | INTERNAL | 必须能回溯来源 |
| `quote` | `string?` | 用户原文/OCR | SENSITIVE_INTERNAL | 不默认展示；用户查看原始材料时单独授权 |
| `confirmed` | `boolean` | 用户确认状态 | INTERNAL | Diagnosis 只优先使用已确认 Evidence |
| `extraction.method` | `questionnaire_rule | qwen | user_correction | document_rule` | Backend | INTERNAL | 不对用户宣传厂商细节 |
| `extraction.confidence` | `Score01?` | Provider/Rule | INTERNAL | 不是医学准确率 |

禁止规则：不得采用“某一题选择某选项 → 直接等于某一脏 → 直接等于某一调式”的硬编码链路。

## 3.4 Output JSON

```json
{
  "schema_version": "assessment_v3.0",
  "agent_id": "assessment_agent",
  "assessment_id": "asmt_xxx",
  "session_id": "sess_xxx",
  "user_id": "u_xxx",
  "revision": 1,
  "status": "needs_confirmation",
  "state_summary": "你最近主要表现为反复思虑、睡眠恢复不足和精力下降。",
  "recent_context_summary": "近期压力主要与学习安排有关。",
  "organ_profile": {
    "liver": 0.18,
    "heart": 0.12,
    "spleen": 0.46,
    "lung": 0.09,
    "kidney": 0.15,
    "score_semantics": "relative_evidence_distribution"
  },
  "organ_evidence": [],
  "conflicts": [],
  "missing_information": [],
  "evidence_coverage": 0.76,
  "evidence_coverage_semantics": "available_source_coverage",
  "requires_user_confirmation": true,
  "safety_status": "clear",
  "safety_signals": [],
  "degradation": {
    "active": false,
    "reason_codes": []
  },
  "provider_metadata": {
    "provider": "qwen",
    "model": "configured-model",
    "latency_ms": 820,
    "input_tokens": 650,
    "output_tokens": 320,
    "attempts": 1
  },
  "presentation": {
    "title": "确认一下我们对你当前状态的理解",
    "summary": "你最近主要表现为反复思虑、睡眠恢复不足和精力下降。",
    "organ_cards": [
      {
        "organ": "spleen",
        "label": "脾相关状态倾向",
        "evidence_summaries": ["反复思虑", "精力下降"]
      }
    ],
    "goal_summary": "本次希望帮助入睡并放松紧张"
  }
}
```

### Output 可见性

| 字段 | 可见性 |
|---|---|
| `presentation.*` | PUBLIC，前端主要数据源 |
| `state_summary`、`recent_context_summary` | PUBLIC |
| `organ_profile` | PUBLIC，但页面必须解释为“相对证据分布”，不是健康分数 |
| `organ_evidence.display_name/direction/severity/time_window` | PUBLIC |
| `assessment_id`、`revision`、`status` | INTERNAL；前端保存但不作为正文展示 |
| `organ_evidence.quote` | SENSITIVE_INTERNAL |
| `evidence_coverage` | INTERNAL；不得显示“可信度xx%” |
| `safety_status` | INTERNAL；前端只按安全状态机展示对应页面 |
| `safety_signals` | SENSITIVE_INTERNAL |
| `degradation.reason_codes` | INTERNAL；前端显示安全映射文案 |
| `provider_metadata` | INTERNAL；仅运维/管理端可查看 |

---

# 4. Agent 2 — Diagnosis V3

## 4.1 职责边界

Agent 2 使用用户已确认的 Assessment Revision，通过审核后的知识库检索和 Qwen 推理生成“辅助辨证倾向”。Agent 2 不接收前端提交的自由 Diagnosis 对象，不直接生成音乐。

## 4.2 Frontend/API 请求

```json
{
  "assessment_id": "asmt_xxx",
  "assessment_revision": 2
}
```

Backend 必须从数据库读取已确认 Snapshot。未确认、过期 Revision、Safety 非 clear 时不得进入普通 Diagnosis。

## 4.3 Agent 内部 Input JSON

```json
{
  "schema_version": "diagnosis_v3.0",
  "diagnosis_id": "diag_xxx",
  "assessment_ref": {
    "assessment_id": "asmt_xxx",
    "revision": 2,
    "confirmation_status": "confirmed",
    "safety_status": "clear"
  },
  "organ_profile": {
    "liver": 0.18,
    "heart": 0.12,
    "spleen": 0.46,
    "lung": 0.09,
    "kidney": 0.15
  },
  "organ_evidence": [],
  "conflicts": [],
  "missing_information": [],
  "evidence_coverage": 0.76,
  "rag_policy": {
    "collection": "harmony_medical_v3",
    "top_k": 5,
    "minimum_score": 0.55,
    "knowledge_version": "medical_v3.0"
  }
}
```

`rag_policy` 由后端配置注入，不接受前端覆盖。

## 4.4 RAG Result Schema

```json
{
  "retrieval_id": "rag_xxx",
  "query_hash": "sha256:...",
  "knowledge_version": "medical_v3.0",
  "status": "success",
  "hits": [
    {
      "chunk_id": "kb_xxx",
      "source_id": "source_xxx",
      "source_title": "审核后的知识来源标题",
      "section": "相关章节",
      "evidence_level": "reviewed_reference",
      "retrieval_score": 0.81,
      "text": "供模型使用的知识片段",
      "display_summary": "与当前证据相关的知识依据摘要",
      "review_status": "approved",
      "knowledge_version": "medical_v3.0"
    }
  ],
  "degradation": {
    "active": false,
    "reason_codes": []
  }
}
```

### RAG 字段可见性

| 字段 | 可见性 |
|---|---|
| `source_title`、`section`、`display_summary` | PUBLIC_SUMMARY |
| `retrieval_id`、`chunk_id`、`source_id`、`knowledge_version` | INTERNAL |
| `query_hash`、`retrieval_score` | INTERNAL |
| `text` | SENSITIVE_INTERNAL；只供模型和审核工具使用 |
| `review_status` | INTERNAL；只有 `approved` 可进入推理 |

RAG 结果为空、版本错误或未审核时，Agent 2 必须降级或 abstain，不得伪造检索成功。

## 4.5 Output JSON

```json
{
  "schema_version": "diagnosis_v3.0",
  "agent_id": "diagnosis_agent",
  "diagnosis_id": "diag_xxx",
  "assessment_id": "asmt_xxx",
  "assessment_revision": 2,
  "status": "success",
  "abstained": false,
  "abstain_reason": null,
  "candidate_tendencies": [
    {
      "syndrome_id": "syd_xxx",
      "display_name": "心脾两虚倾向",
      "score": 0.73,
      "score_semantics": "relative_candidate_support",
      "organs": ["heart", "spleen"],
      "elements": ["fire", "earth"],
      "supporting_evidence_ids": ["ev_1", "ev_2"],
      "contradicting_evidence_ids": ["ev_3"],
      "knowledge_chunk_ids": ["kb_1"],
      "reasoning_summary": "多条已确认状态证据共同支持该辅助辨证倾向。"
    }
  ],
  "primary_tendency_id": "syd_xxx",
  "element_profile": {
    "wood": 0.16,
    "fire": 0.24,
    "earth": 0.42,
    "metal": 0.08,
    "water": 0.10,
    "score_semantics": "relative_element_support"
  },
  "rag_result_ref": "rag_xxx",
  "warnings": [],
  "degradation": {
    "active": false,
    "reason_codes": []
  },
  "provider_metadata": {
    "provider": "qwen",
    "model": "configured-model",
    "latency_ms": 940,
    "input_tokens": 900,
    "output_tokens": 420,
    "attempts": 1
  },
  "presentation": {
    "title": "辅助辨证倾向",
    "primary_tendency": "心脾两虚倾向",
    "basis_summaries": ["反复思虑", "睡眠恢复不足", "精力下降"],
    "knowledge_references": [
      {
        "title": "审核后的知识来源标题",
        "summary": "与当前证据相关的知识依据摘要"
      }
    ],
    "disclaimer": "本结果仅用于音乐调养参考，不构成医学诊断。"
  }
}
```

### Diagnosis 输出可见性

| 字段 | 可见性 |
|---|---|
| `presentation.*` | PUBLIC |
| `candidate_tendencies[].display_name/reasoning_summary` | PUBLIC |
| `candidate_tendencies[].score` | INTERNAL；默认不显示百分比 |
| `supporting_evidence_ids`、`contradicting_evidence_ids` | INTERNAL |
| `knowledge_chunk_ids`、`rag_result_ref` | INTERNAL |
| `element_profile` | PUBLIC，可解释为“本次音乐参数依据的相对分布” |
| `provider_metadata`、`degradation.reason_codes` | INTERNAL |

允许的 `abstain_reason`：`SAFETY_BLOCKED | ASSESSMENT_NOT_CONFIRMED | INSUFFICIENT_EVIDENCE | UNRESOLVED_MAJOR_CONFLICT | RAG_UNAVAILABLE | MODEL_SCHEMA_INVALID`。

---

# 5. Agent 3 — Prescription V3

## 5.1 职责边界

Agent 3 只将后端保存的 Diagnosis、用户目标和个人音乐偏好转换为音乐生成参数。Agent 3 不重新解释病例，不修改 Diagnosis，不让偏好覆盖医学/Safety 边界。

## 5.2 Input JSON

```json
{
  "schema_version": "prescription_v3.0",
  "session_id": "sess_xxx",
  "diagnosis_id": "diag_xxx",
  "assessment_ref": {
    "assessment_id": "asmt_xxx",
    "revision": 2
  },
  "user_goal": {
    "primary_goal": "sleep",
    "secondary_goal": "relaxation",
    "custom_goal_text": null
  },
  "user_preference_snapshot": {
    "profile_id": "pref_xxx",
    "version": 4,
    "preferred_instruments": ["guqin"],
    "disliked_instruments": ["sharp_dizi"],
    "preferred_bpm_range": [52, 64],
    "preferred_duration_seconds": 900,
    "preferred_ambient": ["water"],
    "sample_count": 6
  }
}
```

前端只提交 `diagnosis_id`；其余数据由后端读取并组装。

## 5.3 Tone Profile Schema

```json
{
  "schema_version": "tone_profile_v3.0",
  "weights": {
    "jue": 0.16,
    "zhi": 0.24,
    "gong": 0.42,
    "shang": 0.08,
    "yu": 0.10
  },
  "dominant_tone": "gong",
  "mapping_version": "five_tone_mapping_v3.0",
  "basis": {
    "diagnosis_id": "diag_xxx",
    "element_profile": {
      "wood": 0.16,
      "fire": 0.24,
      "earth": 0.42,
      "metal": 0.08,
      "water": 0.10
    },
    "supporting_evidence_ids": ["ev_1", "ev_2"]
  }
}
```

Tone Profile 约束：

1. 五个 `weights` 均在 `[0,1]`。
2. 权重和必须为 `1 ± 0.001`。
3. `dominant_tone` 必须是最大权重项；并列时按审核后的固定 tie-break 规则处理。
4. `mapping_version` 必须对应已审核知识映射。
5. User Preference 不得直接改变 Tone Profile，只能调整 BPM、乐器、时长、环境音和音乐结构。

## 5.4 Output JSON

```json
{
  "schema_version": "prescription_v3.0",
  "agent_id": "prescription_agent",
  "prescription_id": "rx_xxx",
  "session_id": "sess_xxx",
  "diagnosis_id": "diag_xxx",
  "status": "success",
  "prescription_mode": "syndrome_based",
  "tone_profile": {},
  "music_parameters": {
    "bpm": 58,
    "duration_seconds": 900,
    "instruments": ["guqin", "xiao"],
    "ambient_sounds": ["water"],
    "structure": {
      "intro_seconds": 60,
      "main_seconds": 720,
      "outro_seconds": 120
    },
    "energy_curve": "gentle_decline"
  },
  "forbidden_constraints": ["sharp_high_frequency"],
  "personalization": {
    "applied": true,
    "profile_id": "pref_xxx",
    "profile_version": 4,
    "adjustments": [
      {
        "field": "instrument",
        "from": "dizi",
        "to": "guqin",
        "reason_code": "USER_PREFERENCE"
      }
    ]
  },
  "generation_prompt": {
    "prompt_version": "music_prompt_v3.0",
    "positive_parameters": {},
    "negative_constraints": []
  },
  "presentation": {
    "title": "本次音乐生成依据",
    "tone_summary": "本次以宫音为主，并融合少量徵音与角音。",
    "parameter_summaries": ["节奏较慢，适合睡前放松", "采用古琴和洞箫"],
    "personalization_summary": "已根据你过去的反馈保留古琴并避免尖锐高频音色。"
  },
  "warnings": [],
  "disclaimer": "该方案用于非医疗性的音乐调养参考。"
}
```

### Prescription 输出可见性

| 字段 | 可见性 |
|---|---|
| `presentation.*` | PUBLIC |
| `tone_profile.weights/dominant_tone` | PUBLIC |
| `music_parameters` | PUBLIC |
| `personalization.applied`、`personalization_summary` | PUBLIC |
| `personalization.profile_id/version` | INTERNAL |
| `forbidden_constraints` | INTERNAL；前端只显示友好化解释 |
| `generation_prompt` | INTERNAL；不得返回完整 Prompt 给普通前端 |

`status` 允许：`success | degraded | withheld`。Safety 非 clear、Assessment 未确认或真正信息不足时必须 `withheld`。

---

# 6. Agent 4 — Music Generation V3

## 6.1 Request Schema

```json
{
  "schema_version": "music_generation_v3.0",
  "request_id": "mgr_xxx",
  "session_id": "sess_xxx",
  "user_id": "u_xxx",
  "prescription_id": "rx_xxx",
  "idempotency_key": "sha256:...",
  "parameters": {
    "tone_profile": {},
    "bpm": 58,
    "duration_seconds": 900,
    "instruments": ["guqin", "xiao"],
    "ambient_sounds": ["water"],
    "structure": {
      "intro_seconds": 60,
      "main_seconds": 720,
      "outro_seconds": 120
    },
    "energy_curve": "gentle_decline",
    "negative_constraints": ["sharp_high_frequency"]
  },
  "provider_policy": {
    "preferred_provider": "configured_provider",
    "timeout_seconds": 120,
    "allow_local_fallback": true,
    "max_cost_cny": 2.0
  }
}
```

### Request 字段可见性

| 字段 | 来源 | 可见性 |
|---|---|---|
| `session_id/user_id` | Backend/Auth | INTERNAL |
| `prescription_id` | Agent 3 | INTERNAL |
| `idempotency_key` | Backend | INTERNAL |
| `parameters` | Agent 3 权威输出 | PUBLIC_SUMMARY；完整结构仅内部 |
| `provider_policy` | Deployment/Backend | INTERNAL |

Request 不得包含病例原文、Narrative 原文、语音文本、Safety Signal、Diagnosis Prompt 或用户身份明文。

## 6.2 Provider Interface

```text
interface MusicGenerationProvider:
    create_task(request: ProviderMusicRequest) -> ProviderTask
    get_task(provider_task_id: string) -> ProviderTask
    cancel_task(provider_task_id: string) -> ProviderTask
    health() -> ProviderHealth
```

异步实现必须提供等价接口：

```text
async create_task(request: ProviderMusicRequest) -> ProviderTask
async get_task(provider_task_id: string) -> ProviderTask
async cancel_task(provider_task_id: string) -> ProviderTask
async health() -> ProviderHealth
```

Provider-neutral 类型：

```json
{
  "provider_task_id": "vendor_task_xxx",
  "status": "queued",
  "audio_url": null,
  "duration_seconds": null,
  "format": null,
  "cost_cny": null,
  "latency_ms": 120,
  "error_code": null,
  "retryable": false
}
```

Provider Adapter 负责厂商字段转换；Agent 4、Router 和前端不得依赖厂商专有字段、URL 或 SDK 类型。

## 6.3 Response Schema

```json
{
  "schema_version": "music_generation_v3.0",
  "agent_id": "music_agent",
  "task_id": "task_xxx",
  "prescription_id": "rx_xxx",
  "status": "succeeded",
  "source_type": "generated",
  "provider": "configured_provider",
  "provider_task_id": "vendor_task_xxx",
  "audio_asset": {
    "asset_id": "asset_xxx",
    "stream_url": "/api/v3/music-assets/asset_xxx/stream",
    "format": "mp3",
    "duration_seconds": 900,
    "checksum": "sha256:...",
    "expires_at": null
  },
  "fallback": {
    "applied": false,
    "reason_code": null,
    "matched_music_id": null
  },
  "metrics": {
    "queued_ms": 420,
    "generation_ms": 28000,
    "cost_cny": 0.35
  },
  "error": null,
  "presentation": {
    "title": "音乐已生成",
    "source_label": "AI生成音乐",
    "status_message": "已根据本次音乐参数完成生成。"
  }
}
```

### 状态与降级规则

`status` 允许：`queued | running | succeeded | failed | cancelled`。

生成失败后使用本地曲库时：

```json
{
  "status": "succeeded",
  "source_type": "matched",
  "fallback": {
    "applied": true,
    "reason_code": "PROVIDER_TIMEOUT",
    "matched_music_id": "music_xxx"
  },
  "presentation": {
    "source_label": "本地曲库匹配",
    "status_message": "生成服务暂时不可用，已为你匹配可播放音乐。"
  }
}
```

### Response 可见性

| 字段 | 可见性 |
|---|---|
| `presentation.*` | PUBLIC |
| `status`、`source_type`、`audio_asset.stream_url/duration_seconds/format` | PUBLIC |
| `fallback.applied` | PUBLIC |
| `fallback.reason_code` | INTERNAL；前端使用映射文案 |
| `provider` | PUBLIC_SUMMARY，可显示“AI生成服务”，不必暴露供应商 |
| `provider_task_id`、`checksum`、`metrics.cost_cny` | INTERNAL |
| `error` | INTERNAL；前端只接收安全错误文案 |

Safety blocked、Diagnosis 未完成、Prescription missing/withheld 时，Agent 4 不得创建 Provider Task。

---

# 7. Agent 5 — Feedback V3

## 7.1 Feedback Schema

```json
{
  "schema_version": "feedback_v3.0",
  "session_id": "sess_xxx",
  "prescription_id": "rx_xxx",
  "music_id": "asset_xxx",
  "source_type": "generated",
  "post_state": {
    "change_label": "slightly_better",
    "tension": 4,
    "body_tension": 3,
    "mental_fatigue": 5
  },
  "experience": {
    "overall_rating": 4,
    "relaxation_rating": 4,
    "music_match_rating": 5,
    "continue_use": "yes",
    "favorite": true,
    "liked_features": ["guqin", "gentle_rhythm"],
    "adjustment_preferences": ["slower_tempo", "less_high_frequency"],
    "comment": "古琴部分比较舒服"
  },
  "playback": {
    "listened_seconds": 820,
    "duration_seconds": 900,
    "completion_rate": 0.91,
    "pause_count": 1,
    "skip_count": 0
  },
  "submitted_at": "2026-08-21T11:00:00Z"
}
```

### Feedback 字段规则

| 字段 | 类型 | 来源 | 可见性 | 规则 |
|---|---|---|---|---|
| `post_state.change_label` | `much_better | slightly_better | no_change | worse` | 用户 | PUBLIC | 唯一必填体验字段 |
| `post_state` 其他评分 | `integer? 0..10` | 用户 | PUBLIC | 选填 |
| `experience.*rating` | `integer? 1..5` | 用户 | PUBLIC | 选填 |
| `continue_use` | `yes | maybe | no | null` | 用户 | PUBLIC | 单选 |
| `favorite` | `boolean?` | 用户 | PUBLIC | 收藏意图 |
| `liked_features` | `string[]` | 用户 | PUBLIC | 多选、去重 |
| `adjustment_preferences` | `string[]` | 用户 | PUBLIC | 多选；互斥组不得同时提交 |
| `comment` | `string <= 500` | 用户 | SENSITIVE_INTERNAL | 用户本人历史中可回看，禁止普通日志 |
| `playback` | object? | Player | INTERNAL | 服务端复核 completion rate |

互斥组至少包括：

- `slower_tempo` ↔ `faster_tempo`
- `shorter_duration` ↔ `longer_duration`

前端负责即时互斥，后端必须再次校验。

## 7.2 User Preference Schema

```json
{
  "schema_version": "user_music_preference_v3.0",
  "profile_id": "pref_xxx",
  "user_id": "u_xxx",
  "version": 4,
  "preferred_instruments": [
    {
      "value": "guqin",
      "weight": 0.82,
      "sample_count": 6
    }
  ],
  "disliked_instruments": [
    {
      "value": "sharp_dizi",
      "weight": 0.65,
      "sample_count": 3
    }
  ],
  "preferred_features": [
    {
      "value": "gentle_rhythm",
      "weight": 0.74,
      "sample_count": 5
    }
  ],
  "preferred_bpm_range": [52, 64],
  "preferred_duration_seconds": 900,
  "preferred_ambient": ["water"],
  "adjustment_preferences": ["less_high_frequency"],
  "favorite_music_ids": ["asset_xxx"],
  "learning": {
    "total_feedback_count": 8,
    "minimum_samples_before_apply": 2,
    "maximum_single_update_delta": 0.15,
    "last_feedback_id": "fb_xxx"
  },
  "created_at": "2026-08-01T08:00:00Z",
  "updated_at": "2026-08-21T11:00:01Z"
}
```

### User Preference 字段可见性

| 字段 | 可见性 |
|---|---|
| 偏好/不喜欢的乐器、音乐特点、BPM、时长、环境音 | PUBLIC |
| `favorite_music_ids` | PUBLIC |
| `profile_id/version` | INTERNAL；前端用于并发控制但不展示 |
| 各项 `weight/sample_count` | INTERNAL；个人主页展示时转换成“常用/偏好/偶尔” |
| `learning.*` | INTERNAL |

### Preference 更新规则

1. 每次 Feedback 先生成 `PreferencePatch`，再由受控 Update Service 合并。
2. 一次反馈的单项权重变化不得超过 `0.15`。
3. 默认至少2次一致反馈后，偏好才能影响下一次生成；用户显式收藏可立即进入收藏列表，但不自动改变医学参数。
4. `worse` 反馈可以降低当前音乐元素权重，但不得自动推翻 Assessment 或 Diagnosis。
5. User Preference 只允许影响 Agent 3 的 BPM、乐器、时长、环境音、结构和负面约束。
6. User Preference 不允许影响 Safety、五脏 Evidence、RAG 医学知识、证型候选和五行到五音固定映射。

## 7.3 Agent 5 Output JSON

```json
{
  "schema_version": "feedback_v3.0",
  "agent_id": "feedback_agent",
  "feedback_id": "fb_xxx",
  "status": "success",
  "idempotent": false,
  "preference_patch": {
    "preserve_instruments": ["guqin"],
    "reduce_instruments": [],
    "preferred_features_add": ["gentle_rhythm"],
    "adjustment_preferences_add": ["slower_tempo", "less_high_frequency"],
    "favorite_music_add": ["asset_xxx"]
  },
  "profile_update": {
    "profile_id": "pref_xxx",
    "previous_version": 3,
    "new_version": 4,
    "applied": true
  },
  "global_medical_rules_updated": false,
  "presentation": {
    "message": "反馈已保存，并会在后续音乐参数中参考你的个人偏好。"
  }
}
```

`presentation.message` 为 PUBLIC；`preference_patch` 和 `profile_update` 为 INTERNAL。只有当偏好真正持久化成功时，才允许显示“会在后续参考”。

---

# 8. 跨 Agent 数据权威链

```text
Confirmed Source IDs
→ Assessment V3 (assessment_id + revision)
→ User Confirmation
→ Diagnosis V3 (diagnosis_id)
→ Prescription V3 (prescription_id)
→ Music Generation V3 (task_id + asset_id)
→ Feedback V3 (feedback_id)
→ User Preference Profile (profile_id + version)
→ Next Prescription V3
```

权威规则：

1. Diagnosis 必须读取数据库中已确认的 Assessment Revision。
2. Prescription 必须读取数据库中的 Diagnosis，不能接收前端完整 Diagnosis JSON。
3. Music Generation 必须读取后端权威 Prescription，前端不得传完整生成参数覆盖它。
4. Feedback 必须关联真实的 `session_id + prescription_id + music_id`。
5. 下次 Prescription 读取固定版本的 Preference Snapshot，确保结果可复现。

# 9. Provider 与降级冻结规则

## 9.1 Qwen

```text
Cloud Qwen
→ Local Qwen（策略允许时）
→ 问卷/规则降级
```

降级必须保留：Evidence 来源、Safety、用户确认、abstain 和后端处方权威。

## 9.2 RAG

```text
Approved Knowledge Hits
→ Qwen Diagnosis
```

知识库不可用时不得伪装 RAG 成功；可使用本地审核规则生成保守候选，或在证据不足时 abstain。

## 9.3 Music Generation

```text
Real Generation Provider
→ failure/timeout/quota/invalid audio
→ Local Catalog Matching
```

Fallback 必须标记 `source_type=matched`，不得标记成 AI 实时生成。

# 10. Contract Freeze 验收条件

该文档只有在以下条件全部满足后才能把状态改为 `FROZEN`：

- [ ] Owner 确认 V3 用户流程和 Q19/Q20 UI 移除边界。
- [ ] Medical Knowledge Engineer 确认 Organ/Element/Tone 枚举和 Evidence 规则。
- [ ] AI Engineering Lead 确认 Assessment、RAG、Diagnosis 和 Provider Schema 可实现。
- [ ] Backend Platform Engineer 确认 ID、持久化、异步任务和幂等约束。
- [ ] Client Engineer 确认所有 PUBLIC 字段足以完成页面，不需要读取 INTERNAL 字段。
- [ ] `questionnaire_v3.0` 的10道题和计分/证据规则另行完成医学审核。
- [ ] Contract Tests 覆盖字段类型、枚举、可见性、权重和、互斥、Safety Gate、Revision 和 fallback。
- [ ] V2.1/V2.2 Contract Tests 保持通过。

Freeze 后若需破坏性修改，必须升级 Schema Version；不得静默改变已冻结字段含义。
