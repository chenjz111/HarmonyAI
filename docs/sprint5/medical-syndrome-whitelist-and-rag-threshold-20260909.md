# Agent2 证候倾向白名单 + RAG 检索医学验收（2026-09-09）

> 作者：nob（肖宇翔，Medical Knowledge Engineer）｜状态：医学侧审核通过（机器可读资产已生成）
> Owner 裁决：Agent2 正式 `syndrome_code` 主键 = `syd_001`~`syd_008`；英文名称为语义 alias（不作主键）
> 目的：为 Agent2 结构化输出的"证候倾向"提供医学侧白名单；对 RAG 检索阈值给出医学验收意见；确认 13 chunk 空值语义。
> 边界：不修改 questionnaire-v3.0.1、V3.1 冻结流程、claim/organ/five-tone 映射语义与 AI 代码；本清单只约束"输出面证候倾向的命名与允许集"。

## 1. allowed_syndrome_codes（医学审核通过，8 项）

| english_code | stable_code（主键） | 中文展示名（倾向口径） | 医学含义 | 适用证据范围（支撑信号类型，非计分规则） | 不足以判断时 |
| --- | --- | --- | --- | --- | --- |
| liver_stagnation_heat | syd_001 | 肝郁化火倾向 | 肝失疏泄、气机郁滞化火；表现为烦躁易怒、口苦胁胀等（经典/教材） | 怒/烦躁类情绪信号（q01 类）、胁肋胀闷类身体信号、压力相关文档事实 | 不输出该倾向，返回 evidence insufficient（abstain，不猜测） |
| liver_qi_stagnation | syd_002 | 肝气郁结倾向 | 情志不遂致肝气郁滞，善太息、胸胁胀闷（经典/教材） | 情绪低落/思虑类信号、胁肋不舒、情志诱因背景 | 同上 abstain/degrade |
| heart_fire_flaming | syd_003 | 心火上炎倾向 | 心火亢盛上扰，心烦失眠、口舌生疮（经典/教材） | 烦躁/兴奋难静类信号（q02 类）、睡眠/心系身体信号 | 同上 abstain/degrade |
| heart_spleen_deficiency | syd_004 | 心脾两虚倾向 | 思虑伤脾、心血不足，多梦健忘、食少倦怠（经典/教材） | 思虑过度类信号、睡眠/食欲/精力类信号并见 | 同上 abstain/degrade |
| spleen_deficiency_dampness | syd_005 | 脾虚湿困倾向 | 脾气虚运化失司、湿邪困阻，腹胀便溏、身重（经典/教材） | 消化/身体沉重类信号、倦怠类信号 | 同上 abstain/degrade |
| lung_qi_deficiency | syd_006 | 肺气虚倾向 | 肺气不足、卫外不固，气短声低、易疲（经典/教材） | 呼吸/声音相关身体信号、精力类信号 | 同上 abstain/degrade |
| kidney_yin_deficiency | syd_007 | 肾阴不足倾向 | 肾阴亏虚、失于濡养，腰膝酸软、耳鸣、五心烦热（经典/教材） | 腰膝/耳鸣等肾系身体信号、长期耗损背景 | 同上 abstain/degrade |
| heart_kidney_disconnection | syd_008 | 心肾不交倾向 | 心火亢于上、肾水亏于下，心烦不寐、腰膝酸软并见（经典/教材） | 心系(失眠/烦)与肾系(腰膝/耳鸣)信号并存 | 同上 abstain/degrade |

### 医学复核确认项
- 有医学依据：8 项均有《中医诊断学》《中医内科学》（统编教材）与经典理论支撑（与 knowledge-manifest knowledge_sources 同源）；
- 不与正式问卷/五脏 Evidence 冲突：本清单不新增 claim、不改变 questionnaire-3.0.1 与 organ-mapping 计算语义；仅定义输出面倾向命名；
- 不含诊断/治疗承诺：全部为"证候倾向（调适参考）"口径，禁止出现"诊断/治疗/疗效"表述；
- 可作 Agent2 结构化输出白名单：Agent2 仅在证据支撑时输出对应 code，且必须带证据引用与倾向限定（对齐 honest pipeline：不编造证型）。

## 2. RAG 检索阈值 · 医学验收意见
1. **低相关结果必须过滤**——不相关检索片段不得作为 Agent2 rationale/证据引用；过滤是硬要求。
2. **数值阈值不拍脑袋**：医学侧不直接指定阈值数值；
3. 建议做法：医学侧提供一组 **gold 标注问题集**（query↔13 chunks，覆盖"解释类引用"场景，每对标注 相关 / 不相关 / 边界），由 AI 侧跑 embedding 计算相似度分布并给出阈值候选（召回优先于精度），Owner 批准后作为配置项；
4. 阈值未定或 Provider 失败 → **readiness fail，不得自动降级 Mock**（对齐 #118 要求）。

## 3. 13 chunk claim_codes/organ_codes 空值确认
- 确认：**有意留空，不是遗漏**——该 13 chunk 为中医理论背景解释片段，不充当问卷 claim/器官证据计算源；留空可避免被误代入 organ_net/辨证聚合。
- 建议：ingestion manifest 增加显式字段（如 `empty_claim_organ_semantics: intentional_background_explanation`）固化该语义。

## 4. 正式机器可读资产
- 已生成医学审核通过资产：`knowledge/v3/agent2-syndrome-whitelist-v3.1.json`；
- 本资产在 Owner 合并并由 Agent2 明确加载前不视为生产执行完成；任何 code、医学含义、证据范围或 abstain 语义变化均须重新医学复核。

## 5. 被审核语料身份

- chunk 数量：13；
- corpus content checksum：sha256:07d7e064dae853343787c9706c2396240ceb4430caf57039020f2471fa7bc9a0；
- source registry checksum：sha256:5096bf8509fea4641fef8ca4965245b04a253b1e0bd3910dd0a6b64bef9afb85；
- PR #118 后续若修改 chunk 正文、数量、ID 或上述 checksum，必须重新进行医学复核。
