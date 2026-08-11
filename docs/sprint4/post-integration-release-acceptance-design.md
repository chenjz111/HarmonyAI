# HarmonyAI Sprint 4 收尾验收与发布设计

> **日期**：2026-08-11  
> **状态**：APPROVED DESIGN  
> **适用分支**：`integration/sprint4-real-input`  
> **前置条件**：S4-02、S4-03、S4-04 已合并，Questionnaire、Assessment、Provider 与 Evaluation Contract 均为 FROZEN

## 1. 目标

Sprint 4 后续工作不再扩展业务功能，集中完成真实输入验收、发布门禁和可审计报告。验收必须证明：

1. 20 题正式问卷、评分规则和 60 个案例均能被当前实现消费；
2. 问卷、自由文本和文档输入能够形成可追溯 Evidence；
3. Assessment、用户确认/修订、Diagnosis 和 Safety 按 Frozen Contract 工作；
4. Qwen、PaddleOCR 或数据库异常时系统明确降级，不伪造成功；
5. 自动化测试、真实服务联调和人工业务验收形成统一发布结论。

## 2. 范围与非目标

### 2.1 本阶段范围

- Contract 与正式数据资产一致性检查；
- 60 个正式案例的预测生成和冻结指标计算；
- Qwen、PaddleOCR、数据库的真实服务健康检查与降级验证；
- 十项端到端业务场景验收；
- 前端状态、证据、修订与降级提示验证；
- 生成 JSON 和 Markdown 两种发布报告；
- 形成 P0/P1 发布门禁结论。

### 2.2 非目标

- 不修改 Frozen Contract；
- 不新增问卷题目、评分维度或临床阈值；
- 不引入新的 AI Provider；
- 不扩展音乐生成或推荐算法；
- 不将评估脚本嵌入生产请求路径；
- 不把 Mock 结果作为真实服务通过证据。

## 3. 总体方案

采用四层门禁式收尾：

1. **Gate 1 — Contract 与资产门禁**：验证 Frozen Schema、20 题问卷、评分规则、55 个普通案例和 5 个安全案例。
2. **Gate 2 — 离线与 CI 门禁**：执行单元测试、集成测试、Contract Tests、前端契约测试和 H5 构建。
3. **Gate 3 — 真实服务门禁**：验证 Qwen、PaddleOCR、数据库及其明确降级路径。
4. **Gate 4 — 业务验收门禁**：执行十项端到端场景，汇总 P0/P1 并生成发布报告。

任一门禁出现 P0 失败时停止发布判定；P1 必须修复，或在报告中记录负责人、原因和明确截止日期。

## 4. 架构与组件

### 4.1 Contract Validator

负责验证：

- `questionnaire_v2.1` 恰好包含 20 个唯一题目；
- Q04 为不计分的定性 Evidence；
- Q10 正向题采用反向计分；
- Q15 保存 `direction + severity`；
- Q16 多选互斥规则有效；
- Q19/Q20 只进入 Safety，不参与评分；
- Follow-Up 最大数量为 4；
- Evidence coverage 与 source diversity 分离；
- EvidenceItem value 仅接受 Frozen Contract 中的合法形状；
- 所有 JSON/JSONL 资产可解析且版本匹配。

该组件只读 Contract 和资产，不修改生产数据。

### 4.2 Prediction Generator

文件建议：`evals/sprint4/generate_predictions.py`。

职责：

- 逐行读取 `evals/sprint4/cases.jsonl` 和 `safety-cases.jsonl`；
- 通过现有公开业务接口执行问卷评分、文本提取、OCR、Assessment 和 Diagnosis；
- 为每个案例生成标准化 `predicted`；
- 将运行结果写入独立输出目录，不改写原始标注集；
- 保存 case ID、处理状态、Evidence 引用、候选倾向、弃权状态、安全结果、错误码和耗时；
- 不保存 Provider 密钥或普通日志禁止记录的用户原文。

默认运行离线 Provider；显式传入真实服务配置时才执行真实 Qwen/OCR。

### 4.3 Release Validator

文件建议：`evals/sprint4/validate_release.py`。

职责：

- 读取 Prediction Generator 输出；
- 调用现有 `evals.metrics` 计算冻结指标；
- 对照 `docs/sprint4/evaluation-plan.md` 判断 P0/P1；
- 输出 `passed`、`blocked` 或 `degraded`；
- 列出失败案例、失败指标、对应门禁和建议责任模块。

该组件不得通过降低阈值、忽略安全案例或跳过失败案例改变验收结论。

### 4.4 Acceptance Orchestrator

文件建议：`evals/sprint4/run_acceptance.py`。

职责：

- 依次执行四个 Gate；
- 为每个命令记录退出码、开始时间、结束时间和摘要；
- 聚合自动测试、真实服务和人工验收结果；
- 输出机器可读 JSON 和汇报用 Markdown；
- 在 P0 失败时返回非零退出码，供 GitHub Actions 阻塞合并或发布。

## 5. 数据流

端到端数据流保持现有生产边界：

```text
问卷 / 自由文本 / 文档
  → Input Processing（Qwen / OCR / 明确降级）
  → EvidenceItem
  → Assessment（coverage 与 source diversity 分离）
  → 用户确认或修订
  → Diagnosis（允许 abstained）
  → Safety Gate
  → 音乐流程或安全阻断
  → 验收报告
```

评估代码只能调用生产模块公开接口，不直接拼装内部结果，不绕过 Safety、用户确认或 Revision。

## 6. 降级与错误处理

| 故障 | 必须行为 | 禁止行为 | 发布影响 |
|---|---|---|---|
| Qwen 超时/失败 | 返回 `processing_status=unavailable`，保留问卷证据 | 伪造文本分析结果 | 降级路径通过则不阻塞 |
| PaddleOCR 不可用 | 返回 `ocr_status=degraded`，提示确认或补录 | 返回假 OCR 文本 | 降级路径通过则不阻塞 |
| 数据库失败 | 停止持久化流程，返回脱敏错误码 | 用内存结果伪装持久化成功 | P0 阻塞 |
| Schema 无效 | JSON repair 后再次校验，仍失败则返回明确错误码 | 接受未知字段或错误类型 | P0 阻塞 |
| 证据不足 | `Diagnosis.abstained=true`，最多 4 个追问 | 生成无依据诊断 | P0 阻塞 |
| Q19/Q20 命中 | 立即进入安全流程 | 继续评分、诊断或音乐推荐 | P0 阻塞 |
| 日志包含用户原文 | 立即判定隐私失败 | 仅以“调试需要”为由保留 | P0 阻塞 |

普通日志仅允许记录请求 ID、状态、耗时、错误码、Provider 名称和数量统计。

## 7. 发布门禁

### 7.1 P0 必须全部通过

- Safety Recall = 100%；
- Schema Pass Rate = 100%；
- 普通日志用户原文泄漏率 = 0%；
- 原有回归测试失败数 = 0；
- 数据库迁移与持久化关键路径成功；
- 用户修订可追溯；
- Evidence 引用能够回到合法 source reference；
- 降级状态不得伪装成功。

### 7.2 P1 处理规则

P1 失败默认阻塞发布。确需延期时，发布报告必须同时包含：

- 失败指标和案例；
- 影响范围；
- 临时缓解措施；
- 唯一责任人；
- 明确完成日期。

### 7.3 发布状态

- `passed`：所有 P0/P1 通过；
- `degraded`：真实 Provider 不可用，但规定的降级路径和全部 P0/P1 通过；
- `blocked`：任一 P0 失败，或 P1 未修复且没有完整延期记录。

## 8. 十项验收场景

1. 完整问卷单来源可形成充分证据，不因 source diversity 为 1 自动追问。
2. 自由文本与问卷共同生成可追溯 Evidence、Assessment 和候选倾向。
3. 文档经过 OCR 与用户确认后进入 Assessment。
4. 三来源输入合并后 coverage 与 source diversity 分别计算。
5. 来源冲突生成 Conflict，并只追问必要信息。
6. 信息不足时 Diagnosis 弃权，Follow-Up 数量不超过 4。
7. 用户修订后重新生成 Assessment，并保存 Revision 历史。
8. Q19 非 `never` 的风险答案进入安全流程。
9. Q20 紧急身体状态进入安全流程。
10. Qwen/OCR 不可用时明确降级，日志不包含用户原文。

每个场景必须记录输入类别、预期状态、实际状态、关键 Evidence ID、错误码、是否通过和证据截图或日志摘要。验收记录不得包含完整用户原文。

## 9. 测试策略

### 9.1 单元测试

- Questionnaire scoring、reverse scoring 和安全题旁路；
- JSON repair、Schema validation、retry、timeout 和 ErrorCode；
- Evidence coverage、source diversity、Conflict 和 Follow-Up；
- Diagnosis abstained 与 Revision；
- 日志字段白名单。

### 9.2 集成测试

- Questionnaire → Assessment；
- Narrative → Evidence → Assessment；
- OCR → Confirmation → Assessment；
- Assessment Revision → Diagnosis；
- Safety → Block；
- Provider unavailable → Degraded。

### 9.3 案例评估

- 55 个普通案例全部生成 `predicted`；
- 5 个安全案例全部生成安全结果；
- 不允许用缺少 `predicted` 的原始标注集直接宣称指标达标；
- 失败案例保留最小可复现上下文和脱敏 Evidence 引用。

### 9.4 前端与构建

- 前端 Frozen Contract 测试；
- 自由文本处理状态显示；
- Evidence 来源查看；
- 用户确认和修订；
- Provider 降级提示；
- H5 生产构建。

## 10. 报告格式

每次验收输出：

- `artifacts/sprint4/acceptance-report.json`：供 CI 和自动汇总读取；
- `artifacts/sprint4/acceptance-report.md`：供团队 Review 和汇报使用。

报告包含：

- Git commit、分支和执行环境；
- 20 题问卷、评分规则和 60 案例资产摘要；
- 四个 Gate 的状态；
- P0/P1 指标；
- 失败案例与责任模块；
- Qwen、OCR、数据库健康状态；
- 降级路径验证结果；
- 十项验收场景结果；
- 最终发布状态与剩余风险。

报告目录属于运行产物，默认不提交真实输入内容；只提交脱敏模板或经团队确认的汇总结果。

## 11. 执行顺序

1. 补齐 Contract Validator 和资产一致性测试；
2. 实现 Prediction Generator，生成 60 案例预测；
3. 实现 Release Validator 并锁定 P0/P1 判定；
4. 实现 Acceptance Orchestrator；
5. 补齐真实 Qwen/OCR/数据库健康检查和降级测试；
6. 补齐前端状态、Evidence、修订和降级展示验证；
7. 执行十项场景与人工复核；
8. 生成发布报告并完成 Review。

## 12. 完成定义

满足以下条件才可宣布 Sprint 4 收尾完成：

- 四个 Gate 均有可审计结果；
- 60 个案例全部执行，不存在静默跳过；
- 所有 P0 通过；
- 所有 P1 通过，或具备完整延期记录；
- 本地与 GitHub CI 均通过；
- 十项验收场景完成签署；
- 发布报告明确给出 `passed` 或合规的 `degraded`，不得以口头结论替代。
