# INT-2 Stream authorization candidate

Status: isolated implementation/testing candidate, not permission to enable
historical Player navigation or deploy to production.

## Exact dependency and integration boundary

Original stacked base PR #160: `30a36f81e98dfd4be27da4e118a27d769c87894f`.
Upstreams: PR #158 `a753e4d8bc95f337ada162f2564a63cd54378487`;
PR #159 `067c67746a33c7e848fc522e4d50500b601698b6` (its incremental patch is
already incorporated in #160; do not infer ancestry from patch equivalence).
That was the original stacked target. PR #158/#159/#160 are now merged into
the reviewed team base `bfce62eb4e49d62594387b0b189df5f368b01a7a`.
The 2026-10-18 synchronization starts from original Stream HEAD
`9638ad061eb88b6858d3c06b65175e8fa923e269` and ordinarily merges this exact
team base, preserving history without rebase/squash/force push. PR #161 now
targets `team/s7-m1-w2-baseline`, not the old integration branch.
No team-base or main branch is changed by this candidate.

## Minimal production change

- `generation_service._find_owned_asset`, used only by Stream, delegates to
  `require_library_access` and maps denied/absent to the same existing 404 error.
  Direct asset ownership or an own succeeded/matched_fallback task is required.
  NULL owner, Favorite and another owner's task grant no rights by themselves.
- `get_playable_asset_stream_path` checks membership first, then the shared
  `library_availability`. All non-ready states refuse streaming. Only after
  authorization may retention, private storage or file readability be inspected.
- `music_library_service.resolve_library_audio_path` extracts the existing W1
  path/readability checks without relaxing them. Both availability and Stream
  use it. The path returned to FileResponse is the checked canonical local path,
  not the original untrusted locator. Relative and in-root absolute media paths
  remain supported; remote/unknown/out-of-root storage fails closed.
- FileResponse/router behavior is unchanged. No library router registration,
  Catalog candidate matching, generated output, Provider, snapshot, Favorite,
  Feedback, migration or medical algorithm is changed.

This is a request-time check, not an immutable file-descriptor lease. The existing
FileResponse reopens the checked path. Concurrent local filesystem replacement or
retention change after the check is not tested/solved here. Deployment must protect
the media tree from untrusted local writers and separately evaluate atomic file
handoff/retention races; this candidate is not a production hardening certificate.

## Red/green evidence

Before the production change, synthetic tests reproduced:

- NULL-owner Catalog asset with no own legal task: expected 404, actual 200.
- Owned ready row with expired retention: list/detail expired, but Range stream
  returned 206 instead of 404.

The first full new test run had 30 passed, 1 skipped and one fixture error:
the new test used `user_id`, while the existing auth response is `public_user_id`.
Only that fixture key was corrected; no authentication implementation or assertion
was weakened. A raw datetime SQL fixture was changed to the same ISO timestamp
literal to avoid Python's deprecated SQLite datetime adapter in test setup.

## Original verification (historical, not current synchronization evidence)

Environment: Python 3.12, SQLite 3.49.1, FastAPI 0.139.0, Starlette 1.3.1.
All tests ran through the established private offline wrapper, with synthetic
data, temporary SQLite databases and synthetic parseable MP3 bytes. The legacy
generation tests use their existing Fake/Mock dependencies. No real Provider or
production database was used. Legacy audio fixtures are placed beneath an explicit
private temporary media root; arbitrary system paths are not permitted.

Affected command (run through the offline Python wrapper):

```text
pytest -q -p no:cacheprovider --basetemp=<private-temporary-media-root>
  tests/api/v3/test_int2_stream_gate.py
  tests/api/v3/test_s7_music_library_api.py
  tests/api/v3/test_s7_music_library.py
  tests/api/v3/test_int2_playback_concurrency.py
  tests/api/v3/test_generation.py
  tests/api/v3/test_tokenhub_generation.py
  tests/api/v3/test_stability_generation.py
  tests/api/v3/test_int2_0012_contract.py
  tests/api/v3/test_0011_auth_foundation.py
  tests/api/v3/test_v3_migrations.py
  tests/api/v3/test_v3_business_migrations.py
188 passed / 0 failed / 2 skipped / 1 warning
```

The Stream file contributes 31 passed / 1 skipped. The other skip is the existing
W1 real-symlink test; both require Windows symlink privileges unavailable here.
Controlled canonical-escape tests execute and pass, but are not described as
real Windows symlink end-to-end evidence. The warning is the known Starlette/httpx
deprecation. Offline protection self-tests: 7 passed. Guard evidence records zero
real external connections; the known urllib3 IPv6 import probe is blocked before
its system call. No guards or production/global environment settings are relaxed.

## Authorization/storage acceptance

The new tests cover direct owner, own succeeded/matched_fallback task, A/B owner
isolation, NULL-owner without task, Favorite-only and other-owner task denial.
Absent and unauthorized responses have identical domain error data and do not
probe storage. Auth-less/invalid JWT return 401; a real synthetic guest JWT can
read its authorized asset. Provider resolution during Stream is forbidden by
the test fixture.

Nonterminal/failed/cancelled tasks do not grant access. Existing database CHECKs
are tested: invalid tasks cannot be fabricated with asset links contrary to the
production constraint. Expired/deleted/quarantined/missing/read-denied files and
empty/traversal/URL/network/device/alternate-stream/out-of-root paths are denied.
Authorized in-root absolute paths still return exact bytes. No broad Catalog
entitlement is introduced. Existing matched fallback generation/poll/stream
regressions remain passing with the legal requesting task relationship.

## HTTP and actual byte acceptance

| Request | Verified result |
|---|---|
| Authorized GET | 200, exact MP3 bytes, audio/mpeg, correct Content-Length, Accept-Ranges: bytes |
| bytes=0-99 | 206, exact first 100 bytes and Content-Range |
| bytes=100- | 206, exact remaining bytes; joined with prefix equals original |
| bytes=-64 | 206, exact final 64 bytes |
| Repeated GET | 200, identical bytes; no generation side effect |
| Range starting at file length | 416 and bytes */length |
| Reversed range | 400 |
| Matching If-Range ETag | 206, exact requested bytes |
| Stale If-Range ETag | 200, full bytes |
| HEAD | Existing FastAPI GET-only route returns 405 and no body; not enabled here |

Snapshots of users, MusicAsset, GenerationTask, Diagnosis, Prescription, playback
events and owner/library state are identical before/after GET/Range/retry. Reading
or downloading Stream does not write play_started, bump epoch, or modify checksum.
Response headers and captured logs do not expose the temporary storage path.

## Remaining gates and safe promotion

- Android/H5 real Player, device resume/cache behavior and full App/build acceptance
  remain NOT RUN; historical playback stays closed pending coordinated approval.
- MySQL real execution/concurrency, production deployment, real symlink behavior,
  filesystem mutation/retention races and multi-range load testing remain open.
- Favorite epoch coordination and 0013 remain separate work packages.
- Original PR #160 still describes its own pre-Stream scope. This document is an
  additive child candidate; do not edit that parent's authority claims here.

PR #158/#159/#160 are merged. Review only the four-file net Stream increment
against the exact new team base, including the synchronized evidence below.
The PR stays Draft: no automatic merge, team-baseline update, production
migration or Player activation is authorized.

## 2026-10-18 baseline synchronization and risk review

The ordinary merge has no conflicts. Net files remain generation_service.py,
music_library_service.py, this document and test_int2_stream_gate.py. Upstream
0012 SQL/ORM/preflight tests are unchanged from the team base, including both
latest review fixes. No production code is modified after the automatic merge.

`generation_service._find_owned_asset` has exactly one caller, the Stream service.
The separate Feedback helper with the same name is untouched. Catalog matching,
generation idempotency, task creation, fallback, compiler and Provider resolution
are not redirected through the new Stream access gate.

Storage checks reject unapproved local/remote paths and check actual readability.
They are not an atomic authorization/file lease. FileResponse subsequently stats
and opens the canonical path. A party able to replace media files, symlinks or
ancestor directories between validation and open could change the bytes served.
Deployment must prevent untrusted/other-owner filesystem writers, protect media
root configuration, prevent mutable path reuse across owners and assess hardlinks,
atomic handoff and retention workers. This task does not certify that deployment
condition or add an FD-streaming implementation.

Retention/DB state may also change after the request-time authorization and file
checks. The second resolver call narrows but does not remove the gap: it does not
recheck retention after the availability result. An already-authorized response
may continue after expiry/revocation; removal can fail an in-flight response.
Minimum follow-up options are a coordinated deletion policy and lease, rechecking
immediately before response dispatch, and eventually a securely opened file handle
plus explicit in-flight revocation semantics. None alone should be called a fully
atomic DB/filesystem guarantee. These remain deployment/security gates, not a
new entitlement exception. No public exploit details or real filesystem data are
included in fixtures.

Fresh tests include all Owner-requested migration/library/concurrency/Guest/
Generation/TokenHub/Stability/Feedback suites, using the existing offline guard
and a fresh temporary media root. Stream HTTP tests use real TestClient requests
and synthetic MP3 bytes; they never resolve a live Provider. The read-only snapshot
now also checks nonzero library/feedback epochs, private title/version and the
Favorite/Feedback/Preference tables. Multi-range is characterized via multipart
parsing and exact bytes; it does not create a new Player API promise.

Fresh actual command (existing private offline wrapper, with a new private
temporary media root as both HARMONY_MEDIA_ROOT and pytest --basetemp):

```text
pytest -q -p no:cacheprovider --basetemp=<new-isolated-media-root> --tb=short
  tests/api/v3/test_int2_stream_gate.py
  tests/api/v3/test_s7_music_library_api.py
  tests/api/v3/test_s7_music_library.py
  tests/api/v3/test_int2_playback_concurrency.py
  tests/api/v3/test_int2_0012_contract.py
  tests/api/v3/test_int2_0012_preflight_constraints.py
  tests/api/v3/test_0011_auth_foundation.py
  tests/api/v3/test_v3_migrations.py
  tests/api/v3/test_v3_business_migrations.py
  tests/api/v3/test_guest_auth.py
  tests/api/v3/test_generation.py
  tests/api/v3/test_tokenhub_generation.py
  tests/api/v3/test_stability_generation.py
  tests/api/v3/test_feedback.py
285 passed / 0 failed / 2 skipped / 2 warnings
```

Both skips are Windows real-symlink privilege limitations (Stream and W1);
canonical-path substitution tests do not count as real symlink end-to-end proof.
Warnings: known Starlette/httpx deprecation and intentional expression-index
reflection omission in the malformed-index regression (independently rejected).

Frontend shared fixture2 and original adapter6 tests pass in separate guarded
Node processes: 0 failed/0 skipped, one MODULE_TYPELESS_PACKAGE_JSON warning each.
Offline self-verification7 passed/0 failed/0 skipped/0 warnings. AST3 and
whitespace checks pass. Test egress and Provider calls are zero; only verified
stdlib socketpair is allowed and the urllib3 IPv6 probe is blocked. Authorized
GitHub repository operations are separate from test egress.

The new multi-range TestClient request returns206 with multipart/byteranges,
correct aggregate Content-Length and exactly the two requested byte slices and
per-part Content-Range. GET/single Range/resume/If-Range/416/400 checks pass;
HEAD remains405. No write or epoch/snapshot change is observed across repeat
GET/Range. Multi-range load/abuse behavior is not exhaustively assessed.

Historical counts above do not substitute for this evidence. Real MySQL,
device/H5/full App and deployment remain NOT RUN; no historical Player opening.
