# INT-2 0011 身份会话持久化基础

限定交付，非完整认证系统。基线 ff879f70a19328dbe492bf3aa9418e681a5db06b。
本批仅注册0011_v3_auth_foundation，不导入或修改Draft PR #155，不注册0012/0013。

## 新Schema与安全边界

- user_identities.auth_epoch：INTEGER、非空、默认0、非负CHECK。旧identity/internal_user_pk保持不变。
- auth_sessions.auth_session_id：VARCHAR(64)主键。
- internal_user_pk：现有users.id的INT FK，ON DELETE CASCADE，不新增owner体系。身份有效性仍需后续服务核验。
- refresh_credential_hash：VARCHAR(255)、非空非空串、唯一；仅供未来规范化安全摘要存储，不存明文Token或密码。MySQL使用utf8mb4_bin区分摘要大小写。
- family_id：VARCHAR(64)、非空、索引；仅预留轮换family归属，不实现重放判断。
- created_at：数据库当前时间默认；expires_at：必填且晚于created_at，没有TTL默认；revoked_at：可空，不早于created_at。
- owner、family、expires_at分别有索引。SQLite DateTime、MySQL DATETIME(6)，服务与部署会话必须统一UTC。

字符串容量和列定义是存储合同，不是密码/Token安全参数审批。凭据安全摘要算法、规范编码（必须拒绝空白及非规范值）、生成熵、TTL、轮换/重放/撤销事务仍需实施前验证。
数据库只能验证结构，不能证明某个字符串确实是安全摘要，不能把任意输入写入该列。
本批不写入真实会话，不生成/刷新任何Token，不增加登录/注册/refresh端点，不改JWT解析。
auth_epoch本轮仅存储：旧JWT不新增必需claim，尚不宣称epoch撤销机制已启用。
密码哈希、安全存储、H5 Cookie/CSRF、跨账号切换/绑定仍未实现或验收。

## 迁移和初始化策略

正式顺序：0010 → 0011真实认证基础 → 0012 library → 0013 consent。
0011已是有用途的schema，不是占位；本PR仅将注册序列扩展至0011。
原0001～0010 up/down SQL逐字节不改，checksum算法不改。

preflight_v3_migrations在任何新迁移DDL前检查：

1. 注册编号从0001连续、唯一、严格排序。
2. 已应用版本按applied_at、version读取，必须为注册序列完整前缀；未知、缺口、重复和可观测乱序拒绝。
3. 所有已应用up SQL checksum匹配；预读全部待用SQL后才执行DDL。
4. 已有auth_epoch/auth_sessions形状不兼容时拒绝，不猜测修复。

init_database在Base.metadata.create_all之前也运行只读preflight，避免无效历史下先创建新表。
历史ledger时间只有秒精度，同一时间按version排序；不能据此重建未记录的实际执行次序，也不能证明手工伪造ledger的历史真实性。
多个迁移进程的互斥锁尚未实现，部署必须仅运行一个迁移执行者；并发生产迁移另设Gate。

fresh-create已有auth_epoch时，经结构验证省略0011重复ADD，源checksum仍按原SQL计算。
SQLite 0011新DDL与ledger INSERT在同一BEGIN IMMEDIATE中执行，错误rollback后可重试。
create_all是更早的独立阶段，不声称整次初始化原子；测试验证先前建好的正确schema保留后可继续迁移。
MySQL按相同已有列策略处理0011；另对历史0009/0010执行文本省略已存在的nullable列，源SQL和checksum不改。
MySQL完整fresh-init未真实执行，不以这些渲染检查宣称全部历史迁移已获得双数据库验证。

## 降级与恢复

rollback_auth_foundation(engine)仅支持显式SQLite操作，不在初始化/请求路径调用。
先验证历史/checksum、要求0011为最后已应用版本，再执行有防丢数据CHECK的down SQL。
auth_sessions非空、任何auth_epoch不为0或有更高版本时拒绝；无自动删除会话或重置epoch。
SQLite DROP COLUMN要求>=3.35。测试覆盖拒绝条件、成功降级及随后重新升级。
fresh-create的ORM使用表级auth_epoch CHECK，SQLite不能直接DROP该列；本路径明确不支持自动降级。
rollback_auth_foundation在原库BEGIN IMMEDIATE后、任何降级DDL前，使用仅含identity表定义的内存副本探测DROP兼容性；不复制用户数据、不重建原表。
不兼容时抛MigrationSchemaMismatch，原表、约束、数据及ledger均不变。SQLite down SQL只允许经该入口执行，不得裸跑。
旧0010经0011 ALTER升级产生列级CHECK，原有安全降级/再升级仍保留。
fresh-create需要降级时，先停机并申请独立审查的备份恢复或表重建方案，本PR不擅自实施。
降级后不能继续使用需要auth_epoch的新ORM承接请求，必须停机并与代码版本同步切换。

MySQL DDL隐式提交；普通engine.begin不是整批DDL原子性保证。
部分0011完成后仅允许对已存在且形状正确的字段/表继续，异常结构失败关闭。
MySQL down文件只有操作指令，缺少获真实服务验收的自动前置检查/恢复器；必须由受控操作员先验证会话空、epoch全0、没有后续版本及可恢复备份。
正式部署前需独立MySQL>=8.0.16服务验证父列类型/collation、CHECK、索引、UTC、fresh-create、部分DDL恢复及降级；本轮均不连接真实MySQL。

## 测试回执

Python 3.12，合成资料，隔离SQLite内存/临时文件，已验证offline_pytest包装器：

```
pytest -q -p no:cacheprovider tests/api/v3/test_0011_auth_foundation.py tests/api/v3/test_v3_migrations.py tests/api/v3/test_v3_business_migrations.py tests/api/v3/test_guest_auth.py tests/api/v3/test_v3_ownership.py tests/api/v3/test_owner_flow.py --tb=short
```

70 passed / 0 failed / 0 skipped / 1 warning。其中新增0011专项19项；warning为Starlette/httpx弃用。
离线防护自验证7 passed。真实Provider/外联/生产数据库操作0。
初始RED确认缺0011；修复了SQLite内联FK反射选项缺失（改等价具名FK声明），以及一次新增渲染调用位置的缩进错误；最终重新完整运行上述集合。
MySQL仅SQL静态审阅、模型DDL编译与渲染逻辑检查，真实执行NOT RUN。
全仓后端、H5、账号系统和其他成员业务联调NOT RUN。
本机防护/证据位于Git管理目录，不随clone发布；团队运行测试前须建立等效隔离，不能把上面的裸命令当作网络保护。

## 0012/0013正式化最少步骤

1. Owner审阅/批准并集成本0011 PR，确认团队新基线；本轮不自动合并。
2. 在更新基线上审阅PR #155的字段与约束，移植草案至正式目录、生产metadata/exports；反馈新列与0013同批接线，避免旧库缺列。
3. 在前缀/checksum保护下按0011→0012→0013验证旧库/fresh-create、重复、历史不变、数据保护降级及共享FK/权限。
4. 先闭合真实MySQL/单迁移进程/失败恢复Gate，再批准部署；业务API/helper/权限和stream仍单独验收。

本PR不代表M1、正式认证或生产数据库迁移已验收/执行完成。

## 合并前定向修正

真实SQLite临时文件库复现：fresh-create的表级CHECK导致DROP auth_epoch报no such column。
新增回归验证明确拒绝发生在破坏性DDL前，并比较原schema、identity数据、迁移ledger及foreign_key_check。
限制的是fresh-create自动降级，不限制正常初始化、升级或旧库列级CHECK的降级。
本次重新执行同一受影响集合：71 passed / 0 failed / 0 skipped / 1 Starlette warning。
本段为追加修正回执，上文70项为首轮交付历史回执；MySQL真实执行仍NOT RUN，生产部署Gate不变。
