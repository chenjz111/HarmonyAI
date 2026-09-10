# Agent4 Stability AI 真实音乐生成 — Smoke 说明（Sprint 5）

> 状态：**OWNER_APPROVED_FOR_SPRINT5_REAL_MODE**（Owner Smoke：HTTP 200，audio/mpeg，
> 请求 60s → 实际 ≈61.582s，自动重试 0 次）
> 分支：`feat/s5-v3.1-agent4-minimax`（PR #120，Draft，不 Merge）
> Provider：Stability AI · Model：`stable-audio-2.5`
> Endpoint：`POST https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio`

## 目标链路

```
GenerationSpec → Stability multipart POST（model/prompt/duration/steps/cfg_scale，官方字段）
→ audio/mpeg 二进制（自动重试 0 次）
→ 校验 Content-Type 与 mp3 magic 后写入自有 HARMONY_MEDIA_ROOT/generated/stability/*.mp3
→ 实际时长从保存文件读取（非请求时长）
→ Player 通过受控 /api/v3/music/assets/{id}/stream 读取
```

## Owner 配置（全部只走环境变量）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `MUSIC_PROVIDER` | 是 | 固定 `stability` |
| `STABILITY_API_KEY` | 是 | Stability AI API Key（禁止入代码/日志/Issue） |
| `MUSIC_PROVIDER_MODEL` | 否 | 默认 `stable-audio-2.5`（仅支持该模型） |
| `MUSIC_PROVIDER_BASE_URL` | 否 | 默认 `https://api.stability.ai` |
| `HARMONY_MEDIA_ROOT` | 否 | 音频落盘根目录，默认 `media` |

MiniMax 已标记 `BLOCKED_BY_PROVIDER_ENTITLEMENT`（HTTP 410/2153），不启用；其
adapter 保留为历史参考。

## Provider 级真实 Smoke

### 预检（不发任何请求，充值前可安全运行）

```powershell
$env:PYTHONPATH="."
$env:MUSIC_PROVIDER="stability"
$env:MUSIC_PROVIDER_MODEL="stable-audio-2.5"
$env:STABILITY_API_KEY="<真实 Key>"
python tools/stability_music_smoke.py --check
# [SMOKE][CHECK] no POST will be sent (readiness pre-flight only)
# [SMOKE][CHECK] readiness=READY
```

### 真实生成（仅当 Owner 确认余额已充值后运行）

```powershell
# PowerShell（Windows Owner 机）
cd <repo>
$env:PYTHONPATH="."
$env:MUSIC_PROVIDER="stability"
$env:MUSIC_PROVIDER_MODEL="stable-audio-2.5"
$env:MUSIC_PROVIDER_BASE_URL="https://api.stability.ai"
$env:STABILITY_API_KEY="<真实 Key>"
$env:HARMONY_MEDIA_ROOT="media"
python tools/stability_music_smoke.py
# 期望 [SMOKE][DIAG] http_status=200 content_type=audio/mpeg ...
#      [SMOKE][OK] status=succeeded ... owned asset=...\generated\stability\*.mp3
#      [SMOKE][OK] measured_duration_seconds≈62
#      [SMOKE][OK] POST count = 1 (automatic retry = 0)
```

失败时同样输出安全诊断：
`[SMOKE][DIAG] http_status=<精确码> content_type=<..> response_bytes=<..> response_is_json=<..> transport_error=<异常类型>`
（不打印 Key、不打印请求体、不打印 Provider 响应正文）。

退出码：`0` 成功；`2` 配置缺失（readiness）；`3` Provider 真实失败；`4` 脚本错误。

### Owner 真实 Smoke 结果（2026-09-10，同步记录于 PR #120）

| 项 | 结果 |
| --- | --- |
| `STABILITY_API_KEY` | 有效 |
| 余额查询 | HTTP 200，账户余额 5 credits |
| 真实 Generation POST 次数 | 1（自动重试 0）✅ |
| Provider 返回 | `GENERATION_PROVIDER_REJECTED`（未返回音频、未扣费、未切 Mock）✅ 失败处理路径正确 |
| 原始 HTTP 状态 | 当时被适配器隐藏 → **不能正式认定为 HTTP 402**（仅推测余额不足） |
| 成功响应 | ❌ 尚未真实验证 |
| 音频保存 / 实测 duration | ❌ 尚未真实验证 |
| Android/H5 Player 真实播放 | ❌ 尚未验证 |
| 单次 60s 生成所需 credits | **UNKNOWN**（官方文档/账单未提供可确认的单次额度口径） |

> 下次真实 Smoke 直接读取 `[SMOKE][DIAG] http_status=...`，即可把“推测余额不足”
> 升级为可归档结论。等待 Owner 充值并明确通知后再执行，之前不再发送真实 POST。

## Smoke 验收清单

- [ ] 真实生成一次：multipart 字段 `model/prompt/duration/steps/cfg_scale`（与 Owner
      已验证成功请求一致），返回 `audio/mpeg`、可播放。
- [ ] 音频落入自有存储（`generated/stability/*.mp3`），Player 不读临时 URL。
- [ ] `measured_duration_seconds` 与文件实测一致（≈61.582s 场景应显示 62）；
      实测失败时任务显式失败，绝不把请求时长当实际时长。
- [ ] `401/403、429、5xx、余额/权限、超时、空音频`均明确失败；POST 次数 = 1。
- [ ] `generated`（真实生成）与 `matched_fallback`（审核曲库）在 API/DB 不混淆。
- [ ] 记录真实延迟/费用；不记录 Secret。

## 已知待 Owner 确认

1. 真实 Smoke 复跑确认字段名与官方 Schema 一致
   （`model/prompt/duration/steps/cfg_scale`；seed 当前省略取随机，如要复现再补
   `seed`，改动在 adapter 常量单点位置）。
2. 时长上限：Stable Audio 2.5 官方范围 1–190s（当前
   `STABILITY_MAX_DURATION_SECONDS=190`）；若 Agent3 默认时长超过 190s，需要在
   Owner 确认后调整 GenerationSpec 时长或决定上限（Adapter 对 >190s 请求显式失败，
   不会伪造）。
3. 五音/古琴等乐器还原度（prompt 自由文本表达，不做白名单断言）。

## 测试

```powershell
python -m pytest tests/ai_engine/v3/test_stability_music_provider.py -v
python -m pytest tests/api/v3/test_stability_generation.py -v
python -m pytest tests/tools/test_stability_smoke_diagnostics.py -v
python -m pytest tests/ai_engine/v3/test_audio_duration.py -v
```
