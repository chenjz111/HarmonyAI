# Minimal offline PR CI candidate

This is a narrow backend check, NOT whole-repository, device, MySQL/TLS handshake,
production security or deployment acceptance. It never deploys or migrates a
production database. All existing business assertions and feature flags remain.

## Execution

Python 3.12; Ubuntu 24.04 and Windows 2022 GitHub-hosted runners. Read-only token;
checkout does not persist credentials. Official action versions are pinned to
verified commit SHAs. No pull_request_target, secrets, services, deployment job,
provider credentials, fallback generation or continue-on-error.

Install `python -m pip install -r requirements-test.txt` BEFORE protected tests.
This downloads packages, is NOT offline, and is not claimed as test isolation
evidence. The file includes existing requirements.txt and pins pytest/httpx;
it explicitly is not a fully resolved lock. Hosted installation has to be
verified; local reuse of installed dependencies cannot prove it works on CI.

Run from the repo root, using fresh evidence directories OUTSIDE the checkout:

```sh
python -B -m unittest discover -s tools/ci/tests -p test_launcher.py -v
python -B tools/ci/run.py --suite guard --evidence-dir /isolated/temp/guard
python -B tools/ci/run.py --suite regression --evidence-dir /isolated/temp/regression
python -B tools/ci/run.py --suite hardening --evidence-dir /isolated/temp/hardening
```

Use OS-native temporary paths, not the illustrative `/isolated/temp` literally.
The launcher fixes the exact eight-file regression list, sanitizes inherited
credential/provider settings and supplies synthetic values. The guarded child
blocks socket egress/DNS/unauthorized bind/send/process execution and SQLite
outside its canonical temporary sandbox. SQLite URIs are denied. A per-connection
SQLite authorizer also scopes ATTACH/VACUUM INTO and rejects native extension
loading, which cannot be protected using connect events alone. Authorizers are
installed after real SQLite initialization using guarded public connection
constructors; custom factories/authorizer replacement fail closed. ATTACH
targets unresolved before parameter binding are also rejected, even if the
eventual bound value might have been in scope. No unsafe
fallback to ordinary pytest exists. The only socket exception is the verified
stdlib socketpair implementation's own ephemeral listener/client on platforms
that need it; Unix native socketpair needs no IP exception. A known urllib3 IPv6
capability probe is still BLOCKED, only classified as expected import behavior.
Unknown attempts cause exit 90 even if tests catch the exception. Unexpected
skips (including module-level collection skips) cause exit 91; missing guard
evidence cannot yield PASS. Missing required
regression files, empty suites and ordinary pytest failures remain failures.

Empty SQLite filenames are rejected for both connect and ATTACH: SQLite's
temporary-file behavior is not an approved sandbox path. Only `:memory:` or
canonical filesystem paths inside the database sandbox are accepted.

The protected child inherits only PATH, SYSTEMROOT, WINDIR, PATHEXT, TEMP, TMP,
LANG, LC_ALL, LC_CTYPE and TZ, then receives explicit synthetic test settings.
Cloud credential/config paths (including Google, AWS, Azure and Kubernetes),
user-profile variables and unknown variables are not inherited. This avoids an
open-ended secret-name blacklist; it is not a native filesystem access sandbox
and does not prove that files outside the database sandbox cannot be read.

Audit hooks protect cooperative Python tests, not hostile native/ctypes code or
the whole machine. Do not use this tooling to execute untrusted native binaries
or treat it as a general OS sandbox. The parent launcher/test harness is trusted
orchestration and may spawn guarded children; business pytest never has that
permission. No credentials should be supplied to either process. The selftest
module refuses ordinary unguarded execution.

## Evidence and conditional specialty

Each suite writes command.json, sanitized pytest.log, result.json and guard
telemetry.json. The workflow uploads only those files, not sandbox databases,
audio-named synthetic bytes, CA fixtures or runtime files. A synthetic JWT is
redacted from pytest diagnostics. No raw DNS target, subprocess argv or DB
locator is stored in denial telemetry. Platform skips appear by node ID.

The launcher records `child_exit_code` separately from `final_exit_code` in both
command.json and result.json; legacy `exit_code` always means the final launcher
status. Timeout has no confirmed child exit (null) and final 124. A nonzero child
exit remains nonzero. Missing, unreadable, malformed or inconsistent telemetry
cannot yield success: final 92 with unknown counts, not invented zero counts.
Verified unknown guard denials/incomplete selftests yield 90, unexpected skips
91. These checks are fail-closed even if a child reports a successful process
exit; denial, pytest and count records must agree. Fault-injection unit tests
simulate process/timeouts/telemetry separately from actual guarded API probes.

The base-only infrastructure branch lacks the hardening specialty test. Its
step explicitly emits NOT_INCLUDED with null counts, NOT a passing test result.
If the file exists, it MUST execute; a failure is nonzero. On PR #167's actual
merge context, verify the step says PASSED with real counts, never NOT_INCLUDED.
`--source-root` allows a local read-only worktree to be tested with this tool;
it does not copy or merge that worktree's business changes into this branch.

Only two existing, explicitly named Windows symlink-privilege skips are allowed.
Linux skips (including symlinks) fail the run; no global symlink skip is added.
Windows runners may have permission to execute the tests, in which case they
must pass rather than being forced to skip.

## First deployment of the workflow (future Owner action only)

The default branch is main; team/s7-m1-w2-baseline is a separate integration
line. This workflow uses pull_request's PR merge context, not the default-branch
execution of pull_request_target. Current main/team have no workflow. Do not
assume an infrastructure PR will run its newly introduced workflow until an
actual Actions run, effective merge SHA and both OS results are observed.

After separate review/authorization publishes and merges CI infrastructure into
the TEAM branch, the Owner can authorize reopening PR #167 to emit `reopened`
(or another explicitly authorized supported PR event). Verify its source HEAD,
new base SHA/merge ref, workflow path, both OS jobs and specialty execution. No
main merge, history rewrite, empty business commit or privileged trigger is
needed. This candidate performs none of those remote operations and does not
retroactively create a run for an old event. GitHub workflow discovery/approval
and runner availability are still hosted verification gates.

Reference: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request

## Known OPEN gaps

Not fixed or hidden: three full-suite collection errors (missing evals,
knowledge_organ_eval and tools/stability_music_smoke.py), seven frontend
asset/acceptance gaps, Windows symlink limitations, real MySQL/TLS, sid/epoch
revocation, concurrent initialization, devices/onPlay, context/feedback and E2E.
This first CI does not run full pytest, frontend/H5, or npm run build:h5 (which
regenerates the protected manifest). A green scoped job is not whole-app PASS.
