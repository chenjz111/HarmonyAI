# PF-1B Phase B：隔离业务闭环设计

日期：2026-10-22。状态：实施设计，供 Owner 审查；不批准生产接线。

## 目标及当前事实

在原 Draft PR #164 中补齐可运行的 PF 业务切片：未授权反馈保存、同键重放/冲突、本人读取、一次 tombstone、事务/并发及旧入口兼容验证。所有写入仅在显式安装 R1 0013 的合成数据库中执行。正式 consent=true、保留/账号抹除、clear receipt、生产路由及正式迁移另待批准。

本地实现检查点为 `4057d9735b41cdb55f67126d8763f6d8798d293a`，工作区在设计前干净。已获取团队基线 `fcf6770ab4dc944afbcbfe856c5a4a4fab4bd0ce`；与检查点相比，个人分支 ahead 9 / behind 30。团队新增 PR #163/#166，其中 Music Library 已注册到正式应用；0013 仍未注册。PR #167 尚未合并，不能把其认证改动作为本计划依赖。历史 139 passed 不代表同步后或本计划完成后的结果。

依据：#150/#151/#152；Owner R1 ZIP 来源报告 SHA `5f9a8ad0ec8754084cf9c0eab2ee44d278ed2b51`；当前 `backend/drafts/s7_feedback_consent/contracts.py`、候选 ORM/安装器与三份 INT-2 测试。ZIP 报告 SHA 不作为可 fetch 的提交。

## 选择与文件所有权

采用“显式候选服务 + 真实隔离数据库 + 测试本地接线”。现有 `feedback_v31_candidate_service.py` 扩展保存/重放与删除；新候选查询模块负责过滤、排序与内部读取。复用现有 owner state、epoch、指定播放 proof 和 Phase A 指纹，不克隆这些实现。

直接修改生产 Feedback ORM/启动路径会越过 #150；另建反馈表或 receipt 表会分裂唯一键；以纯 Mock 仓储代替持久化不能证明 FK、Trigger 和回滚。因此均不采用。生产启用前再把已验收候选适配到 #150 的正式模型，而不把 drafts import 永久保留为上线依赖。

仅 PF 新模块/行为测试和必要的候选兼容适配属于本计划写集。R1 SQL、候选模型及共享 helper 保持原始内容；发现问题时报告具体位置，涉及接口修改由 #150/#151 确认。

## 保存和事务

服务新增 `save_unconsented_feedback(db, *, principal, request, idempotency_key, now_utc)`，输入必须为精确 `FeedbackV31`，输出为 `FeedbackSavedV31`。这是内部候选接口，没有 HTTP 路由。`learning_consent=true` 在此切片中显式拒绝；false 回显的政策版本不作为权威保存，版本/时间均为 NULL。

调用方在 SQLite 使用 `BEGIN IMMEDIATE`，以 `autoflush=False` 运行；服务不 commit/rollback。MySQL 的 owner 行锁与竞争恢复仅作设计，不声称已验证。

处理顺序：

1. 校验 DTO、去首尾空白后 1～128 字符的 key 和服务端 UTC 时间；不记录请求正文。
2. 锁定共享 owner state；在 owner 下读取同 key 行。只有此次写事务可创建 state，GET 不创建。
3. 已有行先判 tombstone，再判 legacy NULL fingerprint、同/异 fingerprint；不因当前收藏状态变化重算旧意图。
4. 新写入验证指定 event、owner/asset/context/session 和 Task 终态，并校验 music_ref.source_type 与资产一致；不得用同资产另一次播放替代。
5. exact expected epoch CAS。行的 evidence_epoch 保存写入前 epoch；created_at 为服务端 UTC；原始状态/体验/选择集/播放摘要规范化保存；comment 保持 NULL；处理状态直接 skipped。
6. favorite 非 NULL 时只复用现有 `_change_favorite` 的同事务能力，不调用会自行 commit 的旧公开保存服务，也不修改 Favorite 算法。
7. flush 后用新的 SQL SELECT 重读数据库映射，调用 `verify_persisted_feedback_content`。验证失败必须让调用方整体 rollback，不能把 request.model_dump 冒充数据库投影。
8. 使用共享 helper 推进 feedback epoch；返回新 feedback_id、当前 epoch、replayed=false、learning_applied=false。只有外层 commit 成功才能把结果作为已保存交付。

## 重放与竞争

owner+key 原唯一约束保留。exact replay 不推进 feedback/library epoch，不重复收藏，不重新生成 ID，不启动学习。请求自身的 expected epoch 属于 fingerprint，不自动更新请求后复用旧 key；已存完全相同请求可以在当前 epoch 已增加时重放。

重放除 `replay_decision` 的内容投影核验外，还检查当前 principal 与已存 session/task/event 链接；请求中的公开别名必须与这些权威行一致。fingerprint、内容投影和来源证明分别承担不同职责，不能相互替代。已删行优先返回内部 `FeedbackGone`，不重新授权或创建记录。

唯一键竞争由调用方在整体 rollback 后执行有界数据库事务重试；原服务原语不吞 IntegrityError、不自行 commit。测试事务驱动最多重新执行一次，重新读取已提交见证：同 key 同体走重放、异体冲突；没有见证则继续报告数据库冲突，不能伪造成功。数据库内容/Schema 错误不重试为新写入。生产 HTTP 错误映射不在本阶段确定。

## 本人读取、删除和并发

内部详情/列表/total 使用同一 owner + deleted_at IS NULL 条件；按 created_at DESC、feedback_id DESC 稳定排序。内部查询允许 limit 1～100、默认20及可选 music_id；正式签名 cursor 和公开 DTO 暂不接线。返回内部记录不得直接序列化为 HTTP 响应，尤其不能暴露内部 owner/event row PK。

tombstone 使用现有服务边界，补齐锁后重读/条件更新，保证按数据库实际变化决定是否 bump。重复删除不二次 bump；无记录和其他 owner 统一内部 not-found。首次删除必须 exact epoch；重复已删除请求可以只返回当前 epoch，无二次修改。取消事务应同时恢复 tombstone 和 epoch，历史 profile/current_version_id 保留。

采用两条独立物理连接及 barrier/事件协调复现删除竞争和迟到 CAS；不使用 sleep 碰运气。验证两次删除只有一次实际修改、旧 epoch 写入被拒绝、rollback 无部分状态。SQLite 的串行写入证据不等于 MySQL FOR UPDATE 验收。

## 旧入口兼容

先实现显式候选兼容 facade，复用真实旧 `feedback_service` 的响应模型与业务路径：history 只保留本人未删 ID 并重算 total；legacy POST 在调用真实旧保存前检查 owner+key 的 tombstone。普通旧 V3.0 保存、历史无 fingerprint 行、收藏及 PF-1A 关闭行为保持原有合法语义。

候选 facade 只在测试本地应用挂载，生产 `feedback_router.py` 不启用它。真实旧路由仍不具备 tombstone 保护，因此删除不能上线。未来 #150 正式化后必须把同一过滤/重放门禁接到全部真实入口，再验 HTTP/缓存及身份切换；不能以 facade 测试通过宣称旧 API 已安全。

旧 `submit_feedback` 内有提交阶段，facade前置检查只能证明顺序兼容，不能证明“检查后发生删除”的并发安全。Task 5明确报告这一限制；最终接线须统一旧写事务并在返回/重放处复核权威状态，涉及旧提交语义的改造另交Owner审查。不能把Task 2/3的候选事务保证外推到旧生产入口。

## clear 与发布门槛

当前仅保留已交接 `clear_evidence` 的隔离 CAS/rollback 合同测试，不新增 clear API 或自定 receipt 表/namespace/TTL。Owner 明确 receipt 和保留规则后，另列任务实现整条 clear 路径。保留截止等于 cutoff 的证据失效、历史 profile 只读、迟到派生结果 exact CAS 这些既有候选原则。

发布前仍需：#150 正式 0013/ORM/启动策略及真实 MySQL；#151 指定事件 proof 正式落点；Owner 正式政策/撤销、保留与账号抹除、API/错误码、clear receipt；旧入口和缓存全部过滤；独立复审。PR #164 保持 Draft，不 merge，不开启长期学习。

## 验收及报告

每个新增行为先 RED 后 GREEN。组合运行 PF 服务、保存/重放、并发、旧入口兼容、三份候选合同、Phase A、旧 feedback/PF-1A 以及新增 Library 正式路由测试。仅合成身份、临时文件 SQLite 和 Fake Provider；真实 Provider/生产库为0。

历史全量收集的3项缺依赖，以及扩大 V3 套件的4个 stream 404和1项缺 Corpus 原因持续保留；同步后若结果改变按实际记录，不删除/放宽断言。本轮写设计不运行测试，不新增通过数量。每次代码交付列出精确 HEAD、命令、passed/failed/skipped/warnings、CI状态和未关闭门槛。
