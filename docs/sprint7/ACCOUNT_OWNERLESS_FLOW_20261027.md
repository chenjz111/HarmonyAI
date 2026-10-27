# 账号重启时未确认流程的隔离 — 2026-10-27

用户离线期间继续已批准的账号身份连续性工作。真实风险：账号恢复开始时会先移除本地owner标记并保留评估流程；若应用在此期间被回收，重启后可能出现Registered模式、仍有流程、但owner标记缺失。旧实现会先请求Refresh并把未确认流程带到恢复账号，网络失败时还会清掉该流程。后端数据归属未改变，但本地流程可能跨身份或丢失。

修复：在Owner标记与流程归属无法判断时，关闭运行时身份、通知页面并清理身份关联临时音频，先保留本地未确认流程，再让客户端凭据/journal失效并要求重新认证；不发Refresh、不创建游客、不自动认定新owner。正常同owner刷新保持原流程；明确登录切换仍沿用原有清理行为。本地保留不承诺服务器数据找回，也不新增长期数据保留政策。

RED：原Node Guard复现重启时先调用Refresh且未按IDENTITY_REQUIRED拒绝。首次修复后独立审查发现两项P2：读取owner异常会误删未确认流程，写身份epoch异常时缺少通知。新增两个用例均先失败，再改成读取结论确认前默认保留流程；无法更新epoch时仍尽力清音频及通知页面。独立复核未发现新的有证据P1/P2。

原Guard固定清单、账号启动定向回归；H5真实隔离ASGI同Cookie jar/双进程与Android候选账号ASGI均通过；H5编译109/109素材；完整前端719p/0f/0skip，原Guard未改。证据位于外置`orphan-owner-reviewed-{full,h5,h5-asgi,native-asgi,fixed}-20261027`目录。Hosted CI须核验提交SHA。合成存储和ASGI不是Android Keystore、真实浏览器、系统回收或设备验收；既有测试APK来自40be62e，不含本次JS修复。未创建APK、访问真实Provider/生产数据库或启用Live Flags。
