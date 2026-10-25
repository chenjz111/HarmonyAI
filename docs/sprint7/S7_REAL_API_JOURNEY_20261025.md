# S7 isolated page/API journey — 2026-10-25

Baseline `0cd9811c7ffe24773c5cb6e7d6242541932a1eb9`; own linked worktree/branch unchanged. Owner accepted the preceding asset batch as offline engineering only and requested real integration next. Sharing implementation is now paused pending teacher/Owner discussion; PD016 and its disabled entry remain. Original-image access and long-term preference gates remain closed. Guqin checkerboard/device visuals are deferred unchanged.

## What advanced

Existing frontend modules and actual My/Player/Feedback Vue **script methods** now execute against the real registered FastAPI app, real Guest JWT verification and formally initialized new SQLite with foreign keys ON. A fixed parent relays JSON through stdio between original-Guard-protected Node/Python children; there is no response fixture, listening app server, external connection, Provider or production database. Only database resource dependency is overridden, never the principal/auth dependency.

| User action | Observed integration result | Limit |
|---|---|---|
|Enter as Guest, return with credential, create assessment session|Real issuance, identity verification and session creation; existing token retained|Not next-day/OS restart/device storage acceptance|
|Open My history/favorites|Actual page methods load owned completed/unplayed music; independent lists agree|Isolated flag injection; default remains preview|
|Rename, stale rename, favorite/unfavorite, switch tabs|Real title CAS conflict; both lists show same private title/favorite; page methods persist mutations|No rendered browser clicks|
|Open historical music|Actual My navigation targets existing single Player; actual Player script loads persisted detail/context|No new generation; original3 task/1 asset inventory retained|
|Play/pause/Seek|Actual authorized download yields test WAV bytes; Range206 reads32 bytes; controller creates one audio context and reports exact onPlay proof|Native audio is a substitute; no real decode/playback acceptance|
|Feedback from Player|Actual handoff consumed by actual Feedback page; save/list/detail/Delete/Clear execute real routes/transactions|Learning false; no preference activation|
|Replay, Clear, delete|Same feedback ID on replay; Clear retains history and receipt; tombstone blocks replay|Synthetic data only|
|Guest A→Guest B→A|Backend denies B's private detail; actual My hides A before rendering and restores A's title after switching back|Not registered bind/login; platform account security not accepted|
|Network failure/retry|Platform request failure produces actual My error state, retains credential, real API retry recovers|Injected disconnection, not physical network interruption|
|Account entry|Actual default main app login path returns404; My accountAvailable false|Registered platform integration remains unfinished|

## Evidence and scope

`tools/ci/run_journey.py --evidence-dir <fresh directory outside source>` is reproducible on Node24/Python3.12. Local final evidence: `C:/Users/ASUS/HarmonyAI-s7-m1-evidence-20261024/journey-integration-reviewed-final/{result.json,telemetry.json,backend.log,frontend.log}`. Both application peers verified/exit0, no unexpected Python denial or Node denial. Fixed Hosted workflow now runs this after full frontend/H5 on both OSes; exact commit/run belongs in Draft174 and external state, not a future-looking pass claim.

Early runs exposed test setup/API-name/VM module-loading mistakes; corrected without business changes, assertions removed or Guard relaxation. Windows sandbox stalled inside stdlib socketpair before app requests; reviewed local execution under unchanged Guard passed. This is not a product-network failure or Guard bypass.

Independent review found a P2 in the new launcher: a stopped pipe reader could block a large response write beyond the main-loop deadline. Deterministic watchdog test RED→GREEN now kills a live non-reading child during an8MiB write, and the complete journey passed afterward. Minor deferred: the synthetic library row advertises MP3 while its test bytes are WAV; Range/auth transport is tested, codec/container/MIME compatibility is **NOT RUN**. No new decoder compatibility claim follows.

No business/source-page, asset, generation rule, medical authority, migration or original Guard change. The stage adds integrated evidence, not newly activated product capability. Default App: real facade, but library false→explicit fictional preview; historical/V3.1 path remains WIRED_BUT_DISABLED. Account router remains unregistered; H5 cookie/CSRF/startup bridge, Android secure storage and actual registered UX remain unfinished.

## Five full-backend collection failures — retained

Original raw evidence: `v11-w8-full-backend-collection/{pytest.log,telemetry.json}`, baseline4dd713f,2657 collected/5 errors/exit2. This stage does not modify these inputs or claim a fresh full-repository pass.

| Module | Original error | Classification / next safe action |
|---|---|---|
|tests/ai_engine/test_chroma_store.py|Could not determine home directory|Dependency import/environment; investigate isolated Chroma initialization, no real embedding call|
|tests/ai_engine/test_real_demos.py|Could not determine home directory|Same import blocker; later real-provider assumptions require separate review|
|tests/evals/test_emotion_presence_semantics.py|No module named evals|Missing evaluation source; locate original tracked source, do not invent a replacement|
|tests/knowledge/test_organ_mapping_eval_cases.py|No module named knowledge_organ_eval|Missing evaluation source; preserve medical/knowledge authority|
|tests/tools/test_stability_smoke_diagnostics.py|tools/stability_music_smoke.py absent|Missing tooling source; recover provenance before implementation|

Specialty CI success never replaces those failures. Medical independent approval remains separate. MySQL/TLS, actual HTTP/TLS/CORS/browser rendering, Android install/Keystore, physical audio/Seek, system reclaim and production HTTPS are **NOT RUN**. No merge, deployment, paid Provider, production migration or Live Flag activation.

## Next product dependency

Continue identity/account platform transport and startup integration in isolation under R1, with real server session validation; secure-store substitutes cannot establish Android acceptance. Then obtain explicitly authorized platform validation before proposing any default gate activation. Maintain original source/learning gates and paused sharing implementation; keep all20 frozen PD requirements on the ledger.
