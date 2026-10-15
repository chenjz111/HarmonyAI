# Sprint 7 · R1/R2 医学证据反事实审计（基线版）

- **负责人**：肖宇翔（nob）· 医学知识签核
- **日期**：2026-10-15
- **对应 Issue**：#154 `[S7-M1][R1/R2-B]`
- **审计基线**：`team/s7-m1-w2-baseline` @ `ff879f70a19328dbe492bf3aa9418e681a5db06b`
- **审计分支**：`test/s7-r1r2-evidence`（本地，未推送）
- **执行命令**：`python -m pytest tests/sprint7_audit -q`
- **执行结果**：**78 passed**
- **外联记录**：Provider / 网络生产调用 / 生产库操作 = **0**

---

## 1. 头号发现：V2.1 路由重构（比"否定事实正向累加"更优先）

基线的 `resolve_organ_dominance` docstring 亲口写明：

> Coverage, normalized margin and raw ratio remain persisted audit metrics;
> they have no V2.1 normal-mode routing authority. This normal producer never
> emits `integrated_regulation`; legacy consumers still accept it.

**这意味着 Sprint 6 医学侧 sign-off 过的三档机制被实质改写：**

| 维度 | Sprint 6 冻结（旧分支） | 基线 `ff879f70` | 医学影响 |
|---|---|---|---|
| `integrated_regulation`（综合调适） | 正常产出（多方向接近） | **正常路径不再产出** | 三档 → 两档 |
| coverage 门槛（0.50） | 拦路由（<0.5 → basic） | **只审计，不拦** | "信息不足"也能出主音 |
| margin 门槛（0.08） | 拦路由 | **只审计，不拦** | "微弱主导"也硬选 top1 |
| ratio 门槛（1.20） | 拦路由 | **只审计，不拦** | 同上 |
| 两候选 raw 相等 | → integrated | → **basic**（EXACT_AUTHORITY_TIE） | 并列不再"综合" |
| major conflict | → basic（UNRESOLVED_MAJOR_CONFLICT） | **不拦**（除非 direct_contradiction） | 粗粒度兜底移除 |
| direct contradiction（新增） | 无 | 命中 top1 → 反事实重算 → 不唯一 → basic | 新安全网 |

**新 reason 顺序**（实测）：upstream abstain → 零候选 → 并列 tie → 直接矛盾 → 单候选 → 多候选取 top1。

---

## 2. 版本迁移（v1→v2），不是运行时资产漂移 —— 但医学签核存疑

**（本节已更正：初版误将"v1 资产 vs v2.1 代码"说成"运行时漂移"，实为版本迁移。）**

基线 `knowledge/v3/` 下**同时存在两份资产**，代码加载的是 v2：

```
dominance-rule-v1.json   schema_version=1.0  asset_version=dominance-rule-v1.0-r1
                         medical_review.review_version = s6-p1b-medical-review-v1   ← 我签的三档
dominance-rule-v2.json   schema_version=2.1  asset_version=dominance-rule-v2.1-r1
                         medical_review.review_version = two-mode-v2.1-contract-freeze
```

代码常量已切到 v2（`DOMINANCE_RULE_ASSET_VERSION = "dominance-rule-v2.1-r1"`、`DEFAULT_DOMINANCE_RULE_FILENAME = "dominance-rule-v2.json"`），v2 明确写着：

```
evidence_gate.routing_authority = "audit_only"
dominance_gate.normalized_margin_routing_authority = "audit_only"
dominance_gate.raw_ratio_routing_authority = "audit_only"
candidate_policies: one_legal_candidate / two_or_more_unique_top1 / zero / exact_tie
                    （无 integrated_regulation）
```

→ **代码与 v2 资产一致，不存在"代码偷偷偏离资产"。** 初版的"漂移"结论作废。

**真正的关键问题（codex 提示，已核实）：v2 的 `medical_review.status="approved"` 是谁签的？**

- v2 资产的 `medical_review.review_version = "two-mode-v2.1-contract-freeze"`；
- 我的 Sprint 6 医学签核是 `s6-p1b-medical-review-v1`（三档，含 `integrated_regulation`）；
- `docs/product/TWO_MODE_FIVE_TONE_DECISION_CONTRACT_V2_1.md` 全文 270 行，**无任何医学签核记录**，只标注 `Implementation acceptance: OWNER ACCEPTED`，且 `Android Owner Product Acceptance / Git Closure / Sprint 6 Closure` 均 **PENDING**。

**结论：Two-Mode V2.1 目前是「Owner 接受的产品/工程实现」，不是「重新完成医学签署的正式变更」。** v2 资产里的 `medical_review.status="approved"` 缺乏对应的医学签核主体与记录，需向 Owner 核实。

---

## 3. 否定事实（negated）的完整去向

这是 #154 点名"跟踪 negated / direction"的落实，现已全链实测：

| 阶段 | 否定事实的去向 |
|---|---|
| S0 抽取 | `UnderstandingProviderFact.negated=True` |
| S1 admission | 只做窄字面拦截（见 §4），未拦截时照常通过 |
| S2 落库 | `FactEvidence.direction = contradicting` |
| S7 聚合 | **link.direction 恒 supporting → 否定事实仍正向累加**（实测 raw support 逐位相同） |
| S9 路由 | 否定事实照常撑起 legal candidate |
| S12 公开 | **`public_facts` 过滤 direction≠supporting → 否定事实消失** |

**结论：否定事实在内部"被当作支持证据"推进决策，在公开"被当作不可引用"抹掉 —— 两端语义相反。**

---

## 4. subject（self/other/unknown）的完整去向

| 阶段 | subject 的去向 |
|---|---|
| S0 抽取 | `subject ∈ {self, other, unknown}` |
| **S1 admission** | **唯一消费点**：只认"母亲/父亲/家属 + label"这一种字面模式；仅当 `subject=="self"` 时拦截（`EXPLICIT_SUBJECT_MISMATCH`）。`other/unknown` **从不被查** |
| S2 落库 | `FactEvidence` 无此字段，`subject` 被丢弃 |
| S3–S11 | 完全不可见 |
| S12 公开 | 靠上游 `explanation_excluded_fact_ids` 排除（DB owner 侧算好传入，本函数不读 fact.subject） |

**结论**：subject 的排除是"碎片化"的 —— 一层窄字面拦截 + 一层上游排除名单，中间整条链都不携带该维度。一个 `subject=other` 的家属事实，只要没被误标成 self，就能一路通过并进入公开理由。

---

## 5. 内部/公开不一致（可复现脱节案例）

实测通过（`test_negated_only_population_personalizes_internally_but_explains_nothing`）：

```
输入：liver 两个事实，全部 negated=True
内部：aggregation 把 liver 计为 legal candidate
      resolve_organ_dominance → personalized_five_tone, dominant_organ=liver, primary_tone=jiao
公开：public_facts 把两个 contradicting 事实全过滤 → 空
      direction_explanation → "该主要调适方向缺少可公开引用的具体状态依据"
```

**内部选定了"角"音，对外却说"缺少可公开引用的依据"。** 这是"内部决策依据与公开理由一致性"验收项的直接反例。

---

## 6. 待医学裁定（需 Owner + 独立医学规则负责人签署）

| ID | 问题 | 关联发现 |
|---|---|---|
| **D-1** | 否定事实是否应在器官权重层产生负向贡献？（当前恒 +1） | §3 |
| **D-2** | 否定事实计入 coverage 是否合理？（`counted_directions` 含 contradicting） | §3 |
| **D-3** | `subject=other/unknown` 是否应被 admission 排除？当前只有"亲属+self"被拦 | §4 |
| **D-4** | 仅由否定事实构成的总体应产出什么模式？（当前照常 personalized） | §5 |
| **D-5** | 同 claim 两条 document 也去重，是否造成 coverage 低估？ | 见 §7 未列出的 effective 测试 |
| **D-6** | `integrated_regulation` 正常路径不再产出，是否接受"三档 → 两档"？ | §1 |
| **D-7** | coverage / margin / ratio 降级为纯审计指标，是否接受？ | §1、§2 |
| **D-8** | 公开层过滤 contradicting 与内部正向累加的矛盾，选哪边？ | §5 |

---

## 7. 审计覆盖与回执

`tests/sprint7_audit/` 共 **78 个用例**，覆盖 S0–S12 全链：

| 文件 | 覆盖 | 用例 |
|---|---|---|
| `test_admission.py` | S1 准入（subject 窄拦截 / 否定反转 / 时间窗 / span / 严重度） | 12 |
| `test_direction_provenance.py` | 两个 direction 的来源与不传递性 | 3 |
| `test_negation_contribution.py` | 否定事实的权重贡献 + direct contradiction | 7 |
| `test_subject_chain.py` | subject 断链全过程 | 6 |
| `test_effective_population.py` | S3/S4 去重与有效总体 | 7 |
| `test_coverage_and_candidate_gates.py` | S5 coverage + S8 候选门槛 | 8 |
| `test_dominance_routing_v21.py` | V2.1 路由重构（integrated 消失 / 门槛降级 / tie） | 8 |
| `test_public_explanation.py` | S12 公开解释 + 内部/公开脱节 | 9 |
| `test_stage_s1_s12_auditability.py` | 阶段可用性 + 离线保证 + docs 范围 | 4 |

**78 passed / 0 failed / 0 skipped**（离线执行）。

---

## 8. 未做 / 边界（显式声明）

- 未修改任何生产算法、规则资产、GenerationSpec、Provider、生产 schema。
- 未运行仓库默认测试命令（可能外联）；只运行自建离线审计包。
- 未推送任何内容、未建远端分支、未在 Issue/PR 评论。
- S11 持久化落库路径未覆盖（需 DB，本轮不引入）。
- `parameter_explanations`（S12 的规则参数解释）未覆盖（依赖 agent3 内部 builder，留待后续）。

---

## 9. 结论一句话

基线把路由从"三档 + 阈值门"改成了"两档 + 直接矛盾拦截"（v2 资产的明确设计，代码与资产一致），但 **v2 声称的"医学批准"缺乏我参与的签核记录**，加上**否定事实两端语义相反、subject 碎片化** —— 这三点都需要 Owner 先澄清医学签署主体，再谈是否接受。在此之前生产规则保持不变（本审计未动任何生产代码）。
