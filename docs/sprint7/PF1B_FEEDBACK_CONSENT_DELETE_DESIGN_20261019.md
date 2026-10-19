# PF-1B 逐条反馈授权、删除与偏好失效设计

状态：设计稿，待 Owner / INT-2 复核；不是冻结 API、迁移批准或上线许可。日期：2026-10-19。

## 1. 目标与边界

依据 [Issue #152](https://github.com/chenjz111/HarmonyAI/issues/152) 和 [#150 共享事务约定](https://github.com/chenjz111/HarmonyAI/issues/150#issuecomment-6184425563)，PF-1B 要让 V3.1 反馈具备逐条授权、本人只读列表、软删除及 clear 后的证据失效，同时保持 Sprint 7 M1 的长期偏好学习关闭。成功标准是：旧 V3.0 合法反馈仍可保存，历史 profile 与已生成快照可读；新旧入口、幂等重放及并发迟到结果不能复活已删除或已清除的证据；无真实 Provider、生产数据库或隐式身份推断。

本设计仅覆盖 Preference lane。INT-2 #150 独占正式 0013 迁移、共享模型导出和 `main.py` 注册；Backend #151 提供音乐访问、播放 context 与 owner-state helper。PF-1B 不复制这些实现，不改前端、医学证据、Diagnosis、Prescription、Provider、GenerationSpec、旧资源 checksum 或 Teacher Flow，不重新开启长期学习，也不新增自由文本评论存储。

## 2. 当前可核实的基线

- 编写本设计前，本地隔离分支 `feat/s7-pf1b-feedback` 位于 `5b3da2d17e44615985cb870cd0d2182bc00927f2`，无既有改动；2026-10-19 已获取的团队远端基线为 `347dbe196005df07c2a9e4e6f66073d1f5dea6ef`。正式编码前仅普通快进或普通 merge，不 rebase / force push。
- 团队基线已有真实 0011、0012，`owner_music_state` 含 `feedback_evidence_epoch` 和 `preference_clear_cutoff`。Backend 已实现 `require_library_access`、`resolve_feedback_context`、`lock_owner_music_state` 和 `advance_feedback_epoch`，这些 helper 不自行 commit。
- 正式 0013、V3.1 反馈字段及路由仍未进入团队基线。[PR #155](https://github.com/chenjz111/HarmonyAI/pull/155) 是未合并的隔离 Draft，不是生产模型；其字段名不得直接作为已批准合同。
- 当前 worktree 的 PF-1A 与旧反馈定向基线为 11 passed、1 个 Starlette 弃用警告（内存 SQLite，2026-10-19）；它不证明更新后团队基线或 PF-1B 功能已通过。

## 3. 方案选择

推荐：V3.1 使用独立 request schema、policy/consent service 与路由；旧 V3.0 保留原提交语义，仅在历史、列表及重放读路径加入必要的 tombstone 门禁。新服务复用现有 owner-scoped `feedback_v3` 与 Backend helper，由调用方掌握单一事务。

备选一是在旧 `feedback_service.py` 内按版本分支实现全部新行为；文件已有收藏、旧反馈和 PF-1A 门禁，继续叠加授权、clear 与并发逻辑会扩大旧入口回归面。备选二是另建反馈表；这会分叉唯一幂等键、旧列表和删除语义，违背 #150 的 0013 方向。两者均不采用。

## 4. 组件与数据流

1. **输入边界**：V3.1 request 的 consent 为严格布尔，省略时为 `false`，不接受 `0/1`、字符串等宽松转换。请求必须显式给出音乐与来源 context；是否要求逐条 `playback_event_id` 由第 8 节 Gate 1 决定。客户端仅回传已展示的政策版本，不决定服务端生效版本。旧 V3.0 行一律无新授权。
2. **政策边界**：`consent=false` 可以保存，不能因政策服务未配置而被迫同意或失败；`consent=true` 必须由服务端校验 active policy，记录服务端认定的版本与同意时间。未知、过期、撤销或未配置版本均 fail closed。无论 consent 值如何，M1 不调用学习器、不生成新偏好版本，也不让新生成消费旧长期偏好。
3. **归属边界**：先用服务端 `AuthPrincipal.internal_user_pk` 调用 `require_library_access`，再验证明确 context 与真实、本人、同资产的 `play_started`。不从最近 Session、Favorite、NULL owner 或当前患者推断 context、病历主体或实际聆听者。无合法关联时采用不泄漏归属的错误；具体公开错误码沿正式 API 合同冻结。
4. **保存和幂等**：新 V3.1 行保存 owner+key 约束下的请求指纹；指纹由规范化请求计算，不保存或输出原文。相同 key+相同请求重放首次业务结果，不再次改收藏、授权、epoch 或学习状态；相同 key+不同请求冲突。旧行无指纹时不得伪造历史 hash，也不得把无法核对的 V3.1 请求宣称为同体重放。已删行的 tombstone 优先于旧保存结果，不能通过 replay 返回已删详情。
5. **读取**：本人单曲只读列表、total、详情及旧 `/me/history` 对 tombstone 使用同一过滤谓词。GET 不创建 owner state，不推进 epoch。若存在响应缓存，其键或有效性必须绑定 owner 与证据 epoch；没有实际缓存时不新增缓存层。
6. **删除和 clear**：授权删除仅设置服务端 `deleted_at`，重复删除不二次推进 epoch；clear 写入服务端 cutoff、推进 `feedback_evidence_epoch`，使旧应用证据失效。反馈变更、epoch 与应用有效性检查共享调用方事务；调用 Backend helper 不再独立 commit。旧历史记录及不可变生成物不做物理删除或重写。
7. **并发**：提交、删除、clear 与任何未来的应用结果必须在写事务内校验预期 owner epoch / cutoff。删除或 clear 的 ACK 之后，携带旧 epoch 的计算、GET、replay 不得恢复证据或输出已删详情。测试使用明确 barrier/事务钩子，不用 sleep 作为并发证明。

推荐文件边界：`backend/app/schemas/v3/feedback_v31.py` 负责新请求校验；`backend/app/services/v3/feedback_consent_service.py` 负责政策、授权、幂等和生命周期；`backend/app/routers/v3/feedback_v31_router.py` 只做协议转换；`backend/app/services/v3/feedback_service.py` 仅添加旧入口必要的 tombstone / replay 兼容。`tests/api/v3/` 增加 consent、delete/clear、并发专项测试，并保留 `test_feedback.py` 与 `test_s7_preference_invalidation.py` 原断言。正式模型字段与路由注册待 #150 交接，不由 PF 自行写入迁移或 `main.py`。

## 5. 安全失败语义

- 未授权或无法证明 owner/context/event：不泄漏目标记录是否存在；不以 Favorite 或 NULL owner 兜底。
- 活动政策不存在或版本不匹配：只有 `consent=true` 路径拒绝；`false` 不被强迫升级为同意。
- 幂等键不同体：明确冲突；旧行无可信指纹时不推测为同体。
- tombstone、cutoff 或 epoch 不匹配：拒绝旧结果应用和旧详情重放；不能降级为“重新学习”。
- 数据库/共享 helper 冲突：事务回滚后按合同安全重试或返回可识别冲突，不把唯一约束错误变成 500；不隐式切换另一 owner-state 实现。
- 新自由文本 `comment` 的兼容行为未获裁定前，新 V3.1 路由保持关闭或拒绝该字段；绝不新增可逆正文存储。旧 V3.0 的 hash 历史不冒充可恢复正文。

## 6. 验收证据

先写失败测试，再做最小实现。至少覆盖：legacy 无授权；V3.1 consent 省略/false/true 与严格布尔；政策 active/未知/过期/撤销；本人、跨 owner、跨 asset、无真实播放及多 context；同 key 同体/不同体/并发；删除后的新旧 list/total/detail/replay；重复删除、clear cutoff、跨 owner 隔离；以真实事务 barrier 验证迟到计算/GET/replay；历史 profile 和不可变 checksum 保留；PF-1A 学习及新消费持续关闭。迁移 up/down、旧库升级和 fresh-create 由 #150 负责实现，PF-1B 在合并后的隔离数据库上回归验证，不修改已合入迁移。

运行环境只用合成身份与内容、隔离 SQLite/Fake Provider、有效离线保护；真实 Provider、生产库和受限素材调用为零。PR 必须列出实际命令、passed/failed/skipped/warnings、未跑项目及仍未关闭的 Gate；目标分支为 `team/s7-m1-w2-baseline`，可先 Draft，不自动合并。

## 7. 阶段性交付

1. **无依赖部分**：同步团队基线；重跑旧回归；确定 V3.1 schema、政策验证与请求指纹的 RED 测试和最小纯逻辑。此阶段不宣称已具备持久化。
2. **共享合同冻结后**：#150 提供正式 0013 字段/迁移/路由注册，#151 确认 event/context 证明与 epoch/CAS 事务边界；PF 接入真实保存、查询和幂等。
3. **生命周期与并发**：实现 tombstone、clear、旧入口失效、历史只读；用事务 barrier 和迁移专项验收。
4. **交接**：运行相关合同及后端测试、`git diff --check`，提交仅限 PF 写集的 Draft PR；Owner 审核后再决定 Ready/合并。

## 8. 必须关闭的合同 Gate

这些是明确的发布/接线门槛，不是由 PF 自行决定的空白需求：

1. **播放事件绑定**：现有 `resolve_feedback_context(db, internal_user_pk, music_id, context_id)` 只要求同资产存在本人播放事件，不接收具体 event ID。Owner/#151 须明确 V3.1 是否必须提供并验证特定 `playback_event_id`；若必须，Backend 先补统一 helper，PF 不复制事件授权算法。
2. **0013 与政策**：#150 须冻结 consent、policy version/time、tombstone、source context、request fingerprint、evidence epoch 的正式列名、约束和旧行默认值；Owner 须给出 active policy 的权威来源及版本撤销规则。未落实前不启用对应持久化路径。
3. **clear 的应用指针**：须明确旧 `UserMusicPreference.current_version_id` 是要物理置空，还是保留供历史只读并由 epoch/cutoff 构成独立的有效应用门禁。默认安全设计是不重写历史版本、所有新消费仍为 `None`；不得在未确认下破坏历史 profile GET。
4. **并发和公开响应**：现有 `advance_feedback_epoch` 原子递增但不接收 `expected_epoch`；Owner/#151 须明确预期版本比较的位置、首写 owner-state 冲突处理，以及 tombstone replay、旧无指纹行和 V3.1 comment 的公开错误合同。未冻结时只做不依赖这些结果的逻辑与测试。
