# HarmonyAI V3.1 Flow Amendment Draft

> Status: **DRAFT / PROVISIONAL / PENDING TEACHER CONFIRMATION**
> This document is not frozen and must not be treated as final implementation authority.

## 1. Relationship to Existing Contracts

This draft proposes a V3.1 flow delta over `harmonyai-v3-contract-freeze-v3.0.0-draft.3.md` and `harmonyai-v3-owner-flow-amendment-001.md`. Unchanged V3 object semantics remain reusable. Conflicting flow clauses are proposed replacements only after teacher confirmation and a final freeze review.

## 2. Normative Flow Amendments

### A. Entry

- V3.1 opens on Home/Entry; Welcome is removed from the primary path.
- Entry values remain semantically `recent_document` and `no_document` unless a later schema review versions them.
- App name and Logo remain presentation decisions, not contract fields.

### B. DocumentSet

- The recent-document path accepts 1～3 images as one ordered `DocumentSet`.
- Uploading a page does not automatically advance the route.
- A user may add or remove pages before explicitly starting recognition.
- The session must reference the active DocumentSet, not rely only on one `active_document_id`.

### C. Document Relevance Gate

- OCR success alone is insufficient for downstream use.
- A relevance result is required before summary confirmation.
- `VALID` advances to summary.
- `INVALID` and `IRRELEVANT` advance to the document exception page and must not enter Agent 1/2 evidence.
- `INSUFFICIENT` routing is **PENDING CONTRACT DECISION** and must not be silently mapped to a success or discard path.
- Re-selecting replaces the active candidate set; continuing without a usable document enters the no-document questionnaire path.

### D. Summary Confirmation

- AI produces a plain-language summary derived from recognized material.
- The user may accept, edit the summary inline, or re-upload.
- Editing targets the normalized summary, not raw OCR text.
- The final confirmed revision is `FinalConfirmedSummary` and is the only document summary authoritative for downstream assessment.
- AI suggestions are advisory and must not be persisted as user-confirmed facts unless explicitly confirmed.

### E. Narrative

- Narrative text and Voice ASR are removed from the V3.1 primary user path.
- This is a flow change, not authorization to delete legacy Narrative fields, endpoints, records, or compatibility handling.
- New V3.1 readiness rules must not require Narrative.

### F. Questionnaire

- The V3.1 questionnaire consists of Q1～Q10, rendered as five pages with two questions each.
- No-document path: questionnaire is required.
- Recent-document path: questionnaire is optional; if entered, all ten answers are required.
- Q11/Q12 are not part of the V3.1 primary questionnaire.
- This draft does not modify the authoritative medical knowledge or question mapping file.

### G. UserGoal

Authoritative product semantics:

- UserGoal is an independent, optional step after Q1～Q10 and the whole step is skippable.
- A user may select 0～2 goals. The first selection maps to `primary_goal`; the second maps to `secondary_goal`.
- `custom_goal_text` is optional and limited to 200 characters.
- Approved goal codes are `sleep`, `relaxation`, `emotion_regulation`, `focus`, `energy`, `stress_relief`, and `other`.
- Skipping the step produces `user_goal = null`.
- `UserGoal != FactEvidence` and `UserGoal != OrganEvidence`.
- UserGoal is a music-design preference and cannot override user-confirmed clinical/state facts.
- The exact V3.1 JSON Schema/API/persistence representation remains `SCHEMA_DELTA_REQUIRED` because the existing common UserGoal requires a primary goal whenever the object is present, while V3.1 makes the entire object nullable.

### H. ConfirmedUserState

Exactly three primary source combinations are accepted:

| Path | Required source | Optional source | Result |
| --- | --- | --- | --- |
| Recent document, no questionnaire | FinalConfirmedSummary | None | ConfirmedUserState |
| Recent document plus questionnaire | FinalConfirmedSummary + complete QuestionnaireResult | UserGoal | ConfirmedUserState |
| No document | complete QuestionnaireResult | UserGoal | ConfirmedUserState |

Each result must carry source references, confirmation revision, and a stable checksum. Downstream Agent 1/2 input must resolve from this authoritative object rather than stale client state.

### I. Five-Tone Adaptation Analysis

- The user-facing result page is named “五音调适解析”.
- It presents confirmed state, state tendency, evidence/rationale references, primary tone, optional secondary tone, and generated music parameters with short explanations.
- Frontend may only render returned values; it must not derive or hardcode medical, organ, element, tone, BPM, instrument, ambience, or duration results.

### J. Generation and Player

- Generation starts from the Five-Tone Adaptation Analysis page using the current authoritative GenerationSpec.
- Successful generation routes directly to Player.
- The independent Generation Complete page is removed from the V3.1 primary flow.
- Player exposes only real provider/task/playback state. “End session” returns Home; Feedback is an optional branch.

### K. Feedback and Preference

- Entering or submitting Feedback is optional.
- Submitted feedback may update music preference data only.
- Preference must not overwrite FactEvidence, OrganEvidence, ConfirmedUserState, or Diagnosis evidence.
- Final feedback chip vocabulary remains pending product confirmation.

## 3. Schema Delta Register

| Area | Existing baseline | V3.1 draft requirement | Status |
| --- | --- | --- | --- |
| Entry | Session `input_mode` | Same meaning; new routes | REUSE_WITH_FLOW_CHANGE |
| Document reference | Single `active_document_id` | Active 1～3 page DocumentSet reference | SCHEMA_DELTA_REQUIRED |
| Case summary | `source_document_ids` list and revision model exist | Final user-confirmed summary authority | REUSE_WITH_AUTHORITY_CLARIFICATION |
| Relevance | No dedicated V3 result | `DocumentRelevanceResult` with explicit outcome | SCHEMA_DELTA_REQUIRED |
| Questionnaire | V3.1 request accepts nullable questionnaire | Conditional required/optional rules and Q1～Q10 completeness | VALIDATION_DELTA_REQUIRED |
| UserGoal | Existing common object is required-primary oriented | Independent optional post-questionnaire preference | SCHEMA_DELTA_REQUIRED |
| Unified input | Separate understanding/questionnaire references | Versioned `ConfirmedUserState` | SCHEMA_DELTA_REQUIRED |
| ToneProfile | Five weights + dominant tone | Primary + optional secondary and explainable references | SCHEMA_DELTA_REQUIRED |
| GenerationSpec | BPM/duration/instruments/ambience exist | Preserve; add display explanations outside provider prompt | REUSE_WITH_PRESENTATION_DELTA |
| Read models | Existing activity/summary/result models | DocumentSet, relevance, confirmation, analysis and generation projections | READ_MODEL_DELTA_REQUIRED |
| Navigation | Welcome/Narrative/Generation Complete appear in older flow | Remove from primary route chain, retain compatibility code as needed | FLOW_DELTA_REQUIRED |

No new discriminator, table name, endpoint path, or enum value is frozen by this draft. Implementers must not silently overload V3.0 fields where semantics differ.

## 4. Compatibility and Versioning Rules

- V3.0/Sprint 4 stored data remains readable.
- Removing a page from the main path does not authorize destructive migration.
- A versioned API/schema discriminator is required before V3.1 writes are enabled; its exact value is pending final contract review.
- Current Safety backend capabilities remain intact. Safety is not reintroduced into the V3.1 user path by this draft.
- Provider failures must remain explicit; mock output cannot be serialized as real success.

## 5. Open Contract Decisions

1. Exact `DocumentSet`, `DocumentRelevanceResult`, and `ConfirmedUserState` JSON schemas.
2. `INSUFFICIENT` relevance behavior.
3. UserGoal V3.1 schema/API/persistence representation.
4. Tone secondary-selection threshold and explanation representation.
5. Endpoint and persistence versioning strategy.
6. Final feedback option vocabulary.
7. Teacher approval and subsequent final freeze decision.
