# HarmonyAI Assessment Contract v2.1

> **Version**: 2.1
> **Sprint**: Sprint 4
> **Replaces**: v2.0 (保留兼容)
> **Status**: FROZEN — S4-01 Contract Tests 与全量回归通过
> **Owner**: 陈家智

---

## 一、核心设计原则

1. **Every claim has a source** — 每个结论必须可追溯到 questionnaire / narrative / document / user_follow_up / user_correction
2. **Uncertainty is explicit** — 信息不足时追问或拒绝判断，不强行输出
3. **No medical claims** — 不使用"诊断""确诊""患有""治疗"，统一用"辅助评估""倾向""调节建议"
4. **User confirms before proceeding** — Assessment 必须用户确认后才能进入 Diagnosis

---

## 二、统一证据结构 (EvidenceItem)

```json
{
  "evidence_id": "ev_uuid",
  "category": "emotion|sleep|energy|appetite|physical|life_event|goal",
  "label": "tension_worry",
  "display_name": "紧张与担忧",
  "value": 3,
  "polarity": "present|absent|reduced|increased|unchanged",
  "severity": "none|mild|moderate|severe",
  "severity_display": "有一定表现",
  "time_window": "过去两周",
  "source_type": "questionnaire|narrative|document|user_follow_up|user_correction",
  "source_ref": "narrative:sentence_2",
  "quote": "最近晚上总是担心项目做不完",
  "extraction_confidence": 0.89,
  "confirmed": false,
  "dimension_score": null
}
```

### 字段约束

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| evidence_id | string | ✅ | UUID |
| category | enum | ✅ | emotion/sleep/energy/appetite/physical/life_event/goal |
| label | string | ✅ | 对应维度 key |
| display_name | string | ✅ | 中文展示名 |
| value | constrained union | ✅ | 仅允许 numeric scalar、categorical string、`list[string]` 或 appetite structured value |
| polarity | enum | ✅ | present/absent/reduced/increased/unchanged |
| severity | enum | ✅ | none/mild/moderate/severe |
| severity_display | string | ✅ | 前端展示文本 |
| time_window | string | ✅ | "过去两周""过去7天""当前" |
| source_type | enum | ✅ | questionnaire/narrative/document/user_follow_up/user_correction |
| source_ref | string | ✅ | 精确到题目或句子 |
| quote | string | 条件 | narrative/document 来源时必填 |
| extraction_confidence | float | 条件 | narrative 来源时必填 |
| confirmed | bool | ✅ | 用户确认后为 true |
| dimension_score | int\|null | ❌ | 问卷维度分 (0-100) |

### EvidenceItem.value 联合类型

`value` 禁止使用无约束的 `Any` 或任意 `dict`。其 JSON Schema 采用四个互斥分支：

```json
{
  "oneOf": [
    {"type": "integer", "minimum": 0, "maximum": 4},
    {"type": "string", "minLength": 1},
    {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
    {
      "type": "object",
      "required": ["direction", "severity"],
      "additionalProperties": false,
      "properties": {
        "direction": {"enum": ["increase", "decrease", "none"]},
        "severity": {"type": "integer", "minimum": 0, "maximum": 4}
      }
    }
  ]
}
```

- numeric scalar：维度强度，例如 `3`；
- categorical string：目标或类别，例如 `"relaxation"`；
- `list[string]`：多项身体信号，例如 `["neck_tension", "palpitation"]`；
- appetite structured value：`{"direction":"decrease","severity":3}`；当 `direction="none"` 时 `severity` 必须为 0。

联合类型同时按 `category` 判别，不能只校验 value 的外形：
- `emotion` / `sleep` / `energy` → 0-4 integer；
- `life_event` / `goal` → non-empty string；
- `physical` → non-empty unique `list[string]`；
- `appetite` → 仅允许上述 `{direction, severity}` 结构。

权威、机器可校验的完整 Schema 位于 `tests/contract/fixtures/assessment-v2.1.contract.json`。

---

## 三、冲突结构 (Conflict)

```json
{
  "conflict_id": "cf_uuid",
  "topic": "tension_worry",
  "display_topic": "紧张担忧程度",
  "severity": "minor|moderate|major",
  "sources": [
    {"source_type": "questionnaire", "value": 1, "label": "从不"},
    {"source_type": "narrative", "value": 4, "label": "几乎每天", "quote": "最近每天都特别紧张"}
  ],
  "summary": "问卷显示紧张程度低(1/4)，但自由描述中明确提到'每天都特别紧张'(4/4)",
  "resolution": "awaiting_user|resolved_by_user|resolved_by_rule|unresolved",
  "user_resolution": null
}
```

---

## 四、缺失信息结构 (MissingInformation)

```json
{
  "field": "duration",
  "display_name": "状态持续时间",
  "reason": "narrative 和 questionnaire 均未明确持续时间",
  "severity": "critical|important|supplementary",
  "candidate_follow_up": {
    "question_id": "fu_duration_001",
    "text": "这些状态大概持续了多久？",
    "type": "single_choice",
    "options": ["少于3天", "3-6天", "1-2周", "2周-1个月", "1-3个月", "超过3个月"]
  }
}
```

---

## 五、动态追问结构 (FollowUpQuestion)

```json
{
  "follow_up_id": "fu_uuid",
  "assessment_id": "asmt_uuid",
  "trigger_reason": "duration_unclear",
  "priority": 1,
  "question_id": "fu_duration_001",
  "text": "这些状态大概持续了多久？",
  "type": "single_choice|multi_choice|scale_0_10|text",
  "options": ["少于3天", "3-6天", "1-2周", "2周-1个月", "1-3个月", "超过3个月"],
  "required": true,
  "max_questions_total": 4
}
```

### 追问触发规则

| 触发条件 | 追问方向 | 优先级 |
|---|---|---|
| 时间不明确 | 持续时间 | high |
| 影响程度不明确 | 生活影响 | high |
| 问卷与 narrative 冲突 | 具体冲突维度 | high |
| 两个候选倾向接近 | 区分性追问 | medium |
| 表述过于模糊 | 具体化 | medium |
| 身体信号需要确认 | 确认信号 | medium |
| 证据覆盖不足 (<70%) | 补充信息 | low |

---

## 六、评估修订结构 (AssessmentRevision)

```json
{
  "assessment_id": "asmt_uuid",
  "revision": 3,
  "previous_revision": 2,
  "created_at": "2026-08-06T10:00:00Z",
  "change_summary": "用户修正了紧张维度评分；回答了2道追问",
  "changes": [
    {"field": "evidence.ev_001.value", "from": 4, "to": 3},
    {"field": "follow_up.fu_001.answer", "from": null, "to": "1-2周"}
  ]
}
```

- 每次修订创建新版本，不覆盖原始结果
- API: `GET /api/v2/assessments/{id}/revisions` 返回所有版本
- 原始版本 revision=1 永远保留

---

## 七、输入处理状态 (InputProcessingStatus)

```json
{
  "input_processing_status": {
    "questionnaire": {
      "version": "questionnaire_v2.1",
      "status": "processed",
      "questions_answered": 20,
      "scored_dimensions": [
        "appetite_change",
        "calm_wellbeing",
        "daily_impact",
        "emotional_recovery",
        "fear_unease",
        "interest_loss",
        "irritability_anger",
        "low_energy",
        "low_mood",
        "overthinking",
        "sleep_disturbance",
        "tension_worry",
        "unrefreshing_sleep"
      ],
      "scored_dimension_count": 13,
      "scored_dimension_derivation": "unique dimensions where questionnaire question scored=true",
      "safety_flags": []
    },
    "narrative": {
      "status": "processed|skipped|unavailable|degraded",
      "text_length": 156,
      "extraction_confidence_avg": 0.87,
      "evidence_items_extracted": 8,
      "warnings": []
    },
    "document": {
      "status": "confirmed|unconfirmed|skipped|ocr_failed",
      "ocr_engine": "paddleocr",
      "ocr_confidence_avg": 0.91,
      "evidence_items_extracted": 3,
      "warnings": []
    }
  }
}
```

---

## 八、Evidence Coverage 与来源多样性

`evidence_coverage_score` 与 `source_diversity` 是两个独立指标：

```text
evidence_coverage_score = 获得有效 Evidence 支持的适用关键信息数 / 当前场景适用的关键信息总数
```

- “关键信息”包括适用的状态维度、持续时间、日常影响及安全信息；不适用项不进入分母。
- `source_diversity` 只描述实际使用的来源数量和来源列表，可包含 questionnaire、narrative、document、user_follow_up、user_correction。
- `source_diversity` 不参与 coverage 乘法，也不能单独触发追问。
- Follow-Up 主要由 critical/important `missing_information`、未解决 `conflict` 或低 `evidence_coverage_score` 触发。
- 完整 questionnaire-only 输入可以达到 `evidence_coverage_score=1.0`；不能仅因没有 document/narrative 就判断信息不足。

权威示例位于 `tests/contract/fixtures/assessment-v2.1.contract.json`。

---

## 九、完整 Assessment V2.1 输出

```json
{
  "agent_id": "assessment_agent",
  "assessment_id": "asmt_uuid",
  "session_id": "sess_uuid",
  "user_id": "demo_user_001",
  "status": "awaiting_confirmation",
  "revision": 1,
  "analysis_mode": "document_narrative_questionnaire",
  "confidence": 0.76,
  "confidence_semantics": "evidence_coverage",
  "input_processing_status": {},
  "emotion_profile": {},
  "physical_profile": {},
  "life_events": {"triggers": []},
  "user_goal": "relaxation",
  "assessment_summary": "当前信息支持进一步进行用户确认。",
  "evidence_items": [],
  "evidence_coverage_score": 0.76,
  "source_diversity": {"count": 3, "sources": ["questionnaire", "narrative", "document"]},
  "conflicts": [],
  "missing_information": [],
  "follow_up_questions": [],
  "requires_user_confirmation": true,
  "safety_flags": [],
  "degradation": {},
  "warnings": [],
  "model_metadata": {
    "provider": "qwen",
    "model": "qwen2.5-7b-instruct",
    "prompt_version": "assessment_v2.1",
    "latency_ms": 1234,
    "tokens_input": 850,
    "tokens_output": 320
  },
  "disclaimer": "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。"
}
```

---

## 十、与 V2.0 的兼容性

- V2.0 的 12 题问卷继续接受 (`schema_version: "questionnaire_v2.0"`)
- V2.1 使用 `schema_version: "questionnaire_v2.1"`
- V2.0 不产生 evidence_items / follow_up_questions / revision
- V2.1 新增字段对 V2.0 客户端透明

---

*陈家智审定，已完成 S4-01 Review*
