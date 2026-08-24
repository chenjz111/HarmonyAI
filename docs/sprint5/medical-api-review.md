# HarmonyAI V3 医学 API 审核报告（Medical API Review）

> 版本：medical_v3.0-r1 ｜ 审核人：nob（肖宇翔，Medical Knowledge Engineer）
> 日期：2026-08-24 ｜ 依据：Issue #77「API 调研与选型补充（2026-08-24）」
> 范围：医学表达和产品边界审核（不负责技术 Provider 选型与预算批准）

---

## 一、总体结论

**医学边界审核通过（有条件）**。核心红线确认：V3 全链路（Assessment / Diagnosis / Prescription / Music / 反馈 / RAG / 宣传文案）只能称"状态评估 / 辅助辨证倾向 / 音乐调养参考"，不得出现诊断、确诊、治疗、疗效类表述；音乐 Provider 能力不足时不得以模型生成内容替代 approved Five-Tone Mapping。

---

## 二、禁止用语清单（全链路适用）

| 类别 | 禁止表述 | 允许替代 |
|------|---------|---------|
| 诊断类 | 诊断、确诊、你是X证、你患有X | 状态评估、辅助辨证倾向 |
| 治疗类 | 治疗、治愈、疗效、本音乐可治疗 | 音乐调养参考、帮助放松 |
| 身份类 | 病人、患者 | 用户、朋友 |
| 结论类 | 你有X病、你需要就医（除 Safety 场景） | 你的状态更偏向X、建议关注 |
| 夸大类 | 100%有效、根除、包治 | 不出现 |

**落地位置**：
- `knowledge/v3/knowledge-manifest-v3.0.json` → `forbidden_expressions`（12 项）
- Provider Prompt 边界：钟睿宸在 Understanding Provider 配置时须加入该清单

---

## 三、Qwen 测试案例审核（覆盖度检查）

按 Issue 要求，验收案例须覆盖：**否定、历史情况、他人信息、证据不足、冲突表达**。

| 覆盖项 | 案例 | 验证点 |
|--------|------|--------|
| 否定 | V3_C001（"心情其实挺好…没有低落"）| 问卷 q04=3 vs 叙述否定 → 应产生 conflict 而非强行归肺 |
| 历史情况 | V3_N001（"最近工作压力大"）| 时间窗 past_7_days 内，作当前状态证据 |
| 他人信息 | （新增建议）"我妈说她睡不好" | subject=other → 不计入本人五脏 Evidence |
| 证据不足 | V3_I001 / V3_I002 | organ_net < 0.20 → abstain，不强行映射 |
| 冲突表达 | V3_C001 | 标记 conflict，不静默覆盖 |

**结论**：现有案例覆盖 4/5 项；**他人信息（subject=other）缺案例**——建议钟睿宸的 Understanding 测试补充 1 条（见下方补充案例）。

---

## 四、补充脱敏测试案例（供 API 候选验证用，虚构数据）

### 案例 A：他人信息隔离
```json
{
  "case_id": "V3_X001",
  "type": "other_subject",
  "input": {
    "questionnaire_answers": {"q01": 0, "q02": 0, "q03": 1, "q04": 0, "q05": 0,
      "q06": ["none"], "q07": ["none"], "q08": ["none"], "q09": ["none"], "q10": ["none"]},
    "narrative_text": "我妈说她最近总睡不着，还老觉得腰酸。",
    "document_text": ""
  },
  "expected": {
    "subject_check": "narrative 主体为 other（母亲），不计入本人五脏 Evidence",
    "primary_organ": null,
    "safety_flags": [],
    "abstain": true,
    "expected_tones": []
  }
}
```

### 案例 B：RAG 引用不可溯源
```json
{
  "case_id": "V3_X002",
  "type": "rag_citation",
  "input": {"query": "胸闷和什么有关", "expected_behavior": "RAG 必须返回带 source 引用的知识条目；无 source 或未批准条目不得返回"},
  "expected": {"citation_required": true, "forbidden": ["根据中医理论一定…", "研究表明治愈…"]}
}
```

---

## 五、医学边界 Review 结论（逐项）

| # | 检查项 | 结论 |
|---|--------|------|
| 1 | RAG 引用及 Provider Prompt 边界 | ✅ 已定义禁止用语；RAG 条目须可溯源（见 knowledge-manifest rag_review_notes）|
| 2 | 音乐生成依据 | ✅ Five-Tone Mapping 为 approved 资产；Provider 能力不足时**不得**以模型生成替代 |
| 3 | 结果页与宣传文案 | ⚠️ 前端文案由彭翔实现，已在本报告禁止用语清单中约束；建议验收时人工抽查结果页 |
| 4 | 脱敏测试案例 | ✅ 已提供 V3_X001/V3_X002 + 主案例集（evals/sprint5/）；全部虚构，无真实病历 |
| 5 | 是否替代技术/预算批准 | ❌ 本报告仅医学边界，技术选型与预算由陈家智最终批准 |

---

## 六、遗留事项（不阻塞医学资产，供集成阶段处理）

1. **executable schema 中 `AssessmentV3Request.user_goal` 仍为必填**，与 Owner Flow Amendment（8/24 UserGoal 从 V3 移除）冲突——待陈家智修订可执行 Schema（或 Issue 确认处理方式），医学资产已按 Amendment 不包含 UserGoal。
2. **前端结果页文案**待彭翔实现后人工复核（禁止用语清单落地）。
3. **他人信息（subject=other）测试案例**已补充建议，待 Understanding 测试纳入。
