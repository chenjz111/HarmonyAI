# HarmonyAI Sprint 3 稳定集成设计

- 负责人：陈家智
- 日期：2026-08-04
- 状态：已确认，等待按阶段执行
- 集成基线：dev

## 1. 目标与范围

本设计用于把目前分散在文档、医学知识、后端、AI 和前端分支中的 Sprint 3 成果，按可验证、可回退、可解释的顺序集成到 dev，形成比赛演示稳定版本。

最终流程为：欢迎页 → 病例材料上传或跳过 → 自由描述或跳过 → 图文问卷 → AI 分析 → 可解释评估结果 → 音乐处方与播放 → 多维反馈 → 完成页。

本轮不实现 SkyMusic 实时生成、语音输入、多轮聊天、可穿戴设备、七日疗程、支付、完整用户系统或全局规则自动学习。

## 2. 当前基线

| 工作项 | 当前状态 | 处理结论 |
| --- | --- | --- |
| PR #45：队长规划与发布文档 | 可合并，只有文档 | 第一批进入 dev |
| PR #44：医学知识与问卷规则 | 可合并，50 项测试通过 | 文档之后进入 dev |
| PR #46：后端上传与反馈接口 | 仍有 4 项测试失败 | 不直接合并，建立修复分支 |
| feat/zhongrc：AI 三源融合 | 分支自身 324 项测试通过，但落后 dev 且有 3 处冲突 | 从最新 dev 建立干净集成分支 |
| Sprint 3 前端分支 | 严重落后 dev，包含构建产物、默认 Mock 和接口命名偏差 | 不整体合并，只迁移有效页面和组件 |

分支自身测试通过只表示它在原环境中可工作，不代表与最新 dev 集成后仍然正确。每个阶段都必须在合并后的候选分支上重新验证。

## 3. 集成原则

1. dev 必须始终保持可运行和测试通过。
2. 所有 PR 使用普通 Merge Commit，不使用 Squash、Rebase 或强制推送。
3. 不删除仍包含未合并工作的远程分支。
4. 顺序固定为：文档 → 医学知识 → 后端 → AI → 前端 → 端到端发布。
5. 每次合并前检查文件范围、敏感信息、测试、冲突和兼容性。
6. Sprint 3 新接口不得破坏 Sprint 2 旧流程和旧接口。
7. 本地曲库匹配必须标记为 matched，不能描述为实时 AI 生成。
8. OCR 或 Qwen 不可用时必须返回可理解的降级状态，问卷链路仍可完成。
9. 不上传环境变量文件、API Key、数据库密码、真实患者资料或可识别个人身份的信息。

## 4. 分支与合并顺序

1. PR #45：Sprint 3 文档
2. PR #44：医学知识与问卷规则
3. fix/sprint3-backend-integration
4. integration/sprint3-ai-v2
5. integration/sprint3-frontend-v2
6. release/sprint3-competition

任何阶段未达到合并门槛，后续依赖阶段不得越过它进入 dev。

## 5. 分阶段设计

### 5.1 规划文档

审查 PR #45，确认只包含 Sprint 3 合同、演示、发布、总结、集成门槛和本设计文档。字段、接口和用户流程一致后，以普通 Merge Commit 合并到 dev。

### 5.2 医学知识

审查 PR #44 的问卷映射、候选证型和医学安全说明。确认没有无关代码、没有将单个选项直接硬编码为脏腑或调式、完整测试通过后，以普通 Merge Commit 合并。

知识库只提供辅助辨证依据。输出必须称为“状态评估”或“辅助辨证倾向”，不得称为医学诊断。

### 5.3 后端接口

从最新 dev 创建 fix/sprint3-backend-integration，吸收 PR #46 的有效实现并修复：

- 测试环境不得依赖本机 MySQL root 账号或真实数据库；
- v1 兼容错误响应符合既有 Schema；
- warnings 在模型和错误处理器之间类型一致；
- 对外错误原因不得泄露连接串、密码或内部堆栈；
- Feedback V2 成功、失败和个人偏好更新路径通过测试；
- 用户反馈只更新个人偏好，不能修改全局医学知识规则。

修复分支创建新的 PR 指向 dev。替代 PR 合并后，再说明原因并关闭 PR #46；不强制改写或删除成员分支。

### 5.4 AI 三源融合

从完成后端集成的最新 dev 创建 integration/sprint3-ai-v2，以普通合并方式引入 feat/zhongrc。人工解决以下 3 个 add/add 冲突：

- backend/ai_engine/agent_stubs.py
- tests/ai_engine/test_agent_stubs.py
- tests/ai_engine/test_sprint2_demo.py

冲突处理必须保留 Sprint 2 旧行为，同时接入病例文本、自由描述和问卷三源融合，不得整份选择任一分支。

AI 评估要求：

- 输出结构化情绪、身体状态、依据摘要、安全标志和置信度；
- analysis_mode 区分 AI、降级和问卷模式；
- Qwen 失败时切换到规则或问卷评估；
- OCR 失败时允许确认、手工补充或跳过材料；
- 不展示内部思维链，只展示可验证的依据摘要；
- 置信度代表输入完整度、规则一致性和模型输出可解析程度，不代表医学诊断准确率。

### 5.5 前端体验

从最新 dev 创建 integration/sprint3-frontend-v2。不整体合并严重落后的前端分支，只迁移八个业务页面及分析加载状态、三个复用组件、必要源代码静态资源、对应路由和接口调用。

明确排除：

- frontend/unpackage/dist 等构建产物；
- 默认开启的 Mock；
- 无关的大规模样式或目录重构；
- 错误的 v2 后缀 Agent ID、临时 record_id 和未定义接口路径。

前端默认连接真实后端。Mock 只能通过明确的开发环境开关启用，并在界面或日志中可识别。

### 5.6 端到端与发布

从最新 dev 创建 release/sprint3-competition，只处理联调缺陷、演示数据、发布文档和必要安全修复，不再加入新功能。

至少验证三条场景：

1. 无病例：自由描述 + 问卷 → AI 评估 → 音乐匹配 → 多维反馈；
2. 有病例：上传并确认 OCR 文字 → 三源评估 → 可解释结果 → 音乐匹配；
3. 失败降级：OCR 或 Qwen 不可用 → 明确提示 → 问卷模式仍能完成。

## 6. 统一接口与字段

统一接口：

- POST /api/v2/sessions
- POST /api/v2/documents
- PATCH /api/v2/documents/{document_id}/confirmation
- POST /api/v2/assessments
- PATCH /api/v2/assessments/{assessment_id}/confirmation
- POST /api/v2/workflows
- POST /api/v2/music
- POST /api/v2/feedback
- GET /api/v2/sessions/{session_id}

Assessment 核心字段：

- document_id
- document_text
- narrative_text
- questionnaire_answers
- analysis_mode
- emotion_profile
- physical_profile
- extracted_evidence
- safety_flags

Agent ID 固定为 assessment_agent、diagnosis_agent、prescription_agent、music_agent、feedback_agent，不添加 v2 后缀。

Music 输出至少包含 music_id、title、source_type、stream_url、mode、bpm、duration_seconds 和 instruments。当前比赛版使用本地曲库参数化匹配，因此 source_type 为 matched。

## 7. 失败与安全路径

| 情况 | 系统行为 | 用户后续操作 |
| --- | --- | --- |
| OCR 超时或无法识别 | 保留文件状态，提示未成功提取，不伪造文本 | 手工录入、重新上传或跳过 |
| Qwen 超时、限流或返回不可解析 | analysis_mode 标记降级，内部记录错误码，不展示敏感详情 | 使用问卷和规则完成评估 |
| 文件格式或大小不支持 | 前后端一致校验并明确提示 | 更换文件或跳过 |
| 严重胸痛、呼吸困难、自伤表达 | 生成高优先级 safety_flags 和求助提示 | 不用音乐建议替代紧急医疗帮助 |
| 音乐资源不可用 | 不返回虚假成功 | 更换本地曲目或提示重试 |
| 反馈提交失败 | 保留当前输入并允许重试 | 不影响已完成播放记录 |

## 8. 测试与合并门槛

每个 PR 合并前必须同时满足：

1. Base 是最新 dev，PR 可合并且没有未解决冲突；
2. Files changed 只包含该阶段范围；
3. 后端完整测试通过，不能只运行新增测试；
4. 前端完成语法、构建和现有测试验证；
5. v1 兼容测试通过；
6. OCR、Qwen 和音乐资源失败路径有自动测试或可重复人工证据；
7. 敏感信息扫描无结果；
8. 没有构建产物、虚拟环境、真实患者资料或无关文档；
9. PR 描述记录测试命令、结果、已知限制和回退方式；
10. 陈家智完成最终范围和演示链路验收。

发生失败时停在当前阶段修复，不把多个失败层混入同一 PR。

## 9. 协作与通知

陈家智负责集成顺序、合同冻结、最终验收和 Merge Commit。仅在以下情况需要成员确认：

- 医学规则或安全文案需要肖宇翔确认；
- 后端原设计意图不明确时需要蔡子鑫确认；
- AI Schema 或降级逻辑有歧义时需要钟睿宸确认；
- 页面交互或资源授权不明确时需要彭翔确认。

Codex 给出可直接转发的完整消息，由陈家智在项目群中发送。一般冲突、测试修复和接口对齐由集成分支完成，不要求成员重复提交相同工作。

## 10. Definition of Done

Sprint 3 同时达到以下条件才算完成：

- 新流程可从欢迎页连续走到完成页；
- 病例、自由描述和问卷可以单独或组合提交；
- OCR 和 Qwen 失败时问卷降级可用；
- Assessment 输出结构化、可解释并包含安全边界；
- Diagnosis 和 Prescription 输出辅助倾向与可解释音乐参数；
- Music 明确返回本地匹配来源并能稳定播放；
- Feedback 2.0 保存前后变化、匹配度、收藏、不喜欢特征和文字反馈；
- 反馈只更新个人偏好，不改变全局医学规则；
- Sprint 2 旧接口和核心演示测试保持通过；
- 三条端到端场景均有测试或录屏证据；
- dev 完整测试通过且无敏感信息；
- 发布清单、演示脚本和已知限制与实际实现一致。
