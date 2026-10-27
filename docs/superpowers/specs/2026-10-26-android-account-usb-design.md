# Android 账号真实平台接线：USB 非生产方案

Owner 2026-10-26 明确目标：先完成 USB 连接电脑的非生产账号验收，沿用当前隔离后端，不要求拔线独立联网。
复用 Account Security R1、现有 auth persistence/服务/注册客户端和单一 Player。当前独立工作区 codex/s7-android-resource-build-20261025，保留所有既有脏修改，不复制 unpackage 或签名文件。

## 完成目标
测试 APK 安装后，合法游客能保留归属；在真实 Keystore 及实际 TLS 验证后，显式注册绑定保留 internal_user_pk，登录其他账号不合并，Refresh 旋转/注销/重启恢复遵守 R1。没有这些设备证据，不把 verified 或 accountAvailable 设为真。

## 最小接线
1. 既有 FastAPI 仅绑定回环。新增候选 HTTPS Origin https://127.0.0.1:8443，经当前手机 ADB reverse 8443→8443。不部署公网、不装全机 CA、不关闭 TLS/主机名验证。新增测试 CA/服务端私钥、测试 APK 的限定信任配置与 HTTPS Origin 须 Owner 明确批准后执行。
2. 项目自有可审查 UTS+Kotlin 候选，仅 Android 系统 API，无付费插件或第三方 SDK。Keystore AES-GCM；密文置 noBackupFilesDir；持久、跨线程/进程独占消费后才返回 Refresh；崩溃/密钥失效/备份残留不得恢复旧 proof 或明文 fallback。AtomicFile 仅提供文件完整性，不等于互斥和安全消费，必须另加锁与删除持久性设计。
3. 原生 HTTPS request/upload/download 只允许选定 Origin，默认平台证书/主机名验证，拒绝重定向、不继承环境 Cookie；仅回传安全错误，不记录凭据。后台线程执行。复用既有账号/runtime/facade，不另建认证体系。
4. 原生源码先隔离候选、不导入当前标准基座。引入实际模块、必要官方编译组件下载、云端构建/签名/安装须按旧边界分别获批；不自动消耗此前一次云打包授权。
5. 账号路由只在独立非生产 HTTPS 运行器组合；当前游客 HTTP 和历史音乐保持，未经检查不重启/替换现有运行器。运行器禁止全部付费 Provider 网络请求（现预算10/10）；音频使用既有资产。密码拒绝集来源/完整性和 Argon2目标负载需真实核查，测试小列表不宣称完整安全验收。
6. 现设备 JS 缺少标准 URL，当前 HTTPS Origin/账号传输也会因此不可用。独立修复严格 HTTPS Origin 解析，保留拒绝 userinfo/path/query/hash/control/backslash、跨 Origin 和非HTTPS的约束，不引入全局 URL polyfill。

## 验收顺序
原生构建/签名/权限/私钥夹带审查 → 设备合成 Keystore 写入/消费/重启/失败保护 → TLS 正例及错误证书/主机名/重定向负例 → 同一测试 Guest 的历史可用 → 显式绑定/登录/旋转/注销/跨账号隔离 → 重启及断网恢复。
账号资料/密码由Owner本机输入，不能发到聊天。安装不能清除或冒称迁移标准基座数据，独立包与基座的沙箱不同。

状态必须分别列：代码候选、隔离测试、Android设备、默认App可达。H5/分享/原图/长期偏好/生产/MySQL/医学独立签核不由本阶段替代。

官方依据：
- https://uniapp.dcloud.net.cn/plugin/uts-plugin.html
- https://uniapp.dcloud.net.cn/tutorial/build/SafePack
- https://developer.android.com/privacy-and-security/security-config
