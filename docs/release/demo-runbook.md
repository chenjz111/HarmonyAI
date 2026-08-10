# HarmonyAI 比赛现场 Demo 执行手册 — Demo Runbook

> **基线**: dev @ `714f018`
> **日期**: 2026-08-05
> **用途**: 比赛现场演示操作指南

---

## 一、启动前检查

```bash
# 1. 确认环境
cd HarmonyAI/
git status                              # 应为 dev, clean
python --version                        # 3.10+

# 2. 安装依赖
pip install -r requirements.txt         # 确保无报错

# 3. 检查关键包
python -c "import langgraph; import chromadb; print('OK')"

# 4. 跑冒烟测试
python -m pytest tests/ -q              # 392 passed 即 OK

# 5. 确认 .env
cp .env.example .env                    # 首次
# 编辑 .env:
#   方案 A（有网）: 填入 QWEN_BASE_URL, QWEN_API_KEY, QWEN_MODEL, HARMONYAI_REAL_AGENTS=true
#   方案 B（无网）: 不填，系统自动降级为本地规则
```

---

## 二、启动步骤

### 启动后端

```bash
# 终端 1: 启动 FastAPI
cd HarmonyAI/
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**验证**: 浏览器打开 `http://localhost:8000/docs` → 应看到 Swagger UI

### 打开 Demo

```bash
# 直接在浏览器打开
file:///C:/Users/ASUS/HarmonyAI/frontend/full-demo.html
```

或者使用 Python 静态服务：
```bash
cd frontend/
python -m http.server 3000
# 浏览器打开 http://localhost:3000/full-demo.html
```

---

## 三、演示步骤

### 场景 1: 自由文本 + 问卷 → 音乐处方 → 播放（~3 min）⭐ 推荐开场

```
Step 1: 输入自由文本
  在文本框输入（或粘贴预准备文本）:
  "这两周工作压力很大，老板催项目催得紧，
   昨晚又失眠了，今天胸口闷闷的，整个人都很烦躁。"

Step 2: 点击"下一步" → 进入问卷
  依次回答 30 道问卷题目
  （预准备答案可快速完成）

Step 3: 点击"开始分析"
  等待 AI 分析（约 5-10 秒）
  → 展示"情绪画像"（各维度评分条形图）
  → 展示"中医辨证"（证型 + 置信度）
  → 展示"音乐处方"（五音 + 乐器 + BPM + 推荐理由）

Step 4: 点击播放
  → 音频播放
  → 展示"角调·木音"对应"疏肝解郁"

Step 5: 提交反馈
  → 滑动评分条（紧张度/身体紧绷/脑疲劳/整体评分）
  → 提交后展示 pre/post 对比

🎤 解说要点:
  "用户输入自由文本描述自己的状态 →
   AI 通过多模态评估分析情绪维度 →
   中医辨证引擎给出证型 →
   处方引擎将证型映射为音乐参数 →
   从本地曲库匹配合适曲目 →
   用户反馈形成闭环优化"
```

### 场景 2: 仅问卷 (Qwen off) → 降级 → 本地规则（~2 min）

```
Step 1: 跳过自由文本（留空），直接进入问卷

Step 2: 完成 30 题

Step 3: 点击"开始分析"
  → 右上角显示"仅问卷"模式标签
  → 黄色提示条: "当前使用规则引擎（Qwen不可用或失败）"
  → 仍产出完整的情绪画像 + 辨证 + 音乐处方

🎤 解说要点:
  "即使没有 LLM 服务，HarmonyAI 仍可完整运行。
   问卷评分使用医学团队审核的确定性规则，
   辨证使用本地规则引擎，
   处方基于五音理论映射表，
   全流程离线可用 — 这是降级优雅性的核心设计。"
```

### 场景 3: Feedback 2.0 闭环（~1 min）

```
Step 1: 完成任意场景到达播放页面

Step 2: 注意播放前的状态:
  → pre_tension（听前紧张度）
  → pre_body_tension（听前身体紧绷）
  → pre_mental_fatigue（听前脑疲劳）

Step 3: 播放音乐后，提交反馈:
  → post_tension（听后紧张度）
  → post_body_tension（听后身体紧绷）
  → post_mental_fatigue（听后脑疲劳）
  → overall_rating, relaxation_rating, music_match_rating

Step 4: 查看 subjective_change（主观变化）:
  → "紧张度: 7 → 4 (-3)"
  → "脑疲劳: 8 → 5 (-3)"

🎤 解说要点:
  "Feedback 2.0 引入 pre/post 前后状态对比，
   不只是'喜欢/不喜欢'，而是客观量化情绪变化。
   这些数据用于长期优化个人音乐偏好。"
```

### 场景 4: 安全拦截（~30 sec）—— 可选

```
Step 1: 在自由文本框输入:
  "我最近总是想自杀，活着没有意思。"

Step 2: 点击"下一步"
  → 页面变红色警告
  → 显示: "检测到安全风险，建议寻求专业帮助"
  → 心理援助热线: 12320 / 12355
  → 不会继续进入问卷

🎤 解说要点:
  "安全是第一优先级。系统在 LLM 调用前就拦截
   所有自伤/自杀/严重躯体症状关键词，
   不会让 AI 处理这些输入，直接引导求助。"
```

---

## 四、备用方案

### 方案 A: 网络故障 → 离线降级

```
症状: Qwen 请求超时，或一开始就没配 Key
应对: 
  1. 不填 QWEN_* 环境变量
  2. 启动后端，自动使用本地规则
  3. 演示场景 2（仅问卷降级）
  
解说: "这正是我们设计的降级优雅性 — 无网络仍可运行。"
```

### 方案 B: 后端启动失败

```
症状: uvicorn 报错
排查:
  1. python -c "from backend.app.main import app"  # 检查导入
  2. python -m pytest tests/ -q                     # 确认测试通过
  3. 检查端口 8000: netstat -an | findstr 8000
  4. 切换端口: uvicorn ... --port 8001

终极备用: 展示测试结果 + full-demo.html 录屏
  "我们的 392 个自动化测试全部通过，
   验证了所有 Agent 的输入输出契约。"
```

### 方案 C: Demo 页面无法加载

```
症状: full-demo.html 空白或 JS 报错
排查:
  1. 浏览器 F12 → Console 查看错误
  2. 确认后端在运行: curl http://localhost:8000/docs
  3. 检查 CORS: 后端默认允许所有来源

备用: 使用 Swagger UI (http://localhost:8000/docs) 手动调用 API
  展示 POST /api/v2/assessments → POST /api/v2/workflows → POST /api/v2/music
```

### 方案 D: 音频无法播放

```
症状: jiao-demo.wav 不播放
排查:
  1. 文件存在: ls frontend/static/music/jiao-demo.wav
  2. 浏览器支持: Chrome/Edge 均支持 WAV
  3. 直接访问: http://localhost:8000/static/music/jiao-demo.wav

备用: 展示音乐处方参数（曲目名、乐器、BPM、五音调式）
  "处方引擎已匹配正确的音乐参数，
   实际播放可在任何支持 WAV 的播放器中进行。"
```

---

## 五、时间分配建议（总计 ~7-8 分钟）

| 阶段 | 用时 | 内容 |
|---|---|---|
| 开场介绍 | 30 sec | 一句话定位 + 三层五Agent架构图 |
| 场景 1: 自由文本+问卷 | 3 min | 核心闭环演示 |
| 场景 2: 降级演示 | 1.5 min | Qwen off → 本地规则 |
| 场景 3: Feedback 2.0 | 1 min | 前后对比 |
| 安全展示 | 30 sec | 安全拦截 |
| 总结 | 1 min | 创新点 + 技术栈 + 团队 |

---

## 六、比赛现场所需文件清单

| # | 文件/物品 | 用途 |
|---|---|---|
| 1 | 笔记本电脑 | 运行 Demo |
| 2 | HarmonyAI 仓库 (dev 分支) | 全部代码 |
| 3 | `.env` 文件（已配置） | 环境变量 |
| 4 | 预填问卷答案 | 快速演示用 |
| 5 | 预准备自由文本 | Demo 输入 |
| 6 | 架构图 (PPT/图片) | 辅助讲解 |
| 7 | 手机热点 | 备用网络 |
| 8 | 本手册 | 操作参考 |

---

## 七、异常处理决策树

```
Demo 出错？
├── 后端启动失败 → 展示测试结果 + 架构图讲解
├── Qwen 超时 → 切换到降级演示（场景 2）
├── 前端白屏 → Swagger UI 手动调用 API
├── 音频不播 → 展示处方参数 + 讲解匹配逻辑
└── 全部不可用 → 基于 392 测试结果 + 架构文档讲解
```

**核心原则**: 任何环节出错，都有退路。降级本身就是核心卖点。

---

*由 Claude Code 生成，基于 2026-08-05 审查结果。比赛现场请携带打印版或电子版。*
