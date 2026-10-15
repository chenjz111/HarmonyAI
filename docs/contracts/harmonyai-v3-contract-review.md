# HarmonyAI V3 Contract Freeze Review

> Review 基线：`origin/integration/sprint4-real-input@709e4decef4e7c77ed55f5e548eec7809fc6a281`
> 被审文档：`docs/contracts/harmonyai-v3-contract-freeze.md`（`3.0.0-draft.1`）
> Review 类型：Architecture / Contract Freeze Gate
> Review 日期：2026-08-22
> 最终结论：`DO_NOT_FREEZE`
> 说明：总体架构方向可保留，但存在跨 Agent 类型、状态机、前端 Read Model、持久化和 Provider 边界方面的冻结阻塞项。

## 1. 审查范围与判定

本次只读审查了 V3 Contract，并对照当前真实代码中的：

- Assessment、Evidence、Revision；
- Diagnosis、RAG/Chroma、Qwen Provider；
- Prescription、Tone Mapping、Music Catalog；
- Music Generation Stub；
- Feedback、User Profile；
- SQLAlchemy Models；
- `frontend/pages.json` 中的现有页面。

未修改业务代码，未创建 PR，未提交 Commit。

### 总体检查结果

| 检查项 | 结论 | 摘要 |
|---|---|---|
| Agent 1—5 职责边界 | `PARTIAL_PASS` | 主边界合理；Agent 3/4 的 Prompt 所有权及 Understanding Layer/Agent 1 边界未冻结 |
| JSON Schema 可实现性 | `FAIL` | 存在混合类型对象、空对象示例、命名不兼容及未定义嵌套类型 |
| 前端 PUBLIC 字段 | `FAIL` | Assessment/Diagnosis/依据页基本够用；病例摘要、语音确认、任务进度、播放器、主页、历史、收藏不完整 |
| Backend 持久化 | `PARTIAL_PASS` | 技术上可以实现，但当前模型不能直接完整保存；必须新增迁移、关系约束和真实用户身份 |
| Qwen/RAG/Music Provider 接入 | `PARTIAL_PASS` | Music Provider 边界较清楚；Diagnosis RAG Query、Qwen Provider Input/Output 和状态降级仍不完整 |
| Sprint 5 返工风险 | `HIGH` | 若现在冻结，AI、Backend 和 Frontend 会分别定义自己的 Profile、Preference、Music Result |

---

# A. 必须修改项（Block Freeze）

## BF-01 — Canonical 类型与命名存在直接冲突

### 问题

1. Contract 将 `ToneCode` 定义为：

   ```text
   jue | zhi | gong | shang | yu
   ```

   但当前生产代码、知识库、前端和本地曲库统一使用：

   ```text
   jiao | zhi | gong | shang | yu
   ```

   当前 `prescription_v2.py`、`generation_router.py`、`frontend/common/api.js`、`syndrome-to-tone.json` 都使用 `jiao`。若 V3 使用 `jue`，Agent 3 输出将无法直接被现有 Music Catalog/Fallback 消费。

2. `organ_profile` 示例把五个 `number` 和 `score_semantics: string` 放在同一对象中，但其他位置把它当作：

   ```text
   Record<OrganCode, Score01>
   ```

   `element_profile` 存在同样问题。这无法形成严格的 Pydantic/TypeScript Record。

3. Agent 3 Output 和 Agent 4 Request 中的 `tone_profile` 示例为 `{}`，与 Tone Profile 的必填 `weights/dominant_tone/mapping_version/basis` 冲突。

4. `AssessmentSource`、`QuestionnaireV3Submission`、`UserGoal`、`Conflict`、`MissingInformation`、`ProviderMetadata` 等被引用，但没有完整冻结字段表或外部 Contract 引用。

### 必须修改

- 为兼容现有系统，V3 Canonical `ToneCode` 使用 `jiao`；如果坚持 `jue`，必须冻结双向兼容映射及 API 边界，不能让两种值同时自由出现。
- Profile 改为：

  ```text
  {
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

- `element_profile` 采用同样结构。
- 所有示例不得以 `{}` 代替必填结构。
- 为全部被引用的嵌套对象给出明确字段、类型、枚举、必填性和 `extra=forbid` 策略。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-02 — 可见性模型把“不可展示”和“不可传给前端”混为一谈

### 问题

Contract 将 `assessment_id`、`revision`、`status`、`task_id` 等标记为 `INTERNAL`，但前端必须：

- 保存 `assessment_id + revision` 并提交确认；
- 根据 `status` 路由；
- 使用 `task_id` 轮询音乐生成；
- 使用 `prescription_id/music_id` 提交 Feedback。

当前 `INTERNAL` 定义为“后端和 Agent 使用，前端不得展示”，但文档有时又要求前端保存这些字段。实现人员可能将其理解为“不返回前端”，导致流程无法完成。

同样，用户输入的 Narrative/OCR/Voice 在输入页面必然经过前端，不能简单把它们定义为前端不可接触的 `SENSITIVE_INTERNAL`。

### 必须修改

把一个维度拆成两个维度：

1. `transport_scope`
   - `CLIENT_INPUT`
   - `CLIENT_CONTROL`
   - `SERVER_INTERNAL`
   - `PROVIDER_MINIMIZED`

2. `display_scope`
   - `USER_VISIBLE`
   - `USER_VISIBLE_SUMMARY`
   - `NOT_USER_VISIBLE`

例如：

| 字段 | transport_scope | display_scope |
|---|---|---|
| `assessment_id/revision` | CLIENT_CONTROL | NOT_USER_VISIBLE |
| `task_id/status` | CLIENT_CONTROL | status 可见，task_id 不可见 |
| `narrative_text` | CLIENT_INPUT | 用户可编辑 |
| `provider_metadata` | SERVER_INTERNAL | NOT_USER_VISIBLE |

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-03 — Information Understanding、用户修正和 Safety 状态机没有形成闭合 Contract

### 问题

Agent 1 Input 强制依赖 `understanding_id` 和 `AssessmentSource[]`，但当前文档没有定义：

- Information Understanding Layer 的 Request/Response；
- 病例 AI 摘要的 ID、Revision 和确认 Schema；
- Voice Transcript 的状态与用户确认 Schema；
- `AssessmentSource` 的完整联合类型；
- Assessment 用户修正 Request/Response；
- 修正后是重新运行 Qwen，还是通过 Revision Service 修正 Evidence；
- V3 `needs_verification` 的 API、用户选项和最终状态转移。

Contract 又规定 Q19/Q20 不出现在 V3 UI，只通过病例和叙述继续发现风险。此时 Safety Verification 的来源、确认和路由比 V2 更重要，不能只写原则。

### 必须修改

至少冻结：

1. `UnderstandingV3Request/Response`；
2. `CaseSummaryConfirmationRequest/Response`；
3. `VoiceTranscriptionResult/Confirmation`；
4. `AssessmentConfirmationV3Request/Response`；
5. `AssessmentCorrection` 可修改字段白名单；
6. 修正生成新 Revision 的规则；
7. V3 Safety 状态转移表：

   ```text
   clear
   needs_verification
   confirmed_mental_health_risk
   confirmed_acute_physical_risk
   ```

8. 每个 Safety 状态对应的下一路由和允许操作。

必须明确：普通 Assessment 确认不能清除 Safety；只有专用 Safety Verification 能改变 `needs_verification`。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-04 — 五脏 Evidence 的数据模型与聚合规则尚未冻结

### 问题

当前 Contract 要求“一条 Evidence 只绑定一个脏，多脏关系拆成多条 Evidence”。这会产生两个问题：

1. 同一个用户事实被复制成多条 Evidence，可能虚增 `evidence_coverage`；
2. Agent 2 统计支持证据时，可能把同一个事实当作多个独立证据。

同时没有定义：

- 问卷、Narrative、Case Summary 各自的基础权重；
- `supporting` 和 `contradicting` 如何共同计算；
- 同一来源重复事实如何去重；
- `strength` 是 Qwen 输出还是本地确定性计算；
- `organ_profile` 是否必须归一化为1；
- 全部证据为0时如何表示；
- Evidence Coverage 是否按事实数、来源数还是问卷覆盖计算。

### 必须修改

推荐拆成：

```text
FactEvidence
  evidence_id
  claim_code
  source_ref
  quote
  severity
  confirmed

OrganEvidenceLink
  link_id
  evidence_id
  organ
  direction
  strength
  mapping_version
```

这样一个事实只计算一次，但可以关联一个或多个脏。

还必须冻结：

- 去重键；
- Coverage 计算单位；
- Organ Profile 归一化规则；
- 反证扣减规则；
- Qwen 只提取事实，五脏映射与最终权重由审核后的规则完成，还是允许 Qwen 提出候选后再由规则验证。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-05 — Agent 2 的 RAG + Qwen 只定义了结果，没有定义可实现的执行 Contract

### 问题

Contract 定义了 `RAG Result Schema`，但缺少：

- `RagQuery` Schema；
- Retriever Interface；
- Query 构建字段；
- Qwen Diagnosis Provider Request/Response Schema；
- Qwen 输出的白名单与本地验证顺序；
- `RAG_UNAVAILABLE` 时到底是 `degraded + local candidate`，还是 `abstained`。

文档一处允许 RAG 不可用时使用本地规则，另一处又把 `RAG_UNAVAILABLE` 列为 `abstain_reason`，状态语义不唯一。

现有代码中的 `ChromaKnowledgeStore` 使用 `query(query_text, limit)`，现有 Provider Protocol 还出现过 `search(query, limit)`，若 Contract 不冻结接口名称和类型，Backend 与 AI 会再次产生适配层分叉。

### 必须修改

冻结：

```text
RagRetriever.retrieve(query: RagQuery) -> RagResult
DiagnosisProvider.complete_json(request: DiagnosisProviderRequest)
    -> DiagnosisProviderResponse
```

并固定执行顺序：

```text
confirmed assessment
→ deterministic query builder
→ approved RAG hits
→ Qwen candidate proposal
→ Pydantic validation
→ syndrome whitelist
→ evidence ID validation
→ contradiction validation
→ final candidate/abstain
```

需要状态矩阵明确：Cloud失败、Local失败、RAG空、Schema错误、证据不足分别输出什么 `status/abstained/degradation`。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-06 — Agent 3 与 Agent 4 对“生成 Prompt”的职责发生重叠

### 问题

Agent 3 Output 包含完整 `generation_prompt`，同时 Agent 4 又通过 Provider Adapter 转换厂商请求。

如果 Agent 3 生成文本 Prompt，Agent 4 只能被动发送；如果 Agent 4 根据 Provider 能力生成 Prompt，Agent 3 的 `generation_prompt` 又变成重复职责。这会导致：

- Provider 专有逻辑进入 Agent 3；
- 更换 Provider 时需要修改 Prescription Agent；
- 不同 Provider 对时长、乐器、结构的能力限制无法统一处理。

### 必须修改

边界应冻结为：

```text
Agent 3 → vendor-neutral GenerationSpec
Agent 4 Provider Adapter → provider-specific prompt/request
```

Agent 3 字段建议改为：

```text
generation_spec
  tone_profile
  bpm
  duration_seconds
  instruments
  ambient_sounds
  structure
  negative_constraints
```

Provider-specific Prompt、厂商 Model 和请求体只属于 Agent 4 内部。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-07 — Music Generation Response 不能覆盖真实异步状态，也不足以驱动 Player

### 问题

当前 Response 用一个普通对象同时表示：

- queued；
- running；
- generated succeeded；
- matched fallback succeeded；
- failed；
- cancelled。

但各状态所需字段不同：

- queued/running 没有 `audio_asset`；
- generated success 必须有已验证资产；
- matched fallback 需要本地曲目对象和 `stream_url`；
- failed 必须有安全错误；
- 当前 fallback 示例没有完整 `audio_asset` 或本地曲目展示信息。

前端生成进度页还缺少：

- `progress_percent` 或明确的阶段；
- `poll_after_ms`；
- 可取消能力；
- Provider 不支持取消时的状态；
- Player 所需 `title`、实际乐器、实际 BPM、可播放 URL、Rights Note。

### 必须修改

将响应定义为 discriminated union：

```text
QueuedMusicTask
RunningMusicTask
GeneratedMusicSuccess
MatchedMusicSuccess
MusicTaskFailure
CancelledMusicTask
```

以 `status + source_type` 作为判别字段，并为每种状态明确 Required/Forbidden 字段。

同时定义 `PlayableMusic`：

```text
music_id
source_type
title
stream_url
duration_seconds
format
bpm
instruments
rights_note
```

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-08 — Agent 3 偏好输入与 Agent 5 User Preference Schema 不一致

### 问题

Agent 3 的 `user_preference_snapshot` 使用：

```text
"preferred_instruments": ["guqin"]
```

Agent 5 的正式 User Preference 使用：

```text
"preferred_instruments": [
  {"value": "guqin", "weight": 0.82, "sample_count": 6}
]
```

另外：

- Agent 3 使用顶层 `sample_count`，Agent 5 使用每项 `sample_count` 和 `learning.total_feedback_count`；
- `favorite_music_ids` 混合 generated `asset_id` 与 matched `music_id`，无法确定关联表；
- Feedback 的 `music_id` 示例实际填入 `asset_xxx`，ID 语义不一致；
- 没有冻结 Profile 并发更新/版本冲突响应。

### 必须修改

1. 定义唯一的 `UserMusicPreferenceSnapshotV3`，Agent 3 和 Agent 5 共用同一个类型。
2. 定义 `WeightedPreference` 一次，所有偏好字段引用它。
3. 定义：

   ```text
   {
     "music_ref": {
       "source_type": "generated",
       "music_id": "asset_xxx"
     }
   }
   ```

   matched 则 `source_type=matched` 且 `music_id=music_xxx`。
4. 冻结 `profile_version` 乐观锁和冲突重试规则。
5. 明确 Agent 3 读取的是提交该处方时的不可变 Preference Snapshot。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-09 — PUBLIC 数据不足以完成已规划的全部 V3 页面

### 已足够的页面

- Assessment 最终确认页：`presentation` 基本足够；
- Diagnosis/音乐依据页：基本摘要足够；
- Feedback 表单：字段基本足够。

### 不足的页面

1. **病例 AI 总结页**：没有 Case Summary PUBLIC Schema、段落/字段修正 Contract。
2. **语音输入页**：没有录音上传、ASR 状态、转写文本和确认 Read Model。
3. **Assessment 修正页**：没有可编辑字段 ID、当前值、允许值和提交 Schema。
4. **音乐生成进度页**：缺少阶段、进度、轮询建议和取消能力。
5. **Player**：缺少冻结的 `PlayableMusic` Read Model。
6. **个人主页**：只有 Preference 数据，没有昵称、头像、累计次数、最近记录和趋势摘要 Contract。
7. **历史记录**：没有分页、历史卡片、单次详情 Schema。
8. **收藏页**：只有裸 ID，没有标题、来源、时长、封面/视觉信息、可播放状态。

### 必须修改

在本 Contract 中增加 PUBLIC Read Model，或引用同时冻结的：

```text
case-understanding-v3-contract
voice-transcription-v3-contract
user-profile-v3-contract
music-library-v3-contract
```

在这些 Read Model 冻结前，Client Engineer 无法确认“所有 PUBLIC 字段足以完成页面”。

### Freeze Gate

`BLOCK_FREEZE`

---

## BF-10 — 当前数据库不能直接满足 Contract，身份和持久化映射未冻结

### 当前真实状态

Backend 可以通过新增表和 Migration 实现该 Contract，但现有数据库不能直接完整持久化：

- `assessment_evidences` 没有 `organ/element/evidence_type/direction/strength/mapping_version`；
- `assessment_revisions` 可以保存 Snapshot JSON，但部分旧字段仍为非空设计，V3 写入策略未定义；
- `syndrome_diagnoses` 缺少 `diagnosis_id`、Assessment Revision 关联、完整候选、RAG Result 和 Provider Metadata；
- `prescriptions` 把 Agent 3 和 Agent 4 合并在一张表，不适合保存多次异步生成尝试、取消、回调与多个资产；
- `feedbacks.profile_update` 只是 JSON；没有版本化的偏好表；
- `users` 只有简单偏好字段，无法保存 Weighted Preference；
- 没有正式的 favorites、history、generation_tasks、music_assets；
- 多个当前路由仍使用 `user_id=1`，无法保证个人病例、音乐、收藏和偏好所有权。

### 必须修改

Freeze 前至少增加一份被引用的 Persistence Contract，明确：

- V3 表与字段映射；
- Primary Key、Foreign Key、Unique Constraint、Index；
- `assessment_id + revision` 唯一约束；
- `idempotency_key` 唯一约束；
- Feedback 幂等键；
- Favorite 的 generated/matched 联合引用；
- Preference Version 乐观锁；
- 真实 Auth User ID 来源；
- 病例、录音、RAG 日志和音频资产的保留/删除策略；
- SQLite/MySQL Migration 兼容要求。

### 判定

Backend **可以实现**，但不是“当前模型直接可保存”。未冻结持久化映射前开工，Backend 必然二次迁移。

### Freeze Gate

`BLOCK_FREEZE`

---

# B. 建议优化项（Non-blocking）

## NB-01 — 统一状态命名

当前 Agent 使用 `success`，Music Task 使用 `succeeded`。两者都可以保留，但应声明：

- Agent execution：`success/degraded/failed/blocked`；
- Async task：`queued/running/succeeded/failed/cancelled`。

## NB-02 — 建立统一 Error Code Registry

为 Assessment、RAG、Provider、Generation、Preference 分配稳定 Error Code，并将用户文案放在前端/后端统一映射层，避免页面展示 Provider 原始异常。

## NB-03 — Provider Capability Schema

音乐 Provider 可能不支持900秒生成、取消、指定乐器或进度百分比。建议增加：

```text
max_duration_seconds
supports_cancel
supports_progress
supported_formats
supported_parameters
```

## NB-04 — RAG 来源版权与展示边界

RAG `text` 更准确的分类是 `SERVER_INTERNAL_CONTENT`，不一定属于用户敏感数据。应同时记录来源授权、可展示摘要和引用长度上限。

## NB-05 — Score 统一精度

冻结所有 `Score01/PercentWeight` 的序列化精度，例如4位小数，并定义权重并列时的稳定排序规则。

## NB-06 — ID 前缀补齐

当前基础 ID 列表没有 `summary_`、`nar_`、`tr_`、`rag_`、`pref_`、`mgr_`。建议补齐，便于日志和数据排查。

## NB-07 — Profile/History 分页

历史和收藏 API 应冻结 `cursor/limit/next_cursor`，避免上线后从全量数组再迁移到分页。

## NB-08 — Preference 衰减与撤销

除单次最大更新幅度外，建议定义时间衰减、用户手动删除偏好以及“恢复默认偏好”。

## NB-09 — Provider 成本字段

`cost_cny` 应允许 `null`，并记录 `currency` 和 `estimated/actual`，因为部分 Provider 不返回实时费用。

## NB-10 — 自动生成机器 Schema

最终 Freeze 后应由 Pydantic/OpenAPI 生成 TypeScript 类型，不要由 Backend 和 Frontend 手抄两套 Contract。

---

# C. 可以冻结项

以下架构原则已经清楚，可保留并进入最终 Freeze：

## CF-01 — V3 与 V2 并行

使用 `/api/v3`、`questionnaire_v3.0` 和 V3 Schema，不原地破坏 V2.1/V2.2。

## CF-02 — 五 Agent 高层职责

- Agent 1：多源理解后的五脏 Evidence；
- Agent 2：RAG + Qwen 辅助辨证；
- Agent 3：后端权威音乐参数；
- Agent 4：真实生成与本地 fallback；
- Agent 5：反馈与个人偏好。

除 BF-06 的 Prompt 边界外，整体分工成立。

## CF-03 — 后端权威数据链

以下原则可以冻结：

```text
assessment_id + revision
→ diagnosis_id
→ prescription_id
→ task_id/music_id
→ feedback_id
→ preference profile version
```

前端不得构造完整上游对象。

## CF-04 — Evidence 可追溯原则

每个主要结论必须能追踪到用户来源、Evidence 和审核后的知识条目；必须保留 Supporting 和 Contradicting Evidence。

## CF-05 — Diagnosis 允许 abstain

Safety、未确认、证据不足、重大冲突和模型输出不合法时，不强行给出辅助辨证结论。

## CF-06 — 五行到五音采用版本化审核映射

Tone Profile 权重必须归一化；个人偏好不能改变五行到五音的固定医学映射。

## CF-07 — Music Provider 抽象与显式 fallback

Agent 不依赖厂商 SDK；真实生成失败时允许使用本地曲库，并必须标记 `source_type=matched`，不得伪装生成成功。

## CF-08 — Music Safety Gate

Safety blocked、Assessment 未确认、Prescription missing/withheld 时不创建生成任务。

## CF-09 — Feedback 只改变个人偏好

Feedback 不修改全局医学知识、五脏映射、证型规则和 Safety 规则；个人偏好只能调整音乐参数。

## CF-10 — 隐私和日志边界

普通日志不得记录病例原文、Narrative、Voice Transcript、Prompt、Provider Key 或用户自由反馈原文。

## CF-11 — Q19/Q20 的 Owner 边界

只从 V3 普通问卷 UI 移除，不删除 V2.2 和后端 Safety 能力；同时不得宣传完整风险筛查。具体 V3 Safety 状态机仍需按 BF-03 补齐。

---

# D. Agent 边界专项结论

| 边界 | 当前结论 | 说明 |
|---|---|---|
| Information Understanding → Agent 1 | `BLOCKED` | 上游 Contract 未定义 |
| Agent 1 → Agent 2 | `NEEDS_FIX` | 职责方向正确，但 Fact/Evidence/Organ Aggregation 未冻结 |
| Agent 2 → Agent 3 | `PASS_WITH_FIX` | Element → Tone 边界清楚；需修正 Canonical 类型与命名 |
| Agent 3 → Agent 4 | `BLOCKED` | `generation_prompt` 职责重叠 |
| Agent 4 → Agent 5 | `NEEDS_FIX` | 需要统一 generated/matched MusicRef |
| Agent 5 → 下一次 Agent 3 | `BLOCKED` | Preference Snapshot 类型不一致 |

# E. 推荐 Freeze 修订顺序

1. 修正 Canonical Tone/Profile/Visibility 类型（BF-01、BF-02）。
2. 冻结 Understanding、Confirmation、Safety 状态机（BF-03）。
3. 冻结 Fact Evidence、Organ Link 和 Aggregation（BF-04）。
4. 冻结 RAG Retriever、Qwen Diagnosis 和状态矩阵（BF-05）。
5. 固定 Agent 3 `GenerationSpec` 与 Agent 4 discriminated union（BF-06、BF-07）。
6. 统一 Preference Snapshot 和 MusicRef（BF-08）。
7. 补齐前端 Read Model（BF-09）。
8. 增加 Persistence Contract 与 Auth Ownership（BF-10）。
9. 完成 Medical、AI、Backend、Client 四方 Contract Review。
10. 所有 Block Freeze 关闭后，将文档状态从 `PROPOSED_FOR_FREEZE` 改为 `FROZEN`。

# F. 最终判定

```text
MUST MODIFY / BLOCK FREEZE: 10
NON-BLOCKING: 10
CAN FREEZE: 11

FINAL DECISION: DO_NOT_FREEZE
```

该结论不表示 V3 方案不可行。相反，主架构方向成立；现在最重要的是在成员开始并行实现前，把共享类型、状态机、持久化与 UI Read Model 收敛成同一套机器可验证 Contract。
