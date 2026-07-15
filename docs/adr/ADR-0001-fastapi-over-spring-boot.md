# ADR-0001: 选择 FastAPI 而非 Spring Boot

> **状态：** 已采纳
> **日期：** 2026-07-11
> **决策者：** 陈家智（AI Architect）

---

## 背景

项目需要选择后端框架。团队中有 Java（Spring Boot）和 Python（FastAPI）两种方案的候选人。

## 决策

**选择 FastAPI（Python 3.10+）作为后端框架，不选择 Spring Boot。**

## 理由

1. **与 Python AI 生态兼容：** LangGraph、Qwen2.5-7B、Chroma、BGE-M3 全部是 Python 生态。选择 Python 后端意味着 AI 和后端在同一进程中调用，无需跨语言 RPC，降低延迟和复杂度。
2. **异步原生支持：** FastAPI 基于 Starlette + asyncio，适合 I/O 密集型场景（调用 LLM、调用音乐 API、读写数据库）。
3. **自动生成 OpenAPI/Swagger：** FastAPI 原生支持，前端团队可以直接参考 Swagger 文档。
4. **Schema 验证：** Pydantic 与 JSON Schema 天然兼容，Agent I/O Schema 可以直接用 Pydantic 模型定义。
5. **学习成本低：** 团队 Python 基础好，FastAPI 上手快。

## 后果

- **正面：** AI 引擎和后端在同一语言栈中，开发效率高，调试方便。
- **负面：** Python 在大型项目中类型安全性不如 Java。需要通过 Pydantic 严格定义所有数据模型来弥补。
- **负面：** Python GIL 限制多核性能。但本项目的瓶颈在 I/O（LLM 调用、音乐 API），不在 CPU，影响可控。
