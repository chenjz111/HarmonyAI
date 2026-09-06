# Decision Record — Music Generation Provider

> **状态：** `TEACHER-APPROVED PROVIDER DIRECTION — REAL VALIDATION PENDING`
> **更新日期：** 2026-09-06
> **决策者：** 陈家智（Owner）；老师已确认技术方向
> **冻结基线：** `83fe2f42069e126dbbfdccc252266964a58ce895`

## 决策

HarmonyAI Sprint 5 V3.1 的音乐生成技术方向确定为：

`GenerationSpec → MiniMax Music API → real provider response → owned Audio Asset → Player-readable asset`

MiniMax 的具体 music model snapshot/version、API endpoint、region、timeout/retry、rate limit 和成本/免费额度，在获得真实账号配置并完成 Smoke Test 后由 Owner 记录。上述工程参数不需要老师再次确认；只有更换 Provider 时才重新发起 Provider Direction 审核。

## 状态语义

真实生成成功：

`source_type = generated`

使用本地审核曲库降级：

`source_type = matched_fallback`

两种状态必须在持久化、Read Model、日志和验收证据中保持区分。Fallback 不得冒充真实 AI 生成成功。

## Real Mode 规则

- 缺少 MiniMax Key、endpoint/model 配置不完整、Provider 健康检查失败或真实调用失败时，返回 readiness failure 或明确 provider failure。
- 禁止在 Real Mode 中静默切换到 Mock。
- 只有存在已审核且可播放的本地资产并满足降级策略时，才允许 `matched_fallback`；否则返回明确的无可播放资产错误。
- Provider 返回的音频数据或临时地址必须在有效期内写入项目自有 Asset Storage，保存 `asset_id` 后再供 Player 使用。
- Key 只通过部署 Secret/环境变量注入，不进入仓库、前端包、普通日志、Issue 或截图。

## 现有接口边界

继续复用冻结的 `MusicGenerationProvider` Protocol 和 `generation_provider_adapter.py` 接入点。Adapter 必须根据 MiniMax 真实 API 能力声明进度、取消、格式和时长支持，不能为了适配现有协议伪造 Provider 状态。

## Smoke Test 门禁

- [ ] 确定并记录 MiniMax model snapshot/version、endpoint 和 region。
- [ ] 真实生成一次并验证返回格式、时长与可播放性。
- [ ] Provider response 成功落入自有 Audio Asset Storage。
- [ ] Player 使用项目资产而非临时 Provider locator。
- [ ] timeout、401/403、429、5xx、空音频和格式错误均明确失败。
- [ ] 重复 idempotency key 不重复生成/扣费。
- [ ] `generated` 与 `matched_fallback` 在 API、数据库和前端状态中不混淆。
- [ ] 记录真实延迟、调用成本和免费额度，不记录 Secret。

## 明确不批准

- 未经正式决策更换为其他 Music Provider。
- 通过非官方聚合器接入。
- 用本地曲目、Mock task 或假 URL 作为真实生成证据。
- 把临时 Provider URL 当作永久播放器地址。
