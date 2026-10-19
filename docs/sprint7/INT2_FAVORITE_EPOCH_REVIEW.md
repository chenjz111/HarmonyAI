# INT-2 Favorite epoch repair and new-member audit

Status: independent Favorite subset candidate for Draft review. Generation epoch
remains OPEN and is not a prerequisite for publishing this separated subset.
Base: `854ffae1f874d552f1d7d5dbdae8412eb2ee5bd3`.
No deployment, production-route, authorization or Preference consent approval.

## Audited paths

| Path | Baseline epoch | Candidate subset | Transaction |
|---|---|---|---|
| set_favorite, actual insert | missing | +1 | Favorite insert + existing advance_library_epoch + commit |
| repeated PUT | unchanged | unchanged | no second write/bump |
| remove_favorite, actual delete | missing | +1 | conditional DELETE rowcount + advance + commit |
| repeated DELETE | unchanged | unchanged | zero affected rows, no bump |
| submit_feedback true, actual insert | missing | +1 | durable stage1 Feedback + Favorite + epoch |
| submit_feedback false, actual delete | missing | +1 | same durable stage1 |
| Feedback no-op or idempotent replay | unchanged | unchanged | no extra Favorite transition |
| new generated owned asset | missing | NOT FIXED | new visible asset can commit without cursor invalidation |
| first own terminal shared-asset association | missing | NOT FIXED | terminal task can commit without cursor invalidation |
| existing terminal polling/result replay | unchanged | unchanged | no new membership write |

## Shared-file boundary for PF-1B

Only `backend/app/services/v3/feedback_service.py` changes production behavior.
Modified functions: `set_favorite`, `remove_favorite`, `submit_feedback`.
New `_change_favorite` performs the actual Favorite DML before calling the existing
owner-state authority; it never commits. DELETE counts actual affected rows to
avoid double bumps from stale pre-reads. INSERT must flush successfully first.
Concurrent completed PUT is recognized only after rollback and persisted Favorite
lookup. Favorite/epoch failures roll back together.

New `_persist_feedback_stage1` keeps feedback/Favorite/epoch in the durable first
transaction, preserving the later skipped-status stage. It has at most one local
database retry for witnessed insertion races, with same-owner idempotency lookup
after rollback; no Provider or learning retry. Unknown integrity failures still
raise. Later status-stage failure cannot undo already committed feedback/Favorite.

PF-1B (Issue #152) must adapt its pending changes at this explicit boundary rather
than overwrite the service wholesale. No0013, consent fields/policy, tombstone,
clear/cutoff write, feedback epoch wiring or learning reactivation is included.
`owner_music_state_service.py` and its epoch updater are unchanged and authoritative.

## Authorization compatibility — Owner decision required

Legacy `_find_owned_asset` still permits direct owner OR NULL-owner, without a
terminal task requirement. A Favorite-only NULL-owner catalog row can therefore
be written/listed by the legacy interface yet remains denied by the new library
and Stream access authority. Failed/nonterminal tasks add no new library rights.
An asset owned by another user is rejected by legacy even where a legal own task
could prove membership to the new library. This task does not normalize either
policy or treat Favorite as entitlement.

Minimal future option: explicitly approve migrating the legacy helper/list reads
to require_library_access, with compatibility tests and cleanup/read-filter policy
for previously writable NULL-owner favorites. Broad NULL-owner entitlement is not
an acceptable implicit migration. No such authorization change is made here.

## New-asset audit blocker

Two isolated desired-behavior probes reproduce epoch0 instead of1 after actual
SQLite commit: `_persist_generated_asset` creates a directly owned visible asset;
`_persist_task_outcome` gives first legitimate terminal access to a shared asset.
The probes use synthetic rows/audio and existing validated schema, not a Provider.
Failures are reported separately, never hidden as skipped or included in green
Favorite regression counts.

A safe fix must establish serialized first membership per owner across concurrent
tasks. A read-then-bump hook alone can double count shared membership. It must also
protect the background worker's broad exception handlers: epoch failure must not
be classified as Provider failure and commit an already-flushed owned asset or
fallback membership without invalidation. SQLite and MySQL locking differ.

Per the original Owner stop condition, Generation source and lifecycle were left unchanged.
Required next decision: authorize the minimal owner-scoped membership serialization
and transaction-failure boundary, without Provider retry, then require independent
connection races plus generated/fallback rollback and replay tests. New asset
cursor invalidation remains an OPEN Gate. The earlier combined batch was not
pushed; the new Owner scope permits an independent Favorite-only Draft PR after
production-setting regression. Generation design is private and excluded.

## Verification record

Initial valid-schema Favorite RED:12failed/1passed/3warnings. First correction:
13passed/0failed/1warning. The expanded file has23cases, including actual two
independent-connection PUT/DELETE and Feedback races, and unchanged legacy
authorization behavior. Failure injection runs the real epoch update before
raising, verifying Favorite/Feedback/state rollback rather than mocking success.
Initial fixture setup/import failures are not counted as business RED evidence.

Fresh full command through the private strict offline wrapper:

```text
pytest -c pyproject.toml -q -p no:cacheprovider --basetemp=<fresh-private-media-root>
 tests/api/v3/test_int2_favorite_epoch.py
 tests/api/v3/test_feedback.py
 tests/api/v3/test_s7_preference_invalidation.py
 tests/api/v3/test_s7_music_library_api.py
 tests/api/v3/test_s7_music_library.py
 tests/api/v3/test_int2_0012_contract.py
 tests/api/v3/test_int2_playback_concurrency.py
 tests/api/v3/test_int2_0012_preflight_constraints.py
 tests/api/v3/test_generation.py
 tests/api/v3/test_tokenhub_generation.py
 tests/api/v3/test_stability_generation.py
 tests/api/v3/test_int2_stream_gate.py
271 passed / 0 failed / 2 skipped / 2 warnings
```

Both skips require unavailable Windows real-symlink privileges. Warnings are
known Starlette/httpx deprecation and intentionally malformed expression-index
reflection omission, independently detected by the preflight regression.
Guard self-tests7passed/0failed/0skipped/0warnings; separate guarded Frontend
Fixture2+Adapter6passed/0failed/0skipped, one known module-type warning each.
AST2/whitespace pass. Real Provider/test external connection/production DB
operations0. GitHub fetch is separate authorized repository network traffic.
This green subset does not resolve the separately reported2generation failures.

Generation diagnostic:0passed/2failed/0skipped/1warning; both failures are the
actual missing epoch increment. No production Generation implementation changed.
MySQL actual execution, H5/full App/device/production deployment remain NOT RUN.
Real Windows symlink limitations stay distinct from controlled path tests.

## Historical independent local-checkpoint review

No definite Critical/Important defect was identified in the retained Favorite
subset. This does not clear the stopped Generation blocker or approve a push.
Minor deferred: the new fixture uses autoflush=True, whereas production
SessionLocal uses autoflush=False. Existing independent-connection races are
real SQLite evidence, but do not certify identical production Feedback flush
ordering; add a production-setting race variant before promotion.

Invalid-task variants in the new file deliberately keep asset links NULL to
respect the existing generation consistency CHECK. They show that unrelated
unsuccessful tasks and a Favorite do not grant library access. The original
Stream regression in this run additionally attempts invalid bound links and
asserts actual IntegrityError. Do not fabricate illegal fixtures or relax the
constraint just to create a purported bound-failed-task case.

Real MySQL locking/deadlocks, production deployment, live Provider behavior,
PF-1B unpublished work and the stopped Generation implementation are not certified
by this local checkpoint. No remote branch or Draft PR is published for the batch.

## Production-session supplemental acceptance

The earlier autoflush gap is addressed by running every new test with explicit
autoflush=False (production) and autoflush=True (historical compatibility), both
autocommit=False. Targeted result:52passed/0failed/0skipped/1warning;26 per config.
No production Session setting or business implementation was changed this round.

New true-connection races cover Feedback vs direct Favorite PUT/DELETE and the
first owner-state INSERT unique collision. Existing PUT/DELETE and same/different
Feedback idempotency-key races run under both configurations. SQL listeners only
synchronize each connection before its first actual DML; no SQL/results/errors
are replaced. This avoids artificial SQLite barrier deadlocks after a prior write.
Real owner-state collision yields one row and one confirmed IntegrityError with
rollback, zero Favorite/epoch side effects. Duplicate Favorite insertion and
conditional deletion yield exactly one actual state change and epoch increment.
No claim of equivalent real MySQL concurrency is made.

Exception injection evidence is separate: a real epoch UPDATE executes and then
an injected RuntimeError verifies rollback of Favorite/Feedback/state. Injected
stage2 failure verifies durable stage1 remains and replay does not bump again.
These tests are not represented as actual database lock failures.

Generation production source,0011/0012 SQL, routes and permission policy remain
unchanged. A separate private Generation transaction design is not in this PR.

Fresh full supplemental command uses the same twelve files listed above, with
expanded52case Favorite file and a new private basetemp/media root:
**300passed/0failed/2skipped/2warnings**. Earlier271 counts are historical.
Skip/warning explanations unchanged. Fresh Frontend Fixture2+Adapter6passed,
0failed/0skipped, one known warning per Node process. Fresh guard7passed,
0failed/0skipped/0warnings. AST2 and whitespace pass. No production settings,
Generation implementation or historical fixtures were weakened to get this result.
