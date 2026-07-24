# HarmonyAI 前端项目

uni-app + Vue3 实现的 HarmonyAI 客户端，已具备 Sprint 1 完整页面流程。

## 快速开始

1. 打开 HBuilderX：`C:\HBuilderX\HBuilderX.exe`
2. 文件 → 打开目录 → 选择 `C:\Users\Lenovo\Documents\HarmonyAI\frontend`
3. 运行 → 运行到浏览器 → Edge / Chrome

## 项目结构

```
frontend/
├── pages.json              # 页面路由 + TabBar 配置
├── manifest.json           # 应用配置
├── App.vue                 # 根组件
├── main.js                 # Vue3 入口
├── index.html              # 浏览器入口
├── vite.config.js          # Vite 配置
├── common/
│   └── api.js              # API 接口层（mock / 真实接口切换）
└── pages/
    ├── index/index.vue     # 首页
    ├── emotion/emotion.vue # 情绪选择页
    ├── survey/survey.vue   # 问卷页（30 题分 3 步）
    └── player/player.vue   # 播放页（处方 + 播放器 + 评分）
```

## 页面流程

```
首页 → 开始健康评估 → 情绪选择页 → 问卷页（30 题）→ 播放页 → 评分反馈
```

## 墨刀原型

https://modao.cc/proto/FlcAW0kyti9vu1eMTgUYW/sharing?view_mode=read_only&screen=rbpVPY1RCheNZgeEz

## 当前状态

- ✅ 4 个页面完整流程
- ✅ 问卷页 30 题可交互
- ✅ 提交后进入播放页
- ✅ 播放器 + 五星评分
- ✅ 每个页面具备 loading / success / error 状态
- ⏳ 等待后端 API 接入（修改 `common/api.js` 中 `USE_MOCK = false`）
- ⏳ 等待真实音频 URL
