# PF-0 Preference Safety Audit and Test Plan

Status: W1 implementation-boundary audit; no production behavior changed.

Baseline: `9896ea6cd10eedf1dac1e51f727b89194d086d63`

Decision authority: S7-CHANGE-003 (Owner approved)

## 1. Verified current paths

### Automatic learning write path

`POST /api/v3/feedback` is registered in `backend/app/routers/v3/feedback_router.py` and calls `submit_feedback` in `backend/app/services/v3/feedback_service.py`.

The current service:

1. persists `FeedbackV3`, favorite linkage, and commits Stage 1;
2. counts all feedback rows owned by the principal;
3. calls `_learn_preferences` in Stage 2;
4. may create/update `UserMusicPreference`, `UserMusicPreferenceVersion`, `UserPreferenceItem`, and `PreferenceEvent`, then advances `current_version_id`.

This is the old automatic-learning path that M1 must close. The old `feedback_v3.0` request has no V1.1 consent, policy-version, deletion, or evidence-epoch semantics. Its feedback rows therefore cannot be treated as authorized long-term-learning evidence.

### New-generation preference consumption paths

`get_latest_preference_snapshot` in `backend/app/services/v3/feedback_service.py` reads the profile's `current_version_id` and returns the current immutable snapshot without consent or evidence-epoch qualification.

Confirmed callers:

- `backend/app/services/v3/diagnosis_service.py`: reads the snapshot, applies `apply_preference_policy`, and persists preference/profile references into a new diagnosis result.
- `backend/app/services/v3/prescription_service.py`: `_resolve_preference` reads the same snapshot and validates any request snapshot against it before creating a prescription.

Both new-consumption paths must return/use no preference in M1. Existing persisted Diagnosis, Prescription, MusicAsset, GenerationSpec, and checksum snapshots remain readable and immutable.

### Compatibility, replay, cache, delete, and clear surface

- `GET /api/v3/me/history` calls `list_feedback_history`; it filters only by owner and has no deleted-record filter.
- Idempotent replay calls `_replay_output`; an old `preference_update_status=applied` can still be represented as applied from the current profile pointer.
- `GET /api/v3/me/preferences` reads the current profile/version directly.
- No feedback soft-delete, preference clear, tombstone, consent-policy validation, evidence epoch, or response-cache invalidation implementation exists at this baseline.
- No dedicated feedback response cache was found in the V3 feedback service. The durable replay row and `current_version_id` are nevertheless effective stale-result/version-pointer paths and must be covered as such.
- Existing `backend/app/core/agent_config.py` and RAG caches are unrelated to feedback evidence; they must not be used as a substitute for evidence-epoch invalidation.

## 2. W1 ownership boundary

Preference-owned implementation files under the frozen workstream plan:

- `backend/app/models/v3/feedback.py`
- `backend/app/services/v3/feedback_service.py`
- `backend/app/routers/v3/feedback_router.py`
- future `backend/app/schemas/v3/feedback_v31.py`
- future Preference consent/status services and routers
- future `tests/api/v3/test_s7_feedback_consent.py`
- future `tests/api/v3/test_s7_feedback_delete.py`
- future `tests/api/v3/test_s7_preference_invalidation.py`

Shared or other-lane dependencies that PF must not edit unilaterally:

- Integration: database migration, `backend/app/main.py` router registration, contract fixture/release gate.
- Backend: owner state, `feedback_evidence_epoch`, shared owner/context authorization, and transaction-safe epoch advance API.
- Diagnosis/Prescription consumers are existing cross-lane production files. Closing their consumption path requires the already-approved S7-CHANGE-003 implementation checkpoint and coordinated file ownership; PF-0 does not edit them.
- Agent3 policy, `flow_v31.py`, Prompt Compiler, Provider, GenerationSpec, and medical rules are outside this lane.

## 3. Required RED test matrix before implementation

| Case | Setup/action | Required M1 result |
|---|---|---|
| Legacy unauthorized feedback | submit old `feedback_v3.0`, including enough samples to cross the old threshold | feedback remains durable; no preference version/event/write; `applied=false` |
| New consent=false | submit V3.1 with no consent | server records authoritative false/policy result; no learning or application |
| New consent=true while M1 disabled | submit valid server-recognized policy consent | consent may be recorded, but no version/event/async learning and no new-generation application |
| Forged/obsolete policy | client supplies arbitrary or retired policy version | server rejects or normalizes only through its configured active policy; never trusts the client value |
| Existing current pointer | seed an old current preference version, then create a new diagnosis/prescription | new consumption receives `None`; old persisted historical snapshots remain byte-for-byte unchanged/readable |
| Idempotent replay | replay an old key whose row/status was applied | no new write; M1 response cannot revive an applied preference claim; request-body mismatch remains conflict |
| Delete feedback | soft-delete an owned record, then use old/new list, detail, total, replay, and preference reads | tombstone wins; record never reappears; new application cannot cite it |
| Clear preferences | clear at cutoff/epoch E1 after data at E0 | current application pointer invalid; old versions remain historical only; all new consumption is none |
| Concurrent compute vs delete | start E0 compute, acknowledge delete/clear at E1, then finish E0 | CAS/epoch check discards E0 result; pointer/cache cannot advance |
| Concurrent replay vs delete | begin old replay/list at E0 and complete after E1 | response is rejected/stale or discarded; deleted record is not returned after acknowledgement |
| Cross-owner | owner B guesses A's feedback, version, cursor, or idempotency key | 404-style owner isolation; no count, status, or epoch leak |
| Historical integrity | exercise delete/clear/disabled learning | historical Diagnosis, Prescription, MusicAsset, GenerationSpec, checksum, and generated audio are unchanged |
| Two-Mode/UserGoal | submit current-run feedback while learning disabled | current Two-Mode V2.1 analysis and UserGoal behavior remain unchanged |

The concurrency cases require deterministic barriers or transaction hooks, not timing sleeps. Fake providers and an isolated database are mandatory; external provider calls must remain zero.

## 4. Minimum safe implementation sequence for a later authorized batch

1. Integration lands the approved migration and router/fixture wiring; Backend lands the transaction-safe owner feedback epoch API.
2. Add RED tests for old feedback no-learning and both Diagnosis/Prescription no-consumption paths.
3. Make all old and V3.1 write paths fail closed for learning in M1, including replay, residual async/recompute entry points, and exception paths.
4. Make every new-generation consumption gateway return `None` in M1 while preserving reads of already-persisted historical snapshots.
5. Add server-owned consent policy validation and record the authoritative policy version only after validation; consent never enables M1 learning.
6. Add soft delete, clear cutoff, tombstone, epoch headers, owner-scoped filtering, and idempotent replay invalidation in one transaction boundary.
7. Add deterministic delete/clear/concurrent-compute tests, then run existing feedback, diagnosis, prescription, contract, migration, and historical snapshot suites under the verified offline guard.

No safe partial implementation may leave either the write side or the new-consumption side enabled. Missing migration/shared epoch APIs are `BLOCKED_BY_MIGRATION` / `BLOCKED_BY_BACKEND_OWNER_STATE`; they must not be bypassed with process-local state.

## 5. Existing tests expected to change or remain as regression protection

- `tests/api/v3/test_feedback.py::test_preference_learning_advances_versions_after_min_samples` encodes the old automatic-learning behavior. Preserve its historical intent, but version the expectation for the approved M1-disabled contract rather than deleting or weakening it.
- `test_submit_feedback_is_durable_and_idempotent`, favorite lifecycle, cross-owner isolation, comment hashing, and source-type mismatch remain required regression protection.
- Diagnosis pipeline tests that monkeypatch `get_latest_preference_snapshot` identify a real consumption seam; add M1-disabled coverage without changing medical policy assertions.
- Prescription snapshot conflict and immutable snapshot tests remain required; add M1 no-new-consumption cases while preserving historical snapshot readability.
- Migration and cross-contract suites must prove old `feedback_v3.0` compatibility and the additive V3.1/epoch contract.

## 6. PF-0 conclusion

The approved safety decision is not implemented at the shared baseline. Both the automatic write path and two new-generation consumption paths remain active. The later implementation must close all three together, and deletion/clear safety depends on the Integration migration and Backend owner-state transaction API. PF-0 makes no production or test-assertion change.
