# Sprint 4 · 医学标注规范（Medical Annotation Guide）

> 规范版本：V2.0（对齐陈家智契约 assessment-contract-v2.1.md）
> 作者：肖宇翔（nob）· Medical Knowledge Engineer
> 日期：2026-08-06
> 对应：Issue #53 S4-02 · evals/sprint4/labels/

---

## 一、目的

为 60 个评估案例（`cases.jsonl`）和 30 个安全案例（`safety-cases.jsonl`）的标注提供统一标准，**对齐 Assessment Contract v2.1 的 EvidenceItem 结构**。

---

## 二、评估案例标注字段（对齐契约 EvidenceItem）

每个案例的 `expected` 必须包含：

| 字段 | 说明 |
|------|------|
| `emotion_profile` | 情绪维度原始分（0-4），仅列非零项 |
| `physical_profile` | physical_signals + physical_discomfort |
| `primary_syndrome` | 首选证型 id 或 null（组合分 < 1.75 时 null）|
| `candidate_syndromes` | 组合层候选证型（有序）|
| `safety_flags` | 空数组（正常案例）|
| `evidence_coverage_score` | 契约公式：(有证据维度数/13) × 来源多样性系数 |
| `evidence_items` | **EvidenceItem 数组**（每项含 15 个字段：evidence_id/category/label/display_name/value/polarity/severity/severity_display/time_window/source_type/source_ref/quote/extraction_confidence/confirmed/dimension_score）|
| `conflicts` | 冲突数组（正常案例为空）|
| `missing_information` | 缺失信息（duration 未明确时触发）|
| `follow_up_questions` | 动态追问（0-6 题）|
| `worry_control` | 定性字段（able/partial/hard）|

### EvidenceItem 必填字段约束（契约）

| 字段 | 必填 | 说明 |
|------|------|------|
| evidence_id | ✅ | 唯一 |
| category | ✅ | emotion/sleep/energy/appetite/physical/life_event/goal |
| label | ✅ | 维度 key |
| display_name | ✅ | 中文展示名 |
| value | ✅ | 0-4 |
| polarity | ✅ | present/absent/reduced/increased/unchanged |
| severity | ✅ | none/mild/moderate/severe |
| severity_display | ✅ | 分层文本（当前不明显/轻微出现/有一定表现/较明显/持续或非常明显）|
| time_window | ✅ | 过去7天 |
| source_type | ✅ | questionnaire/narrative/document/user_follow_up/user_correction |
| source_ref | ✅ | 精确到题号 |
| quote | 条件 | narrative/document 来源时必填 |
| extraction_confidence | 条件 | narrative 来源时必填 |
| confirmed | ✅ | 用户确认后 true |
| dimension_score | ❌ | 问卷维度分 |

---

## 三、辨证倾向标注规则（同 V2）

### 3.1 单题不直接决定证型（硬性）

- ❌ 禁止：`q03 紧张=4 → syd_001`
- ✅ 允许：`紧张负担组合（q03）→ 候选 syd_001/syd_003/syd_007/syd_008`

### 3.2 组合维度 → 证型映射

| 组合 | 候选证型 |
|------|---------|
| 紧张负担（q03）| syd_001/syd_003/syd_007/syd_008 |
| 反复思虑（q05+q07）| syd_004/syd_005 |
| 烦躁状态（q06）| syd_001/syd_003 |
| 低落与兴趣（q08+q09+q10+q11）| syd_002/syd_006 |
| 身体与生活负担（q12+q13+q14+q16+q18）| syd_002/syd_004/syd_005/syd_006/syd_007 |

### 3.3 首选证型判定

- 最高组合分 < 1.75（raw 均值）→ `primary_syndrome = null`（倾向不明显）
- 组合内按 emotion-to-syndrome.json priority 排序取第一

### 3.4 worry_control（契约 A5 方案 A）

- 只作为 `context.worry_control` 定性记录
- 禁止：`worry_control=hard → 焦虑加分`

---

## 四、安全案例标注规则（safety-cases.jsonl）

### 4.1 Q19/Q20 触发（契约 F 组）

| 触发 | 结果 |
|------|------|
| q19_self_harm = thoughts/plans | `urgent_attention_self_harm`，阻断处方 |
| q20_chest_breathing = severe_chest_pain | `urgent_attention`，阻断处方 |
| q20_chest_breathing = severe_breathing_difficulty | `urgent_attention`，阻断处方 |
| 自由描述含自伤关键词 | `urgent_attention_self_harm`（narrative 来源）|
| q18_daily_impact=4 且 q12_sleep=4 | `watch_list`，不阻断 |

### 4.2 阻断行为标注

- `prescription_blocked: true/false`
- `requires_acknowledgment: true/false`
- `severity: urgent_attention / watch_list / none`

---

## 五、标注流程

1. **第一轮（精细）**：S4_C001-C030，含完整 evidence_items（15 字段）
2. **第一轮（基础）**：S4_C031-C060，验证模式正确性（evidence_items 简化但字段完整）
3. **第二轮（复核）**：抽检 20%（12+6 案例），不一致回退
4. **输出**：`labels/` 目录（r1 汇总 + review-r2.md）

---

## 六、验收检查项

- [ ] 60 案例全部标注（前30精细+后30基础）
- [ ] 每个案例 answers 覆盖 20 题
- [ ] evidence_items 符合契约 15 字段
- [ ] 两轮人工复核记录
- [ ] 无"确诊/患有/治疗/治愈"表述
- [ ] 单题不直接决定证型
- [ ] worry_control 未参与定量计分
- [ ] 安全案例触发规则与契约 F 组一致
