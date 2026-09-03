# Sprint5 V3.1 Medical 交付说明 — Issue #97 第一批候选稿

> 作者：nob（肖宇翔，Medical Knowledge Engineer）
> 日期：2026-09-03
> 状态：**PROVISIONAL / CANDIDATE** —— 未冻结、未注册入 knowledge-manifest，不得作为生产判定依据
> 关联：#95（总追踪）、#96（Owner）、#97（本任务）、#98（AI/Agent1 消费方）、PR #101（V3.1 owner baseline 契约）

---

## 1. TL;DR

按 Issue #97 范围产出 **3 份医学候选资产 + 1 份交付说明**：

| 文件（仓库路径） | 内容 | canonical sha256 |
| --- | --- | --- |
| `knowledge/v3/document-relevance-rules-v3.1-candidate.json` | Document Relevance 医学规则（VALID/INVALID/IRRELEVANT/INSUFFICIENT + reason-code 白名单 + 判定决策表 + 硬性不变量） | `4506b335…9c69` |
| `knowledge/v3/usergoal-vocabulary-v3.1-candidate.json` | UserGoal 正式词表审核稿（7 code 非医学语义 + 证据边界 UG-01至06 + 消费契约） | `2fb05e5d…12e4` |
| `knowledge/v3/five-tone-safe-expression-rules-v3.1-candidate.json` | “五音调适解析”安全医学表达规则（FT-01至08 + 区块规则 + 免责声明候选文案） | `731edc13…6eb7` |
| `docs/sprint5/medical-v3.1-issue97-delivery-20260903.md` | 本交付说明 | — |

> 哈希口径：对文件内容 `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",",":"))` 后取 sha256（与既有 v3.0 资产 checksum 口径一致）。候选稿暂不在文件内嵌 content_checksum，待冻结注册时按 manifest 约定嵌入并三方对齐。

## 2. Issue #97 验收对照

| #97 要求 | 落点 | 状态 |
| --- | --- | --- |
| 制定 Document Relevance 医学规则 | document-relevance-rules §verdicts/decision_table | ✅ 候选稿 |
| 明确 VALID / INVALID / IRRELEVANT 医学边界 | 同上（含 INSUFFICIENT 的 PENDING_CONTRACT 处理） | ✅ 候选稿（INSUFFICIENT 分流待 #96 合同决策） |
| 审核 UserGoal 正式词表 | usergoal-vocabulary §approved_codes/audit_conclusion | ✅ 7 code 无异议 |
| 明确 UserGoal 不属于 Medical Evidence | usergoal-vocabulary §evidence_boundary_rules（UG-01至06）+ §audit_conclusion | ✅ 候选稿 |
| 制定“五音调适解析”安全医学表达规则 | five-tone-safe-expression-rules（FT-01至08 + section_rules + disclaimer） | ✅ 候选稿 |
| 继续维护现有 RAG 医学资产 | 见 §5；本批未改动任何既有 v3.0 资产 | ✅ 只读维护 |

## 3. 范围外确认（遵守 #97 边界）

- **未改动 Q1至Q10**：questionnaire-v3.0.json 与既有 manifest 零改动（Gate #4 checksum 证据仍待冻结时核验）。
- **未改前端**：未触碰任何 .vue / read-model / frontend 文件。
- **未写 Agent 代码**：本批全部为医学资产（JSON 规则 + 文档），不含实现。
- **未 merge**：个人 feature branch `feat/s5-v3.1-medical-relevance-rules`（commit `ddbd8610`）已建；经 Owner 评审许可后已开 **Draft PR #102**（仅作评审载体，明确 DO NOT MERGE），遵守 V3.1 PROVISIONAL 铁律——老师确认 + #96/#101 冻结前不合并到 integration。

## 4. 关键医学设计决策（候选，均可在审阅期推翻）

1. **Relevance 四值边界**：VALID（本人+可解读+时效相关+状态相关）→ 唯一可进摘要/证据；INVALID（非医疗文书/不可读/无法确认本人/损坏）与 IRRELEVANT（本人文书但与本次状态评估无关）→ 一律阻断，绝不进 Agent1/2 证据与 RAG（对齐 Cross-Interface Invariant #4）；INSUFFICIENT → **PENDING_CONTRACT**，禁止静默成功或丢弃。
2. **时效“近期”候选默认 6 个月**，或以资料内与本次主诉相关的复查时间为准（OD-DR-01，待确认）。
3. **UserGoal 三重隔离**：不是证据（UG-01）、不进 Agent1/2（UG-02）、不改 ToneProfile（UG-04）——最严的一条是 **custom_goal_text 自由文本严禁抽取 claim**（UG-05），防用户写“最近睡不好”回流成证据。
4. **表达安全**：在既有 manifest forbidden_expressions 基础上扩展确诊式/疗效承诺/脏腑结论式禁令（FT-01至03），并要求后端安全装配 + 前端只读（FT-07），免责声明给出候选文案（DIS-V3.1-01，待老师审阅）。
5. **不引入伪精度**：判定不设全局数值置信阈值，用 reason-code 白名单枚举（OD-DR-04）。

## 5. RAG 医学资产维护说明（#97 第 6 项）

- 既有已批准资产（knowledge/v3 下 questionnaire/claim-dictionary/organ-mapping/five-tone-mapping/knowledge-manifest v3.0）**本批零改动**，checksum 不变。
- production RAG Ingestion Manifest 仍为 `NOT_APPROVED_PENDING`（见 knowledge-manifest-v3.0 §rag_ingestion_status），第二批（embedding 选定后）继续等待，本批不提前放行。
- 本批 3 个候选资产为 **增量新文件**，语义与 v3.0 资产一致（同引用风格、同 canonical 口径），冻结后注册进新 knowledge-manifest（或 v3.0 manifest 增量版）再供 RAG/Agent2 使用。
- V2 文献仍为 pending_conversion，维持原状。

## 6. 开放决策（给 Owner/老师/产品）

| ID | 议题 | 候选默认 | 归属 |
| --- | --- | --- | --- |
| OD-DR-01 | “近期”时效阈值 | 6 个月 / 以相关复查时间为准 | 老师+Owner |
| OD-DR-02 | INSUFFICIENT 分流 | A 重试 / B 转问卷路径 / C 人工标注（不推荐） | Owner #96 |
| OD-DR-03 | reason_code 用户可见粒度 | 仅 public_text，完整码入审计 | 产品+Owner |
| OD-DR-04 | 判定置信阈值 | 不用数值阈值，用白名单 | nob 建议 |
| OD-UG-01 | UserGoal 中文 label 文案 | 见 usergoal-vocabulary | 产品+老师 |
| OD-UG-02 | secondary 是否须 ≠ primary | 沿用 V3.0（不同） | Owner #96 |
| OD-UG-03 | custom_goal_text 是否参与弱提示 | 仅可明确映射时 | AI+nob |
| OD-FT-01 | 免责声明最终文案 | DIS-V3.1-01 | 老师+产品 |
| OD-FT-02 | 倾向措辞模板库 | 后端装配器维护 | AI+nob |
| OD-FT-03 | 红旗场景 V3.1 呈现 | 不重接 Safety 流程 | Owner #96 |

## 7. 验证

- 3 个 JSON 均通过 `json.loads`（UTF-8，合法）。
- canonical sha256 见表 1（与既有资产同口径）。
- 本批未运行既有测试集（无代码改动，不影响 52 tests）。

## 8. 后续步骤（等指示，不主动推进）

1. nob/老师审阅候选稿 → 提出修订；
2. 老师确认 + Owner 完成 #96/#101 合同决策（尤其 OD-DR-02 INSUFFICIENT、OD-UG-02）；
3. 冻结后将 3 资产注册入 knowledge-manifest（checksum 三方对齐），并核验 Gate #4（Q1至Q10 不变）；
4. 与 #98（Agent1）对齐消费契约（ConfirmedUserState 只含 VALID+用户确认的摘要；UserGoal 不进入 Agent1/2）。

## 9. R1 修订记录（2026-09-03 晚，回应 PR #102 CHANGES_REQUESTED）

- **P0-01**：Relevance Gate 判定仅使用判定时点可得信息（OCR + 资料元数据 + 固定 V3.1 评估范围/已批准 Claim Dictionary）；删除对摘要确认环节与‘当前主诉’的依赖；归属无法仅凭资料确认一律归 INSUFFICIENT（新增 reason_code ri_ins_ownership_unclear；INVALID 仅保留明确非本人信号 ri_not_own_explicit）；新增硬性不变量 IV-6/IV-7，不引入独立资料确认页。
- **P0-02**：FT-08 移出 global_rules，转 safety_compatibility（FT-08-COMPAT，NOT_ACTIVE_IN_V3.1），激活需 Owner 重新批准。
- **P1-01**：删除 custom_goal_text ‘仅在选择 other 时启用’越权结论，改为 V3.1 Owner Baseline 口径（选填、≤200 字）；schema 表达保留技术开放项 OD-UG-04。
- **P1-02**：document-relevance 资产 purpose 改为‘医学侧候选规则稿（冻结并注册 manifest 后作为权威规则来源）’。
- **P2**：本说明同步为‘已创建 Draft PR #102，未 Merge’。
- 约束保持：PROVISIONAL / Draft；未注册 manifest；未改动正式 Q1至Q10；未转 Ready；未 Merge。
