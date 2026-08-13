# S4-06 人工 Gate 清单

> 自动化测试不能替代真实环境验收。未执行时必须保持 `PENDING`，不得写成 PASS。

## 1. MySQL：PASS（2026-08-13 完成）

本机 MySQL 8.0.44 已通过人工验收。仓库不会保存、打印或提交本机安装路径和密码。

> ✅ 已完成（详见 `s4-06-manual-acceptance-result.md`）：connection / migration（首次+幂等）/ reconnect persistence / Session·Revision·Evidence·FollowUp·Feedback·AICallLog 持久化 / AI log privacy / cleanup safety / real API→MySQL chain 全部 PASS。

### MYSQL_NEXT_USER_ACTION

1. 在 MySQL 中创建独立数据库 `harmonyai_s4_acceptance`，并使用只对该库有权限的测试账户。
2. 在本机 PowerShell 会话中安全设置 `DATABASE_URL`；不要把密码发到聊天、Git、截图或命令记录中。
3. 在仓库根目录执行：`python -m tools.s4_mysql_acceptance`。
4. 将无敏感信息的 JSON 结果填写到 `docs/sprint4/s4-06-manual-acceptance-result.md`。

验收探针只允许连接数据库名 `harmonyai_s4_acceptance`，会验证增量迁移、幂等性、重连持久化、关键 Sprint 4 表和普通 AI 日志隐私钩子；最后只删除本次带唯一标记的验收行，不删除数据库、不清空其他数据、不 reset root。

通过条件：连接、迁移、持久化、隐私检查和验收数据清理全部成功；随后通过真实 API/客户端补充一次 Assessment、Revision、Evidence、Follow-Up、Confirmation、Feedback 链路证据。

## 2. OCR：MANUAL_OCR_POC_PENDING

仅使用合法、已授权、已脱敏的材料：至少一张 JPG、一张 PNG、一份多页 PDF；另准备损坏文件和可手工补录/跳过的降级样例。

- [ ] MIME、文件签名、大小、页数、加密 PDF 校验正确
- [ ] page/block text 与 confidence 可见
- [ ] OCR 文字允许用户编辑、确认，确认后才进入 Assessment
- [ ] `failed` 与 `degraded` 状态明确，不展示 Provider 原始异常
- [ ] OCR 不可用时可跳过并继续 narrative/questionnaire
- [ ] 普通日志不含原图、完整 OCR 原文或敏感字段
- [ ] 记录材料类型、页数、成功/失败状态和脱敏证据，不保存真实身份信息

只有真实脱敏材料完成 POC 后才能标记 PASS；synthetic 测试不能替代。

## 3. Android：MANUAL_ANDROID_TEST_PENDING

当前未检测到 ADB、Android SDK 或 HBuilderX。最低风险路线是安装/使用 HBuilderX，连接真实 Android 设备运行 uni-app；不要为本 Gate 盲目安装完整 Android Studio 工具链。

### 环境启动

1. 手机与电脑连接同一 Wi-Fi。
2. 运行：`powershell -ExecutionPolicy Bypass -File tools/start-s4-manual-acceptance.ps1`
3. 脚本动态显示当前 `Phone API URL`；不得把本机 LAN IP 提交为固定配置。
4. 构建/运行前在同一终端设置 `VITE_API_BASE_URL` 为脚本显示值。前端已有该环境变量机制。
5. 若 Windows 防火墙阻止 TCP 8000，只人工放行当前专用网络；脚本不会自动修改防火墙。

### 真机检查

- [ ] 安装、冷启动、欢迎页
- [ ] 20 题问卷、6 题 Quick State、narrative
- [ ] OCR 上传、编辑、确认、失败与跳过降级
- [ ] Assessment、Follow-Up Revision、Confirmation/Correction/Retry
- [ ] Diagnosis、Prescription、Music 播放/暂停/错误状态、Feedback
- [ ] Safety blocked、Diagnosis abstained、Needs Follow-Up、Prescription missing 均不调用 Music
- [ ] 返回、刷新、弱网、权限拒绝均无崩溃、白屏、原始异常或敏感日志
- [ ] 记录设备型号、Android 版本、测试 commit、网络、时间和截图/录屏证据

H5 PASS 不等于 Android PASS；没有真机证据时保持 `MANUAL_ANDROID_TEST_PENDING`。
