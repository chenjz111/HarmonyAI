# HarmonyAI V3.1 Contract Freeze Candidate

> Status: **FREEZE CANDIDATE — OWNER FINAL FREEZE REVIEW REQUIRED**
>
> Baseline: `origin/integration/sprint4-real-input@d16876d6fcd4cd664370b963bfa545e7e6f1fc00`
>
> Executable schema: `backend/app/schemas/v3/flow_v31.py` in the companion executable-contract PR.
> This document is not `FROZEN`; only the Owner may make the final freeze decision.

## 1. Frozen questionnaire identity

| Field | Authoritative value |
| --- | --- |
| Schema ID | `questionnaire_v3` |
| Schema version | `3.0.0` |
| Manifest version | `medical_v3.0` |
| Canonical path | `knowledge/v3/questionnaire-v3.0.json` |
| Canonical checksum | `sha256:fef9830e3d269236a58213f95e2fd3449baf0ef52c0ffd74f516792f96910211` |
| Manifest path | `knowledge/v3/knowledge-manifest-v3.0.json` |
| Manifest schema/version | `knowledge_manifest_v3` / `3.0.0` |
| Manifest review | `approved`, `medical_v3.0-r1` |

The checksum uses the repository convention: remove the asset's top-level
`content_checksum`, serialize canonical JSON with sorted keys and compact
separators, UTF-8 encode, then calculate SHA-256. V3.1 uses exactly Q1–Q10 in
this asset. It does not add, remove, or change any question.

## 2. DocumentSet

```json
{
  "schema_version": "document_set_v3.1",
  "document_set_id": "dset_xxx",
  "session_id": "sess_xxx",
  "revision": 2,
  "session_input_revision": 4,
  "authority_status": "current",
  "documents": [
    {"document_id": "doc_xxx", "position": 1, "content_checksum": "sha256:..."}
  ]
}
```

- `documents` is ordered, unique, `minItems=1`, `maxItems=3`; positions are
  consecutive from 1.
- `authority_status = current | superseded | discarded`.
- The current server-side set/revision is authoritative. Client thumbnails,
  filenames, and local arrays are presentation only.

## 3. DocumentRelevanceResult

```json
{
  "schema_version": "document_relevance_result_v3.1",
  "relevance_result_id": "rel_xxx",
  "run_id": "run_xxx",
  "revision": 1,
  "document_set_ref": {"document_set_id": "dset_xxx", "revision": 2},
  "outcome": "VALID",
  "reason_code": "VALID_RECENT_CLINICAL_DOCUMENT",
  "reason": "资料可用于本次状态理解。",
  "may_enter_summary": true,
  "may_form_evidence": true,
  "may_enter_agent2": true,
  "completed_at": "2026-09-05T01:00:00Z"
}
```

The enum is exactly `VALID | INVALID | IRRELEVANT | INSUFFICIENT`. Only
`VALID` has all three downstream flags set to `true`. `INVALID`,
`IRRELEVANT`, and `INSUFFICIENT` retain their real status/reason but share the
same frontend exception page and may only lead to reselecting documents or the
no-document questionnaire flow. They cannot enter summary, Evidence, or Agent2.

## 4. FinalConfirmedSummary

```json
{
  "schema_version": "final_confirmed_summary_v3.1",
  "summary_id": "sum_xxx",
  "session_id": "sess_xxx",
  "source_document_set_ref": {"document_set_id": "dset_xxx", "revision": 2},
  "source_relevance_result_ref": {"relevance_result_id": "rel_xxx", "revision": 1, "outcome": "VALID"},
  "source_ai_summary_ref": {"summary_id": "ai_sum_xxx", "revision": 1},
  "ocr_source_refs": [{"document_id": "doc_xxx", "ocr_result_id": "ocr_xxx", "revision": 1}],
  "confirmed_text": "用户确认或原地修改后的通俗摘要。",
  "revision": 2,
  "content_checksum": "sha256:...",
  "authority_status": "current",
  "confirmation_authority": "user",
  "confirmed_at": "2026-09-05T01:02:00Z"
}
```

`confirmed_text` is the authoritative user-confirmed result. The AI draft and
OCR results remain immutable supporting references and are never conflated
with the confirmed revision.

## 5. QuestionnaireResult

```json
{
  "schema_version": "questionnaire_result_v3.1",
  "questionnaire_result_id": "qres_xxx",
  "session_id": "sess_xxx",
  "revision": 1,
  "authority_status": "current",
  "input_mode": "without_document",
  "entry_requirement": "required",
  "schema_id": "questionnaire_v3",
  "questionnaire_schema_version": "3.0.0",
  "manifest_version": "medical_v3.0",
  "content_checksum": "sha256:fef9830e3d269236a58213f95e2fd3449baf0ef52c0ffd74f516792f96910211",
  "answers": ["exactly q01 through q10 in order"],
  "started_at": "2026-09-05T01:00:00Z",
  "completed_at": "2026-09-05T01:03:00Z"
}
```

- `without_document` requires questionnaire entry; `with_document` makes entry
  optional.
- Once submitted, the result always contains one valid answer for every Q1–Q10
  in canonical order. Partial submissions are not a `QuestionnaireResult`.

## 6. UserGoal

Boundary type: `UserGoalV31 | null`.

```json
{
  "primary_goal": "sleep",
  "secondary_goal": "relaxation",
  "custom_goal_text": null
}
```

- Canonical fields are `primary_goal`, `secondary_goal`, `custom_goal_text`.
- Approved codes are `sleep`, `relaxation`, `emotion_regulation`, `focus`,
  `energy`, `stress_relief`, and `other`.
- The whole step is optional; skip serializes as `null`.
- A present object carries one primary and at most one distinct secondary code.
- `custom_goal_text` is trimmed, non-empty when present, and at most 200 chars.
- `other` currently follows the existing conservative V3 rule: it requires
  `custom_goal_text`, and text is not accepted for a non-`other` code.
- UserGoal is a preference input only: it is not Medical Evidence,
  FactEvidence, OrganEvidence, or a source-validity signal.

The approved Q1–Q10 asset explicitly contains no UserGoal and therefore does
not define whether custom-text-only (no goal code) is allowed. This is the only
remaining narrow Owner review item; it does not reopen the field names, code
set, optionality, maximum selection count, or evidence boundary.

## 7. ConfirmedUserState

```json
{
  "schema_version": "confirmed_user_state_v3.1",
  "confirmed_user_state_id": "cus_xxx",
  "session_id": "sess_xxx",
  "source_mode": "document_plus_questionnaire",
  "final_confirmed_summary_ref": {"summary_id": "sum_xxx", "revision": 2, "content_checksum": "sha256:...", "confirmation_status": "confirmed"},
  "questionnaire_result_ref": {"questionnaire_result_id": "qres_xxx", "revision": 1, "content_checksum": "sha256:fef9830e3d269236a58213f95e2fd3449baf0ef52c0ffd74f516792f96910211", "completion_status": "complete"},
  "user_goal_ref": null,
  "confirmed_state_text": "用户确认后的状态摘要。",
  "normalized_projection": [{"fact_id": "fact_xxx", "claim_code": "unrefreshing_sleep", "display_text": "睡后恢复感不足", "source_refs": ["qres_xxx:q01"]}],
  "revision": 2,
  "content_checksum": "sha256:...",
  "authority_status": "current",
  "confirmation_status": "confirmed",
  "confirmed_by": "user",
  "session_input_revision": 5,
  "created_at": "2026-09-05T01:04:00Z"
}
```

Exactly three source unions are legal:

| `source_mode` | FinalConfirmedSummary | QuestionnaireResult |
| --- | --- | --- |
| `document_only` | required | absent |
| `document_plus_questionnaire` | required | required |
| `questionnaire_only` | absent | required |

`user_goal_ref` is independent and nullable, so it never changes source
validity. Agent2 may consume only `authority_status=current` and
`confirmation_status=confirmed`, bound to the exact upstream revisions and
checksums. Stale localStorage, unconfirmed AI summaries, and superseded
revisions are not valid Agent2 inputs.

## 8. ToneProfile V3.1

```json
{
  "schema_version": "tone_profile_v3.1",
  "weights": {"jiao": 0.15, "zhi": 0.10, "gong": 0.45, "shang": 0.10, "yu": 0.20},
  "primary_tone": "gong",
  "secondary_tone": "yu",
  "score_semantics": "relative_tone_distribution",
  "mapping_version": "medical_v3.0",
  "basis": {"diagnosis_id": "diag_xxx", "diagnosis_revision": 1, "supporting_evidence_refs": ["fev_xxx"]}
}
```

All five weights are required and sum to `1 ± 0.001`. The primary tone has a
maximum weight. The optional secondary tone is either `null` or distinct from
the primary tone. The medical selection threshold is a versioned rule asset,
not part of this transport freeze.

## 9. Five-Tone Analysis public read model

`FiveToneAnalysisReadModel` exposes only:

- `confirmed_user_state_ref` and public `confirmed_state`;
- public `state_tendency` and rationale summaries with evidence references;
- primary tone and optional secondary tone, each with display name and
  explanation;
- BPM, instruments, ambience, and duration with an explanation for each;
- generation readiness `ready | not_ready`, a user-safe message, and a
  disclaimer.

Every explanation is required and non-empty. Extra fields are forbidden, so
provider prompts, private reasoning, raw RAG chunks, model/provider metadata,
and debug enums cannot leak through this read model. The frontend consumes the
read model and must not derive medical or music parameters itself.

## 10. Freeze boundary

This candidate freezes request/response shape, enums, validation, authority,
revision/checksum binding, and cross-layer semantics. It does not freeze final
database table or ORM names, a Music Provider, provider prompts, or the
secondary-tone medical threshold.

## 11. PR #102–#105 consistency matrix

| PR | Contract area | Current implementation | Freeze Candidate | Status |
| --- | --- | --- | --- | --- |
| #102 | Relevance / UserGoal medical boundary | Candidate medical rules define four outcomes and keep UserGoal outside evidence | Same four outcomes; UserGoal preference-only | `ALIGNED` |
| #103 | UserGoal | Sends `primary`, `secondary`, `custom_text` | Requires `primary_goal`, `secondary_goal`, `custom_goal_text` | `BLOCKING_DELTA` |
| #103 | Multi-document / questionnaire identity | Supports 1–3 UI items and V3 questionnaire flow | Must bind authoritative DocumentSet revision and exact checksum | `MINOR_DELTA` |
| #103 | Confirmed state / Five-Tone read model | No canonical ConfirmedUserState or complete public analysis read model consumption | Consume the frozen server read models only | `NOT_IMPLEMENTED` |
| #104 | DocumentSet / relevance persistence | Normalized set/revision and four relevance outcomes exist | Add exact checksums/authority flags and aggregate downstream gate semantics | `MINOR_DELTA` |
| #104 | UserGoal backend | Nullable wrapper around existing canonical UserGoal | Same canonical field names and nullable boundary | `ALIGNED` |
| #104 | Agent3 / ToneProfile | Existing V3 `dominant_tone`; conservative GenerationSpec path | V3.1 `primary_tone` plus nullable `secondary_tone` | `BLOCKING_DELTA` |
| #104 | Persistence authority | Can store sets, relevance, questionnaire and goal | No authoritative ConfirmedUserState boundary yet | `NOT_IMPLEMENTED` |
| #105 | Multi-document Understanding | Resolves active set/revision and excludes non-VALID documents | Same revision-bound VALID-only rule | `ALIGNED` |
| #105 | FinalConfirmedSummary | Existing CaseSummary/Understanding revision remains the authority mechanism | Separate AI/OCR refs from user-confirmed final summary | `BLOCKING_DELTA` |
| #105 | ConfirmedUserState binding | Understanding/Assessment inputs remain separate | One current confirmed source-union object required before Agent2 | `NOT_IMPLEMENTED` |

These deltas are implementation work for their owning PRs. They do not alter
this candidate and are not repaired in the contract PR.

## 12. Final review candidate result

All core path behavior, questionnaire identity, INSUFFICIENT behavior,
DocumentSet, relevance, confirmed summary, ConfirmedUserState, ToneProfile,
and Five-Tone public read-model semantics are executable and testable. The
only remaining product clarification is custom-text-only UserGoal behavior;
the candidate retains the current conservative V3 rule until the Owner says
otherwise.

**Candidate review result: READY_TO_FREEZE**

This result means the contract is ready for Owner decision. It does not itself
change the status to `FROZEN` and does not authorize merging implementation PRs.
