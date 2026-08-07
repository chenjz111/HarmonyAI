# HarmonyAI Questionnaire Contract v2.1

> **Version**: 2.1
> **Sprint**: Sprint 4
> **Replaces**: v2.0 (12 题, 保留兼容)
> **Also defines**: Quick State V1 (6 题), Follow-Up V1 (动态追问)
> **Status**: DRAFT — 待肖宇翔 Review 后冻结
> **Owner**: 陈家智 (契约) / 肖宇翔 (内容)

---

## 一、设计原则

1. **Single question ≠ single diagnosis** — 单题不能直接决定证型。证型由领域聚合 + 多源证据共同确定
2. **Every scored question has a dimension** — 每道计分题明确标注对应维度
3. **Safety questions bypass scoring** — 安全题只做分流入安全流程，不参与状态评分
4. **Visual questions preserve both semantics and values** — 视觉题同时保存语义字符串和数值分数
5. **Appetite direction is preserved separately** — 食欲变化必须分方向 (increase/decrease/none)，不简单合并
6. **Reverse-scored questions are explicit** — 正向题（如 Q10 calm_wellbeing）标记 reverse_scored: true

---

## 二、问卷版本体系

| 问卷 | schema_version | 题数 | 用途 | 必填 |
|---|---|---|---|---|
| 阶段性完整评估 | `questionnaire_v2.1` | 20 | 首次/定期评估 | ✅ |
| 快速状态 | `quick_state_v1` | 6 | 每次听前 | ✅ |
| 动态追问 | `follow_up_v1` | 0-6 | Assessment 触发 | 按触发 |
| 旧版兼容 | `questionnaire_v2.0` | 12 | Sprint 3 兼容 | — |

### 版本识别

后端通过 `schema_version` 字段区分：
- `"questionnaire_v2.0"` → 走 V2.0 评分逻辑 (12 题, 1 题 = 1 维度)
- `"questionnaire_v2.1"` → 走 V2.1 评分逻辑 (20 题, 领域聚合)
- `"quick_state_v1"` → 走 Quick State 评分 (6 题, 0-10 量尺)
- `"follow_up_v1"` → 走追问处理 (不评分, 更新 Assessment)

---

## 三、通用题目字段规范

每道题必须包含以下字段：

```json
{
  "question_id": "q03_tension_worry",
  "module": "B_activation",
  "order": 3,
  "text": "过去两周，你有多经常感到紧张、担忧或难以放松？",
  "type": "frequency_0_4 | visual_single | single_choice | multi_choice | scale_0_10 | duration_choice",
  "time_window": "past_14_days",
  "options": [ ... ],
  "dimension": "tension_worry",
  "scored": true,
  "reverse_scored": false,
  "safety_only": false,
  "weight": 1.0,
  "ui": {
    "layout": "button-row | card-horizontal | slider | multi-select",
    "icon_required": false,
    "progress_required": true
  },
  "version": "2.1"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| question_id | string | ✅ | 全局唯一，格式 `q{NN}_{snake_case}` |
| module | string | ✅ | 所属模块代码 (A~F) |
| order | int | ✅ | 在问卷中的顺序 |
| text | string | ✅ | 用户看到的题目文本 |
| type | enum | ✅ | frequency_0_4 / visual_single / single_choice / multi_choice / scale_0_10 / duration_choice |
| time_window | string | ✅ | "past_14_days" / "past_7_days" / "current" / "lifetime" |
| options | array | ✅ | 选项列表 |
| dimension | string\|null | ✅ | 对应维度 key，安全题/表达题为 null |
| scored | bool | ✅ | 是否计入状态评分 |
| reverse_scored | bool | ✅ | 是否反向计分（高分=好状态） |
| safety_only | bool | ✅ | 是否仅用于安全筛查 |
| weight | float | ✅ | 在领域聚合中的权重，默认 1.0 |
| ui | object | ✅ | 前端渲染提示 |
| version | string | ✅ | "2.1" |

---

## 四、题目类型定义

### 4.1 frequency_0_4

频率题，0-4 五级频率。

```json
{
  "type": "frequency_0_4",
  "options": [
    {"value": 0, "label": "从不", "hint": "过去 14 天没有出现"},
    {"value": 1, "label": "偶尔", "hint": "出现 1-3 天"},
    {"value": 2, "label": "有时", "hint": "出现 4-7 天"},
    {"value": 3, "label": "经常", "hint": "出现 8-11 天"},
    {"value": 4, "label": "几乎每天", "hint": "出现 12-14 天"}
  ]
}
```

### 4.2 visual_single

视觉单选题，使用图形表示状态。**必须同时保存语义值和数值**。

```json
{
  "type": "visual_single",
  "options": [
    {"value": "calm", "label": "平静", "score": 0, "icon": "sea-calm"},
    {"value": "ripple", "label": "微澜", "score": 1, "icon": "sea-ripple"},
    {"value": "waves", "label": "波动", "score": 2, "icon": "sea-waves"},
    {"value": "swell", "label": "翻涌", "score": 3, "icon": "sea-swell"},
    {"value": "storm", "label": "风暴", "score": 4, "icon": "sea-storm"}
  ]
}
```

保存格式: `{"value": "waves", "score": 2}`

### 4.3 single_choice

单选，用于目标和持续时间类题目。

```json
{
  "type": "single_choice",
  "options": [
    {"value": "relaxation", "label": "放松紧张", "scored": false},
    {"value": "sleep", "label": "帮助入睡", "scored": false}
  ]
}
```

### 4.4 multi_choice

多选，用于身体信号和安全筛查。

```json
{
  "type": "multi_choice",
  "options": [
    {"value": "neck_tension", "label": "肩颈紧绷"},
    {"value": "palpitation", "label": "心慌"}
  ]
}
```

保存格式: `{"value": ["neck_tension", "palpitation"]}`

### 4.5 scale_0_10

0-10 连续量尺，用于 Quick State 和部分追问。

```json
{
  "type": "scale_0_10",
  "min": 0,
  "max": 10,
  "step": 1,
  "label_min": "完全没有",
  "label_max": "极其严重"
}
```

### 4.6 duration_choice

持续时间选择，用于 Q17。

```json
{
  "type": "duration_choice",
  "options": [
    {"value": "less_than_3_days", "label": "少于 3 天"},
    {"value": "3_to_6_days", "label": "3-6 天"},
    {"value": "1_to_2_weeks", "label": "1-2 周"},
    {"value": "2_weeks_to_1_month", "label": "2 周-1 个月"},
    {"value": "1_to_3_months", "label": "1-3 个月"},
    {"value": "over_3_months", "label": "超过 3 个月"},
    {"value": "recurrent_unclear", "label": "反复出现，难以判断"}
  ],
  "scored": false
}
```

---

## 五、20 题完整问卷 (questionnaire_v2.1)

### A 模块: 当前目标与整体感受 (2 题)

| ID | 题目 | 类型 | 维度 | 计分 | 说明 |
|---|---|---|---|---|---|
| q01_user_goal | 你这次最希望音乐帮助你做什么？ | single_choice | null | ❌ | 8 选项，影响后续音乐目标 |
| q02_mood_weather | 把最近的整体状态比作天气 | visual_single | null | ❌ | 5 天气图，仅作表达辅助 |

### B 模块: 紧张、思虑与情绪激活 (5 题)

| ID | 题目 | 类型 | 维度 | 计分 | 权重 | 说明 |
|---|---|---|---|---|---|---|
| q03_tension_worry | 过去两周多常感到紧张/担忧/难以放松？ | frequency_0_4 | tension_worry | ✅ | 1.0 | — |
| q04_worry_control | 开始担忧后多难让自己停止？ | frequency_0_4 | worry_control | ⚠️ | — | **定性记录**，不参与 tension_worry 聚合。避免与 Q03 double-count。肖宇翔 Decision Required |
| q05_overthinking | 思绪是否反复围绕同一件事打转？ | visual_single | overthinking | ✅ | 1.0 | 海面视觉图，保存语义+数值 |
| q06_irritability_anger | 多经常感到烦躁/易怒/没有耐心？ | frequency_0_4 | irritability_anger | ✅ | 1.0 | — |
| q07_fear_unease | 多经常感到不安/害怕/担心坏事发生？ | frequency_0_4 | fear_unease | ✅ | 1.0 | — |

### C 模块: 情绪低落与积极体验 (4 题)

| ID | 题目 | 类型 | 维度 | 计分 | 权重 | 说明 |
|---|---|---|---|---|---|---|
| q08_low_mood | 多经常感到情绪低落/难过/心情沉重？ | frequency_0_4 | low_mood | ✅ | 1.0 | — |
| q09_interest_loss | 多经常对原本喜欢的事提不起兴趣？ | frequency_0_4 | interest_loss | ✅ | 1.0 | — |
| q10_calm_wellbeing | 多经常感到平静/轻松/内心安稳？ | frequency_0_4 | calm_wellbeing | ✅ | 1.0 | **正向题，reverse_scored=true**。高分=好 |
| q11_emotional_recovery | 情绪受到影响后通常能慢慢恢复吗？ | single_choice | emotional_recovery | ✅ | 1.0 | 5 级恢复能力 |

### D 模块: 睡眠、精力与身体状态 (5 题)

| ID | 题目 | 类型 | 维度 | 计分 | 权重 | 说明 |
|---|---|---|---|---|---|---|
| q12_sleep_disturbance | 多经常入睡困难/夜间醒来/早醒？ | frequency_0_4 | sleep_disturbance | ✅ | 1.0 | — |
| q13_unrefreshing_sleep | 醒来后多经常觉得没休息好？ | frequency_0_4 | unrefreshing_sleep | ✅ | 1.0 | 与 Q12 区分：Q12=入睡过程，Q13=醒来感受 |
| q14_low_energy | 多经常感到精力不足/容易疲惫？ | visual_single | low_energy | ✅ | 1.0 | 电池视觉图 |
| q15_appetite_change | 食欲最近是否发生明显变化？ | single_choice | appetite_change | ✅ | 1.0 | **必须分方向**: direction=(increase\|decrease\|none), severity=0-4 |
| q16_physical_signals | 最近出现过哪些身体感受？ | multi_choice | physical_signals | ❌ | — | 只记录证据，不直接映射证型 |

Q15 保存格式:
```json
{
  "question_id": "q15_appetite_change",
  "value": {
    "direction": "decrease",
    "severity": 3
  }
}
```

Q16 选项: 肩颈紧绷 / 头痛或头部沉重 / 心慌 / 胸口发紧 / 胃部不适 / 四肢乏力 / 手脚发冷 / 出汗 / 口干 / 无明显不适 / 其他

### E 模块: 持续时间与生活影响 (2 题)

| ID | 题目 | 类型 | 维度 | 计分 | 权重 | 说明 |
|---|---|---|---|---|---|---|
| q17_duration | 这些状态持续了多久？ | duration_choice | null | ❌ | — | 7 选项，不计分但影响评估 |
| q18_daily_impact | 对学习/工作/社交/日常生活造成多大影响？ | frequency_0_4 | daily_impact | ✅ | 1.0 | — |

### F 模块: 安全筛查 (2 题)

| ID | 题目 | 类型 | 维度 | 计分 | 说明 |
|---|---|---|---|---|---|
| q19_self_harm | 过去两周是否出现过伤害自己/结束生命/不想活下去的想法？ | single_choice | null | ❌ | **safety_only=true**。命中→安全流程 |
| q20_emergency | 目前是否存在需要优先处理的紧急身体情况？ | multi_choice | null | ❌ | **safety_only=true** |

Q19 选项: 从未有过 / 偶尔闪过 / 有时想到 / 经常想到 / 有具体计划

Q20 选项: 持续或严重胸痛 / 明显呼吸困难 / 意识模糊 / 接近晕厥 / 症状快速加重 / 无以上情况

---

## 六、6 题快速状态问卷 (quick_state_v1)

每次获取音乐建议前填写。听前+听后使用相同题目。

| ID | 题目 | 类型 | 维度 | 量尺 |
|---|---|---|---|---|
| qs01_tension | 此刻紧张或担忧程度 | scale_0_10 | tension_current | 0-10 |
| qs02_overthinking | 此刻思绪反复程度 | scale_0_10 | overthinking_current | 0-10 |
| qs03_low_mood | 此刻情绪低落程度 | scale_0_10 | low_mood_current | 0-10 |
| qs04_body_tension | 此刻身体紧绷程度 | scale_0_10 | body_tension_current | 0-10 |
| qs05_mental_fatigue | 此刻精神疲惫程度 | scale_0_10 | mental_fatigue_current | 0-10 |
| qs06_goal | 这次希望达到的目标 | single_choice | null | 放松/睡眠/恢复精力/专注/释放情绪 |

听后重复 qs01-qs05，Feedback Agent 计算 delta。

---

## 七、评分规则

### 7.1 领域聚合

当多个题目映射到同一维度时，使用加权平均：

```
维度得分 = Σ(题目得分 × 题目权重) / Σ(题目权重)
```

示例 — sleep 领域:
```
sleep_disturbance = (Q12 × 1.0 + Q13 × 1.0) / 2.0
```

### 7.2 正向题反向

```
calm_wellbeing_reversed = 4 - raw_score
```

### 7.3 前端展示分层

| 领域均值 | 展示文本 |
|---|---|
| 0 — 0.75 | 当前不明显 |
| 0.76 — 1.75 | 轻微出现 |
| 1.76 — 2.75 | 有一定表现 |
| 2.76 — 3.50 | 较明显 |
| 3.51 — 4.00 | 持续或非常明显 |

**这些只是 HarmonyAI 内部状态分层，不属于临床阈值。**

### 7.4 食欲方向处理

```json
{
  "appetite_change": {
    "direction": "decrease",
    "severity": 3,
    "severity_display": "较明显下降",
    "source": "q15_appetite_change"
  }
}
```

direction 为 "none" 时 severity 强制为 0。

### 7.5 安全题分流

Q19 和 Q20 的答案不进入状态评分。命中以下条件直接进入安全流程：
- Q19 选择"有时想到"/"经常想到"/"有具体计划" → `SAFETY_SELF_HARM`
- Q20 选择任何紧急情况 → `SAFETY_EMERGENCY_PHYSICAL`

安全流程不进入 Prescription/Music Agent。

---

## 八、动态追问规则 (follow_up_v1)

### 触发条件决策树

```
1. q17_duration 未填或选择"难以判断"
   → 追问: "这些状态大概持续了多久？" (duration_choice)
   优先级: high

2. q18_daily_impact 未填
   → 追问: "这些状态对你的日常生活造成了多大影响？" (frequency_0_4)
   优先级: high

3. narrative 中 tension 评分 ≥3 但 Q03 ≤1 (冲突)
   → 追问: "你提到[quote]，但问卷中紧张程度选择了[value]。能否再确认一下？" (single_choice)
   优先级: high

4. 两个候选倾向得分差距 <0.10
   → 追问: 区分性追问 (由具体维度决定)
   优先级: medium

5. narrative 中时间表述模糊 (如"最近""前一阵")
   → 追问: "你提到的情况大概是从什么时候开始的？" (duration_choice)
   优先级: medium

6. evidence_coverage < 0.70
   → 追问: "为了更好地理解你的状态，请补充..." (text)
   优先级: low
```

### 追问限制
- 单次最多 **4 题**（scope 附录 A4 风险缓解决策）
- 优先级 high > medium > low
- 同一 trigger 不重复追问
- 用户已回答的追问在 revision 中标记为 resolved

---

## 九、向后兼容

### V2.0 → V2.1 映射

V2.0 的 12 题可以直接映射到 V2.1 的对应维度：

| V2.0 question_id | V2.1 question_id | 映射方式 |
|---|---|---|
| q02_tension_worry | q03_tension_worry | 直接 |
| q03_overthinking | q05_overthinking | 直接 |
| q04_irritability_anger | q06_irritability_anger | 直接 |
| q05_low_mood | q08_low_mood | 直接 |
| q06_interest_loss | q09_interest_loss | 直接 |
| q07_fear_unease | q07_fear_unease | 直接 |
| q08_sleep_disturbance | q12_sleep_disturbance | 直接 |
| q09_low_energy | q14_low_energy | 直接 |
| q10_appetite_change | q15_appetite_change | 需要方向适配 |
| q11_daily_impact | q18_daily_impact | 直接 |
| q01_mood_weather | q02_mood_weather | 直接 |
| q12_physical_safety | q16_physical_signals | 需要格式适配 |

V2.0 缺少的 8 个新维度在兼容模式下留空，evidence_coverage 会相应降低。

---

## 十、交付物清单

| 文件 | 负责人 | 状态 |
|---|---|---|
| `knowledge/questionnaire-v2.1.json` | 肖宇翔 | ⬜ |
| `knowledge/questionnaire-scoring-v2.1.json` | 肖宇翔 | ⬜ |
| `knowledge/quick-state-questionnaire-v1.json` | 肖宇翔 | ⬜ |
| `knowledge/follow-up-questions-v1.json` | 肖宇翔 + 钟睿宸 | ⬜ |

---

*陈家智起草，待肖宇翔 Review 后冻结。Q04 决策待定。*
