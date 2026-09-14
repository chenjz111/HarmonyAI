# V3.1 Confirmed Summary Authority Design

## Goal

Make the user-confirmed summary the authoritative current-state text for document-only, questionnaire-only, and document-plus-questionnaire flows without changing the Frozen V3.1 Contract, database schema, migrations, or medical rules.

## Data authority

Raw OCR, immutable earlier Understanding/Assessment revisions, normalized facts, FactEvidence, source references, and hashes remain provenance. The current confirmed revision contains the user-confirmed summary. When a full-text edit removes a canonical fact display name, that fact remains in the earlier revision but is not copied into the new active confirmed revision. Unedited confirmation preserves all canonical facts.

The persisted current Assessment revision's `state_summary` is the downstream authoritative text. Diagnosis constructs ConfirmedUserState and its internal retrieval/provider snapshot only from the current confirmed Assessment revision. The internal snapshot includes the confirmed state text plus only current-revision active evidence; request-body evidence never overrides persisted state.

## Document summary

Build a deterministic, source-grounded Chinese clinical summary from server-resolved OCR. Prefer explicit sections for complaint, recent symptoms/history, four examinations, recorded diagnosis or pattern, abnormal tests, and treatment/advice. Exclude hospital branding, document titles, names, phone/identity/outpatient numbers, signatures, and seals. Never infer a diagnosis or add facts absent from OCR.

Full-text edits create a confirmed Understanding revision without OCR or Provider calls. Facts whose canonical display names remain in the edited text stay active; removed facts remain only in earlier immutable revisions as provenance.

## Assessment summary

- Document only: confirmed CaseSummary text.
- Questionnaire only: deterministic composition of current `fact_evidence[].display_name`.
- Document plus questionnaire: confirmed CaseSummary text followed by deterministic questionnaire fact composition.

Assessment full-text edits create a confirmed revision. Only evidence whose canonical display name remains in the edited text is copied to that active revision. The previous revision retains the full original evidence set.

## Frontend

Both confirmation editors prefill the real backend summary. The generic status sentence is never used as the questionnaire summary. Full-text editing only; no severity or organ editor. Empty-text guards remain. Document-only continues to skip a second summary confirmation page.

## Constraints and verification

Use anonymous synthetic OCR fixtures. Do not read, copy, log, stage, or commit real uploaded medical data. No paid Provider calls. Preserve owner scoping, DocumentSet/relevance, input revision, and idempotency. Run targeted backend suites, every `frontend/tests/*.test.mjs`, H5 build, and `git diff --check`.
