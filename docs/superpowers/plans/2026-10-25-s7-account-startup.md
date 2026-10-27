# S7 account transport and startup integration

Execute inline with executing-plans/TDD; baseline62157935a43753f4463eaf09cb5901be32ced456. Authority: Owner Account Security R1 record and latest Owner instruction; V1.1/PD001 remain binding.

- [ ] RED/GREEN: existing identity runtime preserves original Guest credential while binding is unresolved, authorizes recovery only after actual server Guest verification, and prevents startup/new Guest issuance from overtaking restoration. Same-owner binding retains history; login never imports Guest data.
- [ ] Add gated native HTTPS account transport around existing client, stable runtime/configuration seam and App startup hook. Default unavailable; no H5 cookie approximation, no Keystore plugin/storage fallback, no public account route or flag activation.
- [ ] Reuse original-Guard stdio journey launcher for a fixed account scenario and actual existing router/service/JWT/formal SQLite. Cover bind success/conflict, restart, duplicate refresh, revocation/expiry, lost response, logout, identity switch and data isolation. Use explicit test-only router mounting/secure-store substitute, never advertise platform acceptance.
- [ ] One independent read-only review, fix significant findings once with RED/GREEN, affected regressions/H5/Hosted CI; update Draft174 and a user-facing enablement blocker checklist.

Ruling: H5 remains unavailable because production HTTPS Origin/CSRF/cookie configuration is not supplied. Android transport requires explicit reviewed dependency acceptance including redirect refusal and Keystore atomic proof consumption. Boolean test capabilities are not device evidence. No security parameter, medical/generation rule, historical migration, Guard, sharing/source/learning policy change.

Review focus: unknown binding/refresh outcomes and app death; late A→B→A responses; credentials in ordinary storage/logs; app startup racing Home; native redirect/header and H5 bypass; fail-closed unavailable platform behavior.
