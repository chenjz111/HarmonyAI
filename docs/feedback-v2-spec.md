# HarmonyAI Feedback 2.0 规格

## 1. 目标

Feedback 2.0 将当前“1—5 星 + 选填评论”升级为可用于比较听前与听后状态、评价音乐体验并调整个人偏好的结构化反馈。

反馈闭环是：

```text
听前状态
  → 音乐处方与播放行为
  → 听后状态
  → 用户体验评价
  → Feedback Agent
  → 个人偏好补丁
  → 下一次处方在医学规则允许范围内个性化
```

反馈只能反映用户的主观体验，不能被描述为临床疗效。

## 2. 听前与听后状态

### 2.1 听前基线

在播放器开始前收集：

- 当前紧张程度：0—10；
- 当前身体紧绷程度：0—10；
- 当前精神疲劳程度：0—10；
- 本次最希望改善的目标：放松、帮助入睡、平复烦躁、缓解低落、提升专注、其他。

为降低操作负担，至少要求填写“紧张程度”和“本次目标”，其余可选但建议比赛演示全部填写。

### 2.2 听后状态

播放完成或用户主动结束后收集：

- 当前紧张程度：0—10；
- 当前身体紧绷程度：0—10；
- 当前精神疲劳程度：0—10；
- 主观变化：明显好转、有一点好转、没有变化、更不舒服。

系统计算：

```text
紧张变化 = 听后紧张 - 听前紧张
紧绷变化 = 听后紧绷 - 听前紧绷
疲劳变化 = 听后疲劳 - 听前疲劳
```

负数表示用户主观评分下降。页面必须标注“用户主观反馈”，不能写成治疗效果。

## 3. 反馈字段

### 3.1 必填字段

- 整体星级：1—5；
- 放松程度：1—5；
- 音乐匹配度：1—5；
- 是否愿意继续使用：`yes`、`maybe`、`no`；
- 是否收藏当前音乐：布尔值；
- 听前状态；
- 听后状态。

### 3.2 选填字段

- 不喜欢的音乐特征，可多选：
  - 节奏太快；
  - 节奏太慢；
  - 高频声音刺耳；
  - 某件乐器不喜欢；
  - 环境音不适合；
  - 音量不舒服；
  - 重复感太强；
  - 时长不合适；
  - 其他。
- 对应乐器或环境音名称；
- 文字反馈，最长 500 字；
- 播放行为：播放秒数、完成率、暂停次数、跳过次数；
- 用户主动点“不适”的时刻和原因。

## 4. API Schema 建议

以下为拟议 v2 请求，不代表当前接口已经实现：

```json
{
  "schema_version": "feedback_v2.0",
  "session_id": "sess_20260728_ab12cd",
  "prescription_id": "rx_20260728_ab12cd",
  "track_id": "local_gong_001",
  "pre_state": {
    "tension": 7,
    "body_tension": 6,
    "mental_fatigue": 8,
    "goal": "sleep"
  },
  "post_state": {
    "tension": 5,
    "body_tension": 4,
    "mental_fatigue": 6,
    "change_label": "slightly_better"
  },
  "experience": {
    "overall_rating": 4,
    "relaxation_rating": 4,
    "music_match_rating": 3,
    "continue_use": "yes",
    "favorite": true,
    "disliked_features": ["high_frequency"],
    "disliked_instruments": ["笛子"],
    "comment": "整体比较放松，但笛声有一点尖。"
  },
  "playback": {
    "listened_seconds": 780,
    "duration_seconds": 900,
    "completion_rate": 0.87,
    "pause_count": 1,
    "skip_count": 0
  },
  "submitted_at": "2026-07-28T21:05:00+08:00"
}
```

字段约束：

- 0—10 字段只能为整数；
- 1—5 评分只能为整数；
- `continue_use` 只能为 `yes`、`maybe`、`no`；
- `completion_rate` 由后端根据播放秒数复核并限制在 0—1；
- `comment` 清理前后空白并限制长度；
- 枚举外的“不喜欢特征”写入 `other_detail`，不能直接拼接进 Prompt；
- 同一 `session_id + prescription_id` 应支持幂等提交或明确版本号。

### 4.1 建议响应

```json
{
  "success": true,
  "data": {
    "feedback_id": "fb_20260728_f93a10",
    "agent_id": "feedback_agent",
    "status": "success",
    "subjective_change": {
      "tension_delta": -2,
      "body_tension_delta": -2,
      "mental_fatigue_delta": -2
    },
    "decision": {
      "action": "adjust_personal_preference",
      "next_step": "complete"
    },
    "personal_preference_patch": {
      "reduce_instruments": ["笛子"],
      "reduce_high_frequency": true,
      "favorite_tracks_add": ["local_gong_001"]
    },
    "global_rule_update": false
  },
  "error": null
}
```

## 5. 数据库存储建议

当前 `feedbacks` 表已经具有：

- 满意度、情绪匹配、放松、睡眠、压力和文字反馈；
- 完成率、重播、暂停、跳过、时段和音量；
- 决策、调整参数和 `profile_update`。

Sprint 3 建议做增量迁移，不删除旧字段：

### 5.1 `feedbacks` 增量字段

- `schema_version`
- `prescription_id`
- `track_id`
- `pre_state_json`
- `post_state_json`
- `subjective_change_label`
- `continue_use`
- `favorite`
- `disliked_features_json`
- `disliked_instruments_json`
- `preference_patch_json`
- `global_rule_update`，固定为 `FALSE`

若截止期不允许展开多个列，可先使用命名明确的 JSON 字段，但必须有 Pydantic 校验和迁移版本。

### 5.2 个人偏好

当前 `users` 表已有偏好乐器、BPM 范围、偏好时段等字段。比赛版没有完整用户系统，可采用演示用户或会话级偏好，但应预留：

- 喜欢的曲目；
- 减少使用的乐器；
- 不喜欢的音乐特征；
- 偏好环境音；
- 偏好时长；
- 最近更新时间；
- 偏好的证据来源反馈 ID。

### 5.3 数据原则

- 保存原始用户评分和 Agent 推导结果，二者分开；
- 不覆盖历史反馈；
- 重复提交采用幂等键；
- 用户文字反馈属于敏感内容，日志不得完整打印；
- 用户收藏和个人偏好可以撤销；
- 数据删除策略与比赛版隐私说明一致。

## 6. Feedback Agent 输出

Feedback Agent 不应只将星级映射为 `continue/adjust/stop`。建议输出：

```json
{
  "agent_id": "feedback_agent",
  "status": "success",
  "subjective_change": {
    "tension_delta": -2,
    "body_tension_delta": -2,
    "mental_fatigue_delta": -2,
    "summary": "用户主观感到紧张和身体紧绷有所下降"
  },
  "experience_summary": {
    "overall_rating": 4,
    "relaxation_rating": 4,
    "music_match_rating": 3,
    "continue_use": "yes",
    "favorite": true
  },
  "decision": {
    "action": "adjust_personal_preference",
    "reason_codes": ["dislike_high_frequency", "dislike_instrument"]
  },
  "personal_preference_patch": {
    "reduce_instruments": ["笛子"],
    "reduce_high_frequency": true,
    "preserve_instruments": ["古琴"],
    "favorite_tracks_add": ["local_gong_001"]
  },
  "global_rule_update": false,
  "warnings": []
}
```

用户端可展示：

> 已记录你的偏好：下次会减少高频笛声，保留你喜欢的古琴元素。你的反馈仅用于调整个人体验。

不应展示：

- 大模型内部推理过程；
- “系统已证明本音乐有效”；
- “你的反馈已修改中医规则”。

## 7. 个人偏好更新规则

### 7.1 允许自动更新

- 收藏或取消收藏曲目；
- 对某件乐器增加或减少个人偏好权重；
- 对高频、节奏、环境音、时长等增加个人偏好标签；
- 记录常用时段和本次目标；
- 在已审核的安全参数范围内，下次排序时优先或降权。

### 7.2 更新强度

- 单次反馈只做小幅调整，不永久屏蔽；
- 用户明确选择“不喜欢某乐器”可立即个人降权；
- 多次一致反馈可增强个人偏好；
- “更不舒服”应降低相同曲目的个人排序，并提示下次更换；
- 个人偏好不得绕过处方安全范围和辅助辨证结果。

### 7.3 禁止自动更新

- 证型定义；
- 症状到证型的医学规则；
- 五行、五脏、五音知识映射；
- 全局处方权重；
- 其他用户的偏好；
- 知识库文献内容或可信度；
- 安全阈值。

如团队未来需要改动全局规则，必须经过：

```text
离线统计
  → 医学负责人审查
  → 规则变更提案
  → 版本化测试
  → 人工批准
  → 发布
```

旧架构中“群体低满意度自动触发全局权重调整”的设计在 Sprint 3 中停止使用。

## 8. 异常和安全处理

- 反馈保存失败：保留表单内容，提供重试，不显示成功；
- 听前状态缺失：允许补填，不用默认值伪造；
- 用户选择“更不舒服”：提示停止当前音乐，可尝试其他方式；如伴随风险信号则进入安全提示；
- 不喜欢特征为空：不强制选择；
- 播放不足 30 秒：反馈仍可提交，但标记 `short_exposure=true`，不计算强结论；
- 星级与变化冲突：保留两者并输出冲突提示，不擅自改值；
- Qwen 不可用：使用确定性 delta 和偏好规则，反馈仍可保存。

## 9. 验收标准

- 1—5 星保留；
- 听前和听后至少有紧张程度对比；
- 放松程度、音乐匹配度、继续使用、收藏均可提交；
- 不喜欢特征可多选，文字反馈可留空；
- Feedback Agent 输出包含主观变化和个人偏好补丁；
- 保存失败不伪造成功；
- 单次反馈不会修改全局医学规则；
- Qwen 关闭时反馈仍可计算 delta 并更新个人偏好；
- 页面明确说明变化是用户主观反馈。
