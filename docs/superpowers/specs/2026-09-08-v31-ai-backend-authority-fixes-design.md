# HarmonyAI V3.1 AI/Backend Authority Fixes

Status: OWNER-APPROVED DESIGN

Date: 2026-09-08

Scope: `feat/s5-v3.1-ai-backend-integration`

## 1. Objective

Close five integration defects without changing the teacher-approved user flow,
the frozen questionnaire, provider direction, or frontend page order:

1. an Understanding created from replaced documents can still be confirmed;
2. Document Relevance has persistence and a read gate but no reachable writer;
3. Agent3 can consume a historical Assessment that is no longer current;
4. personalization can be reported as applied without changing any parameter;
5. the canonical Five-Tone Read Model is generated and then discarded.

The governing rule is single authority: every downstream result must be bound to
the current session input revision and must be generated once, persisted once,
and reused rather than reconstructed.

## 2. Non-goals

- No frontend, route order, teacher-flow, questionnaire, or Safety changes.
- No MiniMax implementation and no unapproved provider fallback.
- No production Mock fallback when a real provider is unavailable.
- No rewrite of migrations `0001` through `0008`.
- No new medical mappings or invented evidence, energy curves, explanations, or
  transport sections.

## 3. Authority chain

The only valid chain is:

```text
Session(input_revision)
  -> active DocumentSet(set_revision), when documents are used
  -> latest DocumentRelevanceResult for that exact set revision
  -> confirmed Understanding / Questionnaire submission
  -> current confirmed Assessment revision
  -> Diagnosis bound to that Assessment and input revision
  -> canonical Agent3 execution
  -> persisted FiveToneAnalysisReadModel
  -> Prescription copying the persisted canonical result
```

Every command revalidates its immediate parent and the current Session. A row
that was once valid does not remain valid after `input_revision` advances.

## 4. Document replacement and stale confirmation

`replace_document` is an input transition, not an in-place file swap. Its
transaction must:

- increment `sessions.input_revision` using the existing CAS rule;
- retire or detach the old active DocumentSet;
- clear `active_document_set_id` and the active-document pointer until the new
  set is assembled;
- invalidate session bindings to the old Understanding and downstream
  Assessment;
- leave historical rows immutable for audit.

Creating the replacement DocumentSet establishes a new set revision. An
Understanding confirmation is accepted only when all of these are true:

- the Understanding belongs to the session owner and session row;
- its `input_revision` equals the current Session revision;
- its ordered source document IDs exactly equal the ordered items of the current
  active DocumentSet;
- the set revision is current;
- the latest relevance row for the same set revision is `VALID` and all three
  downstream flags are true.

The confirmation transaction repeats these checks. Validation performed only
at Understanding creation is insufficient because the session can change
before confirmation.

## 5. Reachable Document Relevance execution

Add an internal `DocumentRelevanceEvaluator` interface and one orchestration
function, `ensure_document_set_relevance`, used by V3.1 Understanding creation.
It operates on the current active DocumentSet after every referenced document
has usable OCR text.

Behavior:

1. If a latest relevance row already exists for the exact set revision, return
   it idempotently.
2. If OCR is incomplete or empty, persist no fabricated result and return a
   readiness error.
3. In explicit Mock/Demo tests, a test evaluator may return fixture outcomes.
4. In Real mode, call the configured Understanding/Qwen provider through the
   existing provider abstraction and validate its structured result.
5. Provider missing, timeout, invalid schema, or incomplete configuration is a
   readiness/provider failure. It must never become `VALID` automatically.
6. Persist one append-only result bound to `document_set_id`, `set_revision`,
   `session_id`, `input_revision`, provider run/audit reference, and outcome.
7. Only `VALID` may set `may_enter_summary`, `may_enter_assessment`, and
   `may_enter_diagnosis` true.

The existing Understanding endpoint remains the reachable product entry. No
technical relevance page or frontend-only trigger is introduced.

## 6. Current Assessment enforcement for Agent3

Before Agent3 execution, the service must establish that:

- Diagnosis and Assessment belong to the same owner and Session;
- Diagnosis references the Assessment's current revision;
- Assessment status is `confirmed` and does not need confirmation;
- Assessment `input_revision` equals the current Session revision;
- its Understanding/Questionnaire references are the current confirmed inputs;
- document-based source modes still pass the current relevance gate.

These checks apply to success, degraded, and abstained paths. A historical
confirmed revision cannot be selected merely because it still exists. Stale
input returns a conflict/readiness response and creates no Prescription.

## 7. Honest preference application

The server-authoritative latest preference snapshot is an explicit Agent3
input. Application occurs only after medical/rule output exists and only within
approved constraints.

For every candidate preference:

- compare the canonical value before and after policy application;
- persist an `applied=true` event only when the value actually changes;
- record the real field, before value, after value, profile ID, profile version,
  and reason code;
- record `applied=false` plus a reason when the value is already equal,
  unsupported, or rejected by a medical constraint;
- never emit a fixed or guessed before value;
- never claim that an instrument/BPM/duration preference affected output when
  it did not.

The preference layer may select only values already allowed by the frozen
GenerationSpec and approved music-generation rules. It cannot override medical
readiness or create a missing Diagnosis.

## 8. Canonical Five-Tone Read Model persistence

Agent3 executes once for a specific Diagnosis plus preference snapshot. Add an
append-only migration after `0008` that extends `diagnosis_runs` with:

- `five_tone_read_model_schema_version`;
- `five_tone_read_model_json`;
- `five_tone_read_model_checksum`;
- `five_tone_generated_at`;
- the applied preference profile/version reference where applicable.

The JSON is validated as the frozen `FiveToneAnalysisReadModel` before commit.
Its checksum is calculated from canonical serialized JSON. Diagnosis creation
persists the validated model in the same transaction as the successful Agent3
result, or persists neither.

Prescription creation reads this snapshot and copies its canonical ToneProfile,
GenerationSpec, presentation, explanations, readiness, secondary-tone decision,
confirmed-state reference, and supporting evidence/RAG references. It must not
call Agent3 again.

The following reconstruction behavior is removed:

- BPM-derived energy labels not present in the approved result;
- duration-derived intro/outro sections;
- fabricated `assessment:<id>:r<revision>` evidence references;
- a second mapping pass using a different UserGoal source.

Idempotent retries for the same Diagnosis and preference version return the same
persisted model and Prescription result.

## 9. Failure and transaction semantics

| Condition | Result |
| --- | --- |
| current relevance missing | readiness failure; no Understanding output |
| relevance provider unavailable in Real mode | provider/readiness failure; no Mock fallback |
| relevance outcome not `VALID` | persist outcome; block downstream entry |
| session input changes before confirmation | 409 conflict; no new confirmed revision |
| Assessment is stale or not confirmed | 409/readiness failure; no Agent3 execution |
| Agent3/schema/rule validation fails | explicit failed/abstained result according to frozen policy; no invented model |
| preference cannot be applied | canonical output retained; `applied=false` with reason |
| Five-Tone persistence fails | rollback Agent3 result and Prescription creation |

## 10. Tests and acceptance gates

Tests are written and observed failing before production changes.

Required targeted coverage:

- replacing documents invalidates the old set and old Understanding binding;
- confirming an old Understanding after replacement returns conflict;
- a new set without a relevance result invokes the real evaluator path;
- provider failure in Real mode never creates a `VALID` row;
- explicit Mock evaluator remains isolated from Real mode;
- only the latest exact set revision can enter Understanding/Assessment/Diagnosis;
- stale, superseded, or needs-confirmation Assessment cannot enter Agent3;
- unchanged preferences never produce `applied=true`;
- accepted preferences store real before/after values;
- rejected preferences retain canonical medical output with an explicit reason;
- Five-Tone Read Model survives commit/reload byte-equivalently after schema
  validation;
- Prescription consumes the persisted model and does not execute Agent3 twice;
- migration `0009` up/down and idempotency for SQLite and MySQL;
- V3.1 contract tests, relevant API/service tests, full backend tests, and
  `git diff --check`.

Any pre-existing full-suite failure must be reproduced on the target baseline
before it can be classified as unrelated.

## 11. Delivery boundaries

Implementation stays on `feat/s5-v3.1-ai-backend-integration`. Commits are split
by authority boundary:

1. document replacement and relevance execution;
2. current Assessment and canonical Agent3 persistence;
3. honest preference application and Prescription consumption;
4. migration/contract integration cleanup, if not naturally included above.

No push, PR, or merge occurs until all required verification evidence has been
reviewed.
