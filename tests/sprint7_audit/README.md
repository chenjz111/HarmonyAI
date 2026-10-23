# Sprint 7 R1/R2 evidence counterfactual audit

**Issue**: #154 `[S7-M1][R1/R2-B] 医学证据反事实审计与裁定材料`
**Owner**: 肖宇翔（nob）· 医学知识签核
**Baseline**: `team/s7-m1-w2-baseline` @ `ff879f70a19328dbe492bf3aa9418e681a5db06b`
**Handoff**: PR #156 `handoff/s7-r1r2-fixtures` @ `b1e7a507` (original fixtures,
two known failures fixed below)
**Status**: audit material only, no production change. Runs offline against the
published baseline.

## What this package is

An offline, reproducible read of the R1/R2 evidence chain, built on the
**published** source and the **approved** JSON assets. Every case calls the
real production functions, so a recorded observation is an executed result,
never an inference from a field name.

It answers "what does the code actually do", and separates that from "is that
medically correct" -- the second question is a sign-off item, not a test.

## How to run

```bash
python -m pytest tests/sprint7_audit -q
```

**123 passed / 1 warning** (the warning is the known Starlette/httpx
deprecation). No provider, no network, no production database.

## Owner handoff + fixture fix

PR #156 shipped the two original characterization files byte-for-byte:

* `test_subject_admission.py`
* `test_negation_contribution.py`

They reproduced as **38 passed / 2 failed**. Both failures were the same bug in
`test_questionnaire_document_opposition_requires_comparable_time[False|True]`:
the `fact()` fixture derived `fact_id` from the claim alone, so the two sides
of the same claim shared one id and the `Conflict.fact_ids` model rejected the
single-item list. Fix (per #154, no production change): give each side a
distinct, stable id (`fact_anger_q` / `fact_anger_d`) via a new optional
`fact_id` argument on `fact()`. The original time-window/conflict assertions
were untouched. After the fix: **40 passed**.

## Stage coverage (baseline `ff879f70`)

| Stage | What it is | File | Status |
|---|---|---|---|
| S0 | extraction facts | `understanding.py` | covered |
| S1 | admission | `services/v3/evidence_admission.py` | covered |
| S2 | `FactEvidence` construction | `assessment_service.py` | covered |
| S3 | confirmed filter | `organ_dominance_service.py` | covered |
| S4 | effective population (dedupe) | `organ_dominance_service.py` | covered |
| S5 | coverage | `organ_dominance_service.py` | covered |
| S6 | organ links | `assessment_service.py` | covered |
| S7 | aggregation / weights | `organ_dominance_service.py` | covered |
| S8 | legal candidate gate | `organ_dominance_service.py` | covered |
| S9 | dominance routing | `organ_dominance_service.py` | covered |
| S10 | regulation mode | `organ_dominance_service.py` | covered |
| S11 | persisted Diagnosis | `diagnosis_service.py` | covered (via `test_subject_admission` DB harness) |
| S12 | public explanation | `ai_engine/v3/public_explanation.py` | covered |

## Headline findings (all executed)

1. **V2.1 routing rewrite.** `integrated_regulation` is no longer emitted;
   coverage/margin/ratio are audit-only; a near-tie now hard-selects top1.
   -> `test_dominance_routing_v21.py`
2. **Version migration, not runtime drift.** The code loads
   `dominance-rule-v2.json` (v2.1), which itself declares `routing_authority:
   audit_only`. The open question is whether v2.1's `medical_review.approved`
   has a real sign-off behind it -- Owner confirmed it does not yet.
   -> `test_dominance_routing_v21.py`
3. **A negated fact still scores positive internally** (every approved link is
   `supporting`) **but is dropped from the public reasons**. An all-negated
   liver population yields `personalized_five_tone` internally and "缺少可公开
   引用的具体状态依据" publicly. -> `test_negation_contribution.py`,
   `test_public_explanation.py`
4. **`subject` is fragmented**: S1 only blocks "亲属 + self"; the middle chain
   drops it; route B (exclude other/unknown at input) is feasible because
   `NormalizedFact.subject` is already persisted.
   -> `test_subject_admission.py`, `test_subject_chain.py`, `test_subject_route_b.py`
5. **Direct contradiction** is the new safety net and only blocks when it
   unseats top1. -> `test_direct_contradiction_routing.py`
6. **Neutral exclusion fixes D-4/D-8**: with a prototype filter, an all-negated
   population routes to `basic_wellness` instead of manufacturing a tone.
   -> `test_negation_neutral_exclusion.py`

Findings carry decisions D-1..D-8 in
`docs/sprint7/s7-r1r2-evidence-audit-baseline-20261015.md` and the formal
ruling in `docs/sprint7/s7-r1r2-medical-ruling-D6-D8-20261015.md`.

## Explicit non-goals

* No production algorithm, rule asset, GenerationSpec, provider or schema is
  modified.
* Passing here is not medical approval.
