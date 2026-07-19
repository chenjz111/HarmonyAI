# Agent Architecture（Agent 架构标准）

> **版本：** V0.1（Draft，待 Kickoff Review）
> **日期：** 2026-07-15
> **作者：** 陈家智（Project Leader & AI Architect）
> **状态：** 等待团队 Review → V0.2 → Sprint 结束定 V1.0

---

## 文档定位

这份文档定义了 HarmonyAI 所有 Agent 的**统一架构标准**——每个 Agent 长什么样、怎么跑、怎么死、怎么活过来。

**这是所有 Agent 的"宪法"。** 钟睿宸写 LangGraph 实现时必须遵守，蔡子鑫设计数据库和 API 时必须遵守。

**读者：**
- AI Engineering Lead（钟睿宸）：全文必读，这是你的施工规范
- Backend Engineer（蔡子鑫）：通用字段 → 数据库列设计；生命周期 → API 状态码设计
- Medical Knowledge Engineer（肖宇翔）：理解 Agent 怎么用你的知识库
- Client Engineer（彭翔）：理解 Agent 生命周期 → 前端 loading/error/success 状态

**前置阅读：** `docs/architecture/agent-schemas.md`（五 Agent I/O Schema 已定义）

---

## 第一章：每个 Agent 的统一外壳（Universal Shell）

### 1.1 一句话

> 不管 Agent 内部多复杂，外面看起来一模一样。就像一个 USB 接口——不管里面什么芯片，插口是统一的。

### 1.2 通用字段规范（所有 Agent 输出必须包含）

```json
{
  "agent_id": "evaluation_agent",
  "agent_version": "1.0.0",
  "agent_name": "评估Agent",
  "agent_layer": "medical_analysis",

  "run_id": "run_20260715_001_eval",
  "session_id": "sess_20260715_001",
  "user_id": "u_001",

  "status": "success",
  "confidence": 0.85,
  "reason": ["规则引擎匹配度0.85", "文献支持度0.72", "用户问卷完成率100%"],
  "warnings": [],

  "input": { ... },
  "output": { ... },

  "processing_time_ms": 2340,
  "timestamp": "2026-07-15T10:00:00Z",
  "retry_count": 0
}
```

### 1.3 通用字段详细定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | ✅ | Agent 唯一标识，小写+下划线：`evaluation_agent` / `diagnosis_agent` / `prescription_agent` / `generation_agent` / `feedback_agent` |
| `agent_version` | string | ✅ | 语义化版本 `MAJOR.MINOR.PATCH` |
| `agent_name` | string | ✅ | 中文名称，给前端展示用 |
| `agent_layer` | enum | ✅ | 所属架构层：`medical_analysis` / `knowledge_mapping` / `ai_generation` |
| `run_id` | string | ✅ | 本次运行的唯一标识 |
| `session_id` | string | ✅ | 用户会话 ID |
| `user_id` | string | ✅ | 用户 ID |
| `status` | enum | ✅ | 运行状态：`ready` / `running` / `success` / `failed` / `degraded` / `skipped` |
| `confidence` | float (0-1) | ✅ | 整体可信度 |
| `reason` | string[] | ✅ | 决策依据列表（Explainability 的核心） |
| `warnings` | string[] | ⚠ | 警告信息列表 |
| `input` | object | ✅ | 输入数据（Schema 见各 Agent 定义） |
| `output` | object | ✅ | 输出数据（Schema 见各 Agent 定义） |
| `processing_time_ms` | int | ✅ | 处理耗时（毫秒） |
| `timestamp` | ISO 8601 | ✅ | 输出时间戳 |
| `retry_count` | int | ✅ | 重试次数（0 = 首次成功） |

### 1.4 为什么通用字段重要

```
没有通用字段：
  Agent ① 输出 {"emotion_scores": {...}, "time": "..."}
  Agent ② 输出 {"syndrome": {...}, "reliability": 0.71}
  → 前端/后端/日志系统无法统一处理

有了通用字段：
  Agent ① 输出 {agent_id, status, confidence, reason, output: {emotion_scores: ...}}
  Agent ② 输出 {agent_id, status, confidence, reason, output: {syndrome: ...}}
  → 日志系统一行代码处理所有 Agent
  → 前端一个组件渲染所有 Agent 结果
  → 监控系统统一采集 confidence 和 processing_time_ms
```

---

## 第二章：Agent 生命周期（Lifecycle）

### 2.1 状态机

```
                    ┌─────────────┐
                    │   READY     │  ← 初始状态
                    └──────┬──────┘
                           │ LangGraph Supervisor 调度
                           ▼
                    ┌─────────────┐
                    │  RUNNING    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ SUCCESS  │ │ DEGRADED │ │  FAILED  │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │            │            │
            │            │            ▼
            │            │     ┌──────────┐
            │            │     │  RETRY   │──→ RUNNING（重试）
            │            │     └────┬─────┘
            │            │          │ 超过 max_retries
            │            │          ▼
            │            │     ┌──────────┐
            │            │     │ SKIPPED  │  ← 跳过此 Agent，执行降级路径
            │            │     └──────────┘
            ▼            ▼
       ┌──────────────────────────┐
       │  流转至下一个 Agent       │
       └──────────────────────────┘
```

### 2.2 状态定义

| 状态 | 含义 | 触发条件 | 前端展示 |
|------|------|----------|----------|
| `ready` | 等待调度 | Agent 初始化完成，等待 Supervisor 调度 | 不展示（内部状态） |
| `running` | 执行中 | Supervisor 调起 Agent | Loading spinner + "正在评估您的健康状况…" |
| `success` | 成功完成 | 正常执行完成，confidence ≥ 阈值 | 正常展示结果 |
| `degraded` | 降级成功 | 主路径失败但备路径成功 | 结果正常展示 + 小字提示"部分功能受限" |
| `failed` | 执行失败 | 主路径失败，进入 retry 逻辑 | 不展示（内部重试） |
| `retry` | 重试中 | 第 N 次重试 | Loading spinner（对用户无感知） |
| `skipped` | 已跳过 | 超过最大重试次数，降级路径也失败 | 展示降级信息 + "建议重新尝试" |

### 2.3 状态转换规则

```python
# LangGraph Supervisor 中的状态管理
class AgentLifecycle:
    MAX_RETRIES = 3  # 最多重试 3 次
    
    def transition(self, agent_id: str, current_status: str, result: dict) -> str:
        if current_status == "running":
            if result.get("success"):
                return "success"
            elif result.get("degraded"):
                return "degraded"
            else:
                if result.get("retry_count", 0) < self.MAX_RETRIES:
                    return "retry"
                else:
                    return "skipped"
        
        if current_status == "retry":
            # 与 running 相同的判断逻辑
            return self.transition(agent_id, "running", result)
        
        return current_status
```

### 2.4 可跳过条件

某些情况下，Agent 可以被跳过（不执行）：

| Agent | 可跳过条件 | 跳过时行为 |
|-------|-----------|-----------|
| ① 评估Agent | ❌ 不可跳过（系统入口） | — |
| ② 辨证Agent | ❌ 不可跳过（处方依赖） | — |
| ③ 处方Agent | ❌ 不可跳过（核心逻辑） | — |
| **④ 生成Agent** | ✅ 可跳过（本地曲库兜底） | 返回本地曲库中匹配度最高的音频 |
| ⑤ 反馈Agent | ✅ 可跳过（用户不填反馈） | 不更新用户画像，下次使用默认参数 |

---

## 第三章：异常处理与降级标准（Error Handling & Degradation）

### 3.1 异常分级

```
Level 1: 可恢复异常（Retry）
  ├── 网络超时（API 调用）
  ├── LLM 返回格式不合法（重试 JSON 解析）
  ├── 数据库连接临时断开
  └── 处理：自动重试，最多 3 次

Level 2: 可降级异常（Degrade）
  ├── 音乐 API 全部不可用 → 降级到本地曲库
  ├── Qwen 模型超时 → 降级到纯规则引擎
  ├── RAG 检索超时 → 使用基础映射表（不用知识库）
  └── 处理：走备选路径，标记 status = "degraded"

Level 3: 阻断异常（Fail + Alert）
  ├── MySQL 完全不可用
  ├── 用户数据损坏
  ├── 系统内存溢出
  └── 处理：记录日志，通知管理员，返回友好错误给用户
```

### 3.2 各 Agent 的降级策略

#### Agent ① 评估Agent（evaluation_agent）

| 异常场景 | 降级策略 | status |
|----------|----------|--------|
| OCR 识别失败 | 提示用户手动输入 | `degraded` |
| 问卷未完成（<50%） | 使用已完成部分估算，标记低可信度 | `degraded` |
| 所有输入渠道失败 | 无法降级 → `skipped`，提示用户重试 | `skipped` |

#### Agent ② 辨证Agent（diagnosis_agent）

| 异常场景 | 降级策略 | status |
|----------|----------|--------|
| LLM 调用超时 | 纯规则引擎（硬编码映射表） | `degraded` |
| RAG 检索超时 | 不使用文献支持，confidence 降低 0.15 | `degraded` |
| LLM + 规则引擎均失败 | 无法降级 → `skipped` | `skipped` |

#### Agent ③ 处方Agent（prescription_agent）

| 异常场景 | 降级策略 | status |
|----------|----------|--------|
| 权重网络计算异常 | 使用基础权重表（不调 severity 参数） | `degraded` |
| Prompt Engine 组装失败 | 使用预存的默认 Prompt | `degraded` |
| 知识库检索超时 | 降级为基础映射（不用知识库增强） | `degraded` |

#### Agent ④ 生成Agent（generation_agent）

| 异常场景 | 降级策略 | status |
|----------|----------|--------|
| SkyMusic API 超时 | → 尝试 MiniMax | `degraded` |
| MiniMax 也失败 | → 尝试 Fun-Music | `degraded` |
| 全部 API 失败 | → 本地五音曲库（匹配度最高曲目） | `degraded` |
| 本地曲库也失败 | → 静默失败，返回空音频 URL | `skipped` |

#### Agent ⑤ 反馈Agent（feedback_agent）

| 异常场景 | 降级策略 | status |
|----------|----------|--------|
| 用户不填反馈 | 使用行为数据（完成率/播放次数）估算 | `degraded` |
| 反馈数据写入失败 | 缓存到 Redis，下次重试 | `degraded` |
| 连续 3 次写入失败 | 放弃本次反馈，不影响下次使用 | `skipped` |

### 3.3 降级标记传播

```
Agent ① degraded → Agent ② 收到 warning:"上游降级，输入可信度降低"
Agent ② degraded → Agent ③ 收到 warning:"证型判断基于规则引擎（非LLM），可信度较低"
Agent ③ degraded → Agent ④ 收到 warning:"处方参数使用默认值"
Agent ④ degraded → Agent ⑤ 收到 warning:"音乐来自本地曲库（非AI生成）"

每个 Agent 在 reason[] 中记录是否收到上游降级标记。
```

---

## 第四章：输入输出 Schema 版本管理

### 4.1 版本兼容规则

```
MAJOR: 不兼容的变更（旧版本消费者无法解析新版本输出）
  → 例：删除必填字段、改变字段类型

MINOR: 向后兼容的变更（旧版本消费者可以忽略新字段）
  → 例：新增可选字段、扩展枚举值

PATCH: 不影响 Schema 的变更
  → 例：字段描述修正、示例更新
```

### 4.2 Schema 升级流程

```
1. 提出 RFC（docs/rfc/）
   说明：为什么改 / 影响哪些 Agent / 向后兼容吗 / 迁移计划

2. 陈家智 Review → Approve / Reject / Request Changes

3. 如果 Approve：
   - schemas/v1.0/ 保留不动
   - 新 Schema 放入 schemas/v1.1/（MINOR）或 schemas/v2.0/（MAJOR）
   - 更新 system-architecture.md 和 agent-schemas.md
   - 通知 钟睿宸（AI）+ 蔡子鑫（API）+ 彭翔（前端）

4. 旧版本 Schema 支持 2 个 Sprint
   例：V1.0 在 Sprint 1-2 使用，Sprint 3 废弃
```

### 4.3 Schema 存储结构

```
schemas/
├── v1.0/                          ← Sprint 1 使用
│   ├── agent-01-evaluation.json   ← ① 评估Agent I/O
│   ├── agent-02-diagnosis.json    ← ② 辨证Agent I/O
│   ├── agent-03-prescription.json ← ③ 处方Agent I/O
│   ├── agent-04-generation.json   ← ④ 生成Agent I/O
│   └── agent-05-feedback.json     ← ⑤ 反馈Agent I/O
├── v1.1/                          ← Sprint 2+（如有变更）
└── deprecated/                    ← 废弃版本存档
```

---

## 第五章：监控与日志标准

### 5.1 每个 Agent 必须输出的日志

```
[AGENT_START]    agent_id=prescription_agent run_id=xxx session_id=xxx
[AGENT_INPUT]    agent_id=prescription_agent input_summary="证型:肝郁化火 confidence=0.71"
[AGENT_PROCESS]  agent_id=prescription_agent step="weight_compute" duration_ms=320
[AGENT_PROCESS]  agent_id=prescription_agent step="instrument_select" duration_ms=150
[AGENT_OUTPUT]   agent_id=prescription_agent output_summary="角调0.75 宫调0.15 羽调0.10"
[AGENT_END]      agent_id=prescription_agent status=success confidence=0.71 total_ms=1800
```

### 5.2 日志文件规范

```
logs/
├── agent-traces/        ← 每个 Agent 运行的完整 trace
│   └── {date}/{run_id}.json
├── errors/              ← 异常日志
│   └── {date}/errors.log
├── performance/         ← 性能监控
│   └── {date}/latency.csv
└── degradation/         ← 降级事件
    └── {date}/degradation.log
```

---

## 第六章：LangGraph Supervisor 调度规则

### 6.1 正常流程

```
START → ①评估 → ②辨证 → ③处方 → ④生成 → ⑤反馈 → END
```

### 6.2 条件分支

```python
# LangGraph 条件边
def route_after_diagnosis(state):
    """辨证完成后决定下一步"""
    if state["agent_2"]["confidence"] < 0.40:
        # 低可信度 → 跳过处方，直接提醒用户
        return "low_confidence_handler"
    elif state["agent_2"]["status"] == "degraded":
        # 降级 → 处方Agent 使用保守策略
        return "prescription_conservative"
    else:
        return "prescription_normal"

def route_after_feedback(state):
    """反馈完成后决定下一步"""
    decision = state["agent_5"]["decision"]["action"]
    if decision == "continue":
        return "push_next_day"       # 推送下一天处方
    elif decision == "adjust":
        return "adjust_prescription"  # 微调 → 返回③
    elif decision == "rediag":
        return "restart_diagnosis"    # 重新辨证 → 返回②
```

### 6.3 Supervisor 全局规则

```python
SUPERVISOR_RULES = {
    "global_timeout_ms": 60000,     # 整个 Session 不超过 60 秒
    "agent_timeout_ms": 30000,      # 单个 Agent 不超过 30 秒
    "max_retries_per_agent": 3,     # 每 Agent 最多重试 3 次
    "confidence_warning_threshold": 0.40,  # 低于此值触发就医提醒
    "parallel_agents": False,       # Sprint 1：串行执行（不并发）
}
```

---

## 附录 A：文档版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| V0.1 | 2026-07-15 | 初始草稿，六章完整 | 陈家智 |
| V0.2 | — | Kickoff Review 后修订 | 陈家智 |
| V1.0 | — | Sprint 1 结束定稿 | 陈家智 |

## 附录 B：给各角色的阅读指引

| 角色 | 重点阅读 | 可跳过 |
|------|----------|--------|
| AI Engineering Lead | 全文（这是 LangGraph 施工规范） | — |
| Backend Engineer | 第1、2、5章（通用字段 + 生命周期 + 日志） | 第6章（LangGraph 细节） |
| Medical Knowledge Engineer | 第1章（理解 Agent 输出格式） | 第2-6章 |
| Client Engineer | 第2章（状态机 → 前端 loading/error/success 状态） | 第3-6章 |
