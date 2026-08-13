# S4-06 人工 Gate 清单

> 自动化测试不能替代以下真实环境验收。未执行时必须保持 PENDING，不得写成 PASS。

## 1. MySQL：USER_CREDENTIAL_REQUIRED

用户只需提供一个可用于独立测试库的 MySQL 用户名/密码、主机/端口和临时数据库名（例如 `harmonyai_s4_acceptance`）。不要提供 root 密码截图，不要把密码写入 Git、文档、命令历史或报告。不得 reset root，不得操作已有业务库。

一次性验收：

1. 用户创建/确认独立测试库并授予最小所需权限。
2. 当前 PowerShell 会话临时设置：`$env:DATABASE_URL='mysql+pymysql://<USER>:<URL_ENCODED_PASSWORD>@127.0.0.1:3306/harmonyai_s4_acceptance'`。
3. 启动：`python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`。
4. 确认启动迁移无异常，检查 `GET /health` 与 `GET /api/v2/providers/health`。
5. 通过真实 API 创建并查询 Assessment/Revision/Evidence/Follow-Up/Confirmation/Feedback。
6. 重启后端，确认迁移幂等、记录仍在、日志不含用户原文或数据库凭据。
7. 清除当前会话的 `DATABASE_URL`。测试库是否删除由用户明确决定。

通过条件：连接、增量迁移、重启幂等、关键 CRUD、隐私日志全部成功。

## 2. OCR：MANUAL_OCR_POC_PENDING

使用合法、脱敏且获授权的 JPG、PNG、多页 PDF，以及损坏文件和手工输入降级样例。

- [ ] 文件格式、签名、大小、页数校验
- [ ] page/block text 与 confidence
- [ ] 用户可编辑并确认 OCR 文本
- [ ] 确认后才进入 Assessment
- [ ] failed/degraded 状态明确，不显示原始 Provider exception
- [ ] OCR 不可用时可跳过并走 narrative/questionnaire
- [ ] 日志不记录原图、完整 OCR 原文或敏感字段
- [ ] 删除/保留策略符合隐私说明

只有真实脱敏材料走通后才可 PASS；synthetic 测试不能代替。

## 3. Android：MANUAL_ANDROID_TEST_PENDING

在真实设备记录型号、系统版本、构建 commit、网络环境和时间，逐项检查：

- [ ] 安装、冷启动、欢迎页
- [ ] questionnaire（20 题及 quick state）
- [ ] narrative
- [ ] OCR 上传、编辑、确认与失败降级
- [ ] assessment、follow-up revision、confirmation/correction/retry
- [ ] diagnosis、prescription
- [ ] music 播放/暂停/错误状态
- [ ] feedback
- [ ] safety blocked 不调用 music
- [ ] abstained/needs-follow-up 不调用 music
- [ ] 返回、刷新、弱网、权限拒绝
- [ ] 无崩溃、白屏、原始后端异常或敏感日志

没有真机证据时保持 PENDING。H5 PASS 不等于 Android PASS。
