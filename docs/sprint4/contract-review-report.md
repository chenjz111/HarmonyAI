# HarmonyAI Sprint 4 — Contract Review Report

> **审查日期**: 2026-08-10
> **审查范围**: S4-01 八份契约文档与 `tests/contract/`
> **状态**: ✅ Ready for Freeze — Contract FROZEN
> **分支**: `integration/sprint4-real-input`

---

## 一、同步状态

- 已执行 `git fetch origin`。
- 已按 `dev → integration` 方向将 `origin/dev@e0640b3` 合入 integration。
- 合并无冲突；未修改 `dev`。

## 二、原审查阻塞项与解决结果

| 原阻塞项 | 解决结果 | 状态 |
|---|---|---|
| Q19 漏掉“偶尔闪过” | 只有“从未有过”继续普通评估；其他答案全部进入 safety flow | ✅ |
| Q20 “无以上情况”可与紧急项并选 | 冻结为互斥选项 | ✅ |
| V2.0 q12 safety 迁移可能丢失 | 普通信号→Q16，自伤→Q19，胸痛/呼吸困难→Q20 | ✅ |
| 普通日志允许截断用户原文 | 禁止任何用户原文及截断文本；只保留元数据白名单 | ✅ |
| Follow-Up 4/6 不一致 | 全文统一为 0–4，`max_questions_total=4` | ✅ |
| Q04 未决 | 冻结为 `dimension=worry_control`、`scored=false`、`weight=0`、定性 Evidence | ✅ |
| EvidenceItem.value 只允许 int | 冻结为 numeric/string/list[string]/appetite object 四分支联合 Schema，并按 category 判别 value 形状 | ✅ |
| Evidence Coverage 惩罚可选输入 | coverage 与 source_diversity 拆分；来源数量不参与追问判定 | ✅ |
| `dimensions_scored=15` 硬编码 | 从 canonical questionnaire 中 `scored=true` 的唯一维度动态推导 | ✅ |
| Provider 同步/异步接口不完整 | 冻结 `complete_json()` 与 `acomplete_json()` 的共同语义 | ✅ |
| Contract Tests 存在空断言与 placeholder | 使用 canonical fixtures 重写为真实契约验证 | ✅ |
| Canonical questionnaire fixture 选项不完整 | 补齐 Q01/Q02/Q05/Q16/Q17 冻结选项，并新增完整性断言 | ✅ |
| Fixture 与文档只能验证 JSON 语法 | 增加冻结选项集、安全路由、Q16/Q20 互斥和 category/value 错配反例 | ✅ |
| JSON 示例含 `...` 无法解析 | 所有 `json` fenced examples 与 fixtures 均可解析 | ✅ |

## 三、Canonical Contract Fixtures

- `tests/contract/fixtures/questionnaire-v2.1.contract.json`
- `tests/contract/fixtures/assessment-v2.1.contract.json`
- `tests/contract/fixtures/provider.contract.json`

这些 fixtures 只冻结 S4-01 契约，不替代 S4-02 的正式 `knowledge/*.json` 交付物。

## 四、验证证据

- Contract Tests：`30 passed`，无 skip、无空断言。
- Full Tests：`422 passed`，`1 warning`。
- Warning：现有 Starlette/httpx 测试依赖弃用提示，不是本次变更引入的失败。

## 五、Remaining Blockers

无 S4-01 Contract blocker。

Q04 内容已经冻结；S4-02 仍需由肖宇翔根据本契约生成并医学审核正式问卷 JSON，这属于后续 Issue，不是 S4-01 blocker。

## 六、结论

**Ready to merge S4-01: YES**

本结论仅表示契约和 Contract Tests 可以合并，不代表 S4-02～S4-06 已完成。
