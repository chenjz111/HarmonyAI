# Account Security R1 implementation plan

Owner spec: docs/sprint7/OWNER_APPROVAL_20261024_ACCOUNT_SECURITY_R1.md. Continue inline TDD; no new policy decisions inferred.

1. Persist independent approval; keep Feedback PR CI running.
2. RED registered access must verify existing AuthSession and server UserIdentity.auth_epoch; Guest old claims remain compatible. Implement narrow verifier with no registered issuer exposed until session service exists.
3. RED Argon2/NFC/password blocklist adapter, username normalization, bind same owner/no login merge. Production missing reviewed blocklist fails closed.
4. Reuse0011 AuthSession. Design additive0014 account credentials/refresh-proof evidence/login throttles, exact SQLite/MySQL contracts, no historical checksums modified.
5. RED atomic rotation/replay-family revocation/idle+absolute bounds/logout/global revocation/rollback; implement caller-owned services and durable transaction adapters.
6. Add origin+session-CSRF gates and disabled registration/refresh routing; H5 memory and Android verified-store abstract adapters only, no persistent fallback.
7. Guarded deterministic process tests, regression, independent review, commit and Draft update. Actual MySQL/Android/production HTTPS NOT RUN until available. Do not declare account acceptance complete.
