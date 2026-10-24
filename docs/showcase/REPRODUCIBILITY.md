# 复现问题定位与剩余边界

日期：2026-10-24。仅调查上轮 8 个收集错误和 Provider 超时，没有重新选择技术路线、修改业务代码或测试断言。代码是固定 S6 文件快照；本分支只以 main 为 Git 祖先。

## 8 个收集错误逐项分类

| 测试模块 | 已复现原因 | 分类 | 本轮处理及现状 |
|---|---|---|---|
| tests/ai_engine/test_chroma_store.py | RuntimeError: Could not determine home directory | 环境：清洁子进程没有用户目录，第三方导入无法初始化 | 给子进程提供 sandbox 内 USERPROFILE/APPDATA/LOCALAPPDATA 后收集错误消失；没有安装依赖或修改源码 |
| tests/ai_engine/test_real_demos.py | 同上 | 环境 | 同上；能收集不代表测试执行或真实检索通过 |
| tests/api/test_questionnaire_v21_submission.py | knowledge/questionnaire-v2.1.json 缺失 | 排除资源 | 本轮不恢复未确认许可的知识资产，仍阻塞 |
| tests/api/test_questionnaire_v22_route.py | knowledge/questionnaire-v2.2.json 缺失 | 排除资源 | 同上 |
| tests/contract/test_sprint6_phase1b_cases_contract.py | tests/fixtures/sprint6_phase1b_cases.json 缺失 | 排除数据 fixture | 原候选未带入 JSON 数据 fixture；不编造替代数据以满足批准案例断言 |
| tests/evals/test_emotion_presence_semantics.py | 无法导入 evals.run_sprint4_eval | 排除的项目内依赖 | evals 目录不在上轮 521 个文件中；不是已证实的 pip 包版本问题，不在本轮增加源文件 |
| tests/knowledge/test_organ_mapping_eval_cases.py | 无法导入 knowledge_organ_eval | 排除的项目内依赖 | 对应 scripts/knowledge_organ_eval.py 未纳入；恢复代码后还需核查其资源依赖 |
| tests/tools/test_stability_smoke_diagnostics.py | tools/stability_music_smoke.py 缺失 | 排除的项目内工具依赖 | 原运维/真实 smoke 工具未纳入；不为通过测试而启用真实调用 |

对照结果：旧环境 **1827 collected / 8 errors**；隔离用户目录配置修正后 **1837 collected / 6 errors**。两次都是收集，不是全量执行。增加的 10 项是之前导入失败模块的可收集用例，不是新增或修改测试。

本轮未发现这 8 个错误能够证明的实际业务源码缺陷；这不等于全库无缺陷。6 项缺失继续保留，不删测试、不减弱断言，也不将“依赖缺失”写成已经解决。

## Provider 超时

全文件诊断输出显示同步用例逐步通过，停在 `test_async_create_matches_sync`（原测试第 680 行）。定时栈回溯显示：

```text
test_async_create_matches_sync
  -> asyncio.run
  -> Windows Proactor event loop initialization
  -> _make_self_pipe
  -> socket._fallback_socketpair
  -> socket.accept (blocked)
```

阻塞发生在事件循环初始化，尚未进入异步 Provider 业务调用。独立运行已有守卫的标准库 socketpair 控制用例，在相同受控环境下也于 20 秒超时并停在相同位置。它不依赖 HarmonyAI Provider。

分类：Windows 运行环境/离线守卫组合相关的 asyncio 基础设施阻塞；操作系统、CPython、网络安全软件或守卫具体交互的底层根因仍为 UNKNOWN。没有依据把它定性为服务商响应超时，也不能声称异步 Provider 已正确工作。

保留完整超时记录后，使用原文件和原断言，显式选择 `-k "not test_async_create_matches_sync"`，得到 **77 passed / 0 failed / 0 skipped / 1 deselected**。这些是 Fake transport、合成音频字节和临时文件测试；不证明真实音乐 API、真实模型或真实音频质量。

没有替换标准库 socketpair、修改事件循环语义、扩宽网络权限、跳过失败代码后宣称全文件通过。后续宜在另行批准的隔离环境中单独验证该异步用例，并记录平台差异。

## 验证条件与记录

本轮使用外部已有离线守卫（SHA-256：`849a4ed307f08555083c29ed1099b52b4b696ce13ee94c8df425eadae4c6f708`），业务路径指向本候选。安装与真实 Provider 调用均未执行。测试子进程使用合成 JWT 配置、隔离 SQLite、媒体和用户目录，禁用自动 pytest 插件、字节码和 pytest 缓存。

Compiler、Stub、Provider 同步和两种 collection 运行取得最终 telemetry，均为 0 未识别阻断、0 记录的放行网络连接。超时运行没有最终 telemetry，不能作为完整网络或测试验收回执。守卫是合作式 Python 防护，不替代操作系统级隔离。

原始诊断日志、栈、命令和结果 JSON 只保存在本地独立 review 目录，不放进候选公开文件。公开文档仅保留筛选后的结果。

## 可运行与不可运行

- 已实际运行：确定性 Prompt 编译测试、LangGraph Stub 分支、Provider 同步 Fake 测试，共 170 项通过。
- 未完成：Provider 异步验证、全量收集与测试、知识资产相关业务链、从零安装、完整 FastAPI App、前端构建及设备体验。
- 未执行：真实 Qwen/Embedding/音乐 API、正式 Chroma 索引构建、真实 MySQL、任何发布操作。

恢复资源或工具应先取得文件级许可和数据来源结论；本快照的源码公开展示不代表缺失资源可对外披露或使用。
