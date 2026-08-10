# HarmonyAI 竞赛提交准备清单 — Competition Readiness Checklist

> **基线版本**: dev @ `714f018` (2026-08-04)
> **最后检查**: 2026-08-05
> **目标**: 比赛演示 / 提交前逐项确认

---

## 一、环境检查

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 1.1 | Python 3.10+ 可用 | ☐ | `python --version` |
| 1.2 | 依赖安装完整 | ☐ | `pip install -r requirements.txt` |
| 1.3 | `.env` 文件已配置 | ☐ | 复制 `.env.example` → `.env`，填写真实值 |
| 1.4 | LLM API Key 已设置 | ☐ | `DASHSCOPE_API_KEY` 或等效环境变量 |
| 1.5 | 数据库可用 | ☐ | MySQL 或 SQLite（dev 默认 SQLite） |
| 1.6 | 测试全部通过 | ✅ | 392/392 passed（2026-08-05 验证） |
| 1.7 | 后端可启动 | ☐ | `uvicorn backend.app.main:app --reload` |
| 1.8 | 前端 Demo 可访问 | ☐ | 浏览器打开 `frontend/full-demo.html` |
| 1.9 | 静态文件服务正常 | ☐ | `frontend/static/music/jiao-demo.wav` 可访问 |
| 1.10 | 端口未被占用 | ☐ | 默认 8000 |

---

## 二、代码与版本检查

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 2.1 | 当前在 dev 分支 | ✅ | `git branch --show-current` → dev |
| 2.2 | dev 已与 origin/dev 同步 | ✅ | `git status` → up-to-date |
| 2.3 | 所有 Sprint 3 PR 已合并 | ✅ | PR #43-#50 MERGED |
| 2.4 | 无未提交修改 | ☐ | `git status` — 仅允许报告文件 |
| 2.5 | 版本号一致 | ☐ | `pyproject.toml` version → 当前为 `0.1.0`，需更新为 `0.3.0` |
| 2.6 | Git tag 已创建 | ☐ | `git tag v0.3.0-rc1` (建议) |

---

## 三、数据安全检查

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 3.1 | 无 `.env` 文件提交 | ✅ | 已验证 |
| 3.2 | 无 API Key 硬编码 | ✅ | 已验证 |
| 3.3 | 无真实用户数据 | ✅ | 已验证 |
| 3.4 | 无密码/Secret 泄露 | ✅ | 已验证 |
| 3.5 | `.gitignore` 覆盖完整 | ✅ | `.env`, `*.db`, `data/`, `__pycache__/` |
| 3.6 | Demo 数据均为虚构 | ☐ | 确认 `knowledge/` 中所有数据非真实患者信息 |
| 3.7 | 安全规则 JSON 有效 | ✅ | 已由 `test_safety_rules_json_valid` 验证 |
| 3.8 | 错误信息不泄露内部细节 | ✅ | 已由 `test_feedback_v2.py::test_v2_feedback_error_does_not_leak_internal_details` 等验证 |

---

## 四、功能检查

### 4.1 5-Agent 工作流

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 4.1.1 | Assessment Agent 可用 | ☐ | POST `/api/v2/assessments` |
| 4.1.2 | Diagnosis Agent 可用 | ☐ | 通过 workflow endpoint 触发 |
| 4.1.3 | Prescription Agent 可用 | ☐ | 通过 workflow endpoint 触发 |
| 4.1.4 | Music Agent 可用 | ☐ | POST `/api/v2/music` |
| 4.1.5 | Feedback Agent 可用 | ☐ | POST `/api/v1/feedback` 或 V2 路径 |

### 4.2 输入模式

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 4.2.1 | 仅问卷模式可用 | ☐ | `analysis_mode = questionnaire_only` |
| 4.2.2 | 自由文本 + 问卷可用 | ☐ | `analysis_mode = narrative_questionnaire` |
| 4.2.3 | 病例 + 问卷可用 | ☐ | `analysis_mode = document_questionnaire` |
| 4.2.4 | 全部三种输入可用 | ☐ | `analysis_mode = document_narrative_questionnaire` |
| 4.2.5 | Qwen 降级 → 本地规则可用 | ☐ | 不配置 Qwen key，验证问卷模式仍可产出结果 |

### 4.3 安全机制

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 4.3.1 | 自伤/自杀关键词拦截 | ☐ | 提交 `"我想自杀"` → 应返回 `SAFETY_SELF_HARM_OR_SUICIDE` |
| 4.3.2 | 胸痛关键词拦截 | ☐ | 提交 `"胸痛两小时"` → 应返回 `SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN` |
| 4.3.3 | 呼吸困难关键词拦截 | ☐ | 提交 `"呼吸困难说不出完整句子"` → 应返回安全警告 |
| 4.3.4 | 安全触发后不出音乐处方 | ☐ | 安全 blocked 时不返回 playable track |

### 4.4 Feedback 2.0

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 4.4.1 | 前端可提交 pre_state | ☐ | 播放前情绪评分 |
| 4.4.2 | 前端可提交 post_state | ☐ | 播放后情绪评分 |
| 4.4.3 | subjective_change 正确计算 | ☐ | API 返回 `subjective_change` 字段 |
| 4.4.4 | V1 反馈仍然可用 | ✅ | `test_v1_feedback_compatibility.py` 通过 |

---

## 五、Demo 演示检查

### 5.1 演示数据准备

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 5.1.1 | 预准备 1 个病例文本 | ☐ | 用于场景 1（病例上传演示） |
| 5.1.2 | 预准备 1 段自由描述 | ☐ | 如 `"最近工作压力大，失眠，烦躁"` |
| 5.1.3 | 预准备完整问卷答案 | ☐ | 30 题全部勾选 |
| 5.1.4 | Demo 音频文件可用 | ☐ | `jiao-demo.wav` 在浏览器可播放 |

### 5.2 演示流程

| # | 场景 | 状态 | 操作/备注 |
|---|---|---|---|
| 5.2.1 | **场景 1**: 病例 + 自由文本 + 问卷 → 音乐 → 反馈 | ☐ | 完整三输入流程 |
| 5.2.2 | **场景 2**: 自由文本 + 问卷 → 音乐 → 反馈 | ☐ | 无病例 |
| 5.2.3 | **场景 3**: 仅问卷 (Qwen off) → 音乐 → 反馈 | ☐ | 本地规则降级 |
| 5.2.4 | 安全拦截场景 | ☐ | 展示"自杀念头"→ 安全提示 + 求助建议 |
| 5.2.5 | 反馈对比展示 | ☐ | 播放前后的情绪变化（Feedback 2.0 pre/post） |

### 5.3 UI/UX

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 5.3.1 | `full-demo.html` 可正常渲染 | ☐ | 浏览器打开确认 |
| 5.3.2 | 所有步骤可正常推进 | ☐ | 自由文本 → 问卷 → 结果 → 播放 → 反馈 |
| 5.3.3 | 手机端适配 | ☐ | `max-width: 500px`，在手机浏览器测试 |
| 5.3.4 | 加载状态有提示 | ☐ | Spinner 动画 |
| 5.3.5 | 降级状态有提示 | ☐ | `degraded-warning` 显示"Qwen 不可用" |
| 5.3.6 | 安全拦截有明确提示 | ☐ | 红色警告 + 求助信息 |

---

## 六、文档检查

| # | 检查项 | 状态 | 操作/备注 |
|---|---|---|---|
| 6.1 | README.md 更新至 Sprint 3 | ☐ | 当前 README 可能需要更新项目介绍 |
| 6.2 | `.env.example` 完整 | ☐ | 缺少 LLM API Key 字段，建议补充 |
| 6.3 | 架构文档存在 | ✅ | `docs/architecture/`, `docs/agent-architecture.md` |
| 6.4 | ADR 记录完整 | ✅ | 6 个 ADR (ADR-0001 ~ ADR-0006) |
| 6.5 | Sprint 3 验收清单 | ✅ | `docs/sprint3-acceptance-checklist.md` |
| 6.6 | Demo 脚本 | ✅ | `docs/demo-script-sprint3.md` |
| 6.7 | 竞赛汇报材料 | ✅ | `docs/competition/` |
| 6.8 | Agent 契约文档 | ✅ | `docs/agent-contract-v2.md`, `docs/api-contract-v2.md` |

---

## 七、已知限制（比赛中需说明）

| # | 限制 | 应对策略 |
|---|---|---|
| 1 | **OCR 为 Stub** | 说明：当前版本 OCR 为预留接口，演示中使用预确认文本病例 |
| 2 | **曲库仅 1 首 Demo** | 说明：曲库匹配逻辑完整，可对接更大曲库 |
| 3 | **Qwen 依赖网络** | 说明：无网络时自动降级为本地规则引擎 |
| 4 | **前端的 UniApp 构建** | 说明：Demo 页面 (`full-demo.html`) 为独立 HTML，无需 HBuilderX |

---

## 八、快速启动命令

```bash
# 1. 确认环境
git checkout dev
git status                    # 应为 clean
python --version              # 3.10+

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env → 填入 DASHSCOPE_API_KEY（可选，不填则自动降级）

# 4. 运行全部测试（验证环境）
python -m pytest tests/ -v

# 5. 启动后端
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 6. 打开 Demo
# 浏览器访问: file:///path/to/HarmonyAI/frontend/full-demo.html
# API 地址默认为 http://localhost:8000
```

---

## 九、提交前最终确认

| # | 确认项 | ☐ |
|---|---|---|
| 1 | 全部 392 测试通过 | ☐ |
| 2 | 三个 Demo 场景运行成功 | ☐ |
| 3 | 安全拦截场景演示成功 | ☐ |
| 4 | 无敏感信息泄露 | ☐ |
| 5 | Git 状态 clean | ☐ |
| 6 | 版本号正确 | ☐ |
| 7 | README 已更新 | ☐ |
| 8 | 团队成员已知演示流程 | ☐ |

---

*清单由 Claude Code 自动生成，基于 2026-08-05 验收结果。比赛演示前请逐项检查并勾选。*
