# Agent4 MiniMax 真实音乐生成 — Smoke 说明（Sprint 5）

> **状态：历史参考 / 未启用。** Owner Smoke 显示 MiniMax 账号
> `HTTP 410 / provider code 2153` → `BLOCKED_BY_PROVIDER_ENTITLEMENT`
> （新用户无 Music API 权限）。Sprint 5 真实 Provider 已切换为
> **Stability AI Stable Audio 2.5**，见 `agent4-stability-smoke.md`。
> 本文档与 `tools/minimax_music_smoke.py` 仅作为 MiniMax 适配器（保留代码）的历史说明，不要作为 Sprint 5 接入目标运行。
> 分支：`feat/s5-v3.1-agent4-minimax`（PR #120，Draft）

## 目标链路

```
GenerationSpec → MiniMax Music API (POST /v1/music_generation)
→ 真实生成成功 → 音频写入自有 HARMONY_MEDIA_ROOT（owned Audio Asset）
→ Player 通过受控 /api/v3/music/assets/{id}/stream 读取
```

## Owner 需要提供的配置（全部只走环境变量）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `MUSIC_PROVIDER` | 是 | 固定 `minimax` |
| `MUSIC_PROVIDER_API_KEY` | 是 | MiniMax API Key（平台控制台获取） |
| `MUSIC_PROVIDER_MODEL` | 是 | 建议 `music-3.0`（Smoke 后由 Owner 记录确切 snapshot） |
| `MUSIC_PROVIDER_BASE_URL` | 否 | 默认 `https://api.minimax.io` |
| `HARMONY_MEDIA_ROOT` | 否 | 音频落盘根目录，默认 `media` |

缺少 `API Key`/模型或配置不完整时保持 `not_configured`（readiness fail），
绝不伪装成功、绝不静默切 Mock。

## Provider 级真实 Smoke

```powershell
# PowerShell（Windows Owner 机）
cd <repo>
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt pytest
$env:PYTHONPATH="."
$env:MUSIC_PROVIDER="minimax"
$env:MUSIC_PROVIDER_API_KEY="<真实 Key>"
$env:MUSIC_PROVIDER_MODEL="music-3.0"
$env:MUSIC_PROVIDER_BASE_URL="https://api.minimax.io"
$env:HARMONY_MEDIA_ROOT="media"
.\.venv\Scripts\python tools\minimax_music_smoke.py
# 期望输出 [SMOKE][OK] status=succeeded ... owned asset=...
```

```bash
# macOS / Linux / CI 主机
export PYTHONPATH=. MUSIC_PROVIDER=minimax \
  MUSIC_PROVIDER_API_KEY=<真实 Key> MUSIC_PROVIDER_MODEL=music-3.0 \
  MUSIC_PROVIDER_BASE_URL=https://api.minimax.io HARMONY_MEDIA_ROOT=media
python tools/minimax_music_smoke.py
```

退出码：`0` 成功；`2` 配置缺失（readiness）；`3` Provider 真实失败；`4` 脚本错误。

## Smoke 验收清单（来自 Decision Record）

- [ ] 记录 MiniMax model snapshot / endpoint / region。
- [ ] 真实生成一次，验证返回格式、时长与可播放性。
- [ ] 音频落入自有 Asset Storage（`generated/minimax/*.mp3`），Player 不读临时 URL。
- [ ] `401/403、429、5xx、空音频、格式错误`均明确失败（不能伪装成功）。
- [ ] `source_type=generated`（真实生成）与 `matched_fallback`（审核曲库）在
      API/DB/日志中不混淆。
- [ ] 记录真实延迟与费用；不记录 Secret。

## 已知待真实确认（REAL_SMOKE_REQUIRED）

1. MiniMax Music 3.0 实际输出时长范围（当前保守声明 `max_duration_seconds=300`）。
2. 官方文档当前仅提供同步 `POST /v1/music_generation`，无音乐任务查询/取消端点；
   若真实响应出现 `status=1`（in-progress）且无轮询句柄，adapter 会明确失败而
   不伪造成功；若 Smoke 发现可轮询的任务句柄，再接入轮询并更新能力声明
   （`supports_progress/supports_cancel`）。
3. 五音/古琴等乐器在真实生成中的还原度（capability 白名单仅供参考，
   MiniMax 通过 prompt 自由文本表达乐器）。

## 测试

```powershell
.\.venv\Scripts\python -m pytest tests/ai_engine/v3/test_minimax_music_provider.py -v
.\.venv\Scripts\python -m pytest tests/api/v3/test_minimax_generation.py -v
.\.venv\Scripts\python -m pytest tests/ai_engine/v3/test_music_provider.py tests/ai_engine/v3/test_generation_adapter.py tests/api/v3/test_generation.py -v
```
