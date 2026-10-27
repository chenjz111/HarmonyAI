# S7 isolated user journey integration

> Execute inline with executing-plans and TDD. Baseline: 0cd9811c7ffe24773c5cb6e7d6242541932a1eb9.

Goal: replace response fixtures at the frontend/backend boundary with the actual registered FastAPI application, real Guest JWT validation and a newly created SQLite database. Exercise PD001/006/007/008/009 through existing frontend modules; explicitly distinguish this from a browser/device test.

Authority: Owner V1.1 contract and 2026-10-12 freeze on D:, subsequent Feedback/Account R1, and Owner's current instruction. Sharing implementation paused, PD016 retained. Original images and learning gates stay closed. No production database, loopback/external network, Provider, merge, deployment or Live Flag changes.

- [ ] Run the existing frontend facade, library transport/store, historical session and feedback client against actual ASGI responses through bounded stdio IPC. Both application children retain original offline Guards. The parent only relays protocol lines and launches fixed children. Use synthetic completed music rows and existing test WAV; do not claim generation or actual audio rendering.
- [ ] Follow Guest creation/reopen, successful-unplayed history, rename/conflict, favorite consistency, detail/stream Range, playback event, feedback replay/delete/Clear and second Guest isolation. Fix actual contract failures with observed RED/GREEN, preserve default-disabled behavior.
- [ ] Regress affected frontend/backend, run independent review once, record default reachability and five existing collection errors by category. Commit/push own branch and verify exact-HEAD Linux/Windows CI.

Review focus: credentials must never enter retained logs; IPC must not become arbitrary network/SQL access; child failure/timeouts must fail acceptance; actual authentication must not be overridden; no mock response or flag activation may masquerade as default App acceptance.

Ruling: stdio ASGI integration rather than a listening HTTP server — preserves original no-network Guards and exercises serialized real routes/DTO/auth/database. Cost: native HTTP/TLS/CORS, browser cookies, native audio and platform lifecycle remain NOT RUN.
