# Sprint5 Final Closeout · Medical（Issue #108）— 第一批提交说明

> 作者：nob（肖宇翔，Medical Knowledge Engineer）
> 日期：2026-09-06
> Issue：#108 [S5-FINAL][Medical] Relevance, RAG Corpus & Medical Acceptance（Supersedes #97，Related PR #102）
> Freeze Baseline：`83fe2f42069e126dbbfdccc252266964a58ce895`（V3.1_FREEZE_BASELINE）
> 提交状态：**仅推送到个人分支 `feat/s5-final-medical-108`，未开 PR**（待 nob/Owner 过目后再决定 PR）

---

## 1. 本批文件（5，全部新增于 baseline 之上）

| 文件 | 对应 #108 章节 | canonical sha256 |
| --- | --- | --- |
| `knowledge/v3/document-relevance-rules-v3.1.json` | §1 Document Relevance 终审 | `0689aa50…ca5a` |
| `knowledge/v3/usergoal-vocabulary-v3.1.json` | §2 正式问卷 3.0.1 保护（UserGoal 语义） | `951b2cc5…d740` |
| `knowledge/v3/five-tone-safe-expression-rules-v3.1.json` | §5 Five-Tone Explainability | `561f9786…e058` |
| `knowledge/v3/rag-corpus-manifest-v3.1.json` | §3 RAG Medical Corpus + §4 Corpus Boundary | `d47f4500…e561` |
| `docs/sprint5/medical-issue108-closeout-20260906.md` | 本说明 | — |

## 2. #108 验收对照

| #108 项 | 本批动作 | 状态 |
| --- | --- | --- |
| 1 Document Relevance 终审 | 四值语义+reason 码表定稿；对齐冻结 §3：仅 VALID 三项 downstream=true，其余不进 Evidence/Agent2；INSUFFICIENT 路由已冻结关闭 OD-DR-02 | ✅ 提交（待终审） |
| 2 Formal Questionnaire 3.0.1 严格保护 | **未修改** questionnaire-v3.0.1.json；无 QUESTIONNAIRE_CONTRACT_DRIFT；本批资产只引用不覆盖 | ✅ 无漂移 |
| 3 RAG Medical Corpus | 语料来源注册 v1（13 条解释类知识源，各带 reviewer/version/content_hash/approval） | ✅ v1 提交 |
| 4 Corpus Boundary | manifest 内明确"不入向量"的确定性 Rule Assets 清单 | ✅ 已声明 |
| 5 Five-Tone Explainability | 表达规则定稿；新增 FT-09 只读模型边界（对齐冻结 §9） | ✅ 提交 |
| 6 Medical Tests | JSON 全量 parse + canonical checksum 通过；代码级 tests 待 PR 阶段补 | 🟡 待 PR |

## 3. 关键对齐点（均按 FROZEN 契约）

1. **Relevance**：`reason_code` 语义化非空 + `reason` 公开文案（对齐 flow_v31）；白名单 14 项由本资产供给。
2. **UserGoal**：label 权威 = `questionnaire-v3.0.1.json#user_goal.options[].label`（本资产不复写文案）；`primary_goal` 可空、`secondary_goal` 仅随 primary 且不同、custom-text 独立合法 ≤200 字、全空归 `null`；preference-only，非任何 Evidence。
3. **只读模型**：解释类字段必填非空，read model 之外字段一律禁止（FT-09）。

## 4. 与本批未涵盖 / 留待 Owner 的项（Remaining Medical Risks & Blockers）

- **Production RAG 放行**：corpus 医学复核完成但 `approval_status=MEDICAL_REVIEWED_PENDING_PRODUCTION`；embedding/chunk/ingestion 参数与正式 Ingestion Manifest 属 #109/Owner（manifest 3.0.1 rag_ingestion_status 仍 NOT_APPROVED_PENDING）——**未获 Owner 放行前不得进 Production RAG**。
- **副音阈值**：冻结 §10 明确 secondary-tone 医学阈值是版本化 Rule Asset（未冻结）——待 #104/Agent3 对齐后由医学侧补阈值资产。
- **注册**：4 份资产尚未注册入 knowledge-manifest（registry_status=NOT_REGISTERED_OWNER_PENDING），待 Owner 接受后注册（届时 checksum 三方对齐）。
- **代码级 Medical Tests**：relevance/knowledge/mapping/safety/corpus validation 测试需在代码仓库跑（CI），随 PR 提交。

## 5. 验证

- 4 份 JSON 均通过 `json.loads`（UTF-8）；content_checksum 为移除自身字段后的 canonical sha256（仓库口径），见 §1 表。
- 本批无代码改动，未触碰 questionnaire-v3.0.1 / 既有 v3.0 资产；基线契约文件零修改。

## 6. 下一步（等 nob/Owner 指示）

1. nob 复核本分支内容；
2. Owner 决定是否开 PR（#108 完成格式要求的 13 字段回复将在 PR/Issue 阶段补充）；
3. 医学测试与 CI 随 PR 阶段补齐。
