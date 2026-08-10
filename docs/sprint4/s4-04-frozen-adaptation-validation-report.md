# S4-04 Frozen Contract 适配阶段性验证报告

## 状态

阶段性适配已完成，分支为 `feat/s4-ai-understanding`，基线通过普通 merge 同步至 `integration/sprint4-real-input@4bffaa4`。Frozen Contract 文件和 Contract fixtures 未修改。

## 已完成

- Provider 同步 `complete_json()` 与异步 `acomplete_json()` 共享 JSON repair、Schema validation、重试和错误分类。
- 支持 Frozen `ProviderErrorCode`，429/5xx/连接或读取超时按最多两次重试处理。
- 支持 Markdown JSON、外围文本和可恢复截断修复。
- Provider 日志字段仅保留安全元数据，不保留用户原文、Prompt、OCR 文本或截断内容。
- 支持 Frozen 20 题问卷 ID，同时保留原 V2.1 兼容 ID。
- Q04 仅定性记录，Q10 反向计分，Q15 保留方向和严重度结构。
- Q16 身体信号只作为 Evidence，`none` 互斥。
- Q19 非 `never`、Q20 任一紧急选项进入安全阻断。
- Evidence coverage 与 source diversity 分离；完整 questionnaire-only coverage 可为 1.0。
- Follow-Up 输出上限为 4。
- user correction 产生 `user_correction` Evidence 和递增 Revision。
- Diagnosis 在未确认、安全、重大冲突或覆盖不足时 abstain。

## 验证结果

```text
Frozen Contract / AI / API / Integration: 381 passed
Full test suite: 450 passed, 1 warning
```

唯一 warning 来自 FastAPI/Starlette 测试客户端的依赖弃用提示，不影响测试结果。

## 联调边界

正式问卷 JSON、评分 JSON、60 个评估案例和安全案例等待 #53；真实 OCR、Provider health、数据库迁移和 API 扩展等待 #54。两项合并后需要重新同步 integration 分支，替换内置兼容问卷定义，运行正式评估集，并完成端到端 API 联调。
