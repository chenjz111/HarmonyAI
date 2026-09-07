## 复审修复完成（2026-09-07）

**最新 HEAD**：`e523ac344c6bf8cf3539a3dec5e6b44ae8b8f5ba`

已根据 Issue #111 复审指令修正两项冻结合同漂移：

### 修复一：疗愈诉求字段验证对齐 V3.1 冻结规则

**提交**：`192a7ca` - "fix: align healing intent contract with V3.1 freeze rules"

**修改内容**：
- `frontend/common/v3-healing-intent.js`：重设 `decideHealingIntent()` 验证逻辑
  - ✅ custom_goal_text 可独立存在（无需选择 primary_goal）
  - ✅ 选择 other 无需强制填写文字
  - ✅ 全空时 skip=true（整页跳过，user_goal=null）
  - ✅ secondary_goal 需要 primary_goal（反向不成立）
  - ✅ primary_goal == secondary_goal 时阻止
  - ✅ 新增 reason code：`secondary_requires_primary` / `primary_equals_secondary` / `invalid_goal_code`

- `frontend/pages/v3-goal/v3-goal.vue`：移除清空 primary_goal 时同时清空 custom_goal_text 的错误逻辑

- `frontend/tests/sprint5-v3-owner-flow.test.mjs`：新增 12 个测试覆盖全部规则
  - ✅ 全空 → skip=true
  - ✅ custom-text-only → PASS
  - ✅ other without text → PASS
  - ✅ primary only → PASS
  - ✅ primary + secondary → PASS
  - ✅ secondary without primary → BLOCK
  - ✅ primary == secondary → BLOCK
  - ✅ custom text > 200 → BLOCK
  - ✅ code not in enum → BLOCK
  - ✅ 边界：恰好 200 字 → PASS
  - ✅ custom-text-only 超长 → BLOCK
  - ✅ secondary code 非法 → BLOCK

### 修复二：问卷单一权威来源（消除手工维护第二套问卷）

**提交**：`e523ac3` - "test: add comprehensive questionnaire manifest consistency checks"

**修改内容**：
1. **自动生成机制**（新增 `frontend/scripts/gen-manifest.mjs`）
   - 读取唯一权威来源：`knowledge/v3/questionnaire-v3.0.1.json`
   - 自动生成 `frontend/common/questionnaire-v3-manifest.js`
   - 标注「自动生成，禁止修改」和来源路径

2. **构建流程接入**（`frontend/package.json`）
   - `build:h5` 和 `build:mp-weixin` 命令自动执行 `gen-manifest.mjs`
   - 确保构建前问卷清单与正式 JSON 同步

3. **深度一致性测试**（`frontend/tests/sprint5-v3-owner-flow.test.mjs`）
   - ✅ 逐题对比：10 题数量、顺序、题目文案、选项文案、code、score、类型
   - ✅ checksum 校验：sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031
   - ✅ 五页分页：PAGE_SIZE=2，totalSteps=5
   - ✅ 单一来源校验：页面无硬编码问题文案（如"最近一周，你会不会比较容易着急"）
   - ✅ user_goal 配置深度对比（疗愈诉求 7 code、max_selections=2、custom ≤200）

### 验收结果

✅ **前端测试**：149/149 通过（新增 2 个一致性测试）

✅ **H5 Build**：DONE Build complete

✅ **questionnaire-v3.0.1.json**：零修改

✅ **现有正确流程**：完全保持不变
- 首页双卡片入口
- 无资料直接进问卷
- 有资料 1-3 张
- Relevance 异常页
- document_only 无第二次近期状态总结
- Player 不渲染生成方式/音调标签
- Feedback 选填
- Real/Mock 隔离

✅ **Android Build/真机**：暂无测试环境，合并后可验收

### Remaining Blockers（同 PR 描述）

后端依赖项（已在 PR 描述中如实标注）：
1. 多文档聚合/owner-aware 上传（蔡子鑫）
2. 五音解析 Read Model 端点
3. 音乐生成能力
4. 问卷真实提交端点

---

**Ready for Review & Merge**
