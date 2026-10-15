# HarmonyAI Two-Mode Five-Tone Decision Contract V2.1

```text
Status: FROZEN
Scope: Product semantics + five-tone routing contract
Implementation status: IMPLEMENTED
Implementation acceptance: OWNER ACCEPTED
Android Owner Product Acceptance: PENDING
Git Closure: PENDING
Sprint 6 Closure: PENDING
```

本文是正常五音决策路径的产品语义与 routing authority。Two-Mode V2.1 bounded implementation 与 selection-impact counterfactual 已完成并通过 Owner backend acceptance；新的 normal path 不再产生 `integrated_regulation`。本次 implementation acceptance 不替代仍处于 pending 的 Android Owner Product Acceptance、Git Closure 或 Sprint 6 Closure。

## 1. Normal Production Modes

新的 normal production path 只允许：

```text
personalized_five_tone
basic_wellness
```

`integrated_regulation` 的状态为：

```text
LEGACY COMPATIBILITY ONLY
NO NEW NORMAL-PATH PRODUCTION
```

历史 enum、schema、database/JSON、API transport、GenerationSpec、read model、Prompt Compiler 和 frontend display compatibility 不得因此删除。已有历史 `integrated_regulation` 数据必须继续可读取和展示。

## 2. `personalized_five_tone`

同时满足以下条件时，normal path 产生 `personalized_five_tone`：

```text
legal candidate count >= 1
AND
存在唯一 authority Top1
AND
不存在 unresolved direct contradiction
that prevents reliable primary-tone selection
```

以下情况本身不是 conflict，也不是 evidence insufficiency：

- Top1/Top2 为 51/49；
- Top1/Top2 为 53/47；
- 多个 legal organ candidates；
- 多个脏腑同时具有有效证据；
- Top1 只轻微领先。

只要 authority score 存在唯一 Top1，且没有阻止可靠 primary-tone selection 的 unresolved direct contradiction，就选择该 Top1 并产生 `personalized_five_tone`。

## 3. `basic_wellness`

正常 evidence-routing 下，仅以下情况允许产生 `basic_wellness`：

1. zero legal organ candidate；
2. unresolved direct contradiction that prevents reliable primary-tone selection；
3. exact unresolved canonical-authority tie with no approved medical tie-break authority。

Exact tie 的冻结结果是：

```text
exact unresolved canonical-authority tie
→ basic_wellness
```

以下机制不得作为医学 tie-break authority：

```text
enum order
database order
AUDIT_ORGAN_ORDER
frontend argmax
random choice
default Gong
```

审计或展示排序不得被提升为 dominant organ 或 primary tone 的决策 authority。

## 4. Direct Contradiction Semantics

只有以下条件同时成立时，证据才可能形成 direct contradiction：

```text
same canonical proposition / claim
+
opposite direction / polarity
+
same or comparable temporal scope
```

以下情况不是 direct contradiction：

```text
multi-organ evidence
close weights
ordinary value difference
historical evidence vs current evidence merely because both exist
```

检测到 contradiction 后，还必须判断：

```text
does it actually prevent reliable primary-tone selection?
```

- 如果 contradiction 不影响可靠 primary-tone selection，仍进入 `personalized_five_tone`。
- 只有 contradiction unresolved 且直接阻止可靠 primary-tone selection，才进入 `basic_wellness`。
- 不同 temporal scope 的历史与当前证据不得自动视为 contradiction。

## 5. Global Coverage

旧的：

```text
coverage >= 0.50
```

不再是 personalized eligibility 的 hard gate。

Coverage 可以保留为 audit、observability 和 evaluation metric，但：

```text
coverage < 0.50
```

不得单独把已经形成 legal candidate 的用户路由到 `basic_wellness`。

## 6. Margin and Ratio

旧的：

```text
minimum_normalized_margin = 0.08
minimum_raw_ratio = 1.20
```

不再是 normal mode routing gate。它们可以保留为 audit / observability 数据，但不得决定：

```text
personalized_five_tone vs basic_wellness
```

接近的权重本身既不是 contradiction，也不是 evidence insufficiency。

## 7. Legal Candidate Floor

当前 implementation 暂时继续沿用：

```text
minimum_evidence_count = 2
minimum_raw_support = 0.75
```

这两个数的合同状态是：

```text
TEMPORARY ENGINEERING THRESHOLDS
PENDING REAL-SAMPLE VALIDATION
NOT PERMANENTLY FROZEN PRODUCT CONSTANTS
```

V2.1 冻结的是：

```text
personalized_five_tone requires >= 1 legal candidate
```

V2.1 不把具体数值 `2` 和 `0.75` 永久冻结为产品常量。未来数值调整仍需独立样本验证、医学复核与 Owner approval。

## 8. Questionnaire Objective

完整完成并确认 canonical Q1–Q10 的正常用户，产品目标是：

```text
绝大多数进入 personalized_five_tone
```

但不得实现为：

```text
completed questionnaire == forced personalized
```

真正没有 legal candidate、存在 exact unresolved tie，或存在阻止 primary-tone selection 的关键 unresolved direct contradiction 时，仍可进入 `basic_wellness`。

## 9. Document Route

病例路线继续使用统一 authority chain：

```text
Document
→ OCR/extraction
→ Understanding
→ confirmation/edit/reconciliation
→ FactEvidence
→ eligible evidence
→ OrganEvidence
→ legal candidates
```

不得为 document 路线增加第二套重复的 dominance 或 evidence gate。

`source_recorded` 的语义是：

```text
provenance only
not eligibility downgrade
```

不得重新增加“必须具有近期证据才能 personalized”的 recent-evidence gate。不同时间范围的 evidence 必须保留各自 provenance，并按 direct-contradiction temporal semantics 判断是否可比较。

## 10. Failure Boundary

以下状态永远不是 `basic_wellness`：

```text
RAG_UNAVAILABLE
provider failure
schema failure
checksum failure
asset failure
database failure
network/auth/timeout/rate-limit
TokenHub/MiniMax failure
```

它们必须保持 technical failure、withheld 或 readiness semantics，不得伪装成合法的 evidence-routing 结果。

当前 `RAG_EMPTY` legal abstention contract 本次不修改。`RAG_EMPTY` 与技术性的 `RAG_UNAVAILABLE` 必须继续区分。

## 11. Downstream Protected Areas

V2.1 不重新设计或授权修改：

```text
Prompt Compiler V2.1
Candidate D
TokenHubMiniMaxMusicProvider
GenerationSpec architecture
MusicAsset
audio duration
Player playback lifecycle
Player Frozen Contract
UserGoal/UserMusicPreference separation
RAG Top-K / thresholds / embeddings
G3 corpus
```

历史 integrated compatibility branches 可以并且必须在需要读取历史数据的 schema、transport、Prompt Compiler 和 frontend presentation 中保留。

## 12. Implementation Boundary

本文冻结产品合同，并记录当前 implementation acceptance 状态：

```text
Implementation status: IMPLEMENTED
Selection-impact counterfactual: OWNER ACCEPTED
Backend closure regression: OWNER ACCEPTED
Android Owner Product Acceptance: PENDING
Git Closure: PENDING
Sprint 6 Closure: PENDING
```

正常 producer、contradiction selection-impact semantics 和 regression protection 已按本合同完成 bounded implementation。历史 `integrated_regulation` compatibility 继续保留；实现完成不得被解释为 Android Owner Gate、Git integration 或 Sprint 6 整体 closure 已完成。
