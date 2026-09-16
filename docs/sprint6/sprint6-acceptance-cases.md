# HarmonyAI Sprint 6 — Fixed Acceptance Cases A–H

> Status: **FROZEN ACCEPTANCE CASE SET**
> Phase: Sprint 6 Phase 0
> These cases are the regression set for Phase 1–8. They define **semantic goals**, not numeric
> percentages. Numeric thresholds are deliberately **not** fixed here (see
> `rule-freeze-questions.md` Q4).
>
> **Phase 0 does not require current production code to satisfy these expectations.** The
> expectations describe the intended Sprint 6 end state. Machine-readable form lives in
> `tests/fixtures/sprint6_acceptance_cases.json`; the fixture contract is verified by
> `tests/contract/test_sprint6_acceptance_cases_contract.py`.

---

## 0. Shared vocabulary

**Product modes (user-visible):**

| Mode | User-facing label | `primary_tone` |
|---|---|---|
| `personalized_five_tone` | 个性化五音调适 | a single tone required |
| `integrated_regulation` | 综合调适 | **`null` allowed** — weights retained |
| `basic_wellness` | 基础舒缓 | **`null` allowed** |

**Tone codes (backend-authoritative):** `jiao` 角 · `zhi` 徵 · `gong` 宫 · `shang` 商 · `yu` 羽.

**Non-negotiable invariants across all cases:**

1. `basic_wellness` and `integrated_regulation` must **never** fabricate a `gong` tone.
2. A near-tie/near-uniform profile must **not** be resolved into an arbitrary single primary tone
   by argmax/tie order.
3. An abstained or evidence-insufficient result must be **distinguishable in the API** from a
   genuine single-organ conclusion.
4. A genuine single-organ dominance must remain `personalized_five_tone` (the fix must not push
   real conclusions into `basic_wellness`).
5. All case inputs are **synthetic and code-owned** — never real patient data.

---

## CASE A — Clear liver / wood tendency

| Field | Value |
|---|---|
| Purpose | Verify that a clearly dominant organ is **not** downgraded to integrated/basic. |
| Input type | questionnaire (synthetic) |
| Synthetic shape | q01 (anger tendency) at the top of the scale; q02–q05 at zero; q06 (liver body block) with three liver claims; q07–q10 `["none"]` |
| Expected future mode | `personalized_five_tone` |
| Expected future primary tone | `jiao` |
| Expected future weights | present |
| Sprint 5 baseline | *not measured in Phase 0* — recorded as a Phase 1 measurement task (no speculative baseline) |
| Notes | This is the **most important guard** against over-correction: the fix must keep a real conclusion personalized. |

## CASE B — Clear spleen / earth tendency

| Field | Value |
|---|---|
| Purpose | Verify that **genuine `gong`** is still reachable and is labelled as a real conclusion. |
| Input type | questionnaire (synthetic) |
| Synthetic shape | q03 (overthinking tendency) at the top of the scale; q01/q02/q04/q05 at zero; q08 (spleen body block) with three spleen claims; q06/q07/q09/q10 `["none"]` |
| Expected future mode | `personalized_five_tone` |
| Expected future primary tone | `gong` |
| Expected future weights | present |
| Sprint 5 baseline | *not measured in Phase 0* (Sprint 5 would very likely also produce `gong` here — but via the same argmax path as every other case, so it cannot be treated as evidence of correctness) |
| Notes | **This is the legitimate genuine-`gong` case.** Sprint 6 must be able to distinguish it from the fabricated fallback `gong`. Removing fabricated `gong` must not remove this one. |

## CASE C — Clear heart / fire tendency

| Field | Value |
|---|---|
| Purpose | Verify a third organ direction produces its own tone, not a `gong` default. |
| Input type | questionnaire (synthetic) |
| Synthetic shape | q02 (agitation tendency) at the top of the scale; q01/q03/q04/q05 at zero; q07 (heart body block) with three heart claims; q06/q08/q09/q10 `["none"]` |
| Expected future mode | `personalized_five_tone` |
| Expected future primary tone | `zhi` |
| Expected future weights | present |
| Sprint 5 baseline | *not measured in Phase 0* |
| Notes | Together with A and B this pins three different organs through the same code path. |

## CASE D — Five organs / five tones close together

| Field | Value |
|---|---|
| Purpose | Verify the system **stops forcing a single primary tone** when the profile is close to uniform. |
| Input type | organ-profile snapshot (synthetic) / questionnaire that yields a near-uniform profile |
| Synthetic shape | every emotion question at a mid scale value; every body block with two claims — i.e. all five organs qualify with near-equal support |
| Expected future mode | `integrated_regulation` |
| Expected future primary tone | **`null`** |
| Expected future weights | **present** (a balanced five-tone distribution is retained and remains user-meaningful) |
| Sprint 5 baseline | **documented**: with an exactly uniform organ profile the approved mapping makes `gong` and `shang` tie at raw 1.15 and the `_TONE_CODES` tuple order resolves the tie to **`gong`** (`backend/ai_engine/v3/agent3.py`). So Sprint 5 produces an arbitrary single primary tone here. |
| Notes | **This is the core Sprint 6 defect case.** The mode label is what changes, not the evidence: the weights already exist and are meaningful. |

## CASE E — Insufficient information

| Field | Value |
|---|---|
| Purpose | Verify that insufficient evidence yields `basic_wellness` with **no** fabricated tone. |
| Input type | insufficient input (synthetic) |
| Synthetic shape | all emotion questions at zero; every body block `["none"]` — no organ reaches the approved candidate threshold |
| Expected future mode | `basic_wellness` |
| Expected future primary tone | **`null`** |
| Expected future weights | absent / neutral |
| Sprint 5 baseline | **documented**: the insufficient element profile produces an abstained diagnosis, and the prescription fallback fabricates `primary_tone=gong` with weights `{gong: 0.6, others: 0.1}` (`backend/app/services/v3/prescription_service.py`). Canonical DB: 15/15 `wellness` prescriptions are `gong`. |
| Notes | Must never claim a single five-tone primary tone. User-facing wording requires Medical review (see `rule-freeze-questions.md` Q2). |

## CASE F — Questionnaire with a clearly one-directional difference

| Field | Value |
|---|---|
| Purpose | Verify the questionnaire can form a **clear difference**, instead of every organ landing near 0.2. |
| Input type | questionnaire (synthetic) |
| Synthetic shape | a strong single-organ direction plus a distinct second, weaker organ block — i.e. two organs qualify with clearly different support (not a near-tie) |
| Expected future mode | `personalized_five_tone` following the fixture's explicit direction |
| Expected future primary tone | `jiao` (direction of the stronger organ in the fixture) |
| Expected future weights | present, with a visible spread between the top two organs |
| Sprint 5 baseline | *not measured in Phase 0* |
| Notes | This case exists to prove the questionnaire is **discriminative enough** to support personalization at all. If Phase 1 thresholds classify the fixture's margin as ambiguous, this case must be re-classified to `integrated_regulation` **with Owner + Medical sign-off**, and the fixture updated — not silently reinterpreted. |

## CASE G — Historical `RAG_EMPTY`

| Field | Value |
|---|---|
| Purpose | Verify **`RAG_EMPTY` ≠ `gong`**. |
| Input type | diagnosis snapshot with an empty retrieval result (synthetic) |
| Synthetic shape | a fixed organ profile plus a retrieval result with `status = "empty"` and **zero hits** |
| Expected future mode | `basic_wellness` — or whatever Phase 1/Phase 3 finally contracts, but it must be an explicit, documented decision |
| Expected future primary tone | **`null`** |
| Expected future weights | per the Phase 1/3 final contract |
| Sprint 5 baseline | **documented**: `rag_result.status == "empty"` marks the diagnosis abstained with reason `RAG_EMPTY` without calling the provider, and the prescription fallback then fabricates `gong`. Canonical DB: 10/20 retrievals `empty`, and every abstained prescription is `gong`. |
| Notes | Retrieval abstention must never be presented as a medical tone conclusion. |

## CASE H — Same-input repeatability

| Field | Value |
|---|---|
| Purpose | Verify the pipeline is **deterministic** for a fixed input. |
| Input type | repeatability harness over a referenced fixed case |
| Synthetic shape | the fixture references another case (default CASE D) and a repeat count; no new clinical content |
| Expected future mode | same as the referenced case (`integrated_regulation` for the default reference) |
| Expected future primary tone | **`null`** (inherited from the default reference) |
| Expected future weights | present |
| Sprint 5 baseline | not applicable (no repeatability harness exists yet) |
| Checks to perform in later phases | mode consistency · primary-tone consistency · tone-weight stability · RAG result stability · prompt stability |
| Notes | **Phase 0 must not call any real provider for this case.** Repeatability is verified with fake/injected providers or pure functions only. |

---

## Acceptance usage rules

1. A case may be referenced by more than one phase; the expectation must not be relaxed without an
   explicit Owner + Medical decision recorded in `rule-freeze-questions.md`.
2. When a case starts passing, record the evidence (test name + DB/trace reference) in the phase
   report. Do not edit the expectation to match the implementation.
3. `basic_wellness` and `integrated_regulation` may never carry a tone; any fixture or code change
   that would give them one is a contract violation and requires a rule-freeze decision first.
4. All fixtures must remain synthetic. Real OCR text from `uploads/`, `final-e2e.db`, or runtime
   logs must never be copied into a fixture.
