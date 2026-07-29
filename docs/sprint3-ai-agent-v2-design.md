# Sprint 3 AI Agent V2 联调交接包

> 分支：`codex/sprint3-ai-v2`
> 服务入口：`backend.ai_engine.real_workflow.run_real_workflow_v2`
> 当前仅提供 Python 服务层合同，尚未提供 V2 HTTP 路由。

## 1. 已实现链路

```text
Questionnaire V2 + 已确认病例文本 + 自由描述
  -> Assessment V2 -> 用户确认/安全门禁
  -> Diagnosis V2 -> Prescription V2
  -> 本地 Music 匹配
  -> 用户显式提交 Feedback V2
```

Sprint 3 采用增量 V2 模块，不替换 Sprint 2。旧 `run_real_workflow()` 及其默认四星反馈行为保持不变；V2 入口不会自动提交反馈。

## 2. 工作流调用合同

```python
run_real_workflow_v2(
    user_id="user-001",
    session_id="session-001",
    questionnaire_answers={...},       # Q1-Q12，必填
    assessment_confirmed=True,         # 必填
    document_id="document-001",        # 可选
    document_text="已确认的病例文本",    # 可选
    narrative_text="最近压力较大",       # 可选
    llm=fixed_or_qwen_provider,         # 可选
    knowledge_store=knowledge_store,    # 可选
    music_catalog=[...],                # 可选
    feedback_payload=None,              # 可选；默认不提交
    feedback_repository=None,           # 可选
)
```

调用方只应把已确认 OCR 内容放入 `document_text`。问卷由后端确定性重新计分。四种合法 `analysis_mode` 为：

- `questionnaire_only`
- `document_questionnaire`
- `narrative_questionnaire`
- `document_narrative_questionnaire`

`assessment_confirmed=false` 或安全状态为 `blocked_safety` 时，工作流在确认门禁停止，下游 Diagnosis、Prescription、Music 不运行。

## 3. Assessment V2

严格请求字段：

```json
{
  "session_id": "session-001",
  "user_id": "user-001",
  "document_id": "document-001",
  "document_text": "已确认的病例文本",
  "narrative_text": "最近压力较大",
  "questionnaire_answers": {
    "q01_mood_weather": "cloudy",
    "q02_tension_worry": 3,
    "q03_overthinking": 2,
    "q04_irritability_anger": 1,
    "q05_low_mood": 4,
    "q06_interest_loss": 0,
    "q07_fear_unease": 2,
    "q08_sleep_disturbance": 3,
    "q09_low_energy": 1,
    "q10_appetite_change": 2,
    "q11_daily_impact": 4,
    "q12_physical_safety": ["none"]
  }
}
```

核心响应字段：

```json
{
  "agent_id": "assessment_agent",
  "status": "success",
  "analysis_mode": "document_narrative_questionnaire",
  "sources_used": [],
  "emotion_profile": {
    "primary_states": [],
    "secondary_states": [],
    "dimension_scores": {},
    "tcm_emotion_candidates": []
  },
  "physical_profile": {},
  "life_events": {"triggers": []},
  "assessment_summary": "状态评估摘要",
  "extracted_evidence": [],
  "conflicts": [],
  "missing_information": [],
  "safety_flags": [],
  "degradation": {
    "triggered": false,
    "reason_code": null,
    "fallback": null
  },
  "warnings": [],
  "disclaimer": "非诊断声明"
}
```

LLM 不可用、超时或结构错误时，使用确定性问卷结果回退。用户可见警告使用可读中文；日志不得记录病例全文、自由描述全文、凭据或身份信息。

## 4. Music V2

本 Sprint 只匹配本地曲库，`source_type` 固定为 `matched`，不宣传为实时生成。

```json
{
  "agent_id": "music_agent",
  "legacy_alias": "generation_agent",
  "status": "success",
  "music_id": "music-jiao-01",
  "title": "Jiao Calm",
  "source_type": "matched",
  "stream_url": "/static/music/jiao-calm.wav",
  "mode": "角调",
  "bpm": 68,
  "duration_seconds": 900,
  "instruments": ["古筝", "古琴"],
  "ambient_sounds": [],
  "rights_note": "比赛演示授权曲目",
  "match_explanation": ["按处方调式和 BPM 匹配"],
  "fallback_music_id": null
}
```

不再对外使用 `track_id`、`audio_url`、`fallback_tracks` 或成功态 `generation_mode`。请求生成模式时返回 `MODE_NOT_AVAILABLE`。

## 5. Feedback V2

Feedback 必须由用户显式提交：

```json
{
  "schema_version": "feedback_v2.0",
  "session_id": "session-001",
  "prescription_id": "prescription-001",
  "music_id": "music-jiao-01",
  "pre_state": {
    "tension": 8,
    "body_tension": 7,
    "mental_fatigue": 6,
    "goal": "relax"
  },
  "post_state": {
    "tension": 3,
    "body_tension": 4,
    "mental_fatigue": 4,
    "change_label": "much_better"
  },
  "experience": {
    "overall_rating": 5,
    "relaxation_rating": 5,
    "music_match_rating": 4,
    "continue_use": "yes",
    "favorite": true,
    "disliked_features": [],
    "disliked_instruments": [],
    "comment": "感觉更放松"
  }
}
```

成功响应包含 `subjective_change`、`experience_summary`、`decision`、`personal_preference_patch`、`warnings`，且 `global_rule_update` 永远为 `false`。delta 的计算方式是“听后减听前”，因此负数表示对应主观评分下降。

反馈 ID 由 `session_id + prescription_id` 确定性生成。repository 必须提供原子接口：

```python
save_once(record, preference_patch) -> bool
```

首次保存返回 `True`，重复提交返回 `False`。无 `feedback_payload` 时工作流不会读取或探测 repository。

## 6. 前端与知识库联调要点

前端：

- 展示 `agent_statuses` 与 `degradations`，不要把 `degraded` 包装成成功；
- `needs_confirmation` 和 `blocked_safety` 时不展示普通音乐推荐；
- 使用 `music_id`、`stream_url`、`duration_seconds`；
- 使用“状态评估”“辅助辨证倾向”“音乐调养建议”，不得写成医学诊断或治疗。

知识库：

- 单一问卷维度不能直接决定证型、脏腑或调式；
- Chroma 不可用时只能回退到已审核本地规则，并展示降级；
- 所有用户文案保留“仅供音乐调养参考，不构成医学诊断”的边界。

## 7. 当前限制

- 尚无 V2 HTTP API、数据库迁移或前端页面；
- `SQLiteFeedbackStore` 仍没有 V2 所需的事务型 `save_once` 适配器；
- `result_id` 尚未写入 Feedback record，需要服务层建立关联；
- 当前只支持本地音乐匹配，不支持真实音乐生成。

## 8. 验收依据

- 全量测试：`309 passed`；
- Music/Feedback/Workflow 聚焦测试：`74 passed`；
- 固定离线工作流连续 10 次运行通过；
- Sprint 2 旧入口回归通过；
- `git diff --check` 通过；
- 未自动提交 Feedback，安全和确认门禁均有测试覆盖。
