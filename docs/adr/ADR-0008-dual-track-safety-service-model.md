# ADR-0008: Dual-Track Safety and Music Service Model

> **状态：** 已采纳
> **日期：** 2026-08-14
> **决策者：** 陈家智（Project Leader & AI Architect）

## 背景

HarmonyAI 当前把安全检测结果压缩为单一 `status=blocked_safety`。该状态同时承担风险信号、风险判定、普通评估确认和下游流程控制，导致以下真实错误链路：

```text
OCR / narrative 命中安全关键词
→ Assessment 直接 blocked_safety 并清空 Evidence
→ 用户仍进入普通“评估是否准确”页面
→ 普通 confirmation 把 status 改为 confirmed
→ evidence_coverage_score 仍为 0
→ Diagnosis 退化为 INSUFFICIENT_EVIDENCE
→ 前端错误显示“当前信息不足”
```

该行为混淆了三个不同概念：安全信号是否存在、信号是否已经确认、普通评估内容是否被用户确认。它还错误地让证据覆盖度决定用户能否获得任何音乐服务。

## 决策

### 1. 五 Agent 架构保持不变

系统仍然只有五个 Agent：

```text
Assessment → Diagnosis → Prescription → Music → Feedback
```

Safety 是 Assessment Agent 内部的确定性子模块，不新增第六个 Agent，不修改任何 Agent 名称。

### 2. 采用双轨服务

正常音乐轨：

```text
Safety clear / resolved
→ Assessment
→ Diagnosis
→ Prescription
→ Music
→ Feedback
```

安全支持轨：

```text
Safety needs_verification
→ Safety Verification

Safety confirmed
→ Safety Support
→ 不进入个性化 Diagnosis / Prescription / Music
```

心理安全风险可由用户主动选择经过人工审核的非处方安抚音频。急性身体风险采用紧急帮助优先，不突出音乐入口。

### 3. Safety、Evidence 和技术失败分别控制不同决策

三个正式原则：

1. **Safety determines service boundary.** Safety 状态决定能否进入个性化处方。
2. **Evidence determines personalization level.** Evidence 只决定推荐精细程度。
3. **Technical/model failure must not dead-end non-emergency users.** 技术失败不能让无安全风险的普通用户走入死路。

Score 只产生 signal、confidence 与 specificity。只有显式 State 可以控制 Workflow。禁止直接用 `safety_score` 或 `evidence_coverage_score` 永久阻断全部音乐服务。

## 独立状态模型

在保持 Frozen Contract 向后兼容的前提下，逻辑层至少区分：

- `assessment_status`: `processing | completed | failed`
- `confirmation_status`: `pending | fully_accurate | partially_accurate | corrected | needs_correction`
- `safety_status`: `clear | needs_verification | resolved | confirmed_mental_health_risk | confirmed_acute_physical_risk`

旧 `status=blocked_safety` 可继续作为兼容字段，但不再是唯一状态源。普通 Assessment confirmation 只允许修改 `confirmation_status` 和 Assessment revision，绝不能清除或覆盖 `safety_status`。

## SafetySignal

Safety Detection 只负责产生信号，不直接等同 Safety Decision。信号至少包含：

```json
{
  "signal_id": "safety-...",
  "type": "self_harm",
  "source": "ocr_document",
  "confidence": 0.81,
  "verification_status": "pending"
}
```

`source` 至少区分 `questionnaire`、`user_narrative`、`ocr_document` 与 `system`。普通日志不得记录用户原文、OCR 原文、Prompt 或任何截断文本。

## 来源分级与状态转换

### Questionnaire

Q19/Q20 的 Frozen Safety 语义不变。用户在当前问卷中明确选择高风险项属于直接当前用户信号，可进入确认风险状态，普通“评估是否准确”不能解除。

### 当前自由描述

只有满足既有规则的 direct、current、first-person 明确信号才进入确认风险状态。模糊模型推断进入 `needs_verification`。

### OCR / 医疗材料

OCR 可能包含既往史、否定句、他人描述、排除项或识别错误。OCR 命中默认只产生 `needs_verification`，不得直接等同 `CURRENT_HIGH_RISK`。

验证选项与转换：

| 用户确认 | Safety 状态 |
|---|---|
| 现在仍有这种情况 | confirmed risk |
| 曾经有过，目前不存在 | resolved |
| 描述的是其他人 | resolved |
| OCR/系统理解有误 | resolved |
| 不确定 | needs_verification |

只有专门 Safety Verification 可以执行这些转换。

## Evidence 独立性

`evidence_coverage_score` 表示有效信息覆盖程度，`safety_status` 表示是否允许个性化处方，两者必须独立。

Safety 命中时仍保留已经合法生成的问卷 Evidence，并计算真实 coverage。禁止通过清空 Evidence 把安全风险伪装成“信息不足”。

## 安全支持轨

### 确认心理安全风险

- 阻止个性化 Diagnosis、Prescription 与 Music。
- 页面优先展示现实帮助、可信任联系人和专业支持入口。
- 用户可以主动选择人工审核的非处方安抚音频。
- 安抚音频不自动播放，不根据风险原文实时生成，不属于 Agent③ 处方。

### 确认急性身体风险

- 阻止个性化处方和音乐。
- 页面优先提示立即寻求现实医疗帮助。
- 本阶段 `comfort_audio_allowed=false`，不突出音乐入口。

## Comfort Audio

安抚音频的最小数据语义为：

```json
{
  "audio_type": "comfort_audio",
  "source_type": "curated_library",
  "personalized": false,
  "is_medical_prescription": false,
  "safety_notice_required": true,
  "title": "暂时放松",
  "duration_seconds": 180
}
```

允许偏好：`quiet_instrumental`、`nature_sound`、`simple_pacing`、`no_audio_support`。播放前必须明确说明它只能用于暂时放松，不能替代专业帮助。播放反馈不能自动把 confirmed risk 改为 clear；只有专门的后续安全评估可以改变 Safety 状态。

禁止使用“治疗音乐”“音乐处方”“自伤疗愈音乐”“治愈”等表述。

## 正常轨降级

Safety clear / resolved 时：

- Qwen failure → rule-based / questionnaire fallback
- OCR failure → manual input / skip OCR
- Diagnosis abstain → emotion_based / wellness
- evidence coverage low → 降低推荐精细程度；有有效问卷时不因可选来源缺失 hard stop
- 完全没有有效输入 → 通用舒缓入口；`goal_based` 可推迟到 Sprint 5

唯一不能被普通 fallback 绕过的是 confirmed safety risk。

## 前端语义

必须区分三类页面：

1. 信息不足：说明已切换为更通用的音乐方式，允许补充信息。
2. 需要安全确认：询问风险描述是否为用户当前情况。
3. 明确安全风险：显示“现在更重要的是先确保你的安全”和安全支持操作。

三者不得继续共用单一 `PRESCRIPTION_WITHHELD` 页面。

## 兼容性

- 不删除 Frozen Contract 原字段。
- 新字段作为 V2.1 backward-compatible optional extension。
- 不修改 Q19/Q20 Safety 含义和阈值。
- 不修改五音映射、emotion evaluator/gold 或 Formal 60。
- 不实现真实 AI 音乐生成。

## 后果

- **正面：** Safety Detection 与 Safety Decision 可解释、可修订、可审计。
- **正面：** 安全状态不再被普通确认覆盖，也不再伪装成证据不足。
- **正面：** 非紧急用户在模型或证据降级时仍能获得诚实标注的低特异性音乐服务。
- **正面：** 明确心理风险用户获得帮助优先、用户主动的非处方安抚支持。
- **负面：** 增加 Safety Verification、Safety Support 和 comfort audio 的状态与测试矩阵。
- **风险：** 安抚音频可能被误解为专业干预，因此必须使用人工审核曲库、显式免责声明和非自动播放。
