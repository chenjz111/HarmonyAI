# Sprint 5 Music Generation Plan

## 目标链路

后端权威 Prescription
→ MusicGenerationRequest
→ MusicGenerationProvider
→ 异步任务
→ 音频资产
→ Music Agent 响应
→ Player
→ Feedback

生成失败时显式返回 error/degraded，再退回本地曲库 `matched`，不中断产品。

## Contract 草案

MusicGenerationRequest：request/session/prescription ID、mode、bpm、duration、instruments、ambient、structure、forbidden constraints、idempotency key。

MusicGenerationResponse：task_id/status、provider/model、source_type（`generated` / `matched`）、audio_url、duration/format、latency/cost、error_code/fallback_reason。

Agent 不包含第三方 URL、Key 或厂商专有调用逻辑。

## 数据、安全与边界

- 任务状态：queued/running/succeeded/failed/cancelled。
- 音频资产记录 owner/hash/format/duration/expiry；短时受控访问。
- idempotency key 防止重复收费。
- Safety blocked、Diagnosis abstained、Needs follow-up、Prescription missing 时不得生成。
- 失败不可伪装成功；fallback 必须标记 `source_type=matched`。
- Feedback 只更新个人偏好，不修改全局医学规则。

## PR 顺序与验收

1. Contract/provider interface；
2. Mock 与任务状态测试；
3. 首个真实 Provider adapter；
4. migration/cache/callback；
5. Music Agent + local fallback；
6. Player 状态；
7. 端到端、成本、隐私验收。

验收要求：真实生成成功一次；timeout/限流/失败/无音频/格式错误明确降级；fallback 可播放；重复请求不重复收费；前端不自造 Prescription；音频可删除且不可越权；自动测试和 Android/H5 真实播放通过。
