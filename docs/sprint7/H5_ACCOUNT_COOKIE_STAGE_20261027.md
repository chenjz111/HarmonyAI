# H5账号Cookie候选接线 — 2026-10-27

基线44cbda1，复用Owner Account Security R1和原账号服务/表/客户端状态机。新Browser路由工厂不在main挂载，默认accepted=false；仅明确批准的同源HTTPS及合格CORS可用，缺审核密码源或preauth密钥拒绝签发。没有新的账号体系或迁移。

用户链路：合法Guest→签名且绑定原Guest凭据摘要的preauth挑战→绑定同owner；登录其他账号不合并Guest数据；Access仅运行时，Refresh仅__Host/HttpOnly/Secure/Lax Cookie、不在JSON/JS/普通存储。随机CSRF绑定既有session，不能独立认证；Refresh旋转原proof，旧proof及其合法session CSRF重放撤销family，非法Origin/CSRF无写入。7天idle/14天绝对上限保持。

前端从既有registered-auth抽取共享生命周期，Android仍用原Keystore driver，H5用Cookie driver，未伪造原生能力。未知Refresh结果将非凭据journal记uncertain，进程重建也不自动重试旧Cookie；显式登录可恢复。退出重启必须服务端证明无可用HttpOnly凭据才允许后续显式Guest体验。原数据/历史不删除。

额外自查RED→GREEN：迟到logout不能覆盖新登录journal；入队请求冻结已校验路径/内容/凭据，调用方随后修改不能越界。独立审查复核未发现P1/P2。CSRF采用session生命周期，技术15分钟preauth挑战只在Cookie内过期，不新增保留清理策略。

真实ASGI/SQLite联调31个请求：`h5-account-reviewed-asgi-20261027/result.json`。Python HTTP Cookie jar独自保管HttpOnly Refresh，不将Set-Cookie或Refresh值传入JS/日志；JS运行实际客户端/身份运行时，覆盖绑定历史、登录隔离、重启、刷新、非法CSRF、未知响应不重试、改密及注销。它是隔离集成证据，不是实际浏览器Cookie/TLS证据。原Native候选实际ASGI回归`h5-stage-native-account-regression-20261027`通过。

最终本地验证：全仓后端2800p/0f/2个既有Windows skip、原Guard无未知拦截；固定账号103p；全前端710p/0f/0skip（包含Owner明确批准的两页精确SHA新版本）；H5编译109资源全匹配。证据目录分别`h5-stage-backend-final-20261027`、`h5-account-source-composition-20261027`、`h5-owner-approved-frontend-full-20261027`、`h5-stage-resource-build-20261027`。一次开发中运行遇到模块新旧版本混合，日志保留，未算通过；最终后端运行期间源码冻结。

四类状态：代码候选已接线；隔离验证通过；真实HTTPS浏览器/Android NOT RUN；默认App账号/正式音乐库不开放。实际Origin审批、H5同源静态页/代理配置、Cookie行为与浏览器重启/多Tab/存储异常、Guest旧存储安全整改仍需验收，不能从此文宣称H5全部认证路径完成。

安全依据：[Owner R1](OWNER_APPROVAL_20261024_ACCOUNT_SECURITY_R1.md)、[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)、[MDN Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)。无部署/打包/Provider/Merge/LiveFlags变更。
