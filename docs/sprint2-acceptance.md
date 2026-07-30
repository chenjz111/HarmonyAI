# Sprint 2 验收标准 — 2026-07-24

> 基于 Sprint 2 计划书 `docs/sprint2-plan.md` 的 Walking Skeleton 策略。
> 验收原则：**链不断、数不丢、能解释**。
> 格式对齐 Sprint 1 验收标准（`docs/sprint1-acceptance.md`）：★硬门槛 + 补课项。

---

## 验收总流程（Day 14，预计 90 分钟）

```
1. 彭翔 录屏演示 全流程（15min）
2. 蔡子鑫 Swagger 调 5 接口（15min）
3. 钟睿宸 讲解 Agent 链路（15min）
4. 肖宇翔 展示知识库映射（10min）
5. 陈家智 逐人验收 + 总结（30min）
6. 录屏存档 → 发老师
```

---

## ★ 硬门槛（不过则 Sprint 2 不通过）

### 1. 前端全链路闭环（彭翔 + 全队）

| # | 验收标准 | 验证方式 |
|---|---------|---------|
| 1.1 | 问卷页可填写提交，调用 `POST /assessment`，返回有效 envelope | 录屏 |
| 1.2 | 诊断页显示证型名称 + 可信度（如：肝郁化火 55%） | 录屏 |
| 1.3 | 处方页显示调式 + BPM + 乐器（如：角调 68BPM 古筝/古琴） | 录屏 |
| 1.4 | 播放页音乐能被用户听到 | 录屏 |
| 1.5 | 评分页可提交反馈，返回 continue/adjust/stop | 录屏 |
| 1.6 | 整条链路从头到尾不报错、不白屏 | 录屏 |

**判定**：录屏里音乐响了、评分提交了 = 通过。

---

### 2. 后端 5 接口可调用（蔡子鑫）

| # | 验收标准 | 验证方式 |
|---|---------|---------|
| 2.1 | `POST /api/v1/assessment` 返回 200，envelope 含 agent_id/confidence/output | Swagger 现场调 |
| 2.2 | `POST /api/v1/diagnosis` 返回 200，含 syndrome_diagnosis.primary | Swagger |
| 2.3 | `POST /api/v1/prescription` 返回 200，含 music_feature.tone_id/tone_name/bpm | Swagger |
| 2.4 | `POST /api/v1/generation` 返回 200，含 audio.url | Swagger |
| 2.5 | `POST /api/v1/feedback` 返回 200，含 decision.action | Swagger |
| 2.6 | 异常输入（空 body、缺 session_id）返回 4xx 而非 500 崩溃 | Swagger |

**判定**：5 个 POST 全部 200 + 异常场景不崩 = 通过。

---

### 3. AI Engine 链路可解释（钟睿宸）

| # | 验收标准 | 验证方式 |
|---|---------|---------|
| 3.1 | 5 个 Agent 各自返回 15 个通用字段（agent_id/version/name/layer/run_id/session_id/user_id/status/confidence/reason/warnings/input/output/processing_time_ms/timestamp） | 检查 Swagger 返回值 |
| 3.2 | 每个 Agent 的 confidence 与 reason 一致（不能 confidence=0.9 但 reason=空） | 抽查 |
| 3.3 | Assessment → Diagnosis → Prescription 的 input/output 链不断（下游 input 包含上游 output） | 抽查 |
| 3.4 | 诊断 confidence < 0.4 时，不返回处方/音频，改为 recommend_professional | 传空问卷验证 |
| 3.5 | Agent 降级时 warning 有说明 + degradation_triggered=true | 不配 Qwen 时验证 |
| 3.6 | 配了 Qwen 时返回 status=success（非 degraded） | 可选，有 Qwen 时验证 |

**判定**：字段齐全 + 置信度合理 + 低分截断生效 = 通过。

---

### 4. 知识库可检索（肖宇翔）

| # | 验收标准 | 验证方式 |
|---|---------|---------|
| 4.1 | 8 个证型 × 情绪映射完整（emotion→syndrome→tone 链路不断） | 抽查 2 条 |
| 4.2 | 每条映射有 credibility_level（A/B/C/D） | 抽查 |
| 4.3 | Chroma 检索命中至少 1 条相关文献（如搜"焦虑"命中 k_001） | 现场跑 `chroma_demo` |
| 4.4 | 18 篇文献覆盖 Level A/B/C/D 四个等级 | 自查清单 |

**判定**：映射不断 + 检索命中 + 四等级全覆盖 = 通过。

---

## 补课项（不卡 Sprint 2 通过，但需在 Sprint 3 第一周补齐）

| # | 项 | 负责人 |
|---|-----|--------|
| B1 | 4 个证型（心火上炎/脾虚湿困/肺气虚/肾阴不足）缺现代文献 | 肖宇翔 |
| B2 | Router 异常降级按 agent-architecture.md §3 规范化 | 蔡子鑫 |
| B3 | 前端 api.js USE_MOCK 模式下 mock 数据与真实 API 返回值 100% 对齐 | 彭翔 |
| B4 | 本地曲库音频文件未落地（当前用占位 local:// 路径） | 彭翔 + 陈家智 |
| B5 | 看板缺 Review 和 Done 列（GitHub API 不支持动态加列，需 Web UI） | 陈家智 |

---

## 验收通过后的动作

1. Sprint 2 Issues #14-#18 全部关闭，评论 "Sprint 2 验收通过 ✅"
2. `docs/sprint2-plan.md` 状态更新为"已完成"
3. 全员录屏存档到 `docs/meeting/`
4. 向老师发送 Sprint 2 完成报告（含录屏链接 + 进度总结）
5. 开 Sprint 3 Planning：真实音乐生成（SkyMusic）+ 用户体验打磨

---

## 陈家智最终确认（四问测试）

验收结束前，陈家智逐人问四个问题（不许翻文档）：

1. **你的 Agent/接口/页面做了什么事？**（一句话说清楚）
2. **输入和输出是什么？**（字段级）
3. **失败了怎么办？**（降级路径）
4. **Sprint 3 你会改哪里？**（演进意识）

四问全部答对 = 验收通过。
