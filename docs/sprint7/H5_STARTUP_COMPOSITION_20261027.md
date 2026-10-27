# H5 账号启动候选 — 2026-10-27

基线40be62e。用户当前无法接USB，Owner要求先推进无需配合的Sprint7工程；保留既有已批准Account Security R1、Feedback R1和V1.1产品边界。

`main.js`在App生命周期前执行H5候选组合，复用原H5 Cookie客户端和注册账号runtime；默认没有配置或审批，故不会安装账号、发请求、变更Guest。未来须由经审查代码显式提供非生产授权、浏览器安全验收、批准引用，以及完全相同的批准/配置/页面HTTPS Origin；不从URL或普通存储读取启用标记。失败安装清理候选实例，保留Guest；重复初始化不重建，变更后端拒绝继续。

实际隔离链路：原Guard下真实ASGI/SQLite账号路由、同一TestClient Cookie jar和两个独立Node进程，验证Guest绑定、历史归属、登录其他账号不合并、Refresh、未知结果不自动重试、改密/注销，以及全新进程通过原HttpOnly Cookie恢复账号并读取历史。仅四个非认证UI状态跨进程传递，Cookie和Refresh从未进入JS或证据日志。证据外置`h5-startup-freshprocess-20261027/result.json`；这不是实际浏览器、Cookie持久化、HTTPS/TLS或真实App生命周期验收。

原Node Guard完整前端716p/0f/0skip；H5编译成功并验证109/109素材；启动/Android/账号定向45p；联调watchdog1p。H5与Android默认账号、正式音乐库仍关闭，需实际Origin/浏览器安全验收、Guest旧存储整改和审核密码源/部署预算。源冻结保护及政策边界未改。独立审查未发现有证据P1/P2，指出原单进程模拟的恢复局限，本次以两个全新进程补证，但不宣称真实浏览器验收。
