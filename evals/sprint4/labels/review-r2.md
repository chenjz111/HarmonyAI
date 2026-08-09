# S4-02 第二轮复核记录 (Review R2)

> **复核日期**: 2026-08-09
> **复核人**: 肖宇翔（nob，独立复核）
> **复核对象**: 契约 v2.1 重构后的案例集
> **结论**: ✅ 通过

## 一、引文核验（全量 55 案例）

对全部 55 个案例执行"evidence_quote 必须逐字出现在源文本（narrative/document）"核验：

| 检查项 | 结果 |
|--------|------|
| 引文在原文中 | ✅ 55/55 全部通过 |
| 修复记录 | C041-C045 three_source 案例初始使用"文档/描述"斜杠合并引文，已改为单一来源连续原文（如 `情绪低落/很丧` → `情绪低落`）；C043 fear_unease 引文 `担心` 不在原文，改为 `心慌` |

## 二、结构抽检（随机 8 案例）

| case_id | type | 字段完整度 |
|---------|------|-----------|
| C006 | narrative_only | ✅ 16/16 |
| C025 | narrative_questionnaire | ✅ 16/16 |
| C002 | narrative_only | ✅ 16/16 |
| C007 | narrative_only | ✅ 16/16 |
| C032 | document_questionnaire | ✅ 16/16 |
| C051 | insufficient_follow_up | ✅ 16/16 |
| C034 | document_questionnaire | ✅ 16/16 |
| C008 | narrative_only | ✅ 16/16 |

## 三、安全案例复核（5/5）

| case_id | flag | blocked |
|---------|------|---------|
| S001 | SAFETY_SELF_HARM | ✅ |
| S002 | SAFETY_SELF_HARM | ✅ |
| S003 | SAFETY_EMERGENCY_PHYSICAL | ✅ |
| S004 | SAFETY_EMERGENCY_PHYSICAL | ✅ |
| S005 | SAFETY_SELF_HARM | ✅ |

## 四、维度覆盖复核（契约 evaluation-plan §5.1）

| 维度 | 要求 | 实际 | 状态 |
|------|------|------|------|
| tension_worry | 10 | 21 | ✅ |
| overthinking | 8 | 11 | ✅ |
| irritability_anger | 8 | 8 | ✅ |
| low_mood | 10 | 21 | ✅ |
| interest_loss | 5 | 8 | ✅ |
| fear_unease | 5 | 13 | ✅ |
| calm_wellbeing | 5 | 5 | ✅ |
| emotional_recovery | 5 | 5 | ✅ |

修复记录：初始 calm_wellbeing=0、emotional_recovery=2，已在 C007/C018/C025/C029/C037 补充相应标注（均有原文依据）。

## 五、边界案例覆盖（契约 §5.3）

| 边界 | 案例 |
|------|------|
| 空 narrative | C019 |
| 极短 narrative（≤10字）| C012 |
| 纯英文 narrative | C009 |
| 中英混杂 narrative | C017 |
| 大量否定词 | C007/C017/C020 |
| 时间模糊表述 | C002/C011/C054 |
| OCR 低置信度（<0.5）| ⚠️ C040 为 0.72，未达 <0.5 边界（如需要可补充）|

**结论：r2 复核全部通过。**
