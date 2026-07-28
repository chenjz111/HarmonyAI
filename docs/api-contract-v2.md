# HarmonyAI API Contract V2

> 本文定义 Sprint 3 拟议接口。当前项目实际存在的是 `/api/v1/assessment`、`diagnosis`、`prescription`、`generation` 和 `feedback` 等接口；以下 `/api/v2/*` 尚未实现，不能在汇报中描述为现有能力。

## 1. 设计原则

- v1 保持可用，v2 增量实现；
- 使用 Pydantic 模型而不是无约束 `dict`；
- 所有响应保持统一外壳；
- `session_id` 串联八页流程；
- 每个结果记录 `sources_used`、`degradation` 和 `warnings`；
- 文件上传与医学文本按敏感数据处理；
- Music Agent 诚实区分 `matched` 与 `generated`；
- 用户端称“辅助辨证”，旧后端 `/diagnosis` 名称仅为兼容。

## 2. 通用响应

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "req_8b7f2d",
    "schema_version": "2.0",
    "timestamp": "2026-07-28T20:00:00+08:00"
  }
}
```

错误示例：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "OCR_UNAVAILABLE",
    "message": "材料暂时无法识别，你可以重试、手动补充或跳过。",
    "retryable": true,
    "next_actions": ["retry", "manual_text", "skip"]
  },
  "meta": {
    "request_id": "req_8b7f2d",
    "schema_version": "2.0",
    "timestamp": "2026-07-28T20:00:03+08:00"
  }
}
```

建议状态枚举：

- `success`
- `degraded`
- `needs_confirmation`
- `blocked_safety`
- `failed`

## 3. 会话创建

### `POST /api/v2/sessions`

请求：

```json
{
  "user_id": "demo_user_001",
  "entry_mode": "full",
  "client_version": "competition-2026.07.31"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "session_id": "sess_20260728_a13f9c",
    "status": "active",
    "current_step": "document",
    "created_at": "2026-07-28T20:00:00+08:00"
  },
  "error": null
}
```

比赛版可以使用固定演示用户，但不得继续在所有数据库路由中无说明地硬编码 `user_id=1`。

## 4. Document Upload

### `POST /api/v2/documents`

请求类型：`multipart/form-data`

字段：

- `session_id`：必填；
- `file`：JPG、PNG 或 PDF；
- `document_type`：`outpatient_record`、`checkup_report`、`sleep_emotion_record`、`other`；
- `consent_confirmed`：必须为 `true`。

比赛版建议限制：

- 单文件最大 10 MB；
- PDF 最多 3 页；
- 拒绝加密、损坏或 MIME/文件签名不一致的文件；
- 不保证识别手写体；
- 原始文件采用临时存储并按策略清理。

成功响应：

```json
{
  "success": true,
  "data": {
    "document_id": "doc_20260728_21c8e4",
    "session_id": "sess_20260728_a13f9c",
    "file": {
      "name": "record.pdf",
      "media_type": "application/pdf",
      "size_bytes": 482103,
      "page_count": 2
    },
    "ocr_status": "needs_confirmation",
    "extracted_text": "主诉：近一周入睡困难……",
    "warnings": [
      "请确认识别文字，未经确认的内容不会作为可靠评估依据。"
    ],
    "retention": "temporary"
  },
  "error": null
}
```

OCR 降级响应仍可使用 HTTP 200，并以业务状态表达：

```json
{
  "success": true,
  "data": {
    "document_id": "doc_20260728_21c8e4",
    "ocr_status": "degraded",
    "extracted_text": null,
    "degradation": {
      "triggered": true,
      "reason_code": "OCR_UNAVAILABLE",
      "fallback": "manual_or_skip"
    }
  },
  "error": null
}
```

### `PATCH /api/v2/documents/{document_id}/confirmation`

请求：

```json
{
  "session_id": "sess_20260728_a13f9c",
  "confirmed": true,
  "document_text": "主诉：近一周入睡困难，白天疲惫。",
  "redactions_confirmed": true
}
```

响应：

```json
{
  "success": true,
  "data": {
    "document_id": "doc_20260728_21c8e4",
    "document_text": "主诉：近一周入睡困难，白天疲惫。",
    "ocr_status": "confirmed",
    "confirmed_at": "2026-07-28T20:02:00+08:00"
  },
  "error": null
}
```

未经确认的 `extracted_text` 不得以高可信来源进入 Assessment。

## 5. Assessment

### `POST /api/v2/assessments`

请求：

```json
{
  "session_id": "sess_20260728_a13f9c",
  "user_id": "demo_user_001",
  "inputs": {
    "document_id": "doc_20260728_21c8e4",
    "document_text": "主诉：近一周入睡困难，白天疲惫。",
    "narrative_text": "最近要考试，晚上脑子停不下来，白天很累。",
    "questionnaire_answers": {
      "schema_version": "questionnaire_v2.0",
      "time_window_days": 7,
      "answers": [
        {
          "question_id": "q02_tension_worry",
          "value": 3
        }
      ]
    }
  }
}
```

完整请求必须包含 Q1—Q12；示例为简写。后端必须重新校验和计算 Q2—Q11。

成功响应：

```json
{
  "success": true,
  "data": {
    "assessment_id": "asmt_20260728_7d01bf",
    "session_id": "sess_20260728_a13f9c",
    "agent_id": "assessment_agent",
    "status": "success",
    "analysis_mode": "document_narrative_questionnaire",
    "sources_used": [
      {
        "source": "document",
        "status": "confirmed"
      },
      {
        "source": "narrative",
        "status": "used"
      },
      {
        "source": "questionnaire",
        "status": "used"
      }
    ],
    "emotion_profile": {
      "primary_states": ["紧张", "反复思虑"],
      "secondary_states": ["疲惫", "睡眠困扰"],
      "dimension_scores": {
        "tension_worry": 75,
        "overthinking": 75
      },
      "tcm_emotion_candidates": [
        {
          "emotion": "思",
          "confidence": 0.78
        },
        {
          "emotion": "恐",
          "confidence": 0.35
        }
      ]
    },
    "physical_profile": {
      "sleep_disturbance": 75,
      "low_energy": 75,
      "physical_signals": ["入睡困难", "白天疲惫"]
    },
    "life_events": {
      "triggers": ["考试压力", "担心表现不理想"]
    },
    "assessment_summary": "你过去一周较常出现考试相关担忧和反复思虑，并伴有睡眠与精力变化。",
    "extracted_evidence": [
      {
        "claim": "反复思虑较明显",
        "sources": ["narrative", "questionnaire:q03"],
        "summary": "自由描述提到脑子停不下来，Q3 选择经常。"
      }
    ],
    "conflicts": [],
    "missing_information": [],
    "safety_flags": [],
    "degradation": {
      "triggered": false,
      "fallback": null
    },
    "disclaimer": "本结果用于状态整理和音乐调养参考，不构成医学诊断。"
  },
  "error": null
}
```

Qwen 降级响应：

```json
{
  "success": true,
  "data": {
    "assessment_id": "asmt_20260728_7d01bf",
    "agent_id": "assessment_agent",
    "status": "degraded",
    "analysis_mode": "questionnaire_only",
    "sources_used": [
      {
        "source": "questionnaire",
        "status": "used"
      },
      {
        "source": "narrative",
        "status": "unavailable"
      }
    ],
    "emotion_profile": {
      "primary_states": ["紧张", "反复思虑"],
      "secondary_states": [],
      "dimension_scores": {
        "tension_worry": 75,
        "overthinking": 75
      },
      "tcm_emotion_candidates": []
    },
    "physical_profile": {
      "sleep_disturbance": 0,
      "low_energy": 0,
      "physical_signals": []
    },
    "extracted_evidence": [],
    "safety_flags": [],
    "degradation": {
      "triggered": true,
      "reason_code": "QWEN_UNAVAILABLE",
      "fallback": "deterministic_questionnaire"
    },
    "warnings": [
      "自由描述的 AI 分析暂时不可用，已切换到基础问卷评估。"
    ]
  },
  "error": null
}
```

`analysis_mode` 只使用以下枚举：

- `document_narrative_questionnaire`：材料、自由描述和问卷均参与；
- `document_questionnaire`：自由描述跳过或不可用；
- `narrative_questionnaire`：未上传材料；
- `questionnaire_only`：材料与自由描述均未使用，或 OCR/Qwen 降级。

Assessment v2 的规范字段固定为 `document_id`、`document_text`、`narrative_text`、`questionnaire_answers`、`analysis_mode`、`emotion_profile`、`physical_profile`、`extracted_evidence` 和 `safety_flags`。其他展示字段不得替代这些契约字段。

### `PATCH /api/v2/assessments/{assessment_id}/confirmation`

请求：

```json
{
  "session_id": "sess_20260728_a13f9c",
  "confirmation": "partially_accurate",
  "accepted_labels": ["紧张", "反复思虑", "疲惫"],
  "removed_labels": ["恐惧"],
  "user_correction": "我不是特别害怕，主要是脑子停不下来。"
}
```

响应返回确认后的 Assessment 摘要。用户修正必须保留为独立来源，不能篡改原问卷答案。

## 6. Workflow

### `POST /api/v2/workflows`

该接口在用户确认评估后运行 Diagnosis → Prescription → Music。它不是当前已存在的 HTTP 接口。

请求：

```json
{
  "session_id": "sess_20260728_a13f9c",
  "assessment_id": "asmt_20260728_7d01bf",
  "assessment_confirmed": true,
  "music_mode": "matched"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "workflow_id": "wf_20260728_51d9a2",
    "session_id": "sess_20260728_a13f9c",
    "status": "completed",
    "agents": [
      {
        "agent_id": "assessment_agent",
        "status": "success"
      },
      {
        "agent_id": "diagnosis_agent",
        "display_name": "辅助辨证 Agent",
        "status": "success"
      },
      {
        "agent_id": "prescription_agent",
        "status": "success"
      },
      {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "success"
      }
    ],
    "auxiliary_syndrome": {
      "primary_tendency": "心脾两虚倾向",
      "score": 78,
      "element": "土",
      "organs": ["心", "脾"],
      "evidence_summary": [
        "反复思虑较明显",
        "睡眠与精力受到影响",
        "食欲较平时有变化"
      ],
      "disclaimer": "该结果为用于音乐调养的辅助辨证倾向，不构成医学诊断。"
    },
    "prescription": {},
    "music": {},
    "warnings": []
  },
  "error": null
}
```

当 Assessment 为 `blocked_safety` 或未确认时，接口必须拒绝进入普通处方。

## 7. Music

### `POST /api/v2/music`

如 workflow 已包含 Music 执行，前端无需重复调用；该接口用于重试或重新匹配。

请求：

```json
{
  "session_id": "sess_20260728_a13f9c",
  "prescription_id": "rx_20260728_98e0c2",
  "mode": "matched",
  "personal_preferences": {
    "preferred_instruments": ["古琴"],
    "reduced_instruments": ["笛子"],
    "disliked_features": ["high_frequency"]
  }
}
```

响应：

```json
{
  "success": true,
  "data": {
    "agent_id": "music_agent",
    "legacy_alias": "generation_agent",
    "status": "success",
    "music_id": "music_gong_001",
    "title": "宫调·静心",
    "source_type": "matched",
    "stream_url": "/static/music/gong-demo.wav",
    "mode": "宫调",
    "bpm": 58,
    "duration_seconds": 900,
    "instruments": ["古琴", "洞箫"],
    "ambient_sounds": ["流水"],
    "rights_note": "比赛演示授权曲目",
    "match_explanation": [
      "处方要求较低 BPM 和柔和国风乐器",
      "个人偏好保留古琴并降低高频元素"
    ],
    "fallback_music_id": "music_default_001"
  },
  "error": null
}
```

P0 的 `source_type` 只允许 `matched`，表示本地曲库匹配结果，不表示 AI 实时生成。`generated` 可保留为未来枚举，但当前请求应返回 `MODE_NOT_AVAILABLE`，不能伪装为已生成。

## 8. Feedback

### `POST /api/v2/feedback`

完整请求与响应参见 `docs/feedback-v2-spec.md`。最小响应必须包含：

- `feedback_id`
- `subjective_change`
- `decision`
- `personal_preference_patch`
- `global_rule_update: false`

旧接口的 `overall_satisfaction` 与 `comment` 可映射到 v2 的整体星级和文字反馈，但旧请求缺少的听前/听后字段必须标记为 `legacy_missing`，不能补造默认值。

## 9. Session 查询

### `GET /api/v2/sessions/{session_id}`

响应：

```json
{
  "success": true,
  "data": {
    "session_id": "sess_20260728_a13f9c",
    "status": "active",
    "current_step": "player",
    "completed_steps": [
      "document",
      "narrative",
      "questionnaire",
      "assessment",
      "workflow"
    ],
    "input_status": {
      "document": "confirmed",
      "narrative": "used",
      "questionnaire": "completed"
    },
    "agent_status": {
      "assessment_agent": "success",
      "diagnosis_agent": "success",
      "prescription_agent": "success",
      "music_agent": "success",
      "feedback_agent": "waiting"
    },
    "degradations": [],
    "links": {
      "assessment_id": "asmt_20260728_7d01bf",
      "prescription_id": "rx_20260728_98e0c2",
      "music_id": "music_gong_001"
    }
  },
  "error": null
}
```

查询接口返回摘要，不默认返回完整病例原文或自由描述全文。

## 10. 兼容旧接口方案

### 10.1 不破坏 v1

- 保留现有 `/api/v1/*`；
- 不修改旧请求必填字段；
- 不改变旧响应中已被前端依赖的字段；
- 新字段只做可选增量；
- v2 使用单独路由和 Schema；
- 旧四页面在 v2 稳定前保留。

### 10.2 字段映射

| v1 | v2 | 兼容策略 |
|---|---|---|
| `evaluation_agent` | `assessment_agent` | v2 统一新 ID，读取旧数据接受别名 |
| `diagnosis` | `auxiliary_syndrome` | 内部路由兼容，用户端改名 |
| `generation_agent` | `music_agent` | v2 返回 `legacy_alias` |
| `overall_satisfaction` | `experience.overall_rating` | 可直接映射 |
| `comment` | `experience.comment` | 可直接映射 |
| `input_channel=questionnaire` | `sources_used[]` | v2 新增多来源；旧列可记录 `multi_source` |

### 10.3 数据迁移

- 只做增量迁移，不运行 Sprint 2 `init.sql` 中的 DROP 语句；
- 旧 Feedback 记录保留，标记 `schema_version=1.0`；
- 旧 Assessment 保留原始 `raw_input`；
- 新 ID 使用 UUID/随机后缀或数据库唯一序列，避免同日固定 `_001` 冲突；
- 迁移脚本必须可回滚并在副本数据库验证。

## 11. 建议错误码

| 错误码 | 含义 | 是否可继续 |
|---|---|---|
| `FILE_TYPE_NOT_ALLOWED` | 文件类型不支持 | 可重新上传或跳过 |
| `FILE_TOO_LARGE` | 文件过大 | 可重新上传或跳过 |
| `PDF_PAGE_LIMIT` | PDF 页数超限 | 可拆分或跳过 |
| `OCR_UNAVAILABLE` | OCR 服务不可用 | 可手动或跳过 |
| `OCR_CONFIRMATION_REQUIRED` | OCR 文本未确认 | 需确认后使用 |
| `QUESTIONNAIRE_INCOMPLETE` | 问卷未完成 | 返回补充 |
| `QWEN_UNAVAILABLE` | Qwen 不可用 | 自动降级问卷 |
| `MODEL_OUTPUT_INVALID` | 模型输出不符合 Schema | 重试后降级 |
| `SAFETY_FLOW_BLOCKED` | 命中高风险规则 | 暂停普通处方 |
| `ASSESSMENT_NOT_CONFIRMED` | 评估未确认 | 返回结果页 |
| `TRACK_NOT_FOUND` | 本地曲目不可用 | 切备用曲目 |
| `FEEDBACK_SAVE_FAILED` | 反馈保存失败 | 保留内容并重试 |
| `MODE_NOT_AVAILABLE` | 请求真实生成但未实现 | 改用 matched |

## 12. 契约验收

- 所有 v2 请求和响应有 Pydantic Schema；
- 文档示例可通过 JSON 解析；
- v1 契约测试不回退；
- OCR 与 Qwen 降级均为机器可读状态；
- 用户确认前不使用 OCR 原文作为可靠来源；
- Session 查询不泄露完整敏感原文；
- Feedback 响应固定 `global_rule_update=false`；
- Music 响应统一使用 `music_id`、`title`、`source_type`、`stream_url`、`mode`、`bpm`、`duration_seconds` 和 `instruments`；
- Music 响应明确 `source_type=matched`，且页面说明这是本地曲库匹配结果；
- 所有用户可见文案避免医学诊断。
