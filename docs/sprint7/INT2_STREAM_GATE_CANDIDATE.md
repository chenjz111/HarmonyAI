# INT-2 Stream authorization candidate

Status: isolated implementation/testing candidate, not permission to enable
historical Player navigation or deploy to production.

## Exact dependency and integration boundary

Base PR #160: `30a36f81e98dfd4be27da4e118a27d769c87894f`.
Upstreams: PR #158 `a753e4d8bc95f337ada162f2564a63cd54378487`;
PR #159 `067c67746a33c7e848fc522e4d50500b601698b6` (its incremental patch is
already incorporated in #160; do not infer ancestry from patch equivalence).
This branch is stacked on #160 and must target its integration branch, not the
team baseline. No upstream PR or base branch is changed by this candidate.

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

## Actual verification

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

Review/merge #158, then #159 (including the exact replay fix), then reconcile #160.
After the parent is accepted, transplant only this Stream commit/delta onto the
actual approved unified tree and rerun these gates. If #160 is squash-merged,
compare the child patch explicitly: do not merge the child's repeated ancestry
into the team branch. This stacked Draft PR is review-only; no automatic merge,
team-baseline update, production migration or Player activation is authorized.
