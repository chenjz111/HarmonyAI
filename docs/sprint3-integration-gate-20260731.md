# HarmonyAI Sprint 3 集成门禁记录（2026-07-31）

> 审查人：陈家智
> 审查对象：`origin/dev` 与 Sprint 3 各成员远程分支
> 本文记录可验证事实，不代表相关分支已经合并。

## 1. 基线

- `dev` Commit：`580faca`
- 后端基线：`47 passed`
- Open PR：#44（问卷与医学安全）
- Sprint 3 Issues：#30—#41 均为 Open

## 2. 肖宇翔：PR #44

当前进展：

- 已提交 12 题 Questionnaire V2；
- 已提交确定性评分 JSON；
- 已提交安全规则、医学措辞和演示案例；
- 已补充 `tests/knowledge/test_questionnaire_v2.py`；
- GitHub Action 已通过。

已确认改进：

- 图形题补充了明确的 `score_map`；
- 删除了过宽的单字风险关键词；
- 文件已移动到约定的 `docs/`、`knowledge/`、`tests/`；
- Q12 安全题不直接参与证型或调式计分。

合并前门禁：

- [ ] 确认 PR 中旧知识库修改是否属于 #32/#33；
- [ ] 运行项目完整测试，而不是只运行 `tests/knowledge/`；
- [ ] 医学审核确认睡眠、食欲和日常影响不是单独的“抑郁/思虑”结论；
- [ ] 明确 `candidate_syndromes` 只能进入组合规则，不允许单题直接选证型；
- [ ] 分支落后 `dev` 的历史已安全处理。

## 3. 蔡子鑫：`feat/caizx`

分支状态：

- 相对 `dev`：ahead 5 / behind 0；
- 已修复 ID 唯一性、文件签名、真实写盘、Pydantic 校验；
- 已增加 Feedback V2、v1 兼容和增量迁移测试；
- 当前没有 Pull Request。

契约符合项：

- `/api/v2/documents` 基础路径符合 Contract；
- 支持上传、确认、删除和 Session 查询；
- Feedback V2 响应包含 `personal_preference_patch`；
- `global_rule_update` 为 false；
- 不再自动补造默认 4 星。

合并前问题：

- [ ] 创建 `feat/caizx → dev` PR；
- [ ] 执行完整后端回归；
- [ ] `FeedbackV2Request.experience` 当前仍是宽泛 `dict`，需要固定字段校验；
- [ ] 文档响应中 `ocr_confidence` 类型应统一为数值或枚举；
- [ ] 确认临时文件清理策略实际执行；
- [ ] 确认错误响应不返回敏感异常原文；
- [ ] v2 Assessment、Workflow、Music 仍需要其他模块实现。

## 4. 钟睿宸：`feat/zhongrc`

分支状态：

- 相对 `dev`：ahead 0 / behind 37；
- 尚无 Sprint 3 新 Commit；
- 尚无 Sprint 3 Pull Request。

阻塞影响：

- Assessment 三源融合未进入可审查状态；
- `extracted_evidence`、冲突检测和完整 `safety_flags` 未验收；
- Qwen V2 Schema、重试和问卷降级未验收；
- 可解释 Diagnosis/Prescription V2 未验收；
- #34、#35 和三路径 E2E 被阻塞。

放行条件：

- [ ] 从最新 `dev` 建立分支；
- [ ] 提交 Schema 和测试优先的 Draft PR；
- [ ] 逐字段对照 `agent-contract-v2.md`；
- [ ] 提供正常、Qwen 失败、非法 JSON、来源冲突和安全阻断测试。

## 5. 彭翔：前端 Sprint 3 分支

分支：

`38-sprint3frontend-重构欢迎页病例上传自由描述与问卷v2`

当前进展：

- 已提交欢迎、材料、自由描述、问卷、结果、播放器、反馈、完成页面；
- 已提交三个 Sprint 3 公共组件；
- 已提交 `frontend/common/api-v2.js`；
- 当前没有 Pull Request。

主要阻断：

- 相对 `dev`：ahead 1 / behind 121；
- 与 `dev` 的多个既有前端文件存在 add/add 冲突；
- 提交包含 `frontend/unpackage/dist/` 构建产物；
- `USE_MOCK=true`，当前页面主要走 Mock；
- API 路径与冻结契约不一致：
  - 前端使用 `/api/v2/records`，契约为 `/api/v2/documents`；
  - 前端使用 `/api/v2/assessment`，契约为 `/api/v2/assessments`；
  - 前端使用 `/api/v2/narrative`，契约没有独立 Narrative Agent；
  - 前端使用 `/analysis/{id}/status` 和 `/result`，契约使用 Workflow/Session；
  - 前端使用 `/prescription/audio`，契约使用 `/api/v2/music`；
- Agent ID 使用 `assessment_agent_v2`、`music_agent_v2`、`feedback_agent_v2`，契约要求无版本后缀的规范 ID。

放行条件：

- [ ] 从最新 `dev` 建立干净分支；
- [ ] 只迁移 Sprint 3 页面、组件和必要路由；
- [ ] 移除 `unpackage/dist` 并加入忽略规则；
- [ ] API 路径和字段对齐 Contract；
- [ ] 规范 Agent ID；
- [ ] Mock 与真实模式使用明确配置，比赛验收必须走真实后端；
- [ ] 创建 Draft PR 并附页面截图和测试结果。

## 6. 当前集成结论

现在不能开始最终三路径 E2E，也不能创建稳定比赛 Tag。原因不是陈家智文档未完成，而是三个实现层尚未同时进入可合并状态：

```text
AI V2 未提交
  + 后端 V2 无 PR
  + 前端 V2 契约不一致且冲突
  → 无法形成同一个可运行的 Sprint 3 集成版本
```

## 7. 今日最短行动路径

1. 陈家智发布 Agent Contract 和集成门禁 PR；
2. 肖宇翔处理 PR #44 最终审查；
3. 蔡子鑫立即创建后端 PR；
4. 钟睿宸先提交 Schema + 降级测试 Draft PR；
5. 彭翔从最新 `dev` 整理前端并对齐 API；
6. 在临时集成分支合并候选 Commit；
7. 运行完整测试和三路径 E2E；
8. 只修 P0 阻断问题；
9. 通过后创建 Release PR 和稳定 Tag。
