# 安装、运行及测试条件

状态：公开源码展示快照，尚非从零可复现的完整 App。下述启动步骤为源码接口说明，本轮没有执行安装、服务启动、数据库迁移或前端构建。专项实测以 VERIFICATION.md 为准。

## 环境

Python 声明版本见 pyproject.toml；运行包见 requirements.txt，可选 OCR 包见 requirements-ocr.txt。前端使用 package.json 与 package-lock.json，依赖 uni-app/Vue/Vite。当前不提供已验证的 Node 最低版本或完整 Python 锁文件；不能仅安装 pyproject 中的少数依赖就称环境完备。

## 后续获准复现时的顺序

1. 确认代码和依赖许可、隔离目录及允许写入范围；不要使用生产凭据、原上传或原数据库。
2. 如需安装，先准备经批准的离线 wheel/前端缓存。Python 可按 `python -m pip install --no-index --find-links <approved-wheel-directory> -r requirements.txt` 安装；此为未来操作模板，本轮未安装或验证依赖解析。
3. 人工创建仅含开发配置的本地环境，设置隔离 SQLite 和媒体目录。原 .env.example 因未完成逐项配置复核未复制，不要求用户从本候选复制不存在的文件。
4. 后端入口是 `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`。该过程会初始化数据库；当前知识资产缺失，不能保证所有路由可用，更不能声称 AI 业务链可运行。
5. 前端既有入口为在 frontend 下执行 `npm run dev:h5`；正式构建为 `npm run build:h5`。当前缺图片、字体和音频，且本轮没有安装、构建或浏览器/设备验收。
6. 正式检索另需获许可医学规则、manifest/chunks、Chroma 持久化目录和批准的 Embedding；Qwen 与音乐服务的真实调用还需单独的数据上传和费用许可。它们本轮均不启用。

## 模式与风险

前端默认 real，mock/hybrid 需显式选择；hybrid 不代表 AI 段真实调用成功。关闭 HARMONYAI_REAL_AGENTS 或不配置 Key 不是完整的网络禁止机制。后端存在显式调用真实服务的源码，阅读和复用不代表允许执行。

S6 的反馈/偏好策略按历史原样保留；S7 的学习关闭、Stream、认证及 TLS 后续修复没有回移。这是开发证据，不是生产安全版本。

## 本轮专项测试

原测试位置：

```text
tests/ai_engine/v3/test_prompt_compiler_v2.py
tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py
tests/ai_engine/test_langgraph_workflow.py
```

普通 pytest 命令可定位这些用例，但本轮正式结果必须结合外部离线保护器、清洁环境和隔离 sandbox。保护器位于独立验证环境，未把 S7 业务代码混入本候选，也尚未包装为本候选自身的可分发测试入口。完整从零复现仍需解决这项验证工具许可/交付及资源问题。

离线环境还必须给第三方库提供 sandbox 内的 USERPROFILE/APPDATA/LOCALAPPDATA，否则部分模块在收集阶段无法确定用户目录。这是验证启动环境修正，不是业务代码补丁。Windows asyncio 的 socketpair 阻塞仍未解决，异步 Provider 用例未完成。

运行完整仓库测试会遇到被排除的知识、素材、fixture、评估及工具模块；当前为 1837 collected / 6 errors。不删除或削弱断言来规避。当前不能用某个专项通过数代替完整测试和完整 App 验收。
