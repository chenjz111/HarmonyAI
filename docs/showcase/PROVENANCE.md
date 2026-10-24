# 候选版本、来源与贡献

整理日期：2026-10-24（北京时间）。状态：PUBLIC SHOWCASE SNAPSHOT / OWNER_ATTESTED_SHOWCASE_PERMISSION（项目负责人确认团队源码展示用途；未独立核验各成员原始授权记录）。

## 版本选择

- main 入口基线：`30b72cff6ce90f820aca13c19577b242ffcdddb7`，只有早期文档。
- 选择的唯一业务代码基线：S6 产品恢复 `8e32975607fe96f56852a2b7f7c0ae8f959cb191`。
- 比较过但未复制的 S7 基线：`dc26b3ff04fe72eae2a6f19fa6cd4d1e6c5b7e61`。
- 本地分支：`codex/main-snapshot-candidate-20261024`。未创建公开 PR、未推送、未合并 main。

选择 S6 是因为其已有后端、前端、RAG、Compiler 和 Provider 集成，以及对应历史 PR/CI。它是相对完整的开发线，不是已获正式验收的稳定发布。S7 是独立整理的快照及后续增量，增加音乐库、认证、安全和 CI 等能力，但还有发布与验收 Gate；不将其补丁拼接进 S6，也不把 S7 的安全结论套给 S6。

## 代码整理方式

所有纳入的既有源码逐字节保持上游内容；路径保留，未重新实现功能。源 commit、Git blob、文件 SHA-256、实际作者 UNKNOWN、负责人确认的展示许可状态逐项列在 [SOURCE_MANIFEST.csv](SOURCE_MANIFEST.csv)。新 README、gitignore、showcase 文档由本轮 Codex 按用户要求撰写，不冒充原团队开发成果。

本候选仅以远程 main 的精确 SHA 为 Git 祖先；521 个源码文件从上一轮内部候选按文件快照复制，不 merge/rebase/cherry-pick S6，也不复制其 .git。来源记录仍指向 S6 的真实 commit/blob，不伪造作者或开发提交。展示版经 GitHub 审核流程独立提交；源提交和真实开发历史仍保持不变。

分支可达历史与共享对象库分开核验：共享对象库仍保存其他开发引用的 S6 对象，但这些提交不属于本分支祖先。当前 main 的祖先仍含两张 PNG 等早期文件，其权利风险另列；其他公开分支中的 SQLite 暴露也不会被本候选消除。本快照不能证明其他公开分支的历史数据风险已经消除。

## 团队与个人贡献

本人陈述的职责：产品流程、架构讨论、任务拆解、I/O 合同协调、审查和验收组织。代码由团队共同完成，并使用 AI 编程工具辅助；逐产物分工仍需确认。团队角色和账号活动不是独立作者的充分证据。

以下公开记录可供审阅，但不要将“职责安排”视为“已完成全部功能”：

- [S6 Prompt Compiler #148](https://github.com/chenjz111/HarmonyAI/pull/148)：源 `13e294f9774d6cfec6be59b2e003c33e41e75b11`，代码与历史验收记录。
- [S6 Player #149](https://github.com/chenjz111/HarmonyAI/pull/149)：播放器 seek 和返回流程的团队产出。
- [S7 协调职责 #150](https://github.com/chenjz111/HarmonyAI/issues/150)：说明后续 Owner/Integration 的协调范围，不作为 S6 代码作者证明。
- [后续配置审查意见](https://github.com/chenjz111/HarmonyAI/pull/167#issuecomment-6335820874)：账号会话意见，不是正式独立 Reviewer 批准，代码不在本 S6 候选中。

公开简历中可写“项目负责人，负责产品与接口协调、审查及集成验收组织”；“本人发现并独立修复某缺陷”“独立开发整个系统”需另有明确证据，不能仅由提交账号推断。

## 素材与排除项

没有插入权利来源未确认的截图、原架构图、字体、音频或 Logo。医学 knowledge 目录、原测试 JSON 数据 fixture、环境示例、含种子写入的 backend/init.sql、原内部 docs/HANDOFF/project-memory、原运维与真实 smoke 工具、原网络安装 CI 均未带入。部分代码和测试的资源引用保留，缺失情况如实记录。

目录中的 Prompt 模板属于本次负责人确认的团队源码展示范围；不包括第三方资源，也不授予下游任意复制、修改或商用的开源许可。逐文件作者未知项及第三方依赖义务仍如实保留。
