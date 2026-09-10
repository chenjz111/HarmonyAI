# V3.1 音乐参数规则候选表

状态：`CANDIDATE_FOR_OWNER_AND_MEDICAL_REVIEW`。本文件只提供参数候选和
确定性合并规则，不是 `Approved` 资产，不可作为 Real readiness 配置，也不
改变问卷、医学映射、Teacher Flow 或 Frozen Contract。

这些候选值只描述音乐参数，不表达医学结论，也不从 UserGoal 文本推导医学
事实。最终值须由 Owner 与肖宇翔审核后，另行生成
`music_generation_rules_v3.1` JSON、版本和 canonical checksum。

## 参数边界

| 字段 | 候选约束 |
| --- | --- |
| `bpm` | 沿用现有 Schema：整数 `40..120` |
| `duration_seconds` | 正整数，且不超过 `300` 秒 |
| `instruments` | 非空、无重复字符串 |
| `ambience` | 非空、无重复字符串；“无额外环境音”表示显式无额外音效，不是医学语义 |
| 医学字段 | 不新增 `syndrome_code`、claim、organ 或医学映射 |

## Default 与七个正式 UserGoal code

以下是待审核候选，不是最终批准值。

| 场景 / code | BPM | instruments | ambience | duration_seconds | 候选意图 |
| --- | ---: | --- | --- | ---: | --- |
| `default` | 60 | `古琴` | `细雨` | 180 | 无可用目标、跳过或安全回落 |
| `sleep` | 50 | `古琴`, `箫` | `细雨` | 240 | 低速、稳定的音乐参数候选 |
| `relaxation` | 54 | `古琴` | `溪流` | 240 | 舒缓参数候选 |
| `emotion_regulation` | 60 | `古琴`, `琵琶` | `微风` | 180 | 中性稳定参数候选 |
| `focus` | 72 | `箫` | `无额外环境音` | 180 | 清晰、少环境干扰的参数候选 |
| `energy` | 84 | `笛` | `流水` | 180 | 较快但仍在 Schema 范围内的参数候选 |
| `stress_relief` | 56 | `古琴`, `埙` | `细雨` | 240 | 舒缓参数候选 |
| `other` | — | — | — | — | 不建立专属映射，安全回落 `default` |

正式 `goals` 必须且只能包含以上七个 code。`other` 仍是正式 code，但其
override 允许为空；任意自造字符串都必须被 Schema 拒绝。

## secondary_goal 合并策略

策略名：`primary_over_secondary_fill_missing`。

1. 先读取 `default`。
2. 若有 `secondary_goal`，仅把该目标明确提供的字段写入候选结果。
3. 若有 `primary_goal`，再次写入其明确提供的字段；同字段冲突时主目标
     优先，次目标不得覆盖主目标。
4. 主目标未提供的字段可由次目标补齐，因此次目标不会被前端显示为已应用、
   后端却完全忽略。
5. `other`、custom-only 和 skip/null 没有已批准专属映射时，保持 default，
   不从 `custom_goal_text` 推导 BPM、五音、器官、证型或任何医学结论。
6. 全部参数仍由规则资产确定性生成，LLM 不参与优先级或参数选择。

## 进入 Approved 的必要条件

批准后才生成正式 JSON，并补齐：

```text
schema_id=music_generation_rules_v3.1
review_status=approved
asset_version=<Owner批准版本>
content_checksum=<canonical sha256>
```

运行时配置只能引用已批准的 `PATH / VERSION / CHECKSUM` 三元组。当前没有
在本分支设置这些正式值，也没有将本候选表伪装成 Real Smoke 证据。
