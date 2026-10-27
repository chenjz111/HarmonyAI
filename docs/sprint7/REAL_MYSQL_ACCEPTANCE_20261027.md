# 独立 MySQL 验收 — 2026-10-27

使用已安装 `D:/MySQL/MySQL Server 8.0/bin/mysqld.exe`，版本8.0.44。每次新建独立数据目录、随机loopback端口和合成数据库，不读默认配置或已有库；校验datadir/实例UUID，要求TLS、CA及主机名验证。私钥、随机数据库密码和数据目录均在仓库外；不安装服务，不调用Provider，每个自身进程退出后停止。

最后完整证据：`C:/Users/ASUS/HarmonyAI-s7-m1-evidence-20261024/overnight-mysql-20261027-ddl-failure/result.json`。可重复入口：`tools/ci/mysql_isolated_acceptance.py --mysqld <existing mysqld.exe> --evidence-dir <NEW external directory>`。

已实际验证：生产ORM fresh-create/再次启动；真实0001–0012升级至0014并保留前12个checksum；0013部分DDL中断无成功账本、再次启动拒绝自动收养/修复；缺0014表拒绝启动。中断库仅作为证据保留，不代表自动恢复方案或生产恢复演练。

真实事务：首次同owner/同幂等键并发反馈一写一重放；Clear持久receipt并保持历史可见；删除tombstone优先于重放；游客绑定保持owner/历史；并发Refresh一个成功，旧凭据重放撤销family，新凭据亦拒绝；登录及全设备注销。

实测发现并修复：MySQL保留字RANK、NOW默认值/SQLAlchemy类型反射差异、CHECK服务端改写、ORM已建循环外键和可空列重复添加、PyMySQL对DDL字面百分号的插值、首次owner状态行gap-lock死锁。只精确识别已批准结构，不修改0001–0012源码/checksum，不新增第二套owner/CAS；漂移默认值/unsigned/计算列/显式collation仍拒绝。独立审查的两项P2（含Player竞态）均RED→GREEN并复核。

这不等于所有MySQL版本、生产数据库、跨主机部署、真实故障恢复、Android或Hosted CI通过。没有生产迁移、付费调用、Merge或正式开关变更。

后续同日实际补齐（`h5-mysql-commit-witness-fixed-20261027/result.json`）：保存、Clear、删除的提交ACK丢失由独立Session witness恢复；末尾CAS失败使反馈、收藏及epoch整体回滚；H5同session CSRF与Refresh旋转及旧proof重放撤销通过。首次扩展运行是fixture重复关键字错误，已保留失败日志后修正，未误报业务失败或通过；最新全部checks通过、实例已停止、Provider0。
