# INT-2: 0012 schema and M1 library API subset

Status: isolated integration candidate for review, not production deployment approval.
This is a minimal implementation contract, not approval of the entire R2-A draft.
2026-10-18 reconciliation: the earlier constraint-probe blocker is resolved by
read-only structural preflight validation and formal negative regressions below.
This remains a Draft candidate, not permission to merge or deploy.

## Dependencies and scope

Original team base: `ff879f70a19328dbe492bf3aa9418e681a5db06b`.
Current reviewed team base: `d17ce83164b88bcb2bf34a0a3227d6379683523e`.
PR #158 (`a753e4d8bc95f337ada162f2564a63cd54378487`) and PR #159
(`067c67746a33c7e848fc522e4d50500b601698b6`) are now merged in that base.
The 2026-10-18 reconciliation starts at the published PR #160 commit
`30a36f81e98dfd4be27da4e118a27d769c87894f` and merges the current team base
with a normal two-parent merge, preserving all existing public history.
No conflict occurred and the automatic merge left the production/test code tree
identical to that original PR #160 candidate. A separate repair adds only existing
0012 schema validation, its regressions and this record. No repeated upstream
patch transfer, rebase or squash is performed.
Relative to the new base, this PR is the 0012 schema/DDL/exports/contracts/tests
and private-title epoch increment; the merged Backend router and replay recovery
are not duplicated changes. Separate deployment and cross-database gates remain.
PR #155 (`31b62112d0c2d814ff13c17b67b5d555e4789a3f`) is a reference only;
its DraftBase and 0013 are not imported or registered.

Exactly one production Base defines the three tables below. The library router
remains unregistered in the production application. API tests mount the real
router in an isolated application; the Frontend adapter remains disabled by default.
No Stream, authentication endpoints, Preference business logic or Frontend UI is changed.

## Shared schema

| Table | Actual fields and constraints |
|---|---|
| owner_music_state | owner_internal_user_pk PK/FK users.id; library_epoch and feedback_evidence_epoch nonnegative BIGINT NOT NULL DEFAULT 0; preference_clear_cutoff nullable timestamp |
| music_library_state | owner_internal_user_pk + music_asset_id composite PK; private user_title nullable, 1..120 characters when present; metadata_version nonnegative BIGINT NOT NULL DEFAULT 0; created_at, updated_at |
| music_playback_events | integer autoincrement playback_event_row_id; internal_user_pk, music_asset_id; event_id unique within owner; event_type=play_started; source_context_id nullable; occurred_at and created_at |

The 120-character rule uses character length, not byte length, including on MySQL.
No sidecar last_played_at is stored: the service aggregates real events.
No GET creates owner state. Missing state means epoch/version zero.
Shared assets can have separate private state for different authorized owners.

A parent unique index on generation_tasks(task_id, internal_user_pk, music_asset_id)
supports the playback composite FK (source_context_id, internal_user_pk, music_asset_id).
NULL context is allowed; non-NULL context must match the owner and asset. The service
must additionally verify terminal task status and legal access: FK existence alone
does not grant access. Neither NULL asset owner nor Favorite alone grants membership.
Multiple legal tasks remain explicit contexts; no implicit patient/listener identity
or earliest/latest context selection is permitted.

Compared with PR #155, the actual PR #159 field names, integer playback PK,
owner/event uniqueness and occurred_at are authoritative for 0012. The draft's
255-character title and duplicate last_played_at state are not adopted.
Preference cutoff is schema preparation only: its operational semantics and 0013
still require the Preference workstream's review.

## Migration and initialization

Candidate registration is 0010 -> real 0011 -> 0012; 0013 is absent.
0001..0011 SQL and checksums are unchanged from PR #158.
The executor validates the registered history prefix and checksums before new DDL.
SQLite 0012 DDL and its ledger entry share one transaction; injected failure rolls
back 0012 and permits retry without rewriting the separately committed 0011.
create_all-first initialization and repeated startup are tested. Existing side tables
with incompatible columns/types/defaults, PK, FK/CASCADE, CHECK or uniqueness
fail closed, not auto-repaired. Recorded 0012 history also requires all three tables.
CHECK validation uses a bounded expression grammar with exact structural matching
of canonical conjunctions; unknown expressions fail closed. Column comparisons
are not rounded to integer boundaries: SQLite INTEGER affinity permits REAL.
SQLite physical index metadata verifies full, nonpartial, BINARY uniqueness and
autoincrement structure. MySQL supplements reflection with physical index metadata
and CHECK ENFORCED metadata on supported versions; inability to prove a constraint
is a refusal, not a pass. These checks do not substitute real MySQL verification.

SQLite downgrade refuses nonempty extension tables or higher migration history
before destructive DDL. Empty 0012 downgrade/re-upgrade is tested. The upstream
fresh-create 0011 downgrade limitation remains unchanged: it safely refuses the
identity table-level CHECK case rather than rebuilding identities.

MySQL SQL and ORM DDL compilation are available, but real MySQL execution is NOT RUN.
MySQL DDL may implicitly commit: transaction syntax is not an atomic rollback
guarantee. Deployment requires isolated MySQL upgrade/fresh/retry/downgrade tests,
backup/restore rehearsal, collation/FK/default checks and a single migration writer.
MySQL down SQL requires operator preflight for empty extension data and no later
migration; it is not an approved production downgrade procedure.

## Minimal API contract for Frontend

All paths below have prefix `/api/v3`. Identity comes from the authenticated
principal, never an owner parameter supplied by the client.

| Method/path | Request | Success data / HTTP |
|---|---|---|
| GET /me/music-assets | limit optional 1..50 (default 20), cursor optional | MusicLibraryPageV1 / 200 |
| GET /me/music-favorites | same pagination | MusicLibraryPageV1 / 200 |
| GET /music/assets/{music_id} | context_id optional | MusicDetailV1 / 200 |
| PATCH /music/assets/{music_id}/title | user_title string or null; expected_version nonnegative integer | TitleUpdateResultV1 / 200 |
| POST /music/assets/{music_id}/playback-events | event_id 1..64 safe identifier; event_type=play_started; source_context_id optional/null | PlaybackEventResultV1 / 201, identical replay 200 |

Success envelope: `{ok:true,data,request_id,schema_version:"harmonyai_v3.0"}`.
Domain errors use `{ok:false,error:{code,message,retryable,next_actions},request_id,schema_version}`.
Framework request validation currently returns HTTP 422 with a `detail` array,
NOT the V3 domain error envelope; the unchanged adapter fails closed with its
invalid-response fallback. This distinction is tested, not disguised as a new code.

MusicLibraryPageV1 = items (unchanged MusicCardV1), next_cursor nullable, has_more.
MusicCardV1 fields remain: music_id, source_type, default_title, user_title,
display_title, metadata_version, playable_created_at, last_played_at, activity_at,
duration_seconds, availability, is_favorite, primary_instrument_code,
primary_instrument_origin, source_summary. The original fixed JSON is unchanged.
Unknown measured duration remains null; target generation duration is not substituted.
Availability remains ready/expired/quarantined/deleted/missing.
activity_at uses real playback if present, otherwise playable_created_at; ordering
and cursor boundaries are service-owned, not fabricated by Frontend.

MusicDetailV1 = card, audio:{availability,duration_seconds,format}, source_contexts
[{context_id,kind,availability}], selected_context_id nullable, history_explanation nullable.
Without explicit context both selected_context_id and history_explanation are null.
The explanation is persisted origin metadata (music_id, context_id, task_status,
source_type, fallback_applied, completed_at, prescription_id), not a newly generated
five-chapter explanation or permission to download raw source documents.
Title result = music_id, user_title, display_title, metadata_version.
Playback result = event_id, music_id, event_type, occurred_at, last_played_at, replayed.
occurred_at is server time; UI views/prefetch/seek are not playback starts.

Cursor is signed and bound to owner, list and library_epoch. Clients treat it as
opaque, not as encrypted confidential storage. HARMONY_LIBRARY_CURSOR_SECRET must
be configured securely (minimum 32 bytes); tests use synthetic values only.
Missing signing configuration fails closed. A stale cursor requires first-page reload.

| Domain condition | HTTP / code |
|---|---|
| Invalid limit / cursor | 400 INVALID_LIMIT / INVALID_CURSOR |
| Stale list cursor | 409 LIBRARY_CURSOR_STALE; retryable, refetch_first_page |
| Signing unavailable | 503 LIBRARY_CURSOR_UNAVAILABLE |
| Missing or unauthorized asset | 404 RESOURCE_NOT_FOUND (same shape) |
| Unavailable playback asset | 404 RESOURCE_NOT_AVAILABLE |
| Invalid selected source | 422 CONTEXT_NOT_AVAILABLE |
| Stale title CAS | 409 TITLE_VERSION_CONFLICT; retryable, refetch_detail |
| Event ID reused with different payload | 409 PLAYBACK_EVENT_CONFLICT |

Literal synthetic examples: `tests/api/v3/fixtures/int2_music_library_api_v1.json`.
Python verifies those examples against the real router on migrated SQLite. The
Node contract test passes the same fixture through the unchanged public adapter.

## Transaction hooks and deferred dependencies

PR #159 already advances library_epoch with the first actual playback event;
replay does not increment it. This candidate adds the missing epoch hook at the
two successful private-title CAS return paths in the same transaction. Failed CAS
does not advance the epoch. MusicAsset.title/checksum and generated snapshots
remain unchanged; no new measured-duration column is added.

Favorite writes remain in `backend/app/services/v3/feedback_service.py`:
submit_feedback, set_favorite and remove_favorite, reached through the existing
feedback/favorites router. These paths need coordinated epoch wiring; this batch
does not modify them. Required follow-up tests: actual favorite transition advances
epoch once; identical PUT, missing DELETE and idempotent feedback replay advance
zero; rollback advances zero; cross-owner state is isolated; prior cursors expire
after committed change. Include the legacy feedback path that changes Favorite.
Do not enable list UI until that dependency is closed.

Backend owns library access/service/router behavior. Integration owns shared ORM
exports, migrations and this cross-module contract. Preference owns consent,
delete/clear/tombstone/epoch behavior and must consume the same owner state, not
create a second one. Frontend consumes the fixture without inventing DTO fields.
Stream authorization/retention remains a separate closed Gate; these availability
checks do not certify real Stream access. NULL-owner catalog broad entitlement is
not introduced. PF-1A stays off; no 0013 or automatic learning is implemented here.

## Review and merge order

PR #158 and PR #159 are already merged; review this reconciled PR #160's net
0012/contracts/tests increment against the exact current team base. Do not merge
PR #155 wholesale: its isolated DraftBase and 0013 are not the production schema.
PR #160 remains Draft pending Owner's review and explicit merge decision.
PR #161 remains a separate Stream child; its unchanged branch must synchronize
this new parent in a later, separately authorized task. No Stream code is included.
No main/team-base update, automatic PR merge or production migration is authorized.

## Historical verification record (before reconciliation)

Python 3.12 / SQLite 3.49.1, isolated temporary databases and strict offline guard:

```text
pytest -q -p no:cacheprovider
  tests/api/v3/test_int2_0012_contract.py
  tests/api/v3/test_s7_music_library_api.py
  tests/api/v3/test_s7_music_library.py
  tests/api/v3/test_0011_auth_foundation.py
  tests/api/v3/test_v3_migrations.py
  tests/api/v3/test_v3_business_migrations.py
122 passed, 1 skipped, 1 warning
```

The skip is real Windows symlink creation unavailable on this host; controlled
canonical-path boundary tests still run. Warning: Starlette/httpx deprecation.
Network guard self-tests: 7 passed. Each Node file runs in its own guarded process:
`node --test --test-reporter=tap --test-isolation=none` with
`tests/contract/s7-library-adapter-contract.test.mjs` (2 passed) and
`frontend/tests/s7-library-api.test.mjs` (6 passed). Each process emits one known
MODULE_TYPELESS_PACKAGE_JSON warning. No test calls a real Provider or production
database. Test harnesses/evidence stay private outside the committed source tree.
No complete App, H5 build, real MySQL or real Stream Gate is claimed.

### Approved concurrency increment

The original 122-test result above is historical. The new affected command adds
`tests/api/v3/test_int2_playback_concurrency.py` to those six Python files and
retains the Backend author's new test. All tests run under the same private
offline wrapper, with temporary SQLite files and synthetic identities/assets.
Actual increment result: **133 passed, 0 failed, 1 skipped, 1 warning**.
Skip and warning remain the previously identified Windows real-symlink
limitation and Starlette/httpx deprecation. Shared Node fixture: **2 passed**;
original adapter: **6 passed**, with one known module-type warning per process.
Offline guard self-verification: **7 passed**. No real Provider or external test
connection occurred. MySQL actual execution and full H5/App remain NOT RUN.

Evidence types are deliberately separate:

- **Real request concurrency (8 cases):** two simultaneous in-process HTTP
  requests use distinct SQLAlchemy Sessions and distinct physical SQLite
  connections. A SQL execution listener places a barrier before both actual
  playback INSERT statements; it does not substitute SQL, query results, or an
  exception. Same owner/event/asset is tested three times with initial owner state
  present and absent (6 cases): exactly one row, 201 + 200 replay, identical stored
  occurred_at and epoch exactly 1, including subsequent sequential replay.
  Different assets with the same owner/event are tested with state present and
  absent (2 cases): 201 + 409, one winning event and epoch 1; never a false replay.
- **Real owner-state conflict (1 case):** two independent Sessions/connections
  race actual first owner-state INSERTs via the production shared transaction
  helper. One commits, one gets the real uniqueness error; after rollback the
  replay resolver finds no event. One owner row, epoch 0, no playback rows.
- **Simulated exception evidence:** the retained upstream test injects an
  IntegrityError to exercise the route's already-stored-event recovery branch.
  A separate new route test injects an owner-state IntegrityError with no stored
  event and verifies retryable 409, not a fabricated successful replay. These
  are exception-handler tests, not real concurrency evidence.

SQLite serializes writers: playback is inserted before owner state, so a natural
owner-state collision *inside two playback HTTP requests* is not independently
forced here. Its direct shared-helper race and route error handling are verified
separately. This is not MySQL race validation, an exhaustive scheduling proof,
multi-process/load testing, or approval of database lock retry policy. Each test
barrier/future is bounded; no sleeps, remote services or production data are used.

## Earlier 2026-10-18 reconciliation attempt (historical)

This record describes the earlier blocked attempt, not the repaired result below.
The ordinary merge has parents: published PR #160
`30a36f81e98dfd4be27da4e118a27d769c87894f` and approved team base
`d17ce83164b88bcb2bf34a0a3227d6379683523e`. There were no Git conflicts and
no production-code edits. These are the proposed merge parents; the merge remains
uncommitted after the safety probe failed. Public history is not rewritten.

Actual offline Python command (through the established private wrapper):

```text
pytest -q -p no:cacheprovider
  tests/api/v3/test_int2_0012_contract.py
  tests/api/v3/test_int2_playback_concurrency.py
  tests/api/v3/test_s7_music_library_api.py
  tests/api/v3/test_s7_music_library.py
  tests/api/v3/test_0011_auth_foundation.py
  tests/api/v3/test_v3_migrations.py
  tests/api/v3/test_v3_business_migrations.py
  tests/api/v3/test_guest_auth.py
  tests/api/v3/test_generation.py
  tests/api/v3/test_feedback.py
  tests/api/v3/test_tokenhub_generation.py
163 passed / 0 failed / 1 skipped / 1 warning
```

The skip is Windows real-symlink privilege unavailable; canonical-boundary
protection still runs. Warning: known Starlette/httpx deprecation. No newly
observed or unexplained failure; no assertion, fixture or test is changed here.
Each Node file runs separately through the established Node offline guard:
`node --test --test-reporter=tap --test-isolation=none` with
`tests/contract/s7-library-adapter-contract.test.mjs` (2 passed / 0 failed /
0 skipped) and `frontend/tests/s7-library-api.test.mjs` (6 passed / 0 failed /
0 skipped). One known module-type warning per process. Guard self-tests:
7 passed / 0 failed / 0 skipped / 0 warnings.

Temporary SQLite, synthetic identities/audio and Fake dependencies only.
Live TokenHub credentials are removed from the test child environment. Test
external connections, real Provider calls and production DB operations are all
zero. GitHub fetch/push/PR metadata operations are separate authorized network
activity, not Provider testing. The prior single live MiniMax call is not repeated.
No push or PR metadata write was ultimately performed in this reconciliation.

Additional bounded existing-schema acceptance probe: **0 passed / 1 failed /
0 skipped / 1 warning** (the same Starlette/httpx warning, in a separate process).
A temporary pre-existing owner_music_state table with correct columns/types/
defaults but missing its owner FK was accepted by preflight and migration.
This is an existing PR #160 gap, not introduced by the ordinary merge. It blocks
the Owner requirement that incompatible existing structures fail closed.
The private probe and evidence are not added to the production/test Git tree.
Needed follow-up: validate required PK, FK, CHECK and unique constraints before
any pending DDL, add negative constraint regressions, and rerun the gates. Do not
change frozen 0001..0011 SQL or automatically repair incompatible tables.

0001..0011 published SQL/checksums, production route registration, GenerationSpec,
Prompt Compiler, Provider, Stream and Feedback/Favorite write paths remain
identical to the approved new base. MySQL SQL/DDL compilation remains static
evidence only; real MySQL execution is NOT RUN. Full App/H5/private Corpus and
device-release gates are not claimed. Favorite epoch, 0013, Stream child
reconciliation and deployment approval remain OPEN; this PR stays Draft.

## 2026-10-18 preflight repair and resumed reconciliation

The missing-owner-FK probe was converted into tracked formal tests in
`tests/api/v3/test_int2_0012_preflight_constraints.py`. Initial red evidence:
41 failed / 9 passed. Review also identified that `epoch > -1` is weaker than
`epoch >= 0` for REAL values stored in SQLite BIGINT columns; two real-database
negative tests first failed, then the parser was narrowed to preserve that
difference. No canonical SQL, ORM, existing assertion or business behavior was
changed to obtain a pass.

The new file has 64 tests. Coverage includes PK, FK targets/CASCADE, full owner
event uniqueness, composite context FK and its parent index, CHECK removal and
weakening, defaults/nullability, autoincrement, recorded-history corruption,
read-only rejection with schema/data snapshots, valid alternative SQL forms,
missing parents, expression/partial/collation index traps, and MySQL metadata
enforcement/prefix-index cases. MySQL cases use synthetic metadata transports;
they are not live MySQL execution. Existing suites cover fresh/create_all,
0011 upgrade/retry, title CAS, owner isolation and independent SQLite connections.

Final affected command adds this new file to the eleven Python files listed in
the earlier attempt: **227 passed / 0 failed / 1 skipped / 2 warnings**.
The skip is the existing Windows real-symlink privilege limitation. Warnings are
Starlette/httpx deprecation and expected Inspector omission of a deliberately
malformed expression index; the independent physical-index check rejects it.
Node commands are unchanged and freshly run in separate guarded processes:
shared Fixture 2 passed; original adapter 6 passed; 0 failed / 0 skipped.
There is one known MODULE_TYPELESS_PACKAGE_JSON warning per Node process.
Offline protection self-tests: 7 passed / 0 failed / 0 skipped / 0 warnings.
All test data is synthetic and SQLite temporary; real Provider calls and
production database operations remain zero. Private harnesses are not committed.

The repair and normal merge preserve published history. Only the migration
preflight, this contract and the new test file change relative to the previous
PR #160 tree. 0001..0011 SQL/checksums and 0012 SQL/ORM remain byte-identical.
Favorite epoch, 0013, Stream child reconciliation, real MySQL and deployment
remain open; full App/H5/private Corpus validation is not claimed.
