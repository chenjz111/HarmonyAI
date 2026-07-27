# HarmonyAI Sprint 3 团队任务分工

> 本文列出计划修改或新增的文件。除本文档已存在的规划文件外，下列业务文件不代表当前已经创建或实现。

## 1. 分工原则

- 陈家智负责范围、架构、接口冻结、最终集成和演示，不承担所有人的零散补丁；
- 医学规则与产品文案必须由肖宇翔审核；
- 多源融合和 Agent 契约由钟睿宸统一，避免前后端各自定义；
- 数据库、上传安全和接口错误由蔡子鑫统一；
- 页面和交互组件由彭翔统一，其他成员不直接修改核心页面样式；
- 每个 PR 只解决一个主题，先合契约和测试，再合实现；
- 任何反馈数据都不得自动修改全局医学知识规则。

## 2. 陈家智：Project Leader & AI Architect

### 主要任务

1. 冻结 Sprint 3 P0/P1/Out of Scope；
2. 确认八页流程、对外定位、演示案例和产品文案；
3. 统一 Agent 命名、输入输出、降级状态与错误码；
4. 审核多源评估是否保留来源、冲突和缺失信息；
5. 审核 Music Agent 是否诚实标记本地匹配模式；
6. 组织 7 月 30 日集成冻结和 7 月 31 日最终验收；
7. 准备教师汇报、比赛讲稿、演示录屏和备用方案。

### 计划输出文件

- `docs/sprint3-competition-plan.md`
- `docs/api-contract-v2.md`
- `docs/sprint3-acceptance-checklist.md`
- `docs/demo-script-sprint3.md`（P1）
- 对 `backend/ai_engine/` 下 Agent 契约变更进行代码审查

### 验收标准

- P0 范围在 7 月 28 日结束前冻结；
- API 字段在前后端开发前完成确认；
- 所有用户端文案无“医学诊断”“治疗保证”等越界表达；
- 三条端到端场景均由本人现场复测；
- 演示同时准备在线模式、降级模式和录屏模式；
- 最终版本只包含已验收功能，不临时加入 Out of Scope 功能。

### 依赖

- 依赖肖宇翔确认问卷和医学措辞；
- 依赖钟睿宸提交 Agent Schema；
- 依赖蔡子鑫确认接口与数据库可实现性；
- 依赖彭翔提供页面流程和真机反馈。

## 3. 肖宇翔：Medical Knowledge Engineer

### 主要任务

1. 审核 12 题问卷的时间范围、措辞、选项和计分维度；
2. 确认天气、海面、电池等题只作表达辅助，不直接决定辨证；
3. 审核“状态评估—情志映射—辅助辨证倾向”的解释链；
4. 定义严重胸痛、呼吸困难、自伤风险等安全提示触发条件；
5. 审核中医术语、证型依据、五行五音映射和证据级别；
6. 确认用户反馈不会进入全局医学规则自动学习；
7. 提供固定演示案例的预期结果范围，避免演示时过度承诺。

### 计划输出文件

- 审核并签署 `docs/questionnaire-v2-spec.md`
- 审核 `docs/feedback-v2-spec.md` 中医学边界
- `knowledge/v1/` 下经审核的问卷维度与规则数据文件（实施阶段命名后定）
- `docs/sprint3-medical-review.md`（医学审查记录，P1）
- 对安全规则测试用例提供预期结果

### 验收标准

- 12 题全部有明确测量目的且可在 3 分钟内完成；
- 核心计分题全部采用统一的过去 7 天、0—4 频率量表；
- 不存在“选某身体部位就直接得到某脏腑、证型或调式”的硬编码；
- 每个辅助辨证倾向至少能显示一条可理解依据；
- 高风险提示不依赖大模型，可由确定性规则触发；
- 页面固定显示“不构成医学诊断”的说明。

### 依赖

- 需先获得陈家智确认的目标用户和演示时长；
- 向钟睿宸提供可结构化的维度和规则；
- 向彭翔提供最终题目、图形语义和安全文案。

## 4. 钟睿宸：AI Engineering Lead

### 主要任务

1. 定义 Assessment V2 的多源输入与结构化输出；
2. 保证问卷确定性分数不被 Qwen 覆盖；
3. 实现 OCR 确认文本、自由描述、问卷的来源标注与冲突检测；
4. 扩展风险检测到全部输入来源；
5. 完善 Qwen JSON Schema 校验、一次重试和问卷降级；
6. 统一 `assessment_agent` 标准 ID，同时兼容旧 `evaluation_agent`；
7. 定义 Music Agent 结构化输出；
8. 将 Feedback Agent 升级为个人偏好补丁生成器；
9. 删除真实工作流中默认 4 星反馈的产品路径；
10. 编写 Agent 单元测试、降级测试和多源冲突测试。

### 计划输出文件

- `backend/ai_engine/assessment_v2.py` 或对现有 Agent 的兼容扩展
- `backend/ai_engine/questionnaire_v2.py`
- `backend/ai_engine/safety_rules.py`
- `backend/ai_engine/feedback_v2.py`
- `backend/ai_engine/music_agent.py`
- `backend/app/schemas/assessment_v2.py`
- `backend/app/schemas/feedback_v2.py`
- `tests/ai_engine/test_assessment_v2.py`
- `tests/ai_engine/test_feedback_v2.py`
- `tests/ai_engine/test_safety_rules.py`

具体文件名应在 PR-01 契约冻结后确定；不得为了匹配本文而重复创建现有模块。

### 验收标准

- 三种来源均能在输出中追踪；
- 只有问卷、问卷+文本、问卷+材料、三源齐全四种组合均能运行；
- Qwen 未配置、超时、非法 JSON 时输出 `degraded` 且走问卷模式；
- 危险信号触发后不继续生成普通处方；
- Music Agent 返回曲目、模式、音频、音乐参数、解释和版权来源字段；
- Feedback Agent 只返回 `personal_preference_patch`，不返回全局规则修改；
- 新增测试覆盖正常、跳过、冲突、降级和高风险路径。

### 依赖

- 依赖肖宇翔冻结问卷维度和安全规则；
- 依赖蔡子鑫提供文档 OCR 确认文本与持久化接口；
- 输出 Schema 是彭翔联调的前置依赖。

## 5. 蔡子鑫：Backend Platform Engineer

### 主要任务

1. 设计 v2 路由，不破坏现有 `/api/v1/*`；
2. 实现图片/PDF 上传、MIME 与文件签名校验、大小和页数限制；
3. 建立 OCR Provider 适配层、超时、错误码和降级状态；
4. 提供 OCR 文本确认接口，未经用户确认不进入融合；
5. 实现 assessment、workflow、music、feedback 和 session 查询接口；
6. 设计 `documents`、评估来源、Feedback 2.0 与个人偏好存储迁移；
7. 修复 ID 仅按日期生成可能造成的重复风险；
8. 确保日志脱敏、临时文件清理和错误响应一致；
9. 编写 API 契约、文件安全、数据库与兼容性测试。

### 计划输出文件

- `backend/app/routers/v2/document_router.py`
- `backend/app/routers/v2/assessment_router.py`
- `backend/app/routers/v2/workflow_router.py`
- `backend/app/routers/v2/music_router.py`
- `backend/app/routers/v2/feedback_router.py`
- `backend/app/routers/v2/session_router.py`
- `backend/app/models/document.py`
- 现有模型的增量迁移文件
- `backend/app/services/ocr_provider.py`
- `tests/api/test_documents_v2.py`
- `tests/api/test_workflow_v2.py`
- `tests/api/test_feedback_v2.py`
- `tests/api/test_v1_compatibility.py`

目录和文件名均为建议，实施时应优先沿用项目既有组织方式。

### 验收标准

- JPG、PNG、限定 PDF 可上传，非法类型、超限和损坏文件被拒绝；
- OCR 超时不会阻断会话，且用户可跳过；
- 原始病例默认临时保存并按策略清理；
- v2 响应满足已冻结 Schema；
- `GET session` 能返回当前步骤、降级状态和各 Agent 摘要；
- v1 接口行为和旧测试不回退；
- 失败时不写入伪造成功数据，不在日志记录原文。

### 依赖

- 依赖陈家智冻结 API 契约；
- 依赖钟睿宸定义 AI 层输入输出；
- 需向彭翔提供可联调的 mock 与错误码清单。

## 6. 彭翔：Client Engineer

### 主要任务

1. 将主流程重构为八个页面；
2. 设计统一色彩、字号、卡片、按钮、间距和状态组件；
3. 病例上传页支持选择图片/PDF、预览、进度、失败、重试和跳过；
4. 自由描述页提供引导文案和字数提示；
5. 实现 12 题图文问卷及 0—4 频率量表；
6. 实现评估页加载、成功、降级、安全阻断和重试状态；
7. 实现可解释依据、来源标签和非诊断声明；
8. 展示 Music Agent 结构化参数并播放本地音频；
9. 实现 Feedback 2.0 的听前基线与听后反馈；
10. 编写页面导航、表单校验和降级 E2E 测试。

### 计划输出文件

- `frontend/pages/welcome/welcome.vue`
- `frontend/pages/document/document.vue`
- `frontend/pages/narrative/narrative.vue`
- `frontend/pages/questionnaire-v2/questionnaire-v2.vue`
- `frontend/pages/result/result.vue`
- `frontend/pages/player-v2/player-v2.vue`
- `frontend/pages/feedback-v2/feedback-v2.vue`
- `frontend/pages/complete/complete.vue`
- `frontend/components/` 下图形题、状态卡、风险提示等复用组件
- `frontend/common/api-v2.js` 或现有 `api.js` 的兼容扩展
- `frontend/pages.json` 增量路由
- `frontend/tests/` 下流程和表单测试

上述是计划路径，不代表当前存在。应避免覆盖用户已经修改的 `frontend/pages/survey/survey.vue`。

### 验收标准

- 首屏不再要求选择单一情绪；
- 八页流程可前进、返回、跳过且不会丢失当前会话；
- 至少 3 道题使用真正可理解的图形或图标卡片；
- 所有错误和降级状态有可操作按钮；
- 小屏设备不横向溢出，关键按钮无需精确点击；
- 加载过程不展示大模型内部思维，只展示进度与依据摘要；
- 本地音频加载失败时能切备用曲目；
- 反馈提交前后状态和体验字段完整。

### 依赖

- 依赖肖宇翔提供最终问卷和文案；
- 依赖钟睿宸、蔡子鑫提供固定 Schema、mock 和错误码；
- 由陈家智统一验收视觉与演示节奏。

## 7. 任务依赖

```text
范围冻结（陈家智）
  ├─ 问卷与安全规则（肖宇翔）
  │    └─ 多源融合与Agent Schema（钟睿宸）
  │          ├─ v2后端接口与持久化（蔡子鑫）
  │          └─ v2前端页面与交互（彭翔）
  └─ API与页面契约（陈家智 + 钟睿宸 + 蔡子鑫 + 彭翔）
                └─ 联调与三场景验收（全员）
```

关键门禁：

- 问卷题目未冻结前，不实现计分；
- API Schema 未冻结前，不并行定义同名字段；
- 后端 mock 未就绪前，前端可做静态页面但不写死响应；
- 三条 E2E 场景未通过前，不录制最终演示；
- 7 月 30 日晚后只修 P0 阻断问题。

## 8. PR 拆分建议

| PR | 内容 | 主要负责人 | 合并前置 |
|---|---|---|---|
| PR-01 | Sprint3 文档、Questionnaire/Feedback/API Schema 冻结 | 陈家智 | 全员审阅 |
| PR-02 | 问卷维度、医学措辞、安全规则数据 | 肖宇翔 | PR-01 |
| PR-03 | v2 Pydantic Schema、问卷计分、多源 Assessment | 钟睿宸 | PR-01、PR-02 |
| PR-04 | 文件上传、OCR 适配、临时存储与数据库迁移 | 蔡子鑫 | PR-01 |
| PR-05 | workflow、music、session v2 接口与 v1 兼容 | 蔡子鑫 | PR-03、PR-04 |
| PR-06 | 八页骨架、设计系统和问卷交互 | 彭翔 | PR-01、PR-02 |
| PR-07 | 结果、播放器与 Feedback 2.0 联调 | 彭翔 + 钟睿宸 | PR-03、PR-05、PR-06 |
| PR-08 | E2E、降级、隐私与提交修复 | 全员 | 前述 PR |

每个 PR 必须包含：

- 变更目的和不做内容；
- 对应验收项；
- 测试命令及结果；
- 页面变更截图或接口请求响应；
- 是否影响 v1；
- 回滚方式。
