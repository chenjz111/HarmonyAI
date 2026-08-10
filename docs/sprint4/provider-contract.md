# HarmonyAI Provider Contract — Sprint 4

> **Version**: 1.0
> **Sprint**: Sprint 4
> **Applies to**: QwenCompatibleProvider / all LLM providers / OCR provider
> **Status**: FROZEN — S4-01 Contract Tests 与全量回归通过
> **Owner**: 陈家智

---

## 一、设计原则

1. **Fail explicitly, never silently** — Provider 失败必须返回明确的状态码和原因，不能静默丢弃
2. **Every call is logged** — 每次 LLM 调用记录到 `ai_call_log`，不含用户全文
3. **Degradation is a feature** — 降级不是 Bug，是设计的正常路径
4. **Health check is public** — Provider 状态可查询，不含 Secret
5. **Mock for testing** — 必须提供 Mock Provider 用于评估和测试

---

## 二、LLM Provider 接口

### 2.1 QwenCompatibleProvider (Sprint 3 已有，Sprint 4 增强)

**文件**: `backend/ai_engine/providers.py`

```python
class QwenCompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 20.0,
        max_retries: int = 2,
        transport: Callable | None = None,
    ) -> None: ...

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        """同步返回结构化 JSON。失败抛出 LLMProviderError。"""
        ...

    async def acomplete_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, object]:
        """异步返回与 complete_json 相同的结构化 JSON。"""
        ...
```

### 2.2 Sprint 4 新增能力

| 能力 | Sprint 3 | Sprint 4 |
|---|---|---|
| 调用方式 | 同步 | **异步 + 同步双模式** |
| 重试 | 无 | **最多 2 次 (429/5xx)** |
| 超时分类 | 无 | **connect_timeout / read_timeout 分别设置** |
| JSON 修复 | 基础 | **markdown 包裹修复 + 截断修复 + 重试** |
| Token 统计 | 无 | **input_tokens / output_tokens 记录** |
| 延迟记录 | 无 | **latency_ms 记录到 ai_call_log** |
| Prompt 版本 | 无 | **prompt_version 字段** |
| 错误码 | 通用 Exception | **标准化 ErrorCode 枚举** |
| Mock Provider | 无 | **MockProvider 用于测试和评估** |

同步 `complete_json()` 与异步 `acomplete_json()` 必须：
- 返回相同的结构化结果 Schema；
- 使用同一组 `ProviderErrorCode`；
- 使用相同的重试次数、退避和不可重试条件；
- 使用相同的 JSON 修复与 Schema validation；
- 仅执行模型调用方式不同，不得产生行为差异。

### 2.3 错误码标准化

```python
class ProviderErrorCode(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"           # 环境变量未配
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"   # TCP 连接超时
    READ_TIMEOUT = "READ_TIMEOUT"               # 响应超时
    RATE_LIMITED = "RATE_LIMITED"               # 429
    SERVER_ERROR = "SERVER_ERROR"               # 5xx
    INVALID_RESPONSE = "INVALID_RESPONSE"       # 非 200 且非以上
    INVALID_JSON = "INVALID_JSON"               # 响应体非 JSON
    JSON_REPAIR_FAILED = "JSON_REPAIR_FAILED"   # JSON 修复后仍无效
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"       # JSON 结构不符合预期
    EMPTY_RESPONSE = "EMPTY_RESPONSE"           # 空响应
```

### 2.4 重试策略

```
1st attempt → 失败
  ├── 429 (Rate Limited) → wait 2s → retry
  ├── 5xx (Server Error) → wait 1s → retry
  ├── Connection/Read Timeout → retry immediately
  └── 4xx (except 429) → NO retry, fail immediately

2nd attempt → 失败
  ├── 429 → wait 4s → retry (last)
  └── others → fail

3rd attempt → 失败
  └── return LLMProviderError with reason_code
```

### 2.5 调用日志 (ai_call_log)

每条 LLM 调用记录以下字段到数据库：

| 字段 | 类型 | 说明 |
|---|---|---|
| request_id | string | 全局唯一 |
| session_id | string | 关联会话 |
| agent_id | string | assessment_agent / diagnosis_agent |
| provider | string | "qwen" |
| model | string | "qwen2.5-7b-instruct" |
| prompt_version | string | "assessment_v2.1" |
| status | string | success / degraded / failed |
| error_code | string\|null | 失败时的错误码 |
| latency_ms | int | 端到端延迟 |
| input_tokens | int\|null | 输入 token 数（如果 API 返回） |
| output_tokens | int\|null | 输出 token 数（如果 API 返回） |
| retry_count | int | 实际重试次数 |
| created_at | datetime | 调用时间 |

**Red line**: `ai_call_log` **绝对不能** 包含用户原文 (system_prompt / user_prompt 全文)。只记录元数据。

---

## 三、Provider 健康检查

### 3.1 接口

```
GET /api/v2/providers/health
```

### 3.2 响应

```json
{
  "success": true,
  "data": {
    "qwen": {
      "configured": true,
      "reachable": true,
      "model": "qwen2.5-7b-instruct",
      "latency_ms": 234,
      "last_checked": "2026-08-06T10:00:00Z"
    },
    "ocr": {
      "engine": "paddleocr",
      "version": "2.8.1",
      "available": true,
      "last_checked": "2026-08-06T10:00:00Z"
    },
    "chroma": {
      "available": true,
      "collection_count": 1,
      "chunk_count": 57,
      "last_checked": "2026-08-06T10:00:00Z"
    },
    "database": {
      "type": "sqlite",
      "reachable": true,
      "last_checked": "2026-08-06T10:00:00Z"
    }
  },
  "meta": {"request_id": "req_uuid"}
}
```

### 3.3 安全要求

- **不得** 返回 `api_key` 或任何 Secret
- **不得** 返回数据库连接字符串
- **不得** 返回用户数据统计
- 仅返回配置状态 + 连通状态 + 延迟

---

## 四、OCR Provider 接口

### 4.1 OCRProvider (Sprint 4 重写)

**文件**: `backend/app/core/ocr.py`

```python
class OCRProvider:
    def __init__(self, *, engine: str = "paddleocr", timeout: float = 30.0) -> None: ...

    def process(self, storage_path: str, file_type: str) -> OCRResult:
        """执行真实 OCR。失败抛出 OCRError。"""
        ...

@dataclass
class OCRResult:
    text: str                        # 识别文本
    confidence: str                  # "high" | "medium" | "low"
    provider: str                    # "paddleocr"
    engine_version: str              # "2.8.1"
    page_results: list[PageResult]   # 分页结果
    average_confidence: float        # 0.0 - 1.0
    processing_time_ms: int

@dataclass
class PageResult:
    page_number: int
    text: str
    confidence: float                # 该页平均置信度
    blocks: list[BlockResult]

@dataclass
class BlockResult:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h
```

### 4.2 OCR 错误处理

```python
class OCRErrorCode(str, Enum):
    FILE_TOO_LARGE = "FILE_TOO_LARGE"           # > 10MB
    PDF_PAGE_LIMIT_EXCEEDED = "PDF_PAGE_LIMIT_EXCEEDED"  # > 3 pages
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"   # 非 JPG/PNG/PDF
    ENCRYPTED_PDF = "ENCRYPTED_PDF"             # 加密 PDF
    OCR_ENGINE_UNAVAILABLE = "OCR_ENGINE_UNAVAILABLE"  # PaddleOCR 未安装
    OCR_TIMEOUT = "OCR_TIMEOUT"                 # 处理超时
    OCR_FAILED = "OCR_FAILED"                   # 识别失败
```

### 4.3 OCR 失败时

- **不返回假成功文本**（删除 Sprint 3 的 `"[OCR Stub] 图片文本识别成功。"`）
- 返回 `{"ocr_status": "failed", "error_code": "OCR_FAILED", "user_message": "文字识别失败，请手动输入或跳过"}`
- 用户可以选择手动输入文本或跳过

---

## 五、Mock Provider

### 5.1 用途

- 单元测试 (不需要真实 Qwen)
- 评估脚本 (确定性输出)
- 前端开发 (不需要后端)

### 5.2 接口

```python
class MockProvider:
    def __init__(self, *, responses: dict[str, dict] | None = None) -> None:
        """responses: key=prompt_hash → value=预定义响应"""
        ...

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        """返回预定义响应。未匹配时返回默认响应。"""
        ...

    @staticmethod
    def from_jsonl(path: str) -> MockProvider:
        """从 JSONL 文件加载响应集。"""
        ...
```

---

## 六、Prompt 版本管理

### 6.1 目录结构

```
prompt/
├── assessment/
│   ├── v2.0/                          ← Sprint 3 (保留)
│   │   └── system.txt
│   └── v2.1/                          ← Sprint 4
│       ├── system.txt                 ← system prompt
│       ├── user_template.txt          ← user prompt 模板
│       └── CHANGELOG.md               ← 变更记录
├── diagnosis/
│   ├── v2.0/
│   └── v2.1/
│       ├── system.txt
│       ├── user_template.txt
│       └── CHANGELOG.md
└── README.md                          ← Prompt 版本对照表
```

### 6.2 CHANGELOG 格式

```markdown
# Assessment Prompt Changelog

## v2.1 (2026-08-06)
- 新增: user_goal / negated_facts / missing_information 字段
- 新增: evidence_quotes 要求 (每条结论附带原文)
- 约束: 不得补造用户未提及的信息
- 约束: prohibited_medical_fields 增加 "证型" "syndrome"

## v2.0 (2026-07-28)
- 初始版本
```

---

## 七、配置方式

### 7.1 环境变量

```bash
# .env
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=sk-xxx
QWEN_MODEL=qwen2.5-7b-instruct
QWEN_TIMEOUT=20
QWEN_MAX_RETRIES=2
```

### 7.2 配置验证

Provider 初始化时验证：
- `base_url` 非空且以 `https://` 开头
- `api_key` 非空
- `model` 非空
- `timeout` > 0 且 ≤ 60
- `max_retries` 0-3

验证失败 → `ProviderErrorCode.NOT_CONFIGURED`

---

## 八、日志规范

### 8.1 普通日志红线

普通日志禁止记录任何用户原文，也禁止记录截断后的用户原文。禁止字段包括：

- `narrative_text`
- `document_text`
- `ocr_text`
- `questionnaire_answer_text`
- `system_prompt`
- `user_prompt`

普通日志只允许记录：

- `request_id`
- `session_id`
- `agent_id`
- `source_type`
- `text_length`
- `provider`
- `model`
- `prompt_version`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `status`
- `error_code`
- `retry_count`

不得通过“保留前 100 字符”、截断、摘要或其他方式把用户文本写入普通日志，也不新增用户文本 hash 机制。Secret 和数据库连接信息同样不得进入日志。机器可校验的允许/禁止字段位于 `tests/contract/fixtures/provider.contract.json`。
---

## 九、交付物清单

| 文件 | 负责人 | Sprint 3 状态 | Sprint 4 目标 |
|---|---|---|---|
| `backend/ai_engine/providers.py` | 钟睿宸 | 已有 (v1.0) | 增强 (v2.0) |
| `backend/app/core/ocr.py` | 蔡子鑫 | Stub | 重写 (PaddleOCR) |
| `backend/app/core/provider_health.py` | 蔡子鑫 | 无 | 新增 |
| `backend/app/routers/provider_router.py` | 蔡子鑫 | 无 | 新增 |
| `backend/app/models/ai_call_log.py` | 蔡子鑫 | 无 | 新增 |
| `prompt/assessment/v2.1/` | 钟睿宸 | 无 | 新增 |
| `prompt/diagnosis/v2.1/` | 钟睿宸 | 无 | 新增 |
| `migrations/` | 蔡子鑫 | — | ai_call_log 等 |

---

*陈家智起草，已完成 S4-01 Review。*
