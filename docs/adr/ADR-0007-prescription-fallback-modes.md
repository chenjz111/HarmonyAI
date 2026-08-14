# ADR-0007: 处方 Agent 内部按「辨证可信度」选择处方精细程度（四档处方模式）

> **状态：** 已采纳
> **日期：** 2026-08-14
> **决策者：** 陈家智（AI Architect）

---

## 背景

五 Agent 架构保持不变：① Assessment、② Diagnosis、③ Prescription、④ Music、⑤ Feedback。

此前诊断（Agent②）遇到「辅助辨证倾向不够明确」时会 abstain，下游工作流以
`diagnosis.abstained == True` 直接跳过处方（Agent③）与音乐（Agent④）。结果：用户完成
完整 20 题问卷后，仅因单一证型规则需要「两个独立维度同时出现」、而用户的症状分布较
分散，就被告知「信息不足」，拿不到任何音乐。

这与产品目标矛盾：**评估足够、状态真实的用户，不应因为「辨证不够细分」而拿不到音乐。**

## 设计原则

1. **五 Agent 架构不变**：不新增第六个 Agent，不改任何 Agent 名称。
2. **Diagnosis uncertainty ≠ no music**：诊断不确定不再等于没有音乐。
3. **Prescription specificity follows certainty**：辨证可信度决定处方精细程度，而非是否给出处方。
4. **Safety / true information insufficiency 仍 hard stop**：安全与真实信息不足硬阻断。
5. **wellness 是 non-clinical 处方策略，不是医学结论**。
6. **Prescription 不重新决定医学 diagnosis**：不发明候选分差阈值来重新判定「是否完成辨证」。
7. **不使用固定虚假 confidence 制造精确感**：数值置信度必须来自真实上游数据。

## 核心原则

> **辨证可信度决定「处方精细程度」，而不是决定「有没有音乐处方」。**

- 只有 **安全风险（SAFETY）** 与 **真实信息不足（TRUE INFORMATION INSUFFICIENT）** 才阻断处方与音乐。
- 诊断（Agent②）保持保守：允许诚实 abstain / 低置信，**不放松其医学门槛**。
- 处方（Agent③）在诊断不够明确时，**降级处方精细程度**，而不是**取消处方**。

## 决策

处方 Agent 内部新增 `prescription_mode`（Agent③ 的**内部功能**，不是第六个 Agent），
按确定性优先级选择：

| 优先级 | 模式 | 触发条件（复用 Agent② 既有结论，不发明阈值） | 选调依据 | 示例输出 |
|--------|------|---------------------------------------------|----------|----------|
| 1 | `syndrome_based` | `abstained == False` 且仅有 1 个有效候选 | 证型 → 五行 → 五音 | 角调 / 68 BPM |
| 2 | `candidate_blend` | `abstained == False` 且 ≥2 个有效候选 | 归一化 tone 权重、top-K | 角调(0.54)+徵调(0.46) |
| 3 | `wellness` | abstain 且状态整体平稳（无中度、至多 1 个轻度维度） | 平和安神宫调 | 宫调 / 62 BPM |
| 4 | `emotion_based` | abstain 且状态非平稳、但评估充分 | 主导情绪维度 → 五音 | 主导「紧张担忧」→ 角调 |

### 模式选择不使用「候选分差阈值」

早期版本曾用 `top1 - top2 >= 30%` 判定「证型是否明确」。该规则被删除：它是在 Agent③ 里
重新发明医学/诊断阈值，违背原则 6。现在的选择完全复用 Agent② 已给出的结论
（`abstained` + `candidate_tendencies` 的有效候选数量），不再自行判定「辨证是否完成」。

### 阻断条件（仅此两类）

1. **安全风险：** `assessment.status == "blocked_safety"` 或 `diagnosis.abstain_reason == "SAFETY_BLOCKED"`。
2. **真实信息不足：** `evidence_coverage_score < 0.5`、`missing_information` 含 `critical`/`important`，
   或 **abstain 且无任何维度数据**（"no data" 不是平稳态，落入 true insufficient）。

「无本地多维候选」导致的 `diagnosis.abstain_reason == "INSUFFICIENT_EVIDENCE"`（评估却充分）
**不再阻断**，落入 `emotion_based` / `wellness`。

### wellness 判定（non-clinical）

`wellness` 仅在以下条件**同时满足**时选用（`_NON_CLINICAL_STABLE_*`，仅用于选择处方特异性，
不是医学判定）：

- 有维度数据（维度为空 → 不判 wellness，而落入 true insufficient）。
- 无「中度及以上」维度（归一化分 < 50，即 raw < 2）。
- 至多 1 个「轻度」维度（归一化分 ≥ 25 且 < 50）。

多个接近中等的负向维度（例如 3 个 45）不再因「每个都 < 50」被误判为「平稳」。

### 置信度解耦

禁止「诊断低置信 → 无音乐」。三个置信度概念独立：

- `assessment_confidence`（`evidence_coverage_score`）：证据覆盖度。
- `diagnosis_confidence`（Agent② 输出）：证型细分的可信度，可低、可 abstain。
- `recommendation_confidence`（Agent③ 新增）：**处方依据的充分程度**，与是否给出音乐无关。

处方新增字段（向后兼容的**增量**扩展，不删除任何既有字段）：

- `prescription_mode`：`syndrome_based` / `candidate_blend` / `emotion_based` / `wellness`。
- `source_basis`：选调依据的中文说明。
- `recommendation_specificity`：分类标签（`high` / `medium` / `conservative` / `wellness`），
  表示处方精细程度，**不是数值置信度**。
- `recommendation_confidence`：`score` 直接取 `evidence_coverage_score`（真实数据、保留两位），
  `level` 为其粗分档（≥0.8 high / ≥0.5 medium / 其余 low），`basis` 标注 `"evidence_coverage"`；
  旧 V2.0 路径无 assessment 时 `score=None`、`basis="unavailable"`，**不伪造数字**。
- `tone_weights`（仅 `candidate_blend`）：归一化 tone 权重。
- `dominant_dimension`（仅 `emotion_based`）：主导情绪维度。

### candidate_blend 无有效候选

`candidate_blend` 的定义是「存在 ≥2 个有效候选并融合」。若无有效候选，`_candidate_tone_weights`
返回空 `{}`（**不回退 `{gong: 1.0}`**），模式选择器不会进入 `candidate_blend`。空候选由上层
降级到 `emotion_based` / `wellness` 或 withhold。

### 工作流硬停止

`run_real_workflow_v21` / `continue_real_workflow_v21` 显式区分：

- **Safety** → 不产生处方、不调用 Music。
- **True insufficient** → 不产生处方、不调用 Music。
- **其余** → 运行 Prescription；仅当处方 `generation_mode == "matched"` 才调用 Music，
  否则 `music = None`。

Music Agent 在 safety / true insufficient 下**根本不会被调用**（`_should_run_music` 门控），
而不是依赖 `match_music_v2` 自己失败。

## 兼容性

`run_prescription_v2(diagnosis, knowledge_store=None, assessment=None)`：

- `assessment is None`（旧 V2.0 路径）：`_withheld_reason` 行为**逐字不变**，既有契约测试不回退。
- `assessment` 提供（V2.1 证据优先路径）：启用四档模式选择。

## 理由

1. **不新增 Agent、不改名称**：降级是 Agent③ 内部决策，架构图不变。
2. **诚实且不放大风险**：安全与真实信息不足仍硬阻断；诊断不放松医学门槛。
3. **可解释**：`source_basis` + `recommendation_reasons` + `recommendation_specificity` 说明
   「为什么是这个调式、有多具体」。
4. **确定性**：模式选择纯规则、可单测、可复现。
5. **不伪造精确**：数值置信度来自真实覆盖度，无数据时不编造。

## 后果

- **正面：** 完整问卷的分散症状用户不再落入「信息不足 → 无音乐」的死角。
- **正面：** 处方粒度与辨证可信度成正比，比「一刀切取消」更符合调养场景。
- **正面：** 增量字段向后兼容，旧客户端忽略新字段不受影响。
- **负面：** `emotion_based` / `wellness` 的推荐特异性低于 `syndrome_based`，需在文案中如实说明。
- **风险：** 需在医生复核与后续迭代中监控低特异性处方是否被误解为诊断——保持 `disclaimer` 恒定输出。
