# 多资料 / Relevance 交接说明（Issue #99 · 蔡子鑫 → 钟睿宸）

> 本说明描述 `feat/s5-v3.1-multidoc-agent3`（PR #104）中 **DocumentSet / Relevance 的持久化 + API 层**，
> 供钟睿宸把「多资料 + Relevance」接入 Understanding / Agent1 / Agent2 下游时使用。
> 本轮 PR 验收范围仅到持久化 + API 层，不包含 Understanding 下游接线。

---

## 1. 表结构与迁移

迁移编号：`0005_v3_multidoc`、`0006_v3_relevance`、`0007_v3_doc_fk`、`0008_v3_prescription_mode`（`0004` 留空）。

### `document_sets`（资料集）
| 列 | 类型 | 说明 |
|---|---|---|
| `document_set_id` | String PK | 资料集 ID，`dset_<hex>` |
| `internal_user_pk` | FK → users.id | 归属用户 |
| `session_row_id` | FK → sessions.id | 归属会话 |
| `revision` | int ≥1 | 资料集版本，每次替换/新增/删除 +1 |
| `status` | enum | `active` / `superseded` / `discarded` |
| `created_at` / `updated_at` | datetime | |

唯一约束：`(session_row_id, document_set_id)`。

### `document_set_items`（资料集条目，1～3 张）
| 列 | 类型 | 说明 |
|---|---|---|
| `document_set_item_id` | String PK | `dsetitem_<hex>` |
| `document_set_id` | FK → document_sets | 归属资料集 |
| `document_id` | FK → documents.document_id | 来源资料 |
| `position` | int 1..3 | 用户上传顺序 |

唯一约束：`(document_set_id, position)`、`(document_set_id, document_id)`；`position` CHECK 1..3。

### `document_relevances`（相关性结果，1 条 / 每来源资料）
| 列 | 类型 | 说明 |
|---|---|---|
| `document_relevance_id` | String PK | `rel_<hex>` |
| `document_set_id` | FK → document_sets | 归属资料集 |
| `document_set_revision` | int | 评估时绑定的资料集 revision |
| `document_id` | String | 来源资料 |
| `outcome` | enum | `VALID` / `INVALID` / `IRRELEVANT` / `INSUFFICIENT` |
| `reason_codes_json` | JSON list | 内部审计原因码 |
| `evaluator` / `evaluator_version` | String nullable | 内部审计（Provider/规则版本） |
| `evaluated_at` | datetime | 评估时间 |

唯一约束：`(document_set_id, document_id)`；`outcome` CHECK 四枚举。

---

## 2. Session 活动引用字段

`Session`（`backend/app/models/session.py`）新增/相关：

- `active_document_set_id`：指向**当前活动资料集**（V3.1 多资料）。
- `active_document_id`：**V3.0 兼容**单资料引用（保留，多资料下取第一张）。
- `input_revision`：活动输入版本，任何来源变更都 CAS +1。

**活动资料判定**：`session.active_document_set_id` 非空，且对应 `document_sets.status == "active"`，其 `document_set_items`（按 `position` 升序）即当前权威资料集。

---

## 3. API 面（已实现）

### 资料（Document）
| 方法/路径 | 说明 |
|---|---|
| `POST /api/v3/documents` | 注册资料元数据（`session_id`/`original_filename`/`file_type`/`file_size_bytes`）；`storage_path`/`status`/OCR 字段由服务端控制，上传+OCR 走现有链路，不在此伪造 |
| `GET /api/v3/sessions/{session_id}/documents` | 列出会话资料（归属校验） |
| `DELETE /api/v3/documents/{document_id}` | 删除；**若资料仍在活动资料集内 → 409 `DOCUMENT_IN_ACTIVE_SET`** |

### 资料集（DocumentSet）
| 方法/路径 | 说明 |
|---|---|
| `POST /api/v3/sessions/{session_id}/document-sets` | 替换/创建资料集（1～3 张，`document_ids` 有序）；CAS `input_revision`，新增 revision，旧 active 置 `superseded`，清空旧 `active_understanding_id/rev` |
| `GET /api/v3/sessions/{session_id}/document-sets/active` | 读取当前活动资料集 |

请求体：`{"session_id", "expected_input_revision", "document_ids": [1..3]}`；Idempotency-Key 必填。

### Relevance
| 方法/路径 | 说明 |
|---|---|
| `GET /api/v3/document-sets/{document_set_id}/relevance` | **前端只读** outcome |
| （内部 service `record_relevance`） | **仅供 Understanding 内部**写入，非 HTTP 端点 |

`record_relevance` 校验：资料集 `active`、`document_set_revision` 与当前 revision 一致、结果**完整覆盖**资料集全部条目、reason_code 白名单。

---

## 4. 替换 / 丢弃行为（活动状态清理）

- **`replace_document_set`**：旧 active 集 → `superseded`；`session.active_document_set_id` / `active_document_id` 更新为新集；`active_understanding_id/rev` 清空（旧摘要失效）；`input_revision +1` 并写 `session_input_revisions` 快照（action=`replace_document`）。
- **`discard_document`**（input-transitions）：旧 active 集 → `discarded`；`active_document_set_id` / `active_document_id` 清空；`input_revision +1`。之后旧集不再返回 active，其资料可被删除。
- **`delete_document`**：若资料在当前活动集 → 409，避免活动集留失效引用。

---

## 5. 测试示例（`tests/api/v3/`）

- `test_document_set.py`：`test_replace_document_set_orders_and_revisions`（顺序 + revision）、`test_delete_document_in_active_set_is_rejected`、`test_discard_document_clears_active_set_and_allows_delete`
- `test_document_relevance.py`：`test_record_and_read_relevance`、`test_relevance_rejects_partial_coverage`
- `test_document.py`：归属/跨用户隔离

---

## 6. 尚未接入下游（钟睿宸负责，不在本 PR 范围）

- Understanding 仍按单个 `active_document_id` 校验，**尚未**读取 `active_document_set_id` 的 1～3 份资料集。
- Relevance 结果**尚未**被 Understanding 消费：`INVALID` / `IRRELEVANT` 的来源资料尚未被排除出摘要、Agent1、Agent2。
- `INSUFFICIENT` 保持待定语义，既不视为通过、也不丢弃，最终用户分流待 Owner/老师确认。
- 交接后需接入点：
  1. Understanding 读取 `session.active_document_set_id` → `document_sets`（status=`active`）→ `document_set_items`（按 position 排序）作为权威多资料输入。
  2. 读取 `GET /api/v3/document-sets/{id}/relevance` 的 `outcome`，排除 `INVALID`/`IRRELEVANT` 来源；`INSUFFICIENT` 单独分流。
  3. 确认排除后，被排除资料不进入 CaseSummary、Agent1 Assessment、Agent2 Diagnosis。
