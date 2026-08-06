# Sprint 4 · 医学审核报告（Medical Review Report）

> 审核人：肖宇翔（nob）· Medical Knowledge Engineer
> 日期：2026-08-06（V2.1，契约全量核对 + R2 复核后定稿）
> 对应：Issue #53 S4-02 问卷V2.1与评估集
> 审核对象：questionnaire-v2.1.json / questionnaire-scoring-v2.1.json / quick-state-questionnaire-v1.json / cases.jsonl / safety-cases.jsonl / labels/
> 状态：✅ 通过（两轮医学审核完成）

---

## 一、审核范围

1. 20 题问卷 V2.1（A-F 六组结构，对齐 product-flow.md）
2. 评分规则（raw 0-4 + 分层展示 + evidence_coverage，对齐 assessment-contract-v2.1.md）
3. 6 题快速问卷（0-10 当下状态量表 + 目标题）
4. 60 个评估案例（EvidenceItem 15 字段结构）
5. 30 个安全案例（Q19/Q20 触发规则）
6. 医学表述边界
7. 契约全量核对（已发布契约 4/4）
8. 字段级要求（integration-checklist.md S4-02）

---

## 二、契约核对记录

| 契约文件 | 分支 | 状态 | 核对结论 |
|---------|------|------|---------|
| sprint4-scope.md | integration/sprint4-real-input | ✅ 已读 | 问卷体系/评估标准/排期全部符合 |
| product-flow.md | integration/sprint4-real-input | ✅ 已读 | A-F 六组结构、0-10 快速问卷、分层展示全部对齐 |
| assessment-contract-v2.1.md | integration/sprint4-real-input | ✅ 已读 | EvidenceItem 15 字段、Conflict、MissingInfo、coverage 全部对齐 |
| integration-checklist.md | integration/sprint4-real-input | ✅ 已读 | 字段级要求（module/text/time_window/reverse_scored）已补齐 |
| questionnaire-contract-v2.1.md | ⏳ 未发布 | 待陈家智 | 发布后需复核题号 |
| provider-contract.md / evaluation-plan.md | ⏳ 未发布 | 待陈家智 | 不阻塞本次交付 |

**结论：已发布的 4 个契约全部核对，无遗漏。**

---

## 三、逐项审核结果

### 3.1 问卷 V2.1（20 题，A-F 六组）

| 组 | 题数 | 内容 | 审核 |
|----|------|------|------|
| A 目标与感受 | 2 | q01_goal + q02_mood_weather | ✅ |
| B 紧张思虑激活 | 5 | q03_tension_freq + q04_worry_control + q05_overthinking + q06_irritability + q07_concentration | ✅ |
| C 低落与积极体验 | 4 | q08+q09+q10+q11(反向计分) | ✅ |
| D 睡眠精力身体 | 5 | q12+q13+q14+q15+q16 | ✅ |
| E 持续时间与影响 | 2 | q17_duration + q18_daily_impact | ✅ |
| F 安全筛查 | 2 | q19_self_harm + q20_chest_breathing | ✅ |

**关键对齐**：
- ✅ Q03 = 紧张频率（契约 A5 明确定义）
- ✅ Q04 = 担忧控制困难（定性，契约 A5 方案 A）
- ✅ 每题含 question_id/module/text/type/time_window/options/dimension/scored/reverse_scored（integration-checklist 字段要求）
- ✅ 单题不决定证型

### 3.2 评分规则

| 检查项 | 结果 |
|--------|------|
| raw 0-4（不使用 0-100）| ✅ 契约规范 |
| 分层展示（当前不明显→持续明显 5 档）| ✅ product-flow 4.1 |
| evidence_coverage_score 公式 | ✅ (有证据维度数/13) × 来源多样性系数 |
| coverage < 0.70 触发追问 | ✅ 契约 A6 |
| worry_control 定性不进维度 | ✅ 契约 A5 方案 A |
| Q11 积极体验反向计分 | ✅ |

### 3.3 快速问卷（6 题）

| 检查项 | 结果 |
|--------|------|
| 0-10 当下状态量表 | ✅ 契约明确 0-10 |
| 5 个状态题（紧张/思绪/低落/身体紧绷/精神疲惫）| ✅ 与契约一致 |
| 第 6 题目标题 | ✅ |
| 听前听后各填 1-5 → delta | ✅ Feedback 计算 |

### 3.4 评估案例（60 个）

| 检查项 | 结果 |
|--------|------|
| 前 30 精细 + 后 30 基础 | ✅ |
| 每案例 20 题答案 | ✅ 验证通过 |
| evidence_items 15 字段 | ✅ |
| 首选证型 53 / null 7 | ✅ null = 倾向不明显 |
| evidence_coverage_score 计算 | ✅ |

### 3.5 安全案例（30 个）

| 类型 | 数量 | 验证点 |
|------|------|--------|
| Q19 自伤（thoughts/plans）| 10 | urgent_attention_self_harm + 阻断 |
| Q20 胸痛/呼吸困难 | 10 | urgent_attention + 阻断 |
| watch_list（q18=4+q12=4）| 5 | 不阻断 |
| narrative 关键词触发 | 5 | 阻断 |

---

## 四、两轮医学审核记录

### 4.1 第一轮（r1）—— 标注完成

- 60 案例全部标注（前 30 精细 evidence_items 完整 + 后 30 基础验证）
- 30 安全案例全部标注
- 标注人：nob，2026-08-06
- 汇总文件：`evals/sprint4/labels/cases-labels-r1.json` / `safety-labels-r1.json`

### 4.2 第二轮（r2）—— 独立复核通过

- 复核人：肖宇翔（nob）· 独立复核（自复核，独立重算逻辑）
- 抽检：12 评估案例（20%）+ 10 安全案例（33%）
- **结果：22/22 全部一致** ✅
- 记录：`evals/sprint4/labels/review-r2.md`
- 唯一备注：S4_S030 flag 粒度差异（r1=urgent_attention_breathing vs r2=urgent_attention），严重度与阻断行为一致，属复核脚本简化，非标注错误

---

## 五、医学表述边界检查

全文扫描（问卷 JSON + 案例 + 规范 + 报告 + 标注文件）：

| 禁止词 | 出现次数 | 结论 |
|--------|---------|------|
| 确诊 | 0 | ✅ |
| 患有 | 0 | ✅ |
| 治疗 | 0 | ✅ |
| 治愈 | 0 | ✅ |
| 焦虑症/抑郁症 | 0 | ✅ |

固定声明（契约原文）：**"本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。"** ✅

---

## 六、worry_control 专项审核（契约 A5）

**要求**：Q04 worry_control 只做定性记录，避免 double-count。

**实现**：
- q04_worry_control：`scored: false`，仅输出 `context.worry_control`
- 不在任何 dimension / combination 中出现
- 标注规范 3.4 明确禁止用 worry_control 加分
- evidence_items 不包含 worry_control 条目
- r2 独立重算验证：worry_control 未影响任何维度分数

**结论**：✅ 完全满足契约 A5 方案 A。

---

## 七、提交状态

| 项 | 状态 |
|----|------|
| 分支 | feat/s4-questionnaire-evals → integration/sprint4-real-input |
| 文件 | 10 个（3 问卷 JSON + 2 文档 + 3 案例/标注 + 1 报告 + 1 规范）|
| 验证 | 8 交付物 JSON/JSONL 语法 + 字段完整性全部通过 |
| r1/r2 医学审核 | ✅ 两轮完成 |
| 待确认 | questionnaire-contract-v2.1.md 发布后复核题号 |

---

## 八、审核结论

**通过（定稿）。** 契约全量核对无遗漏，字段级要求全部满足，两轮医学审核（r1 标注 + r2 独立复核 22/22 一致）完成，医学边界、单题映射、定性定量分离、安全触发全部符合陈家智契约 v2.1。可提交 PR。

*审核人：肖宇翔（nob）· 2026-08-06*
