# Sprint 5 Provider Upgrade Plan

## 原则与接口

Agent 只依赖 Provider Contract，不依赖具体厂商 SDK。运行时使用 `QWEN_BASE_URL`、`QWEN_API_KEY`、`QWEN_MODEL` 以及明确的 timeout/retry/quota/fallback policy。

`AssessmentProvider.complete_json(request) -> ProviderResponse`

`DiagnosisProvider.complete_json(request) -> ProviderResponse`

ProviderResponse 包含 provider、model、latency、token usage、attempts、status/error_code；业务输出必须通过版本化 Schema。普通日志禁止用户原文、Prompt、病例和凭据。

## 路由与 fallback

1. 首选 Cloud Qwen。
2. timeout、限流、网络、5xx 返回标准 ErrorCode。
3. 策略允许时切换 Local Qwen。
4. Local 也失败则显式降级到 questionnaire/规则路径，不伪装 AI 成功。
5. Safety、abstain、follow-up、confirmation 与后端处方权威不可被 fallback 绕过。

## 安全与成本

- Key 仅由部署环境注入。
- 只发送完成任务所需的最小数据。
- 记录 token、延迟、重试和费用估算，不记录原文。
- 设置并发、日配额、熔断和数据保留边界。

## PR 顺序

1. Contract/ADR；
2. Cloud adapter + contract tests；
3. Assessment wiring；
4. Diagnosis + RAG wiring；
5. health/cost/privacy；
6. 前端 Provider 状态；
7. integration acceptance。

## 验收

覆盖 Cloud success、timeout、401/403、429、5xx、invalid JSON；sync/async 一致；JSON repair 后仍 Schema validate；cloud → local → questionnaire/规则可复现；CI 无 Secret；固定小样本记录质量、错误率、延迟和成本，但不改变 Sprint 4 Formal 结果。
