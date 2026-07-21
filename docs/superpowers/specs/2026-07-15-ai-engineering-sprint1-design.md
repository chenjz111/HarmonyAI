# AI Engineering Sprint 1 Design

## Goal

为 HarmonyAI 建立一个可本地运行、可替换外部依赖的 AI Engineering Sprint 1 最小闭环，覆盖 Prompt Engine、两节点 Agent 工作流，以及 Qwen/Chroma/LangGraph 的适配边界。

## Scope

本次实现聚焦 AI Engineering Lead 的 Sprint 1 验收项：

- Prompt Engine：根据模板 ID 和参数生成可验证的完整 Prompt。
- Agent Workflow：实现评估节点到音乐处方节点的结构化状态传递。
- Provider Adapters：定义 LLM 和向量检索接口，外部服务不可用时可降级运行。
- Tests：覆盖正常流程、空输入、缺失模板参数、低置信度和 Provider 失败。

本次不实现 FastAPI、数据库、前端、真实医疗诊断或真实音频生成。

## Approaches Considered

### Pure LangGraph

所有流程直接绑定 LangGraph。优点是贴近目标技术栈；缺点是本地演示必须安装并维护较多依赖，外部服务失败时测试和演示不稳定。

### Pure Custom State Machine

使用自研 Python 状态机替代 LangGraph。优点是依赖少；缺点是与项目既定的 LangGraph + Supervisor 架构偏离，未来迁移成本较高。

### Adapter-Based Hybrid

使用小型、明确的内部工作流协议承载核心业务，并通过适配器接入 LangGraph、Qwen 和 Chroma。默认提供规则引擎和内存检索 fallback。该方案被选中，因为它同时满足 Sprint 1 的可运行性、可测试性和后续替换能力。

## Architecture

```text
Input
  -> EvaluationNode
       -> health_profile / emotion_scores
  -> PrescriptionNode
       -> tone_weights / BPM / instruments / prompt_template
  -> Structured WorkflowResult
```

### Components

- `backend/ai_engine/models.py`：工作流状态、节点输出和 Provider 协议使用的结构化类型。
- `backend/ai_engine/prompt_engine.py`：加载 `prompt/v1/` 模板，校验必需参数，缺少可选参数时使用安全默认值。
- `backend/ai_engine/providers.py`：定义 LLM 与向量检索协议，并提供规则/内存 fallback。
- `backend/ai_engine/workflow.py`：编排评估节点和处方节点；节点之间只依赖结构化状态，不依赖具体 Provider 实现。
- `prompt/v1/CN_V1.txt`：版本化中文音乐生成 Prompt 模板。

## Contracts

所有 Agent 输出至少包含：

```json
{
  "agent_id": "evaluation_agent",
  "agent_version": "1.0.0",
  "confidence": 0.85,
  "reason": ["..."],
  "processing_time_ms": 0,
  "timestamp": "2026-07-15T00:00:00Z"
}
```

工作流内部使用 Python 结构化对象；对外导出时提供 JSON-compatible 字典。Prompt 只在运行时组装，不写入 Agent Schema 的持久化对象。

## Error Handling and Fallback

- 空输入：生成默认的中性健康画像，并在 `reason` 中标记 fallback。
- 模板缺失：抛出明确的 `TemplateNotFoundError`，不静默生成错误 Prompt。
- 缺少 Prompt 参数：可选字段使用默认值；必需字段使用安全默认值并记录原因。
- LLM 或向量检索失败：切换到规则引擎/内存检索，并将 `degradation_triggered` 记录到结果中。
- 置信度低于 0.4：结果保留，但设置专业人员复核提醒。

## Testing Strategy

遵循 Red-Green-Refactor：

1. 先验证 Prompt 模板组装的失败测试。
2. 再验证 Provider fallback 的失败测试。
3. 再验证工作流节点和状态传递的失败测试。
4. 最后运行完整测试集和一个无外部服务的演示命令。

测试不调用真实 Qwen、Chroma 或远程 API；这些依赖通过协议和确定性的 fallback 实现隔离。

## Non-Goals

- 不将演示规则描述为医疗结论。
- 不引入 FastAPI、MySQL、Redis 或前端代码。
- 不在本次实现真实向量数据库持久化或音频供应商调用。

