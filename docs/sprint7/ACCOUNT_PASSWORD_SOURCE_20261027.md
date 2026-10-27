# 账号密码源接入候选 — 2026-10-27

复用R1 Argon2id参数、NFC、用户名规范和既有AccountService/原生路由。不提供虚构生产拒绝集，不联网查询泄露密码。

`load_reviewed_password_policy`要求部署方独立提供已审核manifest SHA256；manifest再绑定同目录JSON拒绝集的SHA256、条目数、版本、许可和批准引用。两级摘要、格式、大小或路径不符均不可用，不回退少量测试口令。`build_reviewed_native_account_router`复用现有工厂，缺平台验收或审核源时关闭；默认main未挂载，没有功能放行。

manifest格式字段：`format=harmonyai.password-blocklist.v1`、`version`、`approval_ref`、`license_ref`、`passwords_file`（相邻JSON文件名）、`passwords_sha256`、`entry_count`。生产文件不进Git，测试仅用临时合成值。摘要对应不等于Owner批准、完整泄露覆盖或许可结论。

证据：原Guard固定账号84p：`overnight-20261027-account-reviewed/result.json`；完整真实ASGI/SQLite账号流程：`overnight-20261027-account-journey/result.json`，均在外部evidence目录。MySQL另见同日实测记录。真实Android Keystore/TLS、H5 Cookie/Origin/CSRF、目标资源预算及生产拒绝集审批仍未完成。
