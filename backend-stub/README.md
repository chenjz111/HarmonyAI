# HarmonyAI 后端 Stub（Sprint 1 验收辅助）

这是一个最小化的本地后端服务，让前端在蔡子鑫正式后端不可用的情况下，也能演示"真实调用 POST /api/assess"。

## 用途

- Sprint 1 验收时，前端不再使用写死在前端的 mock 数据
- 问卷提交会真实发出 HTTP 请求到本机 `localhost:8000`
- 后端返回动态的评估结果、处方信息和音频 URL

## 启动方式

### 方式一：双击运行（推荐）

直接双击 `run.bat`，等待出现 `Application startup complete` 即可。

### 方式二：命令行

```bash
cd C:\Users\Lenovo\Documents\HarmonyAI\backend-stub
pip install -r requirements.txt
python server.py
```

启动成功后：
- 接口文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/

## 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/assess` | 提交问卷，返回评估结果 |
| GET | `/api/prescription/{session_id}` | 获取音乐处方 |
| POST | `/api/feedback` | 提交播放反馈 |

## 前端如何切换

打开 `frontend/common/api.js`，确认：

```js
const BASE_URL = 'http://localhost:8000'
const USE_MOCK = false
```

这样前端就会请求这个本地后端。

## 注意事项

- 本 stub 只用于 Sprint 1 演示真实网络调用，不包含 AI 辨证逻辑
- 返回的音频 URL 是公开测试音频（SoundHelix），不是真实中医音乐
- 等蔡子鑫正式后端 ready 后，把 `BASE_URL` 改成他的地址即可
