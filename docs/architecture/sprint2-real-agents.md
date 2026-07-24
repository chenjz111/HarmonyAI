# Sprint 2 Real Agent Adapter Design

## Goal

将 Sprint 2 的五 Agent 从确定性 stub 推进到“可接入真实 Qwen、无配置可离线运行”的完整链路，同时保持既有 Agent Schema、LangGraph 路由和 Chroma 接口不变。

## Scope

本次覆盖 AI Engineering Lead 的四项未完成工作：

- Assessment：问卷 JSON 到结构化 `emotion_profile`；
- Diagnosis：规则映射、知识检索与可选 Qwen 结构化补充；
- Prescription：证型权重、Chroma 检索和 Prompt Engine 组装；
- Feedback：统一反馈存储协议与本地 SQLite 实现。

Generation 继续使用 Sprint 2 本地曲库占位输出；真实音频生成不在本 Sprint 范围内。

## Runtime Adapter

`QwenCompatibleProvider` 通过环境变量连接 OpenAI-compatible `/chat/completions` 接口：

```text
QWEN_BASE_URL
QWEN_API_KEY
QWEN_MODEL
```

未配置或请求失败时，Agent 使用明确的规则 fallback，并在结果中记录 `degradation_triggered` 和 warning。测试不访问外部网络，不保存 API Key。

## Data Flow

```text
questionnaire
  -> assessment_agent
  -> diagnosis_agent (rule mapping + Chroma + optional Qwen)
  -> prescription_agent (tone weights + Chroma + Prompt Engine)
  -> generation_stub
  -> feedback_agent -> FeedbackStore
```

所有节点继续返回统一 envelope：`agent_id`、`confidence`、`reason`、`warnings`、`input`、`output`、`timestamp` 等字段。

## Components

- `providers.py`：增加 JSON LLM 协议、Qwen-compatible HTTP provider 和规则 fallback；
- `real_agents.py`：Assessment、Diagnosis、Prescription、Feedback 的真实适配器；
- `real_workflow.py`：把真实 Agent 接入现有 LangGraph 状态流，保留低置信度安全分支；
- `feedback_store.py`：FeedbackStore 协议与 SQLite 实现；
- `*_demo.py`：四个可现场运行的离线/真实适配器 Demo；
- `tests/`：覆盖真实 provider 的请求解析、fallback、Agent 输出、Chroma 检索和 SQLite 持久化。

## Safety and Error Handling

- 没有问卷输入或模型输出无法解析时，Assessment 返回 `degraded`；
- 诊断置信度低于 `0.4` 时，不生成处方或音频，转专业人员复核；
- Qwen 输出只接受 JSON，拒绝无法解析或缺少必需字段的结果；
- 规则映射作为 Diagnosis 的安全底线，不允许模型凭空创建未登记证型；
- 所有知识检索结果保留来源、证据等级和距离信息；
- Feedback 写入失败时返回 warning，不阻塞用户播放结果。

## Verification

- 无环境变量时四个 Demo 可离线运行；
- 配置 fake OpenAI-compatible transport 时验证真实 JSON 解析；
- 全量测试验证旧 stub workflow 不回归；
- `python -m pytest -q` 和各 Demo 命令均通过；
- 不提交任何 API Key、个人数据或真实医疗诊断结论。
