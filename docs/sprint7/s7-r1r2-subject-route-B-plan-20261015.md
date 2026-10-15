# Sprint 7 · subject 路线 B 方案（在权威证据输入阶段排除 other/unknown）

- **出具人**：肖宇翔（nob）· 医学知识签核
- **日期**：2026-10-15
- **性质**：方案，非实现。不改生产代码/规则资产/schema，不改迁移。仅供 Owner/INT-2 决策路线 A/B。

---

## 1. 结论：路线 B 可行，无需加字段、无需迁移

已核实数据流（基线 `ff879f70`）：

```
NormalizedFact.subject                    schema 第196行 + DB 列 nullable=False（已落库）
presentation_json["normalized_facts"]     含 subject（understanding_extraction.py:130 写入，model_dump 全字段）
load_confirmed_facts() → fact dict        含 subject（assessment_service.py:578 facts.append(item) 追加原始 dict）
_fact_evidence()                          ★ 唯一断链点：不读 subject（assessment_service.py:595-602）
FactEvidence                              无 subject → 下游 S3~S12 全丢
```

**subject 数据在 assessment 入口处是完整可用的**，只是 `_fact_evidence` 没把它带进 `FactEvidence`。所以路线 B 只需在**评分入口**按 subject 分流，不需要动 schema/迁移。

---

## 2. 分流点与分流逻辑（方案，供工程实现参考）

分流点：`create_assessment` 中，`load_confirmed_facts` 之后、`_fact_evidence` 之前（`assessment_service.py` 约 888-891 行的 `evidence = [...]` 构造处）。

```text
对每个 fact（含 subject）：
  subject == "self"                → 进入个人五音评分（生成 FactEvidence）
  subject in ("other","unknown")   → 不生成 FactEvidence；
                                     原始 fact 保留到 assessment 的审计记录（如 presentation_json 的
                                     excluded_subject_facts），记录 fact_id / claim_code / subject / source_refs，
                                     供追溯，不参与评分
```

要点：

1. **在评分入口排除，不是解释层排除**——这样 Assessment / Diagnosis / 五音选择 / 公开解释四层天然一致，不用在每层补 subject 过滤。
2. **保留原始事实与审计来源**——other/unknown 事实不删除、不篡改，仍落审计，只是不进入"个人五音"这条评分链。
3. **questionnaire 事实天然 subject="self"**（`questionnaire_evidence.py:118/171`），不受影响。

---

## 3. 四层一致性保证

| 层 | subject 处理 |
|---|---|
| Assessment | 只给 self 生成 FactEvidence |
| Diagnosis | 基于 self 的 aggregation / decision |
| 五音选择 | 基于 self 的 decision（dominant_organ / primary_tone） |
| 公开解释 | `public_facts` 只引用 self 的 supporting 事实（现状方向过滤 + 输入已排除 other/unknown） |

**一致性成立**：因为 other/unknown 从未进入 FactEvidence，下游各层根本没有它们，不存在"评分用了、解释没提"的脱节。

---

## 4. 若路线 B 不满足（触发路线 A 的条件）

陈已明确：若 B 无法保证四层一致，再提 A（加 `FactEvidence.subject` + 迁移，由 INT-2 协调）。当前判断 B 已足够，不触发 A。触发条件供记录：

- 若后续需要"other/unknown 事实的差异化处理"（例如 other 作为背景影响 mode 但不影响主音），则 FactEvidence 需要携带 subject，转 A。
- 若需在 Diagnosis/解释层按 subject 做二次判断，而不仅是入口排除，转 A。

---

## 5. 验证测试（已写，随包提交）

`tests/sprint7_audit/test_subject_route_b.py` 证明三件事（全离线、合成数据、真实 schema）：

1. `NormalizedFact` 含 subject，`FactEvidence` 不含——确认断链点与上游可用性。
2. 按路线 B 分流的原型函数：self 进评分、other/unknown 不进评分但保留原始事实。
3. 分流后四层一致：评分（snapshot/decide）与公开解释（public_facts）只用 self，不再出现"内部选主音、公开说依据不足"的脱节。

---

## 6. 边界

- 本方案只出测试与方案，**不修改生产实现**。是否落地、何时落地，由 Owner/INT-2 决定。
- 医学规则生产实现（dominance-rule、organ-mapping、resolve_organ_dominance）在本方案中不动。
