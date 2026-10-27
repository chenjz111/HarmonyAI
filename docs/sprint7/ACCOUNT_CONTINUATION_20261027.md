# 账号用户流程续接 — 2026-10-27

本轮继续已授权的 USB 非生产账号工作。基线 b6bda0ee7f4cfabc77287b3985f0621ea06031ff，分支 codex/s7-android-resource-build-20261025；保留此前 Android/Player/传输未提交修改。

## 用户流程变化

- 修复恢复登录后“我的”未读运行时 owner、因而不显示退出按钮的问题。账号显示只读运行时，不信任普通存储里的 owner 标签；账号事件订阅不依赖音乐库开放。
- 离开“我的”立即清除输入密码、用户名和旧账号视图；迟到登录结果不在隐藏页面弹成功提示或覆盖新的表单。
- 成功退出注册账号后，提供显式确认的“使用游客体验”。仅本次运行时确知退出成功才获得一次性转换资格；不自动创建游客、不迁移账号历史。进入首页后复用原 Guest 创建链。
- 未知绑定、退出未确认、后续重新登录均不能使用旧资格。没有新增“放弃未知绑定”的操作或政策。

## 原生构建修复候选

2026-10-26 21:19:43 提交的唯一获批云任务已失败，Kotlin 编译无法解析 okhttp3/okio，未产生账号验收 APK。最终 APK 包含运行时类不代表插件编译 classpath 包含这些类。

源码 config.json 现显式声明 compileOnly okhttp 3.12.12 与 okio 1.15.0：前者与 DCloud 官方 uni-app 内置版本相同，后者与该版 OkHttp 官方 POM 一致。使用 compileOnly 避免重复打入框架已有类；不是升级框架网络库，也不是新依赖下载已获批准的声明。未执行 Gradle 解析/下载、云打包或安装；云端是否正确应用声明以及实际 APK 链接仍 NOT RUN。

依据：
- https://uniapp.dcloud.net.cn/plugin/uts-plugin.html （config.json dependencies 的 source 原生声明）
- https://uniapp.dcloud.net.cn/plugin/uts-for-android.html （uni-app 内置 okhttp 3.12.12）
- https://raw.githubusercontent.com/square/okhttp/parent-3.12.12/pom.xml （okio 1.15.0）

## 验证与待办

页面两个复现 RED→GREEN；退出到游客三个 runtime 用例 RED→GREEN；确认/取消/离页页面用例 RED→GREEN。页面+runtime+startup 51 项通过，原离线 Guard 未改。

- 全前端：685 passed / 1 failed / 0 skipped，guard_unchanged=true。失败为 s7-restored-assets.test.mjs 的整页源码冻结 SHA 断言：首先发现 Player 当前哈希不等于恢复素材时记录。原冻结清单也包含本轮修改的 Profile，因此本轮 UI 变化同样需要后续版本化证据；不能仅以 Player 旧失败概括所有源码差异。原素材 113 文件精确哈希校验仍通过，未覆盖历史 manifest 或删改断言制造通过。
- 真实 FastAPI/SQLite 账号 stdio 联调通过：成功绑定、重启旋转、跨账号隔离、未知结果、撤销、显式新游客与重新登录后历史保留。存储仍为替身、ASGI 没有实际 TLS，不能算 Android 验收。首次受限环境运行在后端就绪前退出且无诊断输出；保留失败记录，使用同一原 Guard 在获准的本机进程环境重跑，9 秒完成并校验后端 telemetry，无外部请求。
- H5 离线编译通过，109/109 正式静态资源核验，问卷 manifest 和原 Guard 未变；未运行浏览器账号。
- 同一已有独立审查者对本轮范围复核，未确认新 P1/P2；明确保留 compileOnly 格式/解析/运行时链接未验证风险。

外置证据：C:/Users/ASUS/HarmonyAI-s7-m1-evidence-20261024/account-continuation-20261027-{frontend,asgi,asgi-diagnostic,h5}/。两次 ASGI 状态分别 FAILED/PASSED，保留原始结果。

后续：先核对全量/实际 API 结果与独立审查，再准备具体依赖解析及第二次 0 元构建授权请求。原生 Keystore、APK 内 TLS、账号真机绑定/登录/重启仍 NOT RUN。默认账号和正式音乐库未开启；原图、偏好、分享、医学边界不变。

尚未补齐：成功退出后立即杀进程会丢失内存中的游客返回资格，重启仍要求重新认证；离线退出也不开放此按钮。此保守候选不宣称所有退出/重启 UX 已完成。原生 vault 提交失败补偿、缓存清理生命周期、密码拒绝集和实际账号启动组合仍待收口。

## 顺序开发续接：退出重启与改密（后续状态覆盖上一段同名缺口）

Owner 随后明确要求先完成业务流程，不提前重复打包。本轮未解析/下载原生依赖、未提交云任务、未安装 APK、未改默认 Live Flags。

- 成功退出现在持久化 `signed_out` 这个非认证 UI 状态。重启需验证无 Guest/token/owner/flow，且经既有安全存储原子 take 确认没有 Refresh 后，才提供显式游客选项。不会凭 marker 恢复账号或自动创建游客；仍由既有首页链路在明确确认后创建新 Guest。
- 新的退出状态不适用于未知绑定；`binding` 保持原隔离与恢复规则。异常 proof 被消费后转回要求认证状态，不因再次重试获得游客资格；UI epoch 改变使旧资格失效。安全存储 unavailable 或退出结果未知仍要求重新认证，不冒称服务端撤销成功。
- 启动等待正在进行的注销，防止注销中又发 Refresh。普通 UI storage 的读/写异常均不阻止安全凭据销毁与服务端撤销尝试。“我的”显示时等待启动恢复结果，再更新登录/游客返回控件。
- 补齐已批准 Account R1 的改密前端入口：当前密码、新密码及确认，NFC 与既定长度校验，明确确认后复用 `/api/v3/auth/password`。成功或响应未知均移除本地 Registered 权限与旧 Refresh，不自动重试。成功提示重新登录；不新增密码找回、密码规则、服务端路由或账号表。

最终本轮证据：

| 层级 | 结果 |
|---|---|
|真实 FastAPI/SQLite 隔离联调|PASS；绑定保留历史、退出后模拟重启、显式 Guest、重新登录保留历史，以及改密使旧 Access/Refresh/密码失效，新密码登录成功。安全存储替身，stdio，无 HTTP/TLS socket|
|全前端|695 passed / 1 failed / 0 skipped，原 Guard 未变。仍为素材恢复时保护的源码快照断言；未改断言、未覆盖历史 manifest。Player/Profile 源码合法变动仍待单独版本化证据|
|H5资源编译|PASS，109/109 静态素材，问卷 manifest 未变；不是浏览器账号验收|
|独立审查|只读审查本轮范围，未确认 P1/P2；审查者另外复跑目标61项通过|
|Android原生/真机|NOT RUN，本轮没有 APK 构建或安装|
|默认App可达|账号继续关闭；候选 UI/隔离联调不等于默认开放|

最终证据目录：`C:/Users/ASUS/HarmonyAI-s7-m1-evidence-20261024/account-ordered-20261027-{asgi-password,frontend-password,h5-password}/`。中间的退出专项目录也保留，不混用测试数量或声称全仓后端通过。

下一步：继续收口非生产账号实际启动组合、密码拒绝集接入要求和下载音频的身份生命周期清理；不以再次打包代替这些工作。原生 vault 失败恢复/Keystore/TLS、真实设备、MySQL 和原5项后端全仓收集错误仍独立保留。分享暂停、原图/长期偏好及医学签核门禁不变。
