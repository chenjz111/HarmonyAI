# Account R1 resumable engineering checkpoint

- Branch: codex/s7-m1-account-security-r1-20261024, based on fab8b50514347cec9f8950235ac9c052fe6ea83e. Implementation commits:7b66b47 (account core/0014),324b195 (client),46714e0 (CI/acceptance).
- PR171 remains Draft on prior branch. Hosted run40106717516 passed Linux+Windows all specialties at fab8b50. No merge.
- Owner Account Security R1 independently recorded; previous draft preserved. No further R1 parameter approval needed.
- Implemented: registered sid/epoch/session checks, Guest compatibility, fixed Argon2id/NFC/password-blocklist adapter, same-owner binding, login/no merge, durable rate buckets, refresh proof rotation/family replay revocation, idle/absolute expiry, logout/all/password-change revocation, explicit unknown-commit reauthentication.
- Formal0014 new account tables reuse0011 AuthSession. Paired SQL/registry/preflight present; no0001–0013 checksum changes. Partial schema fails closed; SQLite DDL/ledger atomic; MySQL engine/check/type enforcement and recovery refusal.
- Evidence: registered/Guest14p; password17p; initial lifecycle10p; combined expanded account51p. Review found missing InnoDB enforcement: RED3f -> implementation added;51p includes fix. No real MySQL claim.
- Verified: previous-key rotation plus runtime safety140p; three process scenarios12 children passed; backend fixed72p, frontend fixed92p; integration193p/2 permitted Windows symlink skips.
- Next: migration145p/Feedback72p/launcher44p confirmed; commit reviewed account milestone, own Draft PR targeting team baseline with dependency171, verify Hosted CI. Native router/H5/Keystore adapters are implemented but remain closed/unaccepted.
- Gaps: reviewed production password blocklist distribution, H5 production Origin/preauth-CSRF deployment, verified Android Keystore adapter/device and target resource/load acceptance. Registered/refresh public routes remain unexposed and H5 service stays fail-closed. No ordinary-storage credential fallback.
- NOT RUN: real MySQL/TLS/concurrency, Android, production HTTPS/CSRF/cookie and real Provider. No learning/live/release enabled.
- Medical preparation selection:135p/7f; all7 failures missing approved corpus chunks asset. No medical rule/test assertion changed; #154 still independent signoff.

- Final read-only review of keyring/exclusive authentication, router validation sanitization, H5 primitives and client isolation found no confirmed P1/P2; production gates remain closed. Browser helper lock order aligned identity→session; ORM explicitly sets InnoDB.

## 2026-10-25 continuation
- Account Draft PR173 opened against the team baseline, depending on PR171. Added explicit restart restore: persisted Refresh proof must complete one server rotation before runtime authority is restored; no trusted identity is read from ordinary storage.
- MySQL8.0.44 binary exists locally; no existing database was accessed and no isolated daemon/TLS/concurrency channel has been validated. Real MySQL remains NOT RUN; original Guard was not loosened.
