# Account Security R1 engineering delivery — 2026-10-24

Base: `fab8b50514347cec9f8950235ac9c052fe6ea83e` (PR171). Branch: `codex/s7-m1-account-security-r1-20261024`. Target: `team/s7-m1-w2-baseline`. Owner approval is independently preserved in `OWNER_APPROVAL_20261024_ACCOUNT_SECURITY_R1.md`; earlier security Draft remains historical.

## Implemented contract

- Existing Guest four-claim HS256 tokens remain valid until their signed/database expiry; no new sid/epoch requirement or TTL extension. Explicit previous-key verification supports normal rotation windows without relaxing expiration. Operators must retain required old verification keys; configuration rejects more than8 previous keys rather than silently pruning, so rotation cadence/configuration must preserve the complete lawful-token window. This is not emergency-compromise revocation.
- Registered access requires explicit access type, sid, current server auth_epoch, owned active session and expiry. Exclusive transaction authentication supports binding, password change and revocation without borrowed-transaction lock conflicts.
- NFC passwords use pinned Argon2id19456KiB/time2/parallel1/salt16/hash32, independent random salts,15–1024 Unicode codepoints, no truncation/category rule. A reviewed common/compromised blocklist is mandatory for the injected policy; no production distribution is claimed.
- Guest binding retains internal owner and existing data; login has no merge operation. Lowercase3–32 ASCII username uniqueness/format is enforced in service and DB. Password change/all logout advance server epoch and revoke sessions.
- Refresh uses CSPRNG256bit proofs and persisted digests only. Rotation consumes the original once, preserves initial14day absolute bound and7day idle bound, and consumed-proof replay durably revokes family. Commit uncertainty returns no credential and requires reauthentication; no automatic old-proof recovery/retry.
- Account/source15minute rate buckets are transactionally locked and persisted. Candidate5-failure progressive delay and30-source-attempt limits are locally tested, including independent-process races; production resource/load acceptance remains outstanding. Trusted source is server peer address, never caller forwarding headers.
- Additive paired0014 creates credential/session-extension/refresh-evidence/rate structures, reusing0011 identity/AuthSession. Exact schema checks include PK/unique/FK/CHECK/type/precision, partial-state refusal and MySQL InnoDB+enforced CHECKs. Historical0001–0013 SQL is unchanged. SQLite DDL+ledger rollback is tested; destructive downgrade is explicitly refused pending reviewed operator recovery.
- Native API router factory defaults closed and is deliberately absent from production `main`/OpenAPI. Isolated HTTP harness covers binding/refresh/logout; browser Origin/Cookie cannot select native behavior. Validation errors are sanitized to avoid credential echo.
- H5 Cookie/Origin/session-CSRF primitives are isolated and unexposed. H5 issuer/refresh stay closed without verified deployment inventory/preauth-CSRF integration. Cookie attributes are __Host-,Path=/,Secure,HttpOnly,SameSite=Lax,no Domain.
- Frontend registered adapter keeps access in runtime memory, refresh solely in an injected verified Keystore-backed store, rejects unavailable/H5 capabilities, protects identity generations and serializes credential writes/clear. Unknown refresh clears local authority and requires reauthentication; logout clears locally and requests server revocation even if one side fails. No production Keystore plugin or browser credential fallback is supplied.

## Verification

Use original guarded runner `tools/ci/run.py --suite account --evidence-dir <new-outside-source-dir>`, `run_account_processes.py`, and frontend specialty runner. Current fixed inventory72 backend tests; frontend specialty91 tests including7 new adapter behaviors. Three independent-process scenarios/12 guarded children cover refresh double use, competing Guest bind and source-limit increments. Relevant integration regression193p/2 existing Windows symlink permission skips; historical/generic migration regression145p; Feedback R1 regression72p; launcher44p; Guest/keyring+runtime security140p. Final exact-commit CI to be recorded in the Draft PR and external local resume state.

Independent read-only reviews found missing InnoDB engine verification, fixed with RED→GREEN. New routing/keyring/CSRF/client scope was separately reviewed with no confirmed P1/P2; reviews are engineering checks, not platform acceptance. All raw logs/telemetry are external; sanitized Hosted logs exclude databases and credentials.

## Acceptance matrix

| Gate | Status / boundary |
|---|---|
| PR171 Linux+Windows CI at fab8b50 | PASS, run40106717516 |
| Account SQLite/Fake internal lifecycle | Guarded tests; not a deployment grant |
| Account Hosted Linux+Windows at final head | Pending own Draft PR run |
| Real MySQL DDL/TLS/recovery/concurrency | **NOT RUN** |
| Android build/device/Keystore backup/reinstall/unavailable-key | **NOT RUN**; abstract adapter/fakes only |
| H5 actual HTTPS Origin/Cookie/CORS/preauth-CSRF | **NOT RUN**; registered H5 feature closed |
| Production password blocklist provenance/distribution | Missing reviewed operational dependency; issuer closed |
| Target Argon2 memory/concurrency/latency and rate load review | **NOT RUN**; approved algorithm never downgraded |
| Existing Guest browser storage remediation | Still outstanding; new registered adapter does not certify it |
| Real authorized audio/Range/redirect acceptance | **NOT RUN**; retain existing synthetic coverage and redirect limitation |
| Whole frontend materials | Earlier552p/7 missing approved visual/evidence assets; added adapter tests separate; no fabricated replacements |
| Full backend | Earlier collection5 historical missing-module/scrubbed-home errors; no Guard relaxation |
| Medical preparation |135p/7f, missing approved corpus chunks; #154 full counterfactual audit/independent medical signoff still open |
| Final retention/account erasure/backup cleanup | Not decided here; no automatic evidence cleanup introduced |

No new account UI/route is advertised as operational, no registration/refresh activation, no production migration, real Provider, Live Flag, learning, merge or release. Account product completion and M1_GO remain unclaimed. Remaining dependencies are concrete acceptance gates, not missing approval of the already-approved R1 parameters.
