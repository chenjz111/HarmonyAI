# HarmonyAI Sprint 5 Manual Gates

> 状态：`PREPARATION_IN_PROGRESS`
>
> 当前基线：`origin/integration/sprint4-real-input@cef9d2660beb1f9ab6a6f677718d4854aa548288`

本文件定义 Sprint 5 最终人工验收证据。任何项目只有实际操作并记录环境、步骤和结果后才能从 `PENDING` 改为 `PASS`。自动化测试、Schema 通过或 Sprint 4 的历史结果不能替代 Sprint 5 人工验收。

## 1. 当前状态

| Manual Gate | 当前状态 | 说明 |
|---|---|---|
| Desktop H5 V3 normal flow | NOT_READY | V3前端与Five-Agent workflow尚未完成 |
| Desktop H5 V3 degradation | NOT_READY | 需真实验证OCR/ASR/Qwen/RAG/Music Provider降级 |
| Android V3 full flow | MANUAL_ANDROID_TEST_PENDING | 必须真机执行，不得由H5或单元测试推断 |
| V3 live MySQL | MANUAL_MYSQL_V3_PENDING | Sprint 4 MySQL曾PASS；V3后续业务表和事务尚未完成 |
| V3 OCR redacted material | MANUAL_OCR_V3_PENDING | 必须使用脱敏的真实支持格式材料 |
| Cloud Qwen V3 | PROVIDER_NOT_CONFIGURED | 当前只有Provider基础，未启用production医学链路 |
| Local Qwen V3 fallback | NOT_READY | 需approved Claim/Knowledge资产与完整业务编排 |
| Real Music Generation Provider | PROVIDER_NOT_CONFIGURED | 未选择/配置厂商adapter，不得写AI实时生成已完成 |
| Reviewed local music fallback | AUTOMATED_ONLY | 状态与隐私边界有自动化测试；V3端到端人工播放未执行 |
| Feedback preference closed loop | NOT_READY | Feedback持久化到下一次Prescription读取尚未实现 |

## 2. 通用证据格式

每次人工验收必须记录：

- integration完整Commit SHA；
- 日期、操作系统、浏览器或真机型号；
- Backend/Frontend版本与安全的Provider配置状态；
- 测试步骤、实际结果、截图或日志引用；
- Console/Network错误；
- 是否使用真实Provider或明确fallback；
- 执行人；
- `PASS | FAIL | BLOCKED`；
- 失败时的 Issue/PR 链接。

禁止记录：API Key、数据库密码、完整Token、病例原文、OCR/ASR原文、完整Prompt、Provider原始异常、用户自由反馈原文或本机绝对隐私路径。

## 3. Desktop H5 场景

### H5-01 有病例普通路径

```text
有近期病例 → 上传 → OCR → AI病例摘要 → 用户确认/修正
→ 可选最近事情/五脏问卷 → 综合状态 → 唯一最终确认
→ Assessment → Diagnosis → Prescription → Music → Feedback
```

验收重点：无重复确认；材料失败可跳过；前端不显示内部enum/coverage/provider；正常安全用户有音乐出口。

### H5-02 无病例普通路径

```text
无近期病例 → 文字或语音表达 → 10题五脏问卷
→ 综合状态 → 唯一最终确认 → Five-Agent → Music → Feedback
```

验收重点：语音失败可改文字；问卷来自approved manifest；用户修正后的最新revision进入Diagnosis。

### H5-03 降级矩阵

- OCR失败：文字/问卷继续，不假成功。
- ASR失败：可编辑文字/跳过，不假转写成功。
- Cloud Qwen失败：Local成功时明确 degraded。
- Cloud/Local失败：只保留确定性Fact；不足则failed/abstain，不造事实。
- RAG失败：审核规则足够才degraded，否则abstain。
- Diagnosis abstain且安全、信息充分：后端可返回保守音乐。
- Music Provider失败：仅在策略允许且存在审核资产时 `matched_fallback`。
- 无审核曲目：`NO_PLAYABLE_ASSET`，不得伪装生成成功。

### H5-04 Safety

- V3不在普通问卷呈现V2 Q19/Q20。
- 病例/OCR、Narrative、ASR中的确定性风险信号先于普通Assessment。
- `needs_verification`进入专用核验；普通确认不能清除Safety。
- confirmed mental/acute risk不得进入个性化音乐，可进入Safety Support/安抚音频双轨。
- `past_resolved`只有经专用resolution后才能回普通轨。

### H5-05 Feedback闭环

- 必填变化可单独提交；其他反馈保持选填。
- 收藏、历史、偏好只属于当前用户。
- 达到合同最小样本前只收集不应用。
- 达到阈值后下一次Prescription引用新的immutable Preference Version。
- 个性化只能调整非医学音乐参数，不能改变五行五音固定映射。

## 4. Android Gate

必须在 HBuilderX 构建的真实 Android 设备完成：

1. guest bootstrap与token恢复；
2. 图片/PDF选择与上传权限；
3. 录音权限、ASR失败转文字；
4. 10题问卷、返回/恢复、唯一确认；
5. 生成进度轮询、后台/前台切换；
6. 音频播放、暂停、耳机/扬声器；
7. Feedback、收藏、历史和个人页；
8. Safety Support外部帮助动作；
9. 小屏、键盘遮挡、长文本、网络断开恢复。

当前必须保持：`MANUAL_ANDROID_TEST_PENDING`。

## 5. Provider 与数据 Gate

### Cloud / Local Qwen

顺序：health → 单来源smoke → schema/claim/span/time-window → fallback → 隐私日志。必须使用approved Claim/Knowledge版本；未批准时不得用测试fixture冒充production通过。

### Real Music Provider

顺序：health/capabilities → create → poll → cancel → success asset materialization → controlled stream → provider failure/local match → no asset failure。必须验证私有provider task ID、asset locator和原始错误不下发。

### OCR

至少覆盖JPG、PNG、PDF分页、无文字、低置信度、加密PDF、超大小/页数、错误MIME和失败降级。材料必须脱敏。

### MySQL V3

在隔离数据库验证 migration checksum/idempotency、Auth ownership、Revision事务、Generation Task/Asset、Feedback两阶段事务、Preference optimistic concurrency、删除/清理。凭据只存在本机环境变量。

## 6. Final Sign-off

只有下列条件全部满足后，Owner 才能签署 Sprint 5：

- #77～#80 的必要实现已进入 integration；
- V3 Contract/AI/API/Integration测试与一次最终Full全部通过；
- 全部Frontend测试与H5 build通过；
- Desktop H5必测场景通过；
- Android/OCR/MySQL/Qwen/Music Provider按实际范围标记PASS或由Owner明确接受为发布前PENDING；
- 无敏感信息、原始Provider错误或内部医学字段泄漏；
- acceptance report记录精确HEAD、数量、限制和rollback point。

当前结论：`NOT_READY_FOR_FINAL_SIGN_OFF`。
