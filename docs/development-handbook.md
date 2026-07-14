# HarmonyAI · Development Handbook

> 版本：V1.0  
> 日期：2026-07-12  
> 定位：所有开发规范的唯一依据

---

## 一、Project Principles

> 放在 README 第一页。每一条都可被评委/面试官追问。

| # | 原则 | 含义 |
|---|------|------|
| ① | **Knowledge First** | 所有AI推理必须基于Knowledge Engine，不能仅靠LLM自由生成 |
| ② | **Explainability** | 所有输出必须能够解释——为什么推荐这个调式、依据哪篇文献 |
| ③ | **Human in the Loop** | 任何医疗相关建议必须允许人工确认，可信度<40%强制提醒 |
| ④ | **Modular Design** | 所有Agent可替换——换音乐平台/LLM模型不影响其他模块 |
| ⑤ | **Fail Gracefully** | 任何模型失败，系统仍可运行——降级链覆盖所有关键路径 |

---

## 二、Project Lifecycle

```
Idea
  │
  ▼
RFC ──→（任何架构级变更必须先写RFC，组会讨论通过）
  │
  ▼
Architecture ──→（更新 docs/architecture/）
  │
  ▼
Schema ──→（更新 schemas/，递增版本号）
  │
  ▼
Development ──→（在 feature 分支开发）
  │
  ▼
Review ──→（Owner自审 → Reviewer复审 → 陈家智架构Review）
  │
  ▼
Merge ──→（合并到 dev，通过CI检查）
  │
  ▼
Release ──→（dev → main，打Tag）
  │
  ▼
Feedback ──→（Sprint Review收集反馈，下一轮迭代）
```

---

## 三、Module Ownership & Review

| 模块 | Owner | Reviewer | 变更需通知 |
|------|-------|----------|-----------|
| Knowledge Architecture | 陈家智 | Medical Knowledge（待定） | 全员 |
| Mapping JSON | Medical Knowledge（待定） | 陈家智 | AI Engineering（钟睿宸） |
| Prompt Engine | AI Engineering（钟睿宸） | 陈家智 | Backend（蔡子鑫） |
| LangGraph Workflow | AI Engineering（钟睿宸） | 陈家智 | Backend（蔡子鑫） |
| FastAPI / Backend | Backend（蔡子鑫） | AI Engineering（钟睿宸） | Client（彭翔） |
| Agent Schema | 陈家智 | 全员 | 全员 |
| uni-app / Client | Client（彭翔） | Backend（蔡子鑫） | — |
| MySQL / Redis | Backend（蔡子鑫） | 陈家智 | AI Engineering（钟睿宸） |

**规则：** 任何 PR 必须经过 Reviewer 批准 + 陈家智架构 Review 后才能合并。Owner 负责实现，Reviewer 负责质量把关，陈家智负责架构一致性。

---

## 四、Definition of Done (DoD)

> 任何人说"完成了"，必须满足以下条件。

### Backend 接口

```
POST /assessment 完成标准
☐ Swagger /docs 自动生成 OpenAPI
☐ Postman 测试通过（HTTP 200）
☐ Response JSON 与 agent-schemas.md 100%一致
☐ 错误时返回统一错误码
☐ 单元测试通过（pytest）
☐ 日志写入 logs/api.log
```

### AI Agent 模块

```
Prompt Engine 完成标准
☐ 输入参数 → 输出完整Prompt（可验证）
☐ 模板版本号在 prompt/ 目录有对应文件
☐ 异常输入不崩溃（有默认fallback）
☐ 日志写入 logs/prompt.log
```

### Knowledge 模块

```
Mapping JSON 完成标准
☐ 每条映射有 source 字段标注文献出处
☐ 每条映射有 confidence_level 字段
☐ JSON 通过 schema 校验
☐ 版本号在 knowledge/ 目录有对应标记
```

### Client 页面

```
播放页 完成标准
☐ 与 Figma 原型一致
☐ 三个主流机型测试通过（iOS/Android/PC模拟器）
☐ 加载态 / 空状态 / 错误态 三种状态覆盖
☐ 与 Backend 接口联调通过
```

---

## 五、Risk Management

### 风险登记表

| ID | 风险 | 影响 | 概率 | 应对策略 |
|----|------|------|------|----------|
| RISK-001 | 天工SkyMusic API不可用 | 高 | 中 | 自动降级：SkyMusic → MiniMax → FunMusic → 本地曲库 |
| RISK-002 | Qwen2.5-7B 推理失败 | 高 | 低 | 降级：Qwen本地 → 阿里云API → DeepSeek API → 规则引擎纯硬编码 |
| RISK-003 | OCR识别失败 | 中 | 中 | 降级：提示用户手动修改识别结果，跳过OCR继续流程 |
| RISK-004 | Chroma向量库损坏 | 高 | 低 | 定期备份 knowledge/ 目录，故障时回退到规则引擎（不查RAG） |
| RISK-005 | MySQL连接超时 | 中 | 中 | Redis缓存降级，关键数据本地SQLite兜底 |
| RISK-006 | 用户上传非医疗图片 | 低 | 高 | OCR返回空时，自动切换为问卷输入通道 |
| RISK-007 | LLM输出不合规医疗建议 | 高 | 低 | 所有输出带"仅供参考"声明 + 可信度<40%强制就医提醒 |
| RISK-008 | 团队成员进度落后 | 中 | 中 | 每日三句话同步 → 连续2天阻塞升级到陈家智 → Sprint Review砍非核心功能 |

---

## 六、Logging Strategy

### 日志分类

| 日志文件 | 记录内容 | 格式 |
|----------|----------|------|
| `logs/assessment.log` | 每次评估请求：input_channel、OCR耗时、术语映射命中率、LLM耗时 | JSONL |
| `logs/syndrome.log` | 每次辨证请求：情绪分数输入、证型输出、confidence_breakdown、RAG命中数 | JSONL |
| `logs/prescription.log` | 每次处方请求：调式权重、BPM、乐器选择、Prompt模板版本 | JSONL |
| `logs/generation.log` | 每次生成请求：平台、attempt_order、latency、cost、degradation_triggered | JSONL |
| `logs/feedback.log` | 每次反馈：评分、action决策、user_profile_update | JSONL |
| `logs/rag.log` | 每次RAG检索：query_text、n_results、命中文献ID列表、相似度分数 | JSONL |
| `logs/api.log` | 所有HTTP请求：method、path、status_code、latency、client_ip | JSONL |

### 日志规范
- 每条日志必含：`timestamp`（ISO 8601）、`agent_id`、`session_id`
- 敏感信息（用户姓名、手机号）不入日志
- 生产环境仅保留 INFO 及以上级别

---

## 七、Version Management

### 版本号规则（语义化版本 MAJOR.MINOR.PATCH）

| 变更类型 | 示例 | 版本变化 |
|----------|------|----------|
| Schema 新增必填字段 | 所有Agent输出新增 `version` 字段 | 2.0.0 |
| Schema 新增可选字段 | Agent③ 新增 `wearable` 字段 | 1.1.0 |
| Prompt 模板措辞调整 | "舒缓" 改为 "舒缓、清新" | 1.0.1 |

### 各组件版本追踪

```
prompt/
├── v1/    ← 当前版本
├── v2/    ← 未来迭代

knowledge/
├── v1/    ← 当前版本

schemas/
├── v1.0/  ← 当前版本
├── v1.1/  ← 未来迭代

docs/adr/
├── adr-0001-fastapi.md
├── adr-0002-langgraph.md
├── adr-0003-five-agents.md
├── adr-0004-knowledge-engine.md
```

---

## 八、Architecture Decision Records

| ADR | 决策 | 理由 | 备选方案 |
|-----|------|------|----------|
| ADR-0001 | 后端使用 FastAPI (Python) | 异步高性能、与LangGraph/LangChain生态兼容、Swagger自动生成 | Spring Boot（不兼容Python的AI生态） |
| ADR-0002 | Agent编排使用 LangGraph | Supervisor模式天然支持多Agent调度、条件边、状态持久化 | CrewAI（太高层不够灵活）、纯Python asyncio（缺少状态管理） |
| ADR-0003 | 采用五Agent而非单Agent | 职责分离——医学/知识映射/生成各自独立，可独立替换和调试 | 单Agent全包（黑箱、不可解释） |
| ADR-0004 | 核心映射使用规则引擎+LLM混合 | 硬编码保证核心正确性，LLM处理模糊推理 | 纯LLM（幻觉风险）、纯规则（太僵硬） |
| ADR-0005 | 七音→五音 不删除Fa/Si | 文献支持五声+六声+七声调式共存，正向约束优于负面禁止 | 强制删除（文献不支持、音乐僵硬） |
| ADR-0006 | 知识库分四层 | 经典+论文+经验+反馈，每层可信度不同，检索时可分层查询 | 单层混合（可信度无法区分） |
