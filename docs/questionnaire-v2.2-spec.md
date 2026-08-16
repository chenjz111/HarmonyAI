# HarmonyAI Questionnaire v2.2 与评估体验规范

## 1. 目标

Questionnaire v2.2 在保持五 Agent 架构、Safety 状态机和 v2.1 向后兼容的前提下，降低填写与确认负担。系统仍综合问卷、自由描述和已确认的材料文字形成状态评估；自由描述或 OCR/AI 暂不可用时，必须诚实标记来源状态，并允许问卷提供基础评估。

## 2. 问卷变化

- 总题数仍为 20 题，Q19、Q20 的安全语义保持不变。
- Q1 必须选择一个主要音乐目标，可再选择一个不同的次要目标，最多两个。选择“其他”时必须补充文字。目标只作为音乐偏好，不作为症状证据或诊断依据。
- Q14 使用五档电量：精力充足、比较充足、还有一半、电量较低、几乎耗尽；对应低精力分数为 0、1、2、3、4。
- Q16 保持多选和“无明显不适”互斥；选择“其他”时必须补充文字。自定义内容作为用户提供的身体感受证据进入 Assessment，不直接硬编码到脏腑、证型或调式。
- Q19、Q20 在视觉上作为最后的安全确认区，不参与普通状态评分；Frozen Safety 规则不变。

Canonical artifacts：

- `knowledge/questionnaire-v2.2.json`
- `knowledge/questionnaire-scoring-v2.2.json`
- `tests/contract/fixtures/questionnaire-v2.2.contract.json`

## 3. Assessment 页面

问卷提交后只展示一个用户确认页：

1. 用通俗文字说明系统目前如何理解用户状态；
2. 仅展示本次参考了哪些来源，不展示证据数量、内部字段、可信度百分比或原始 provider 信息；
3. 提供“这与我现在的情况基本相符”和“我想补充或修改”两个入口；
4. 用户修正产生新 revision，后续 Workflow 必须使用最新 `assessment_id` 和 `revision`。

普通来源冲突、缺失信息和内部 follow-up 不再各自形成额外页面。若 Safety 状态为 `needs_verification`，材料安全核验嵌入这一确认页；已确认的心理或急性身体风险仍进入原 Safety Support，不进入普通 Diagnosis、Prescription 或个性化音乐服务。

## 4. Feedback 体验

- “明显好一些 / 稍微好一些 / 差不多 / 感觉更不舒服”为 2×2 大卡片，且是唯一必填项。
- 听前听后评分、整体满意度、放松程度、音乐匹配度、是否继续使用、是否收藏均为选填。
- 支持记录喜欢的音乐特点、希望下次调整的方向和自由体验文字。
- 未填写的评分保持为空，不能用默认值制造反馈数据。
- Feedback 只更新个人偏好；`global_rule_update` 必须始终为 `false`。

## 5. 兼容与安全边界

- `questionnaire_v2.1` 请求与旧测试继续有效。
- `questionnaire_v2.2` 使用结构化的 Q1 和 Q16 value。
- Q19 任一非“从未有过”答案、Q20 任一 emergency 选项仍进入既有 Safety flow。
- Comfort Audio 仍是用户主动选择的非个性化安抚音频，不能解除 Safety 状态，也不能被描述为音乐处方或治疗。
- 本系统输出仅称为状态评估或辅助辨证倾向，不构成医学诊断或治疗建议。
