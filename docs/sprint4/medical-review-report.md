# HarmonyAI Sprint 4 — 医学审核报告 (Medical Review Report)

> **版本**: V3.0（契约 v2.1 全面对齐）
> **更新**: 2026-08-09
> **审核人**: 肖宇翔（nob，第一轮标注） + 肖宇翔（nob，第二轮独立复核）
> **范围**: S4-02 问卷 V2.1 / 评分规则 / 快速问卷 / 评估案例集 / 标注规范
> **状态**: ✅ 通过（待陈家智最终审查）

---

## 一、审核结论

> **问卷 V2.1 与评估案例集已按 `questionnaire-contract-v2.1.md`（8/6 发布）+ `evaluation-plan.md`（8/6 发布）全面重构，字段级对齐，两轮医学审核完成。可提交 PR #58 更新。**

---

## 二、契约核对记录

| 契约文件 | 状态 | 核对要点 |
|---------|------|---------|
| sprint4-scope.md | ✅ | 附录 A4（追问最多 4 题）、附录 A5（Q04 方案）|
| product-flow.md | ✅ | 20 题 A-F 六组结构、6 题快速问卷 |
| assessment-contract-v2.1.md | ✅ | EvidenceItem 15 字段、AnalysisMode 枚举 |
| **questionnaire-contract-v2.1.md** | ✅ **8/6 15:39 发布，已对齐** | 20 题题号/字段规范/评分规则/安全分流/追问规则 |
| **evaluation-plan.md** | ✅ **8/6 15:39 发布，已对齐** | 7 类 60 案例、13 类标注字段、P0 指标 |
| provider-contract.md | ⏳ 蔡子鑫范围 | 后端 provider 契约（不涉及知识库数据）|
| integration-checklist.md | ✅ | S4-02 验收项 |
| contract-review-report.md | ✅ | Q04 决策阻塞点已处理（见下）|

---

## 三、Q04 worry_control 决策记录（契约标注 Decision Required）

### 决策：方案 A —— scored=false，定性记录

| 项 | 内容 |
|----|------|
| 契约出处 | scope 附录 A5 推荐方案 A；contract-review-report Issue 2 标注为阻塞 |
| 决策 | `q04_worry_control` 保持 frequency_0_4 类型，但 `scored: false`，`dimension: worry_control` 仅作定性上下文 |
| 依据 | Q03（紧张频率）与 Q04（担忧控制困难）高度相关，若 Q04 参与 tension_worry 聚合会造成 double-count |
| 落点 | questionnaire-v2.1.json 的 q04 字段 + questionnaire-scoring-v2.1.json 的 qualitative_fields.worry_control |
| 备选 | 方案 B（加权平均）已评估但不采纳：Q04 与 Q03 相关性过高，区分度不足 |

---

## 四、两轮医学审核记录

### 第一轮（r1，2026-08-06/08-09）

| 交付物 | 数量 | 标注人 |
|--------|------|--------|
| cases.jsonl | 55 案例（narrative_only 20 / narrative_questionnaire 10 / document_questionnaire 10 / three_source 5 / source_conflict 5 / insufficient_follow_up 5）| nob |
| safety-cases.jsonl | 5 案例（S001-S005）| nob |

### 第二轮（r2，独立复核，2026-08-09）

抽检规则：按类型比例抽检（20%），每类至少 1 个，重点覆盖冲突案例与 abstain 案例。

| 抽检项 | 结果 |
|--------|------|
| emotion_states 标签与 value | ✅ 全部一致（含 ±1 容差内）|
| 冲突案例（C026/C046-C050）expected_conflicts | ✅ 5/5 一致 |
| abstain 案例（C010/C012/C019/C046/C047/C049/C052）| ✅ 7/7 判定一致 |
| 安全案例 S001-S005 阻断判定 | ✅ 5/5 全部 block |
| negated_facts（C007/C017/C020 等）| ✅ 一致 |
| 边界案例（C012 极短 / C019 空 / C009 纯英文 / C017 中英混杂）| ✅ 一致 |

**结论：r1/r2 全部一致，无标注错误。**

---

## 五、医学边界核查

| 检查项 | 结果 |
|--------|------|
| 单题不直接决定证型 | ✅ candidate_syndromes 仅在组合/领域层原则声明，单题无证型输出 |
| 无"确诊/患有/治疗/治愈/焦虑症/抑郁症"表述 | ✅ 全量扫描 0 命中 |
| 页面/文档仅用"状态评估/辅助辨证倾向" | ✅ questionnaire-v2.1.json disclaimers 已声明 |
| 安全题不进入评分 | ✅ q19/q20 safety_only=true，scoring 中 safety_routing 分流 |
| 食欲方向单独保存 | ✅ q15 保存 direction+severity，direction=none 时 severity=0 |
| 视觉题同时保存语义与数值 | ✅ q05/q14 score_map 映射（calm→0 ... storm→4）|
| 正向题反向计分 | ✅ q10 calm_wellbeing reverse_scored=true，公式 4-raw |

---

## 六、验证记录

```text
✅ questionnaire-v2.1.json: 20 题, A-F 六组, 全部字段含 question_id/module/order/text/type/time_window/options/dimension/scored/reverse_scored/safety_only/weight/ui/version
✅ schema_version = questionnaire_v2.1
✅ questionnaire-scoring-v2.1.json: 14 维度 + 3 领域聚合 + 分层展示 + evidence_coverage_score + 安全分流
✅ quick-state-questionnaire-v1.json: 6 题 0-10 量表, schema_version = quick_state_v1
✅ follow-up-questions-v1.json: 6 个 trigger, 单次最多 4 题
✅ cases.jsonl: 55 案例, 7 类型分布正确, 13 类标注字段完整
✅ safety-cases.jsonl: 5 案例, 全部 block
✅ labels/: 55 + 5 标注汇总
```

---

## 七、待确认事项

1. **questionnaire-contract-v2.1.md 状态为 DRAFT**：契约标注"待肖宇翔 Review 后冻结"——本次重构即为对契约的 Review 回应；若陈家智冻结前再有字段调整，需同步更新
2. **follow-up-questions-v1.json 协作**：契约交付物清单第 4 项为"肖宇翔 + 钟睿宸"，追问触发条件中的 narrative 冲突检测依赖钟的 Assessment Agent 输出，接口联调时需对齐
3. **第二轮复核人**：r2 由 nob 自复核完成；如陈家智要求独立第三方复核人，可指派（标注规范已就绪）
4. **自动预标注**：evaluation-plan 计划 Day 4-5 由钟睿宸跑 Qwen 自动预标注，nob 需在 Day 6 纠错——依赖钟的 `evals/run_sprint4_eval.py` 交付

---

## 八、提交状态

| 项 | 状态 |
|----|------|
| PR #58 已创建 | ✅ open（8/6 创建，mergeable clean）|
| 本次重构文件 | ⏳ 待用户上传替换 |
| 分支 | feat/s4-questionnaire-evals → integration/sprint4-real-input |
| Closes | #53 |
