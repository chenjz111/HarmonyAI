# PF-1B Phase B 隔离业务交付记录

日期：2026-10-24。关联 #152 / Draft PR #164。状态：隔离服务层可供复审；正式API/迁移和发布仍关闭。

## 代码与范围

业务验证提交：`0543088dc9a4749e9a1010d26cac72af83457d70`。本记录为其后的纯文档提交，不改变业务代码。
源分支 `feat/s7-pf1b-feedback`；目标 `team/s7-m1-w2-baseline`，已普通合并团队基线 `fcf6770ab4dc944afbcbfe856c5a4a4fab4bd0ce`。

本轮PF业务文件：

- `backend/app/services/v3/feedback_v31_candidate_service.py`：consent=false保存、指定proof、来源校验、DB投影重读、exact replay、原子epoch，以及删除缓存修复。
- `backend/app/services/v3/feedback_v31_candidate_queries.py`：owner/tombstone统一条件、内部详情/首批列表/总数/稳定排序。
- `backend/app/services/v3/feedback_v31_legacy_candidate.py`：显式候选Schema验证，顺序旧history过滤与旧POST tombstone门禁；拒绝V3.1请求误入V3.0接口以及V3.1 key通过旧体重放。
- `test_s7_pf1b_save.py`、`test_s7_pf1b_reads.py`、`test_s7_pf1b_concurrency.py`、`test_s7_pf1b_legacy_compat.py`：真实文件SQLite、独立连接与真实旧服务行为测试。

原R1候选SQL/模型/共享合同未改；生产Feedback ORM、正式0013登记、路由、Provider及学习路径未改。团队合并带来的Library/前端更新不是PF新增写集。

## 本次结果

业务提交上运行下列13个文件，实际额外加载本机 `offline_guard` 插件，并设置内存默认DATABASE_URL、禁止字节码；候选业务使用独立临时文件库。该本机插件不随PR分发，其他电脑执行前需建立等效隔离。

```text
python -m pytest -q -p no:cacheprovider -p offline_guard tests/api/v3/test_s7_pf1b_candidate_service.py tests/api/v3/test_s7_pf1b_save.py tests/api/v3/test_s7_pf1b_reads.py tests/api/v3/test_s7_pf1b_concurrency.py tests/api/v3/test_s7_pf1b_legacy_compat.py tests/api/v3/test_int2_feedback_0013_candidate.py tests/api/v3/test_int2_feedback_0013_mysql_static.py tests/api/v3/test_int2_pf1b_contract.py tests/api/v3/test_s7_feedback_consent.py tests/api/v3/test_s7_feedback_fingerprint.py tests/api/v3/test_feedback.py tests/api/v3/test_s7_preference_invalidation.py tests/api/v3/test_s7_music_library_router_wiring.py --tb=short
```

**199 passed / 0 failed / 0 skipped / 1 warning，79.44秒。** Warning为Starlette/anyio弃用。基线阶段的防护自检验证外部DNS/socket被阻止，允许环回供TestClient使用。真实Provider与生产数据库操作为0。

`git diff origin/team/s7-m1-w2-baseline...HEAD --check`通过。已做作者整分支自审；按用户要求未使用子代理，不冒充独立Review。

全仓收集命令：

```text
python -m pytest --collect-only -q -p no:cacheprovider -p offline_guard tests --tb=short
```

**2510 tests collected / 3 collection errors**，具体为：

1. `tests/evals/test_emotion_presence_semantics.py`：缺 `evals` 模块。
2. `tests/knowledge/test_organ_mapping_eval_cases.py`：缺 `knowledge_organ_eval` 模块。
3. `tests/tools/test_stability_smoke_diagnostics.py`：缺 `tools/stability_music_smoke.py`。

因此本轮不宣称全后端通过。之前扩大V3套件的4个stream 404及1个缺Corpus错误保留为历史证据，本轮未重新运行该扩大套件，不能把旧数量称为当前HEAD结果。GitHub CI以平台实际run为准；当前代码树无`.github/workflows`，本机通过不等于GitHub CI成功。

## 有效行为与边界

新保存只有false路径，政策版本/时间NULL，status=skipped；true直接关闭。指定event/context/session/asset须一致；同key同体复用feedback_id且不再写收藏或推进epoch，异体冲突。行写前epoch与返回当前epoch分开；flush后投影必须来自DB。请求与DB行都不写入日志。

新服务提交由调用方拥有，服务不commit/rollback。失败要求外层整体rollback。SQLite测试调用方使用BEGIN IMMEDIATE；同key竞争和重复删除用两个连接/barrier，SQLite序列化写入不作为MySQL并发证据。

删除已修复实际RED缺陷：旧ORM缓存把第二次删除误当首次，epoch从1增加到2。现在锁后重读与条件更新按DB实际结果推进。详情/列表/total不返回tombstone，读取不创建owner state。

旧兼容facade只在隔离服务调用层测试，生产旧路由尚未接入。旧submit有内部多阶段commit，前置检查不解决检查后删除/响应迟到的并发窗口。不得启用生产删除。最小旧库fixture缺完整Session列导致旧服务查询失败，运行时兼容测试改用真实fresh-init Schema；这不证明所有历史旧库可直接跑完整Session ORM。

## 执行中采用的裁定

1. 本机bash任务脚本不可用，使用计划正文和本机ledger记录；代价是执行账本不由脚本自动生成。
2. 遵守禁止批量删除，保留gitignored scratch；不纳入提交。
3. 按用户要求不使用子代理，作者自审；仍需Owner/独立复审。
4. 比较epoch前刷新共享锁定状态，未修改共享helper；每次写多一次刷新查询，避免旧identity map。
5. SQLite真实竞争验证采用BEGIN IMMEDIATE；IntegrityError向调用方传播，不伪造MySQL竞争恢复或生产重试包装器。
6. legacy运行时使用真实fresh-init；未改共享最小迁移fixture/生产迁移，历史最小Schema运行时兼容仍为已知限制。
7. 带V3.1指纹的key拒绝通过V3.0体重放；普通legacy NULL指纹保持旧合法语义。

## 仍需后续确认

- Owner：正式consent政策/撤销、保留与账号抹除、公开DTO/错误码、clear receipt namespace/期限。
- #150：正式0013、生产ORM/启动、真实MySQL及失败恢复。
- #151：指定播放proof正式落点、生产事务/竞争语义。
- PF后续：正式cursor/公开响应适配、真实旧入口统一过滤和事务、缓存/身份切换/迟到响应、完整clear receipt。

PR保持Draft，不merge，不开启长期学习。本交付完成的是批准计划中的隔离业务切片，不代表完整PF-1B上线。
