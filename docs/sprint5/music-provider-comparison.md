# Music Provider 选型对比（Music Generation Provider）

> **状态：** 调研稿（供 Owner 决策）
> **日期：** 2026-08-24
> **作者：** 蔡子鑫（Backend Platform Engineer）
> **上游依赖：** `backend/ai_engine/v3/music_provider.py`（`MusicGenerationProvider` Protocol）、`backend/ai_engine/v3/generation_provider_adapter.py`（`build_music_provider_bundle`，待接线）

---

## 一、需求锚点（以代码接口为准）

Music Generation Provider 必须映射到已冻结的 `MusicGenerationProvider` Protocol：

- `create_task / get_task / cancel_task / health / capabilities`
- `MusicProviderCapabilities`：`max_duration_seconds`、`supports_progress`、`supports_cancel`、`supported_instruments`、`supported_formats`（`mp3|wav|m4a`）
- `ProviderTask`：`queued|running|succeeded|failed|cancelled`、`progress_value`(0–100)、`asset_locator`、稳定 `error_code`
- `GenerationSpec`：`bpm`(40–120)、`duration_seconds`、`instruments[]`、`ambient_sounds[]`、`structure`(intro/main/outro)、`energy_curve`、`forbidden_constraints[]`

因此候选能力按以下维度打分：**结构化控制（五音·古琴等中国乐器）｜异步任务+进度+取消｜时长(10–300s 量级)｜mp3｜商用授权｜国内可用/成本｜隐私**。

## 二、候选对比

> 注：标注「待验证」的项表示需要真实 Key 调用官方文档/API 后确认（本项目不持有任何 Secret）。价格与授权信息来自 2026-08 公开资料，正式预算以厂商控制台/商务报价为准。

| 候选 | 官方 API | 异步+进度+取消 | 中国乐器/五音 | 时长 | 格式 | 商用授权 | 国内可用/成本 | 隐私/数据 |
|---|---|---|---|---|---|---|---|---|
| **阿里云百炼·通义音乐**（Model Studio Fun-Music / Qwen-Music） | ✅（Model Studio 通道） | 待验证 | 国风强（五音对齐潜力高） | 待验证 | mp3 等（待验证） | ✅ 付费调用商用 | ✅ 国内；与 Qwen 同通道低成本 | 结构化 spec，无患者原文 |
| **MiniMax 海螺 Music 3.0** | ✅ `POST /v1/audio/generations` | 待验证 | 100+ 乐器库、`instrumental=true` | 10–300s | wav/flac/mp3 | ✅ 免版税商用 | ✅ 国内；约 $0.002/生成秒 | 结构化 spec |
| **Stable Audio 3.0**（Stability AI） | ✅（Stability / fal.ai） | ✅ async + 进度 | 器乐强；国风/古琴需实测 | ≤ 6:20 | mp3 等 | ✅ 订阅商用 | ⚠️ 国际网络/支付；订阅 $11.99+/月 或 ~$0.5/首 | 中；小/中权重开源可自托管 |
| **Suno AI** | ❌ 无官方开发者 API（仅第三方聚合器） | — | 有国风；以 vocals 见长，器乐较弱 | 4–8+ min | mp3 | ⚠️ 订阅 tier 绑定；训练诉讼未定（Sony 案预计 2026 中裁决） | ⚠️ 仅聚合器；~$0.055–0.55/首 | 中 |
| **Udio** | ❌ 无官方 API | — | 中 | 2–6+ min | — | ⚠️ 绑定 | ⚠️ 仅聚合器；~$0.03–0.12/次 | 中 |
| **ElevenLabs Music** | ✅ | 待验证 | 弱 | ≤2 min 为主 | mp3 等 | ✅ 商用含 | ⚠️ 国际；$0.26–2.55/首（较贵） | 中 |
| **Mureka** | ✅（官方套餐） | 待验证 | 中 | — | — | ✅ 商用含 | ✅ 国内；$8–24/月 | 中 |
| **AIVA** | ⚠️ 订阅为主，API 不确定 | — | 古典/配乐强 | 短 | — | ⚠️ Pro 档才全版权 | ✅ 国内；$15+/月 | 中 |

## 三、与现有架构的契合度

1. **通义音乐（Qwen-Music）**：2026-07 由 Qwen 团队发布，盲听评测超过 MiniMax Music 2.6、Mureka V8、Suno V5，与 Suno V5.5 持平。与既有 `QWEN_BASE_URL`（DashScope compatible-mode）生态一致，Cloud Qwen 基础设施可复用；结构化 spec 输入不携带患者原文。
2. **MiniMax Music 3.0**：官方 API、纯器乐参数、免版税商用、按生成秒计费，独立于阿里生态，适合作第二来源。
3. **Stable Audio**：唯一同时具备「官方 API + 开源权重」的主流器乐方案，符合「云/本地可切换」哲学；小/中权重可自托管，云不可用时降级。

## 四、排除项说明

- **Suno / Udio**：无官方开发者 API，程序化访问只能走第三方聚合器（存在账号合规与版权转移风险）；训练版权诉讼尚未尘埃落定。不列为 Primary/Backup。
- **AIVA**：以订阅制为主、API 形态不确定、全版权授权仅在 Pro 档，不适合任务式集成。

## 五、结论

候选按「结构化控制 + 官方 API + 商用授权 + 国内可用 + 成本」排序：**通义音乐（阿里云百炼）≈ MiniMax Music 3.0 > Stable Audio > Mureka > ElevenLabs Music > 其余**。最终选择见 `provider-decision-record-music.md`。

## 六、资料来源（公开文档，非项目内部）

- [AI Music Generator Comparison 2026: Suno vs Udio vs Stable Audio](https://www.songaifarm.com/blog/ai-music-generator-comparison-2026-suno-vs-udio-vs-stable-audio-414)
- [Best AI Music Generation APIs 2026 – Apiframe](https://apiframe.ai/blog/best-ai-music-generation-apis)
- [AI Music API Pricing in 2026: What You Pay – Apiframe](https://apiframe.ai/blog/ai-music-api-pricing-2026)
- [Stable Audio vs Suno Pricing | Costbench](https://costbench.com/compare/stable-audio-vs-suno/)
- [MiniMax Music 3.0 API: Pricing, Playground & Docs | EmpirioLabs AI](https://empiriolabs.ai/models/minimax-music3)
- [MiniMax Music 2.6 Pricing: Is It Free for Commercial Use? (2026)](https://www.nemovideo.com/blog/minimax-music-2-6-pricing-free)
- [2026年10大最佳AI音乐生成模型：功能、优缺点、定价及更多](https://modelhunter.ai/zh-CN/blog/best-ai-music-generation-models-2026)
- [阿里巴巴Qwen团队打造AI音乐创作神器](https://cj.sina.cn/article/norm_detail?url=http%3A%2F%2Ffinance.sina.com.cn%2Fstock%2Ft%2F2026-07-29%2Fdoc-iniknmif1636575.shtml&from=redirect&autocallup=no&isfromsina=no)
- [Alibaba Cloud Model Studio Error codes（Fun-Music）](https://www.alibabacloud.com/help/en/model-studio/error-code)
