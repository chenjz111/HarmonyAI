# Sprint 4 Frozen Contract 适配设计

## 目标

在不修改 Frozen Contract、不丢弃现有 Sprint 4 AI Understanding 成果的前提下，将当前实现适配到 `integration/sprint4-real-input` 的正式契约，并为 #53/#54 合并后的最终联调保留清晰边界。

## 约束

- 基线使用普通 merge，同步点保留在 `feat/s4-ai-understanding`。
- 保留现有 V2.0/V2.1 兼容入口；新增适配不改变旧调用方的基本返回结构。
- 不修改 `docs/sprint4/*-contract*.md`、`tests/contract/fixtures/*` 和 Frozen Contract 测试。
- 不把 `docs/superpowers/` 新增内容作为本任务交付物。
- 只提交 Sprint 4 相关实现、测试和本设计/计划文档；缓存与其他资料不进入提交。

## 设计

### Provider

`complete_json()` 与 `acomplete_json()` 共享请求构造、响应解析、JSON 修复、Schema 校验、重试决策和元数据生成，只在传输调用方式上分开。错误统一映射到 Frozen `ProviderErrorCode`，429/5xx/连接或读取超时按契约重试，其他 4xx 立即失败。普通日志只保留 request/session/agent、provider/model、prompt_version、延迟、Token、状态、错误码和重试次数，不写入任何用户文本或 Prompt。

### Evidence 与 Assessment

所有新证据归一化为 Frozen `EvidenceItem`，按 category 校验 `value` 联合类型。coverage 只计算当前场景适用关键信息的有效证据覆盖率；source diversity 独立返回来源数量和列表，不参与 coverage 乘法，也不能单独触发追问。questionnaire-only 完整输入允许 coverage 为 1.0。Follow-Up 使用确定性决策树，上限统一为 4；user correction 追加 `user_correction` 证据并产生不可覆盖的 Revision。

### Safety 与 Diagnosis

Q16 只记录身体信号；Q19 除 `never` 外全部进入自伤安全流程；Q20 任一紧急选项进入紧急身体安全流程，两个 `none` 选项分别执行互斥规则。安全结果不能继续 Diagnosis/Prescription/Music。Diagnosis 输出候选倾向及支持/反对证据；未确认、命中安全、重大冲突、覆盖不足或无证据候选时输出 `abstained`。

## 验证策略

先以 Frozen Contract 测试作为不可变基线，再为每个适配点新增失败测试并实现最小改动。完成后运行 Provider、Assessment、Questionnaire、Diagnosis、集成、Contract 和全量回归测试；#53/#54 合并前只验证 Mock/兼容路径，不伪造正式问卷或 OCR 数据。
