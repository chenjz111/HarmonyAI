# 账号传输、启动恢复与正式 App 启用阻塞

2026-10-25；本工作包基线62157935a43753f4463eaf09cb5901be32ced456。依据 Owner 本轮授权、V1.1 与 [Account Security R1](OWNER_APPROVAL_20261024_ACCOUNT_SECURITY_R1.md)。这是候选工程与隔离联调记录，不是平台验收、上线或账号系统完成声明。

## 用户流程实际前进了什么

| 用户动作 | 本阶段结果 | 证据入口 |
|---|---|---|
|合法游客注册绑定|复用现有账号服务；保留同 owner、原历史与评估 flow；成功后仅 Registered Access 留在内存|account-transport.js / auth-runtime.js；account ASGI 场景|
|绑定失败或游客输错登录密码|原 Guest key 留在原存储位置并隔离；仅 GET identity 确认同一合法 Guest 后恢复使用，不创建替代 Guest|startup 单测与真实冲突/断网场景|
|断网后留在原页点击绑定重试|先验证隔离中的 Guest，再请求绑定；不能确认则不写入|runtime.bind 的恢复前置；真实 ASGI 重试|
|绑定结果未知，Guest GET 返回401|401 也可能是自然过期，不能宣称已注册。保留 unknown journal、禁止使用旧凭据；允许显式输入账号密码登录|独立审查 P2 的 RED→GREEN；真实绑定响应丢失/过期 Guest 场景|
|登录另一个账号|成功认证后切换 owner、清当前 Guest flow；不转移资产、任务或反馈|真实 A/B 切换，B 看不到 A 的音乐|
|App 启动/再次显示|实际 App hook 调用启动屏障；Home 等待恢复，不先创建 Guest；重建客户端通过现有原子 Refresh 旋转恢复|实际 App 脚本＋Home facade＋真实 ASGI；存储为替身|
|连续前台使用导致 Access 过期|普通 facade/library 请求先安全续期；身份快照改变时以 AUTH_REFRESHED 在发送前终止旧操作，用户重试；不自动重放写入|可控时钟单测同时覆盖 facade/library，0 mutation-before-retry|
|并发刷新/旧 proof 重放|同客户端合并刷新；后端真实重放撤销 family，原 Access 随后被拒绝|真实 ASGI＋既有 R1 独立进程竞态专项|
|Refresh 成功但响应丢失|原 proof 已消费且本地不留重试凭据，要求重新认证|真实响应丢弃场景；重启无旧 proof 网络重试|
|登出、撤销或过期|复用既有 sid/epoch 语义；本地清凭据并尝试服务端撤销。断网登出本地仍关闭，服务端结果不能冒称成功|真实单/全设备路径、过期会话/Guest、断网登出|

`binding` 是本地“Guest→账号身份转换未决”的隔离标记，也用于从 Guest 登录的失败恢复；不是后端注册成功事实。未新增 Guest 凭据副本、未延长原 exp、未启用新清理/保留政策。Registered Access/Refresh/密码不进普通 uni storage；集成逐一检查实际返回的 Registered 凭据，失败断言也不输出原文。

## 代码、集成与平台证据必须分开

| 层级 | 状态 |
|---|---|
|候选代码/单元验证|启动与恢复11项；Guest/runtime 回归通过；原 R1 后端74项通过|
|隔离真实 API|原 Node/Python Guard、真实 JWT、正式新建 FK SQLite、现有 R1 路由/Argon2/会话服务；音乐与账号两个场景通过|
|H5 编译/资源|通过；109/109 资源哈希匹配，原 Guard 与问卷 manifest 未变|
|前端全量|649 passed /0 failed /0 skipped；后续精确 SHA 的 Hosted 结果记录在 Draft174 与外置状态|
|浏览器页面/HTTPS/Cookie/CSRF|NOT RUN；H5 Registered 传输未开放，没有长效 Bearer fallback|
|Android/Keystore/重定向/系统回收|NOT RUN；只有明确标识的 secure-store、原生网络/音频替身|
|默认 App|Guest 仍走原 real 路径；账号 runtime 未安装、账号 router 未注册；My 音乐库仍 false/明确预览。候选注入不等于默认可达|

测试路由只在隔离子进程中挂载，使用合成密码 blocklist，不是生产可用的泄露密码集。HTTPS 仅为 ASGI scope，未建立 TLS 连接。固定的会话/Guest 过期故障注入不进入 App 路由。没有修改后端密码、JWT、Refresh、撤销参数/语义或已有迁移。

独立审查仅一次：修复401错误归因与原页重试两个 P2；普通请求续期缺口也按 RED→GREEN 修复；明文 proof 断言改为布尔断言。保留既有测试含义，对旧“未知登录必删 Guest”假设精确化为“未验证前隔离，服务端确认后才恢复”。前端页面/素材、医学/生成规则和原 Guard 均未改动。最初过期测试准备违反现有 DB 时间约束，已修正测试数据，没有改约束。

## 正式用户可用前的具体阻塞

| 能力 | 还必须完成什么 | 当前负责边界 |
|---|---|---|
|Android 注册与启动恢复|选定并审查实际 Keystore-backed adapter，证明加密、持久原子 take、备份/重装/密钥失效安全失败；验证 HTTPS 证书与不转发凭据的重定向拒绝。不能用 verified/redirectsRejected 测试布尔值替代设备证据|候选接口已具备；插件引入、实机安装需单独授权|
|H5 注册/Refresh|批准明确 HTTPS Origin 清单；补齐真正 Cookie 传输/路由组合、HttpOnly Secure SameSite=Lax/Host 属性、登录前和会话绑定 CSRF、Origin/CORS 拒绝测试，再做浏览器验证。现有 native router **不能**改 platform 字符串后冒充 H5|仍缺工程与真实环境，继续关闭；不是“只差改配置”|
|密码安全依赖|版本化的常见/泄露密码拒绝集和运行时完整性；目标环境 Argon2 资源/并发/延迟预算、登录限流负载审查|参数与服务不改；生产依赖未验收|
|平台启动接线|在经过授权的非生产验收配置中，在 App 生命周期/页面创建之前组合 createNativeAccountRuntime 与 installRegisteredAccountRuntime；测试真实 storage/plugin/network adapter。默认仓库没有安装调用|普通候选接线已有；不得自动启用正式功能|
|过期与恢复 UX|真平台检查 AUTH_REFRESHED 的刷新/重试提示，不重复提交原操作；已登出用户显式进入游客体验的导航仍需产品路径接线与验收，不能靠静默移除 registered 标记实现|工程待补，不宣称默认 App 完成|
|未知绑定且 Guest 已失效|401 无法证明是否已有账号。已能显式登录；若账号不存在，尚无已验收的主动放弃未决身份并新建 Guest 路径。须明确警示/放弃条件，再接线；当前 fail-closed|保留为启用阻塞，不自动丢弃旧身份/资料、不承诺找回|
|真实音乐库与 Player|先在授权非生产平台配置验证正常入口→本人历史→同一 Player→真实播放/Seek→收藏/改名→按曲反馈→重开，含 unavailable/401/断网；核验媒体容器/MIME。旧测试 WAV/合成 MP3 元数据不证明解码|默认库仍关闭；须平台证据后另行申请正式启用|
|正常生成到历史|实际输入/确认→真实可播资产→退出/重开→本人历史的全链路仍需授权验收。真实付费 Provider、真实资料上传不能继承旧批准|不得用合成完成任务或测试音频冒充真实生成|
|数据库与后端放行|MySQL/TLS 真验证、受控迁移审查；init_database 仍可能自动应用0013/0014，未挂账号路由不意味着部署安全。全仓5项收集错误保留，详见上一阶段分类|不访问现有用户库、不迁移生产、不以专项绿替代全仓绿|

正式开放顺序应是：完成上述候选/依赖 → Owner 授权指定非生产平台验收 → 留下实际用户操作证据 → 独立安全/产品核对 → 单独申请 Live Flags/迁移/发布权限。不得先打开默认功能再补验收。

音乐分享停止新增实施，保留 S7-PD-016 与禁用入口；原始病历图片、长期偏好门禁不变。医学独立签核、古琴棋盘格/真机视觉及原5项收集错误不由本工作包关闭。未 Merge、部署、生产迁移或调用付费 Provider。
