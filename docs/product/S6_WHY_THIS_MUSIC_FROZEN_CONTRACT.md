# Sprint 6 — “为什么是这首音乐？”冻结产品合同

**状态：FROZEN**  
**日期：2026-10-04**  
**范围：Player 内默认折叠的音乐解释，不新增独立五音解析流程。**

> Player public presentation 的当前唯一 authority 为 `S6_PLAYER_FROZEN_CONTRACT.md`；本文件保留为解释区历史冻结记录，冲突处以后者为准。

## 1. 用户界面

Player 仅在存在可展示内容时显示“为什么是这首音乐？”，每次进入或重新进入 Player 均默认折叠。展开后按以下顺序展示；单项缺失时直接省略，不补默认文案：

1. **近期状态**：`confirmed_state`
2. **状态解读**：`state_tendency`
3. **本次调适方向**：`analysis_rationales[].summary`
4. **五音方案**：`mode_explanation`，以及仅在后端明确给出时展示的 `primary_tone` / `secondary_tone` 与各自 explanation
5. **音乐设计**：BPM、乐器、环境音、能量走向、音乐结构及各自的后端 explanation

`UserGoal` 表示当前 session 的调适诉求，不是历史学习偏好，不单独显示“偏好已纳入”，也不成为状态、诊断或五音推理依据。Generation Spec 的目标时长不得作为“推荐时长 / 建议时长 / 调适时长”显示；Player 只展示实测或已验证的音频播放时长。

## 2. 三种模式

### `personalized_five_tone`

- 展示后端 `mode_explanation.label`（“个性化五音方案”）及 explanation。
- 展示后端明确给出的主音及主音 explanation。
- 仅在后端明确存在 `secondary_tone` 时展示辅音及辅音 explanation。
- 禁止从权重取最大值、第二大值，禁止默认宫音，禁止前端补辅音。

### `integrated_regulation`

- 展示后端 `mode_explanation.label`（“综合调适”）及 explanation。
- 不展示主音、辅音或任何权重信息。

### `basic_wellness`

- 展示后端 `mode_explanation.label`（“基础舒缓”）及 explanation。
- 不展示主音、辅音或任何权重信息。

## 3. Public UI 权重禁令

用户侧不得投影或渲染：

- 五音百分比或权重数字
- 比例条、柱状图、饼图
- `toneWeights` presentation 字段
- 任何由 `tone_weights` 推断的模式、主音或辅音

Backend `tone_weights` 保留，继续供 Diagnosis、Prescription、GenerationSpec、Prompt Compiler、审计与音乐生成使用。

## 4. Backend public read model

现有 `FiveToneAnalysisReadModel` / `FiveToneAnalysisReadModelV33` 添加以下可选 public presentation 字段：

- `mode_explanation: { label, explanation }`
- `energy: { value, explanation }`
- `structure: { value, explanation }`

新生成的记录填充这些字段；旧 v3.2/v3.3 payload 缺失字段时继续可读。schema version 不变，不新增数据库 migration。

能量和结构必须由 backend 现有确定性 BPM/时长决策投影。transport `GenerationSpec` 与 public read model 共用同一 helper，不允许前端解析 raw structure，也不允许复制第二套 GenerationSpec 决策逻辑。

## 5. 不变边界

- Diagnosis authority 不变。
- GenerationSpec 的 BPM、时长、能量和结构决策语义不变。
- Prompt Compiler 不变。
- RAG、threshold、Top-K、basic_wellness gate、dominance logic 不变。
- Candidate D、provider adapter、MiniMax、TokenHub、knowledge corpus、embedding/index 不变。
- 展开/折叠只修改 Player 本地 presentation state：0 API、0 Diagnosis、0 Prescription、0 Generation、0 RAG、0 provider；不得重建 controller/audio context，不得暂停、重载或重置播放进度。

## 6. 验收

- 默认折叠与本地 toggle 行为保持。
- personalized（含/不含辅音）、integrated、basic 均有自动化覆盖。
- state tendency、mode、BPM、乐器、环境音、能量和结构 explanation 均由后端字段驱动。
- 缺失字段省略，持久化 explanation 原样保留，前端不推断、不硬编码事实解释。
- public presentation 与 Player 模板均无 tone weights 或百分比显示。
- routine tests 不调用真实 Qwen、embedding 或音乐 provider，不生成音频。
