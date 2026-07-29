# Sprint 3 AI Agent V2 设计说明

## 1. 目标与范围

本设计对应 GitHub Issue #34、#35，并遵守 Issue #30 的 V2 Contract 方向：在不破坏 Sprint 2 既有 Agent、LangGraph 工作流和 v1 数据结构的前提下，增加多源评估、可解释输出、安全门禁和 V2 兼容适配。

本周 AI 范围包括：

- `Assessment V2`：已确认病例文本、自由描述、Questionnaire V2 三源输入融合；
- `Questionnaire V2`：确定性计分和可复现的维度输出；
- `Safety Rules`：对三种来源执行统一的确定性安全检查；
- `Diagnosis/Prescription V2`：输出辅助辨证倾向、证据和音乐推荐理由；
- `Music Agent`：规范本地曲库匹配结果，明确 `matched`，不伪装实时生成；
- `Feedback V2`：用户主观变化和个人偏好补丁，不修改全局医学规则；
- 异常、降级、冲突、敏感日志和回归测试。

不在本范围内：真实音乐生成、语音输入、可穿戴设备、自动训练、全局医学规则自动学习和完整用户系统。

## 2. 兼容策略

Sprint 2 的入口和结果保持可运行：

- 保留 `backend/ai_engine/real_agents.py`、`real_workflow.py` 和现有 Stub workflow；
- V2 优先使用新模块或兼容扩展，不直接改变旧函数的必填参数；
- 旧 Agent ID `evaluation_agent` 可读取，但 V2 统一输出 `assessment_agent`；
- 内部旧字段 `diagnosis` 可继续兼容，用户端显示“辅助辨证倾向”；
- v1 接口和旧测试保持原行为，v2 使用独立 Pydantic/TypedDict 结构；
- V2 workflow 通过适配层调用 Sprint 2 Agent，逐步替换节点，不做整链路重写。

## 3. V2 数据流

```text
document_text ───────────┐
narrative_text ──────────┼─> safety_rules ─> questionnaire_v2 scoring
questionnaire_answers ──┘                         │
                                                   v
                                  assessment_v2: state + sources + evidence
                                                   │
                                  user confirmation / safety gate
                                                   │
                                                   v
                         diagnosis_v2: tendencies + reasons + confidence
                                                   │
                                                   v
                      prescription_v2: music parameters + explanation
                                                   │
                                                   v
                         music_agent: matched local track
                                                   │
                                                   v
                         feedback_v2: delta + preference patch
```

问卷是必填基线；病例和自由描述可以跳过。未确认的 OCR 文本不得进入可靠证据集合。高风险安全状态优先于普通评估和音乐处方。

## 4. Assessment V2 输入与输出

### 输入

```python
AssessmentV2Request(
    session_id: str,
    user_id: str,
    document_id: str | None,
    document_text: str | None,
    narrative_text: str | None,
    questionnaire_answers: QuestionnaireSubmission,
)
```

调用方只应把已确认 OCR 内容写入 `document_text`；未确认内容不得进入该字段。`questionnaire_answers` 必须使用 `schema_version="questionnaire_v2.0"`、`time_window_days=7` 和完整 `answers` 列表；列表包含 Questionnaire V2 的 Q1—Q12，后端重新计分，不能信任前端传入的总分。

### 输出

```python
AssessmentV2Response(
    agent_id="assessment_agent",
    status: Literal["success", "degraded", "blocked_safety"],
    analysis_mode: Literal[
        "questionnaire_only",
        "narrative_questionnaire",
        "document_questionnaire",
        "document_narrative_questionnaire",
    ],
    sources_used: list[SourceStatus],
    emotion_profile: EmotionProfile,
    physical_profile: PhysicalProfile,
    life_events: LifeEvents,
    assessment_summary: str,
    extracted_evidence: list[EvidenceItem],
    conflicts: list[ConflictItem],
    missing_information: list[str],
    safety_flags: list[str],
    degradation: DegradationInfo,
    warnings: list[str],
    disclaimer: str,
)
```

每条 Evidence 必须包含 `claim`、`sources` 和 `summary`。`sources` 只能使用 `document`、`narrative` 或 `questionnaire:qXX`。LLM 只能提取、归纳和提示冲突，不得改写问卷确定性分数，也不得直接输出中医证型。

## 5. Questionnaire V2 计分

- Q1 天气只保存为 `mood_metaphor`，不进入核心分数；
- Q2—Q11 使用过去 7 天的 0—4 频率值；
- `normalized_score = raw_score * 25`；
- Q12 普通身体选项进入 `physical_signals`，高风险选项进入 `safety_flags`；
- 单题不能直接决定证型、脏腑或调式；
- 同一答案重复计算必须得到完全相同的结果；
- 计分模块应返回原始分、归一化分和维度来源，便于前端解释。

## 6. Safety Rules

安全规则使用确定性匹配，不依赖 Qwen：

- 自伤或自杀表达：`level=high`，状态 `blocked_safety`；
- 严重或持续胸痛：`level=high`，提示急救或线下医疗；
- 明显呼吸困难：`level=high`，提示立即寻求专业帮助；
- 普通身体不适：记录 `physical_signals`，不直接阻断；
- 规则命中只记录非敏感 `reason_code`，普通日志不保存原文。

安全检查应覆盖自由描述、已确认病例文本和 Q12。命中高风险后，Diagnosis、Prescription 和 Music 不得继续普通处方链路。

## 7. Diagnosis/Prescription V2

Diagnosis V2 在 Sprint 2 规则映射基础上增加：

- `primary_tendency`；
- `secondary_tendencies`；
- 每个倾向的 `score`、`element`、`organs`；
- `evidence_summary`；
- `conflicts` 和 `warnings`；
- 固定声明“用于音乐调养参考，不构成医学诊断”。

模型置信度不能直接当作医学可信度。最终状态应结合输入完整度、来源一致性、规则命中和模型结构化结果计算或分级。

Prescription V2 保留 Sprint 2 的调式、BPM、时长、乐器、Prompt 和 Chroma evidence，同时增加：

- `recommendation_reasons`；
- `parameter_sources`；
- `generation_mode="matched"`；
- `knowledge_degradation`。

Music Agent 输出扁平合同：`music_id`、`title`、`source_type="matched"`、`stream_url`、`mode`、`bpm`、`duration_seconds`、`instruments`、`ambient_sounds`、`rights_note`、`match_explanation` 和 `fallback_music_id`。本 Sprint 只允许本地曲库匹配，不返回 `generated` 成功状态。

## 8. Feedback V2

Feedback V2 使用 `schema_version="feedback_v2.0"`，并接收：

- `session_id`、`prescription_id`、`music_id`；
- 嵌套的 `pre_state` 与 `post_state`；
- 听前、听后身体紧绷和精神疲劳；
- `experience` 中的整体评分、放松程度、音乐匹配度；
- 是否继续、是否收藏、不喜欢的特征/乐器和可选文字反馈；
- 可选 `playback` 播放摘要。

输出：

- 逐项 delta；
- 用户主观体验摘要；
- 决策及原因码；
- `personal_preference_patch`；
- `global_rule_update=false`。

V2 工作流不自动写入默认 4 星。只有用户主动提交 Feedback V2 后才通过原子 `save_once(record, preference_patch)` 保存反馈和个人偏好；Sprint 2 旧入口的历史默认行为保持不变。

## 9. 降级与错误处理

| 场景 | 状态 | 处理 |
|---|---|---|
| 未上传病例 | `success` 或 `degraded` | 继续文本和问卷 |
| OCR 未确认/失败 | `degraded` | 不使用 OCR 原文，允许手动补充或跳过 |
| Qwen 超时/非法 JSON | `degraded` | 丢弃 LLM 输出，使用问卷和本地规则 |
| 来源冲突 | `degraded` | 展示冲突摘要，不包装成确定结论 |
| Chroma 无法查询 | `degraded` | 使用已审核规则，记录检索降级 |
| 高风险命中 | `blocked_safety` | 阻断普通处方和音乐播放 |
| 反馈保存失败 | `failed` 或可重试 | 不伪造成功，不更新偏好 |

所有 Qwen 不可用或输出无效场景均将 `analysis_mode` 回退为 `questionnaire_only`，并把未参与最终分析的 document/narrative 来源标记为 `unavailable`。

## 10. 日志和隐私

- 普通日志只记录 `session_id`、状态、来源类型、错误码和耗时；
- 不记录病例全文、自由描述全文、身份证号、手机号或 API Key；
- Evidence 在用户可见结果中只保存必要摘要；
- 测试使用脱敏固定数据；
- V2 迁移和回滚不执行破坏性 DROP。

## 11. 测试设计

必须覆盖：

- 四种输入组合：问卷、问卷+文本、问卷+确认病例、三源齐全；
- Questionnaire V2 计分边界和重复计算一致性；
- Qwen 未配置、超时、非法 JSON、缺字段；
- OCR 未确认、OCR 失败和跳过；
- 来源冲突和缺失信息；
- 三类高风险安全规则；
- 低可信或安全阻断不进入普通处方；
- Music Agent 输出 `matched` 而非伪造 `generated`；
- Feedback 不自动写默认评分，只更新个人偏好；
- Sprint 2 原有行为全部回归通过；
- V2 工作流固定输入连续运行 10 次，状态、确定性评估和音乐匹配结果保持一致。
