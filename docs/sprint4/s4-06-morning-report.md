# S4-06 夜间收口 Morning Report（2026-08-13）

> 作者：Claude Code（自主执行）
> 分支：`fix/s4-06-integration`（PR #65 worktree）
> 基线：`dd92f09`（2026-08-12 权威结论，emotion_f1 = 0.7362）
> 本次新增：commit `4b36f90`

---

## 0. 一句话结论

**emotion_f1 未达 0.80 的根本原因不是 evaluator 的 value 语义（那是红鲱鱼），而是 Qwen2.5-7B-q4 的叙事情绪抽取能力 + gold 标注中「问卷 vs 叙事」优先级的不一致。本夜完成了 value=0 不对称的合法修复（0.7362 → 0.7407），并确认：在不降阈值、不改 expected、不 Mock、不换 DeepSeek 的约束下，无法自主把 F1 提到 0.80——需要 Contract Owner 拍板两项决策。**

---

## 1. 本夜做了什么（按计划阶段）

| 阶段 | 内容 | 结果 |
|---|---|---|
| TDD | 新增 `_actual_emotion_present`（问卷 salience 阈值）+ 回归测试 | ✅ 81/81 通过 |
| 离线重算 | 确定性重算 value 语义三态 | ✅ BEFORE 0.7362 / AFTER 0.7407 / NAIVE 0.346 |
| 冲突融合 + 证据审计 | 55 例 per-label 混淆分析 + FN/FP 根因分类 | ✅ 完成（见 §4） |
| 最终正式 60 | 用生产 runner + 本地 Formal Qwen 重跑 | ✅ 60/60 executed，0 ERROR，emotion_f1 **0.7407** |
| 全量回归 | `pytest tests/` | ✅ 610/610 passed |

## 2. 本次 commit（Checkpoint B，`4b36f90`）

**「fix(evals): restore questionnaire emotion salience on actual side」**

核心修正是把「presence」和「salience」两个概念分离：

- `_emotion_present`（presence）：value≥1 = present，value=0/absent = absent。这是 Contract Owner 2026-08-13 的「value≥1=present」决定，**仅用于 expected 侧**和证据的 existence 判定。
- `_actual_emotion_present`（label-set salience）：在 presence 基础上，问卷来源的情绪**额外要求 value≥3**才计入 emotion_f1 标签集。叙事/document 来源的情绪由 Qwen 抽取、天然 salient，不受此阈值约束。

**为什么要还原 value≥3 阈值**：上一棒（Checkpoint A，`5988b27`）把「value≥1=present」直接套到了 emotion_f1 标签集，导致离线重算 F1 从 0.7362 **塌缩到 0.346**——因为问卷对每个 case 报 ~6 个 value=2（"有时"）的背景情绪，而 gold 的 emotion_states 是叙事派生的、只标 2-3 个 salient 情绪（"只标明确出现的情绪状态"）。

**value=0 不对称修复（合法保留）**：expected 侧原先把 value=0 / polarity=absent 的 emotion_states 也当作「必须有」，而 actual 侧正确视其为缺席。修复后 expected 侧经 `_emotion_present` 丢弃 value=0/absent 标签。这是唯一一个「只改 evaluator 就带来正向收益」的点，幅度 +0.0045。

## 3. 权威数字

| 指标 | 值 | 阈值 | 状态 |
|---|---:|---:|---|
| emotion_f1（保存 2026-08-12） | 0.7362 | ≥ 0.80 | FAIL |
| **emotion_f1（value=0 修复后）** | **0.7407** | ≥ 0.80 | **FAIL** |
| event_f1 | 0.7500 | ≥ 0.75 | PASS（临界） |
| physical_f1 | 0.8000 | ≥ 0.80 | PASS（临界） |
| safety_recall | 1.0 | = 1.00 | PASS |
| schema_pass_rate | 1.0 | = 1.00 | PASS |
| provider_failure_rate | 0.0 | ≤ 0.05 | PASS |

> `0.7407` 已由**最终正式 60 重跑**机器落盘确认（`evals/sprint4/results/s4-06-evaluation-final.json`，60/60 executed / 0 ERROR）：`emotion_f1 = 0.7407407407407407`，与离线确定性重算（0.740741）完全一致（Qwen temperature=0 输出确定）。非 Mock、非伪造。

## 4. emotion_f1 缺口根因（value=0 修复后：TP=60, FP=14, FN=28）

### 4a. 漏报 FN=28 的分类

| 根因桶 | 数量（约） | 代表 case | 说明 |
|---|---:|---|---|
| **H 模型质量（叙事漏报）** | ~15 | C002/C008/C009/C014/C015/C016/C017/C020/C053 | Qwen7B-q4 对成语/英文/隐含表达（提不起劲/开了很多窗口/活着没意思/缓过来/anxious/针对我）提取失败；词法回退只能命中字面关键词 |
| **问卷 value 1/2 salience 歧义** | ~8 | C023/C039/C041/C029/C037/C047 | gold 把问卷 value 1/2（偶尔/有时）情绪计入，actual 侧 value<3 丢弃 → FN |
| **冲突消解 / 语义边界** | ~5 | C005/C011/C025/C029/C037 | tension vs fear vs overthinking 重叠、反向题、叙事"还好"的否定语义 |

per-label FN（value=0 修复后）：low_mood=9, fear_unease=5, emotional_recovery=4, overthinking=4, tension_worry=3, calm_wellbeing=1, interest_loss=1, irritability_anger=1。

### 4b. 误报 FP=14 的分类

| 根因桶 | 数量（约） | 代表 case | 说明 |
|---|---:|---|---|
| **问卷 value 3/4 过度纳入** | ~9 | C024/C026/C027/C046/C049/C050 | gold 有时又把问卷 value 3/4 情绪**排除**（叙事优先），actual 纳入 → FP |
| **词法过度触发** | ~3 | C003/C010/C038 | "翻来覆去"→overthinking（实为睡眠）、"平静"→calm（实为"有时候"）、"烦躁不安"→fear（实为 irritability） |
| **冲突消解** | ~2 | C046/C050 | narrative 与 questionnaire 打架时 gold 的取舍无法从冻结文档推导 |

per-label FP：fear_unease=3, calm_wellbeing=3, interest_loss=3, tension_worry=2, low_mood=1, overthinking=1, emotional_recovery=1。

## 5. 关键结论：value 语义是红鲱鱼，但问卷语义是真实歧义

1. **value=0 修复（已做）**只带来 +0.0045。离 0.80 还差约 12 个错误（需 FP+FN ≤ 30，当前 42）。
2. **问卷情绪在 gold 中的纳入不是一个 value 的确定性函数**：gold 有时纳入 value 1/2（→FN），有时排除 value 3/4（→FP）。任何「统一按 value 阈值纳入/排除」的 evaluator 改动都会在一个方向上引入大量新错误——「value≥1」塌缩到 0.346 就是铁证。
3. 真正能上 0.80 的路径只有两条，**都需要 Owner 决策**：
   - **更强 Qwen 模型（14B+ 或云端）**：修复 ~15 个叙事漏报 FN 即可把 FN 压到 ~13，F1 ≈ 0.816。受限于 8GB VRAM 无法本机执行（14B q4 ≈ 9GB）。
   - **Contract Owner 重标/澄清问卷情绪在 gold 的纳入语义**：消除 ~8 FN + ~9 FP 的问卷优先级歧义。

## 6. 需要 Owner 拍板的两项决策（阻塞上 0.80）

| # | 决策 | 选项 | 后果 |
|---|---|---|---|
| D1 | 问卷情绪在 gold emotion_states 的纳入规则 | A：仅叙事/document 派生；B：value≥3 纳入；C：重标 | 消除 ~17 个问卷语义错误 |
| D2 | 是否换更强 Qwen（14B/云端 API） | A：本机 7B（当前）；B：14B 量化（需更大显存）；C：云端 API（需预算） | 消除 ~15 个叙事漏报 FN |

> 这是「新的契约语义，无法从冻结文档推导」——按约束，本夜**不做**自主决定，仅 flag。

## 7. 手工 Gate（未伪造，保持 PENDING）

| Gate | 状态 |
|---|---|
| MySQL | `USER_CREDENTIAL_REQUIRED` |
| OCR | `MANUAL_OCR_POC_PENDING` |
| Android | `MANUAL_ANDROID_TEST_PENDING` |

## 8. 红线遵守声明

- ✅ 未降 emotion_f1 阈值（仍 0.80）
- ✅ 未改 expected 只为过线（value=0 修复是消除 expected/actual 不对称的合法性修正）
- ✅ 无 case-specific hardcode
- ✅ 未用 Mock / DeepSeek 冒充 Formal Qwen（重跑用本地 Ollama `qwen2.5:7b-instruct-q4_K_M`）
- ✅ 未删测试、未放宽 schema、未关 safety gate
- ✅ 未删 evidence grounding、未破坏 privacy
- ✅ 未 force push、未动 dev/main、未 tag v0.4.0、未 release

## 9. 总状态

**`AUTOMATED_ACCEPTANCE_FAILED`**（唯一未达标项 emotion_f1 = 0.7407 < 0.80；根因 = 模型质量 H + 问卷标注语义，均需 Owner 决策）。

## 10. 复现命令

```bash
cd C:\Users\ASUS\HarmonyAI-s4-contract-fix
# 最终正式 60（本地 Formal Qwen，已执行）
QWEN_BASE_URL=http://localhost:11434/v1 QWEN_API_KEY=ollama \
QWEN_MODEL=qwen2.5:7b-instruct-q4_K_M \
python evals/run_sprint4_eval.py \
  --cases evals/sprint4/cases.jsonl \
  --safety-cases evals/sprint4/safety-cases.jsonl \
  --output evals/sprint4/results/s4-06-evaluation-final.json --verbose
# 全量回归
python -m pytest tests/ -q    # 610 passed
```
