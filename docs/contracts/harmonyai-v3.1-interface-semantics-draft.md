# HarmonyAI V3.1 Interface Semantics Draft

> Status: **FREEZE CANDIDATE — OWNER FINAL FREEZE REVIEW REQUIRED**
> Scope: semantic ownership plus frozen V3.1 executable boundaries. Exact fields and examples are authoritative in `harmonyai-v3.1-freeze-candidate.md` and the companion executable-schema PR.

## 1. DocumentSet

- **Purpose:** Represent one user-selected group of 1～3 recent-document images.
- **Produced By:** Document upload/input service.
- **Consumed By:** OCR orchestration, relevance gate, summary service, session read model.
- **Authority:** The active server-side session revision; client thumbnails are not authoritative.
- **V3.1 Changes:** Replaces single-document flow semantics with an ordered multi-page set. Page deletion/addition must update a new revision.
- **Existing Mapping:** Individual document records and single `active_document_id` exist.
- **Freeze Candidate:** `document_set_id`, `session_id`, ordered unique 1～3 document references, set revision, session input revision and authority status are executable. Database replacement/retention remains implementation detail.

## 2. DocumentRelevanceResult

- **Purpose:** Decide whether recognized material may enter summary and downstream evidence.
- **Produced By:** Information Understanding Layer after OCR.
- **Consumed By:** Flow router, summary service, audit log.
- **Authority:** Latest completed server-side relevance run for the active DocumentSet revision.
- **V3.1 Changes:** Freezes `VALID`, `INVALID`, `IRRELEVANT`, and `INSUFFICIENT` with reasons and source-set revision binding.
- **Existing Mapping:** No dedicated V3 object.
- **Freeze Candidate:** Only `VALID` may enter summary, Evidence or Agent2. The other three outcomes retain distinct backend status/reason and share the same frontend exception route. Reason-code vocabulary and retry implementation may be versioned without changing the enum or gate.

## 3. FinalConfirmedSummary

- **Purpose:** Store the plain-language document summary after user confirmation or inline correction.
- **Produced By:** Understanding summary service plus user confirmation.
- **Consumed By:** ConfirmedUserState assembler, Agent 1, audit/read models.
- **Authority:** Latest confirmed revision; raw OCR and pre-confirmation AI summaries are supporting sources only.
- **V3.1 Changes:** Makes inline-edited summary explicitly authoritative and binds it to DocumentSet/relevance revisions.
- **Existing Mapping:** CaseSummary and understanding revision/confirmation models are reusable.
- **Freeze Candidate:** User-confirmed text is a separate authoritative revision with explicit source DocumentSet, VALID relevance, AI draft, OCR references and checksum. Re-extraction execution remains an implementation responsibility.

## 4. QuestionnaireResult

- **Purpose:** Represent a complete Q1～Q10 answer set and its derived state facts.
- **Produced By:** Questionnaire service using the approved questionnaire manifest.
- **Consumed By:** Summary/confirmation, ConfirmedUserState assembler, Agent 1.
- **Authority:** Server-validated manifest version, checksum, answers, and revision.
- **V3.1 Changes:** Required in no-document mode; optional in recent-document mode, but complete once started/submitted.
- **Existing Mapping:** Questionnaire payload/readiness logic exists but requires V3.1 flow validation.
- **Freeze Candidate:** `questionnaire_v3` / `3.0.0`, manifest `medical_v3.0`, canonical checksum `sha256:fef9830e3d269236a58213f95e2fd3449baf0ef52c0ffd74f516792f96910211`; exactly Q1～Q10 when submitted.

## 5. UserGoal

- **Purpose:** Capture an optional expectation for this music adaptation session.
- **Produced By:** User after completing Q1～Q10.
- **Consumed By:** Prescription/personalization input only.
- **Authority:** Latest explicit user selection for the current session; a skipped step is authoritative as `user_goal = null`.
- **V3.1 Changes:** Independent and optional; must be tagged as preference, never Medical Evidence, FactEvidence, or OrganEvidence.
- **Existing Mapping:** A common UserGoal model already defines the approved codes, primary/secondary fields and 200-character text bound, but requires a primary goal whenever the object is present.
- **Freeze Candidate:** `UserGoalV31 | null` with canonical `primary_goal`, `secondary_goal`, `custom_goal_text` fields and executable validation.
- **Frozen Product Semantics:** Approved codes are `sleep`, `relaxation`, `emotion_regulation`, `focus`, `energy`, `stress_relief`, and `other`; the whole step is skippable; 0～2 selections are allowed; the first is `primary_goal`, the second is `secondary_goal`; optional `custom_goal_text` is limited to 200 characters.
- **Open Question:** Only whether custom text may be submitted without a goal code; the Q1～Q10 asset contains no UserGoal definition. Persistence location and endpoint mapping remain implementation details, not product-field decisions.

## 6. ConfirmedUserState

- **Purpose:** Provide one authoritative, versioned input boundary for downstream assessment/diagnosis.
- **Produced By:** Confirmation service from one of the three legal source combinations.
- **Consumed By:** Agent 1 Assessment, Agent 2 query preparation, user-facing analysis read model.
- **Authority:** Server-side confirmed revision and checksum.
- **V3.1 Changes:** Unifies document-only, document-plus-questionnaire, and questionnaire-only paths; carries source references and optional UserGoal separately.
- **Existing Mapping:** No single object currently provides this authority boundary.
- **Freeze Candidate:** Exact `document_only`, `document_plus_questionnaire`, and `questionnaire_only` unions, normalized projection, authority, confirmation, upstream revisions and checksums are executable. Persistence location remains an implementation detail.

## 7. Agent2Result / AnalysisResult

- **Purpose:** Carry validated diagnosis/tendency output, retrieval provenance, evidence links, and abstention/degradation state.
- **Produced By:** Agent 2 after query building, RAG/LLM or approved fallback, schema validation, and medical rule validation.
- **Consumed By:** Agent 3 Prescription and Five-Tone Adaptation Analysis read model.
- **Authority:** Latest accepted diagnosis run bound to the ConfirmedUserState revision.
- **V3.1 Changes:** Must expose user-safe state tendency and rationale references without leaking provider/internal fields.
- **Existing Mapping:** Diagnosis V3 schemas exist; production RAG/Qwen reachability is not complete on the authoritative integration branch.
- **Status:** `REUSE_WITH_EXECUTION_AND_READ_MODEL_DELTA`.
- **Open Questions:** Approved syndrome whitelist, degraded/abstain user wording, final provider decision.

## 8. ToneProfile

- **Purpose:** Express the normalized five-tone prescription derived from validated analysis.
- **Produced By:** Agent 3 deterministic prescription logic.
- **Consumed By:** GenerationSpec builder and explanation read model.
- **Authority:** Accepted prescription run.
- **V3.1 Changes:** Retains `jiao`, `zhi`, `gong`, `shang`, `yu`; identifies a primary tone and optional secondary tone with supporting rationale references.
- **Existing Mapping:** Five weights and `dominant_tone` exist.
- **Freeze Candidate:** All five weights, primary tone, nullable distinct secondary tone, score semantics, mapping version and evidence-bound basis are executable. The medical threshold/tie rule remains a versioned rule-asset decision.

## 9. GenerationSpec

- **Purpose:** Define provider-neutral music parameters.
- **Produced By:** Agent 3.
- **Consumed By:** Agent 4 Music Generation Provider adapter.
- **Authority:** Accepted prescription revision; provider-specific prompts remain internal to Agent 4.
- **V3.1 Changes:** Existing BPM, duration, instruments, ambient sounds, structure, energy curve, constraints and fallback remain reusable. User-facing explanations must not be mixed into provider prompt fields.
- **Existing Mapping:** GenerationSpec schema already exists.
- **Status:** `KEEP_WITH_PRESENTATION_MAPPING`.
- **Open Questions:** Provider capability negotiation and unsupported-parameter behavior.

## 10. Explanation / Rationale

- **Purpose:** Explain the chain from confirmed state and evidence to tone and music parameters.
- **Produced By:** Validated Agent 2/3 outputs and a safe presentation assembler.
- **Consumed By:** Five-Tone Adaptation Analysis page.
- **Authority:** References accepted evidence/diagnosis/prescription runs; presentation text is not new evidence.
- **V3.1 Changes:** Requires structured sections for state tendency, tone selection, BPM, instruments, ambience and duration, each traceable to real output.
- **Existing Mapping:** Partial summary/presentation strings exist.
- **Freeze Candidate:** A PUBLIC-only read model requires confirmed state, tendency, rationale/evidence refs, primary/optional secondary explanations, BPM/instruments/ambience/duration explanations, generation readiness and disclaimer. Extra/internal fields are forbidden; localization remains presentation work.

## 11. FeedbackPreference

- **Purpose:** Convert explicitly submitted optional feedback into bounded music preferences.
- **Produced By:** Agent 5 Feedback processing.
- **Consumed By:** Future Agent 3 personalization input and profile read models when in scope.
- **Authority:** Persisted user feedback/preferences with provenance and effective revision.
- **V3.1 Changes:** Feedback entry is optional; preference influence must remain separate from state/medical evidence.
- **Existing Mapping:** Feedback and preference schemas/persistence foundations exist.
- **Status:** `REUSE_WITH_FLOW_AND_GUARDRAIL_CLARIFICATION`.
- **Open Questions:** Final feedback chips, decay/aggregation rules, when closed-loop influence is enabled.

## 12. Cross-Interface Invariants

1. All downstream results bind to explicit upstream IDs, revisions, and checksums.
2. User-confirmed content outranks unconfirmed AI extraction for current-state authority.
3. UserGoal and FeedbackPreference are preference inputs, not medical/state evidence.
4. Invalid/irrelevant documents never enter Agent 1/2 evidence.
5. Frontend read models expose only approved public fields; provider status, internal enums, prompts and retrieval internals remain private.
6. Mock/degraded output is explicitly labeled and cannot masquerade as real provider success.
