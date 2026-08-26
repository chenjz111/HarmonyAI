# HarmonyAI Sprint 5 Manual Gates

> 状态：`PREPARATION_IN_PROGRESS`
>
> 当前基线：`origin/integration/sprint4-real-input@cef9d2660beb1f9ab6a6f677718d4854aa548288`

> 上述为原证据基线；2026-08-26按 [Owner Flow Amendment 001](../contracts/harmonyai-v3-owner-flow-amendment-001.md) 更新待验收流程。修订基线4a22b5f，合同PR待审核，所有新增人工场景尚未执行。

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
我有近期就诊资料 → 必填上传 → OCR成功 → AI摘要 → 必填确认/修改摘要
→ 可选最近情况 → 可选10题问卷 → Agent1综合评估 → 唯一最终确认
→ Diagnosis → Prescription → Music → Feedback
```

验收重点：描述与问卷都跳过仍可继续；无重复最终确认、无音乐目标；摘要四操作齐全，通俗文本修改后事实也更新，保存即确认。前端不显示内部enum/coverage/provider；有效输入按当前合同有后端音乐出口，不把Safety未执行称为“安全”。

### H5-02 无病例普通路径

```text
我没有近期就诊资料 → 可选文字/语音（可跳过） → 必填10题五脏问卷
→ Agent1综合评估 → 唯一最终确认 → Diagnosis → Prescription → Music → Feedback
```

验收重点：完全不填写描述也能完成；语音失败可转文字或跳过；10题来自approved manifest且必填，不补假Understanding；最新已确认Assessment revision进入Diagnosis。

### H5-03 降级矩阵

- OCR失败：不进摘要/Agent1；显示“资料暂未识别成功”，可重传或“改用描述与问卷”；清楚提示描述选填/10题必填。
- 摘要不准/无法确认：四操作可用；修改失败保留输入；弃用后旧资料、旧摘要、迟到回调不参与当前分析。
- 有资料选填问卷：可整份跳过；部分草稿不作为有效submission。
- ASR失败：可编辑文字/跳过，不假转写成功。
- Cloud Qwen失败：Local成功时明确 degraded。
- Cloud/Local失败：只保留确定性Fact；不足则failed/abstain，不造事实。
- RAG失败：审核规则足够才degraded，否则abstain。
- Diagnosis abstain且输入有效、满足当前policy的其他门禁：后端可返回保守音乐，不把not_run当clear。
- Music Provider失败：仅在策略允许且存在审核资产时 `matched_fallback`。
- 无审核曲目：`NO_PLAYABLE_ASSET`，不得伪装生成成功。

### H5-04 版本隔离与Safety兼容

- 新v3-owner-flow-1不含Q19/Q20或独立Safety检测/核验/支持分流，不以其作为普通继续条件。
- 新policy记录deferred_v3/not_run/null，不显示“安全通过”，也不将null误判为风险阻断全部音乐。
- 单独验证旧Sprint4/V3：原Q19/Q20、needs_verification、confirmed mental/acute门禁保持；普通确认、弃用资料、Feedback不能清除风险。
- 旧风险会话不能换版本降级，客户端不能注入policy；未知合同报错，不能静默提交旧目标Schema。
- 新V3专用Safety本身记DEFERRED/NOT_RUN；兼容测试PASS不代表新版Safety已实现。

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
8. OCR失败分流、摘要修改/弃用、来源版本恢复；原Safety外部帮助动作仅在独立旧版兼容场景验证；
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
