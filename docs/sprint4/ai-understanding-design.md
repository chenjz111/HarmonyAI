# Sprint 4 S4-04：AI Understanding 统一设计文稿

> **对应任务**：[GitHub #55](https://github.com/chenjz111/HarmonyAI/issues/55)
> **负责人**：钟睿宸（AI Engineering Lead）
> **目标分支**：`feat/s4-ai-understanding` → `integration/sprint4-real-input`
> **文档状态**：Draft，待团队 Review
> **编写日期**：2026-08-06

## 1. 目标与边界

### 1.1 目标

S4-04 为 Sprint 4 的真实输入流程提供一条可解释、可降级、可评估的 AI Understanding 链路：

```text
Qwen Provider
  → 自由文本/材料结构化提取
  → Questionnaire V2.0/V2.1/Quick State 确定性评分
  → Assessment 多源证据融合
  → 冲突、缺失与追问决策树
  → 用户确认后的 Diagnosis 辅助倾向
  → 评估集与指标验证
```

核心原则：

1. **每条主要结论都有证据**：证据必须能定位到问卷题目、文本句子、材料片段、追问回答或用户修正。
2. **不确定性显式化**：输入不足、来源冲突、Provider 失败时，返回 `degraded`、`needs_follow_up` 或 `abstained`，不伪装成完整成功。
3. **规则约束 LLM**：LLM 负责结构化提取和候选排序，不负责创造未授权的倾向、追问或医疗结论。
4. **安全优先**：安全筛查在 LLM 之前执行；安全阻断时不进入 Diagnosis、Prescription 或 Music。
5. **兼容 Sprint 2/3**：保留 V2.0 12 题和既有同步调用方式，V2.1 能增量接入现有工作流。

### 1.2 本任务包含

- Qwen Provider 工程化：异步调用、重试、超时分类、JSON 修复、Token/延迟统计、Mock Provider。
- `questionnaire_v2.py`：同时支持 Questionnaire V2.0（12 题）、V2.1（20 题）和 Quick State（6 题）。
- `narrative_schema.py`：自由文本/已确认材料的 13 类信息提取和 `evidence_quotes`。
- `assessment_v2.py`：EvidenceItem、Conflict、MissingInformation、Evidence Coverage、追问决策树、Revision。
- `diagnosis_v2.py`：`candidate_tendencies`、支持/反对证据、`abstained` 和安全/降级传播。
- `prompt/assessment/*`、`prompt/diagnosis/*`：版本化 Prompt 与结构约束。
- `evals/run_sprint4_eval.py`、`evals/metrics.py`：60 案例评估、指标计算和报告输出。

### 1.3 不包含

- 真实音乐生成、音乐曲库扩充、五音映射重做。
- 用户注册、支付、七日方案和可穿戴设备。
- 前端页面、真实 OCR 引擎、数据库迁移和 Provider Health API；这些由 S4-03/S4-05 负责，S4-04 只提供稳定的 AI 输入输出契约。
- 任何确诊、患病判断或治疗建议。

## 2. 现状与问题

当前 Sprint 3 已有增量 V2 能力，但仍存在以下边界：

| 现状 | S4-04 问题 | 设计处理 |
|---|---|---|
| `providers.py` 以同步 `complete_json` 为主 | 没有统一重试、超时、错误分类和 Token 统计 | 新增 Provider 请求/响应模型与异步实现，保留同步兼容适配器 |
| `questionnaire_v2.py` 只接受 `questionnaire_v2.0` 12 题 | 无法承载 20 题和 6 题快速状态 | 按 `schema_version` 分发到独立评分器，旧入口保留为兼容别名 |
| `assessment_v2.py` 以问卷确定性结果为基线 | 自由文本证据、冲突、缺失和追问还未形成统一模型 | 统一 EvidenceItem，并把所有来源归一到相同证据管道 |
| `diagnosis_v2.py` 主要输出一个本地候选 | 没有支持/反对证据和明确 abstain 语义 | 先生成白名单候选，再按证据门槛排序或拒绝判断 |
| Prompt 主要内嵌 Python 字符串 | 难以版本管理、复现和评估 | 移到版本化文件，响应严格按 JSON Schema 验证 |
| 测试以单元测试为主 | 无法量化证据引用、无依据结论和 abstention | 新增 60 案例离线评估与可重复指标输出 |

## 3. 方案比较与选型

### 方案 A：单次 LLM 端到端生成

由一次 Prompt 同时完成问卷解释、文本抽取、评估、辨证倾向和追问。

- 优点：开发初期代码少，链路短。
- 缺点：不可解释、难以定位失败；问卷分数可能被模型覆盖；无法可靠实现安全阻断和 V2.0 兼容。
- 结论：不采用。

### 方案 B：确定性规则 + LLM 受约束提取/排序（推荐）

问卷评分、安全判断、证据合并、冲突检测、追问决策树和 abstain 门槛由本地规则负责；Qwen 只负责自由文本/材料的结构化提取，并在白名单候选中辅助排序。

- 优点：保留可测试的业务边界；Provider 失败时可降级；每条结论都能回溯来源；适合医疗相关高风险场景。
- 缺点：需要维护 Schema、规则和评估集；初期代码量较大。
- 结论：采用。

### 方案 C：拆为独立 AI 微服务和消息队列

Provider、提取、Assessment、Diagnosis 分成独立服务，通过异步任务传输。

- 优点：长期扩展和隔离能力强。
- 缺点：超出 Sprint 4 范围，增加部署、持久化和联调成本；当前 FastAPI 进程内工作流无法直接复用。
- 结论：暂不采用；保留模块边界，为后续拆服务留接口。

## 4. 总体架构

```text
┌────────────────────────────────────────────────────────────┐
│                    AI Understanding Facade                 │
│  run_assessment_v21() / run_diagnosis_v21()                │
└──────────────┬─────────────────────┬───────────────────────┘
               │                     │
       ┌───────▼────────┐    ┌───────▼──────────┐
       │ Deterministic  │    │ Provider Gateway  │
       │ Rules           │    │ Async Qwen/Mock   │
       │ safety/scoring/ │    │ retry/timeout/    │
       │ fusion/gating  │    │ repair/metrics    │
       └───────┬────────┘    └───────┬──────────┘
               │                     │
       ┌───────▼─────────────────────▼───────┐
       │ Canonical Evidence Model             │
       │ EvidenceItem / Conflict / Missing    │
       │ FollowUpQuestion / Revision          │
       └───────┬─────────────────────┬────────┘
               │                     │
       ┌───────▼────────┐    ┌───────▼──────────┐
       │ Assessment      │    │ Diagnosis        │
       │ evidence score  │    │ whitelist        │
       │ follow-up tree  │    │ candidate rank   │
       │ confirmation    │    │ supporting/      │
       │                 │    │ contradicting   │
       └─────────────────┘    └──────────────────┘
```

### 4.1 数据流顺序

1. 校验输入 envelope、版本和长度；不符合契约时返回机器可读错误。
2. 先执行安全规则，不把高风险原文发送给 Provider。
3. 对问卷执行确定性评分，生成问卷 EvidenceItem。
4. 对自由描述和已确认材料调用 Provider；空文本、未确认 OCR 和用户跳过内容不调用 Provider。
5. 校验 Provider JSON，只接受声明过的字段和允许的枚举值；解析失败进入显式降级。
6. 归一化多源 EvidenceItem，计算维度分数、冲突、缺失和 `evidence_coverage_score`。
7. 按固定决策树生成 0-6 道追问；首版规则默认最多 4 道，契约上限仍为 6 道。
8. Assessment 返回 `requires_user_confirmation=true`；只有确认后的 Assessment 才能进入 Diagnosis。
9. Diagnosis 只从本地白名单中生成候选；证据不足、冲突未解决或安全阻断时返回 `abstained=true`。

## 5. 核心接口与数据契约

### 5.1 Provider Gateway

新增接口建议如下，具体命名以现有模块导入约定为准：

```python
@dataclass(frozen=True)
class ProviderRequest:
    system_prompt: str
    user_prompt: str
    operation: str              # narrative_extraction / diagnosis_rank
    prompt_version: str
    timeout_seconds: float = 20.0


@dataclass(frozen=True)
class ProviderResponse:
    data: dict[str, object]
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    attempts: int


class ProviderError(RuntimeError):
    reason_code: str             # TIMEOUT / NETWORK / RATE_LIMIT / INVALID_JSON / SCHEMA_ERROR
    retryable: bool
    user_message: str


class AsyncJsonProvider(Protocol):
    async def complete_json(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError
```

Provider 行为：

- 默认最多 2 次尝试：首次失败只对 `NETWORK`、`5XX`、`RATE_LIMIT` 重试；`TIMEOUT` 仅允许一次短重试；`INVALID_JSON` 先执行一次 JSON 修复再判定失败。
- 每次请求使用显式 `timeout_seconds`，总耗时不得超过调用方预算。
- JSON 修复只允许从响应中提取一个对象，不允许通过默认值补齐业务字段；修复后仍不合法必须返回 `INVALID_JSON`。
- Token、模型、Prompt 版本、延迟只写结构化元数据；普通日志不得写 API Key、病例全文、自由描述全文或原始 OCR 文本。
- `MockProvider` 支持固定成功、超时、网络失败、非法 JSON、Schema 错误五类场景，并记录调用次数。
- 保留现有同步 `JsonLLMProvider` 作为 Sprint 2/3 兼容入口；新 Provider 通过显式 adapter 接入旧同步函数，不在旧调用方中偷偷启动事件循环。

### 5.2 Questionnaire Dispatcher

```python
def score_questionnaire(
    answers: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """兼容旧 V2.0 调用；根据 schema_version 分发评分。"""


def score_questionnaire_v21(
    envelope: Mapping[str, Any],
) -> QuestionnaireScore:
    """校验并评分 questionnaire_v2.1 20 题。"""


def score_quick_state(
    envelope: Mapping[str, Any],
) -> QuickStateScore:
    """校验并评分 quick_state_v1 6 题。"""
```

约束：

- `questionnaire_v2.0` 原有字段和错误行为不变。
- V2.1 的评分规则只从 `knowledge/questionnaire-scoring-v2.1.json` 读取，不在代码里重复定义权重。
- `q04_worry_control` 初版仅做定性记录，不重复计入与 Q03 相同的 `tension_worry` 聚合，避免 double-count。
- Quick State 使用 0-10 原始分，不能直接作为阶段性 Assessment 的 0-4 分量；需通过明确字段标注为 `quick_state`。
- 单题不能直接生成候选倾向；任何 Diagnosis 候选至少需要两个独立维度或一条以上独立文本/材料证据支持。

### 5.3 Narrative Extraction

`narrative_schema.py` 负责把 Provider 输出转成统一证据，不负责候选倾向和追问。13 类信息为：

1. `emotion_state`
2. `worry_thought`
3. `irritability`
4. `mood_interest`
5. `fear_unease`
6. `sleep`
7. `energy`
8. `appetite`
9. `physical_signal`
10. `life_event`
11. `duration`
12. `daily_impact`
13. `goal_and_expectation`

```python
@dataclass(frozen=True)
class NarrativeEvidence:
    category: str
    label: str
    value: int | str | bool | None
    polarity: str
    time_window: str | None
    quote: str
    source_ref: str
    extraction_confidence: float
    negated: bool


async def extract_narrative(
    text: str,
    *,
    source_type: Literal["narrative", "document"],
    provider: AsyncJsonProvider,
) -> NarrativeExtractionResult:
    raise NotImplementedError
```

要求：

- `quote` 必须是输入文本中可定位的短片段，不能由模型自由改写成输入中不存在的事实。
- 否定表达、时间范围和不确定表达必须保留到结构化字段。
- 每条 EvidenceItem 都带 `source_type`、`source_ref`、`quote` 和 `extraction_confidence`。
- Provider 失败返回 `status=unavailable|degraded` 和错误码；Assessment 必须保留该来源的处理状态，不能静默当成“没有输入”。

### 5.4 Assessment Fusion

Assessment 以 `docs/sprint4/assessment-contract-v2.1.md` 为正式对外契约，并实现以下规则：

```text
evidence_coverage_score
  = 有证据的维度数 / 总维度数
  × min(1.0, 不同 source_type 数量 / 3)
```

- “有证据的维度”指至少一条通过 Schema 校验、且 `confirmed` 或来源为确定性问卷的 EvidenceItem。
- 来源多样性只统计 `questionnaire`、`narrative`、`document`、`user_follow_up`、`user_correction` 中实际出现的类型。
- `source_type` 不因 Provider 失败而计入；Provider 返回 unavailable 时要在 `input_processing_status` 中显示。
- 冲突检测只标记事实差异，不自动选择“正确来源”。冲突结果包含主题、来源值、严重度、用户解决状态。
- 缺失信息按 `critical|important|supplementary` 分级；追问只从缺失或冲突的结构化原因中生成。

追问决策树固定优先级：

```text
安全风险                         → 不追问，blocked_safety
关键时间缺失                     → duration
关键影响程度缺失                 → daily_impact
主要来源冲突                     → conflict_resolution
候选倾向接近                     → discriminating_question
身体信号需要确认                 → physical_confirmation
coverage < 0.70                  → supplementary_context
```

每次运行按优先级去重，默认最多返回 4 道，契约允许最多 6 道；追问回答进入 `user_follow_up` 来源，并通过 `revision + 1` 重新生成 Assessment。任何一次用户修正都生成新 Revision，不覆盖历史结果。

### 5.5 Diagnosis

Diagnosis 的输出不再只依赖 `primary_tendency`，而是以候选列表为核心：

```json
{
  "status": "success|degraded|blocked_safety",
  "abstained": false,
  "abstain_reason": null,
  "candidate_tendencies": [
    {
      "id": "syd_001",
      "label": "辅助辨证倾向展示名",
      "score": 0.82,
      "supporting_evidence_ids": ["ev_001", "ev_004"],
      "contradicting_evidence_ids": ["ev_008"],
      "reasoning_summary": "由两个独立维度和一条文本证据共同支持"
    }
  ],
  "confidence": {"level": "medium", "score": 0.68},
  "warnings": [],
  "assessment_revision": 2,
  "disclaimer": "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。"
}
```

Abstain 条件：

- Assessment 为 `blocked_safety`。
- Assessment 尚未用户确认。
- `evidence_coverage_score < 0.50` 且没有两个独立维度支持任何候选。
- 存在 `major` 冲突且 `resolution != resolved_by_user`。
- Provider 的候选排序无效；此时可保留本地候选，但不能把模型输出当成事实。

LLM 只能从 `MVP_SYNDROMES` 白名单选择和排序，不能创建新 ID、修改规则支持维度或生成医疗诊断文本。本地规则先生成可解释候选，LLM 失败时保留本地结果并把 `degradation.reason_codes` 返回给前端。

## 6. Prompt、日志与隐私

### 6.1 Prompt 版本

- `prompt/assessment/narrative_extraction_v2.1.json`
- `prompt/assessment/conflict_normalization_v2.1.json`
- `prompt/diagnosis/candidate_rank_v2.1.json`

每个 Prompt 文件包含 `prompt_version`、任务目的、允许字段、枚举白名单、禁止输出、示例和 Schema 版本。运行结果的 `model_metadata.prompt_version` 必须与实际加载文件一致。

### 6.2 隐私边界

- Provider 请求前先执行长度限制、敏感字段屏蔽和安全规则；不把姓名、电话、身份证、住址等直接标识符送入 Prompt。
- 日志只保留 `session_id` 的不可逆短标识、operation、reason_code、latency、token 计数和结果状态。
- 不记录病例全文、自由描述全文、OCR 全文、Prompt 原文和 API Key。
- 评估集使用脱敏、合成或经过授权的文本；报告只输出统计指标和案例编号。

## 7. 测试与验收

### 7.1 单元测试

- Provider：成功、重试、超时、网络失败、限流、非法 JSON、JSON 修复、Token 统计、Mock 调用次数。
- Questionnaire：V2.0 回归、V2.1 20 题完整校验、Quick State 0-10 校验、版本拒绝、Q04 不 double-count。
- Narrative：13 类字段、否定、时间、短 quote、越界枚举、空文本和 Provider 失败。
- Assessment：五类来源、coverage 公式、冲突、缺失、追问优先级、最多 4/6 题、Revision、确认门禁、安全阻断。
- Diagnosis：候选支持/反对证据、白名单、单题不足、major 冲突、未确认、Provider 失败和 `abstained`。

### 7.2 评估指标

`evals/run_sprint4_eval.py` 读取 `evals/sprint4/cases.jsonl` 和安全案例，输出 JSON 报告及可读摘要：

| 指标 | 目标 |
|---|---:|
| V2.1 Schema 通过率 | 100% |
| 有效自由文本实际尝试 Provider 率 | 100% |
| 输入静默丢弃率 | 0% |
| 证据引用正确率 | ≥95% |
| 无依据结论率 | ≤5% |
| 情绪/事件/身体信号综合 F1 | ≥0.80 |
| 冲突识别率 | ≥80% |
| 关键安全召回率 | 100% |
| Diagnosis abstain 规则准确率 | 100%（规则案例） |
| Qwen 错误可解释率 | 100% |

### 7.3 回归门槛

- `pytest -q tests/ai_engine tests/api` 全部通过。
- Sprint 2 旧入口和 Sprint 3 V2 合约测试全部通过。
- `python evals/run_sprint4_eval.py --cases evals/sprint4/cases.jsonl` 能生成报告，不依赖真实 Qwen Key；默认使用 Mock Provider。
- `git diff --check` 通过。

## 8. 分阶段实施方案

具体步骤见 [`ai-understanding-implementation-plan.md`](ai-understanding-implementation-plan.md)。总体顺序如下：

| 阶段 | 交付 | 依赖 | 完成标志 |
|---|---|---|---|
| 1 | Canonical 类型与 Provider 错误模型 | 现有 `providers.py` | 单元测试覆盖五类失败 |
| 2 | Provider Async/Mock/兼容适配器 | 阶段 1 | 无 Key 可完整跑测试 |
| 3 | 问卷 V2.1/Quick State 分发与评分 | S4-02 JSON | 三版本 Schema/评分通过 |
| 4 | Narrative Schema 与 Prompt | 阶段 2/3 | 13 类字段可验证，quote 可回溯 |
| 5 | Assessment 融合、冲突、追问、Revision | 阶段 3/4 | coverage 和追问树确定性通过 |
| 6 | Diagnosis 候选与 abstained | 阶段 5 | 支持/反对证据和门禁通过 |
| 7 | 评估脚本与联调 | 阶段 1-6 | 60 案例报告和全量回归通过 |

## 9. 兼容、发布与回滚

- 新增 V2.1 入口，不删除 `run_assessment_v2`、`run_diagnosis_v2` 和 V2.0 评分入口。
- 新字段对旧客户端采用可选字段策略；旧客户端继续读取 `primary_tendency`，新客户端读取 `candidate_tendencies`。
- Provider 默认 Mock/本地规则可运行；生产环境由环境变量启用 Qwen，不把 Key 写入仓库。
- 若 V2.1 任一门禁失败，集成分支保留代码但关闭 V2.1 路由开关，继续使用 V2.0 兼容链路；不回滚 Sprint 2 模块。
- 合并前必须附上测试命令、评估报告、降级案例和契约差异说明。

## 10. 待 Review 决策

以下内容已在本设计中给出默认选择，团队 Review 如无异议即按此冻结：

1. Provider 新入口采用 async，旧同步接口通过显式 adapter 保留。
2. Q04 `worry_control` 初版只做定性记录，不参与 `tension_worry` 聚合。
3. 追问契约上限为 6，道路由首版默认最多输出 4 道。
4. Diagnosis 采用本地白名单候选 + LLM 排序，不能由 LLM 新增倾向。
5. `evidence_coverage_score` 使用三来源多样性公式，不以 Provider 是否成功作为单独证据来源。

---

*本设计文稿用于 S4-04 开发前评审；实现前需由团队确认正式契约版本和 S4-02 的问卷评分 JSON。*
