# Owner Account Security Contract R1 — approved 2026-10-24

Source: explicit Owner decision in this Codex chat. This independent approved record supersedes earlier unapproved account parameter candidates, while preserving the old lawful Guest JWT contract. The historical account security draft is retained unchanged.

## A. Existing Guest compatibility

Keep existing `sub`, `auth_type`, `iat`, `exp` and HS256 verification. Do not require sid/auth_epoch/refresh on already issued Guest tokens or reject them simply for missing new claims. Their validity ends at the earlier of signed exp and database guest_expires_at. Existing default issuance TTL is7 days; do not extend any existing token. Old Guest has no automatic registered refresh entitlement and no claim of single-session revocation. Normal signing-key rotation must preserve necessary verification windows for unexpired lawful old tokens; compromise requires a separate emergency revocation procedure. Earlier Guest revocation requires separately designed and tested server denial evidence.

## B. Registered identity

Guest-first, optional registration. Binding an authenticated Guest retains internal_user_pk and lawful history ownership. Login to an existing account never merges or transfers Guest assets/tasks/feedback/files. Validate ownership and transaction consistency throughout binding/switching. Username:3–32 ASCII letters/digits/underscore, normalized lowercase, database unique. Nickname is separate. No unverified email/phone recovery or self-service password reset; explain recovery limitations at registration.

## C. Password and login protection

Argon2id: memory19456KiB, time2, parallelism1, salt16 bytes, hash32 bytes; independent random salt, no plaintext or direct SHA256 password storage. Validate resource/concurrency/latency on target environment; never silently downgrade. NFC-normalize consistently, minimum15 Unicode characters, support at least64, no truncation or forced character categories. Reject common/known-compromised passwords; no risk-free periodic rotation requirement. Account+trusted-source rate controls: candidate5 failures/account/15min with progressive delay,30 attempts/source/15min limited, subject to local tests/load review; never trust client-supplied IP. Generic errors do not disclose username existence; no plaintext/full credential logging.

## D. Registered access and refresh

Access TTL15 minutes; refresh absolute14 days, idle7 days, never extend initial absolute bound. New access contains verifiable sid, auth_epoch and explicit token type. Protected requests verify signature/expiry/identity/session/account epoch; frontend v3_auth_epoch is only async isolation. Single logout revokes sid; all logout/password change advance server epoch and revoke refresh sessions. Refresh proof: CSPRNG >=256bits, database secure digest only. Successful refresh atomically rotates and consumes old proof; reused consumed proof revokes family, no double concurrent successor. Lost successful response requires reauthentication or separately reviewed recovery, no infinite old-proof retry. Database/revocation uncertainty fails issuance closed. Guest validation remains distinct and compatible.

## E. H5

Production HTTPS only. Registered refresh in HttpOnly+Secure+SameSite=Lax cookie, preferably `__Host-`,Path=/,no Domain. Registered access runtime memory only, no local/session/uni persistent storage. Refresh/logout/binding and cookie-authenticated mutations require server session-bound CSRF and Origin verification; SameSite alone is insufficient. Explicit approved HTTPS credentialed-CORS allowlist, no wildcard. CSRF is not a long-lived authentication credential. Missing verified origin/cookie/CSRF deployment keeps registered H5 login/refresh disabled; no persistent bearer fallback. Existing Guest storage requires separate compatibility/security remediation before claiming all H5 auth acceptance.

## F. Android

Verified uni-app/Android-compatible Keystore-backed encrypted refresh storage; no plaintext ordinary storage/log/backup/project-file fallback. Access preferably memory. Logout clears local proof and requests server revocation. Backup/restore/reinstall/unavailable Keystore fail safely. Plugin documentation alone is not acceptance. Abstract adapters/fakes/integration allowed without a device; actual Android security acceptance remains NOT RUN.

## G–H. Engineering and delivery boundaries

Reuse merged0011 auth persistence, no duplicate tables/migrations or historical checksum edits. New structures use controlled paired migrations and tests. Cover old Guest vs registered validation, concurrent refresh/revocation/switch/bind conflicts/password/rollback deterministically. SQLite/Fake is not MySQL/Android evidence. Do not enable unaccepted registration/refresh routes. Do not change learning/medical authority. No merge/base push/production migration/release/Live Flag authorization. Preserve earlier Draft history, proceed autonomously within approved scope, keep unavailable production origin/device/storage dependencies fail-closed and record them in acceptance matrix. Local endpoints alone do not complete account acceptance. Do not interrupt ongoing0013/Feedback/CI; schedule account work by actual dependencies.
