# V3.1 音乐参数规则候选表

状态：`OWNER_APPROVED_ASSET_GENERATED`。本文件保留参数候选与审核来源记录；
正式运行时只使用 `knowledge/v3/music-generation-rules-v3.1.json`，不得直接将
本 Markdown 作为 readiness 配置。本次批准不改变问卷、医学映射、Teacher
Flow 或 Frozen Contract。

这些值只描述音乐参数，不表达医学结论，也不从 UserGoal 文本推导医学事实。
Owner 已批准按本表生成 `music_generation_rules_v3.1` 正式资产，无需重复医学
复核。

## 参数边界

| 字段 | 候选约束 |
| --- | --- |
| `bpm` | 沿用现有 Schema：整数 `40..120` |
| `duration_seconds` | 目标/预计时长，正整数，且不超过 `300` 秒；Player 实际时长以生成文件实测为准 |
| `instruments` | 非空、无重复字符串 |
| `ambience` | 非空、无重复字符串；“无额外环境音”表示显式无额外音效，不是医学语义 |
| 医学字段 | 不新增 `syndrome_code`、claim、organ 或医学映射 |

## Default 与七个正式 UserGoal code

以下表格现作为 Approved JSON 的审核来源记录。除 `default` 外，各行只列出
本 UserGoal 明确覆盖的字段；留空表示该字段交由合并策略继续从 secondary
或 default 补齐，不表示删除原有候选方向。

| 场景 / code | BPM 覆盖 | instruments 覆盖 | ambience 覆盖 | 目标/预计时长覆盖 | 候选意图 |
| --- | ---: | --- | --- | ---: | --- |
| `default` | 60 | `古琴` | `细雨` | 180 | 无可用目标、跳过或安全回落 |
| `sleep` | 50 | — | — | 240 | 低速、稳定的音乐参数候选；未覆盖字段沿用安全默认 |
| `relaxation` | — | — | `溪流` | 240 | 舒缓参数候选；未覆盖字段沿用安全默认 |
| `emotion_regulation` | — | `古琴`, `琵琶` | `微风` | — | 中性稳定参数候选；未覆盖字段沿用安全默认 |
| `focus` | 72 | — | `无额外环境音` | — | 清晰、少环境干扰的参数候选；未覆盖字段沿用安全默认 |
| `energy` | 84 | `笛` | — | — | 较快但仍在 Schema 范围内的参数候选；未覆盖字段沿用安全默认 |
| `stress_relief` | — | `古琴`, `埙` | — | 240 | 舒缓参数候选；未覆盖字段沿用安全默认 |
| `other` | — | — | — | — | 不建立专属映射，安全回落 `default` |

正式 `goals` 必须且只能包含以上七个 code。`other` 仍是正式 code，但其
override 允许为空；任意自造字符串都必须被 Schema 拒绝。

## secondary_goal 合并策略

策略名：`primary_over_secondary_fill_missing`。

1. 先读取 `default` 的完整 BPM、乐器、环境音和目标/预计时长。
2. 若有 `secondary_goal`，只把该目标明确覆盖且 primary 未覆盖的字段补入。
3. 若有 `primary_goal`，只把该目标明确覆盖的字段写入最终结果；同字段冲突
   时 primary 优先，secondary 不得覆盖 primary。
4. 由此得到确定性优先级：`primary explicit > secondary explicit > default`。
   每个字段独立选择，不能用某一目标的整组参数覆盖其他字段。
5. explanations 也按字段合并：最终字段来自 primary/secondary 时使用对应说明；
   最终值与 default 相同则保留 default 的中性说明，不声称目标已应用。
   任一非空 override 必须同时提供且只提供其覆盖字段对应的 explanations；
   缺少说明或夹带未覆盖字段说明时，资产校验必须失败。空的 `other`
   override 不携带 explanations。
6. `other`、custom-only 和 skip/null 没有已批准专属映射时，保持 default，
   不从 `custom_goal_text` 推导 BPM、五音、器官、证型或任何医学结论。
7. 全部参数仍由规则资产确定性生成，LLM 不参与优先级或参数选择。

## 字段级 explanations 示例

以 `primary=sleep`、`secondary=relaxation` 为例，最终结果和说明分别按字段
确定，不做整组替换：

| 字段 | 最终值来源 | 说明示例 |
| --- | --- | --- |
| BPM | primary `sleep` | `主要目标对应的速度候选。` |
| instruments | default | `按批准规则提供配器参考。` |
| ambience | secondary `relaxation` | `次要目标对应的环境音候选。` |
| 目标/预计时长 | primary `sleep` | `主要目标对应的预计时长候选。` |

说明只描述音乐设计参数及其来源，不描述医学作用、疗效或证候结论。
`duration_seconds` 是目标/预计时长；播放器最终采用生成文件的实际测量时长。

## Approved 发布记录

正式 JSON 已生成并通过 loader 的版本、Schema 与 canonical checksum 校验：

```text
path=knowledge/v3/music-generation-rules-v3.1.json
schema_id=music_generation_rules_v3.1
review_status=approved
asset_version=music-generation-rules-v3.1-r1
content_checksum=sha256:b8b65b2658ea849945a43884bb786d59689606e4cdb97d63620df8b5179539be
```

运行时配置只能引用以上已批准的 `PATH / VERSION / CHECKSUM` 三元组。本次
资产发布不等同于真实 Provider Smoke；Real 状态仍以 Owner 环境验证为准。
