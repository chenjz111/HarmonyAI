# HarmonyAI Sprint 4 — Scope & Boundaries

> **Sprint**: Sprint 4: Real Input & Grounded State Understanding
> **Version**: v0.4.0
> **Duration**: 12 working days (8 dev + 2 eval + 1 regression + 1 review)
> **Baseline**: v0.3.0 (dev @ `a38099c`)
> **Integration Branch**: `integration/sprint4-real-input`
> **Owner**: 陈家智 (Project Leader & AI Architect)

---

## 一、Sprint 目标

**唯一核心目标**: 用户提交的每一类信息都被真实处理；系统输出的每一个主要结论都有来源；信息不足时，系统会追问或拒绝判断，而不是强行给出看似完整的结果。

### 成功标准

| 指标 | 最低目标 |
|---|---|
| Questionnaire V2.1 Schema 通过率 | 100% |
| 有效自由文本处理率 | 100% |
| 输入静默丢弃率 | 0% |
| 证据引用正确率 | ≥95% |
| 无依据结论率 | ≤5% |
| 情绪/事件/身体信号综合 F1 | ≥0.80 |
| 冲突案例识别率 | ≥80% |
| 关键安全案例召回率 | 100% |
| 干净打印体 OCR 字符准确率 | ≥90% |
| Qwen 错误可解释率 | 100% |
| 20 题中位完成时间 | ≤5 min |
| 6 题中位完成时间 | ≤60 sec |
| 原有测试回归 | 392 项全部保持通过 |
| 敏感原文进入普通日志 | 0 条 |

---

## 二、Sprint 4 数据流

```
用户上传真实材料
  → 真实 OCR 识别 (PaddleOCR)
  → 用户确认 OCR 文本
  → 填写自由描述
  → Qwen 真实提取状态信息
  → 完成 20 题阶段性问卷
  → Assessment Agent 融合三类来源
  → 识别支持证据、冲突和缺失信息
  → 必要时生成动态追问 (0-6 题)
  → 用户回答并确认评估结果
  → Diagnosis Agent 基于确认后的证据输出辅助辨证倾向
  → 进入现有 Prescription → Music → Feedback 流程
```

---

## 三、保持不变的内容

- ✅ 五个 Agent 名称
- ✅ 三层架构
- ✅ LangGraph 工作流编排
- ✅ FastAPI 框架
- ✅ uni-app 前端框架
- ✅ SQLite/MySQL 技术选择
- ✅ V2 接口体系
- ✅ V1 兼容接口
- ✅ Prescription/Music/Feedback Agent 名称和基本职责
- ✅ Qwen OpenAI-compatible 接口方式
- ✅ 安全规则先于 LLM 执行的原则
- ✅ v0.3.0 基线代码

---

## 四、明确不做

| 推迟项 | 目标 Sprint |
|---|---|
| 真实音乐生成 API | Sprint 5+ |
| 扩充音乐曲库 | Sprint 5+ |
| 修改五音核心映射 | Sprint 5+ |
| 用户注册/登录 | 待定 |
| 会员/支付 | 待定 |
| 七日方案 | 待定 |
| 可穿戴设备 | 待定 |
| 重新设计整个 App | — |
| 继续维护比赛版 HTML 为主产品 | — |
| Agent 名称调整 | — |
| Docker 和完整 CI/CD | Sprint 5+ |
| 宣称问卷属于临床诊断量表 | — |

---

## 五、产品流程

### 5.1 阶段性完整评估

用户首次使用、两周后重新评估、或状态明显变化时：
- 填写 **20 题完整问卷** (V2.1)
- 预计 3-5 分钟

### 5.2 动态追问

Assessment Agent 根据用户信息决定 **0-6 题动态追问**（正常 1-3 题）。

触发条件:
- 时间不明确
- 影响程度不明确
- 问卷和文字冲突
- 两个候选倾向接近
- 用户表述过于模糊
- 身体信号需要确认
- 证据覆盖不足

### 5.3 每次音乐使用前

填写 **6 题快速状态问卷** (Quick State V1)，预计 30-60 秒。

### 5.4 音乐结束后

重复快速问卷中的前 5 题状态评分，供 Feedback Agent 计算听前/听后变化。

---

## 六、问卷体系

| 问卷 | 版本 | 题数 | 用途 |
|---|---|---|---|
| 阶段性完整评估 | `questionnaire_v2.1` | 20 | 首次/定期评估 |
| 快速状态 | `quick_state_v1` | 6 | 每次听前 |
| 动态追问 | `follow_up_v1` | 0-6 | Assessment 触发 |
| 旧版兼容 | `questionnaire_v2.0` | 12 | 向后兼容 |

---

## 七、分支和 PR 规划

| PR | 负责人 | 分支 | 内容 |
|---|---|---|---|
| S4-01 | 陈家智 | `feat/s4-contracts` | Sprint 范围与契约 (最先合并) |
| S4-02 | 肖宇翔 | `feat/s4-questionnaire-evals` | 问卷 V2.1 + 评估集 |
| S4-03 | 蔡子鑫 | `feat/s4-real-ocr-backend` | 真实 OCR + 后端基础 |
| S4-04 | 钟睿宸 | `feat/s4-ai-understanding` | Assessment/Diagnosis 增强 |
| S4-05 | 彭翔 | `feat/s4-frontend-flow` | uni-app 真实产品流程 |
| S4-06 | 陈家智 | `integration/sprint4-real-input` | 集成修复与最终验收 |

所有 PR 先进入 `integration/sprint4-real-input`，验收后进入 `dev`。

---

## 八、12 天排期

| Day | 内容 | 负责人 |
|---|---|---|
| 1 | 契约冻结 | 陈家智 |
| 2 | 问卷初稿 + PaddleOCR 验证 + Provider 设计 | 全员 |
| 3 | 正式契约落地 | 全员 |
| 4-5 | 核心并行开发 | 全员 |
| 6 | 第一次联调 | 全员 |
| 7-8 | 融合与追问 | 钟睿宸 + 彭翔 |
| 9 | 前端完整闭环 | 彭翔 |
| 10 | 评估日 (60 cases) | 全员 |
| 11 | 修复与全量回归 | 全员 |
| 12 | Sprint Review | 全员 |

---

## 九、团队分工

| 成员 | 角色 | Sprint 4 核心职责 |
|---|---|---|
| 陈家智 | Project Leader & AI Architect | 契约、集成、验收 |
| 肖宇翔 | Medical Knowledge Engineer | 问卷 V2.1、评估集、医学审核 |
| 钟睿宸 | AI Engineering Lead | Qwen Provider、文本提取、多源融合 |
| 蔡子鑫 | Backend Platform Engineer | OCR、数据库、API |
| 彭翔 | Client Engineer | uni-app 完整产品流程 |

---

## 附录 A: 风险评估与缓解措施

> 陈家智 AI Architect Review — 2026-08-06

### 🔴 A1. PaddleOCR 实际表现是最大未知数

**风险**: 要求"干净打印体 OCR 字符准确率 ≥90%"，但 PaddleOCR 在中文医疗文档上的表现受扫描质量、字体（手写病历基本无解）、表格混排影响。如果在 Day 10 评估日才发现准确率不达标，整个 Sprint 的核心交付物失败。

**缓解措施**:
- **Day 2 必须跑 PaddleOCR POC**：蔡子鑫用 5 份真实医疗文档（挂号单、检查报告）做验证
- 如果 POC 准确率 <70% → 立刻降级方案（如限制仅支持打印体 JPG，放弃 PDF 表格）
- 手写体不承诺（规划中已标注），评估指标只计算打印体

### 🔴 A2. 60 个评估案例标注工作量

**风险**: 每个案例需要标注 ≥10 个字段（情绪/事件/身体信号/时间/否定/冲突/缺失/追问/证型）。按 20-30 分钟/例计算，60 个需要 20-30 小时。肖宇翔同时还要完成 20 题问卷设计和评分规则。

**缓解措施**:
- **分两批**: Day 3 前完成 30 个核心案例（覆盖 5 个场景类型各 6 个）
- **自动预标注**: Day 4-5 钟睿宸跑一轮自动标注，肖宇翔 Day 6 只做纠错
- 剩余 30 个案例降级为"仅验证不细标"，用于回归而非训练

### 🔴 A3. 彭翔前端工作量可能不够 8 天

**风险**: 交付物清单包含 7 个页面/模块（document、questionnaire-v21、quick-state、narrative、assessment-result、assessment-followup、assessment-confirmation），加上 api-v2.js 和 session-store.js 的改动。全部做完可能超出 8 天。

**缓解措施**:
- **分优先级**:
  - P0 (Day 4-6): questionnaire-v21、quick-state、assessment-result（核心三页）
  - P1 (Day 7-8): narrative（升级）、assessment-followup
  - P2 (Day 9): document（上传+OCR+确认）、assessment-confirmation（复用现有组件）
- confirmation 页面复用现有 dialog/overlay 组件，不做独立页面

### 🟡 A4. 动态追问是功能复杂度最高的模块

**风险**: 追问质量影响用户体验极大。问太多→用户烦，问太少→信息不足，问错了→不专业。7 个触发条件之间的优先级、去重、合并都没有定义。

**缓解措施**:
- **Sprint 4 只用硬编码 if-else 决策树**，不上 LLM 生成追问
- 决策树规则在 Day 3 冻结，钟睿宸和肖宇翔共同确认
- "时间不明确"和"影响程度不明确"合并为一道复合追问
- 最多 4 题（而非规划中的 6 题），进一步控制体验风险

### 🟡 A5. Q04 worry_control 可能 double-count

**风险**: Q03（紧张频率）和 Q04（担忧控制困难）高度相关。如果两道题答案接近，tension_worry 维度会被双倍加权。医学术语叫"维度内共线性"。

**缓解措施**:
- **方案 A（推荐）**: Q04 只做定性记录（scored: false），不参与 tension_worry 维度聚合
- **方案 B**: Q03 和 Q04 做加权平均（各 0.5 权重），不是简单相加
- 决策权交给肖宇翔，但在评分规则 JSON 中必须明确标注

### 🟡 A6. evidence_coverage_score 算法

**风险**: 这个数字展示给用户作为"系统证据充分度"。算得不合理会直接打击用户信任。当前没有定义算法。

**缓解措施**:
- **Day 1 冻结公式**:
  ```
  coverage = (有证据的维度数 / 总维度数) × 来源多样性系数
  来源多样性系数 = min(1.0, 不同 source_type 数量 / 3)
  ```
  - 三源都有且维度全覆盖 → 1.0
  - 仅问卷 → 0.50
  - 算法透明，可向用户解释

---

## 附录 B: 排期风险评估

| 阶段 | 评估 | 说明 |
|---|---|---|
| Day 1-3: 契约冻结 | ✅ 可行 | 有 Sprint 3 经验，Review 可以压缩 |
| Day 4-5: 并行开发 | ⚠️ 偏紧 | 2 天太紧，OCR 可能需要更多调试 |
| Day 6: 第一次联调 | ⚠️ 风险 | 大概率暴露契约理解偏差，需要回修时间 |
| Day 7-8: 融合追问 | ⚠️ 风险 | 追问功能可能到 Day 8 还是半成品 |
| Day 9: 前端闭环 | 🔴 风险 | 如果 Day 6 联调出问题，这一天会被挤 |
| Day 10: 评估日 | ✅ 可行 | 前提是前 9 天无大翻车 |
| Day 11: 修复回归 | ✅ 可行 | 预留比例合理 |
| Day 12: Review | ✅ 可行 | |

**总体: 12 天可行，缓冲 1-2 天。** 关键路径: PaddleOCR POC → 第一次联调 → 前端闭环。如果 PaddleOCR 踩坑，需要立刻从"不做事项"中砍低优先级 feature（如前端非核心页面），不延总工期。

---

## 附录 C: 与 Sprint 3 的关键改进对比

| 维度 | Sprint 3 | Sprint 4 | 评价 |
|---|---|---|---|
| 范围控制 | 后期膨胀 | Day 1 写死不做事项 | 巨大改进 |
| OCR | Mock 固定文本 | PaddleOCR 真实识别 | 核心突破 |
| 自由文本 | 静默丢弃 | 显示处理状态 + 证据 | 用户信任飞跃 |
| 证据 | 不存在 | EvidenceItem 全链路 | 架构级升级 |
| 拒绝判断 | 不存在 | Abstained + 追问 | 产品成熟度标志 |
| 契约管理 | 众人各自定义字段 | 契约先行 → 冻结 → 开发 | 工程成熟度标志 |
| 评估体系 | 只有 pytest | 60 案例 + F1 + 覆盖率 + Schema | 质的飞跃 |

---

*陈家智审定，Sprint 4 Day 1*
