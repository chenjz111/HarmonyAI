# Account A security implementation Gate — W2 local evidence

Status: preparation only; no live registration/login enabled. Owner approved the account product behavior, not the parameters below.

## Local evidence (2026-10-14, Windows AMD64, Python 3.12)

Installed versions observed through package metadata: argon2-cffi 25.1.0, argon2-cffi-bindings 26.1.0, cryptography 46.0.7, PyJWT 2.13.0. No package was installed or downloaded. Local presence does not establish approved distribution provenance or a vulnerability audit; dependency pin/lock review remains required.

Synthetic Argon2id benchmark candidate: memory_cost=19456 KiB, time_cost=2, parallelism=1, salt_len=16, hash_len=32. Three hash-plus-verify measurements: 47.75, 50.07, 48.26 ms; median 48.26 ms. The synthetic password and encoded hashes were not logged. This is one-machine serial latency, not peak-memory/concurrency/load proof or an approved production parameter set.

Before implementation: pin approved package sources/versions; benchmark alternatives and concurrent failure/login load; set resource admission and per-account/per-IP limits; verify rehash policy, independent salts, malformed hash handling and no plaintext persistence. Do not use a general-purpose digest for password storage.

## Parameters requiring security/Owner approval

| Gate | Concrete decision/evidence needed |
|---|---|
| Access TTL | Choose short-lived TTL, clock skew and signing/key-rotation policy; former 60 minutes remains a candidate only |
| Refresh TTL | Choose absolute/sliding expiry, idle limit and revoked-family evidence retention; former 30 days remains a candidate only |
| Rotation | Server stores only cryptographic digest of high-entropy random refresh proof; transaction atomically consumes old proof and creates successor |
| Replay/concurrency | Two simultaneous refreshes must not both issue successors; consumed-proof replay revokes family; decide explicit lost-response/retry behavior without silently trusting a reused token |
| Revocation | Session logout and owner auth_epoch checked on protected requests; binding and identity switch revoke stale guest authority without transferring data |
| Username | Freeze Unicode normalization/case/collision and length policy; enforce unique normalized subject in DB; concurrent binding atomic/idempotent |
| Login failures | Approve per-account/per-origin limits, generic failure responses, backoff, audit retention and denial-of-service controls |
| Account recovery | No verified email/phone means no self-service reset; show loss/recovery limits; never recover ownership from records, device IDs or guessed username |

## Platform dependencies

Android: no verified application secure-credential adapter was found in this W2 review. Require a pinned Keystore-backed adapter, device/version tests, backup/migration behavior, logout deletion and failure handling. Ordinary uni/local storage is not an acceptable refresh fallback.

H5: require actual deployment-origin inventory and HTTPS proof. Refresh uses HttpOnly+Secure Cookie with approved SameSite/domain/path; response body need not expose refresh proof. Login/refresh/logout require CSRF and Origin validation, credentialed CORS allowlist, and rejected unexpected origins. Token/body platform selection must not bypass browser protections. No long-lived credentials in localStorage/ordinary frontend storage.

The current api-v3 storage/auth code is legacy and not evidence that these new guarantees exist. This review implements no auth endpoint, credentials table, migration 0011, password reset or global configuration change.

## Approval checklist

Approve dependency pins/provenance and measured Argon2id resource budget; choose token lifecycle and refresh race policy; validate Android adapter and H5 deployment protections; freeze username/limit/recovery semantics; then authorize authenticated session/credential models and paired migration 0011. Any unavailable dependency remains fail-closed. Account A remains a mandatory unfinished M1 delivery, not deferred by this preparation checkpoint.
