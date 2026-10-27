# Guest Music Library Acceptance Plan

**Goal:** Close evidenced Guest journey gaps and prepare the existing USB Android path for device acceptance without enabling production features.

**Architecture:** Reuse the existing My, Player and Feedback pages, actual FastAPI routes, scoped identity and approved development-only loopback switch. Exercise a truthful authorized audio fixture in isolated SQLite, then document the actual device workflow and remaining gates.

**Constraints:** Owner freeze and later R1 decisions; no paid Provider, production database, deployment, release flags, account security relaxation, source-image/learning/share policy change or second Player. Existing Player/Profile protected hashes remain enforced.

## Tasks

- [ ] Audit existing development flag, page flows, approved decisions and current CI; distinguish platform evidence from injected isolation.
- [ ] Reproduce integration fixture mismatch as a failing content/MIME/duration assertion; use the restored WAV with matching isolated database metadata and run the real-page ASGI journey.
- [ ] Investigate and minimally repair independently reviewed, reproducible user-flow gaps with RED/GREEN and original Guards.
- [ ] Run frontend full regression, backend relevant regression and ASGI journeys; document device steps, unresolved requirements and exact evidence.
- [ ] Request independent review, resolve evidenced findings, commit and update Draft PR; verify exact-head CI or record pending.
