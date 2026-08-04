# HarmonyAI 前端

HarmonyAI 比赛版前端基于 Vue 3 与 uni-app。Sprint 3 默认从欢迎页进入八页流程：材料上传（可跳过）→ 自由描述（可跳过）→ 12 题图文问卷 → 可解释状态评估 → 本地曲库音乐播放器 → Feedback 2.0 → 完成页。

## 本地运行

```powershell
cd frontend
npm install
npm run dev:h5
```

后端默认地址为 `http://localhost:8000`。需要更换时设置 `VITE_API_BASE_URL`；真实后端始终是默认模式。

只有明确设置 `HARMONYAI_USE_MOCK=true` 时才启用演示 Mock。不要用 Mock 结果冒充真实 Agent 或实时音乐生成。

## 验证

```powershell
node --test tests/*.test.mjs
npm run build:h5
```

`node_modules/` 与 `unpackage/` 已忽略，不应提交到 Git。

## 边界

- 病历 OCR 当前为需要用户确认的辅助识别，不构成诊断。
- Qwen 不可用时降级到确定性问卷评估。
- 音乐来自本地曲库匹配，`source_type` 为 `matched`，不是实时生成。
- 用户反馈仅更新个人偏好，不能自动修改全局医学知识规则。