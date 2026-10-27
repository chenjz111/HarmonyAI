# Android 平台依赖审计（2026-10-25）

基线 ceb6c19675c3eed378a9b62ea33e5c1dda728308；执行合同为 S7 V1.1、Account Security R1 及本次 Owner 环境审计指令。本记录不批准安装、打包、签名、部署或功能启用。

## 本机与仓库事实

只读审计覆盖 PATH 命令 HBuilderX/cli.exe/studio64.exe/adb/sdkmanager/java/gradle，Process/User/Machine 的 HBUILDERX_HOME、ANDROID_HOME、ANDROID_SDK_ROOT、JAVA_HOME，三个卸载注册表位置及下列显式目录；未进行全盘搜索。

| 项目 | 已确认结果 |
|---|---|
| Java | `D:\idea\jdk-21\bin\java.exe` 文件存在，文件/产品版本 21.0.10.0；Process/Machine JAVA_HOME 指向存在的 `D:\idea\jdk-21` |
| HBuilderX、Android Studio、SDK、ADB、Gradle | 在上述范围内未检测到安装或可执行命令，当前不可用；不能排除其他未检查目录存在副本 |
| 卸载注册表 | 无匹配 HBuilder/Android Studio/Android SDK 项 |
| 非生产 HTTPS Origin | Owner 明确尚未批准；未发现可作为批准证据的现有配置 |
| Keystore / 原生网络适配器 | 无已批准实现或插件；未加载、下载或安装任何候选 |

检查的 13 个目录：`C:\Program Files\HBuilderX`、`C:\Program Files (x86)\HBuilderX`、`C:\Users\ASUS\AppData\Local\Programs\HBuilderX`、`D:\HBuilderX`、`C:\Program Files\Android\Android Studio`、`C:\Users\ASUS\AppData\Local\Programs\Android Studio`、`D:\Android Studio`、`D:\AndroidStudio`、`D:\Program Files\Android\Android Studio`、`C:\Users\ASUS\AppData\Local\Android\Sdk`、`C:\Android\Sdk`、`D:\Android\Sdk`、`D:\AndroidSDK`，均不存在。原始清单保存在工作区外证据目录的 `android-environment-audit-20261025.json`。

仓库 `frontend/manifest.json` 的 DCloud appid 为空；无 Android 包名、签名配置、原生插件模块；Android 声明 INTERNET 权限。`frontend/package.json` 仅有 H5/mp-weixin 构建脚本；锁文件没有 `@dcloudio/uni-app-plus`。DCloud 依赖为 `3.0.0-alpha-5020320260803001`，Vue 3/Vite 5.2.8。未发现 nativeplugins、uni_modules、本地 Android 工程或可用打包产物。H5 编译成功不能证明 APK 可构建。

## 构建路线与最小依赖

| 路线 | 能减少的依赖 | 仍需申请/验证 | 风险与建议 |
|---|---|---|---|
| HBuilderX 安心云打包 | 可减少本机完整 APK Gradle/SDK 工具链需求 | 安装兼容 HBuilderX、DCloud 登录/AppID、包名、非生产签名方案、原生适配器及费用/数据处理授权 | 优先评估；不等于已具备 Keystore 插件，也不免除原生 AAR 编译及设备测试。传统打包上传代码/证书；安心模式官方说明不上传二者，实际流程仍需审查。存在额度、排队及包体收费风险 |
| Android 本地离线打包 | 避免云打包账号与上传流程 | HBuilderX、匹配离线 SDK/AppKey、Android Studio/SDK/build-tools、兼容 JDK/Gradle/AGP、签名和原生工程 | 本地依赖更重；现有 Java 21 不证明兼容。工具版本必须按选定 HBuilderX/离线 SDK 配对，不能直接复制最新参数 |

来源：[DCloud 云打包](https://uniapp.dcloud.net.cn/dev/app/cloud-build.html)、[Android 离线 SDK](https://nativesupport.dcloud.net.cn/AppDocs/usesdk/android.html)、[CLI](https://uniapp.dcloud.net.cn/worktile/CLI.html)。CLI 的 App 资源编译与最终 APK 是不同环节。当前未执行任何 Android 编译或打包。

最小下一步是先批准兼容版本 HBuilderX 的安装与构建路线核查，而非立即下载整套 SDK；原生适配器开发若需本地 AAR，再申请匹配工具链。标准调试基座不包含任意新插件，不能拿它代替含适配器的自定义基座。[插件基座说明](https://nativesupport.dcloud.net.cn/NativePlugin/use/faq.html)

## 安全存储候选（选型研究，未批准引入）

推荐审查小型 Java 原生适配器：Android Keystore 中生成不可导出 AES-GCM 密钥；仅将加密 Refresh blob 存于应用私有 SQLite。`take` 在事务内读取并删除 blob，提交成功后才将解密凭据交给刷新流程，确保跨调用/进程不能双重消费。`write` 必须先持久化新密文再报告成功；数据库结果不确定、密钥失效、解密失败均关闭会话，不明文回退。事务与加密组合是候选设计，尚无实现或设备证据。[Keystore](https://developer.android.com/privacy-and-security/keystore)、[SQLite 事务 API](https://developer.android.com/reference/android/database/sqlite/SQLiteDatabase)

硬件保护级别需读取实际 KeyInfo 并记录，不能仅凭 API 名称宣称硬件保护。备份与设备迁移必须排除凭据文件，恢复/重装后缺密钥安全失败；Guest 现有存储兼容整改独立保留，不能宣称整个 App 认证安全验收通过。

不将已废弃的 EncryptedSharedPreferences 直接选为默认新方案；它还要求避免备份加密首选项。[官方 API](https://developer.android.com/reference/androidx/security/crypto/EncryptedSharedPreferences)。DataStore 有事务更新能力，但本身不提供完整 Keystore 加密与一次消费合同，并增加 Kotlin/协程依赖；DCloud 离线 SDK 文档说明其 Kotlin 支持限制，需先证明工具链兼容，当前不引入。[DataStore](https://developer.android.com/topic/libraries/architecture/datastore)

## HTTPS 网络候选（未批准引入）

必须由统一原生适配器覆盖 request/uploadFile/downloadFile：系统信任链与主机名验证、拒绝所有重定向及 HTTPS 降级、不携带环境 Cookie、不记录令牌、不自动重放 Refresh；拒绝无效/过期/错主机证书。可审查 Android 平台网络 API 或兼容版本 OkHttp 的实现，但尚未选定依赖与版本，不下载插件。

`uni.request` 文档的 sslVerify 默认 true，并注明 Android 离线打包不支持该选项；请求还可能自动携带 Cookie，未找到可证明禁止重定向的公开参数。因此设置 `sslVerify:true` 只是一项请求约束，不能作为完整 TLS/重定向验收证据。[官方请求文档](https://uniapp.dcloud.io/api/request/request)。实际证书、重定向、上传及音频下载必须在批准的构建与设备上验证。

## 本阶段安全工程与边界

新增 `api-origin.js` / `android-platform.js`：App 启动前识别原生平台，Android 不继承桌面 HTTP localhost；统一晚绑定 HTTPS Origin。账号安装需要明确非生产批准引用、严格能力标记与真实适配器接口；标记仅为接线门禁，不构成安全验收证据。账号、历史、音频与上传共享安装后的网络适配器。默认没有依赖注入、没有 Origin，账号/音乐库开关维持关闭。旧 V1/V2 深链仍需另行核查，本阶段未重做旧页面。

独立审查修复：拒绝已有账号 runtime 时不得先改变后端地址；普通 API、上传、音频不得绕过已审核网络适配器。无页面重绘、原生插件、签名、系统环境或正式开关修改。

需要 Owner 后续单独批准：工具安装/下载、DCloud 账号登录与 AppID、包名和签名方案、插件/原生代码来源及版本、非生产 HTTPS Origin 与证书、云打包的费用/数据处理、真实设备连接和安装。当前无需为继续离线接线重复申请这些权限。

## 四类交付状态

| 状态 | 结论 |
|---|---|
| 代码 | 平台接线候选完成；真实 Keystore/网络原生实现尚缺 |
| 隔离测试 | 11 项平台专项、真实 ASGI/SQLite Android 上下文及账号流程通过；不经过真实 TLS/Android |
| Android 真机 | NOT RUN：无批准工具链、适配器、Origin、签名或设备操作 |
| 默认 App 可达 | 账号/音乐库仍关闭；缺平台依赖时拒绝连接，不回退 localhost |

H5 Cookie/CSRF/Origin 独立未完成；真实 MySQL、医学独立签核仍未完成。原有 5 项全仓后端收集错误独立追踪，不因专项结果改写为全仓通过。
