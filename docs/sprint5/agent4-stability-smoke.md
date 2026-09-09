# Agent4 Stability AI 真实音乐生成 — Smoke 说明（Sprint 5）

> 状态：**OWNER_APPROVED_FOR_SPRINT5_REAL_MODE**（Owner Smoke：HTTP 200，audio/mpeg，
> 请求 60s → 实际 ≈61.582s，自动重试 0 次）
> 分支：`feat/s5-v3.1-agent4-minimax`（PR #120，Draft，不 Merge）
> Provider：Stability AI · Model：`stable-audio-2.5`
> Endpoint：`POST https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio`

## 目标链路

```
GenerationSpec → Stability multipart POST（text_prompt/seconds_total/output_format=mp3）
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
# 期望 [SMOKE][OK] status=succeeded ... owned asset=...\generated\stability\*.mp3
#      [SMOKE][OK] measured_duration_seconds=61 ...
#      [SMOKE][OK] POST count = 1 (automatic retry = 0)
```

退出码：`0` 成功；`2` 配置缺失（readiness）；`3` Provider 真实失败；`4` 脚本错误。

## Smoke 验收清单

- [ ] 真实生成一次：`text_prompt`/`seconds_total` 字段名与 Owner 已验证请求一致，
      返回 `audio/mpeg`、可播放。
- [ ] 音频落入自有存储（`generated/stability/*.mp3`），Player 不读临时 URL。
- [ ] `measured_duration_seconds` 与文件实测一致（≈61.582s 场景应显示 62）。
- [ ] `401/403、429、5xx、余额/权限、超时、空音频`均明确失败；POST 次数 = 1。
- [ ] `generated`（真实生成）与 `matched_fallback`（审核曲库）在 API/DB 不混淆。
- [ ] 记录真实延迟/费用；不记录 Secret。

## 已知待 Owner 确认

1. 真实请求的 multipart 字段名：当前实现采用官方文档字段
   `text_prompt` / `seconds_total` / `output_format`；若平台对 Owner 账号返回
   需要其他别名（如 `duration`/`prompt`），只需在 smoke 中快速比对并修正 adapter
   常量（单点修改）。
2. 时长上限：Stable Audio 2.5 官方范围 1–190s（当前
   `STABILITY_MAX_DURATION_SECONDS=190`）；若 Agent3 默认时长超过 190s，需要在
   Owner 确认后调整 GenerationSpec 时长或决定上限（Adapter 对 >190s 请求显式失败，
   不会伪造）。
3. 五音/古琴等乐器还原度（prompt 自由文本表达，不做白名单断言）。

## 测试

```powershell
python -m pytest tests/ai_engine/v3/test_stability_music_provider.py -v
python -m pytest tests/api/v3/test_stability_generation.py -v
python -m pytest tests/ai_engine/v3/test_audio_duration.py -v
```
