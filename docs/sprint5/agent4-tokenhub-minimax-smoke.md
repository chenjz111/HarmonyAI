# Agent4 TokenHub / MiniMax Music 真实 Provider — Smoke 说明（Sprint 5）

> 状态：**当前 Sprint 5 正式真实 Provider**
> 分支/PR：`feat/s5-v3.1-agent4-minimax` → PR #120（Draft，不 Merge）
> Provider：Tencent Cloud TokenHub / MiniMax
> Endpoint：`POST https://tokenhub.tencentmaas.com/v1/wand/minimax-music/generation`
> Model：`minimax-music-v3.0`
> Key：`TOKENHUB_API_KEY`（只从环境变量读取）

## 目标链路

```
GenerationSpec → TokenHub JSON POST（model/prompt/is_instrumental=true/output_format=url/audio_setting.mp3）
→ 单次 POST（自动重试 0）
→ data.audio：hex → 解码保存 MP3；url → 立即下载保存（禁止长期依赖临时 URL）
→ 自有 Audio Asset（source_type=generated）+ 实测 duration
→ Player 通过受控 /api/v3/music/assets/{id}/stream 读取
```

## Owner 配置（全部只走环境变量）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `MUSIC_PROVIDER` | 是 | 固定 `tokenhub` |
| `TOKENHUB_API_KEY` | 是 | TokenHub API Key（禁止入代码/日志/Issue/DB/Git） |
| `TOKENHUB_BASE_URL` | 否 | 默认 `https://tokenhub.tencentmaas.com` |
| `TOKENHUB_MUSIC_MODEL` | 否 | 默认 `minimax-music-v3.0`（需 `minimax-music-*`） |
| `HARMONY_MEDIA_ROOT` | 否 | 音频落盘根目录，默认 `media` |

历史/未启用（保留代码，不启用）：`MUSIC_PROVIDER=stability`（Stability Stable Audio 2.5）、
`MUSIC_PROVIDER=minimax`（直连 `https://api.minimax.io/v1/music_generation`，
`BLOCKED_BY_PROVIDER_ENTITLEMENT`，禁止调用；adapter 内置硬性拒绝）。

## 请求与解析契约

- 请求体：`application/json`，字段 `model` / `prompt` / `is_instrumental=true` /
  `output_format=url`（hex 响应同样正确处理）/ `audio_setting.format=mp3`。
- **模型必须精确等于 `minimax-music-v3.0`**（不使用前缀匹配；`minimax-music-v3.1` 等一律 readiness fail）。
- **Base URL 白名单**：只允许 `https://tokenhub.tencentmaas.com`；其它值（含 `http://` 变体、
  `api.minimax.io`、任意第三方域名）在构造/构建阶段即 `PROVIDER_NOT_CONFIGURED`，
  防止 `TOKENHUB_API_KEY` 被发送到其他服务器。
- 解析：`HTTP 状态`、`base_resp.status_code`、`base_resp.status_msg`（仅用于判定，
  不写入日志/错误，避免回显密钥）、`data.status`（1=进行中→显式失败；2=完成）、
  `data.audio`、`trace_id`、`request_id`、`usage.total_tokens`、`extra_info.music_duration`。
- `extra_info.music_duration` 为**毫秒**；适配器按 `ms / 1000` 转为秒记入运行元数据
  （入库的 `music_assets.duration_seconds` 仍取保存文件的实测值）。

## Provider 音频 URL 安全策略（Owner 加固）

`output_format=url` 返回的临时地址必须同时满足：

1. **仅 HTTPS**（`http://` 一律拒绝，不发起下载）；
2. **公共地址**：拒绝 `localhost`/`*.local`/`*.internal`、回环、私网、链路本地
   （如 `169.254.169.254`）、保留/组播地址及 IP 字面量私网；
3. **最大体积上限** 25 MiB：流式下载累计超限立即拒绝（hex 响应同样受此上限约束）；
4. **最终跳转地址再校验**：下载后的 `final_url` 必须仍是公共 HTTPS，防止异常重定向到
   HTTP 或内部地址；
5. 下载完成后仍做 **MP3 校验**（ID3 / MPEG 同步字）；
6. 无论 hex 还是 url，最终只把**自有落盘路径**写入资产；Provider 临时 URL
   不进入数据库、任务响应、日志或 Player。

`output_format=hex`：十六进制解码 + 体积/MP3 校验后落盘。

## Smoke

### 预检（不发请求，安全）

```powershell
$env:PYTHONPATH="."
$env:MUSIC_PROVIDER="tokenhub"
$env:TOKENHUB_MUSIC_MODEL="minimax-music-v3.0"
$env:TOKENHUB_API_KEY="<真实 Key>"
python tools/tokenhub_music_smoke.py --check
# [SMOKE][CHECK] readiness=READY
```

### 真实生成（Owner 只跑一次，避免重复计费）

```powershell
cd <repo>
$env:PYTHONPATH="."
$env:MUSIC_PROVIDER="tokenhub"
$env:TOKENHUB_BASE_URL="https://tokenhub.tencentmaas.com"
$env:TOKENHUB_MUSIC_MODEL="minimax-music-v3.0"
$env:TOKENHUB_API_KEY="<真实 Key>"
$env:HARMONY_MEDIA_ROOT="media"
python tools/tokenhub_music_smoke.py
# 期望 [SMOKE][DIAG] http_status=200 content_type=application/json ...
#      [SMOKE][OK] status=succeeded provider=tokenhub label=tokenhub/minimax-music-v3.0
#      [SMOKE][OK] trace_id=... request_id=... total_tokens=...
#      [SMOKE][OK] owned asset=...\generated\tokenhub\*.mp3
#      [SMOKE][OK] measured_duration_seconds=...
#      [SMOKE][OK] provider_reported music_duration_ms=... -> seconds=...
#      [SMOKE][OK] POST count = 1 (automatic retry = 0), download calls = 0|1
```

失败时输出安全诊断：`[SMOKE][DIAG] http_status=<精确码> content_type=.. response_bytes=..
response_is_json=.. transport_error=<异常类型>`；不打印 Key、请求体、Provider 响应正文。

退出码：`0` 成功；`2` 配置缺失（readiness）；`3` Provider 真实失败；`4` 脚本错误。

## 验收清单

- [ ] 单次真实生成成功；`POST count = 1`（自动重试 0），不重复计费。
- [ ] 模型为 `minimax-music-v3.0`（精确匹配），Base URL 为官方主机。
- [ ] `source_type=generated` + `provider=tokenhub/minimax-music-v3.0` 落库。
- [ ] hex 与 url 两种响应都能落盘为自有 MP3（url 场景 `download calls = 1`）。
- [ ] url 非 HTTPS / 内网地址 / 超 25 MiB / 跳转到 HTTP 或内网 → 全部显式失败且不落盘。
- [ ] `music_duration` 毫秒→秒转换正确；入库时长为文件实测值。
- [ ] `401/403、429、5xx、额度/参数类 base_resp、超时、空音频`均显式失败。
- [ ] `matched_fallback` 仅来自本地审核曲库（`source_type=matched`），不冒充 generated。
- [ ] Player 走受控 stream；DB/Player 不保存 Provider 临时 URL。
- [ ] 记录 trace_id / request_id / total_tokens / 延迟 / 费用；不记录 Secret。

## 仍需 Owner 确认

1. 真实请求字段与 `minimax-music-v3.0` 模型在 TokenHub 侧的实际可用性（首次真实生成验证）。
2. 实际时长上限（当前 `max_duration_seconds=300`，超出即显式失败）。
3. `usage.total_tokens` 的计费口径与实际费用；单次生成成本记录。
4. 五音/古琴等乐器还原度。

## 测试

```powershell
python -m pytest tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py -v
python -m pytest tests/api/v3/test_tokenhub_generation.py -v
```
