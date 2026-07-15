# ADR-0002: 选择 LangGraph 而非 CrewAI

> **状态：** 已采纳
> **日期：** 2026-07-11
> **决策者：** 陈家智（AI Architect）

---

## 背景

项目需要多 Agent 编排框架。候选方案：LangGraph（LangChain 生态）和 CrewAI。

## 决策

**选择 LangGraph + langgraph-supervisor 作为 Agent 编排框架，不选择 CrewAI。**

## 理由

1. **Supervisor 模式：** LangGraph 支持 Supervisor Agent 模式——一个中央调度器根据条件动态决定下一个 Agent 是否执行、走哪条路径。这恰好匹配我们的"反馈→微调/重新辨证"条件分支。
2. **条件边（Conditional Edge）：** LangGraph 的状态图支持条件分支（`confidence < 0.4 → 跳过处方Agent`），CrewAI 的线性 Task 流不支持。
3. **状态持久化：** LangGraph 内置 checkpoint，支持 Agent 执行到一半时保存状态，后面恢复。CrewAI 无此特性。
4. **社区活跃度：** LangGraph 是 LangChain 生态核心项目，GitHub Stars > 10k，社区维护活跃。CrewAI 相对较新。
5. **可观测性：** LangGraph 的 tracing 集成 LangSmith，便于调试多 Agent 链路。

## 后果

- **正面：** 条件分支 + 状态持久化完美匹配五 Agent 的反馈回路设计。
- **正面：** 与 Qwen（通过 LangChain 的 ChatModel 接口）集成方便。
- **负面：** LangGraph 学习曲线较陡（Graph API + State 概念），钟睿宸需要额外学习时间。
- **负面：** LangChain 生态版本更新频繁，需要注意依赖锁定。
