# Sprint 7 V1.1 product progress — 2026-10-25

Owner explicitly replaced report/demo priorities with normal W0–W8 execution on2026-10-25. Complete V1.1 source SHA256:bccfce90414bdde3518c270a3ae09ee8bbe3d91b54243b409ccce77ac08f7c69. Original2026-10-12 frozen scope and later explicit approvals remain the product authority; this progress file does not change them.

## W0 baseline

Started from0ab274e in an existing clean own isolated worktree; branch codex/s7-v11-product-continuity-20261025. Team Base9a6d472; PR173 depends on171,164 remains independent Draft,170 merged. No automatic integration. No report package or separate Demo build.

## W1: PD001 / U01,U08,U10

User journey delta: Home verifies an existing credential with the server before creating a new assessment session. Returning Home no longer deliberately mints another Guest. Restart uses the same stored Guest token, without renewal or extending expiry. Registered credentials are not overwritten by Guest initialization. Invalid/network-failed verification retains recoverable credentials and refuses to continue; it never silently abandons an owner. A public owner label alone cannot authenticate.

Read-only GET/auth/identity reuses existing server principal validation, returns public identity/type only, no-store/Vary Authorization, no token issuance/row creation. New-registration/Refresh routes remain closed. New sessions and late page continuations verify the originating authentication instance.

Evidence: frontend initial RED9f→GREEN9p; independent whole-W1 review found a session-settlement microtask race, additional RED9p/1f→GREEN10p. Fixed frontend specialty106p. Backend identity/Guest/registered/keyring regression144p. Final full frontend574p/7f/0skip; fixed account+identity74p; original7 material/evidence failures retained. No Guard relaxation, actual Provider or production DB.

Layer: OFFLINE_VERIFIED. NOT RUN: actual frontend-to-backend platform integration, Android, MySQL/TLS, production HTTPS. W1 integration/device end gates remain open. Expired/lost Guest cannot be silently recovered or replaced; explicit recovery/restart UI remains part of account/data integration. No claim of perpetual Guest recovery or single-session revocation for old Guest.

## Frozen scope ledger

| PD | Current product state / remaining work |
|---|---|
|001|W1 offline candidate; account UI/platform acceptance incomplete|
|002|No self/other or patient profiles; preserve|
|003|Subject/negation safety review154 open|
|004|My five regions incomplete; remove global feedback navigation|
|005|Single Player exists; title/favorite/share controls incomplete|
|006|Backend title/CAS exists; user entry/cross-page consistency incomplete|
|007|Backend history exists; default UI still preview|
|008|Same Player candidate exists; navigation/integration gate closed|
|009|R1 backend exists; generated and historical per-song UI incomplete|
|010|Learning OFF; status/clear product integration incomplete|
|011|No free tone/instrument recipe UI; preserve|
|012|Main-instrument illustration not connected; approved material gap|
|013|Original-image linkage/access/policy gate open|
|014|No patient grouping; preserve|
|015|No duplicate original-image Player block; list source entry incomplete|
|016|Single-song anonymous sharing remains in full scope; permission/contract gate open|
|017|Multiple candidates deferred by Owner, do not implement|
|018|Brand rename deferred by Owner, do not implement|
|019|Explanation depth requires approved guideline; preserve stored authority|
|020|Medical audit only; no algorithm/rule changes authorized|

Next: W2 existing library→single Player/title/favorite path with explicit isolated integration configuration, no permanent Live Flag activation. Preserve existing schemas/state/controllers. Every stage records default-path reachability separately from injected/offline/platform evidence.

## W2 — existing history to the single Player

Library navigation and historical Player now share the existing central gate (still false). Returning to My starts a new read even if an earlier read remains pending; stale results cannot overwrite the returned view. No new Player, write request, or flag activation.

Evidence: navigation RED2f→GREEN; independent review found the pending-read return race, RED1f→GREEN17 profile tests. Fixed frontend specialty114p. Full frontend577p/7f/0skip; unchanged Guard. Seven pre-existing material/evidence failures remain visible. Seek test harness now supplies the imported disabled gate and is included in the specialty.

Layer: WIRED_BUT_DISABLED / OFFLINE_VERIFIED under controlled test configuration. Actual backend/platform integration, Android and default live user path NOT RUN. Remaining Player controls and primary-instrument illustration are W3, not completed by this milestone.

## Unchanged boundaries

No merge/base or main push, force push, deployment, public account activation, paid Provider, real MySQL instance or Android installation. Original Guard unchanged. Learning OFF; source retention/share/consent policy/medical approval gates stay closed. init_database can automatically apply0013/0014 even when an account router is unregistered: no deployment or existing-database startup is authorized. Known full backend5 collection errors and frontend7 material/evidence gaps remain unresolved, not hidden by specialty CI.
