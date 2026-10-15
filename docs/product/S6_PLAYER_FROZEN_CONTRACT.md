# Sprint 6 Player 冻结产品合同

**状态：FROZEN**  
**日期：2026-10-06**  
**Authority：本文件是 Sprint 6 Player public presentation 的唯一产品 authority。**

## 1. Authority 边界

- Player 是已持久化音乐资产与 `FiveToneAnalysisReadModel` 的只读消费端。
- Player 前端只做字段 projection，不推断医学结论、五音、音乐参数、偏好或生成原因。
- `UserGoal` 是当前 session 的调适诉求；`UserMusicPreference` 是历史反馈形成的学习偏好。两者来源、生命周期和公开语义不同，禁止混用。
- Player 不单独展示“偏好已纳入”。当前调适诉求只有在 backend 已形成对应公开 explanation 时，才可作为该 explanation 的依据之一。

## 2. 播放主区域

播放主区域保留品牌头部、hero、真实媒体进度/当前时间/总时长和播放控制。按 2026-10-11 Owner 决定，hero 与进度条之间不再显示曲名行，顺序为圆形封面 → 进度条/时间 → 播放控制。该区域不得重复展示：

- regulation mode 或主/辅音文字；
- BPM、乐器、环境音；
- 生成来源标签“AI生成音乐”。

资产 title 若是 `生成音频 84 BPM` 一类技术标题，presentation 数据仍稳定投影为中性标题“五音调适音乐”。这是 temporary deterministic display fallback，不是正式的音乐命名机制；当前 Player 主播放区域不渲染该 title。普通 title 的数据语义、历史入口及其他页面不变。不得修改 MusicAsset identity、URL、checksum 或持久化 title。

## 3. “本次音乐”摘要

“本次音乐”只承担快速参数摘要，可展示 backend 已确认的 mode/tone、BPM、乐器和环境音。`matched_fallback` 必须在该区域如实披露为审核曲库匹配；正常生成不显示“AI生成音乐”。

环境音值为 `无额外环境音` 时，标题保持该值，解释必须使用否定语义，例如“本次不加入额外环境音层……”，禁止表达成“加入无额外环境音”。

## 4. “为什么是这首音乐？”

解释默认折叠；展开/收起保持 0 API、0 Diagnosis、0 Prescription、0 Generation、0 RAG、0 provider，并且不改变 audio controller、播放状态或进度。

公开 explanation 必须解释为什么采用该设计，而不是简单复述参数：

- BPM 原因来自 backend 已确认的 regulation mode、Tone Profile、GenerationSpec、当前 UserGoal 或已批准规则语义；
- 乐器和环境音原因遵循相同 authority；
- energy 和 structure 仅在 backend 有实际 authority 字段时展示；
- 缺失 explanation 时省略，前端不补写。

2026-10-11 Owner 授权兼容扩展：现代 v3.2/v3.3 read model 的 BPM、乐器、环境声 explanation 可缺省或为 null，参数值仍必填；非空解释仍须满足原约束。legacy v3.1 的严格读取、已持久化 payload/checksum 及其他解释字段保持不变。无可信的实际选用规则依据时省略参数理由，不生成循环套话。

三种 mode 的既有 authority 不变：`personalized_five_tone`、`integrated_regulation`、`basic_wellness` 不得因展示层互相升级或推导；basic 不展示主/辅音，integrated 不从最大 weight 推主音。

## 5. Duration

- `GenerationSpec.duration_seconds` 是内部 provider generation target，可继续参与 structure sum、Prompt Compiler、provider request 与 Prescription persistence。
- 它不得进入 public explanation 或 Prescription 的公开参数摘要，不得被称为音频长度、推荐时长或建议聆听时长。
- Player 实际总时长只来自 validated `MusicAsset.duration_seconds` 或 runtime audio measured duration；runtime 有效值优先。

## 6. 非目标

本合同不改变 evidence chain、organ mapping、dominance thresholds、RAG policy/Top-K/threshold、GenerationSpec authority、Prompt Compiler、provider、audio duration 验证、candidate identity 或 temporal semantics。
