# PF-1B Phase B 隔离业务实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking. 用户已选择当前会话执行，不使用子代理。

**Goal:** 在原 Draft PR #164 交付未授权反馈保存/重放、本人查询、事务安全 tombstone 和旧入口兼容的可运行隔离实现。

**Architecture:** 在显式安装 R1 0013 的临时 SQLite 中运行候选服务。业务服务复用共享 owner/proof/epoch 和候选 DTO/完整性验证；调用方负责完整事务和有界数据库竞争恢复。生产路由与正式迁移保持关闭。

**Tech Stack:** 现有 Python、Pydantic v2、SQLAlchemy、pytest、文件 SQLite，沿用项目测试依赖。

**Spec:** `docs/sprint7/PF1B_PHASEB_DESIGN_20261022.md`

## Global Constraints

- Branch `feat/s7-pf1b-feedback`；PR #164；base `team/s7-m1-w2-baseline`。只普通 merge/push，不 rebase/force push/merge PR。
- 不改正式迁移注册、0011/0012/R1 SQL checksum、共享 ORM exports、main.py、医学、前端和Provider；不建第二 owner state。
- 本计划只实现 consent=false；true、账号抹除/保留裁决、clear receipt和生产API保持Gate。M1学习/旧长期偏好消费持续关闭。
- 不物理删反馈，不改已存fingerprint内容，不补造legacy摘要；candidate facade通过不等于生产旧入口已过滤。
- 不运行真实 Provider，不用真实资料/生产库。测试前核验本机离线保护、DATABASE_URL和临时目录。
- 所有业务测试先RED后GREEN；失败记录准确保留，不删原断言。不批量删除任何文件或目录。

## Review Focus

1. stale ORM identity map不得遮蔽数据库实际内容：Task 3使用Core重读投影及漂移失败测试。
2. 请求expected epoch成为陈旧值但为exact replay时，不得重复写：Task 3同时检查ID、行数和epoch。
3. 同key不同owner的请求不得共享结果：Task 3做A/B隔离与指定event冒用测试。
4. 并发删除与rollback不得多bump或部分提交：Task 2用独立连接/barrier及事务回滚。
5. candidate Schema未安装时不得自动装迁移或自动跳过过滤：Task 5明确拒绝候选适配，旧生产路径保持原基线。

## Task 1：同步与真实基线

**Files:** 不新增业务文件；更新本计划执行记录只写实际证据。

**Interfaces:** 使用当前worktree及远端团队分支，预期当前HEAD `4057d97...`；完整值见设计。

- [ ] 确认工作区：计划/设计文件应先单独提交，其他用户改动不得覆盖。fetch两个分支，记录新HEAD/base/差异。
- [ ] 普通merge `origin/team/s7-m1-w2-baseline`。出现合同冲突时核对具体内容，不能选择整侧覆盖。
- [ ] 运行下文组合命令（新文件尚不存在时，只列已存在的测试）并加入 `tests/api/v3/test_s7_music_library_router_wiring.py`；Expected：实际结果完整记录，基线失败先定位归因，不当成本计划修复范围。
- [ ] 提交合并结果，不夹带业务实现。

## Task 2：补强删除事务

**Files:** 修改 `backend/app/services/v3/feedback_v31_candidate_service.py`；扩展 `tests/api/v3/test_s7_pf1b_candidate_service.py`；新增 `tests/api/v3/test_s7_pf1b_concurrency.py`。

**Interfaces:** 保留 `tombstone_owned_feedback(db, *, principal, feedback_id, expected_epoch, now_utc) -> int`；复用 `lock_owner_music_state`、`advance_feedback_epoch`，无内部commit。

- [ ] 写行为测试：stale epoch拒绝且deleted_at/epoch不变；调用后rollback恢复两者；非UTC拒绝；首次state初始化冲突不被吞为成功；两连接删除同一记录只bump一次；已有ORM缓存不得使第二次写重复bump。barrier/事件协调，不以sleep替代。
- [ ] 单文件执行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_pf1b_candidate_service.py tests/api/v3/test_s7_pf1b_concurrency.py --tb=short`；Expected：新竞争用例先暴露实际缺口，其他错误先修测试环境。
- [ ] 最小修复：owner锁后重读候选行；按条件更新实际rowcount决定bump/重复删除。无owner记录不得泄漏，GET不创建state。
- [ ] 重跑同命令及旧feedback/PF-1A；Expected：相关测试全部通过，事务原子断言保留。
- [ ] 仅提交服务和对应测试，message `fix(s7): enforce candidate tombstone transaction semantics`。

## Task 3：consent=false保存与exact replay

**Files:** 修改候选服务；新增 `tests/api/v3/test_s7_pf1b_save.py`；复用Task 2并发测试。

**Interfaces:** 新增 `save_unconsented_feedback(db: Session, *, principal: AuthPrincipal, request: FeedbackV31, idempotency_key: str, now_utc: datetime) -> FeedbackSavedV31`。复用候选 `request_fingerprint`、`resolve_feedback_playback_proof`、`verify_persisted_feedback_content`、`replay_decision`。true使用内部 `CandidateConsentNotEnabled(ValueError)` 明确拒绝，不新增HTTP code。

- [ ] 写成功路径RED：合成ctx_a/event-a、false、expected_epoch=0；调用后commit，反馈行数增1、内容一致、policy/time=NULL、row.evidence_epoch=0、current_epoch=1、status skipped、learning_applied=false；未commit时第二连接不能观察新记录；rollback撤销反馈及epoch。
- [ ] 写重放/冲突RED：相同owner+key+精确DTO两次得到同feedback_id且行数不增；当前epoch增加后仍同体重放；改post_state或expected_epoch冲突；legacy NULL fingerprint拒绝；tombstone优先；坏DB投影拒绝。含请求选择集重排和false政策回显等规范化等价。
- [ ] 写归属RED：跨owner/event/asset/session、NULL context、asset source_type不符均不生成反馈；true在本切片拒绝且无写入；不可信dict/subclass不得代替精确DTO。
- [ ] 运行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_pf1b_save.py --tb=short`，观察缺失行为导致RED。
- [ ] 按设计顺序实现单事务原语。favorite用现有 `_change_favorite` 参与调用方事务；测试实际变化时library_epoch推进一次，replay不再推进。不得复用旧submit中自行commit的阶段。
- [ ] 保存flush后强制Core SELECT取得DB映射验证；replay同时核对链接的session/task/event及asset类型。不得从请求构造“已存投影”。返回结果只在外层commit成功后有效。
- [ ] 两连接同时提交同key：调用方测试事务驱动在整体rollback后最多重试一次；同体重放、异体冲突，反馈数1、epoch只增加1。保留无witness IntegrityError，不假装成功；不实现生产HTTP提交包装器。
- [ ] 运行save、concurrency及Task 2测试；Expected：全部通过，无隐式commit，无学习函数调用。
- [ ] 单独提交 `feat(s7): persist unconsented candidate feedback with replay`。

## Task 4：内部本人查询

**Files:** 新增 `backend/app/services/v3/feedback_v31_candidate_queries.py`、`tests/api/v3/test_s7_pf1b_reads.py`；现有 `list_owned_feedback` 如需转调，仅保持原签名。

**Interfaces:** `visible_feedback_query(principal, *, music_id: str | None = None)` 返回SQLAlchemy Select；`get_owned_feedback(db, *, principal, feedback_id) -> FeedbackCandidate`，缺失/他人/已删均 `FeedbackNotFound`；`read_owned_feedback_page(db, *, principal, music_id=None, limit=20) -> tuple[list[FeedbackCandidate], int]` 是内部首批读取，暂无cursor、不冒充公开分页接口。

- [ ] 写RED：A/B隔离；删后详情不可读；items与total使用相同谓词；同时间按ID稳定排序；limit=0/101拒绝；music筛选生效；读取不创建state、不推进epoch。
- [ ] 执行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_pf1b_reads.py --tb=short`，Expected：RED来自缺失行为。
- [ ] 使用单一可见性条件实现；内部记录不直接作为HTTP DTO，禁止输出内部PK或评论摘要。
- [ ] 重跑reads、save、candidate service；Expected：全通过。提交 `feat(s7): add isolated owner feedback query services`。

## Task 5：旧入口候选兼容验证

**Files:** 新增 `backend/app/services/v3/feedback_v31_legacy_candidate.py`、`tests/api/v3/test_s7_pf1b_legacy_compat.py`；生产旧路由不修改。

**Interfaces:** `list_legacy_history_candidate(db, principal) -> FeedbackHistory` 调用真实旧history后按候选owner可见ID过滤并重算total；`submit_legacy_feedback_candidate(db, principal, request: FeedbackV3, idempotency_key: str)` 返回原旧submit元组，在任何旧commit之前按owner+key检查tombstone。使用 `FeedbackGone`，尚不映射为公开HTTP错误。

- [ ] 写RED：真实旧V3.0请求仍保存；普通旧key重放保持原合法语义；被tombstone的旧key不得复活；history的items/total排除已删；跨owner不泄漏；缺候选Schema显式失败且不安装迁移；comment hash不被当成可恢复正文；历史profile和PF-1A关学习维持。
- [ ] 执行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_pf1b_legacy_compat.py --tb=short`，Expected：缺失candidate facade RED。
- [ ] 最小实现facade，只在测试本地应用调用；复用旧业务服务，不复制Favorite/owner算法。任何需要更改生产路由、正式ORM或错误码的部分到此停止。
- [ ] 单独记录旧submit内部commit导致的并发窗口：本任务的顺序facade测试不作为删除ACK之后旧POST/replay安全的证据。最终统一旧事务及响应前复核另待接线批准；不得将其列为已完成。
- [ ] 重跑compat及原 `test_feedback.py`、`test_s7_preference_invalidation.py`；Expected：通过，原断言不删减。提交 `test(s7): verify legacy feedback tombstone compatibility in isolation`。

## Task 6：组合验收与原Draft交付

**Files:** 仅更新PR正文及本计划交付记录，不添加运行产物。

- [ ] 运行：

```text
python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_pf1b_candidate_service.py tests/api/v3/test_s7_pf1b_save.py tests/api/v3/test_s7_pf1b_reads.py tests/api/v3/test_s7_pf1b_concurrency.py tests/api/v3/test_s7_pf1b_legacy_compat.py tests/api/v3/test_int2_feedback_0013_candidate.py tests/api/v3/test_int2_feedback_0013_mysql_static.py tests/api/v3/test_int2_pf1b_contract.py tests/api/v3/test_s7_feedback_consent.py tests/api/v3/test_s7_feedback_fingerprint.py tests/api/v3/test_feedback.py tests/api/v3/test_s7_preference_invalidation.py tests/api/v3/test_s7_music_library_router_wiring.py --tb=short
```

- [ ] Expected：准确读取最终结果；任何失败逐项归因，不能以历史139通过替代。真实MySQL、生产API、clear receipt、正式政策/账号删除仍NOT RUN。
- [ ] `git diff origin/team/s7-m1-w2-baseline...HEAD --check`；检查写集无迁移注册、共享状态复制、用户数据/密钥/缓存/数据库。单独自审事务边界、锁后重读、重放及legacy过滤是否同源。
- [ ] 普通push原分支；更新原Draft #164的HEAD/文件/实际测试/CI。区分“隔离service完成”与“正式API未启用”，保留此前全量失败证据。
- [ ] 不转Ready、不merge。正式0013、receipt、政策与生产旧入口接线应由Owner明确批准后另排计划。

## 计划自审结论

范围已映射：删除→Task2；保存/重放/竞争→Task3；本人查询→Task4；旧入口兼容→Task5；验证/交付→Task6。五项Review Focus均有相应测试。clear完整实现及正式签名cursor有意留在未批准范围；本计划不创造其表、字段、HTTP code或通过数量。
