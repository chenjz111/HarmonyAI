# HarmonyAI Agent Contract V2

> 负责人：陈家智（Project Leader & AI Architect）
> 状态：Sprint 3 冻结契约
> 适用范围：比赛版多源评估、辅助辨证、音乐处方、曲库匹配和反馈闭环
> 重要说明：本文是跨模块契约，不代表所有字段已经在 `dev` 分支实现。

## 1. 契约目标

Sprint 2 已经跑通五 Agent 顺序链路，但主要面向问卷输入，部分对象仍使用 `dict`，`evaluation_agent`/`assessment_agent`、`generation_agent`/`music_agent` 等命名也不统一。

Sprint 3 统一以下原则：

1. 问卷是确定性基线，病例材料和自由描述是可选增强信息；
2. 每一条评估依据都能追踪到 `document`、`narrative` 或 `questionnaire`；
3. OCR、Qwen 或知识检索失败时返回机器可读降级状态；
4. 用户端只使用“状态评估”和“辅助辨证倾向”，不宣称医学诊断；
5. Music Agent 的 P0 输出是本地曲库匹配，必须返回 `source_type=matched`；
6. Feedback 只能形成个人偏好补丁，不能自动修改全局医学规则。

## 2. 五 Agent 规范命名

| 顺序 | 规范 `agent_id` | 用户端名称 | 兼容旧 ID |
|---|---|---|---|
| 1 | `assessment_agent` | 状态评估 Agent | `evaluation_agent` |
| 2 | `diagnosis_agent` | 辅助辨证 Agent | 无 |
| 3 | `prescription_agent` | 音乐处方 Agent | 无 |
| 4 | `music_agent` | 音乐匹配 Agent | `generation_agent` |
| 5 | `feedback_agent` | 反馈 Agent | 无 |

兼容规则：

- v2 写入和展示只使用规范 ID；
- 读取历史数据时允许旧 ID；
- 兼容别名不得改变 Agent 的业务含义；
- 内部保留 `diagnosis` 路由不等于允许前端展示“医学诊断”。

## 3. 通用 Agent Envelope

所有 Agent 输出都应具有以下外壳：

```json
{
  "agent_id": "assessment_agent",
  "agent_version": "2.0.0",
  "run_id": "run_7f31a2",
  "session_id": "session_7f31a2",
  "status": "success",
  "confidence": 0.82,
  "confidence_basis": {
    "source_coverage": 0.85,
    "schema_validity": 1.0,
    "source_consistency": 0.75,
    "execution_reliability": 0.9
  },
  "reason": ["问卷完成，文本结构化成功，三源信息基本一致"],
  "warnings": [],
  "input": {},
  "output": {},
  "started_at": "2026-07-31T09:00:00+08:00",
  "finished_at": "2026-07-31T09:00:01+08:00",
  "processing_time_ms": 860
}
```

### 3.1 `status` 枚举

| 状态 | 含义 | 用户端处理 |
|---|---|---|
| `success` | 规范输出完整，未触发降级 | 正常展示 |
| `degraded` | 外部能力失败，但确定性路径仍有可用结果 | 展示降级说明，允许继续 |
| `blocked` | 命中安全门禁或缺少不可替代输入 | 停止普通处方流程 |
| `failed` | 当前步骤无法形成可用结果 | 展示重试、返回或跳过 |

### 3.2 可信度的统一解释

`confidence` 是系统对“本次输出是否有足够输入、格式是否合法、来源是否一致、执行路径是否可靠”的工程置信指标，不是：

- 疾病概率；
- 医学诊断准确率；
- 治疗有效率；
- Qwen 自己声称“我有多确定”；
- 用户星级对辨证正确性的证明。

建议由下列可审计分量产生：

```text
overall =
  0.35 × source_coverage
  + 0.25 × schema_validity
  + 0.20 × source_consistency
  + 0.20 × execution_reliability
```

在完成真实数据校准前，该数值只能称为“系统置信指标”。前端建议同时展示文字等级：

- `high`：`overall >= 0.80`
- `medium`：`0.60 <= overall < 0.80`
- `low`：`overall < 0.60`

硬性约束：

- 模型返回的自报置信度只能作为参考分量，不能直接成为 `overall`；
- Qwen 降级后 `execution_reliability` 必须下降；
- OCR 未经用户确认的文本不得提高 `source_coverage`；
- 来源冲突必须降低 `source_consistency`；
- 高风险信号不因置信度较低而被忽略。

## 4. Assessment Agent

### 4.1 输入

```json
{
  "session_id": "session_7f31a2",
  "document_id": "doc_7f31a2",
  "document_text": "用户确认后的 OCR 文本",
  "narrative_text": "最近要考试，晚上脑子停不下来。",
  "questionnaire_answers": {
    "q01": 2,
    "q02": 3
  }
}
```

固定字段：

- `document_id`
- `document_text`
- `narrative_text`
- `questionnaire_answers`

约束：

- `questionnaire_answers` 是 P0 必填基线；
- `document_text` 只有用户确认后才可作为可靠输入；
- `narrative_text` 必须去除首尾空白、限制长度并经过安全规则；
- 可选输入缺失或失败不应导致 HTTP 500。

### 4.2 输出

```json
{
  "assessment_id": "assessment_7f31a2",
  "analysis_mode": "document_narrative_questionnaire",
  "emotion_profile": {
    "primary": "焦虑",
    "secondary": ["思虑过多", "疲惫"],
    "intensity": 72
  },
  "physical_profile": {
    "sleep": "入睡困难",
    "energy": "白天疲惫",
    "appetite": "轻度下降"
  },
  "life_events": ["考试压力"],
  "extracted_evidence": [
    {
      "source": "narrative",
      "source_ref": "narrative_text",
      "summary": "担心考试结果，睡前反复思考"
    }
  ],
  "source_conflicts": [],
  "missing_information": [],
  "safety_flags": []
}
```

`analysis_mode` 只允许：

- `questionnaire_only`
- `narrative_questionnaire`
- `document_questionnaire`
- `document_narrative_questionnaire`

降级要求：

- Qwen 未配置、超时或 JSON 非法：重试一次，仍失败则 `status=degraded`；
- 降级后保留确定性问卷分数，`analysis_mode=questionnaire_only`；
- OCR 失败不进入 Assessment 可靠来源；
- 命中自伤、严重胸痛或呼吸困难等规则时输出 `status=blocked` 和 `safety_flags`。

## 5. Diagnosis Agent

### 5.1 输入

- Assessment 的 `emotion_profile`
- `physical_profile`
- `extracted_evidence`
- `source_conflicts`
- `safety_flags`

### 5.2 输出

```json
{
  "syndrome_tendency": {
    "primary": {
      "syndrome_id": "syd_001",
      "name": "心脾两虚倾向",
      "score": 0.78
    },
    "secondary": []
  },
  "tcm_emotion_mapping": [
    {"emotion": "思", "weight": 0.78},
    {"emotion": "恐", "weight": 0.32}
  ],
  "explanations": [
    {
      "summary": "思虑较多，同时出现睡眠、食欲和精力变化",
      "evidence_refs": ["narrative_text", "q07", "q08", "q09"]
    }
  ],
  "limitations": ["该结果为音乐调养用途的辅助辨证倾向，不构成医学诊断"]
}
```

约束：

- 不允许单道题直接决定证型、脏腑或调式；
- 低可信或来源冲突必须显示限制说明；
- `safety_flags` 非空且达到阻断级别时，不继续普通处方。

## 6. Prescription Agent

### 6.1 输入

- `syndrome_tendency`
- 情绪与身体画像
- 用户个人音乐偏好（如果存在）
- 使用场景

### 6.2 输出

```json
{
  "prescription_id": "prescription_7f31a2",
  "name": "安神调养方案",
  "mode": "宫调",
  "bpm": 58,
  "duration_seconds": 900,
  "instruments": ["古琴", "洞箫"],
  "ambient_sounds": ["流水"],
  "usage_scene": "睡前",
  "explanations": [
    "根据当前思虑偏多、睡眠不佳的状态，选择较慢节奏和柔和乐器"
  ],
  "knowledge_evidence": []
}
```

约束：

- 参数必须落在已审核范围；
- 个人偏好只能微调乐器、节奏、时长和环境音，不能改变医学知识映射；
- 知识检索失败时允许本地规则降级，但必须返回 warning。

## 7. Music Agent

### 7.1 输入

- `prescription_id`
- `mode`
- `bpm`
- `duration_seconds`
- `instruments`

### 7.2 输出

```json
{
  "music_id": "music_gong_001",
  "title": "宫调·静心",
  "source_type": "matched",
  "stream_url": "/static/music/gong-demo.wav",
  "mode": "宫调",
  "bpm": 58,
  "duration_seconds": 900,
  "instruments": ["古琴", "洞箫"],
  "copyright_source": "HarmonyAI competition demo library",
  "fallback_music_id": "music_default_001"
}
```

P0 只允许 `source_type=matched`。当前版本不能将本地音频描述为“Qwen 生成”或“AI 实时生成”。`generated` 只作为未来扩展枚举保留。

## 8. Feedback Agent

### 8.1 输入

应包含：

- `session_id`
- `prescription_id`
- `music_id`
- 1—5 星整体评价
- 听前和听后状态
- 放松程度
- 音乐匹配度
- 是否继续使用
- 是否收藏
- 不喜欢的音乐特征
- 选填文字反馈

### 8.2 输出

```json
{
  "feedback_id": "feedback_7f31a2",
  "effect_summary": {
    "emotion_change": -2,
    "tension_change": -3,
    "relaxation_level": 4
  },
  "personal_preference_patch": {
    "prefer_instruments": ["古琴"],
    "avoid_instruments": ["高频笛声"],
    "bpm_delta": -4
  },
  "global_rule_update": null
}
```

硬性边界：

- 不允许自动修改证型规则、五行五音映射或全局权重；
- 不允许把五星评价解释为辨证正确；
- 只有用户主动提交后才能写入反馈，不能自动填入默认 4 星；
- 保存失败时不得伪造成功或应用偏好补丁。

## 9. Agent 间传递顺序

```text
Assessment
  → Diagnosis
  → 用户确认可解释结果
  → Prescription
  → Music
  → 用户播放并主动反馈
  → Feedback
```

安全路由优先级：

```text
safety blocked
  > required input failed
  > degraded fallback
  > normal success
```

## 10. 错误与降级代码

| 代码 | Agent | 处理 |
|---|---|---|
| `OCR_UNAVAILABLE` | Assessment 上游 | 跳过材料，继续问卷 |
| `LLM_UNAVAILABLE` | Assessment/Diagnosis | 问卷和本地规则降级 |
| `LLM_SCHEMA_INVALID` | Assessment/Diagnosis | 重试一次，仍失败则降级 |
| `KNOWLEDGE_UNAVAILABLE` | Prescription | 使用审核过的本地规则 |
| `MUSIC_NOT_FOUND` | Music | 切换备用本地曲目 |
| `FEEDBACK_SAVE_FAILED` | Feedback | 保留输入，允许重试，不更新偏好 |
| `SAFETY_BLOCKED` | Assessment | 停止普通处方并展示安全提示 |

## 11. 契约冻结清单

- [x] 五 Agent 规范 ID 和兼容别名已定义
- [x] Assessment 三源字段已统一
- [x] `analysis_mode` 枚举已统一
- [x] Music P0 字段和 `matched` 边界已统一
- [x] Feedback 个人偏好边界已统一
- [x] 可信度的含义和组成已明确
- [x] OCR、Qwen、知识库、音乐和反馈降级代码已明确
- [ ] 钟睿宸的 AI 实现与本文逐字段对照
- [ ] 蔡子鑫的 v2 API 与本文逐字段对照
- [ ] 彭翔的前端消费字段与本文逐字段对照
- [ ] 三条 E2E 全部通过后签署最终实现一致性
