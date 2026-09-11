# Agent4 TokenHub / MiniMax Music 真实 Provider — Smoke 说明（Sprint 5）

> 状态：**当前 Sprint 5 正式真实 Provider**
> **真实 Smoke：2026-09-11 SUCCESS**（HTTP 200 / Provider succeeded / 单次 POST / 重试 0 /
> 音频落盘 / Provider 时长与本地实测一致）——详见下文「Owner 真实 Smoke 结果」
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

## 音乐规则 ↔ Provider 最小兼容

### 乐器固定映射（规则资产公开中文值 → Provider 规范化 token）

| 规则资产（展示用，保持中文） | Provider token |
| --- | --- |
| 古琴 | `guqin` |
| 箫 | `xiao` |
| 琵琶 | `pipa` |
| 笛 | `dizi` |
| 埙 | `xun` |

- 中文名称继续用于五音解析页显示；**前端显示合同未改动**，请求/持久化仍保留原始中文值
  （E2E 断言 `music_assets.instruments_json == ["古琴","箫"]` 且读模型返回中文）。
- Provider prompt 只用规范化 token；**未映射乐器（如 唢呐/古筝/二胡）显式
  `GENERATION_INSTRUMENT_UNSUPPORTED` 失败**，绝不静默丢弃。

### 环境音「无额外环境音」

- `无额外环境音`（及 `无其他环境音/无环境音/无/none/no_extra_ambient` 等）不会被渲染成
  `soft 无额外环境音 ambience`；Provider prompt 直接**省略自然环境音段**。
- 若同时存在真实环境音（如 `water`），只渲染真实项，none 值被剔除。

### 时长真实性

- `GenerationSpec.duration_seconds` **只作为 prompt 中的目标时长**
  （prompt 文案：`target length about N seconds`）。
- **不向 TokenHub 发送任何 duration 字段**（JSON body 仅 `model/prompt/is_instrumental/
  output_format/audio_setting`；单测断言 body 无 `duration/seconds_total/length/duration_seconds`）。
- 成功后**以下载音频的实测时长**入库并供 Player 展示；Provider 返回的
  `extra_info.music_duration`(ms→s) 仅作对照元数据，**不直接当成本地实测值**。
- 探针（`backend/app/core/audio_duration.py`）兼容真实返回结构：
  - 跳过 ID3v2（含 footer 标记）；
  - **逐帧解析每个帧头**，不再假设所有帧长度与首帧相同（兼容 VBR）；
  - 优先使用 **Xing/Info** 或 **VBRI** 帧数（首帧常为 Xing 头帧，长度与数据帧不同）；
  - 声明的帧数与物理扫描不一致（>5%）时以扫描值为准；
  - **合理性护栏**：按体积/时长推算的平均码率必须落在 8–448 kbps，否则判为异常 →
    探针返回不可用 → 任务显式失败，**绝不把错误数值写入数据库**
    （旧实现把真实 75.89s 文件测成 ~0.052s → 入库 1s 的问题由此根治）。
- `300s` 仅为**项目内部上限**（`PROJECT_INTERNAL_MAX_DURATION_SECONDS`），
  **不是 Provider 已确认能力**，待真实 Smoke 记录后再更新。

## Provider 音频 URL 安全策略（Owner 加固）

`output_format=url` 返回的临时地址必须同时满足：

1. **仅 HTTPS**（`http://` 一律拒绝，不发起下载）；
2. **公共地址**：拒绝 `localhost`/`*.local`/`*.internal`、回环、私网、链路本地
   （如 `169.254.169.254`）、保留/组播地址及 IP 字面量私网；
3. **逐跳重定向校验**：下载禁用自动跟随（`allow_redirects=False`），每次跳转**先校验**
   目标仍是公共 HTTPS，再发起下一跳；**最大跳转 3 次**，超过即拒绝；
   跳转到 HTTP/localhost/私网/链路本地/保留地址一律拒绝且不发起该跳；
4. **最大体积上限** 25 MiB：流式下载累计超限立即拒绝（hex 响应同样受此上限约束）；
5. 下载完成后仍做 **MP3 校验**（ID3 / MPEG 同步字），并再次确认最终地址安全；
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

## Owner 真实 Smoke 结果（2026-09-11：SUCCESS）

| 项 | 结果 |
| --- | --- |
| Owner 执行日期 | 2026-09-11 |
| RESULT | **SUCCESS** |
| HTTP status | **200** |
| Provider | Tencent Cloud TokenHub |
| Model | `minimax-music-v3.0` |
| Provider status | **succeeded** |
| Generation POST count | **1**（自动重试 **0**） |
| Download calls | **1** |
| Audio returned | YES（MP3） |
| Audio size | 957,325 bytes |
| Provider `music_duration` | 238,994 ms = **238.994 s** |
| 本地 MP3 探针实测 | **238.99428571428572 s** |
| Provider 与本地实测 | **一致** |
| 自有音频资产落盘 | 成功 |
| Mock fallback | **未使用** |
| `source_type` | 预期 `generated`（Smoke 工具不查询 DB；E2E 测试已覆盖该字段） |
| `total_tokens` / 精确费用 | **UNKNOWN**（Provider 未返回 tokens，未做任何推测） |
| API Key | 未打印、未写入仓库 |

### 验证状态

- **成功响应兼容：PASS**（HTTP 200 / Provider succeeded / 单次 POST / 重试 0）
- **音频保存：PASS**（url 响应立即下载，1 次下载，落盘为自有 Audio Asset）
- **时长验证：PASS**（Provider 238.994 s 与本地探针 238.99428571… s 一致；两种来源互相印证）

### 时长真实性（不得声明精确时长控制）

- 本次请求的 `duration_seconds=60` **仅为 Prompt 目标时长**，不是 Provider 保证值；
- 实际生成约 **239 秒（≈4 分钟）**；
- TokenHub / MiniMax Music **不提供精确时长控制字段**，本 PR 不声称 Provider 支持按秒精确控制；
- 入库与 Player 展示始终使用**保存音频的本地实测时长**（Provider 的 238.994 s 仅作对照元数据）。

### Owner 人工试听结论（本次样本）

| 项 | 结论 |
| --- | --- |
| 无人声 | **PASS** |
| 古琴 | 明显 |
| 箫 | 较弱，但可辨识、不影响验收 |
| 整体氛围 | 舒缓，符合放松方向 |
| 明显噪声或异常 | 无 |
| 时长（≈4 分钟） | 可接受 |
| 人工试听结论 | **PASS** |

> 边界说明：该结论仅证明**本次样本**的音乐表现可接受，**不得**扩展为 Provider 每次都能稳定还原
> 相同乐器或效果；跨样本稳定性仍需后续样本累积验证。

## 验收清单

- [x] 单次真实生成成功；`POST count = 1`（自动重试 0），不重复计费。
- [x] 模型为 `minimax-music-v3.0`（精确匹配），Base URL 为官方主机。
- [x] 规则资产中文乐器（古琴/箫）本次 Smoke 走规范化路径并被 Provider 接受；未映射乐器显式失败（单测覆盖）。
- [x] `无额外环境音` 不出现在 prompt；有真实环境音时仅渲染真实项（单测覆盖）。
- [x] prompt 中时长为 target 表述；请求体无 duration 字段；入库/展示时长为文件实测（真实 Smoke 已验证实测维度）。
- [ ] `source_type=generated` + `provider=tokenhub/minimax-music-v3.0` 落库（E2E 测试已覆盖，真实链路 DB 查询待补）。
- [x] url 响应落盘为自有 MP3（真实 Smoke：`download calls = 1`）；hex 路径由单测覆盖。
- [x] url 非 HTTPS / 内网地址 / 超 25 MiB / 跳转到 HTTP 或内网 → 全部显式失败且不落盘（单测覆盖）。
- [x] `music_duration` 毫秒→秒转换正确（238,994 ms → 238.994 s）；入库时长为文件实测值。
- [x] `401/403、429、5xx、额度/参数类 base_resp、超时、空音频`均显式失败（单测覆盖）。
- [x] `matched_fallback` 仅来自本地审核曲库（`source_type=matched`），不冒充 generated（E2E 覆盖）。
- [x] Player 走受控 stream；DB/Player 不保存 Provider 临时 URL。
- [ ] `total_tokens` / 精确费用记录（Provider 未返回 → UNKNOWN）。

## Remaining Blockers

1. **H5 / Android Player 真机播放验收**：尚未验证（需前端联调侧在真机通过受控
   `/api/v3/music/assets/{id}/stream` 播放本次生成的资产）。
2. **人工试听正式验收记录**：本次样本已 PASS（见上表），但仍需按验收流程留档，并累积更多样本后再下稳定性结论。
3. `usage.total_tokens` 与精确费用：**UNKNOWN**（Provider 未返回，不做推测）。
4. 真实链路 DB 抽查：确认真实 Smoke 产生 `source_type=generated` 且
   `provider=tokenhub/minimax-music-v3.0`（自动化 E2E 已覆盖，真实链路未查）。

## 已由真实 Smoke 关闭的确认项

1. ~~真实请求字段与 `minimax-music-v3.0` 模型在 TokenHub 侧的实际可用性~~ → **已确认可用（2026-09-11 SUCCESS）**。
2. 实际时长上限：当前项目内部上限 `max_duration_seconds=300`；本次实际生成 ≈239 s，
   **未探测到上限边界**，上限仍属项目内部约束（非 Provider 已确认能力）。
3. 五音/古琴等乐器还原度：本次样本古琴明显、箫较弱但可辨识（仅样本级结论）。

## 测试

```powershell
python -m pytest tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py -v
python -m pytest tests/api/v3/test_tokenhub_generation.py -v
```
