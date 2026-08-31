# Decision Record — Music Generation Provider

> **状态：** `PENDING_OWNER_APPROVAL`（待 Owner 批准后接线 `generation_provider_adapter.py`）
> **日期：** 2026-08-24
> **作者：** 蔡子鑫（Backend Platform Engineer）
> **决策者：** 陈家智（产品/集成）— 需批准
> **对比表：** [music-provider-comparison.md](music-provider-comparison.md)

---

## 背景

Agent 4 需要真实音乐生成，失败时明确退回本地审核曲库（`source_type=matched`，代码已就绪）。Provider 必须映射 `MusicGenerationProvider` Protocol（异步任务 + 进度 + 取消 + `MusicProviderCapabilities`），并满足五音/国风器乐（`GenerationSpec`：bpm、instruments、structure、duration）与商用授权。真实调用证据需要真实 Key，本记录不包含任何 Secret；「待真实 Key 验证」项需负责人提供 Key 后补脱敏调用记录。

## 决策建议

### Primary（Cloud）：阿里云百炼 Model Studio · 通义音乐（Qwen-Music / Fun-Music）

- 与既有 `QWEN_BASE_URL`（DashScope compatible-mode）生态一致，复用 Cloud Qwen 基础设施与降级链。
- 2026-07 Qwen-Music 发布，盲听评测超过多数商业产品；国风对齐潜力高（符合五音场景）。
- 付费调用商用授权明确；国内低延迟。
- **待真实 Key 验证**：任务式 API 形态（异步/同步）、进度/取消支持、五音/古琴 prompt 服从度、真实单价与延迟。

### Backup（Cloud）：MiniMax 海螺 Music 3.0

- 官方 API（`POST /v1/audio/generations`），独立于阿里生态，作第二来源。
- `instrumental=true` 纯器乐、100+ 乐器库、`audio_duration` 10–300s、`format` 支持 mp3；免版税商用；约 $0.002/生成秒。
- **待真实 Key 验证**：异步任务形态、分段/进度支持、古琴等中国乐器实际效果、国内 API 区域访问与结算。

### Local（可选自托管）：Stable Audio 3.0 开源权重（small/medium）

- 云不可用时的「本地可切换」路径；器乐强、无 vocals。
- 小/中权重开源可自托管（fal.ai 或自有推理），符合云→本地降级哲学。
- **待验证**：古琴/五音 prompt 服从度、无 GPU 环境下的时长。

### Fallback（内置，已有代码）：本地审核曲库匹配 `matched`

- `build_matched_fallback_task` + `ProviderTaskTransitionGuard` 已就绪；任何 provider 失败/未配置 → `source_type=matched` 显式降级，不伪装生成成功。

## 环境变量映射（沿用 `build_music_provider_bundle`）

```bash
MUSIC_PROVIDER=qwen_music            # 或 minimax_music
MUSIC_PROVIDER_BASE_URL=<OpenAI 兼容或厂商端点>
MUSIC_PROVIDER_API_KEY=<仅部署环境注入，不提交仓库>
MUSIC_PROVIDER_MODEL=<模型名>
```

> 建议：两个候选都优先走 OpenAI 兼容端点（DashScope compatible-mode / MiniMax OpenAI 兼容），适配器按 Protocol 收敛为单一 `MusicGenerationProvider` 实现，切换仅改配置。

## 明确不做

- **Suno / Udio**：无官方开发者 API（仅第三方聚合器），版权诉讼未定，不入选。
- 不在 Agent 内硬编码任何厂商 URL/Key；`ai_call_log`/普通日志只记 spec-sha256 + provider/model/latency/error_code（复用 `build_safe_music_provider_log_fields`），不落 spec 值/资产 locator。

## 验收清单（接线后，需真实 Key）

- [ ] 真实生成成功一次（音频可播放、时长/格式符合 spec）
- [ ] 五音·古琴示例谱：宫/商/角/徵/羽各至少 1 例，记录 prompt 服从度
- [ ] timeout / 限流 / 5xx / 无音频 / 格式错误 → 明确 `failed` + 本地 `matched` 降级
- [ ] 重复 idempotency key 不重复扣费
- [ ] 取消、进度轮询、终态不可逆
- [ ] 无 GPU 环境可降级到本地曲库；健康检查不返回 Secret/locator
- [ ] 成本/延迟抽样记录（脱敏）

## 决策影响

- 影响 `generation_provider_adapter.py` 的接线（当前 `NotConfiguredMusicProvider` + `TODO(owner)`）。
- 不改变冻结的 `schemas/v3/music.py` 与 `MusicGenerationProvider` Protocol。
- 变更只发生在 provider 适配器层，前端/Player 契约不变。
