# Questionnaire V2 设计说明

> 文档对应：`questionnaire-v2.json` + `questionnaire-scoring-v2.json`
> 审核签字：`knowledge/v2/sprint3-medical-review.md`
> 设计者：肖宇翔（nob）· Medical Knowledge Engineer
> 日期：2026-07-28

---

## 一、设计目标

Questionnaire V2 是 Sprint 3 多源评估中的**稳定基线**。它不替代医学量表，也不独立完成医学诊断。其作用是：

1. 以简短、易理解的方式收集用户的情绪、睡眠、精力、食欲和日常影响
2. 为 Assessment Agent 提供**确定性的结构化输入**
3. 提供**可视化降压入口**（天气/海面/电池题）让用户进入问卷时不抗拒
4. 配合 narrative/document/OCR 输入做**多源融合**

---

## 二、12 题结构总览

| 编号 | 维度 | 情绪映射 | 类型 | 计分 |
|------|------|---------|------|------|
| Q1 | mood_metaphor | — | visual_single | ❌ 仅表达 |
| Q2 | tension_worry | anxiety | frequency_0_4 | ✅ |
| Q3 | overthinking | overthinking | visual_single | ✅ |
| Q4 | irritability_anger | anger | frequency_0_4 | ✅ |
| Q5 | low_mood | depression | frequency_0_4 | ✅ |
| Q6 | interest_loss | depression | frequency_0_4 | ✅ |
| Q7 | fear_unease | fear | frequency_0_4 | ✅ |
| Q8 | sleep_disturbance | depression | frequency_0_4 | ✅ |
| Q9 | low_energy | depression | visual_single | ✅ |
| Q10 | appetite_change | overthinking | frequency_0_4 | ✅ |
| Q11 | daily_impact | depression | frequency_0_4 | ✅ |
| Q12 | physical_safety | — | visual_multi | ❌ 仅 safety |

10 题计分（Q2—Q11）+ 2 题非计分（Q1 表达 + Q12 风险）

---

## 三、医学 rationale（每题设计理由）

### Q1 今日内在天气
- **目的**：降低用户进入问卷的心理门槛
- **设计依据**：用户面对医学化问卷容易紧张，隐喻式问题（晴朗/雷雨）降低防御
- **约束**：天气不直接映射证型，"雷雨≠愤怒≠肝≠角调"硬性禁止

### Q2 紧张与担忧 → anxiety
- **目的**：焦虑情绪的**最直接观测点**
- **对应文献**：k_003（Li 2025 Meta，HAMA MD=-3.89，老年人群）、k_004（Zhang 2025 RCT，HAMA B=-2.433）
- **风险**：癌症人群 k_001 显示焦虑无效，AI 检索时需带人群限定

### Q3 思绪像海面一样停不下来 → overthinking
- **目的**：捕捉反复思虑的频率
- **设计依据**：单题覆盖 overthinking 维度。判定为可接受（spec 第 3 节 Q3 注释）
- **图形约束**：海浪强度仅作频率视觉表达，不直接映射证型

### Q4 烦躁易怒 → anger
- **目的**：捕捉情绪触发倾向
- **对应证型**：syd_001 肝郁化火（priority 1）、syd_003 心火上炎（priority 2）

### Q5 情绪低落 → depression（anhedonia 倾向）
- **目的**：抑郁情绪的直接观测
- **依据**：k_005 林奕2018 RCT，SDS 改善；k_001 Meta，HAMD SMD=-1.11
- **注意**：Q5+Q6 取平均，反映抑郁情绪+兴趣下降的整体倾向

### Q6 兴趣下降 → depression（anhedonia 直接征）
- **目的**：与 Q5 共同捕捉抑郁
- **设计依据**：单独的兴趣下降比单独的情绪低落更具临床指示意义，但结合用户安全放在 Q5+Q6 平均

### Q7 恐惧不安 → fear
- **目的**：恐惧情绪的捕捉
- **对应证型**：syd_007 肾阴不足（priority 1）、syd_008 心肾不交（priority 2）

### Q8 睡眠困扰 → depression / anxiety / cardiac
- **目的**：跨维度信号（既属焦虑又属抑郁，跨多个证型）
- **依据**：k_005、k_014（徵调-心系失眠）、k_007（角调-肝气郁结失眠）

### Q9 精力电池 → depression / fatigue
- **目的**：补充体力评估，避免仅依赖"情绪低落"
- **设计依据**：Q9 是中文情境下的特殊设计（西方量表一般不单独问），但与 k_015（彭思涵2020 宫调-脾瘅糖尿病前期，总有效率90%）对应
- **无障碍**：电池图标"满→空"方向可能误选，**文字标签反向**（"从不精力不足"→"几乎每天精力不足"）

### Q10 食欲变化 → overthinking
- **目的**：脾系疾病的旁证（脾主运化，食欲变化是脾系指征）
- **依据**：k_015 宫调-脾瘅研究涉及血糖/食欲

### Q11 日常影响 → depression（功能受损）
- **目的**：评估**功能受损程度**（不是症状本身）
- **作用**：与 safety watch_list 联动（Q11=4 触发关注）

### Q12 身体感受与安全检查 → physical_signals + safety_flags
- **目的**：身体背景 + 风险筛查（高风险项进入 safety_flags）
- **硬约束**：禁止根据 Q12 单一身体选项直接得出某脏腑、证型或调式
- **风险项**：严重胸痛/呼吸困难/自伤想法 → 阻断常规处方流

---

## 四、计分规则

### 4.1 单维度分数

```
Q2—Q11 每题 raw_score: 0-4
normalized = raw × 25  → 范围 0-100
```

### 4.2 组合维度（用于状态展示）

| 组合 | 维度 | 方法 |
|------|------|------|
| 紧张负担 | tension_worry + fear_unease | 平均 |
| 反复思虑 | overthinking | 直取 |
| 烦躁状态 | irritability_anger | 直取 |
| 低落与兴趣 | low_mood + interest_loss | 平均 |
| 身体与生活负担 | sleep_disturbance + low_energy + appetite_change + daily_impact | 平均 |

### 4.3 严重程度标签

| 归一化分数 | 用户端标签 |
|-----------|-----------|
| 0—24 | 当前较少 |
| 25—49 | 轻度出现 |
| 50—74 | 较明显 |
| 75—100 | 频繁出现 |

**标签只表达主观频率，不等价于医学严重程度。**

---

## 五、安全规则

### 5.1 立即阻断（urgent_attention）

触发：Q12 选中"严重胸痛/呼吸困难/自伤想法"
- 显示醒目安全提示
- 阻断常规处方流
- 后端二次确认
- 紧急联系方式按地区配置，**不可由模型猜测**

### 5.2 非紧急关注（watch_list）

触发：
- Q11 = 4（日常影响几乎每天）
- Q8 = 4 + 自由描述提到"超过两周"
- 多个核心维度同时为 4
- OCR/文本提到"症状明显加重"

行为：提示关注，不阻断。

### 5.3 检测来源覆盖

风险检测必须覆盖**全部四个来源**：
1. 问卷 Q12
2. 自由描述关键词与结构化提取
3. 用户确认后的 OCR 文本
4. Qwen 输出后的二次规则校验

**Qwen 不可用时，确定性规则仍必须生效。**

---

## 六、结果展示链

```
原始症状（用户回答）
  ↓
维度分数（归一化 0-100）
  ↓
情绪推测（基于 emotion-to-syndrome.json）
  ↓
辅助辨证倾向（含推荐调式、文献依据摘要）
```

约束：
- 输出只能称"状态评估"或"辅助辨证倾向"
- 固定显示"不构成医学诊断"声明
- 每条辨证倾向至少显示一条可理解依据
- 不展示大模型内部思维

---

## 七、与现有知识库的衔接

### 7.1 emotion-to-syndrome.json 复用

Q2-Q11 各题的 emotion_mapping 直接对应 `emotion-to-syndrome.json` 的情绪维度：

| 问卷维度 | emotion-to-syndrome 候选证型 |
|---------|--------------------------|
| tension_worry + fear_unease | anxiety → syd_001/003/008 |
| overthinking | overthinking → syd_004/005 |
| irritability_anger | anger → syd_001/003 |
| low_mood + interest_loss + daily_impact + sleep_disturbance + low_energy | depression → syd_002/006 |
| appetite_change | overthinking → syd_004/005 |
| fear_unease | fear → syd_007/008 |

### 7.2 五级证据标记

`questionnaire-scoring-v2.json` 的 `evidence_legend` 字段指向 emotion-to-syndrome.json 中已用的五级标记体系（[直接证据]/[病机相关]/[旁证-同类证型]/[旁证-五行归属]/[经典理论]）。

**这是 nob 本地扩展**，未写入陈家智 knowledge-architecture.md spec。AI 检索时按级加权。

### 7.3 与 literature.json 22 篇文献的关联

| 文献 | 在问卷中的作用 |
|------|--------------|
| k_001/k_003/k_004 | anxiety/depression 维度的 Level A 证据 |
| k_005 | 抑郁维度直接证据（角调-肝气郁结） |
| k_007 | 焦虑+失眠维度的 C 级证据 |
| k_008~k_012 | 经典理论（情绪脏腑映射） |
| k_013 | 五声/六声/七声调式理论支撑 |
| k_014~k_022 | 各脏腑/证型维度的现代旁证/直接证据 |

### 7.4 与 chunks 的关系

22 个文献知识块（34 个 chunk）可作为 RAG 检索结果，**辅助** Assessment Agent 的辨证推理。问卷分数为**确定性事实**，文献检索为**辅助推理**，二者职责分明。

---

## 八、图形题资源需求

| 题 | 图形资源 | 版权要求 |
|----|---------|---------|
| Q1 | 5 张天气图标（晴朗/微云/阴天/下雨/雷雨）| 团队自制或 CC0 |
| Q3 | 5 张海面图标（平静→风暴）| 团队自制或 CC0 |
| Q9 | 5 张电池图标（满→空）| 团队自制或 CC0 |
| Q12 | 9 张身体图标（肩颈/头/心/胃/疲劳/胸/肺/脑/无）| 团队自制或 CC0 |

视觉要求：
- 每张图必须有文字标签
- 不依赖红绿颜色区分
- 不使用脏腑图
- 不将五音五行作为答案选项

---

## 九、Acceptance Criteria（自检清单）

- ✅ 题目总数固定为 12
- ✅ 正常阅读速度下 3 分钟内完成（10 题 × 9 秒 = 90 秒）
- ✅ Q2—Q11 全部使用统一 0—4 频率量表
- ✅ 覆盖指定 10 个核心维度
- ✅ 至少 3 题具有图形/图标卡片（Q1/Q3/Q9/Q12 共 4 题）
- ✅ 天气题（Q1）不进入核心评分
- ✅ 身体选项（Q12）不直接映射脏腑、证型或调式
- ✅ 前后端都能识别高风险选项（Q12 + safety_rules）
- ✅ 问卷分数可由相同答案稳定复算（deterministic）
- ✅ 页面和 API 均不输出医学诊断

---

## 十、待 Sprint 3 后续 PR 衔接

| PR | 内容 | 依赖 |
|----|------|------|
| PR-02（本次） | 问卷维度、医学措辞、安全规则数据 | PR-01（陈家智冻结文档）|
| PR-03 | v2 Pydantic Schema、问卷计分、多源 Assessment | PR-01 + PR-02 |
| PR-06 | 八页骨架、设计系统和问卷交互 | PR-01 + PR-02 |
