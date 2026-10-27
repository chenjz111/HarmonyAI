# Android 自有原生候选源码复核 — 2026-10-27

保留此前Owner批准的UTS/Kotlin项目自有候选、既有测试包名和仅USB本机HTTPS方案；本轮没有下载、云打包、证书创建或设备操作。上次OkHttp/Okio classpath失败仍未经过新编译验证。config.json使用显式compileOnly既有DCloud运行时版本的候选接法，不宣称已解析/链接。

独立只读审查覆盖RefreshVault、NativeHttps、桥接、合成设备检查和候选源准备器。发现P2：Java URI和OkHttp对编码点段规范化不同，原路径前缀检查可能将凭据发到同源白名单外路径。候选修复使用最终OkHttp规范路径校验、拒绝路径百分号、发送前再核对Request；query编码仍允许。复核未发现新增P1/P2。依据为确切[OkHttp3.12.12官方HttpUrl源码](https://raw.githubusercontent.com/square/okhttp/parent-3.12.12/okhttp/src/main/java/okhttp3/HttpUrl.java)。这是源码层关闭，实际原生编译/负例请求检查仍NOT RUN。

本轮临时音频清理只删除该模块在应用cacheDir生成且匹配命名的文件；不删除历史MusicAsset、上传资料或任意路径。前端仅跟踪本应用授权下载返回的临时文件；换身份、Player卸载和迟到下载清理，快速切歌竞态已由离线真实controller修复。

全部原生安全capability仍false。合成Keystore检查不替代真实账号/备份/强杀测试。候选准备器只在仓库外新目录插入检查页和公开测试CA；源码默认网络配置仅系统信任、禁HTTP、禁备份，不提交私钥/签名缓存。默认App不挂载检查页或启用账号。
