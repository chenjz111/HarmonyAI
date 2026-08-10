# HarmonyAI 竞赛发布计划 — Competition Release Plan

> **基线**: dev @ `714f018` (2026-08-04)
> **审查日期**: 2026-08-05
> **目标**: 比赛现场 Demo 准备与发布

---

## 一、当前版本

| 维度 | 值 |
|---|---|
| 分支 | dev |
| HEAD | `714f018` |
| 版本号 (pyproject.toml) | `0.1.0` ⚠️ 需更新 |
| 版本号 (.env.example) | `1.0.0` ⚠️ 与 pyproject 不一致 |
| 测试 | 392/392 passed |
| Sprint 3 PR | #43-#50 全部合并 |
| dev 领先 main | 218 commits 🔴 |

---

## 二、发布前必须修复（🔴 阻塞）

### 2.1 版本号更新

| 文件 | 当前值 | 应为 | 优先级 |
|---|---|---|---|
| `pyproject.toml` | `version = "0.1.0"` | `version = "0.3.0"` | 🔴 |
| `.env.example` | `APP_VERSION=1.0.0` | `APP_VERSION=0.3.0` | 🔴 |
| `backend/app/core/config.py` | `APP_VERSION: str = "1.0.0"` | `"0.3.0"` | 🔴 |

> 三处版本号不一致，且都未反映 Sprint 3 状态。

### 2.2 `.env.example` 缺少 LLM 字段

当前 `.env.example` 仅有 MySQL/Redis/JWT/CORS，但代码实际读取以下环境变量：

```
QWEN_BASE_URL      ← backend/ai_engine/providers.py:92
QWEN_API_KEY       ← backend/ai_engine/providers.py:93
QWEN_MODEL         ← backend/ai_engine/providers.py:94
HARMONYAI_REAL_AGENTS ← backend/app/core/agent_config.py:17
```

**必须在 `.env.example` 中补充这些字段**，否则新人无法配置 LLM。这些字段在 README 第 122-126 行有文档，但 `.env.example` 中缺失。

### 2.3 `requirements.txt` 缺少核心依赖

`requirements.txt` 缺少：
- `langgraph>=0.2`
- `chromadb>=1.2`

这两个依赖只在 `pyproject.toml` 中声明。如果新人按照 `pip install -r requirements.txt` 安装，运行时将因缺少 `langgraph` 和 `chromadb` 而报错。

### 2.4 `full-demo.html` 使用 V1 API

`frontend/full-demo.html` 当前调用的是 Sprint 2 的 V1 端点：

```
/api/v1/assessment   (并非 /api/v2/assessments)
/api/v1/diagnosis    (并非 /api/v2/workflows)
/api/v1/prescription
/api/v1/generation
/api/v1/feedback
```

这意味着比赛 Demo 页面**不会展示 Sprint 3 的核心能力**（V2 工作流、Feedback 2.0 pre/post 对比、narrative_text、document upload）。

### 2.5 `main` 分支严重落后

```
main: 30b72cf (Initial commit, 2025)
dev:  714f018 (PR #50, 2026-08-04)
Gap: 218 commits
```

需要在发布前执行 `main ← dev` merge，并打 tag。

---

## 三、建议修复（🟡 非阻塞）

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 3.1 | README 无 Sprint 3 章节 | 评委无法快速了解当前版本能力 | 在 README 添加 "Sprint 3" section |
| 3.2 | README 项目结构过时 | 仍显示 `schemas/v1.0/`、`prompt/v1/` 等已不存在的目录 | 更新为当前实际结构 |
| 3.3 | FastAPI description 显示 "Sprint 2" | Swagger UI 首页过期 | 更新 `main.py` 中的 description 字符串 |
| 3.4 | `full-demo.html` API 地址硬编码为 `localhost:8000` | 无法快速切换到其他地址 | 可接受，比赛现场通常是 localhost |
| 3.5 | 远程旧分支未清理 | 彭翔-feature/sprint1-frontend 等 9 个旧分支 | 赛后清理 |

---

## 四、发布流程

```
Step 1: 修复阻塞问题
├── 更新 pyproject.toml version → 0.3.0
├── 更新 .env.example 补充 LLM 字段
├── 更新 requirements.txt 添加 langgraph + chromadb
├── 更新 full-demo.html → V2 API（或确认 V1 可用）
└── 更新 backend/app/core/config.py APP_VERSION

Step 2: 验证
├── python -m pytest tests/ -q          # 392 passed
├── pip install -r requirements.txt     # 无报错
├── python -c "import langgraph; import chromadb"  # 验证
└── 手动启动后端 + 打开 full-demo.html

Step 3: 合并发布
├── git checkout main
├── git merge dev                       # fast-forward expected
├── git tag v0.3.0
├── git push origin main --tags
└── git checkout dev                    # 回到 dev 继续开发
```

---

## 五、Demo 流程

参见 `docs/release/demo-runbook.md`

### 推荐演示场景

| 顺序 | 场景 | 用时 | 展示重点 |
|---|---|---|---|
| 1 | 自由文本 + 问卷 → 音乐处方 → 播放 | ~3 min | 核心闭环、多模态输入 |
| 2 | 仅问卷 (Qwen off) → 降级 → 本地规则 | ~2 min | 容错能力、离线可用 |
| 3 | Feedback 2.0 pre/post 对比 | ~1 min | 反馈闭环、效果量化 |
| 4 | 安全拦截 (输入"想自杀") | ~30 sec | 安全机制 |

---

## 六、已知限制（比赛中如实说明）

| # | 限制 | 说明方式 |
|---|---|---|
| 1 | **OCR 为 Stub** | "当前版本 OCR 为预留接口，演示中使用预确认文本病例。PaddleOCR 集成在规划中。" |
| 2 | **曲库仅 1 首 Demo** | "曲库匹配逻辑完整，当前装载 1 首 Demo 曲目。对接更大曲库后可直接扩展。" |
| 3 | **Qwen 需要网络** | "无网络时自动降级为本地规则引擎，核心流程不受影响。" |
| 4 | **Generation Agent 使用本地曲库** | "音乐生成当前匹配本地曲库而非实时 AI 生成，确保输出可控可审核。" |

---

## 七、比赛现场注意事项

### 7.1 环境准备

- [ ] 比赛电脑预装 Python 3.10+
- [ ] 确保 `pip install -r requirements.txt` 一次性成功
- [ ] 准备 `.env` 文件（含或不含 Qwen Key 均可演示）
- [ ] 确认端口 8000 未被占用
- [ ] 浏览器可播放 WAV 音频
- [ ] 准备手机热点（备用网络）

### 7.2 Demo 准备

- [ ] 预填一份完整问卷答案（快速演示用）
- [ ] 准备一段自由文本（如"工作压力大失眠"）
- [ ] 确认 `jiao-demo.wav` 可播放
- [ ] 准备"安全拦截"演示文本

### 7.3 备用方案

- [ ] **网络故障**: 不配 Qwen Key → 纯本地规则演示
- [ ] **后端启动失败**: 准备 `full-demo.html` 截图/录屏
- [ ] **音频播放失败**: 准备音频播放替代方案
- [ ] **数据库问题**: 默认 SQLite，零配置

---

## 八、版本历史

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1.0 | 2025 | 项目初始化、Sprint 1：FastAPI 脚手架 + 前端交付 |
| v0.2.0 | 2026-07-22 | Sprint 2：5-Agent 独立端点 + Real Agent + Chroma |
| v0.3.0 | 2026-08-04 | Sprint 3：V2 工作流 + 多模态 + Feedback 2.0 + 降级 |

---

*由 Claude Code 生成，基于 2026-08-05 审查结果。*
