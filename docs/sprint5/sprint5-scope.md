# Sprint 5 Scope — Cloud AI & Real Music Generation

## 目标

在不破坏 Sprint 4 稳定链路的前提下，将 HarmonyAI 升级为“云端/本地 AI 可切换 + 真实音乐生成可降级”的比赛级产品。Sprint 5 不再围绕单一 emotion F1 反复调优；Sprint 4 权威分数 0.7407 与 `ACCEPTED_KNOWN_MODEL_LIMITATION` 保持不变。

## P0

1. Cloud Qwen Provider：endpoint/key/model 由环境注入，不提交 Secret。
2. Assessment Agent 可用 Cloud Qwen，本地 Ollama 为明确 fallback。
3. Diagnosis Agent 使用 Cloud Qwen + 现有 RAG，保持 evidence、abstain 与 safety contract。
4. `MusicGenerationProvider`：结构化音乐 Prompt → 生成任务 → 音频资产 → Player。
5. 生成失败明确退回本地曲库匹配，响应标明 source/type/status。
6. 完整 Demo 与 Provider health、成本、超时、隐私可观察。

## P1 / P2

- P1：异步任务/取消、缓存去重、运行时 Provider 选择、Demo 配额保护、参数解释。
- P2：多 Provider 对比、更多音乐风格、历史偏好参与生成、成本趋势。

## 不做

- 不修改 Sprint 4 gold/expected/Frozen threshold，不恢复 0.80 优化。
- 不让反馈修改全局医学规则，不宣称医疗诊断或治疗。
- 不把第三方调用写死在 Agent 内。
- 不在 PR #65 实现 Sprint 5 production code。

## 团队分工

| 成员 | 责任 |
|---|---|
| 陈家智 | 产品范围、Provider/Music Contract、集成与验收 |
| 肖宇翔 | 医学边界、Prompt/RAG 证据与安全案例 |
| 钟睿宸 | Cloud Qwen、Assessment/Diagnosis 与评测 |
| 蔡子鑫 | 生成任务、存储、回调、缓存与数据库 |
| 彭翔 | Provider 状态、生成进度、播放器与降级 UI |

## Definition of Done

- 云端/本地 Qwen 可切换，Secret 不入仓库。
- Cloud failure 可明确降级到 local，安全语义不变。
- Music Generation 有真实成功案例和本地曲库 fallback。
- Player 只消费后端权威 Prescription/Music。
- 自动测试覆盖成功、超时、配额、失败、fallback、隐私和 safety。
- Android/H5 完成真实 Demo 验收，部署和回滚步骤完整。
