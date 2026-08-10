# README 更新方案

> **目标文件**: `README.md`（当前 145 行）
> **当前状态**: 描述 Sprint 1-2，无 Sprint 3 内容
> **日期**: 2026-08-05

---

## 一、当前 README 问题

### 1.1 缺少 Sprint 3 章节

README 详细描述了 Sprint 1 和 Sprint 2，但**完全没有 Sprint 3 内容**。新增的核心能力未体现：

- 多模态输入（病例上传 + 自由文本 + 问卷）
- 统一工作流端点（V2）
- Feedback 2.0（pre/post 对比）
- Qwen / OCR 降级
- 安全规则引擎

### 1.2 项目结构过时

当前（第 68-81 行）:
```
├── docs/
├── schemas/v1.0/    ← 已不存在
├── prompt/v1/       ← 路径已变
├── knowledge/v1/    ← 已升级到 v2/
├── backend/
├── frontend/
├── api/             ← 已不存在
├── logs/
└── deploy/
```

### 1.3 版本信息混乱

| 位置 | 当前值 | 应更新为 |
|---|---|---|
| README 隐含版本 | Sprint 2 | Sprint 3 |
| FastAPI description (main.py) | "Sprint 2" | "Sprint 3" |
| 演示命令 | Sprint 1/2 demo | Sprint 3 workflow |

### 1.4 缺少快速启动指南

没有清晰的"新人 5 分钟启动"流程，启动命令散落在多个 demo 章节中。

---

## 二、建议的 README 结构

```
# HarmonyAI（和鸣AI）                              ← 保留
一句话定位                                           ← 保留
Project Principles                                   ← 保留
系统架构                                             ← 更新（反映 V2）
团队                                                 ← 保留
技术栈                                               ← 更新（+pytest, SQLite, V2）
项目结构                                             ← 重写（当前实际结构）
快速启动 🆕                                          ← 新增
  ├── 环境要求
  ├── 安装依赖
  ├── 配置环境变量
  ├── 运行测试
  └── 启动服务
Sprint 3 新能力 🆕                                   ← 新增
  ├── 多模态输入
  ├── V2 统一工作流
  ├── Feedback 2.0
  └── 降级优雅性
演示 🆕                                              ← 新增（替代旧 Sprint 1/2 章节）
  ├── 打开 Demo 页面
  └── 场景 1/2/3
旧版演示（参考）                                      ← 折叠/简化
项目生命周期                                          ← 保留
License                                              ← 保留
```

---

## 三、具体修改点

### 修改 1: 项目结构（第 68-81 行）

**当前**:
```
HarmonyAI/
├── docs/
├── schemas/v1.0/
├── prompt/v1/
├── knowledge/v1/
├── backend/
├── frontend/
├── api/
├── logs/
└── deploy/
```

**改为**:
```
HarmonyAI/
├── backend/
│   ├── ai_engine/    ← 5 Agent + LangGraph + Chroma
│   └── app/          ← FastAPI + Routers + Models + Schemas
├── frontend/
│   ├── pages/        ← narrative, survey-v2, player-v2, feedback-v2
│   ├── common/       ← api-v2.js, sprint3-session.js
│   └── full-demo.html ← 比赛演示页面
├── tests/
│   ├── ai_engine/    ← 26 测试
│   ├── api/          ← 13 测试
│   └── knowledge/    ← 2 测试
├── knowledge/
│   ├── v2/           ← 问卷 V2 + 安全规则 + 文献
│   └── v1/           ← 旧版映射
├── docs/
│   ├── architecture/
│   ├── release/      ← RC 报告 + 比赛清单
│   └── sprint3-*.md
└── prompt/           ← Agent Prompt 模板
```

### 修改 2: 新增 "快速启动" 章节

```markdown
## 快速启动

### 环境要求
- Python 3.10+
- 浏览器（Chrome / Edge）

### 安装 & 运行

```bash
# 1. 克隆仓库
git clone <repo-url> && cd HarmonyAI
git checkout dev

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境（可选 — 不配则自动降级为本地规则）
cp .env.example .env
# 编辑 .env → 填入 QWEN_BASE_URL, QWEN_API_KEY（可选）

# 4. 运行测试
python -m pytest tests/ -q
# 预期: 392 passed

# 5. 启动后端
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 6. 打开 Demo
# 浏览器打开 frontend/full-demo.html
# 或访问 Swagger API 文档: http://localhost:8000/docs
```
```

### 修改 3: 新增 "Sprint 3 能力" 章节

```markdown
## Sprint 3 新能力

| 能力 | 说明 |
|---|---|
| 🌐 **多模态输入** | 支持病例上传(PDF/JPG) + 自由文本 + 30题问卷，AI 自动分析来源组合 |
| ⚡ **V2 统一工作流** | POST /api/v2/workflows 一次调用完成全部 5 Agent |
| 📊 **Feedback 2.0** | pre/post 前后状态对比，量化情绪变化，个人偏好优化 |
| 🛡️ **安全规则引擎** | 自伤/自杀/严重症状关键词拦截，LLM 调用前即阻断 |
| 🔄 **优雅降级** | Qwen 不可用时→本地规则引擎；OCR 失败→使用预确认文本 |

### 分析模式

| 模式 | 输入 | 适用场景 |
|---|---|---|
| questionnaire_only | 仅问卷 | 离线 / 快速评估 |
| narrative_questionnaire | 自由文本 + 问卷 | 有主观描述 |
| document_questionnaire | 病例 + 问卷 | 有就诊记录 |
| document_narrative_questionnaire | 全部三种 | 最完整评估 |
```

### 修改 4: 旧演示章节精简

将第 99-145 行的 Sprint 1/2 演示章节合并为一个折叠或简化的"历史版本演示"章节。

### 修改 5: FastAPI description (main.py)

`backend/app/main.py` 第 49 行:
```python
# 当前
"## Sprint 2 — 五 Agent 独立端点\n"
# 改为
"## Sprint 3 — V2 统一工作流 + 多模态评估\n"
```

并添加 V2 端点说明:
```python
"## Sprint 3 — V2 端点\n"
"| `/api/v2/assessments` | 多源状态评估 |\n"
"| `/api/v2/workflows` | 五 Agent 工作流 |\n"
"| `/api/v2/music` | 本地曲库匹配 |\n"
```

---

## 四、修改文件清单

| 文件 | 修改类型 | 优先级 |
|---|---|---|
| `README.md` | 重写部分章节 | 🔴 |
| `backend/app/main.py` | FastAPI description + 端点表 | 🟡 |

---

## 五、决策建议

| 方案 | 内容 | 推荐 |
|---|---|---|
| **最小改动** | 只修复过时信息（项目结构、版本号）+ 加 Sprint 3 能力表 | ⭐ 比赛前 |
| **完整重写** | 按新结构重写 README，含完整快速启动 + 演示章节 | 赛后 |

> 建议比赛前做最小改动（30 分钟工作量），确保评委看 README 时能了解 Sprint 3 的核心能力。

---

*由 Claude Code 生成，基于 2026-08-05 代码审查。未修改任何代码。*
