## 🎉 Sprint 2 已完成（2026-07-25）

> 核心代码今天已全部收尾。以下是每人 Day 14 验收前还需要完成的。

---

## 肖宇翔 — Medical Knowledge Engineer（Issue #18）

### 必须完成

1. **Level D 文献 0 → 2 篇**
   - 目前 18 篇文献中缺少 Level D（个案报告/经验总结）
   - 现有 2 篇 Level D（k_017 直肠癌个案、k_018 脾胃不和型失眠）已入库但等级标注需确认
   - 要求：每篇标注 credibility_level + source_type + applicable_emotions

2. **4 个证型缺现代文献**
   - 心火上炎（syd_003）、脾虚湿困（syd_005）、肺气虚（syd_006）、肾阴不足（syd_007）
   - 这 4 个证型在 `literature_chunks（依照demo_chunks）.jsonl` 中没有对应的现代临床文献
   - 至少每个证型补 1 篇（万方/知网/SinoMed 均可）

### 交付方式
- 直接更新 `knowledge/v2/chunks/literature_chunks（依照demo_chunks）.jsonl`
- 推送到 `feat/nob` 分支，提 PR 到 dev

---

## 蔡子鑫 — Backend Platform Engineer（Issue #16）

### 必须完成

1. **异常与降级处理**
   - 按 `docs/architecture/agent-architecture.md` 第 3 章规范
   - 当前 Router 缺少对 AI Engine 异常的统一处理：
     - LLM 调用超时 → 返回 degraded 状态 + warning
     - Chroma 查询失败 → 降级到纯规则处方
     - 数据库写入失败 → 回滚 + 返回错误码
   - 每个 Router 加 try/except，异常时返回 Universal Shell 而非 500

2. **Day 14 验收准备**
   - 本地启动 `uvicorn backend.app.main:app --reload`
   - 打开 `http://localhost:8000/docs`
   - 在 Swagger 里逐个调 5 个 POST 接口，确认全部返回 200

### 可选（不做不卡验收）
- 加 FOREIGN KEY 后跑一次完整的 DB migration 测试

---

## 彭翔 — Client Engineer（Issue #17）

### 必须完成

1. **前端对接真接口验证**
   - 今天 `api.js` 已更新格式（`emotion_scores` → `questionnaire`，`prompt_template` 字段对齐）
   - 需要确认：4 个页面在实际调用中不报错
   - 重点验证：survey.vue 提交问卷 → player.vue 显示音乐处方 → 播放 → 评分
   - `USE_MOCK = false` 模式下跑通全流程一次

2. **音频文件落地**
   - 当前 `generation_stub` 返回 `local://music/jiao-demo.mp3`，文件不存在
   - 需要准备至少 1-2 首可播放的本地音频（免费/CC 授权）
   - 放到 `frontend/static/music/` 目录下
   - 更新 `generation_router` 返回正确的本地路径

3. **Day 14 验收录屏**
   - 从头到尾录一遍完整流程（问卷 → 辨证 → 处方 → 播放 → 反馈）
   - 作为给老师的汇报素材

### 可选
- Mock 音频 URL 从外部 SoundHelix 换成本地文件

---

## 钟睿宸 — AI Engineering Lead（Issue #15）

### ✅ 实质上已完成

代码部分全部完成（今天代理修了 6 个 bug + Router 换真）。只剩：

1. **Day 14 验收当天到场**
   - 确认 `HARMONYAI_REAL_AGENTS=true` 模式下所有 Agent 正常运行
   - 如配置了 Qwen，现场演示 LLM + Chroma 真实链路
   - 如未配置，演示规则降级链路（也是完整闭环）

---

## 陈家智 — Project Leader & AI Architect（Issue #14）

### 还需完成

1. **向老师同步报告**（Day 13 前）
   - 当前进度：约 70-80%
   - 已完成：Walking Skeleton 闭环 + 全部 Agent 代码 + Router 换真
   - 当前问题：文献缺口、音频未落地
   - 下步计划：Day 14 验收 → Sprint 3

2. **Day 14 正式验收组织**
   - 定时间、发会议链接
   - 按 Sprint 1 验收标准逐人检查
   - 全程录屏存档

3. **曲库版权确认**（与彭翔协作）
   - 确认 5 调式音频来源
   - 确认无版权问题

---

## ⚠️ 全队提醒

- **日报制度**：今晚 21:00 开始在群里发日报（三句话：完成/问题/明天）
- **Deadline**：Day 14 正式验收前所有 Must Have 必须完成
- **分支规范**：代码走 feat 分支 → PR → 陈家智 Review → 合入 dev
