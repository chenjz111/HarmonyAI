# HarmonyAI Sprint 3 GitHub Issue 规划

> 文档状态：发布前预览  
> 依据：`sprint3-competition-plan.md`、`sprint3-team-tasks.md`、`questionnaire-v2-spec.md`、`feedback-v2-spec.md`、`user-flow-v2.md`、`api-contract-v2.md`、`sprint3-acceptance-checklist.md`  
> 注意：本文中的 `S3-01`—`S3-12` 是本地计划编号，不是尚未创建的 GitHub Issue 编号。未经项目负责人确认，不创建任何远程 Issue、Label、Milestone 或 PR。

## 1. Milestone 预案

- 名称：`Sprint 3 - Competition Upgrade`
- 描述：完成 HarmonyAI 比赛版的用户流程重构、病例与自由文本输入、图文问卷、多源评估、可解释结果、Feedback 2.0、UI 升级和端到端验收。
- 截止日期：`2026-07-31`
- 当前远程检查：未发现任何已有 Milestone。
- 发布策略：收到“确认发布”后再创建；创建前再次查询同名及近似名称。

## 2. Label 预案

### 2.1 已存在，直接复用

- `P0`
- `P1`
- `frontend`
- `backend`
- `knowledge`
- `documentation`

### 2.2 准备新建

- `sprint-3`
- `architecture`
- `testing`
- `security`
- `ui-ux`
- `blocked`
- `release`

### 2.3 可能重复，需确认

- 计划名称：`ai-agent`
- 已有近似 Label：`ai-engine`
- 建议：复用现有 `ai-engine`，避免创建意义重复的 `ai-agent`。本文仍保留需求原文中的 `ai-agent`，发布时需由陈家智确认最终映射。

不删除、不改名、不改色任何现有 Label。

## 3. GitHub Assignee 映射

| 姓名 | GitHub 用户名 | 识别依据 | 是否确定 |
|---|---|---|---|
| 陈家智 | `chenjz111` | Git 提交中“陈家智”和 `chenjz111` 使用同一邮箱；当前仓库 Owner/Admin；PR 作者 | 是 |
| 肖宇翔 | `xyx123-teach` | 项目文档明确 `nob（肖宇翔）`；`feat/nob` 的 PR 作者为 `xyx123-teach`；仓库 Collaborator | 是 |
| 钟睿宸 | `greenlasso` | `feat/zhongrc` 的 PR 作者和主要提交作者为 `greenlasso`；仓库 Collaborator | 是 |
| 蔡子鑫 | `SuuuperCorn` | `feat/caizx` 的 PR 作者为 `SuuuperCorn`；仓库 Collaborator | 是 |
| 彭翔 | `Paimeng835` | Git 中“彭翔”和 `Paimeng835` 使用同一邮箱；`feat/pengx` PR 作者；仓库 Collaborator | 是 |

## 4. Issue 总览与依赖

| 计划编号 | 负责人 | 简称 | 主要依赖 | 截止日期 |
|---|---|---|---|---|
| S3-01 | 陈家智 | 架构与契约冻结 | 无 | 2026-07-28 |
| S3-02 | 陈家智 | 管理、验收与发布计划 | S3-01 | 2026-07-31 |
| S3-03 | 肖宇翔 | 问卷与计分规则 | S3-01 | 2026-07-29 |
| S3-04 | 肖宇翔 | 安全规则与医学审核 | S3-01、S3-03 | 2026-07-29 |
| S3-05 | 钟睿宸 | 三源评估融合 | S3-01、S3-03、S3-07 | 2026-07-29 |
| S3-06 | 钟睿宸 | 可解释辨证与异常测试 | S3-04、S3-05 | 2026-07-30 |
| S3-07 | 蔡子鑫 | 材料上传与 Session | S3-01 | 2026-07-29 |
| S3-08 | 蔡子鑫 | Feedback 2.0 API | S3-01 | 2026-07-30 |
| S3-09 | 彭翔 | 入口、上传、描述、问卷 | S3-01、S3-03、S3-07 | 2026-07-30 |
| S3-10 | 彭翔 | 结果、播放器、反馈 | S3-05、S3-06、S3-08、S3-09 | 2026-07-30 |
| S3-11 | 陈家智 + 全员 | 三路径 E2E | S3-04—S3-10 | 2026-07-31 |
| S3-12 | 陈家智 | 比赛版本冻结与发布 | S3-02、S3-11 | 2026-07-31 |

主依赖链：

```text
S3-01 架构冻结
  ├─ S3-03 问卷规则 ── S3-04 安全审核
  ├─ S3-07 上传后端 ─┐
  ├─ S3-05 三源融合 ─┴─ S3-06 可解释AI
  ├─ S3-08 Feedback API
  └─ S3-09 前端入口 ── S3-10 前端结果与反馈
                          ↓
                     S3-11 E2E
                          ↓
                     S3-12 发布
```

## 5. Issue 详细预览

### S3-01

- Issue 标题：`[Sprint3][Architecture] 冻结用户流程V2与Agent Contract V2`
- 业务负责人：陈家智
- GitHub Assignee：`chenjz111`
- Priority：P0
- Labels：`sprint-3`、`P0`、`architecture`、`documentation`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-28

#### 任务背景

Sprint 2 已跑通五 Agent 链路，但入口、问卷、接口字段和用户端医学表达不满足比赛版要求。必须先冻结八页流程和 v2 契约，才能避免 AI、后端和前端各自定义字段。

#### 详细任务

- 审核并冻结用户流程 V2；
- 确定病例、自由文本、问卷三种输入路径；
- 确定 Assessment、Diagnosis、Music、Feedback 的 v2 Contract；
- 确定 OCR 和 Qwen 的降级逻辑；
- 明确状态评估、辅助辨证和非医学诊断边界；
- 统一 `assessment_agent`、`music_agent` 及旧 ID 别名；
- 审核所有 Sprint 3 PR 的架构兼容性。

#### 输出文件或代码模块

- `docs/user-flow-v2.md`
- `docs/api-contract-v2.md`
- `docs/agent-contract-v2.md`（计划新增）
- `docs/sprint3-competition-plan.md`

#### 验收标准

- 三种输入路径均有明确字段；
- 旧版本请求有兼容方案；
- Agent 之间不存在字段冲突；
- P0 与 P1 边界清晰；
- OCR/Qwen 降级状态机器可读；
- 全体成员已确认接口。

#### 依赖 Issue

- 无。

#### 阻塞 Issue

- S3-03、S3-05、S3-07、S3-08、S3-09。

#### PR 拆分建议

- PR A：流程与 API 文档冻结；
- PR B：Agent Contract V2；仅文档和 Schema，不混入业务实现。

### S3-02

- Issue 标题：`[Sprint3][Management] 完成验收、演示和比赛版本发布计划`
- 业务负责人：陈家智
- GitHub Assignee：`chenjz111`
- Priority：P0
- Labels：`sprint-3`、`P0`、`documentation`、`testing`、`release`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-31

#### 任务背景

比赛截止期短，需要用统一 DoD、演示案例和发布门禁控制范围，防止最后一天继续增加功能。

#### 详细任务

- 维护 Sprint 3 Definition of Done；
- 管理 Milestone 和 Issue；
- 审核 PR；
- 准备三个演示场景；
- 准备老师汇报和比赛演示脚本；
- 组织最终联调和版本冻结；
- 在全部验收通过后创建比赛版本 Tag。

#### 输出文件或代码模块

- `docs/sprint3-acceptance-checklist.md`
- `docs/demo-script.md`（计划新增）
- `docs/release-checklist.md`（计划新增）
- `docs/sprint3-final-report.md`（计划新增）

#### 验收标准

- 三个演示场景可稳定运行；
- 所有 P0 Issue 关闭；
- 无阻塞 Bug；
- 无密钥提交；
- 有稳定版本 Tag 和回退版本；
- 演示视频可完整展示主流程。

#### 依赖 Issue

- S3-01、S3-11。

#### 阻塞 Issue

- S3-12。

#### PR 拆分建议

- PR A：演示与验收文档；
- PR B：最终发布文档和 README，待 S3-11 通过后提交。

### S3-03

- Issue 标题：`[Sprint3][Knowledge] 完成问卷V2与评分规则`
- 业务负责人：肖宇翔
- GitHub Assignee：`xyx123-teach`
- Priority：P0
- Labels：`sprint-3`、`P0`、`knowledge`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-29

#### 任务背景

旧版 30 题和 1—5“像我”量表不符合老师提出的 3 分钟图文问卷要求，需要将已冻结的 Questionnaire V2 变成程序可读取数据。

#### 详细任务

- 审核 `questionnaire-v2-spec.md` 中的 12 题；
- 将问卷转为程序可读取 JSON；
- 完成天气、海面、电池等图形题定义；
- 完成 0—4 频率量表；
- 定义每道题的维度、权重和计分逻辑；
- 禁止单题直接决定证型、脏腑或调式；
- 组织试答，保证 3 分钟内能够完成。

#### 输出文件或代码模块

- `knowledge/questionnaire-v2.json`
- `knowledge/questionnaire-scoring-v2.json`
- `docs/questionnaire-v2-design.md`

#### 验收标准

- 每题有唯一 `question_id`；
- 每个选项有明确 `value`；
- 每个计分项有维度与权重；
- 图形题有资源需求说明；
- 程序能够读取；
- 不存在诱导或直接医学诊断表述。

#### 依赖 Issue

- S3-01。

#### 阻塞 Issue

- S3-04、S3-05、S3-09。

#### PR 拆分建议

- 单独一个知识数据 PR；JSON、设计说明和校验测试一起提交，不混入前端组件。

### S3-04

- Issue 标题：`[Sprint3][Knowledge] 完成安全规则、医学表达和演示案例审核`
- 业务负责人：肖宇翔
- GitHub Assignee：`xyx123-teach`
- Priority：P0
- Labels：`sprint-3`、`P0`、`knowledge`、`security`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-29

#### 任务背景

当前风险检测主要覆盖部分自伤关键词，且旧文档存在反馈影响全局规则的设计。比赛版需补齐身体急症提示并统一非诊断表达。

#### 详细任务

- 审核辅助辨证和音乐推荐文案；
- 增加严重胸痛、呼吸困难、自伤风险等安全规则；
- 设计三个比赛演示案例；
- 为每个案例提供问卷输入、预期状态画像、辅助辨证倾向和推荐理由；
- 审核反馈字段是否错误影响全局医学知识；
- 明确正式紧急联系方式需按上线地区合规配置。

#### 输出文件或代码模块

- `knowledge/safety-rules.json`
- `docs/medical-wording-guidelines.md`
- `docs/demo-cases-medical-review.md`

#### 验收标准

- 高风险表达能触发确定性安全提示；
- 系统不使用确诊、治疗、治愈等绝对医学表述；
- 三个演示案例可解释；
- 用户反馈只影响个人偏好；
- Qwen 不可用时安全规则仍有效。

#### 依赖 Issue

- S3-01、S3-03。

#### 阻塞 Issue

- S3-06、S3-10、S3-11。

#### PR 拆分建议

- PR A：安全规则数据；
- PR B：医学文案与案例审核，便于独立审阅。

### S3-05

- Issue 标题：`[Sprint3][AI] 实现病例、自由文本和问卷三源评估融合`
- 业务负责人：钟睿宸
- GitHub Assignee：`greenlasso`
- Priority：P0
- Labels：`sprint-3`、`P0`、`ai-agent`（发布前确认是否复用 `ai-engine`）
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-29

#### 任务背景

现有 Assessment 支持问卷和 `narrative_text`，但没有病例来源、统一三源 Schema、来源追踪和完整冲突处理。

#### 详细任务

- 接收用户确认后的病例提取文本；
- 接收 `document_id` 与用户确认后的 `document_text`；
- 接收 `narrative_text`；
- 接收 `questionnaire_answers`；
- 输出统一 `emotion_profile`、`physical_profile`、`life_events`；
- 输出 `extracted_evidence`、`safety_flags`、`analysis_mode`；
- 保留问卷确定性分数；
- 保留 Qwen 和 OCR 失败降级；
- 标记来源冲突和缺失信息。

#### 输出文件或代码模块

- `backend/ai_engine/assessment_v2.py` 或现有 Assessment 的兼容扩展
- `backend/ai_engine/questionnaire_v2.py`
- `backend/ai_engine/safety_rules.py`
- `backend/app/schemas/assessment_v2.py`
- `tests/ai_engine/test_assessment_v2.py`
- `tests/ai_engine/test_safety_rules.py`

最终文件名以 S3-01 契约为准，避免重复模块。

#### 验收标准

- 支持病例 + 文字 + 问卷；
- 支持文字 + 问卷；
- 支持仅问卷；
- OCR 失败不返回 500；
- Qwen 失败不返回 500；
- 输出通过 Pydantic 校验；
- Evidence 可追溯来源；
- 不由单个答案直接决定中医证型。

#### 依赖 Issue

- S3-01、S3-03、S3-07。

#### 阻塞 Issue

- S3-06、S3-10、S3-11。

#### PR 拆分建议

- PR A：Schema、问卷计分和安全门禁；
- PR B：三源融合与 Qwen 降级；
- 每个 PR 都包含对应测试。

### S3-06

- Issue 标题：`[Sprint3][AI] 实现可解释辅助辨证与AI异常测试`
- 业务负责人：钟睿宸
- GitHub Assignee：`greenlasso`
- Priority：P0
- Labels：`sprint-3`、`P0`、`ai-agent`（发布前确认是否复用 `ai-engine`）、`testing`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-30

#### 任务背景

旧链路可输出证型和处方，但结果解释与三源依据没有统一结构，且模型自报置信度不等于医学可信度。

#### 详细任务

- Diagnosis 读取多维画像；
- 输出主倾向、辅助倾向和分析依据；
- Prescription 输出音乐参数与推荐原因；
- 增加模型非法 JSON、超时、字段缺失测试；
- 保持规则降级模式；
- 不使用模型自报置信度作为医学可信度；
- 普通日志不记录完整病例和自由文本。

#### 输出文件或代码模块

- Diagnosis/Prescription 现有模块的 v2 兼容扩展
- v2 Agent Schema
- `tests/ai_engine/test_diagnosis_v2.py`
- `tests/ai_engine/test_ai_degradation_v2.py`
- 可解释依据测试数据

#### 验收标准

- 结果页所需解释字段完整；
- Evidence 可以追溯输入来源；
- 模型异常时完整工作流继续执行或安全阻断；
- AI 相关测试全部通过；
- 低可信和冲突状态不会包装为确定结论；
- 普通日志不泄露敏感原文。

#### 依赖 Issue

- S3-04、S3-05。

#### 阻塞 Issue

- S3-10、S3-11。

#### PR 拆分建议

- PR A：可解释 Diagnosis/Prescription 输出；
- PR B：异常、日志脱敏与降级测试。

### S3-07

- Issue 标题：`[Sprint3][Backend] 实现病例材料上传、校验与Session关联`
- 业务负责人：蔡子鑫
- GitHub Assignee：`SuuuperCorn`
- Priority：P0
- Labels：`sprint-3`、`P0`、`backend`、`security`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-29

#### 任务背景

当前没有文档上传、OCR 适配、材料确认和 Session 查询能力。病例属于敏感信息，必须先完成校验、临时存储和日志边界。

#### 详细任务

- 支持 JPG、PNG 和限定 PDF；
- 完成文件类型、签名、大小和页数校验；
- 返回 `document_id`；
- 支持删除、确认和跳过；
- 与 `session_id` 关联；
- OCR 失败时保留文件状态并继续流程；
- 避免敏感数据进入普通日志；
- 不暴露本地绝对路径。

#### 输出文件或代码模块

- v2 Document Router 与 Schema
- OCR Provider 适配层
- Document 数据模型和增量迁移
- Session 查询扩展
- 文件安全、OCR 降级和数据库测试

#### 验收标准

- 图片上传成功；
- PDF 上传成功；
- 非法文件返回明确错误；
- 不上传也能继续；
- 不暴露本地绝对路径；
- 记录可通过 `session_id` 查询；
- 文件处理失败不会破坏主流程；
- 未确认 OCR 文本不作为可靠输入。

#### 依赖 Issue

- S3-01。

#### 阻塞 Issue

- S3-05、S3-09、S3-11。

#### PR 拆分建议

- PR A：上传校验、临时存储和迁移；
- PR B：OCR 适配、确认和 Session 查询；
- 不与 AI 融合实现放在同一 PR。

### S3-08

- Issue 标题：`[Sprint3][Backend] 实现Feedback 2.0 API与持久化`
- 业务负责人：蔡子鑫
- GitHub Assignee：`SuuuperCorn`
- Priority：P0
- Labels：`sprint-3`、`P0`、`backend`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-30

#### 任务背景

旧接口主要接收星级和评论，无法记录听前听后、音乐匹配度和个人偏好，也存在真实工作流自动写入默认 4 星的问题。

#### 详细任务

- 扩展反馈请求和响应 Schema；
- 保存整体星级、听前听后状态、放松程度和音乐匹配度；
- 保存是否继续、是否收藏、不喜欢的音乐特征和文字反馈；
- 关联 `session_id`、`prescription_id` 与 `music_id`；
- 兼容旧版 `rating`/`overall_satisfaction`；
- 增量迁移可回退；
- 固定禁止全局医学规则自动更新。

#### 输出文件或代码模块

- v2 Feedback Router 与 Schema
- Feedback 模型增量迁移
- 个人偏好存储扩展
- `tests/api/test_feedback_v2.py`
- `tests/api/test_v1_feedback_compatibility.py`

#### 验收标准

- Feedback 2.0 可提交；
- 旧反馈请求仍可处理；
- 数据关联 Session 和曲目；
- 数据可以查询；
- 缺失旧版字段不会被伪造；
- 反馈不修改全局医学知识规则；
- 数据库迁移可回退。

#### 依赖 Issue

- S3-01。

#### 阻塞 Issue

- S3-10、S3-11。

#### PR 拆分建议

- PR A：Schema、迁移与兼容；
- PR B：个人偏好更新和 API 测试。

### S3-09

- Issue 标题：`[Sprint3][Frontend] 重构欢迎页、病例上传、自由描述与问卷V2`
- 业务负责人：彭翔
- GitHub Assignee：`Paimeng835`
- Priority：P0
- Labels：`sprint-3`、`P0`、`frontend`、`ui-ux`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-30

#### 任务背景

当前主入口先展示五音卡片并要求选择情绪，旧问卷 30 题且纯文字。比赛版需改为材料—描述—图文问卷的新入口。

#### 详细任务

- 重构首次进入页面；
- 不再首先展示五音卡片和单一情绪选择；
- 增加病例上传和跳过；
- 保留自由描述和跳过；
- 实现 12 题图文问卷；
- 至少 3 题使用图形或图标卡片；
- 增加问卷进度；
- 完成移动端适配；
- 统一 UI 视觉语言；
- 保留旧页面兼容，不覆盖现有 `survey.vue` 修改。

#### 输出文件或代码模块

- 欢迎、材料、自由描述、问卷 v2 页面
- 图形题、进度和错误状态组件
- `pages.json` 增量路由
- API v2 客户端适配
- 前端页面与表单测试

#### 验收标准

- 用户无需说明即可完成前三步；
- 上传和跳过均有效；
- 自由文本可输入和跳过；
- 图形题可正常选择；
- 页面无大面积无意义留白；
- 页面不再像后台管理系统；
- 网络错误有明确提示；
- 手机端无横向溢出。

#### 依赖 Issue

- S3-01、S3-03、S3-07。

#### 阻塞 Issue

- S3-10、S3-11。

#### PR 拆分建议

- PR A：设计系统、八页路由骨架；
- PR B：上传和自由描述；
- PR C：图文问卷与表单测试。

### S3-10

- Issue 标题：`[Sprint3][Frontend] 重构分析结果、播放器和Feedback 2.0`
- 业务负责人：彭翔
- GitHub Assignee：`Paimeng835`
- Priority：P0
- Labels：`sprint-3`、`P0`、`frontend`、`ui-ux`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-30

#### 任务背景

旧前端提交问卷后直接进入播放器，缺少分析中、可解释结果、结构化 Music Agent 和多维反馈。

#### 详细任务

- 实现 AI 分析加载、成功、降级和安全阻断状态；
- 展示多维状态画像、辅助辨证倾向和输入依据；
- 展示音乐推荐原因；
- 根据 `music_id` 与 `stream_url` 播放；
- 实现 Feedback 2.0 表单；
- 增加错误、重试和降级提示；
- 完成页只展示真实保存结果。

#### 输出文件或代码模块

- 结果页
- 处方与播放器 v2 页
- Feedback 2.0 页
- 完成页
- 音频与反馈组件测试

#### 验收标准

- 用户能够看懂分析依据；
- 不只显示单一情绪标签；
- 音乐可播放和暂停；
- Music Agent 明确标记 `matched`；
- 反馈字段完整；
- 接口失败不白屏；
- Qwen 降级时页面有正常提示；
- 手机端布局可正常使用。

#### 依赖 Issue

- S3-05、S3-06、S3-08、S3-09。

#### 阻塞 Issue

- S3-11。

#### PR 拆分建议

- PR A：分析结果与降级状态；
- PR B：播放器结构化输出；
- PR C：Feedback 2.0 和完成页。

### S3-11

- Issue 标题：`[Sprint3][Testing] 完成三路径端到端联调`
- 业务负责人：陈家智，其他成员协作
- GitHub Assignee：`chenjz111`
- Priority：P0
- Labels：`sprint-3`、`P0`、`testing`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-31

#### 任务背景

主链路必须同时证明多源成功、可选输入跳过和外部 AI 失败三类场景，而不只是单次顺利演示。

#### 详细任务

- 测试病例 + 自由文本 + 问卷；
- 测试自由文本 + 问卷；
- 测试仅问卷；
- 测试跳过病例和自由文本；
- 测试 OCR 失败、Qwen 失败和安全阻断；
- 测试 Feedback 保存；
- 测试旧接口兼容；
- 连续运行至少 10 次；
- 对照 `sprint3-acceptance-checklist.md` 记录证据。

#### 输出文件或代码模块

- E2E 测试脚本和测试数据
- 三场景验收记录
- 缺陷清单及关闭证据
- 演示录屏

#### 验收标准

- 三条主路径全部完成；
- 五 Agent 链路在允许路径上不中断；
- 无阻塞 Bug；
- 异常时可以降级或安全阻断；
- 结果数据可以追踪；
- 前端、后端、Agent 和数据库数据一致；
- 连续 10 次运行记录完整。

#### 依赖 Issue

- S3-04、S3-05、S3-06、S3-07、S3-08、S3-09、S3-10。

#### 阻塞 Issue

- S3-02 最终签收、S3-12。

#### PR 拆分建议

- PR A：自动化测试与固定测试数据；
- PR B：仅包含联调中发现的 P0 修复；不同模块的修复继续拆分。

### S3-12

- Issue 标题：`[Sprint3][Release] 完成比赛版本冻结、文档和发布`
- 业务负责人：陈家智
- GitHub Assignee：`chenjz111`
- Priority：P0
- Labels：`sprint-3`、`P0`、`release`、`documentation`
- Milestone：`Sprint 3 - Competition Upgrade`
- 建议截止日期：2026-07-31

#### 任务背景

比赛版需要可复现启动、无密钥、可回退、可离线演示，不能只在开发者电脑上临时运行。

#### 详细任务

- 更新 README 和运行说明；
- 准备安全的 `.env.example`；
- 清理测试数据、密钥和上传材料；
- 全部验收通过后创建稳定 Tag；
- 准备演示视频、项目介绍、架构图和功能截图；
- 保留可回退版本；
- 记录 Sprint 2 稳定版本位置。

#### 输出文件或代码模块

- `README.md`
- `.env.example`
- 运行和发布说明
- 演示视频与参赛材料清单
- 稳定 Tag 和回退说明

#### 验收标准

- 新成员可以按照 README 运行；
- Git 中没有敏感信息；
- 有最终版本 Tag；
- 有稳定演示视频；
- 报名材料完整；
- 可以回退到 Sprint 2 稳定版本；
- Music 输出统一使用 `music_id`、`title`、`source_type`、`stream_url`、`mode`、`bpm`、`duration_seconds` 和 `instruments`；
- `source_type=matched` 的音乐明确为本地曲库匹配，不被描述为实时生成。

#### 依赖 Issue

- S3-02、S3-11。

#### 阻塞 Issue

- 无；这是 Milestone 的最终发布门禁。

#### PR 拆分建议

- 单独 Release PR，只含发布文档、配置示例和必要清理；
- Tag 在 PR 合并且验收通过后单独创建。

## 6. 相似历史 Issue

当前远程没有 Open Issue。以下已关闭 Issue 与 Sprint 3 主题相似，但交付范围属于 Sprint 1/2，不应视为重复：

| 历史 Issue | 相似点 | 不重复原因 |
|---|---|---|
| #14 Sprint 2：陈家智 — Architecture Review + 联调指挥 | 架构与联调 | 未包含 v2 三源契约和比赛版流程 |
| #15 Sprint 2：钟睿宸 — 五 Agent 实现 | Agent 实现 | 未包含病例输入、三源融合和 Feedback 2.0 |
| #16 Sprint 2：蔡子鑫 — 五接口 + 全链路数据库 | 后端 API | 未包含文档上传、OCR、v2 Session 和新反馈 |
| #17 Sprint 2：彭翔 — 问卷到播放完整流程 | 前端链路 | 仍是旧入口和旧问卷 |
| #18 Sprint 2：nob — 文献签收 + Chroma 知识块 | 医学知识 | 未包含 Questionnaire V2 和新安全规则 |

发布时可在 Sprint 3 Issue 正文中链接这些历史 Issue 作为背景，但不能复用已关闭 Issue 替代新任务。

## 7. 发布前门禁

在收到“确认发布”前，禁止：

- `git commit`
- `git push`
- 创建或修改 Milestone
- 创建或修改 Label
- 创建 Issue
- 创建 Pull Request
- 分配 Assignee
- 修改仓库权限

确认发布后仍应按以下顺序执行：

1. 再次检查 Git 状态和敏感信息；
2. 只暂存批准的 Sprint 3 文档；
3. 展示 staged diff 和文件列表；
4. 创建文档 Commit；
5. Push 文档分支；
6. 再次查询 Milestone、Label 和相似 Issue；
7. 创建缺失 Milestone/Labels；
8. 按依赖顺序创建 12 个 Issue；
9. 最后核对 Assignee、Milestone、Label 和正文。
