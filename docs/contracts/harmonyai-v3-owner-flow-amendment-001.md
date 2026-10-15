# HarmonyAI V3 Owner Flow Amendment 001

> 日期：2026-08-26
> 状态：`OWNER_APPROVED_NOT_IMPLEMENTED`；Owner 于 2026-08-27 完成合同审核。该状态只批准合同，不表示业务代码已适配或验收通过。
> 基线：`origin/integration/sprint4-real-input@4a22b5fad75abf839d902fda6f35487d1865a9a8`
> 新流程标识：`v3-owner-flow-1`
> 范围：仅文档；不表示接口已部署、代码已适配或运行验收已通过。

## 1. 权威关系与开发门禁

本文件定向补充 [draft.3 主合同](harmonyai-v3-contract-freeze-v3.0.0-draft.3.md)，不重写历史冻结结果。合并后，仅在 `v3-owner-flow-1` 范围内优先于冲突的旧条款；未列出的 Evidence/Organ/Tone 类型、五 Agent 边界、RAG、GenerationSpec、反馈/偏好及隐私合同继续沿用。

配套 [前端 Read Model](frontend-read-model-contract-v3.md) 和 [持久化合同](harmonyai-v3-persistence-contract.md) 同步修订。旧 draft、Review、测试是历史证据，不能证明本修订已实现。

**本 PR 合并前，成员不要实施与旧合同冲突的生产改动。** 可继续无冲突基础工作与列出适配差异；保留已有成果，不要求重写。合并文档不等于切换运行时，须经过第 9 节 Gate。

## 2. 最终用户流程

| 项目 | 我有近期就诊资料 | 我没有近期就诊资料 |
|---|---|---|
| 上传资料 | 必填，OCR 必须成功 | 不要求 |
| 资料摘要确认 | 必填；允许修改后确认 | 不出现 |
| 最近情况（文字/语音） | 选填，可整步跳过 | 选填，可整步跳过 |
| 10 道五脏状态问卷 | 选填，可整份跳过 | 必填，提交全部10题 |
| 音乐目标 | 删除 | 删除 |
| 最终 Assessment 确认 | 1 次 | 1 次 |

有资料：入口 → 上传 → OCR → AI摘要 → 确认/修改摘要 → 可选最近情况 → 可选问卷 → 综合状态评估 → 唯一最终确认 → 音乐依据/生成/播放 → Feedback。

无资料：入口 → 可选最近情况 → 必填10题问卷 → 综合状态评估 → 唯一最终确认 → 音乐依据/生成/播放 → Feedback。

技术顺序：Information Understanding 整理来源；Agent1 先产出 Assessment，用户最终确认后，其**最新已确认 revision**进入 Agent2 → Agent3 → Agent4 → Agent5。不在确认后再生成一个未经确认的 Agent1 结果。资料摘要确认是来源确认，不替代最终确认；不再插入普通材料核验、普通冲突确认或音乐目标页面。

有效输入约束：

- 有资料必须引用本用户、本会话成功 OCR 及最新 confirmed CaseSummary；仅上传、空摘要、未确认内容不合格。
- 无资料必须有 approved manifest/checksum 对应的完整10题 submission。描述为空合法；不创建空 Narrative、伪 Understanding 或默认事实。
- 选填问卷是“不提交”或“完整有效提交”。部分草稿不作为证据、不按零分补齐；跳过时明确草稿未参与分析。
- 全选“无相关情况”的完整问卷仍是有效输入；有效不等于足以辨证。Diagnosis 可 abstain，后端按审核 fallback policy 决定保守音乐，不伪造证型。
- 有已确认有效资料时不因缺少选填来源阻断。真正无有效资料/问卷时返回补充，不造音乐依据。

## 3. OCR 失败、摘要确认与修改

### 3.1 OCR 失败

标题：**资料暂未识别成功**。

说明：我们暂时无法从这份资料中提取有效内容。你可以重新上传清晰的图片或PDF，也可以跳过本次资料，改用最近情况描述和10道状态问卷继续评估。

按钮：`重新上传资料` / `改用描述与问卷`。

提示：**自由描述可以跳过，10道状态问卷需要完成。**

失败、无有效文字或处理中均不进入摘要确认，也不向 Agent1 传失败/占位结果。重传生成新 document ID，旧来源保留失败审计但不再活动。OCR 成功但 AI 无法产出可确认摘要时也提供重试/重传/改用描述与问卷，不以空摘要假成功。

### 3.2 摘要确认

标题：**请确认资料摘要**。

说明：以下内容是系统根据你上传的资料整理出的简要信息。请确认它是否准确反映你的近期情况。

四个操作：

1. 主按钮：`内容基本准确，继续`。
2. 次按钮：`修改资料摘要`。
3. 次按钮：`重新上传资料`。
4. 弱按钮/链接：`改用描述与问卷`。

无法确认时提示：如果你暂时无法确认这份资料是否准确反映自己的近期情况，可以先修改摘要、重新上传，或通过最近情况和状态问卷继续。

### 3.3 修改摘要

提供可编辑的通俗摘要文本框，例如“资料中提到近期存在入睡困难、白天精神不足等情况。”不要求编辑复杂 OCR 原文。允许修正、添加或删除摘要事实；结构化字段是辅助，不能代替摘要文本框。

按钮：`保存修改并继续` / `取消修改`。保存表示提交修正并确认，成功后直接进入选填最近情况，**不再增加保存后的二次确认**。取消不写入、不增加 revision，回原摘要。

文本与事实必须一起更新，不能只改 presentation、继续用旧 Evidence。全文修改通过 Understanding 受控重新提取，明确字段修改可走 RevisionService。成功时原子保存 `revision+1` 完整快照与确认；提取/校验失败时保留编辑输入、停留本页，旧快照不变，不进入 Agent1。

保留原 OCR 的受控审计，修正事实标记 `user_correction`，不冒充医生/OCR原文。仍校验 Claim/来源/否定/时间范围，不扩展为用户未提供的医学结论。

### 3.4 弃用资料与竞争处理

`改用描述与问卷` 必须服务端切换为无资料模式，不是前端隐藏卡片。弃用资料、摘要及派生事实不能进入当前 Agent1、Agent2/RAG、Agent3或音乐依据。保留历史不可变快照，但不得继续作为活动引用。

重传/弃用递增活动输入版本；已有 Assessment 不再是当前结果。下游新任务拒绝旧引用，迟到 OCR 回调不能恢复弃用来源。无需删除已完成历史音乐。独立填写的描述/有效问卷可保留；混合了弃用资料的 Understanding 必须去除活动引用并重新整理保留来源。不能通过普通跳过/修正清除 Sprint4 已确认 Safety。

## 4. 版本与 API 增量（拟实施，非已部署）

维持 `/api/v3`，显式 session 合同版本区分新旧请求。旧客户端/旧V3/Sprint4不自动迁移。

### 4.1 Session 活动输入

新客户端创建 session 时请求 `flow_contract_version="v3-owner-flow-1"`；服务端部署后才接受，否则 HTTP 409 `FLOW_CONTRACT_UNSUPPORTED`，不能静默按旧流程执行。客户端不能提交 Safety policy 降级旧会话。

| 字段 | 类型 | 来源/约束 |
|---|---|---|
| `flow_contract_version` | string | 服务端确认、永久绑定 session |
| `input_mode` | with_document / without_document / null | 用户入口选择、服务端保存；null仅限初始未选入口，不能评估 |
| `input_revision` | integer >=1 | 来源替换、弃用、活动引用改变时递增 |
| `active_document_id` | string / null | 活动上传资源；失败资源可保留 ID 供重试，但不是有效来源 |
| `understanding_ref` | object / null | `{understanding_id, revision}`，纯问卷可 null |
| `questionnaire_ref` | object / null | draft.3 submission ID + schema identity，未提交为 null |

新增拟议 `POST /api/v3/sessions/{session_id}/input-transitions`，Auth、Idempotency-Key、所有权及 expected_input_revision 必须校验。动作：

- `select_mode`：仅初始无活动输入时使用，附 `input_mode`；session 创建后从 input_revision=1 开始。
- `replace_document`：附 `document_id`，必须本用户/本会话上传的新资源；模式变为 with_document，旧摘要失效。
- `discard_document`：不带 document_id；变为 without_document，移除资料派生的活动引用。

弃用示例；响应展示 envelope.data：

```json
{"expected_input_revision":2,"action":"discard_document"}
```

```json
{
  "session_id":"sess_xxx",
  "flow_contract_version":"v3-owner-flow-1",
  "input_mode":"without_document",
  "input_revision":3,
  "active_document_id":null,
  "understanding_ref":null,
  "questionnaire_ref":null
}
```

示例没有其他活动来源；已有独立描述/有效问卷可以保留。来源切换与引用更新在同一事务完成。问卷提交、来源确认/修正导致引用变化时也必须校验并递增 input_revision；UI 取响应版本，不自行加一。POST 同键同请求重试返回同一结果；同键异 payload 返回冲突。

### 4.2 Understanding 确认

仍使用 `POST /api/v3/understandings/{id}/confirmations`，新会话按 `understanding_v3.1` 判别验证，保留 expected_revision/decision/changes。

```json
{
  "schema_version":"understanding_v3.1",
  "expected_revision":1,
  "expected_input_revision":2,
  "decision":"confirm_with_changes",
  "changes":[],
  "edited_summary_text":"资料中提到最近入睡较慢，白天有些疲惫。",
  "reprocess_requested":true
}
```

- edited_summary_text：去空白后1..2000字符，仅 confirm_with_changes 使用，是 PUBLIC 本人编辑内容。全文修改时 changes 必须为空，避免两套冲突修正；reprocess_requested 必须 true。
- 结构化修正不带 edited_summary_text，reprocess_requested=false，changes 沿用原字段/类型白名单，不允许改器官权重/Safety。
- 两个 expected 版本均校验；HTTP 409 `REVISION_CONFLICT` / `INPUT_REVISION_CONFLICT`。
- 提取与验证成功后原子确认新 revision，返回最新 Understanding Read Model 与 input_revision；失败不发布半成品 revision。
- 基本准确使用 decision=confirm，无文本修改、不额外调用 LLM。新文字才触发受控提取，不声称所有修正重跑五 Agent。
- 新流程弃用/重传统一走 input-transitions；不以 reject_source/cannot_confirm 得到一个可用的空确认。旧接口行为保留。

### 4.3 Assessment V3.1

`POST /api/v3/assessments`：无资料且描述跳过时允许如下输入。

```json
{
  "schema_version":"assessment_v3.1",
  "session_id":"sess_xxx",
  "expected_input_revision":3,
  "understanding_ref":null,
  "questionnaire_ref":{
    "questionnaire_submission_id":"qsub_xxx",
    "schema_id":"questionnaire_v3",
    "schema_version":"3.0.0",
    "manifest_version":"medical_v3.0",
    "content_checksum":"sha256:approved-manifest-checksum"
  }
}
```

checksum 是形状占位，真实值必须取批准 manifest。questionnaire_ref 沿用 draft.3 字段集。

7天窗口与10题完整性从该submission的持久化数据验证，不在资源引用中新增time_window_days。不能把questionnaire_submission_id另起名为submission_id。

- understanding_ref 可空；有资料模式必须指向包含成功资料的最新 confirmed CaseSummary；无资料允许纯问卷。
- questionnaire_ref 可空；无资料必填且10题完整，有资料选填。
- expected_input_revision 必填并匹配服务端；引用必须属于本用户/会话及活动来源集。
- user_goal/music_goal 在新输入禁止（extra=forbid），不补默认 sleep/relaxation。
- 输出保留 assessment_id/revision/status、事实/器官证据、profile、确认及降级结构；schema_version=assessment_v3.1，understanding_ref 可 null，新增服务端 flow_contract_version/input_revision，Safety 按第6节，移除 presentation.goal_summary 等目标字段。
- 最终确认仍调用 assessments/{id}/confirmations；新请求带 expected_input_revision，响应最新 assessment revision。之后仅最新已确认 revision 可进 Diagnosis。

### 4.4 Agent2～5

- Agent2 使用 diagnosis_v3.1，上游 assessment_ref 指向最新已确认 Assessment，并校验 input_revision/policy。RAG+Qwen+Schema/Rule Check、Fact引用及abstain规则不改。
- Agent3 使用 prescription_v3.1，删除输入 user_goal。沿用 diagnosis_id 和服务端 preference_snapshot；参数来自已确认状态、审核映射/fallback与历史偏好，不能伪造本次用户目标。
- Agent4 的 GenerationSpec/Provider边界不改，不新增 UserGoal，不把弃用 OCR 送入 Prompt；只消费权威有效处方。
- Agent5 不改反馈/偏好合同；历史偏好不是本次目标，不能暗中替代目标字段。
- Understanding/Assessment/Diagnosis/Prescription 新判别版本只适用新 session；未变的 Evidence/GenerationSpec/Music DTO 保持原版本，禁止新版 payload 冒充旧v3.0。

## 5. 删除音乐目标的完整边界

| 层 | 新流程要求 |
|---|---|
| 页面 | 移除目标入口/独立页/确认页目标卡片，不塞回10题问卷 |
| DTO | 删除 UserGoal 输入输出依赖；新版带旧目标字段拒绝，不静默接受 |
| Agent3 | 不要求 primary_goal/secondary_goal/custom_goal_text，不编造默认目标 |
| DB | 历史值保留；新合同行 user_goal_json=null，不因旧 NOT NULL 填假值 |
| 验收 | 无目标可完成两条路径，无隐藏必填或相关422 |
| 兼容 | 不删 Sprint4 Q1、V2.1/V2.2 字段/测试或旧V3快照 |

## 6. V3 Safety 暂缓与 Sprint4 兼容

这是 Owner 选择暂缓接入的功能限制，不是 Safety 已通过或风险不存在。新流程不运行专用 Safety 检测/核验/支持分流，不出现 Q19/Q20、Safety Verification、Safety Support、Comfort Audio 必经步骤；资料按普通来源规则处理，不自动转入 Sprint4 Safety。

必须按 session 分离，不能全局关闭：

| 场景 | 规则 |
|---|---|
| 新 v3-owner-flow-1 session | 服务端绑定 deferred_v3；不执行独立 Safety pipeline |
| Sprint4 / 旧 V3 session | 保留原 detector、状态机、路由、风险门禁；不自动换 policy |
| 旧 confirmed risk | 原记录/限制不变；普通跳过、修正、反馈不能写 clear/resolved |
| 切换版本继续旧风险会话 | 拒绝原地切换，409 FLOW_CONTRACT_MISMATCH；不把旧风险资源复制成未筛查新资源 |

新 Understanding/Assessment 及 Agent2 上下文的服务端字段（内部/传输，不直接展示）：

```json
{
  "flow_contract_version":"v3-owner-flow-1",
  "safety_policy":"deferred_v3",
  "safety_evaluation_status":"not_run",
  "safety_status":null
}
```

新 policy 下 status 必须 null，不输出 clear/resolved、不声明无风险；旧 SafetyStatus 枚举不增加 not_run 或改变语义。Agent2/3 先验证服务端 policy 与 session，再执行对应合同，不能直接把 null 套进旧非clear gate导致永久阻塞。未知版本/policy 拒绝；客户端不能省略状态放行。

新版不以“Safety未执行”设额外音乐门禁，但有效输入、用户确认、医学生产审批、所有权、后端处方权威仍有效。保留非诊断/非治疗免责声明；不能宣称本版本适用于高风险人群或可替代专业服务。汇报明确“V3专用Safety暂未接入”，验收记 DEFERRED/NOT_RUN 而非PASS。将来启用须另行 Owner 决策、修订与测试；不删除 Sprint4 能力/数据/API/测试。

## 7. 历史冲突关闭表

| 历史位置 | 冲突 | 新依据 |
|---|---|---|
| 主合同§2.5/4.1/6.1/9 | UserGoal 必需 | §5删除新版，保留旧版 |
| 主合同§4.1 | 无资料要求 Narrative/Voice | §2/4.3纯问卷、understanding_ref=null |
| 主合同§3.7 | 摘要全文修正/确认未闭合 | §3.3/4.2原子修正确认 |
| 主合同§3.2/3.8/5.5/6.2/10 | 所有V3运行Safety gate | §6版本隔离，不改历史 |
| 前端§3～9/12/15～16 | 旧入口、目标、安全页及必填性 | 同步配套文档 |
| DB understanding/assessment | 旧NOT NULL约束 | 同步持久化，不补假对象/目标/安全 |
| Sprint5验收模板 | 旧无资料/Safety流程 | 新版验收+Sprint4兼容，历史证据保留 |

## 8. 团队适配责任

| 成员 / Issue | 适配与验收重点 |
|---|---|
| 陈家智 / #81 | 文档PR审核、版本优先级、集成门禁；DTO/DB/前端一起适配后启用，不先独立切入口 |
| 肖宇翔 / #77 | 10题医学审核不变；资料分支选填，纯问卷有效；不把跳过当阴性 |
| 钟睿宸 / #78 | nullable Understanding、摘要修改事实、活动来源、Agent1/2/3去目标与policy；弃用来源不进RAG |
| 蔡子鑫 / #79 | session/input-transitions、所有权/幂等/revision、判别API、双数据库兼容迁移 |
| 彭翔 / #80 | 两入口、失败分流、摘要四操作与文本编辑、选填/必填、无目标/独立Safety页、单一最终确认 |

API厂商/预算/账号与医学生产审批沿用已有Issue决定；本文不新增供应商授权，也不替代成员Review。

## 9. 实施验收（目前全部 NOT_RUN）

| ID | 必测条件 |
|---|---|
| FLOW-01 | 有资料成功/摘要确认，描述与问卷都跳过，正常进入最终确认及音乐出口 |
| FLOW-02 | 无资料跳过描述，完整10题正常；未完成不能提交Agent1 |
| FLOW-03 | 选填问卷可整份跳过；部分草稿不作为有效submission |
| FLOW-04 | OCR失败不进摘要/Agent1；重传有效；改描述问卷后10题必填 |
| FLOW-05 | 摘要四操作；全文修正更新事实；成功确认新revision、失败保留编辑且不改旧版 |
| FLOW-06 | 弃用/重传后旧来源、迟到回调与旧下游引用不能用于新生成 |
| FLOW-07 | 无音乐目标UI/依赖/假默认；新版拒绝旧目标字段，旧版兼容 |
| FLOW-08 | Agent1先评估、唯一最终确认，最新已确认revision交Agent2 |
| FLOW-09 | 新policy为deferred_v3/not_run/null，无专用Safety分流；客户端policy绕过/未知版本被拒绝 |
| FLOW-10 | Sprint4 Q19/Q20/风险门禁回归不变，普通确认不能清风险；旧V3不降级 |
| FLOW-11 | SQLite/MySQL新旧数据、FK/所有权、迁移ledger、乐观锁/幂等正确 |
| FLOW-12 | 医学生产审批、Provider/fallback真实性、隐私/非诊断免责声明继续成立 |

文档PR只验证链接、JSON示例、差异与范围；不跑Formal60、不以历史全绿宣称新版PASS。实施证据进入 [验收报告](../sprint5/sprint5-acceptance-report.md) 和 [人工Gate](../sprint5/sprint5-manual-gates.md)。
