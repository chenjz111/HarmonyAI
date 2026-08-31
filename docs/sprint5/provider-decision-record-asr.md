# Decision Record — ASR / 语音转写 Provider

> **状态：** `PENDING_OWNER_APPROVAL`（待 Owner 批准；批准后定义 ASR Provider Protocol 并接线）
> **日期：** 2026-08-24
> **作者：** 蔡子鑫（Backend Platform Engineer）
> **决策者：** 陈家智（产品/集成）— 需批准
> **对比表：** [asr-provider-comparison.md](asr-provider-comparison.md)

---

## 背景

V3 理解支持 `voice_transcript` 源（with_document 输入路径），ASR Provider 把用户语音转成 `VoiceTranscript`（含毫秒级 `segments[]`、`language`、`degradation`），进入资料摘要确认流程。语音是**生物识别 PII**，隐私与降级语义是核心。真实调用证据需要真实 Key，本记录不包含任何 Secret。

## 决策建议

### Primary（Cloud，默认）：阿里云 智能语音交互（实时语音转写）

- 中文 WER 3.73%（声网实测最优）、延迟 458ms 最低、¥0.228/小时（前 100h/月免费）成本最低。
- 与项目 Qwen/DashScope 生态一致；支持分段时间戳。
- **待真实 Key 验证**：实际业务语音（五音场景话术）WER、分段边界质量、真实计费口径。

### Backup（Cloud）：腾讯云 语音识别

- 独立第二来源（WER 4.97%、¥3.2/小时），避免单一云厂商依赖。

### Local（隐私优先 / 断网降级）：Qwen3-ASR-0.6B（推荐）或 faster-whisper large-v3

- 部署为本地 OpenAI 兼容 `/v1/audio/transcriptions` 服务，客户端切 `api_url` 即切换，与「云/本地可切换」哲学一致。
- Qwen3-ASR 中文≈large-v3 且**保留方言**（粤语 CER 14.2% vs Whisper 28.6%），与 Qwen 生态一致；faster-whisper 需约 10GB 显存（large-v3）。
- 语音数据不出内网，隐私最稳；无 GPU 时成本与吞吐受限于硬件。

### Fallback（内置）：音频不可用 → 显式 `failed`/`degraded`

- 遵循 OCR 先例：识别失败不返回假文本，返回明确状态并引导用户改用文字 narrative；`VoiceTranscript.status=failed`，理解源 `processing_status` 相应标记，不进入 confirmed ref。

## 接口形态建议（批准后定义，不冻结 schema）

```python
class ASRProvider(Protocol):
    def transcribe(self, request: ProviderASRRequest) -> ASRTranscript: ...
    def health(self) -> ProviderHealth: ...
```

- `ProviderASRRequest`：audio_ref（受控访问的音频 locator）、language_hint、采样要求（16kHz 单声道 PCM）。
- `ASRTranscript` → 映射到冻结 `VoiceTranscript`（transcript_id、audio_id、revision=1、language、text、segments、degradation）。
- 错误码：`ASR_PROVIDER_NOT_CONFIGURED` / `ASR_TIMEOUT` / `ASR_RATE_LIMITED` / `ASR_FAILED`；失败 → `failed` 不伪装。
- 日志红线：只记 `audio_hash`(sha256) + 时长 + language + latency + error_code，不落音频原文/文本。

## 环境变量映射（沿用 Secret 只从环境读取的既定模式）

```bash
ASR_PROVIDER=aliyun_speech      # 或 tencent_asr / local_qwen3_asr
ASR_PROVIDER_APP_KEY=<仅部署环境注入，不提交仓库>
ASR_PROVIDER_BASE_URL=<本地 OpenAI 兼容端点或厂商端点>
```

## 明确不做

- 不用真实用户音频做评测样本（安全约束）；评测用合成/公开授权样本，记录脱敏结果。
- 不做说话人分离（diarization），不在本期范围。
- 不在 Agent 内硬编码厂商 SDK；统一走 ASR Provider Protocol + 环境配置。

## 验收清单（接线后，需真实 Key / 或本地模型）

- [ ] 中文普通话样例转写成功，输出含毫秒分段、language、text
- [ ] 噪音/方言样例 → 记录 WER，明确 degrade 与显式提示
- [ ] Cloud timeout / 限流 → 明确 `failed` + 引导文字输入，不伪装成功
- [ ] 本地 Qwen3-ASR / faster-whisper 切 URL 即可切换
- [ ] 日志无音频原文/文本；健康检查不返回 Secret
- [ ] 成本/延迟抽样记录（脱敏）

## 决策影响

- 新增 ASR Provider Protocol（不影响冻结的 V3 schema，属新增接口）。
- 理解服务 `_resolve_source` 在 `voice_transcript` 路径接入 ASR 结果；失败路径保持显式降级。
- 不影响 narrative / document / questionnaire 输入路径。
