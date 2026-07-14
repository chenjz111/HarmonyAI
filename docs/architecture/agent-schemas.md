# 五Agent I/O JSON Schema

> 版本：V1.0  
> 日期：2026-07-12  
> 状态：已确认

---

## 通用字段（每个Agent输出必须包含）

```json
{
  "agent_id": "evaluation_agent",
  "agent_version": "1.0.0",
  "confidence": 0.85,
  "reason": ["规则引擎匹配度0.85", "文献支持度0.72"],
  "processing_time_ms": 2340,
  "timestamp": "2026-07-12T10:00:00Z"
}
```

| 通用字段 | 类型 | 说明 |
|----------|------|------|
| `agent_id` | string | 当前Agent标识 |
| `agent_version` | string | 语义化版本，升级Schema时递增 |
| `confidence` | float (0-1) | 当前Agent输出的整体可信度 |
| `reason` | string[] | 决策依据列表，解释"为什么输出这个结果" |
| `processing_time_ms` | int | 处理耗时 |
| `timestamp` | ISO 8601 | 输出时间戳 |

---

## Agent ① 评估Agent

### 输入
- 病例图片（西医/中医报告）→ PaddleOCR
- 语音输入 → 阿里云ASR
- 问卷自评 → 30题Likert 5级

### 输出 Schema

```json
{
  "agent_id": "evaluation_agent",
  "agent_version": "1.0.0",
  "user_id": "u_001",
  "session_id": "sess_20260712_001",
  "input_channel": "case_input",

  "raw_input": {
    "source_type": "western_medicine",
    "ocr_text": "诊断：焦虑症。主诉：入睡困难、心悸...",
    "original_diagnosis": ["焦虑症", "睡眠障碍"],
    "questionnaire_raw": null
  },

  "health_profile": {
    "emotion_scores": {
      "anxiety": 82,
      "depression": 35,
      "anger": 60,
      "fear": 20,
      "overthinking": 45
    },
    "body_indicators": {
      "sleep_quality": 40,
      "appetite": 55,
      "energy": 50,
      "palpitation": 70,
      "digestion": 45
    },
    "questionnaire_scores": {
      "total": 72,
      "emotion_dimension": 38,
      "sleep_dimension": 22,
      "body_dimension": 12
    }
  },

  "term_mapping": [
    {
      "western_term": "焦虑症",
      "tcm_syndrome": "肝郁化火",
      "source": "preset_table",
      "confidence": 0.90
    },
    {
      "western_term": "睡眠障碍",
      "tcm_syndrome": "心肾不交",
      "source": "llm_inference",
      "confidence": 0.72
    }
  ],

  "confidence": 0.85,
  "reason": ["OCR识别成功率98%", "西医→中医映射命中15/18术语", "LLM补充3个未命中术语"],
  "processing_time_ms": 2340,
  "timestamp": "2026-07-12T10:00:00Z"
}
```

---

## Agent ② 中医辨证Agent

### 输入
Agent ① 的 `health_profile` + `term_mapping`

### 输出 Schema

```json
{
  "agent_id": "diagnosis_agent",
  "agent_version": "1.0.0",
  "user_id": "u_001",
  "session_id": "sess_20260712_001",

  "syndrome_diagnosis": {
    "primary": {
      "name": "肝郁化火",
      "element": "木",
      "organ": "肝",
      "emotion": "怒",
      "severity_level": 3,
      "severity_name": "中度"
    },
    "secondary": [
      {
        "name": "阴虚",
        "element": "水",
        "organ": "肾",
        "emotion": "恐",
        "severity_level": 2,
        "severity_name": "轻度"
      },
      {
        "name": "心神不宁",
        "element": "火",
        "organ": "心",
        "emotion": "喜",
        "severity_level": 2,
        "severity_name": "轻度"
      }
    ]
  },

  "confidence": {
    "overall": 0.71,
    "breakdown": {
      "rule_engine_match": 0.85,
      "llm_confidence": 0.72,
      "literature_support": 0.65
    }
  },

  "evidence": [
    {
      "source": "《黄帝内经·素问·阴阳应象大论》",
      "excerpt": "东方生风，风生木...在脏为肝...在音为角",
      "relevance": "high"
    },
    {
      "source": "RCT_2023_Zhang",
      "excerpt": "角调音乐对肝郁化火证焦虑患者有效率82.3%",
      "relevance": "high"
    }
  ],

  "search_keywords": ["肝郁化火", "角调", "疏肝解郁", "木克土", "护脾胃"],

  "warnings": {
    "low_confidence": false,
    "conflicting_signals": false,
    "recommend_professional": false
  },

  "reason": [
    "主导情绪：焦虑82分为最高分 → 怒 → 木 → 肝",
    "睡眠40分提示心肾不交 → 兼证阴虚",
    "RAG检索命中5篇文献，3篇高度相关"
  ],
  "processing_time_ms": 3200,
  "timestamp": "2026-07-12T10:00:05Z"
}
```

---

## Agent ③ 音乐处方Agent

### 输入
Agent ② 的完整输出（syndrome_diagnosis + search_keywords + evidence）

### 输出 Schema

```json
{
  "agent_id": "prescription_agent",
  "agent_version": "1.0.0",
  "user_id": "u_001",
  "session_id": "sess_20260712_001",
  "prescription_id": "rx_20260712_001",

  "daily_plan": [
    {
      "day": 1,
      "title": "疏肝解郁 · 首日调理",
      "tone_weights": [
        { "tone_id": "jiao", "tone_name": "角调", "note": "Mi", "element": "木", "organ": "肝", "weight": 0.75, "role": "主调" },
        { "tone_id": "gong", "tone_name": "宫调", "note": "Do", "element": "土", "organ": "脾", "weight": 0.15, "role": "辅调" },
        { "tone_id": "yu",   "tone_name": "羽调", "note": "La", "element": "水", "organ": "肾", "weight": 0.10, "role": "辅调" }
      ],
      "strategy": "角调为主疏肝解郁，宫调护脾胃防肝病传脾（木克土），羽调滋水涵木",
      "bpm": 68,
      "duration_minutes": 15,
      "instruments": [
        { "id": "guzheng", "name": "古筝", "role": "primary", "weight": 0.70 },
        { "id": "zhudi",   "name": "竹笛", "role": "secondary", "weight": 0.20 },
        { "id": "guqin",   "name": "古琴", "role": "harmony", "weight": 0.10 }
      ],
      "ambient_sound": { "id": "water_stream", "name": "流水声", "volume": 0.15 },
      "mood": "舒缓、清新，如春风拂柳",
      "scenario": "睡前放松"
    },
    {
      "day": 2,
      "title": "疏肝健脾 · 巩固调理",
      "tone_weights": [
        { "tone_id": "jiao", "tone_name": "角调", "note": "Mi", "element": "木", "organ": "肝", "weight": 0.60, "role": "主调" },
        { "tone_id": "gong", "tone_name": "宫调", "note": "Do", "element": "土", "organ": "脾", "weight": 0.30, "role": "辅调" },
        { "tone_id": "yu",   "tone_name": "羽调", "note": "La", "element": "水", "organ": "肾", "weight": 0.10, "role": "辅调" }
      ],
      "strategy": "降低角调比重，增加宫调强化脾胃，延续羽调滋水",
      "bpm": 66,
      "duration_minutes": 20,
      "instruments": [
        { "id": "guzheng", "name": "古筝", "role": "primary", "weight": 0.60 },
        { "id": "bianzhong", "name": "编钟", "role": "secondary", "weight": 0.30 },
        { "id": "guqin", "name": "古琴", "role": "harmony", "weight": 0.10 }
      ],
      "ambient_sound": { "id": "forest", "name": "森林鸟鸣", "volume": 0.12 },
      "mood": "平稳、安定，如大地包容",
      "scenario": "午后放松"
    }
  ],

  "prompt_template": {
    "template_id": "CN_V1",
    "template_version": "1.0.0",
    "parameters": {
      "day": 1,
      "duration": 15,
      "tone_weights": [
        { "tone_name": "角调式", "weight": 0.75 },
        { "tone_name": "宫调式", "weight": 0.15 },
        { "tone_name": "羽调式", "weight": 0.10 }
      ],
      "bpm": 68,
      "instruments": {
        "primary": "古筝",
        "secondary": "竹笛",
        "harmony": "古琴"
      },
      "ambient": "流水",
      "mood": "舒缓、清新",
      "scenario": "睡前放松"
    }
  },

  "explanation": {
    "summary": "主导情绪焦虑82分→怒→木→肝→角调。辅以宫调护脾胃（木克土），羽调滋水涵木。",
    "user_facing": "🎵 为什么推荐角调式？\n\n肝属木，五行对应角音。角调音乐像春风一样清新舒缓，能帮助您释放积压的情绪。\n\n📚 依据：《黄帝内经·素问·阴阳应象大论》",
    "warnings": ["本系统可信度为71%，仅供参考", "如有持续不适，建议咨询专业中医师"]
  },

  "confidence": 0.71,
  "reason": [
    "权重矩阵命中：角调0.75（规则引擎主推）",
    "生克选调：木克土 → 辅宫调0.15",
    "知识库检索：8篇文献，5篇支持角调为主",
    "BPM：证候中度 → 角调65-75区间取68"
  ],
  "processing_time_ms": 1800,
  "timestamp": "2026-07-12T10:00:08Z"
}
```

> **注意：Schema 里不存 `generated_prompt` 字符串。** 只存 `prompt_template_id` + `parameters`。Prompt 由独立的 Prompt Engine 在运行时组装。

---

## Agent ④ 音乐生成Agent

### 输入
Agent ③ 的 `daily_plan[day]` + `prompt_template`

### 输出 Schema

```json
{
  "agent_id": "generation_agent",
  "agent_version": "1.0.0",
  "user_id": "u_001",
  "session_id": "sess_20260712_001",
  "prescription_id": "rx_20260712_001",
  "day": 1,

  "audio": {
    "url": "https://oss.example.com/music/rx_20260712_001_day1.mp3",
    "duration_seconds": 912,
    "file_size_bytes": 7340032,
    "format": "mp3",
    "bitrate_kbps": 320
  },

  "actual_params": {
    "bpm": 68,
    "instruments_used": [
      { "id": "guzheng", "name": "古筝" },
      { "id": "zhudi", "name": "竹笛" },
      { "id": "guqin", "name": "古琴" }
    ],
    "prompt_template_used": "CN_V1",
    "prompt_sent": "请生成15分钟中国民族风纯音乐...",
    "prompt_truncated": false
  },

  "provider": {
    "name": "skymusic",
    "attempt_order": 1,
    "retry_count": 0,
    "degradation_triggered": false,
    "api_response_time_ms": 8234,
    "cost_cny": 0.20
  },

  "degradation_log": [
    {
      "attempt": 1,
      "provider": "skymusic",
      "status": "success",
      "latency_ms": 8234
    }
  ],

  "confidence": 1.0,
  "reason": ["天工SkyMusic首次调用成功", "音频时长912秒，符合预期"],
  "processing_time_ms": 8500,
  "timestamp": "2026-07-12T10:01:30Z"
}
```

---

## Agent ⑤ 用户反馈Agent

### 输入
Agent ④ 的 `audio.url` + 用户在APP上的反馈

### 输出 Schema

```json
{
  "agent_id": "feedback_agent",
  "agent_version": "1.0.0",
  "user_id": "u_001",
  "session_id": "sess_20260712_001",
  "prescription_id": "rx_20260712_001",
  "feedback_id": "fb_20260712_001",

  "feedback": {
    "subjective": {
      "overall_satisfaction": 4,
      "emotion_match": 5,
      "relaxation_feeling": 4,
      "sleep_improvement": 3,
      "stress_reduction": 4,
      "text_feedback": "听完之后胸口没那么闷了，很舒服"
    },

    "behavioral": {
      "completion_rate": 0.95,
      "replay_count": 1,
      "pause_count": 0,
      "skip_forward_count": 0,
      "listen_session": "bedtime",
      "average_volume": 0.65
    },

    "wearable": {
      "heart_rate": { "value": null, "unit": "bpm", "source": null },
      "hrv": { "value": null, "unit": "ms", "source": null },
      "sleep_duration": { "value": null, "unit": "minutes", "source": null },
      "sleep_score": { "value": null, "unit": "score", "source": null },
      "respiration": { "value": null, "unit": "rpm", "source": null }
    }
  },

  "decision": {
    "action": "continue",
    "action_detail": "用户满意度4分，维持当前处方参数，继续Day2方案",
    "next_step": "push_day2_prescription",
    "adjustments": null
  },

  "user_profile_update": {
    "preferred_instruments": [
      { "id": "guzheng", "name": "古筝", "score": 0.85, "occurrences": 3 },
      { "id": "zhudi", "name": "竹笛", "score": 0.70, "occurrences": 2 }
    ],
    "preferred_bpm_range": { "min": 65, "max": 70 },
    "preferred_session": "bedtime",
    "effective_syndrome_prescription": {
      "syndrome": "肝郁化火",
      "effective_tone_ids": ["jiao", "gong"],
      "effectiveness_score": 0.82
    }
  },

  "confidence": 0.88,
  "reason": [
    "整体满意度4分，情绪匹配5分",
    "完成率95%，重复播放1次",
    "文字反馈正面，用户报告'胸闷缓解'"
  ],
  "processing_time_ms": 120,
  "timestamp": "2026-07-12T22:30:01Z"
}
```

---

## 低满意度场景 Schema（action = "rediag"）

```json
{
  "agent_id": "feedback_agent",
  "agent_version": "1.0.0",

  "feedback": {
    "subjective": {
      "overall_satisfaction": 2,
      "emotion_match": 1,
      "relaxation_feeling": 2
    }
  },

  "decision": {
    "action": "rediag",
    "action_detail": "满意度2分且情绪匹配度1分，可能存在证型误判。触发重新辨证。",
    "next_step": "trigger_agent_2_rediag",
    "adjustments": {
      "reason": "用户反馈与预期效果严重不符",
      "trigger_rediag": true,
      "original_syndrome": "肝郁化火",
      "original_confidence": 0.71
    }
  },

  "confidence": 0.60,
  "reason": ["满意度2分，情绪匹配度极低(1分)", "建议重新辨证"],
  "processing_time_ms": 95,
  "timestamp": "2026-07-12T22:30:01Z"
}
```

---

## 满意度3分场景 Schema（action = "adjust"）

```json
{
  "decision": {
    "action": "adjust",
    "action_detail": "满意度3分，返回处方Agent微调BPM和乐器配比。",
    "next_step": "trigger_agent_3_adjust",
    "adjustments": {
      "reason": "用户认为节奏偏快",
      "trigger_rediag": false,
      "param_changes": {
        "bpm": { "from": 68, "to": 64 },
        "instruments_add": [{ "id": "xiao", "name": "箫" }]
      }
    }
  }
}
```

---

## Schema 衔接关系

```
① health_profile.emotion_scores ──→ ② 输入
② syndrome_diagnosis             ──→ ③ 输入
② search_keywords                ──→ ③ RAG检索关键词
② confidence.overall             ──→ ③ 可信度标记
③ daily_plan[day]                ──→ ④ 输入
③ prompt_template                ──→ ④ Prompt Engine 运行时组装
④ audio.url                      ──→ ⑤ 输入
⑤ decision.action                ──→ LangGraph Supervisor 调度
⑤ user_profile_update            ──→ 下次③的处方个人化
```

---

## 设计原则总结

| 原则 | 说明 |
|------|------|
| **每层说自己的语言** | ①不提音乐 / ②③不提采集 / ④⑤不提中医 |
| **对象优于字符串** | 乐器/调式/tone_weight 都用结构化对象 |
| **Prompt不入库** | Schema只存 template_id + parameters，运行时组装 |
| **每个Agent带五通用字段** | agent_id / version / confidence / reason / timestamp |
| **severity双字段** | severity_level(数字给AI) + severity_name(文字给前端) |
| **预留不空** | wearable等远期字段预留结构，值填null，不写死空对象 |
| **Schema即合约** | 团队其他成员据此写代码，改了要通知全员 |
