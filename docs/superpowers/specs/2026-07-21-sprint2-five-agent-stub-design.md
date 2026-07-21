# Sprint 2 Five-Agent LangGraph Stub Design

## Goal

实现 Sprint 2 Day 2–3 的五 Agent LangGraph stub 骨架，让 HarmonyAI 在不依赖 Qwen、Chroma、数据库或真实音乐 API 的情况下，完成可演示的端到端闭环。

## Scope

本次只实现确定性 stub：

1. Assessment：接收问卷/情绪输入，输出结构化情绪画像。
2. Diagnosis：从评估结果生成示例证型、五行和置信度。
3. Prescription：生成调式、BPM、乐器和 Prompt 参数。
4. Generation：返回本地演示音频的占位 URL，不调用外部音乐服务。
5. Feedback：接收示例评分，返回 `continue` 决策。

不实现 Qwen 推理、Chroma 检索、数据库写入、FastAPI 路由或前端页面。这些由 Sprint 2 后续任务和其他角色负责。

## Approaches Considered

### Sequential Python Functions

直接顺序调用五个函数，开发最快，但无法证明 LangGraph 状态编排与条件边可用，不满足 Issue #15。

### Full Real Agents

一次接入 Qwen、Chroma、真实知识库和音乐 API，结果最接近成品，但依赖未全部就绪，无法保障 Day 4 联调。

### LangGraph with Deterministic Stubs

采用真实 `StateGraph` 作为编排器，节点只返回稳定的示例 Schema 数据。该方案被选中：它满足 Day 4 的假数据闭环，并可在后续逐节点替换为真实实现。

## Architecture

```text
START
  -> assessment_stub
  -> diagnosis_stub
  -> [confidence < 0.4] low_confidence_handler -> END
  -> [otherwise] prescription_stub
  -> generation_stub
  -> feedback_stub
  -> END
```

工作流 State 保存 `run_id`、`user_id`、`session_id`、原始输入、各 Agent 统一结果，以及最终状态。每一个 Agent 节点只读取上游字段，并写入自己的结果字段；节点不直接访问外部网络或数据库。

## Universal Agent Envelope

每个节点输出符合 `docs/agent-architecture.md` 的统一外壳：

```json
{
  "agent_id": "evaluation_agent",
  "agent_version": "1.0.0",
  "agent_name": "评估Agent",
  "agent_layer": "medical_analysis",
  "run_id": "...",
  "session_id": "...",
  "user_id": "...",
  "status": "success",
  "confidence": 0.85,
  "reason": ["stub：使用确定性示例数据"],
  "warnings": [],
  "input": {},
  "output": {},
  "processing_time_ms": 0,
  "timestamp": "ISO-8601",
  "retry_count": 0
}
```

正常路径的 five-agent result key 为 `assessment`、`diagnosis`、`prescription`、`generation`、`feedback`。低置信度路径不会生成处方或音频，而是添加 `low_confidence` 结果，并返回专业人员复核提醒。

## Error Handling

- 空问卷/空情绪输入：Assessment 返回 `degraded`，置信度 `0.3`。
- Diagnosis 置信度小于 `0.4`：条件边转入 `low_confidence_handler`，不进入处方或生成。
- Stub 不调用外部服务，因此 Day 4 演示不受模型、网络、API 密钥或数据库状态影响。
- 真实 Agent 替换时，保持 State key 和统一外壳不变；异常与降级逻辑按 `agent-architecture.md` 扩展。

## Files

- `backend/ai_engine/agent_stubs.py`：五个确定性节点和统一外壳创建函数。
- `backend/ai_engine/langgraph_workflow.py`：`StateGraph`、条件边和运行入口。
- `backend/ai_engine/sprint2_demo.py`：正常路径和低置信度路径的命令行演示。
- `tests/ai_engine/test_langgraph_workflow.py`：正常闭环、低置信度分支、统一字段测试。
- `pyproject.toml`：声明 LangGraph 运行依赖。
- `README.md`：增加 Sprint 2 stub 演示命令。

## Verification

- `python -m pytest -q` 通过。
- `python -m backend.ai_engine.sprint2_demo` 输出五 Agent 正常闭环 JSON。
- 测试输入空情绪时，验证只产生低置信度提醒而不产生处方/生成结果。
- 五个正常节点输出均包含统一外壳的必填字段。

