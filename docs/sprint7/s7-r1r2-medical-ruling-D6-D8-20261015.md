# Sprint 7 · R1/R2 医学裁定 D-6~D-8（正式意见稿）

- **出具人**：肖宇翔（nob）· 医学知识签核
- **日期**：2026-10-15
- **依据**：#154 医学证据反事实审计 + 基线 `team/s7-m1-w2-baseline` @ `ff879f70` 的只读核查与合成测试
- **性质**：医学意见，非工程实现指令。落地由 Owner/INT-2 协调，本稿不改任何生产代码或规则资产。
- **执行回执**：`tests/sprint7_audit` 78 passed（离线，0 Provider/网络/生产库）。

---

## 0. 裁定总原则（先于 D-6~D-8）

1. **五音调适是辅助性、非医疗诊断场景**。正因为不做诊断，证据不足或方向不唯一时，**宁可保守（综合调适/基础舒缓），不可硬选**。这是所有三条裁定的共同地基。
2. **"数值接近"不等于"医学主导"**。脏象支持度是规则映射 + 标注可靠性算出来的近似值，0.01 的差可能只是噪声。
3. **否定证据 ≠ 反向证据**。"没有失眠"只能说明该症状未被确认，不能推出"存在相反的证候"。因此否定事实既不正向加分，也不负向扣分，先中性排除。
4. **内部决策依据必须等于公开解释依据**。评分层用什么、解释层就必须能引用什么；不能评分用 A、解释却只谈 B。

---

## D-6：保留 `integrated_regulation`，不接受"两档化"

**结论：否决 Two-Mode V2.1 的"正常路径不再产出 integrated_regulation"。三档医学语义必须保留。**

### 医学必要性

- **整体观**：五脏通过五行生克、脏腑相关相互影响。多脏象证据接近（如肝郁与心火同时明显）时，孤立取最高分硬选单一调式，等于人为割裂这种相关性。
- **辨证论治的下限**：当证据不足以区分单一主导证型时，正确的做法是"综合调适"（调和多个相关脏腑），而不是制造一个伪主导。这正是 `integrated_regulation` 的医学含义。
- **噪声容限**：支持度是 `link_strength × reliability` 的累加，其中 `reliability` 来自抽取置信度/问卷频率，本身带误差。微小差异不构成可靠主导。

### 反事实案例（均在真实代码上实测）

| 场景 | 支持度 | Two-Mode 结果 | 医学应然 |
|---|---|---|---|
| CF-1 肝心几乎并列 | liver 1.00 / heart 0.99 | `personalized_five_tone`（硬选角） | `integrated_regulation`（综合调适） |
| CF-2 肝略高于心 | liver 1.00 / heart 0.90 | `personalized_five_tone`（硬选角） | `integrated_regulation`（差异不足） |
| CF-3 三脏接近 | liver 1.20 / heart 1.00 / spleen 1.00 | `personalized_five_tone`（硬选角） | `integrated_regulation`（margin 0.0625 < 0.08） |
| CF-4 精确并列 | liver 1.00 / heart 1.00 | `basic_wellness` | 可接受（并列无主导，退基础舒缓），但更优是 `integrated` |

> 关键：CF-2 的 raw ratio = 1.11 < 1.20、CF-3 的 normalized margin = 0.0625 < 0.08，在 Sprint 6 冻结门槛下都该走 `integrated`。Two-Mode 把它们全改成了硬选主音，这是医学上不可接受的倒退。

### 医学意见

恢复三分语义：`basic_wellness`（无合法方向/信息不足/直接矛盾）→ `personalized_five_tone`（单一主导，或主导差异足够）→ `integrated_regulation`（多方向接近，不指定主音、保留均衡权重）。

---

## D-7：coverage / margin / ratio 各守其职，不得整体降级

**结论：否决"三者全部 audit-only"。三个门槛必须恢复分层路由职责。**

### 职责划分

| 门槛 | 职责 | 冻结值 | 医学含义 |
|---|---|---|---|
| **coverage** | 信息量下限 | 分母 8，门槛 0.50 | "证据够不够谈主导"——不够则 basic，但不是"无意义审计字段" |
| **margin** | 多候选主导性 | 0.08（≥） | "第一第二差多少"——差不足则 integrated |
| **ratio** | 多候选主导性 | 1.20（≥） | "第一是第二的几倍"——倍数不足则 integrated |

### 分层逻辑（医学上自洽）

```text
coverage < 0.50            → basic_wellness（信息不足，不硬选）
coverage ≥ 0.50 且 0 候选  → basic_wellness（无合法方向）
coverage ≥ 0.50 且 1 候选  → personalized_five_tone（唯一方向）
coverage ≥ 0.50 且 ≥2 候选：
    margin ≥ 0.08 且 ratio ≥ 1.20 → personalized_five_tone（主导可靠）
    否则                          → integrated_regulation（方向接近，不硬选）
    存在 unresolved direct contradiction 命中 top1 → basic_wellness
```

### 为什么不能"audit-only"

- **coverage audit-only** 的后果：3/8 事实、coverage=0.375 仍可 `personalized`（基线实测）——证据稀薄却硬给主音，违反"信息不足不宣称主音"。
- **margin/ratio audit-only** 的后果：CF-2/CF-3 的"接近"全部变成"硬选 top1"，正是 D-6 要拦的倒退。
- 三者不是"装饰性指标"，而是把"噪声"与"主导"区分开的医学闸门。

### 医学意见

恢复 `coverage` 作为 Evidence Gate 的必要条件、`margin/ratio` 作为多候选 Dominance Gate。`direct_contradiction` 作为新增安全网保留（它是对的，见 §5）。

---

## D-8：negated 中性排除，内部与公开一致

**结论：否定事实从个人五音评分中中性排除——不正向支持器官，也不默认负向；评分层与解释层必须一致。**

### 医学依据

- "没有失眠"≠"有反向健康证据"。它通常只说明该症状未被确认，不能自动推出相反证候（如"肾阴充足"）。因此**不能把 negated 统一乘 -1**（那是制造虚假的反向证据）。
- 但也不能让它**正向**贡献器官支持度——否则"否认失眠"反而推动了心/脾/肾的方向，逻辑上自相矛盾。

### 当前基线的错误（实测）

```text
negated=True → FactEvidence.direction=contradicting
             → OrganEvidenceLink.direction 仍 = supporting（映射无 contradicting 方向）
             → direction_signed 恒 +1.0
             → 否定事实正向累加器官支持度
             → 可促成 personalized_five_tone
             → 但 public_facts 过滤 direction≠supporting → 该事实从公开理由消失
```

**结果：内部选了主音，公开却"缺少可公开引用的依据"——决策依据与解释依据脱节。** 这是 D-8 要修的核心。

### 医学意见（中性保守方案）

1. **评分层**：negated 事实不进入正向器官支持度累加（中性排除，非 -1）。
2. **coverage**：negated 事实不计入"支持性覆盖度"；可单独记录 `contradicting_fact_count` 供审计。
3. **冲突**：negated 与问卷同 claim 方向相反，保留为 `direct_contradiction` 信号（已有，正确）。
4. **解释层**：negated 事实不作为正向理由展示（现状已如此，保留）。
5. **仅否定事实的总体**：不产生 `personalized_five_tone`，走 `basic_wellness` 或 `integrated`。

---

## 配套裁定 D-1~D-5（速记）

| ID | 结论 |
|---|---|
| D-1 | negated 不正向、不默认负向，先中性排除（同 D-8） |
| D-2 | negated 不计入支持性 coverage，拆分 `supporting` / `contradicting` 两个计数 |
| D-3 | subject=other/unknown 不进入个人五音评分（走路线 B，见附案）；self 才可支撑个人结论 |
| D-4 | 仅否定事实构成的总体 → basic_wellness，不宣称主音 |
| D-5 | 同 claim 多份 document 去重保留，但须保留来源数量/多样性指标供审计，避免 coverage 低估 |

---

## 附：subject 路线 B 可行性结论（供陈/INT-2）

已核实数据流：`NormalizedFact.subject` 已落库（DB 列 `nullable=False`），`presentation_json["normalized_facts"]` 含 subject，仅 `_fact_evidence()` 构造 `FactEvidence` 时未带入。

**路线 B 可行**：在 assessment 权威证据输入阶段（`load_confirmed_facts` 之后、`_fact_evidence` 之前）按 `subject` 分流——`self` 进入个人五音评分，`other/unknown` 不进评分但保留原始事实 + 审计来源，保证 Assessment / Diagnosis / 五音选择 / 解释四层一致。无需加字段、无需迁移。详细方案与验证测试另出。

---

## 结论一句话

**两档化不可接受。** 恢复三档（保留 integrated），coverage 管信息量、margin/ratio 管多候选主导性、direct_contradiction 管矛盾拦截，negated 与 other/unknown 在权威证据输入阶段中性排除，评分层与解释层统一。落地由 Owner/INT-2 协调，本稿不动任何生产实现。
