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
|001|W1 continuity + W5 gated account UI/runtime candidate; verified platform integration incomplete|
|002|No self/other or patient profiles; preserve|
|003|Subject/negation safety review154 open|
|004|W4 five visible regions and scoped music feedback navigation; account/preference functionality still gated|
|005|W3 visible safe title/favorite and disabled-share candidate; platform/layout acceptance incomplete|
|006|Private-title UI/CAS and W2/W3 return/read candidate exist; live platform consistency NOT RUN|
|007|Backend history exists; default UI still preview|
|008|Same Player candidate exists; navigation/integration gate closed|
|009|W4 generated/history per-song V3.1 candidate and scoped list/delete; default gate/platform acceptance incomplete|
|010|Learning OFF; status/clear product integration incomplete|
|011|No free tone/instrument recipe UI; preserve|
|012|W3 reads canonical primary-instrument metadata, neutral illustration fallback; approved material gap remains|
|013|W6 list source entry with honest unavailable state; original-image linkage/retention/access acceptance open|
|014|No patient grouping; preserve|
|015|No duplicate original-image Player block; list source entry incomplete|
|016|Single-song anonymous sharing remains in full scope; permission/contract gate open|
|017|Multiple candidates deferred by Owner, do not implement|
|018|Brand rename deferred by Owner, do not implement|
|019|Explanation depth requires approved guideline; preserve stored authority|
|020|Medical audit only; no algorithm/rule changes authorized|

Sequence: W1–W6 offline candidates are recorded below; W7/W8 retain policy/platform end gates. No permanent Live Flag activation. Preserve existing schemas/state/controllers; record default reachability separately from injected/offline/platform evidence.

## W2 — existing history to the single Player

Library navigation and historical Player now share the existing central gate (still false). Returning to My starts a new read even if an earlier read remains pending; stale results cannot overwrite the returned view. No new Player, write request, or flag activation.

Evidence: navigation RED2f→GREEN; independent review found the pending-read return race, RED1f→GREEN17 profile tests. Fixed frontend specialty114p. Full frontend577p/7f/0skip; unchanged Guard. Seven pre-existing material/evidence failures remain visible. Seek test harness now supplies the imported disabled gate and is included in the specialty.

Layer: WIRED_BUT_DISABLED / OFFLINE_VERIFIED under controlled test configuration. Actual backend/platform integration, Android and default live user path NOT RUN. Remaining Player controls and primary-instrument illustration are W3, not completed by this milestone.

## W3 — visible controls on the existing Player

Player displays the safe persisted default/private title, uses the existing favorite operation without naming, and shows disabled sharing. Favorite is below playback controls, share aligned right. Fresh generated music reads the current owned library card through the existing detail endpoint; history consumes its own card. No second Player or generation write. Central illustration no longer chooses its instrument from the tone. Approved art is absent: known canonical instrument or unknown both retain a neutral illustration, not a fabricated picture.

RED7f→GREEN7p; envelope regression RED→GREEN; independent review found whole-load identity exposure and optional metadata outage blocking playback. Review fixes RED→GREEN: identity is checked across metadata and basis awaits, auth events clear the controller/private view, non-auth metadata outage preserves existing audio but disables unverified favorites. Final specialty129p; full589p/7f/0skip, original Guard unchanged. Old S6 assertions requiring a hidden title/tone central image were versioned explicitly to Owner PD005/012; read-only/seek/explanation safety assertions retained.

H5 compiler exited0 and generated index.html in v11-w3-h5; manifest hash unchanged. This is not a clean build acceptance: missing approved static assets remain unresolved, and the existing build wrapper exited1 because Guard denied Rollup report-header spawnSync and Vite `net use` discovery. Neither process ran; no network allowed and Guard was not relaxed. The final small control-placement adjustment is covered by final specialty/full tests; H5 compiler snapshot predates that layout adjustment. Android/HTTPS/platform layout/audio acceptance NOT RUN.

Layer: OFFLINE_VERIFIED candidate; no whole-W3/device acceptance. Sharing remains a required full-S7 feature, policy/permission gated. Next W4: five My regions and per-song feedback scope; normal-generation V3.1 handoff and account bridge still incomplete.

## W4 — per-song feedback and five My regions

My now exposes history, favorites, preferences, account/data and about. Removed the independent top-level feedback entry; each music card opens its own scoped history. Preference region states learning OFF and favorite/evidence separation; account region explains Guest recovery limits and disabled binding. These explanatory regions do not constitute registered-account or preference activation.

Generated Player reuses the existing library playback session/proof helper only under the existing controlled gate. Its cached current task/session is matched to the server's selected context/session; mismatches close feedback without replacing context or invoking legacy feedback. One existing controller: load itself creates no play event; actual onPlay unlocks the explicit V3.1 handoff. Legacy default path retained with gate false. Both handoff form and history GET include music_id; unscoped history fails before reads. Clear still acts on all music for the current identity, explicitly stated in button and confirmation; history preserved, learning OFF.

Evidence: regions/scope RED4f→GREEN; generated proof RED2f→GREEN. Final frontend specialty135p; full595p/7f/0skip. Guard unchanged. Existing backend Feedback/receipt/migration specialty72p under original offline Guard. Independent W4 read-only review found no new P1/P2. H5 compiler snapshot v11-w4-h5 exited0/index generated/manifest unchanged; wrapper still failed on blocked local compiler discovery probes, and approved static assets remain missing. Actual default live library/registered UI, platform E2E, Android, MySQL/TLS and production HTTPS NOT RUN.

W4 layer: OFFLINE_VERIFIED / WIRED_BUT_DISABLED, not full product acceptance. No claim that disabled binding, inactive learning or seven existing frontend failures are complete. Next W5 runtime registered/Guest bridge and candidate account interaction; W6 historical stored explanation/source, W7 policy/medical, W8 CI and acceptance.

## W5 — registered credential bridge and candidate account interaction

One runtime coordinator reuses the existing registered-auth secure client; the legacy facade and library transport now read its memory bearer. Only mode/owner/UI-epoch markers persist; no registered Access/Refresh is written to ordinary storage. Expired/restarted/failed registered selection never falls back to a leftover Guest bearer or mints a new Guest. Bind captures the existing legitimate Guest credential; login sends no merge/import instructions. Same-owner refresh preserves the current assessment flow and advances UI isolation; unknown outcome removes local authority and proof.

My account region contains candidate bind/login and current/all-device logout controls, generic credential errors, password recovery limitation, NFC handling and explicit length validation without truncation. Default coordinator is unavailable: forms cannot send requests, account router remains unregistered, no verified Keystore or H5 Origin/CSRF/cookie deployment is assumed. The credential bridge has only been tested with explicit secure-store/platform substitutes. Automatic app startup restore/platform transport configuration, real UI/backend account E2E and actual device acceptance remain unfinished.

Evidence: initial runtime RED6f→GREEN7p; concurrent refresh/Guest overwrite/UI RED4f→GREEN; independent review found same-owner flow loss and UI-storage-blocked logout, both reproduced RED2f→GREEN. Secure logout now runs independently from fallible UI bookkeeping. Final specialty148p; full608p/7f/0skip, unchanged Node Guard. Backend fixed account74p. One initial test accidentally awaited an unanswered synthetic route; bounded replacement preserved the intended failing assertion before implementation; no false passing evidence used.

Hosted CI run40153170415 on777f214 failed identically on Linux/Windows: identity test assumed Vary was a scalar, hosted CORS added Origin. Fixed required Authorization membership while retaining no-store and forbidding wildcard; local74p. Guard24, regression195, hardening127, BE2B45, Feedback72 and five independent-process Feedback scenarios passed on that hosted run; later steps were skipped, not passed. Replacement hosted run still required after this commit.

W5 layer: OFFLINE_VERIFIED / WIRED_BUT_DISABLED. NOT RUN: real Keystore, Android, native account HTTPS integration, browser Origin/CSRF/cookie, target Argon2 resource/latency and reviewed production password-blocklist acceptance. No account-system completion claim. UI password input uses documented uni maxlength=-1 and rejects >1024 NFC characters consistently with existing server limits (https://zh.uniapp.dcloud.io/component/input.html); platform input acceptance still NOT RUN.

## W6 — original stored explanation and unavailable source entry

New read-only `/api/v3/music/assets/{music_id}/analysis?context_id=...` binds an owned terminal task/asset to the same owned prescription, diagnosis, session and exact confirmed assessment revision. It reads checksum-verified persisted public FiveToneAnalysis using the existing checksum/legacy projection sequence. Extracted that pure reader from the current reader: current generation still executes all existing current-input/relevance gates first. No medical rule, algorithm, schema checksum, old JSON or authority mutation. Frozen MusicDetailV1 remains unchanged.

Same historical Player loads only the explicit source's old explanation, never today's assessment/UserGoal. Optional explanation is independent of authorized audio controller readiness; slow/failing reads do not block music, identity/session/generation checks discard late results. User sees a loading/unavailable explanation state. Source picker shows ordinal labels rather than internal task IDs. History/favorites source entry explains original-image viewing is unavailable; no image endpoint, fake sample, retention extension or historical backfill.

Evidence: backend RED4f/1p→GREEN8p with existing endpoint; targeted diagnosis/library/proof regression101p; final fixed Feedback/history77p. Frontend initial scope RED2f; optional-latency RED1f→GREEN; final specialty152p; full612p/7f/0skip. Original Guards unchanged. Independent W6 review found no new P1/P2 and noted latency; the additional RED/GREEN addressed that observation. DML rejection during history GET verifies read-only behavior; old checksum/payload unchanged after current input changes. H5 compiler v11-w6-h5 exited0/index generated/manifest unchanged; wrapper remains failed on two blocked compiler discovery probes and missing approved assets, not clean acceptance.

Hosted CI on prior W5 HEAD98c2f961384794edc1bc429d557b0e436d4ffb64 completed SUCCESS (run40153829169). That success is not evidence for this unpushed W6 revision. Android/MySQL/TLS/production HTTPS/platform E2E and original-image retention policy remain NOT RUN/unapproved. W6 is an offline candidate; actual original-image product outcome remains incomplete.

## W7 — policy and independent medical boundaries

Read-only live #154/comment/PR156 verification located the actual original audit inputs at b1e7a50710d6e7fce4a7914cb953dcb961b695ad (not in this checkout). Reproduced their exact bytes against current code under the original Guard:38p/2f/0skip. Failures still occur in Conflict.fact_ids validation because fixture identities collide, before the comparable-time assertion. No temporal medical conclusion follows. Raw characterization observes subject admission/public-reason filtering and fact/link direction at synthetic seams; it does not prove clinical correctness or full upstream readiness. Original files were preserved in private local evidence, then temporary inputs removed from this checkout; no assertion/fixture/rule was changed or republished over PR156. Independent Two-Mode V2.1 sign-off chain remains open; Three-Mode V1 sign-off must not substitute for it.

Pending product contracts, not deleted scope:

| Capability | Concrete unresolved decision / preserved threat boundary |
|---|---|
|Original images PD013|Retention/deletion/backup policy and authorized source revision linkage; no endpoint/backfill/retention extension, unavailable UI only|
|Anonymous single-song sharing PD016|Audio licensing, grant lifetime/revocation authority and safe metadata; no public URL, token-in-URL or owner-wide stream capability|
|Soft preference PD010|Versioned active consent/listener/source eligibility and approved soft policy; true consent rejected, learning and new-generation consumption OFF; favorite never evidence|
|Medical PD003/020|R1/R2 fixture follow-up and independent adjudication; no rule, direction, coverage, mode or historical authority changes|

## W8 — continuity recovery and acceptance status

Expired/missing Guest authority now has an explicit, warned new-Guest action; cancellation, network failures, registered reauthentication and changed/hidden/unloaded page do not replace identity. Original Guest expiry is never extended and old server records are never deleted or imported. Independent review reproduced a response-after-hide/unload race: RED2f→GREEN after moving lifecycle validation into guest credential commit, before token/owner/flow changes. Initial recovery RED4f and lifecycle RED→GREEN; final specialty160p; full620p/7f/0skip, unchanged Guard. Existing Home onShow session-start assertion retained unchanged. Removed the unsupported Home claim that all data was used only for the current listening session; no new retention promise.

Final H5 compiler snapshot v11-w8-h5 exited0 with index generated and manifest unchanged; acceptance wrapper exited1 on the same two blocked compiler discovery probes. Approved static assets remain missing. Build/device acceptance is not green.

| Journey | Evidence now | Remaining actual product acceptance |
|---|---|---|
|U01 Guest/reopen|Server identity+actual page/facade offline behavior; explicit recovery|Default platform generation/restart E2E NOT RUN|
|U02 source/history|Immutable old-analysis HTTP+Player candidate; unavailable original entry|Actual original-image/revision access and retention approval missing|
|U03 generated-unplayed history|Existing backend list/proof regressions|Live default list/platform acceptance NOT RUN|
|U04 single Player|Controlled actual page/controller/navigation/favorite tests|Actual audio/Range/Seek/device E2E NOT RUN|
|U05 instrument art|Canonical instrument separated from tone; neutral missing art|Approved dizi/guqin etc artwork and device visual acceptance missing|
|U06 rename|Existing private-title CAS and return refresh/owned-card reads|Live cross-page platform operation NOT RUN|
|U07 feedback/delete/Clear|Backend transactions/process races; generated/history onPlay handoff and scoped UI|Default live gate remains closed; platform E2E NOT RUN|
|U08 binding/switching|R1 backend + secure fake client/runtime/UI isolation|Verified Keystore/transport/startup restore and app E2E missing|
|U09 sharing|Disabled control and retained product requirement|Licensing/grant contract, implementation and public acceptance blocked|
|U10 failures/reclaim|Offline stale/ABA/refresh-unknown/Guest lifecycle cases|Real OS reclaim/reinstall/audio/network recovery NOT RUN|
|U11 five My areas|All five reachable; truthful disabled/empty states|Actual account/preference functionality not enabled or accepted|
|U12 medical boundary|Original audit38p/2f; no inference/rule edits|Independent medical sign-off and full clinical-chain proof open|

Hosted CI succeeded on98c2f96 (run40153829169) and d413e3d (run40154442677); the final recovery revision still requires its own run. Fixed suites are not full-repository acceptance. Full frontend retains seven approved-material/evidence failures; full backend's existing five collection errors involve Chroma home discovery and absent evals/knowledge_organ_eval/tools/stability_music_smoke inputs, not a passing full suite. Do not fabricate missing source or bypass Guard. Approved artwork location was requested asynchronously; no reply yet.

Next actual work: verify the final Draft PR CI and update its evidence; with approved resources/contracts, perform isolated frontend/backend integration and real MySQL/TLS/Android/HTTPS acceptance, then finish currently gated source/sharing/preference product capabilities. No S7_COMPLETE or M1_GO claim.

## Unchanged boundaries

No merge/base or main push, force push, deployment, public account activation, paid Provider, real MySQL instance or Android installation. Original Guard unchanged. Learning OFF; source retention/share/consent policy/medical approval gates stay closed. init_database can automatically apply0013/0014 even when an account router is unregistered: no deployment or existing-database startup is authorized. All genuine unrun validations above remain NOT RUN.
