# INT-2 第一批：隔离共享基础草案

范围依据：Issue #150 / comment 6184425563 和 Owner 对未注册草案的实施确认。
基线 ff879f70a19328dbe492bf3aa9418e681a5db06b。不是账号、Library API 或 PF-1B 的实现。

## 隔离设计与迁移顺序

`backend/drafts/s7/models.py` 显式加载 `DraftBase` 和三个模型。
DraftBase 复制生产表定义用于 FK 解析，使用独立 metadata；不修改生产 Base、ORM exports、应用加载路径或 create_all。
不要把 DraftBase 当作生产 Base；其副本不是可运行的第二套业务 ORM。
`backend/drafts/s7/{sqlite,mysql}/` 是未注册草案，不在生产 migrations 目录或注册表中。
0011 未创建占位。正式顺序仍须 **0010 → 真实0011认证 → 0012 library → 0013 consent**。
没有真实0011和顺序保护接线，不得正式注册0012/0013。

SQLite 显式隔离验证使用 migrations.apply_draft(sqlite3_connection, version)，版本为
0012_library、0013_consent；只写 int2_draft_migrations，不写 schema_migrations。
调用方必须提供隔离空闲 SQLite 连接；此工具不读取配置或连接地址，也不会自动运行。
它不是生产数据库保护边界：严禁把真实数据库连接传入。
同一草案按账本 checksum 重复执行返回 false，SQL 改动后拒绝重放；失败 DDL/账本同事务回滚。
raw SQL 未包含账本和降级预检，不得把手工执行 SQL 当作完整迁移工具。

未来注册前必须在生产执行器中接入 `validate_migration_history` 等效检查：
注册版本严格排序且不重复，数据库已应用版本必须是注册列表的完整前缀，检查在任何新 DDL 之前。
测试覆盖在已应用0012后插入0011、未知已应用版本和乱序注册。
本 PR **没有修改生产执行器**；旧执行器的顺序保护仍未闭合，不得宣称现网已受保护。
并发迁移锁、半完成 MySQL DDL 恢复也必须在正式接线前处理。

## 字段合同

| 表 | 主键/字段 | 默认与约束 |
|---|---|---|
| owner_music_state | internal_user_pk → users.id | owner 唯一，删除 owner 时 cascade |
| owner_music_state | library_epoch、feedback_evidence_epoch | BIGINT，非空且>=0，初始0 |
| owner_music_state | preference_clear_cutoff | 可空 UTC 时间；初始NULL |
| music_library_state | (internal_user_pk, music_asset_id) | 复合主键；分别指向 users、music_assets |
| music_library_state | user_title、last_played_at | NULL；不回填旧 title 或播放时间 |
| music_library_state | metadata_version | BIGINT非负，初始0；首次成功合法修改由 Backend CAS递增 |
| music_playback_events | (internal_user_pk, event_id) | 复合主键；event_id非空、最多128，建议服务端校验ASCII不透明幂等键 |
| music_playback_events | music_asset_id、origin_task_id | asset必填、task可空；非空task通过(owner,asset,task)复合FK匹配 |
| music_playback_events | event_type、played_at | 仅play_started；记录真实onPlay后插入，时间默认数据库当前UTC；不补造历史事件 |

播放context复合FK需要 generation_tasks 上新增唯一索引
uq_s7_task_context_ref(task_id,internal_user_pk,music_asset_id)，仅草案 metadata/SQL包含。
约束不代替服务授权；Side state 的存在不会授予播放/管理权限。
shared asset可被多个owner合法关联，分别保存私有状态；NULL owner/Favorite单独不授权。
origin_task_id非空时保证owner和asset一致，但还需服务验证terminal成功状态和当前访问资格。
禁止多context静默选择；涉及来源/反馈必须验证明确context。

0013仅SQL/字段合同，不提前扩展现有 FeedbackV3 / UserMusicPreferenceVersion ORM：

| 表 | 新增列 | 语义 |
|---|---|---|
| feedback_v3 | learning_consent | 非空0/1，默认0；旧记录无追溯授权 |
| feedback_v3 | consent_policy_version、consented_at | 默认NULL；授权为1时必须非空，版本非空；服务端核验有效政策版本 |
| feedback_v3 | source_task_id | 可空FK至generation_tasks.task_id；授权时必须非空；服务必须验证同owner/asset/terminal状态，单列FK不证明授权 |
| feedback_v3 | evidence_epoch | 可空非负BIGINT；旧记录NULL；授权时必须记录 |
| feedback_v3 | deleted_at | NULL或服务端UTC删除时间；tombstone保留原幂等键，不允许删除重放复活 |
| feedback_v3 | request_fingerprint | 可空VARCHAR(96)，记录规范请求安全摘要，不存原文；具体规范化/哈希版本由PF/BE审定 |
| user_music_preference_versions | evidence_epoch | 可空非负BIGINT；旧版本NULL表示没有新授权来源 |

保留原 (internal_user_pk,idempotency_key) 唯一键，deleted_at不参与该键。
SQL的同意检查只是结构要求，不能证明有效政策、来源权限或实际同意；必须由PF服务校验。
M1即使明确授权也禁止实际长期学习；不改变历史Diagnosis、Prescription、GenerationSpec、MusicAsset.title/checksum。
timestamp以UTC存取；SQLite时间文本不自带时区，MySQL需要会话UTC设置；服务端负责验证，不接受任意客户端时间。
合成fixture：tests/api/v3/fixtures/int2_shared_fields.json。

## Backend / Preference 依赖

SharedOwnerAccess Protocol 在 contracts.py，仅函数签名，不实现蔡子鑫的业务服务：
get_owner_state（GET不创建）、lock_owner_state（写事务中锁定/竞争安全初始化）、
require_music_access、require_music_context、advance_library_epoch、advance_feedback_epoch。
调用方持有事务，helper不得commit；Preference复用同一owner state，不创建第二张状态表。
当前Protocol参数/返回类型可用于协作评审，但草案未集成前不能直接导入生产业务路由。

Backend：新成功资产入库、收藏、改名、播放等改变列表的操作，与library_epoch递增在同事务；
event幂等重放必须比较asset/context并不重复更新活动或epoch，不能只靠主键冲突就算实现。
Preference：删除/clear、feedback_evidence_epoch、clear_cutoff和缓存/旧版本失效同事务，CAS冲突拒绝；
旧接口和idempotency replay不得复活tombstone。上述均为后续业务要求，不是此PR已完成服务。
Frontend：MusicCardV1不新增字段；activity_at=last_played_at ?? playable_created_at，未知实测时长NULL。
cursor需绑定owner/list/epoch/排序边界及防篡改，完整codec仍由Backend/Integration后续交付。

## 验证、降级和剩余Gate

SQLite：旧0010与fresh-create、旧记录默认值、FK/唯一/CHECK、shared owner隔离、checksum、失败回滚、降级前置条件和历史快照不变。
降级必须按0013→0012；任何新同意/删除/来源/epoch/fingerprint数据或侧表/事件记录存在时拒绝，不能自动丢弃成果。
SQLite DROP COLUMN需要>=3.35，正式发布前必须验证部署版本。
MySQL：仅成对DDL及SQLAlchemy方言编译/静态审查；没有连接MySQL或验证真实执行。
要求MySQL>=8.0.16、InnoDB、与原FK父列完全一致的字符集/collation和INT类型；正式使用须用隔离服务验证。
MySQL DDL隐式提交，不能以engine.begin宣称整批可回滚；必须做前置检查、备份和可恢复分阶段方案。
SQL down本身不执行数据丢失预检；MySQL尚无获验收的执行器，禁止直接对正式库运行。

未接线：生产ORM导出、0012/0013注册、路由、共享业务helper、真实API、stream、PF-1B、账号系统。
正式0011、安全迁移顺序检查接线和真实MySQL验证仍阻断生产集成，不阻断本隔离草案评审。

## 本次实际测试回执

在离线防护下，配置数据库仅为SQLite内存，显式旧库用临时文件，执行：

```
pytest -q -p no:cacheprovider tests/api/v3/test_int2_shared_drafts.py tests/api/v3/test_v3_migrations.py tests/api/v3/test_v3_business_migrations.py tests/api/v3/test_s7_music_library.py tests/api/v3/test_s7_preference_invalidation.py tests/api/v3/test_feedback.py --tb=short
```

实际通过已验证的offline_pytest包装器运行，不是无防护裸跑上述命令。
结果87 passed / 0 failed / 1 skipped / 1 warning；其中新专项30项。
skip为Windows真实symlink权限不可用；warning为Starlette/httpx弃用。
离线防护自验证7 passed；遥测无真实外联/Provider，仅被拒绝的库探测和自验证拒绝案例。
MySQL真实执行、全仓后端、H5及其他成员业务联调NOT RUN，不以本回执代替这些Gate。
草案测试包不分发本机Git管理目录中的防护脚本；团队运行前须准备等效、已验证隔离。
