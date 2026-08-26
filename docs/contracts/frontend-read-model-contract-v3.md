# HarmonyAI V3 Frontend Read Model Contract

> 版本：`draft.3 + owner-flow-amendment-001`
> 状态：`PENDING_OWNER_REVIEW`；本修订未表示页面/API已实现。
> 权威：[Owner Flow Amendment 001](harmonyai-v3-owner-flow-amendment-001.md) 优先于 [历史 draft.3](harmonyai-v3-contract-freeze-v3.0.0-draft.3.md) 的冲突条款。
> 目标：保证 Client Engineer 只依赖稳定 Read Model 完成全部 V3 页面，不读取 Agent 内部对象。

## 1. 客户端边界

1. 页面只消费本合同的 Read Model，不直接渲染 `FactEvidence`、`OrganEvidenceLink`、RAG hit、Provider metadata 或数据库行。
2. `resource_id/revision/task_id/status/safety_status` 可以传到客户端完成流程，但属于 `NOT_USER_VISIBLE`。
3. 客户端不得显示内部 enum、Coverage、模型置信度、检索分数、Prompt 或 Provider 原始错误。
4. 所有用户文案由后端 `presentation` 或前端稳定 error-code 映射提供。
5. Client 提交的 `user_id` 无效；身份来自 Auth Context。
6. 本文新页面只适用服务端已接受的 `flow_contract_version=v3-owner-flow-1`。旧 V3/Sprint4 页面保持原合同；前端不能把旧session改成新版本或自行设置Safety policy。

## 2. Common Types

```ts
type ResourceRef = { id: string; revision?: number };
type Action = {
  id: string;
  label: string;
  style: "primary" | "secondary" | "danger" | "link";
  enabled: boolean;
  endpoint?: string;
  method?: "GET" | "POST" | "PATCH" | "DELETE";
};
type UiError = {
  code: string;
  title: string;
  message: string;
  retryable: boolean;
  actions: Action[];
};
type EditableValue =
  | { type: "text"; value: string }
  | { type: "severity"; value: "none" | "mild" | "moderate" | "severe" }
  | { type: "boolean"; value: boolean };
type EditableItem = {
  target_id: string;       // NOT_USER_VISIBLE，提交修正使用
  label: string;           // PUBLIC
  value: EditableValue;
  allowed_values?: string[];
  max_length?: number;
  required: boolean;
};
type PageState = "idle" | "loading" | "ready" | "empty" | "degraded" | "failed";
```

字段命名在 JSON 中保持 snake_case。TypeScript 示例只表达类型，不授权前端构造后端对象。`target_id` 必须由后端生成且只用于提交，不得直接显示。

应用启动且无有效身份时先调用 `POST /api/v3/auth/guest`：

```json
{
  "access_token":"opaque-or-signed-token",
  "token_type":"Bearer",
  "expires_at":"2026-08-23T08:00:00Z",
  "public_user_id":"u_guest_xxx"
}
```

该结果不是页面 Read Model。`access_token` 只能放入安全客户端存储并作为 Bearer token 发送，不得显示、写普通日志或放入 URL；随后才能创建业务 Session。过期/无效 token 走 `UNAUTHENTICATED`，不得回退固定 `user_id`。
## 3. Start / Input Flow

### 3.1 EntryReadModel

```json
{
  "page":"entry",
  "session_id":"sess_xxx",
  "title":"开始了解你最近的状态",
  "description":"请选择是否有近期就诊资料。没有资料也可以通过状态问卷开始。",
  "choices":[
    {"id":"with_document","label":"我有近期就诊资料","next_route":"/v3/material"},
    {"id":"without_document","label":"我没有近期就诊资料","next_route":"/v3/narrative"}
  ]
}
```

### 3.2 SourceStatusReadModel

```json
{
  "source_id":"doc_xxx",
  "source_type":"document",
  "state":"processing",
  "label":"正在识别资料",
  "message":"通常需要几秒钟。",
  "can_skip":false,
  "actions":[{"id":"discard_document","label":"改用描述与问卷","style":"secondary","enabled":true,"endpoint":"/api/v3/sessions/sess_xxx/input-transitions","method":"POST"}]
}
```

状态：`uploading | processing | needs_confirmation | ready | degraded | failed | skipped`。OCR失败必须区分“未提供”和“已提供但识别失败”。

有资料模式不能用普通skip跳过必需资料；discard_document 成功后才切换无资料模式。失败页标题“资料暂未识别成功”，文案及两个按钮严格使用 Amendment §3.1；旁注“自由描述可以跳过，10道状态问卷需要完成”。失败不进入摘要或Agent1。后端未完成切换时留在当前页、允许重试，不先导航造成旧资料残留。

每个流程 Read Model 额外携带服务端 `flow_contract_version`、`input_mode`、`input_revision`（NOT_USER_VISIBLE，下面页面示例省略这些通用字段）。来源更改请求带 expected_input_revision，成功后使用响应的新版本。未知合同错误不能自动退回旧目标页。

## 4. Case Summary Page

```json
{
  "page":"case_summary",
  "understanding_id":"und_xxx",
  "revision":1,
  "status":"needs_confirmation",
  "title":"请确认资料摘要",
  "summary":"材料中提到近期睡眠恢复不足。",
  "editable_fields":[
    {
      "target_id":"fact_sleep_xxx",
      "label":"睡眠情况",
      "value":{"type":"text","value":"近期睡眠恢复不足"},
      "max_length":300,
      "required":false
    }
  ],
  "source_notice":"以下内容是系统根据你上传的资料整理出的简要信息。请确认它是否准确反映你的近期情况。",
  "warnings":[],
  "actions":[
    {"id":"confirm","label":"内容基本准确，继续","style":"primary","enabled":true,"endpoint":"/api/v3/understandings/und_xxx/confirmations","method":"POST"},
    {"id":"edit","label":"修改资料摘要","style":"secondary","enabled":true},
    {"id":"reupload","label":"重新上传资料","style":"secondary","enabled":true},
    {"id":"discard_document","label":"改用描述与问卷","style":"link","enabled":true,"endpoint":"/api/v3/sessions/sess_xxx/input-transitions","method":"POST"}
  ]
}
```

基本准确提交 `schema_version=understanding_v3.1 + expected_revision + expected_input_revision + decision=confirm + changes=[]`。结构化changes沿用旧 target_id/old_value/new_value；全文修改按 Amendment §4.2。页面不展示 OCR Provider、raw confidence 或原始异常。

编辑状态增加 `summary_editor={value:string,max_length:2000,required:true}`，value初始化为当前summary，显示通俗文本框；可修改、添加、删除事实。按钮“保存修改并继续”“取消修改”。保存提交 edited_summary_text/reprocess_requested=true，提取校验和确认成功后直接进最近情况；失败保留输入、不改旧版本、不增加二次确认页。取消恢复原摘要、不提交。重新上传先取得新document ID再执行replace_document，原摘要不得继续被使用。
## 5. Narrative / Voice Page

```json
{
  "page":"state_expression",
  "title":"说说最近发生了什么",
  "prompt":"可以写下最近的事情、感受、睡眠或身体状态，不需要先判断自己的情绪。",
  "text_input":{"enabled":true,"required":false,"max_length":2000},
  "voice_input":{"enabled":true,"max_duration_seconds":180,"status":"available"},
  "transcript":{
    "transcript_id":"tr_xxx",
    "revision":1,
    "status":"needs_confirmation",
    "text":"最近总是睡不好。",
    "editable":true
  },
  "actions":[
    {"id":"continue","label":"继续","style":"primary","enabled":true},
    {"id":"skip_narrative","label":"暂不填写，继续","style":"link","enabled":true}
  ]
}
```

ASR unavailable 时 `voice_input.status=unavailable` 并保留文字输入；不得把“已输入但AI暂不可用”显示成“未提供”。

### 5.1 选填与音乐目标删除

两条路径的文字/语音均选填；跳过不创建空Understanding。用户主动录音后可编辑/确认转写，但不录音不强制出现转写页。新版无音乐目标页面、UserGoal输入、目标卡片或隐藏必填；历史Sprint4页面不删除。

## 6. QuestionnaireReadModel

数据来自 `GET /api/v3/questionnaire/schema`，前端不得内置另一套题目、分值或器官映射。

```json
{
  "page":"questionnaire_v3",
  "schema_id":"questionnaire_v3",
  "schema_version":"3.0.0",
  "manifest_version":"medical_v3.0",
  "content_checksum":"sha256:...",
  "time_window":"past_7_days",
  "review_status":"approved",
  "time_window_days":7,
  "title":"五脏状态问卷",
  "question_count":10,
  "required_for_flow":false,
  "skip_action":{"id":"skip_questionnaire","label":"跳过问卷，继续评估","style":"link","enabled":true},
  "estimated_minutes":3,
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
  "progress":{"current":1,"total":10},
  "submit_action":{"id":"submit","label":"提交问卷","style":"primary","enabled":false,"endpoint":"/api/v3/questionnaire/submissions","method":"POST"}
}
```

`answer_type` 只允许 `multi_choice_evidence | single_choice_evidence | frequency_0_4`。选择题 options 使用 `option_code/claim_code/is_none/exclusive_with`；频率题 value 为0..4整数。示例只表达Schema形状，不代表医学内容已批准。生产 Manifest 必须恰好10题、`review_status=approved` 且 checksum 匹配；提交带 schema identity、7天窗口、answers 与 Idempotency-Key。过期 checksum 返回 `QUESTIONNAIRE_SCHEMA_STALE` 并要求刷新，不能静默按新题目解释旧答案。

V3普通页面不含Q19/Q20；这不授权删除后端Safety能力。问卷选择值以Schema code提交，页面只显示审核文案。

上述 required_for_flow/skip_action 是有资料且摘要已确认的示例。无资料（包括弃用资料）必须 required_for_flow=true、skip_action=null；描述可跳过但问卷不可跳过。它们由session权威模式生成，不改题目级required。资料模式问卷可整份跳过，未提交草稿不作为有效来源；一旦提交必须完整10题。Questionnaire schema本体仍是审核manifest，流程字段由Read Model组合层附加。
## 7. Understanding Processing

```json
{
  "page":"understanding_progress",
  "understanding_id":"und_xxx",
  "state":"loading",
  "title":"正在整理你的信息",
  "steps":[
    {"id":"document","label":"材料内容","status":"complete"},
    {"id":"narrative","label":"最近情况","status":"complete"},
    {"id":"facts","label":"状态整理","status":"running"}
  ],
  "message":"请稍候，我们正在生成可供你确认的摘要。",
  "poll_after_ms":1500,
  "error":null
}
```

步骤状态只允许 `pending | running | complete | failed | skipped`。某来源 failed 时页面必须显示安全文案和可用的文字/问卷降级操作，不得显示 Provider 原始异常。

纯问卷模式不创建understanding_id或展示伪Understanding进度，直接进入Agent1评估加载状态。可选来源跳过不写complete/100%。
## 8. Final Assessment Confirmation

```json
{
  "page":"assessment_confirmation",
  "assessment_id":"asmt_xxx",
  "revision":1,
  "status":"needs_confirmation",
  "safety_policy":"deferred_v3",
  "safety_evaluation_status":"not_run",
  "safety_status":null,
  "title":"确认一下我们对你当前状态的理解",
  "summary":"近期主要表现为思虑增多、睡眠恢复不足和精力下降。",
  "sections":[
    {"id":"body","title":"身体感受","items":["睡眠恢复不足","白天精力下降"]},
    {"id":"context","title":"最近情况","items":["近期学习安排带来压力"]}
  ],
  "editable_items":[
    {"target_id":"fev_xxx","label":"睡眠恢复不足","value":{"type":"severity","value":"moderate"},"allowed_values":["none","mild","moderate","severe"],"required":false}
  ],
  "degradation_notice":null,
  "actions":[
    {"id":"confirm","label":"基本符合，继续","style":"primary","enabled":true,"endpoint":"/api/v3/assessments/asmt_xxx/confirmations","method":"POST"},
    {"id":"correct","label":"有些地方不对，我要修改","style":"secondary","enabled":true}
  ]
}
```

修正提交必须带 `expected_revision` 与 changes[]；成功响应返回 `revision+1` 的完整 Assessment Read Model。禁止字段：`evidence_coverage`、`source_diversity`、`provider_metadata`、内部 enum、原始 Evidence ID列表、模型置信度。`assessment_id/revision/safety_status/target_id` 只用于路由和提交。

新合同确认同时带expected_input_revision。未提供最近情况时省略context或显示“未填写”，不能生成虚构经历。Safety policy/status不显示，不能渲染“已确认安全”。普通最终确认只有一次；Agent1先生成本页数据，确认后的最新revision再进入Agent2。
## 9. V3 Safety 暂缓（不是已通过）

新流程不接入专用Safety检测/核验/支持/安抚音频页面；不存在独立Safety路由或以此为前提的继续按钮。按 Amendment §6 保存 deferred_v3/not_run/null，页面不显示这些技术字段，也不能显示“无风险”。

旧V3与Sprint4的Safety页面、Q19/Q20和风险门禁保留在其原版本。新旧路由不能共用一个全局关闭开关；普通确认/跳过资料/反馈不能清除旧会话风险。若收到旧资源或合同不匹配，返回版本错误并停止该请求，不把用户重定向到一个伪造的clear状态。后续启用V3 Safety须新的Owner决策。
## 10. Diagnosis / Generation Basis

```json
{
  "page":"music_basis",
  "diagnosis_id":"diag_xxx",
  "prescription_id":"rx_xxx",
  "title":"本次音乐生成依据",
  "tendency":{"label":"心脾两虚倾向","disclaimer":"仅用于音乐调养参考，不构成医学诊断。"},
  "basis_summaries":["反复思虑","睡眠恢复不足","精力下降"],
  "tone_profile":{
    "dominant_tone":"gong",
    "dominant_label":"宫音",
    "summary":"本次以宫音为主。"
  },
  "music_parameters":{
    "bpm":58,
    "duration_seconds":900,
    "instrument_labels":["古琴","洞箫"],
    "ambient_labels":["流水"]
  },
  "personalization_summary":"已参考你过去的音乐偏好。",
  "actions":[{"id":"generate","label":"生成本次音乐","style":"primary","enabled":true}]
}
```

不展示候选分数、RAG检索分数、Provider名称或医学规则ID。

## 11. Music Generation Progress

```json
{
  "page":"music_generation",
  "task_id":"task_xxx",
  "status":"running",
  "title":"正在生成音乐",
  "progress":{"value":50,"indeterminate":false},
  "message":"正在根据本次音乐参数生成。",
  "poll_after_ms":2000,
  "can_cancel":true,
  "actions":[{"id":"cancel","label":"取消生成","style":"secondary","enabled":true}]
}
```

状态：`queued | running | succeeded | matched_fallback | failed | cancelled`。Provider不报告进度时用不定进度，不伪造百分比。Fallback 必须明确“使用审核曲库匹配”，不能伪装实时生成。

## 12. PlayerReadModel

```json
{
  "page":"player",
  "music_ref":{"music_id":"asset_xxx","source_type":"generated"},
  "title":"宫调·静心",
  "stream_url":"/api/v3/music/assets/asset_xxx/stream",
  "duration_seconds":900,
  "source_label":"AI生成音乐",
  "tone_label":"宫音为主",
  "instrument_labels":["古琴","洞箫"],
  "controls":{"play":true,"pause":true,"seek":true,"favorite":true},
  "favorite":false,
  "disclaimer":"音乐调养不能替代专业医疗或心理帮助。"
}
```

缺失stream_url或Prescription withheld时，前端不得构造处方或请求生成。服务端按session policy判定可用性：新版不能把safety_status=null误判为风险阻断，旧版非clear/resolved仍执行原门禁。Diagnosis abstained由Agent3决定emotion_based/wellness；有效fallback处方/资产可播放，但不得伪装辨证音乐。

## 13. FeedbackReadModel

```json
{
  "page":"feedback",
  "music_ref":{"music_id":"asset_xxx","source_type":"generated"},
  "pre_state_snapshot":{"snapshot_id":"qs_xxx","source":"player_session","captured_at":"2026-08-22T08:45:00Z","tension":6,"fatigue":7},
  "required_fields":["post_state.change_label"],
  "change_options":[
    {"value":"much_better","label":"明显好一些"},
    {"value":"slightly_better","label":"稍微好一些"},
    {"value":"no_change","label":"差不多"},
    {"value":"worse","label":"感觉更不舒服"}
  ],
  "post_state_fields":{"tension":{"required":false,"min":0,"max":10},"fatigue":{"required":false,"min":0,"max":10}},
  "continue_use_options":[{"value":"yes","label":"愿意"},{"value":"maybe","label":"可以考虑"},{"value":"no","label":"暂时不愿意"}],
  "liked_feature_options":[{"value":"guqin_timbre","label":"古琴音色"},{"value":"gentle_rhythm","label":"节奏舒缓"},{"value":"ambient_sound","label":"环境音"},{"value":"duration_fit","label":"音乐时长"},{"value":"overall_relaxing","label":"整体氛围"}],
  "adjustment_options":[{"value":"slower_tempo","label":"节奏更慢"},{"value":"faster_tempo","label":"节奏更快"},{"value":"change_instruments","label":"更换乐器"},{"value":"adjust_volume","label":"调整音量"},{"value":"adjust_ambient","label":"调整环境音"},{"value":"shorter_duration","label":"缩短时长"},{"value":"longer_duration","label":"延长时长"}],
  "mutual_exclusion_groups":[
    ["slower_tempo","faster_tempo"],
    ["shorter_duration","longer_duration"]
  ],
  "comment":{"required":false,"max_length":500},
  "submit_action":{"id":"submit_feedback","label":"提交反馈","style":"primary","enabled":false,"endpoint":"/api/v3/feedback","method":"POST"}
}
```

除状态变化外均选填。`pre_state_snapshot` 来自播放器开始前的权威快照，不允许前端伪造疗效差值；前端和后端都必须阻止冲突调整组合。提交成功响应必须包含 `feedback_id` 与 preference_update 结果。
## 14. Personal Profile / History / Favorites

### 14.1 ProfileReadModel

```json
{
  "page":"profile",
  "updated_at":"2026-08-22T09:00:00Z",
  "user":{"avatar_url":"/static/avatars/default.png","nickname":"用户"},
  "stats":{"history_count":8,"favorite_count":3,"feedback_count":6},
  "preference_summary":{
    "instrument_labels":["古琴"],
    "feature_labels":["节奏舒缓"],
    "ambient_labels":["流水"],
    "description":"你较常选择古琴和舒缓节奏。"
  },
  "actions":[
    {"id":"history","label":"生成记录","style":"secondary","enabled":true},
    {"id":"favorites","label":"我的收藏","style":"secondary","enabled":true},
    {"id":"reset_preferences","label":"重置音乐偏好","style":"link","enabled":true,"endpoint":"/api/v3/me/preferences/reset","method":"POST"}
  ]
}
```

### 14.2 MusicHistoryReadModel

```json
{
  "items":[
    {
      "music_ref":{"music_id":"asset_xxx","source_type":"generated"},
      "title":"宫调·静心",
      "created_at":"2026-08-22T09:00:00Z",
      "duration_seconds":900,
      "source_label":"AI生成音乐",
      "favorite":true,
      "playable":true
    }
  ],
  "next_cursor":null
}
```

收藏列表复用相同 Item。历史和收藏必须分页；删除/撤销收藏使用 `music_ref`，不使用数组位置。

## 15. Error / Degradation Mapping

| Error code | 页面文案 | 操作 |
|---|---|---|
| `UNAUTHENTICATED` | 登录状态已失效 | 重新登录/游客继续 |
| `RESOURCE_NOT_FOUND` | 当前内容不存在或不可访问 | 返回上一页 |
| `OCR_UNAVAILABLE` | 资料暂未识别成功 | 重新上传资料 / 改用描述与问卷（描述选填，10题必填） |
| `FLOW_CONTRACT_UNSUPPORTED` | 当前服务尚未支持此流程 | 稍后重试，不按旧合同静默提交 |
| `FLOW_CONTRACT_MISMATCH` | 当前记录不属于此流程版本 | 停止请求，返回原版本记录入口 |
| `INPUT_REVISION_CONFLICT` | 资料已更新，请刷新后继续 | 刷新当前活动来源，不能重用旧资料 |
| `ASR_UNAVAILABLE` | 语音识别暂时不可用，可直接输入文字 | 切换文字 |
| `QUESTIONNAIRE_SCHEMA_STALE` | 问卷已更新，请刷新后重新填写 | 刷新问卷 |
| `MEDICAL_ASSET_UNAVAILABLE` | 医学内容尚未就绪，当前不能完成正式状态评估 | 稍后重试/返回 |
| `REVISION_CONFLICT` | 内容已更新，请刷新后再确认 | 刷新 |
| `SAFETY_BLOCKED`（仅旧版本） | 当前不会提供个性化音乐服务 | 原版本安全支持；新流程不借此隐式接入Safety |
| `INSUFFICIENT_EVIDENCE` | 还需要补充少量信息 | 返回补充/保守非诊断路径 |
| `DIAGNOSIS_ABSTAINED` | 当前没有形成明确辨证倾向，将使用较保守的音乐方式 | 等待/展示后端 `emotion_based` 或 `wellness` 结果；仅真实无数据时返回补充 |
| `PRESCRIPTION_WITHHELD` | 当前还不能提供音乐建议 | 按后端原因补充/确认/重试；新版不默认跳Safety Support |
| `PROVIDER_AUTH_FAILED` | 智能分析服务暂时不可用 | 使用降级结果/稍后重试 |
| `PROVIDER_RATE_LIMITED` | 当前请求较多，请稍后重试 | 重试 |
| `PROVIDER_TIMEOUT` | 智能分析暂未完成 | 重试/使用降级结果 |
| `GENERATION_PROVIDER_UNAVAILABLE` | 生成服务暂时不可用 | 重试/审核曲库fallback |
| `NO_PLAYABLE_ASSET` | 当前没有可播放音频 | 返回音乐依据页 |

Raw provider exception、Provider名称和密钥信息不得进入UI。按session合同消费后端权威状态；前端不得自行放行或伪造Safety clear。
## 16. Client Freeze Checklist

- [ ] 每页数据只来自对应 Read Model。
- [ ] ID/revision/task状态/target_id可以传输但不显示。
- [ ] 病例摘要、语音、Assessment 修正均有 optimistic concurrency。
- [ ] Questionnaire包含真实10题 Schema、checksum、7天窗口和stale处理。
- [ ] 普通流程只有一次最终 Assessment Confirmation。
- [ ] 两路径描述选填；有资料问卷选填、无资料10题必填；不造空Understanding。
- [ ] OCR失败不进摘要；弃用/重传服务端更新input_revision，旧来源不再参与分析。
- [ ] 摘要有四操作和可编辑通俗文本；保存即修正并确认，无新增确认门。
- [ ] 无音乐目标页面/请求/展示依赖。
- [ ] 新流程Safety暂缓且不伪造clear；Sprint4原Safety能力保留，旧风险不可由普通确认解除。
- [ ] Understanding、生成进度、失败、fallback和Player均有明确状态。
- [ ] Feedback具有权威听前快照、选填听后状态和feedback_id响应。
- [ ] Profile、History、Favorites 字段完整且支持分页。
- [ ] 页面不显示内部 enum、Coverage、置信度、检索分数或原始异常。
