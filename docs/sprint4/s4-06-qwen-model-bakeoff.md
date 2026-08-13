# S4-06 Qwen 模型观察性对比

> 日期：2026-08-13
> 性质：`OBSERVATIONAL_MODEL_CAPABILITY_BAKEOFF`
> 本实验只用于 Sprint 5 或更后续的模型选型，不改变 Sprint 4 权威 Formal 60 结果。

## 固定条件

- 数据：`evals/sprint4/hard-case-manifest.json` 中冻结的 15 个正式案例。
- 不修改 gold、expected、Frozen threshold、Prompt、RAG、pipeline、normalization 或 scorer。
- 两组均使用 `AsyncQwenCompatibleProvider`、`timeout=240s`、`max_retries=0`。
- 唯一变量：`QWEN_MODEL`。
- 非计分中英混合 probe 不进入指标。

## 结果

| 指标 | Qwen2.5 7B Instruct Q4_K_M | Qwen2.5 14B Instruct Q4_K_M |
|---|---:|---:|
| 执行案例 | 15/15 | 15/15 |
| 可比较输出 | 15 | 9 |
| Provider errors | 0 | 6 |
| Schema pass rate | 1.0000 | 0.6000 |
| Provider failure rate | 0.0000 | 0.4000 |
| Emotion F1 | 0.6552 | 0.6471* |
| TP / FP / FN | 19 / 3 / 17 | 11 / 2 / 10* |
| 总耗时 | 132.40 秒 | 1096.55 秒 |
| 平均耗时/案例 | 8.83 秒 | 73.10 秒 |
| Ollama runtime | 约 4.7 GB | 约 10.0 GB |
| 当前硬件分配 | 稳定运行 | 38% GPU / 62% CPU |

`*` 14B 的 F1 与 TP/FP/FN 只基于 9 个非 ERROR 输出；6 个 Provider error 被 evaluator 排除，不能把该 F1 解读为完整 15-case 的等价质量成绩。

14B Provider error：`C007`、`C009`、`C014`、`C024`、`C025`、`C053`。

## Per-label

| Label | 7B TP/FP/FN | 7B F1 | 14B TP/FP/FN* | 14B F1* |
|---|---:|---:|---:|---:|
| tension_worry | 7/0/2 | 0.8750 | 3/0/1 | 0.8571 |
| calm_wellbeing | 2/1/1 | 0.6667 | 1/1/0 | 0.6667 |
| emotional_recovery | 0/1/3 | 0.0000 | 0/0/1 | 0.0000 |
| overthinking | 2/1/4 | 0.4444 | 1/1/3 | 0.3333 |
| irritability_anger | 2/0/0 | 1.0000 | 2/0/0 | 1.0000 |
| low_mood | 1/0/4 | 0.3333 | 1/0/3 | 0.4000 |
| interest_loss | 3/0/0 | 1.0000 | 2/0/0 | 1.0000 |
| fear_unease | 2/0/3 | 0.5714 | 1/0/2 | 0.5000 |

## 运行门

- 14B download：COMPLETE，SHA256 PASS。
- Provider smoke：PASS，合法 JSON，冷启动约 14.5 秒。
- 3-case（默认 20 秒）：3/3 Provider error。
- 3-case（统一 240 秒、无重试）：1 个可比较输出、2 个 Provider error，约 362.13 秒。
- 15-case：完成，14B Provider failure rate 40%。

## 结论

14B 在当前 8 GB 显存机器上没有形成可部署的质量提升：hard subset F1 未高于 7B，错误率从 0% 升到 40%，总耗时约为 7B 的 8.3 倍。Sprint 4 继续使用 7B Q4。

该结论不证明 14B 模型能力普遍弱于 7B；它证明当前 14B Q4、当前硬件与当前 Provider 输出约束的组合不适合作为默认配置。云端 Qwen 或其他部署统一延期到 Sprint 5 或更后续。

## 权威 Formal 结果不变

- Model：`qwen2.5:7b-instruct-q4_K_M`
- Formal 60：60/60 executed，0 ERROR
- Emotion F1：`0.7407`
- Frozen target：`>= 0.80`
- Formal model quality：`NOT_MET`
- Owner disposition：`ACCEPTED_KNOWN_MODEL_LIMITATION`
- Sprint 4 emotion F1 optimization：`CLOSED`
