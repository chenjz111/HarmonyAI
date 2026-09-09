# Sprint5 Final Closeout · Medical（Issue #108）— PR #114 交付说明

> 作者：nob（肖宇翔，Medical Knowledge Engineer）
> 日期：2026-09-06
> Issue：#108 [S5-FINAL][Medical] Relevance, RAG Corpus & Medical Acceptance（Supersedes #97，Related PR #102）
> Freeze Baseline：`83fe2f42069e126dbbfdccc252266964a58ce895`（V3.1_FREEZE_BASELINE）
> PR：#114（feat/s5-final-medical-108 → integration/sprint4-real-input）——更新中，未合并

---

## 1. 交付文件（5 资产/文档 + 1 测试文件）

| 文件 | 对应 #108 | canonical sha256 |
| --- | --- | --- |
| `knowledge/v3/document-relevance-rules-v3.1.json` | §1 Document Relevance 终审 | `3445dedc…22`（R3 冻结分流对齐） |
| `knowledge/v3/usergoal-vocabulary-v3.1.json` | §2 问卷 3.0.1 保护（UserGoal） | `02813bdf…9f`（R2 更新） |
| `knowledge/v3/five-tone-safe-expression-rules-v3.1.json` | §5 Five-Tone Explainability | `c752d619…23f` |
| `knowledge/v3/rag-corpus-manifest-v3.1.json` | §3 RAG Medical Corpus + §4 Boundary | `5096bf85…fb85`（R2 更新） |
| `docs/sprint5/medical-issue108-closeout-20260906.md` | 本说明 | — |
| `tests/knowledge/test_s5final_medical_assets.py` | #108 §6 Medical Tests（10 项） | — |

## 2. 状态声明（按 PR #114 评审意见修正）

### RAG 完成状态（rag-corpus-manifest-v3.1）
| 项 | 状态 |
| --- | --- |
| 医学来源审核 | **已完成**（13 条解释类来源，reviewer/hash/reference 齐备） |
| 实际语料 / chunk | **未完成**——本 manifest 仅为医学来源登记，**无正文/chunk 伪造**；待 AI 侧 #109 接入 |
| Embedding / Ingestion | **待 #109** |
| Production RAG | **NOT_APPROVED_PENDING** |

> ⚠️ **边界说明**：rag-corpus-manifest-v3.1 仅为**医学来源登记与审核**，不是可检索的 corpus/chunk，不得视为 Production RAG。
> **交付给 Agent2 的成果**：医学侧=13 条来源全部 `MEDICALLY_REVIEWED`（经典 10 + 统编教材 3，见 manifest `medically_reviewed_sources`）+ 来源登记（source_id/title/use/grade/source_reference/content_hash）；
> 实际内容（正文提取/清洗/分块/embedding）**待 AI 侧 #109 整理后形成可检索 chunks** 再接入 Agent2（manifest `pending_for_agent2_corpus_build`）。

### 知识资产注册状态
- 4 份资产 `registry_status = NOT_REGISTERED_OWNER_PENDING`，**未写入任何 knowledge manifest**；
- 本 PR 仅交付医学资产；**Owner 审核通过后统一注册**；
- **注册前生产代码不得读取这些资产**。

### Real / Mock
- Real Mode Status = **`MEDICAL_ASSET_ONLY / NOT_PRODUCTION_REACHABLE`**（本批为规则与登记资产，无生产可达性）

## 3. 自动化测试（#108 §6 / 评审意见第 1 项）

文件：`tests/knowledge/test_s5final_medical_assets.py`（10 项）

覆盖：① 4 资产 JSON 可解析 ② canonical checksum 自洽 ③ Relevance verdicts/reason_codes 合法（reason 非空）④ 仅 VALID 进下游（downstream_gate 断言），且 INSUFFICIENT 按冻结合同进入统一异常流程 ⑤ UserGoal code 与 questionnaire-v3.0.1 完全一致 ⑥ UserGoal 非 Medical/Fact/Organ Evidence ⑦ RAG 仅解释类知识 + 确定性规则不入向量 + 无伪造 chunk ⑧ 五音表达无诊断/治疗承诺/夸大措辞 ⑨ questionnaire-v3.0.1 零修改（checksum = 冻结 `69a01d07…`）

命令：`python -m pytest tests/knowledge/test_s5final_medical_assets.py -q`
结果：由本次提交重新执行并以 PR #114 workflow `test` 复核。

## 4. #108 验收对照

| #108 项 | 状态 |
| --- | --- |
| 1 Document Relevance 终审 | ✅ 定稿 + 自动化断言 |
| 2 正式问卷 3.0.1 保护 | ✅ 零修改（测试断言冻结 checksum） |
| 3 RAG Medical Corpus | ✅ 医学来源登记（正文/chunk 明确未完成） |
| 4 Corpus Boundary | ✅ 不入向量清单 + 测试断言 |
| 5 Five-Tone Explainability | ✅ 定稿 + 措辞测试 |
| 6 Medical Tests | ✅ 9 项已提交并通过本地执行 |

## 5. Remaining Blockers（未冻结项，不自行决定）
- 「近期」时间范围（OD-DR-01，数值口径未冻结）
- Relevance 置信判定方式（OD-DR-04）
- secondary tone 医学阈值（冻结 §10 未冻结项）
- 五音免责声明最终文案（OD-FT-01，待老师/产品）
- 状态倾向措辞模板（OD-FT-02）

另：Production RAG 放行与资产注册均待 Owner；Embedding/Chunk 待 #109。

## 6. 修订记录
- R1 自查修订（VALID reason/措辞/label_ref/status_note/source_reference）；
- R2（按 PR #114 评审意见）：新增结构化字段（downstream_gate / evidence_role / completion_status）+ 修正 RAG 完成状态表述 + 交付报告更新。
- R3：按 V3.1 冻结合同修正 INSUFFICIENT 分流与权威文档引用，并新增对应回归断言。
