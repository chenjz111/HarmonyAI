# HarmonyAI Sprint 4 — Integration Checklist

> **Owner**: 陈家智
> **Integration Branch**: `integration/sprint4-real-input`
> **Target**: dev

---

## 一、PR 合并顺序

| 顺序 | PR | 负责人 | 分支 | 前置依赖 |
|---|---|---|---|---|
| 1 | S4-01 | 陈家智 | feat/s4-contracts | 无 |
| 2 | S4-02 | 肖宇翔 | feat/s4-questionnaire-evals | S4-01 |
| 3 | S4-03 | 蔡子鑫 | feat/s4-real-ocr-backend | S4-01 |
| 4 | S4-04 | 钟睿宸 | feat/s4-ai-understanding | S4-02, S4-03 |
| 5 | S4-05 | 彭翔 | feat/s4-frontend-flow | S4-02, S4-03 |
| 6 | S4-06 | 陈家智 | integration/sprint4-real-input | S4-02~S4-05 |

---

## 二、每阶段验收项

### S4-01: 契约

- [ ] `docs/sprint4/sprint4-scope.md` 已 Review
- [ ] `docs/sprint4/product-flow.md` 已 Review
- [ ] `docs/sprint4/assessment-contract-v2.1.md` 已 Review
- [ ] EvidenceItem Schema 冻结
- [ ] Conflict Schema 冻结
- [ ] MissingInformation Schema 冻结
- [ ] FollowUpQuestion Schema 冻结
- [ ] AssessmentRevision Schema 冻结
- [ ] InputProcessingStatus Schema 冻结
- [ ] 无字段各写各的情况

### S4-02: 问卷与评估集

- [ ] `knowledge/questionnaire-v2.1.json` 20 题完成
- [ ] `knowledge/questionnaire-scoring-v2.1.json` 评分规则完成
- [ ] `knowledge/quick-state-questionnaire-v1.json` 6 题完成
- [ ] 每道题含 question_id/module/text/type/time_window/options/dimension/scored/reverse_scored
- [ ] 单题不直接决定证型
- [ ] `evals/sprint4/cases.jsonl` 60 个案例完成
- [ ] `evals/sprint4/safety-cases.jsonl` 安全案例完成
- [ ] `evals/sprint4/labels/` 标注完成
- [ ] 两轮医学审核通过
- [ ] 不存在"确诊""患有""治疗"表述

### S4-03: OCR 与后端基础

- [ ] **Day 2 POC 先决条件**: 蔡子鑫用 5 份真实医疗文档验证 PaddleOCR 准确率，≥70% 通过，<70% 降级方案
- [ ] `backend/app/core/ocr.py` PaddleOCR 真实识别
- [ ] 图片 OCR 返回真实文本
- [ ] PDF OCR 分页处理
- [ ] 置信度按块返回
- [ ] OCR 失败明确提示，不返回假成功
- [ ] Mock 文本已删除
- [ ] 文件安全: MIME/签名/大小/PDF页数/加密拒绝
- [ ] 数据库迁移: ai_call_log/assessment_evidence/assessment_followup/assessment_revision/document 扩展
- [ ] SQLite 迁移通过
- [ ] MySQL 迁移通过
- [ ] GET /api/v2/providers/health 可用
- [ ] POST /api/v2/assessments/{id}/follow-up 可用
- [ ] PATCH /api/v2/assessments/{id}/confirmation 可用
- [ ] GET /api/v2/assessments/{id}/revisions 可用
- [ ] 日志不包含 Key 和病例全文
- [ ] 测试: test_real_ocr.py/test_document_confirmation.py/test_provider_health.py/test_assessment_followup.py/test_assessment_revision.py/test_questionnaire_v21_api.py

### S4-04: AI 理解

- [ ] Qwen Provider: 异步/重试/超时分类/错误码/JSON修复重试
- [ ] Token 统计 + 延迟记录
- [ ] Prompt 版本记录
- [ ] Mock Provider 用于测试
- [ ] 自由文本提取 13 类信息字段
- [ ] 每条有 evidence_quotes
- [ ] 不补造用户没说过的信息
- [ ] Qwen 不可用: processing_status=unavailable, used_in_assessment=false
- [ ] 问卷 V2.0 和 V2.1 同时接受
- [ ] Quick State V1 评分
- [ ] EvidenceItem 统一结构
- [ ] 来源合并/去重/否定/时间窗
- [ ] 冲突检测
- [ ] 缺失信息检测
- [ ] 动态追问生成 (0-6 题)
- [ ] Evidence Coverage 计算
- [ ] Assessment Revision 机制
- [ ] 用户修正融合
- [ ] Diagnosis: candidate_tendencies + supporting/contradicting evidence
- [ ] Diagnosis: 可 abstained
- [ ] 评估脚本: evals/run_sprint4_eval.py + evals/metrics.py
- [ ] 所有输出通过 Schema
- [ ] 无依据结论率 ≤5%
- [ ] 日志不记录敏感全文

### S4-05: 前端

- [ ] 20 题问卷页面 (JSON 动态渲染)
- [ ] 6 题快速问卷页面
- [ ] 文档上传 → OCR 处理 → 编辑 → 确认完整流程
- [ ] 自由文本处理状态显示
- [ ] Assessment 结果页 (来源/摘要/维度/证据/冲突/缺失/追问)
- [ ] 用户可点状态标签查看来源证据
- [ ] 追问交互
- [ ] 确认交互 (完全准确/部分准确/不准确)
- [ ] 结果版本切换
- [ ] H5 通过
- [ ] ≥1 台安卓手机测试通过
- [ ] 正常流程不依赖 full-demo.html

### S4-06: 集成验收

- [ ] 原有 392 测试全部通过
- [ ] Sprint 4 新增测试全部通过
- [ ] 60 案例评估完成
- [ ] 10 项验收场景逐一跑通:
  1. [ ] 20 题完整评估
  2. [ ] 6 题快速评估
  3. [ ] 文档+文本+问卷三源融合
  4. [ ] 来源冲突
  5. [ ] 动态追问
  6. [ ] 用户确认
  7. [ ] Qwen 不可用
  8. [ ] OCR 失败
  9. [ ] 安全阻断
  10. [ ] Diagnosis 拒绝判断 (abstained)
- [ ] SQLite 和 MySQL 均可运行
- [ ] H5 正常
- [ ] 安卓手机正常
- [ ] dev 合并

---

## 三、验收定级

| 等级 | 标准 |
|---|---|
| P0 阻塞 | 安全案例不通过；数据库迁移失败；原有测试回归失败 |
| P1 必须修复 | 关键验收场景不通过；Schema 不通过；证据引用错误 |
| P2 建议修复 | UI 细节；非关键流程降级体验 |
| P3 可推迟 | 优化项；非核心路径 |

---

## 四、Sprint 4 完成定义

- [ ] 所有 P0 和 P1 项关闭
- [ ] `integration/sprint4-real-input` 合并到 `dev`
- [ ] `docs/sprint4/sprint4-final-report.md` 已发布
- [ ] Sprint Review 演示完成
- [ ] 团队全员确认

---

*陈家智审定*
