# 医学侧核对 · RAG Query 命名来源与合成验收组合（2026-09-11）

> 作者：nob（肖宇翔，Medical Knowledge Engineer）
> 任务来源：Owner review 指派（支援钟睿宸 AI 侧修复「英文内部 code 不能命中中文语料」的医学语义来源问题）
> 状态：医学侧核对完成（只读核对 + 验收组合建议；未修改任何资产）

## 0. 范围与依据

| 依据文件 | 版本/状态 | content_checksum（前 16 位） |
| --- | --- | --- |
| knowledge/v3/claim-dictionary-v3.0.json | approved, medical_v3.0 | 9a20931048e775fb |
| knowledge/v3/organ-mapping-v3.0.json | approved, organ_mapping_v3.0 | 771ca8d799a2df6f |
| knowledge/v3/five-tone-mapping-v3.0.json | approved | 8f6bd8b91a598920 |
| knowledge/v3/rag-corpus-chunks-v3.1-candidate.json | PR #118 复核版（13 chunks） | 07d7e064dae85334 |

**约束遵守声明**：本文档仅做只读核对与验收组合定义；未新增医学描述，未修改问卷、语料正文或阈值。

---

## 1. claim-dictionary-v3.0.json：code ↔ display_name 核对（32/32）

核对结论：**32 条 claim 的英文 code 与中文 display_name 一一对应、无冲突、无遗漏，review_status=approved，可直接作为 RAG query 的中文命名来源。**

| # | claim_code | display_name | category | 语义正确性 |
| --- | --- | --- | --- | --- |
| 1 | anger_tendency | 烦躁易怒倾向 | emotional_state | ✓（怒→肝志） |
| 2 | agitation_tendency | 兴奋激动倾向 | emotional_state | ✓（喜→心志） |
| 3 | overthinking_tendency | 思虑过度倾向 | emotional_state | ✓（思→脾志） |
| 4 | sadness_tendency | 低落悲伤倾向 | emotional_state | ✓（悲→肺志） |
| 5 | fear_tendency | 紧张恐惧倾向 | emotional_state | ✓（恐→肾志） |
| 6 | flank_discomfort | 胁肋胀闷不适 | physical_signal | ✓（肝经循行部） |
| 7 | tendon_stiffness | 筋脉拘紧 | physical_signal | ✓（肝主筋） |
| 8 | muscle_cramp | 肢体抽筋 | physical_signal | ✓（肝主筋膜） |
| 9 | eye_discomfort | 目干眼涩 | physical_signal | ✓（肝开窍于目） |
| 10 | palpitation_at_rest | 静息心悸 | physical_signal | ✓（心系） |
| 11 | palpitation_after_activity | 活动后心悸 | physical_signal | ✓（心系） |
| 12 | palpitation_night | 夜间心悸 | physical_signal | ✓（心系/不寐相关） |
| 13 | tongue_tip_discomfort | 舌尖不适 | physical_signal | ✓（心开窍于舌） |
| 14 | poor_appetite | 食欲不振 | physical_signal | ✓（脾系） |
| 15 | postmeal_bloating | 餐后腹胀 | physical_signal | ✓（脾系） |
| 16 | loose_stool | 大便溏稀 | physical_signal | ✓（脾系） |
| 17 | postmeal_heaviness | 餐后困重 | physical_signal | ✓（脾系湿困） |
| 18 | throat_cough | 咽喉不适咳嗽 | physical_signal | ✓（肺系） |
| 19 | exertional_breathlessness | 活动后气短 | physical_signal | ✓（肺系） |
| 20 | nasal_discomfort | 鼻塞不适 | physical_signal | ✓（肺开窍于鼻） |
| 21 | voice_change | 声音嘶哑 | physical_signal | ✓（肺系，声嘶属肺） |
| 22 | lower_back_knee_weakness | 腰膝酸软 | physical_signal | ✓（肾系，腰为肾之府） |
| 23 | tinnitus | 耳鸣 | physical_signal | ✓（肾开窍于耳） |
| 24 | nocturia | 夜尿频多 | physical_signal | ✓（肾系） |
| 25 | sleep_disturbance | 睡眠障碍 | physical_signal | ✓（不寐责心脾肾） |
| 26 | unrefreshing_sleep | 睡眠不解乏 | physical_signal | ✓（睡眠质量域） |
| 27 | low_energy | 精力不足 | physical_signal | ✓（气血精力域） |
| 28 | worry_control | 担忧控制困难 | cognitive_state | ✓ |
| 29 | concentration_decline | 注意力下降 | cognitive_state | ✓ |
| 30 | social_withdrawal | 社交退缩 | behavioral_state | ✓ |
| 31 | daily_impact | 日常影响程度 | functional_state | ✓ |
| 32 | emotional_recovery_slowness | 情绪恢复缓慢 | emotional_state | ✓ |

---

## 2. 五脏 code ↔ 正式中文展示名核对

核对结论：**对应关系明确且一致（liver=肝/木、heart=心/火、spleen=脾/土、lung=肺/金、kidney=肾/水），但 organ-mapping-v3.0.json 中没有「organ code → 中文展示名」的机器可读正式字段**——中文脏名只出现在 source/note 的自然语言中（可人工推导，不可直接程序读取）。

| organ_code | 中文展示名 | 五行 | 推导依据（approved 资产内） |
| --- | --- | --- | --- |
| liver | 肝 | wood | organ-mapping single_mappings「怒伤肝」+ five-tone-mapping note「角调……应肝之疏泄」 |
| heart | 心 | fire | single_mappings「喜伤心；心主神明」+ five-tone-mapping note「应心之阳热」 |
| spleen | 脾 | earth | single_mappings「思伤脾」+ five-tone-mapping note「应脾之运化」 |
| lung | 肺 | metal | single_mappings「悲/肺」+ five-tone-mapping note「应肺之宣肃」 |
| kidney | 肾 | water | single_mappings「恐/肾」+ five-tone-mapping note「应肾之藏精」 |

**给 AI 侧的实现建议（不修改资产文件）**：query 构造时使用受控中文常量 `{liver:"肝", heart:"心", spleen:"脾", lung:"肺", kidney:"肾"}`（与上表逐一核对一致）；如需机器可读字段正式化，属资产变更，走 Owner 流程，不在本次范围。

---

## 3. Approved 展示名用于 RAG Embedding Query 的确认

**确认：可以。** 理由：
1. **语言一致**：32 条 display_name 与五脏中文展示名全部为中文，与 13 chunk 语料（中文教材口径）同语言；
2. **口径一致**：display_name 均为教材/问卷正式表述（approved），与语料同源（knowledge-manifest knowledge_sources）；
3. **无歧义词**：display_name 无口语、无缩写、无英文混排。

**但需区分预期命中等级**（不是所有 claim 都有语料支持——这是语料覆盖面的事实，不是缺陷）：

| 等级 | 条数 | claim |
| --- | --- | --- |
| **直接支持**（display_name 核心词直接出现在 chunk 文本中，query 应命中） | 14 | anger_tendency(src_01)、overthinking_tendency(src_01/11)、fear_tendency(src_01)、tendon_stiffness(src_03)、muscle_cramp(src_03)、eye_discomfort(src_01/02)、postmeal_bloating(src_11)、loose_stool(src_11)、exertional_breathlessness(src_08/12)、nasal_discomfort(src_06)、voice_change(src_11)、lower_back_knee_weakness(src_05/11)、tinnitus(src_06/13)、sleep_disturbance(src_11) |
| **边界支持**（脏系背景可命中，但 display_name 本词不在语料） | 9 | agitation_tendency、sadness_tendency、palpitation_at_rest/after_activity/night、tongue_tip_discomfort、poor_appetite、throat_cough、concentration_decline(「健忘」为近义) |
| **无语料支持**（13 chunk 未覆盖该域，正确行为是返回空而非强答） | 9 | flank_discomfort、postmeal_heaviness、nocturia、unrefreshing_sleep、low_energy、worry_control、social_withdrawal、daily_impact、emotional_recovery_slowness |

**Query 构造规则建议**：query 文本 = display_name（中文）拼接 + 脏中文展示名（如适用）；**英文 claim_code / organ_code 一律不进入 query 文本**（它们只作结构化过滤与结果对账用）。

---

## 4. 合成验收组合（生产风格）

> 以下组合基于 approved 资产的确定性对应，供 AI 侧做检索回归验收。chunk_id 均为 PR #118 语料的正式 chunk_id。
> 「应命中」= 相关性排序应在前且过阈值；「边界允许」= 允许出现在结果中但不要求；「应返回空」= 13 chunk 全部不得过阈值。

### 组合 A（正例 · 肝系组合，应命中）
- **输入**：claims=[`anger_tendency`(烦躁易怒倾向), `eye_discomfort`(目干眼涩)]，organ=`liver`(肝)
- **示例 query 文本**：「烦躁易怒 目干眼涩 肝」
- **应命中**：`v31_src_01_scope_001`（五志五脏对应：怒肝/肝目）、`v31_src_02_scope_001`（肝开窍于目）
- **边界允许**：`v31_src_12_scope_001`（情志调畅赖肝）

### 组合 B（正例 · 脾系组合，应命中）
- **输入**：claims=[`postmeal_bloating`(餐后腹胀), `loose_stool`(大便溏稀)]，organ=`spleen`(脾)
- **示例 query 文本**：「餐后腹胀 大便溏稀 脾」
- **应命中**：`v31_src_11_scope_001`（食后腹胀/便溏属脾虚）
- **边界允许**：`v31_src_04_scope_001`（脾胃者仓廪之官）、`v31_src_09_scope_001`（脾为生痰之源）

### 组合 C（正例 · 肾系组合，应命中）
- **输入**：claims=[`lower_back_knee_weakness`(腰膝酸软), `tinnitus`(耳鸣)]，organ=`kidney`(肾)
- **示例 query 文本**：「腰膝酸软 耳鸣 肾」
- **应命中**：`v31_src_05_scope_001`（腰者肾之府）、`v31_src_11_scope_001`（腰膝酸软属肾虚）、`v31_src_13_scope_001`（慢性耳鸣多责肾虚）
- **边界允许**：`v31_src_06_scope_001`（肾气通于耳）

### 组合 D（空例 · 语料未覆盖域，应返回空）
- **输入**：claims=[`social_withdrawal`(社交退缩), `daily_impact`(日常影响程度)]（behavioral/functional 域）
- **示例 query 文本**：「社交退缩 日常影响程度」
- **预期**：13 chunk 零命中（语料不含行为/功能状态内容）。正确行为 = 返回空结果集，**不得**强行召回低相关 chunk 充数。

### 组合 E（空例 · 英文 code 直查 + 域外词，应返回空）
- **输入 1**：query 文本直接用英文内部 code：「anger_tendency liver」
- **输入 2**：query 文本用非医学域词：「运动健身计划」
- **预期**：两者均零命中。其中输入 1 是本修复的**反向验收锚点**：修复前英文 code 命中不了中文语料（缺陷），修复后 query 改用中文 display_name（组合 A 应命中）；若实现仍把英文 code 拼进 query 文本，组合 A 应转为失败——**组合 A + E 合用可验证 query 构造是否真正切换到了中文命名来源**。

---

## 5. 变更与边界声明

- 本核对**未修改** claim-dictionary / organ-mapping / 语料 / 阈值 / 问卷中的任何字节；
- 未新增任何医学描述性结论；组合 A–E 的「应命中/应空」判定全部来自 approved 资产已有内容与五志五脏、开窍、脏腑隶属等教材级对应关系；
- 权重条数值、embedding 阈值不在医学侧职责内，本文件不给出数值建议（阈值由 AI 侧基于 gold 集分布提出、Owner 批准）。
