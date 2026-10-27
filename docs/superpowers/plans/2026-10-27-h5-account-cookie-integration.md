# H5 账号 Cookie 接线（R1 候选，默认关闭）

基线44cbda1；延续Owner已批准R1/V1.1，不新增账号体系、密码算法或数据库结构。原生构建/设备、分享、原图、偏好及SHA例外依旧跳过，不替代审批。

Ruling：第一版H5候选限定前端/API同一明确批准HTTPS Origin，复用既有账号服务和运行时；不接受跨站Cookie拓扑或通配CORS。这样CSRF辅助Cookie可由同源页面读取，Refresh仍仅HttpOnly Cookie。缺实际Origin/浏览器安全证据时默认不挂载。

1. 既有BrowserMutationGate增加短效、签名、用途隔离的preauth挑战（15分钟技术期限，无数据库/保留政策变化）；bind挑战绑定当前合法Guest凭据摘要，login挑战绑定匿名浏览器nonce。POST bootstrap只设置挑战Cookie，不撤销旧会话或覆盖身份。
2. 复用AccountService；显式browser gate才允许h5。注册/登录检查preauth，Refresh在原单事务内检查session绑定CSRF，再旋转原Refresh；授权重放仍撤销family。无效Origin/CSRF不得触发任何状态写入。注销/改密仍用Access及同sid的CSRF检查。
3. 新浏览器路由工厂仅隔离候选：Refresh返回HttpOnly/Secure/Lax/__Host Cookie，绝不进入JSON；Access仅JSON/runtime，CSRF辅助值单独Cookie（不具备认证效力）。Cookie期限取既有会话7天idle/14天绝对界限，不延长。
4. 提取既有客户端共同生命周期，Android保留Keystore凭据driver；H5用浏览器Cookie driver、同源fetch、内存Access，不复制认证状态机。未知网络结果持久化非凭据reauth标记，重启不自动重试旧Cookie；明确登录可恢复，不能自动造Guest。
5. RED→实现→GREEN；真实ASGI/SQLite Cookie/CSRF联调、已有Guest/Android兼容回归；独立整体审查和提交。实际浏览器HTTPS、部署Origin、Android均仍NOT RUN。任何默认路由/开关、部署不在本轮范围。

Ruling：H5 CSRF采用既有session绑定随机secret，随session失效，Refresh只旋转认证proof；CSRF不在每次Refresh后变化。这样合法旧proof和其原session CSRF重放仍撤销family，无效Origin/CSRF则拒绝且不写入。Native原有刷新输出不变，无新数据库字段/迁移。退出/改密清除浏览器辅助Cookie，CSRF本身不能认证。

依据：Owner Account Security R1 E；OWASP CSRF Prevention Cheat Sheet（session绑定token及签名挑战），MDN Set-Cookie（__Host/Secure/HttpOnly/Path/Domain）。注册后随机CSRF只作为原会话校验的一部分，不能独立认证。外部政策冲突时保持fail-closed并继续其他工程。
