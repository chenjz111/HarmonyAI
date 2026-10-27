# Sprint 7 V1.1 product continuity

> Execute inline with executing-plans and TDD. Owner explicitly authorized continuous W0–W8 work on 2026-10-25, replacing report/demo priorities. No additional design approval for frozen behavior.

Goal: restore the user's identity before starting a new assessment, then connect the existing private library and single Player. Reuse PR171/173; do not rebuild auth, library, state or playback.

Spec: Owner Freeze V1.0 (2026-10-12), PD001–020; Owner Autonomy Contract V1.1 (2026-10-25); approved Feedback/Clear and Account Security R1. V1.1 was read from the complete local download with a .crdownload suffix; no source document was modified.

## Baseline and limits

- Start: 0ab274efbfb3afd3c1f64e2c5f4dae7299a7386f; own isolated linked worktree, clean, no stash. New own branch codex/s7-v11-product-continuity-20261025.
- PR173 depends on171; both Draft. No merge/base push/history rewrite. Preserve S6/other worktrees.
- Original Guard unchanged. Synthetic isolated SQLite/Fake only; no paid Provider, production DB, live flags, public account activation, Android installation or real MySQL instance without separate authorization.
- init_database can apply0013/0014 even with account router disabled; no deployment.
- Known prior gaps: frontend564p/7f; backend5 collection errors; real MySQL/Android/HTTPS NOT RUN; medical154/retention/share/policy gates remain open.

## Task 1: W1 identity continuity — PD001, U01/U08/U10

- [x] RED: actual entry + API facade with synthetic platform transport: valid persisted Guest reused across home/restart; fresh assessment creates a new session only; expired/network failure never silently replaces owner; concurrent startup coalesces; late identity/session response cannot overwrite switched authority.
- [x] Add authenticated read-only identity projection using existing get_current_v3_principal. No token renewal, no patient inference or registered issuance.
- [x] Implement ensureIdentity in existing facade, validate on server, keep Guest four-claim compatibility. Entry uses ensureIdentity. Never trust public_user_id as authority, never extend token.
- [x] GREEN: frontend behavior + original Guard, backend HTTP identity/Guest/registered tests and relevant regressions. Record layer honestly; device remains NOT RUN.
- [x] Commit abcba90; W2 committed5c53f83. W3 offline candidate complete; platform gates remain open. Current full-scope task ledger remains external for resumability.

## Remaining product stages

W2: real history/favorites → same Player, title/favorite consistency, no create/provider calls; isolated integration configuration only, live flags unchanged.
W3: visible title/favorite/disabled-share controls and persisted primary-instrument illustration; approved assets or neutral fallback, no spec changes.
W4: five My regions, per-song feedback for generated/history playback, remove global feedback navigation; consent false/learning OFF.
W5: account UI and runtime auth bridge, no real platform activation.
W6: persisted historical explanation; source candidate and unavailable states until retention approval.
W7: nonpublic share/preference candidates and medical read-only evidence only; policy/permission gates cannot be assumed.
W8: cross-module/CI acceptance matrix; actual device/MySQL/HTTPS need separate permission. No S7_COMPLETE claim.

## Review focus

W5 implementation ruling: reuse the existing registered-auth client and verified secure-store gate. A runtime coordinator owns no credentials: it bridges that client's memory reader to both existing transports, advances the frontend epoch and clears assessment/private projections on transitions. Registered selection must never fall back to a stale Guest token after expiry/restart/failure. Only nonsecret mode/owner/epoch markers persist. Binding uses the captured existing Guest bearer; login never merges assets. Default coordinator remains unavailable until accepted platform dependencies exist; candidate UI must state this. No native plugin installation, account route registration, or H5 credential fallback is authorized by this plan.

Token expiry/server identity vs client labels; asynchronous A→B→A; failed startup retaining recoverable authority; default page controls vs fixture-only tests; no silent new owner after network failure; no paid operation on re-entry. One independent whole-branch review after the product work package.
