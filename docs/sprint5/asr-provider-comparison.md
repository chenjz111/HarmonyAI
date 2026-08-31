# ASR / 语音转写 Provider 选型对比（Voice Transcript Provider）

> **状态：** 调研稿（供 Owner 决策）
> **日期：** 2026-08-24
> **作者：** 蔡子鑫（Backend Platform Engineer）
> **上游依赖：** V3 `voice_transcript` 理解源（`schemas/v3/understanding.py` 的 `VoiceTranscript`），`_WITH_DOCUMENT_TYPES` 输入路径

---

## 一、需求锚点（以冻结 Schema 为准）

`VoiceTranscript` 是 V3 理解源类型之一（`source_type=voice_transcript`），ASR Provider 负责把用户语音转成：

- `VoiceTranscript`：`transcript_id`、`audio_id`、`revision`(≥1)、`status`(`needs_confirmation|confirmed|failed`)、`language`、`text`、`segments[]`、`degradation`
- `VoiceTranscriptSegment`：`segment_id`、`start_ms`、`end_ms`、`text`（要求**毫秒级分段**）
- 结果进入理解 Agent（with_document 输入模式），最终以「需要确认」进入资料摘要 revision 流程

维度：**中文普通话 WER/准确率｜分段时间戳｜延迟｜成本｜国内可用｜隐私（语音=生物识别 PII）｜方言（P2）**。

## 二、候选对比

> 价格为 2026-06 公开核验口径（声网评测/厂商公开），不同产品形态（流式/一句话/长音频）计费口径不同，正式预算以控制台为准。

| 候选 | 类型 | 中文 WER（实时基准） | 毫秒分段 | 延迟 | 成本 | 国内可用 | 隐私/数据 |
|---|---|---|---|---|---|---|---|
| **阿里云 智能语音交互（实时语音转写）** | Cloud | 3.73% | ✅ | 458ms | ¥0.228/小时，前 100h/月免费 | ✅ | 数据出网（阿里云） |
| **腾讯云 语音识别** | Cloud | 4.97% | ✅ | 684ms | ¥3.2/小时，前 50h/月免费 | ✅ | 数据出网 |
| **讯飞 实时语音转写（大模型）** | Cloud | 4.67% | ✅ | 754ms | ¥4.95/小时，前 200h/月免费 | ✅ | 数据出网 |
| **火山引擎 流式识别** | Cloud | 4.58% | ✅ | 480ms | ¥3.5/小时 | ✅ | 数据出网 |
| **百度 短语音识别** | Cloud | 中文场景 ≥97% | ✅ | — | 资源包 | ✅ | 数据出网 |
| **Microsoft Azure Speech** | Cloud | 4.53% | ✅ | 1539ms | ~¥3/小时 | ⚠️ 国际 | 数据出网（微软） |
| **OpenAI Whisper API（cloud）** | Cloud | 中 | ✅（词级） | — | ~$0.006/分钟 | ⚠️ 国际 | 数据出网（OpenAI） |
| **faster-whisper large-v3（本地）** | Local 服务 | 安静 CER 3.3%（中文须 large-v3） | ✅（词级） | GPU RTF≈0.142 | 仅硬件（~10GB 显存） | 自托管 | **数据不出内网** |
| **Qwen3-ASR-0.6B（本地）** | Local 服务 | 中文≈large-v3，且**保留方言特征**（粤语 CER 14.2% vs Whisper 28.6%） | ✅ | A10 显存峰值 13.8GB，可百路并发 | 仅硬件 | 自托管 | **数据不出内网** |
| **SenseVoice（本地）** | Local 服务 | CJK 优化，处理速度优于 Whisper | ✅ | 快 | 仅硬件 | 自托管 | **数据不出内网** |

## 三、隐私是决定性维度

语音是**生物识别 PII**（声纹可关联身份），本项目安全约束明确「不用真实音频」。因此：

- Cloud ASR 需将音频发给厂商——只发送完成任务所需的最小数据，日志只记录 audio hash / 时长 / 语言 / 状态，不落原文。
- Local ASR（Qwen3-ASR / faster-whisper）可「数据不出内网」，隐私最稳，且断网可用。
- 无论哪种，ASR 失败都必须**显式降级**（`failed`/`degraded` + 引导用户改用文字 narrative），不伪装成功——这与 OCR「识别失败不返回假文本」先例一致。

## 四、方言（P2）

五音疗愈面向地域人群，方言（粤语等）是 P2 增强点：

- **Qwen3-ASR** 保留方言特征（粤语 CER 14.2%）优于 Whisper（28.6%），且与项目 Qwen 生态一致 → 若方言进入范围，本地首选 Qwen3-ASR。
- Cloud 方案中文方言覆盖较好（部分厂商 20+ 方言模型），但方言准确率需真实语音实测。

## 五、结论

按「中文准确率 + 分段能力 + 成本 + 国内可用 + 隐私」排序：

- **Cloud 首选：阿里云 智能语音交互**（WER 3.73% 最优、¥0.228/h 最低、延迟最低、与 Qwen 生态一致）。
- **Cloud Backup：腾讯云**（独立第二来源）。
- **Local 隐私/降级：Qwen3-ASR-0.6B**（推荐，方言保留 + Qwen 生态）或 **faster-whisper large-v3**（标准 OpenAI 兼容 `/v1/audio/transcriptions` 接口，切 URL 即切换）。
- **内置 Fallback：音频不可用 → 显式 failed/degraded + 引导文字输入**，不伪装成功。

最终选择见 `provider-decision-record-asr.md`。

## 六、资料来源（公开文档，非项目内部）

- [五大语音转文字 API 服务深度评测：技术选型与场景适配指南（百度开发者）](https://developer.baidu.com/article/detail.html?id=7034545)
- [中国自动语音识别服务综述：服务形态、计费模式与工程选型（搜狐）](https://www.sohu.com/a/1039738495_455817)
- [2026 年最佳语音转文字 (STT) API：技术对比与集成指南（Fish Audio）](https://fish.audio/zh-CN/blog/speech-to-text-api-comparison-integration-guide-2026/)
- [Speech Seaco Paraformer 与其他 ASR 成本对比（CSDN）](https://blog.csdn.net/weixin_35754962/article/details/157372207)
- [声网 AI 模型评测平台（对话式）——上海区域实测](https://www.real-time.org.cn/duihua/benchmark/all-model?region=Shanghai)
- [faster-whisper 模型选型指南：如何在速度与准确率间找到最佳平衡点](https://blog.gitcode.com/abba8ed133f34275a417221a87c45b60.html)
- [Whisper Large v3: OpenAI's Best Open-Source Speech Recognition Model](https://pristren.com/blog/whisper-large-v3-transcription/)
- [Whisper Local API for Openclaw（OpenAI 兼容本地接口参考）](https://www.toolify.ai/openclaw-skills/whisper-local-api-6649)
- [本地跑 Whisper 还是用在线 API？实测告诉你谁更准、更省、更安全](https://post.smzdm.com/p/aqrp0d6x/)
