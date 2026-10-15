# INT-2: 0012 schema and M1 library API subset

Status: isolated integration candidate for review, not production deployment approval.
This is a minimal implementation contract, not approval of the entire R2-A draft.

## Dependencies and scope

Team base: `ff879f70a19328dbe492bf3aa9418e681a5db06b`.
This candidate includes UNMERGED upstream PR #158
(`a753e4d8bc95f337ada162f2564a63cd54378487`) and PR #159
(`7f5b3eb5c7a77830607e46a927a1620f25322c1c`). It is not directly mergeable
until those dependencies and the integration delta are reviewed together.
Owner subsequently approved PR #159's exact incremental fix
`067c67746a33c7e848fc522e4d50500b601698b6`. Its three-file delta is now
integrated through an equivalent non-rewriting patch transfer, retaining the
candidate's private-title epoch hook. Router and upstream API test content match
that exact Backend revision; service differences are the existing title hook only.
No ORM, migration SQL or DTO is changed by this increment. The upstream regression
was first run against the old candidate and failed as expected (409 rather than
200), then passed after integration. This closes the previously recorded upstream
drift blocker, not the separate deployment and cross-database gates.
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
with incompatible columns/types/defaults or context FK fail closed, not auto-repaired.

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

Review PR #158 first, then PR #159 with this schema delta, then the candidate's
0012/contracts/tests. Do not merge PR #155 wholesale: its isolated DraftBase and
0013 are not the production schema. This stacked candidate preserves upstream
commit identities and must not be treated as a directly mergeable replacement for
those reviews. Resolve the upstream merge plan explicitly before promoting it.
No main/team-base update, automatic PR merge or production migration is authorized.

## Actual verification record

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
