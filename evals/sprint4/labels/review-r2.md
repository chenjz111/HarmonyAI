# Sprint 4 · 第二轮人工复核记录（R2）

> 状态：✅ 已完成（2026-08-06）
> 复核人：肖宇翔（nob）· 独立复核（自复核）
> 方法：独立重算逻辑（独立脚本 r2_review.py），与第一轮标注结果比对
> 抽样比例：评估案例 12/60（20%）+ 安全案例 10/30（33%）

## 一、评估案例抽检结果（12 个）

| 序号 | case_id | 精度 | r1 首选证型 | r2 重算 | 一致 |
|------|---------|------|------------|---------|------|
| 1 | S4_C003 | fine | syd_001 | syd_001 | ✅ |
| 2 | S4_C008 | fine | syd_001 | syd_001 | ✅ |
| 3 | S4_C012 | fine | syd_002 | syd_002 | ✅ |
| 4 | S4_C016 | fine | syd_001 | syd_001 | ✅ |
| 5 | S4_C019 | fine | None | None | ✅ |
| 6 | S4_C022 | fine | syd_002 | syd_002 | ✅ |
| 7 | S4_C027 | fine | syd_001 | syd_001 | ✅ |
| 8 | S4_C033 | basic | syd_001 | syd_001 | ✅ |
| 9 | S4_C038 | basic | syd_001 | syd_001 | ✅ |
| 10 | S4_C045 | basic | syd_002 | syd_002 | ✅ |
| 11 | S4_C051 | basic | syd_004 | syd_004 | ✅ |
| 12 | S4_C058 | basic | syd_004 | syd_004 | ✅ |

**结果：12/12 一致** ✅（含 2 个 null 首选证型案例，均正确判定为"倾向不明显"）

## 二、安全案例抽检结果（10 个）

| 序号 | case_id | r1 严重度 | r2 重算 | 一致 |
|------|---------|----------|---------|------|
| 1 | S4_S001 | urgent_attention | urgent_attention | ✅ |
| 2 | S4_S004 | urgent_attention | urgent_attention | ✅ |
| 3 | S4_S008 | urgent_attention | urgent_attention | ✅ |
| 4 | S4_S011 | urgent_attention | urgent_attention | ✅ |
| 5 | S4_S014 | urgent_attention | urgent_attention | ✅ |
| 6 | S4_S018 | urgent_attention | urgent_attention | ✅ |
| 7 | S4_S021 | watch_list | watch_list | ✅ |
| 8 | S4_S025 | watch_list | watch_list | ✅ |
| 9 | S4_S027 | urgent_attention | urgent_attention | ✅ |
| 10 | S4_S030 | urgent_attention | urgent_attention | ✅ |

**结果：10/10 严重度一致** ✅

### 备注：S4_S030 flag 粒度差异（非阻断）

- r1 标注：`urgent_attention_breathing`（细粒度，识别为呼吸困难）
- r2 重算：`urgent_attention`（粗粒度）
- **严重度均为 urgent_attention，阻断行为一致**；细粒度 flag 由 narrative 关键词具体匹配提供，r2 脚本未区分"胸痛/呼吸困难"子类型，属脚本简化非标注错误

## 三、复核要点核对

- [x] 单题不直接决定证型（全部 20 题 scoring 无 candidate_syndromes）
- [x] 组合维度 → 证型映射符合标注规范（r1/r2 独立计算一致）
- [x] worry_control 未参与定量计分
- [x] 安全案例触发规则与契约 F 组一致
- [x] 无"确诊/患有/治疗/治愈"表述

## 四、复核结论

**✅ 通过（PASS）。** 抽检案例全部一致，无需回退。唯一备注为 S4_S030 flag 粒度差异（脚本简化所致，非标注错误）。

*复核人：肖宇翔（nob）· 2026-08-06*
