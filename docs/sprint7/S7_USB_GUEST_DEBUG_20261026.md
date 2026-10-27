# Sprint 7 USB Guest 本地真机联调 — 2026-10-26

## Owner批准与范围
本轮Owner明确批准复用本机隔离FastAPI与HBuilderX内置ADB、仅当前USB设备的reverse、严格Android开发构建127.0.0.1:8000 HTTP例外，先验证合成Guest创建/身份/会话/重启。不使用公网隧道，不引入软件/插件，不重新云打包。此决定是开发验收例外，不改变Account Security R1、正式HTTPS或产品Live Flags。

## Sprint6实际机制
历史ref origin/codex/s6-player-seek-final，4d935bb，docs/sprint6/acceptance-runtime.md §§1–2明确：后端127.0.0.1:8010、VITE_API_BASE_URL=http://127.0.0.1:8010、adb reverse tcp:8010 tcp:8010；明确排除0.0.0.0，且验收端口不硬编码进前端默认值。不是仅据README默认localhost猜测。历史验收库和外置凭据文件均未打开或复用。
当前 frontend/.hbuilderx/launch.json 为standard Android base。当前手机已有8000→8000与8001→8001 reverse；未手工改任何映射，HBuilder运行后另出现8002调试映射。本次后端始终127.0.0.1:8000，独立SQLite。

## 最小代码差异
- frontend/common/api-origin.js：仅DEV===true、MODE===development、VITE_S7_USB_GUEST_DEBUG==='1'、实际Android App、显式地址严格等于http://127.0.0.1:8000时接受HTTP。其他端口、localhost别名、LAN、用户信息、路径/query、正式构建均拒绝。
- frontend/common/android-platform.js：USB模式明确日志标识，固定健康探测；Registered组装即使给出accepted适配器也停止，不能安装原生账号网络组件。SSL校验仍true。
- frontend/tests/s7-usb-guest-debug.test.mjs：4项边界测试。
- 本地被gitignore的.env.development.local启用上述开发profile。未写入.env.local或production配置；未改变正式manifest/network XML和业务页面。

## 操作与实际证据
1. 手机已有curl，通过reverse读/health返回healthy；不安装诊断软件。
2. HBuilder停止旧运行后重新标准基座运行，实际5.15开发编译加载profile并显示USB标识。
3. 手机首先提示身份失效：旧基座凭证不能被新隔离库验证。保持原凭据，未静默覆盖。Owner明确确认旧身份可丢弃后，在手机通过既有“使用新的游客身份”警告/确认操作继续；非清数据或绕过鉴权。
4. Owner确认首页出现两个真实入口；DB users5→6、identities4→5、sessions2→3，music_assets/generation_tasks保持0。
5. Owner从最近任务划掉并重开基座。PID21671→28929，证明并非只热刷新。Owner确认入口仍可用；identities保持5、users保持6、sessions3→4，最近两会话同owner，全部身份hash集合不变。因此Guest凭据在实际Android App进程重启中保留并通过服务端鉴权，首页新建会话符合现有行为。
6. 未验证后端重启恢复：当前测试JWT key仅在后端进程内，后端重启会使隔离Token失效，不能把本次App重启说成后端重启/永久找回通过。

## 验证
新增边界先RED2f/2p，再GREEN4p；既有Android11p、Guest/Startup/Runtime41p，共56相关用例通过，原offline_node未改。正式App资源编译exit0、问卷manifest hash不变，实际产物USB开关函数编译为return false、无USB环境变量引用。资源编译不生成新APK；当前真机标准基座不是正式APK权限验收。此候选未commit/push，Hosted CI NOT RUN。
证据：外置usb-guest-debug-20261026/{mechanism.json,result.json,phone-before-restart.json,phone-after-restart.json,build-result.json,build.log}。未记录原始JWT、密码或设备存储内容。

## 下一阶段评估与限制
本机服务目前只开放health/Guest/identity/session；资料上传、生成、账号均503。要测历史/收藏/Player/Feedback，需准备来源清楚的合成历史和可辨识测试音频、明确非生产路由范围，并对既有单一Player做实际编解码/Range/seek验证。默认音乐库false、账号不启用；没有开启新Provider、分享、原图、偏好学习或医学规则。
未测：网络物理中断、手机重启/重装、Keystore、Registered、真实音乐、正式HTTPS/MySQL。原5项后端收集错误及医学独立签核不因本阶段关闭。
恢复操作：保持后端进程、数据线与8000 reverse；HBuilder在该隔离frontend目录运行标准基座。.env.development.local仅本机开发使用。回退只需停用该开发profile，不能在正式构建启用HTTP。


## 2026-10-26 真机播放故障跟进

Owner 后续批准本机完整 Guest 流程及最多 10 次真实 API 调用。当前独立预算按所有付费 POST 保守计数为 7/10（含 1 次音乐生成）；本次播放修复未重新生成。
显式非生产 USB profile 增加音乐库接线；默认发布与其他平台门禁保持关闭，不代表音乐库正式验收。

设备已证实标准 URL 解析器缺失、Object.hasOwn 缺失。我的页面后者已修复，Owner 已确认入口可用。
新增实际 Vue reactive 回归证实：历史 session 和 controller 的 raw/proxy 引用比较误判，分别丢弃历史加载结果和播放状态/错误回调。改为捕获存储后的相同响应式引用，保留 owner、epoch、加载代次校验。
音频下载仅在已批准 USB debug 上接受精确 http://127.0.0.1:8000/api/v3/music/assets/[A-Za-z0-9_-]+/stream，无标准 URL 时仍能鉴权下载；其他地址继续 fail-closed，未关闭证书校验。

相关 91 项回归通过；生产 App 资源编译通过（非 APK）。完整前端回归及手机实际声音/进度复验另见外部证据 playback-fix/frontend-native-final；手机播放尚待 Owner 返回结果，不能标记通过。
现有真实 MP3 约 23.93 秒、数据库 24 秒，而处方请求 240 秒，时长不符仍未解决；不得循环拼接、伪造时长或重复付费生成掩盖。

Owner 手机复验结果：从历史重新进入同一首音乐后，有声音且时间开始增长。仅此 USB 标准基座路径通过；独立 APK/Registered 安全验收未通过本结果替代。完整前端 671 passed / 1 failed，Guard 未变；失败为素材恢复测试固定整个 Player 旧 SHA，与本次已复现并修复的响应式逻辑变更冲突，保留断言和失败证据，未用修改 checksum 制造全绿。
