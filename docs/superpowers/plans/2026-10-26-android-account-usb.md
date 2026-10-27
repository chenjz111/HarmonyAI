# 执行顺序
- [x] 核实实际候选、R1、标准基座与独立APK差异；Owner选择USB非生产目标。
- [x] 修复无标准URL运行时的严格HTTPS Origin前置兼容问题：RED→GREEN，回归拒绝/跨Owner边界。
- [x] Owner批准本机HTTPS、原生源码候选及一次0元打包；不包含安装或新增编译依赖下载。
- [ ] Keystore/网络真实原生候选与不影响当前基座的构建接线；独立审查。
- [ ] 明确密码拒绝集与目标资源测量；非生产HTTPS组合现有账号服务，无Provider调用。
- [ ] 最小实际编译；产物审查；获批后安装与TLS/Keystore/账号真机闭环。
- [ ] 记录四种状态及剩余阻塞；不声称未执行环节完成。

2026-10-27 续接：唯一云提交因 okhttp/okio classpath 失败。已准备 compileOnly 显式声明，未解析/下载或再次打包。账号页面恢复/离页、成功退出后显式游客路径已完成本轮候选及真实 ASGI 隔离验证，参见 ../../sprint7/ACCOUNT_CONTINUATION_20261027.md。全前端685p/1f保留，H5/资源通过；Android未完成。既有脏改和签名缓存保留，不重建账号或 Player。
