# 本候选验证记录

日期：2026-10-24（北京时间）。Git 祖先：main `30b72cff6ce90f820aca13c19577b242ffcdddb7`。业务文件快照来源：`8e32975607fe96f56852a2b7f7c0ae8f959cb191`；未导入其历史。状态：LIMITED OFFLINE VERIFICATION；不是完整 App 验收。

## 本轮实际结果

环境：Windows、Python 3.12.10、已安装 pytest 9.1.1；未安装依赖，未构建前端或启动服务。清洁子进程只接收必要系统变量与合成配置，禁用 pytest 第三方自动插件及字节码/pytest 缓存；SQLite 和测试临时目录隔离。

| 检查 | 实际结果 | 范围/限制 |
|---|---|---|
| 原样源码校验 | 521 个纳入文件 SHA-256 与固定上游一致，0 差异 | 不证明行为正确或公开许可 |
| Python 静态解析 | 348 个 Python 文件，0 语法错误 | AST 解析，不导入模块、不执行业务 |
| 原 Prompt Compiler 测试 | **91 passed / 0 failed / 0 skipped**，退出 0 | `tests/ai_engine/v3/test_prompt_compiler_v2.py` |
| 原 LangGraph Stub 测试 | **2 passed / 0 failed / 0 skipped**，退出 0 | `tests/ai_engine/test_langgraph_workflow.py`；不证明真实模型节点 |
| TokenHub Provider 同步 Fake 测试 | **77 passed / 0 failed / 0 skipped / 1 deselected**，退出 0 | 未选择 `test_async_create_matches_sync`，该用例另行诊断超时；不称全文件通过 |
| Provider 全文件与异步用例 | **TIMEOUT 45s / NOT VERIFIED** | 调用栈停在 Windows socketpair accept，独立标准库控制用例也超时；底层环境根因未完全确认 |
| 全 tests 收集（修正隔离用户目录后） | **1837 tests collected，6 collection errors**，退出 2 | 仅 collect-only；旧环境的 1827/8 也已复现，详见 REPRODUCIBILITY.md |
| H5 / Android / MySQL / 正式 Chroma 索引 / 真实 Provider | **NOT RUN** | 缺资源、权限或未在本轮范围 |

Compiler、Stub 和 Provider 同步部分共 170 个原测试通过；Provider 异步 1 项未完成。不能称为全量通过或整个项目可运行。同步筛选没有删除测试、改断言或用 Mock 替换原实现；异步失败与收集错误单列保留。

## 离线保护器与验证基础设施

使用外部已有 `tools/ci/guarded_pytest.py`（S7 CI 工具所在独立环境）保护所选 S6 测试；未将 S7 应用代码、规则或接口混入候选。外部执行器不是本候选的原业务代码，尚未打包为可公开复现的独立工具。

上一轮保护器自检历史（不是本轮新结果）：

1. 全部 24 项自检尝试在 180 秒超时；35 秒定位运行停在本机标准库 socketpair 用例，根因未完全核实。
2. 明确选择 22 项、未选择 socketpair 与 asyncio self-pipe 两项后，第一次得到 17 passed / 5 failed，原因是本轮外部启动脚本遗漏 `CI_DB_SANDBOX`；这不是业务代码缺陷。
3. 修正启动脚本环境后，同一 22 项得到 **22 passed / 0 failed / 0 skipped / 2 deselected**；全部预期阻断探针完成。未修改上游测试和断言。两个未完成的自检仍为 NOT VERIFIED。

本轮 Compiler、Stub、Provider 同步和 collection 的 telemetry 均记录：0 未识别阻断，0 放行的真实网络连接，退出码与相应结果一致。Provider 超时未产出最终 telemetry，不使用它证明通过或完整网络验收。保护器针对合作式 Python 进程，不是操作系统级隔离，也不证明任意原生扩展无法外联。

## 精确用例与命令说明

实际通过外部启动脚本执行，每套使用独立 sandbox 与 telemetry；脚本、完整命令、JSON、原始失败和超时记录保留在本地审核目录，不纳入公开候选日志。

内部 pytest 参数分别为：

```text
# Compiler
-q --tb=short tests/ai_engine/v3/test_prompt_compiler_v2.py
# LangGraph Stub
-q --tb=short tests/ai_engine/test_langgraph_workflow.py
# Provider 同步部分：77 passed / 1 deselected
-q --tb=short -k "not test_async_create_matches_sync" tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py
# Provider 全文件：45 秒超时，不是通过结果
-vv --setup-show --tb=short tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py
# Collection
--collect-only -q --tb=short tests
```

每次另显式传入本候选 pyproject/rootdir、`-p no:cacheprovider`、sandbox 内 basetemp，以及外部保护器的 source-root、sandbox-root 和 telemetry 路径。以上参数不是建议在生产环境或携带真实凭据时直接裸跑的命令；复现须先具备相同的获批准保护环境。

## 全量收集阻塞

旧环境下 8 个收集错误已复现。其中前两个是缺少用户目录导致；在 sandbox 内提供 USERPROFILE/APPDATA/LOCALAPPDATA 后已消失，增加收集到 10 项。其余 6 个依赖被裁剪的资源或项目内辅助模块，仍然保留。逐项分类见 [REPRODUCIBILITY.md](REPRODUCIBILITY.md)。原 8 个模块为：

- `tests/ai_engine/test_chroma_store.py`
- `tests/ai_engine/test_real_demos.py`
- `tests/api/test_questionnaire_v21_submission.py`
- `tests/api/test_questionnaire_v22_route.py`
- `tests/contract/test_sprint6_phase1b_cases_contract.py`
- `tests/evals/test_emotion_presence_semantics.py`
- `tests/knowledge/test_organ_mapping_eval_cases.py`
- `tests/tools/test_stability_smoke_diagnostics.py`

已确认的 6 项残留原因分别是 knowledge/questionnaire-v2.1.json、knowledge/questionnaire-v2.2.json、tests/fixtures/sprint6_phase1b_cases.json、evals.run_sprint4_eval、scripts/knowledge_organ_eval.py、tools/stability_music_smoke.py 缺失。它们都在上一轮裁剪范围之外；没有在本轮擅自恢复文件。未发现能由这 8 个错误证明的新业务实现缺陷，也不据此推断整个代码库没有缺陷。

## 历史证据：不能代替本轮结果

- [S6 Compiler 历史 CI](https://github.com/chenjz111/HarmonyAI/actions/runs/36745146849)：源 `13e294f9774d6cfec6be59b2e003c33e41e75b11` 的成功记录，不能当作裁剪后候选的全量验收。
- [S6 Player 历史 CI](https://github.com/chenjz111/HarmonyAI/actions/runs/36807380627)：源 `4d935bb88475560617b2a6014192012407f78e9c` 的成功记录。
- 上游 [PR #148](https://github.com/chenjz111/HarmonyAI/pull/148) 的专项/集成数量是历史声明，不挪用成新结果。

原 CI 包含联网安装及构建步骤，本候选未复制为可自动触发的工作流，也未声称有本候选托管 CI。

## 文件快照的 Git 检查

本机 Git 自动换行转换曾使 3 个前端文件的暂存 blob 与原始 blob 不同，未改变工作目录文件。新增 `.gitattributes` 的 `* -text` 后，仅在新候选重新暂存，521 个源码 Git blob 均与来源清单一致；没有重写源码或修改全局 Git 配置。

按允许上游 CRLF 的检查规则，新文档差异检查通过；全快照仍保留原文件 `tests/sprint6_phase1b_fixtures.py:381` 的 EOF 空行格式警告。为保持原内容未改它，该警告不代表业务测试失败或通过。

## 结论

本轮重新验证了新 main 快照候选，已有原源码和有限离线验证证据。完整 App 可运行性、全量测试、视觉、设备、真实 API 和生产安全均未完成。本快照适合代码结构与真实工程实现审阅，但不构成完整 App、CI 或生产运行验收。
