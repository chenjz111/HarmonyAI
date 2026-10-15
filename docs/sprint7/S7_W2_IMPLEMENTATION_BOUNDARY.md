# S7 W2 implementation boundary

Authority: Owner W2 task dated 2026-10-14. Baseline: `58505288c7128ed5081a58d0dc6c1d088b68b6ac`.

This checkpoint freezes only the approved implementation subset. The four R2-A contracts remain drafts outside that subset.

## Shared contract

- MusicCardV1 retains the exact W1 schema, nullable measured duration, UTC times, and safe asset-date title. No extra DTO aliases.
- MusicDetailV1, PageV1, LibraryAudioV1 and playback events use R2-A technical contract sections 4.1–4.3. Detail reads only an explicitly selected, owner-verified persisted generation context. No latest-session fallback.
- Library authorization is direct owner or that owner's succeeded/matched_fallback task; NULL owner and favorite alone grant nothing. Context IDs never include another owner's tasks.
- OwnerMusicState is Backend-owned, not duplicated by Preference. `lock_owner_music_state` and `advance_feedback_epoch` participate in the caller's transaction and never commit independently.
- Cursor HMAC binds owner/list/version/epoch/sort boundary. No weak unsigned fallback if signing configuration is unavailable. Title CAS uses owner+asset metadata version. Real asset additions must invalidate library pagination; GET must not write or invent play events.
- FeedbackContext requires an owned playback event and an explicit legal task context. No inferred patient/listener relationship. V3.1 consent defaults false; server validates active policy; true never enables M1 learning.
- PF-1A independently closes legacy automatic writes, direct learner entry, replay applied claims, and new snapshot consumption. Historical profile/snapshot reads remain intact.
- PF-1B requires the single Backend owner/context/state implementation plus migration 0013; until available, no production delete/clear/consent endpoint is advertised.

## Migration allocation and current gates

0011: auth/session/credential fields, deferred until authentication dependencies and parameters are approved.

0012: Backend music_library_state, music_playback_events, owner_music_state; definitive SQL waits for the actual Backend model contract. GET is read-only; sidecars are created only on explicit writes. No new MusicAsset primary-instrument columns are needed for W2 read-only legacy projection.

0013: Preference consent/deleted_at/request_hash/context and epoch provenance fields; definitive SQL waits for the shared owner-state/context model. Legacy consent defaults false, all historical JSON/checksums remain immutable.

SQLite/MySQL pairs and up/down tests are Integration-owned. No DDL or fabricated placeholder migration is applied while model dependencies are unavailable. No production database access.

## Stream gate requiring explicit Owner approval

Current `generation_service._find_owned_asset` grants access for `owner=NULL`; `get_playable_asset_stream_path` checks stored ready/path only, without retention or the new library root/readability proof. The legacy `generation_router.stream_asset` uses that function.

Proposed minimum cross-module change, not implemented here:

1. Authorize changes to `backend/app/services/v3/generation_service.py::get_playable_asset_stream_path` (Backend) and relevant existing stream regression tests. Do not globally change `_find_owned_asset`, which has legacy generation/fallback consumers.
2. Delegate that stream entry to the single library access/availability authority after owner authorization; preserve 404 RESOURCE_NOT_FOUND versus RESOURCE_NOT_AVAILABLE and private FileResponse behavior. Every Range/retry request rechecks.
3. Decide explicitly whether previously unrestricted NULL-owner catalog streams must now require a successful owner task, or whether a separate narrowly scoped catalog entitlement is approved. No assumption of entitlement or public sharing.
4. Verify A/B/shared matched/no-task/expired/missing/unsafe path and legacy catalog scenarios with isolated files. Do not change Provider, generation rules, or public audio routes.

Until this decision and tests pass, no real historical Player audio integration or claim of complete library/stream consistency. BE-2B's end-to-end acceptance and dependent FE live enablement remain blocked; independent adapter/tests and PF-1A may proceed.

## Independent W2 work

Frontend: implement a transport-injected contract adapter and state tests; no real transport default, no second Player, historical navigation remains disabled until the Backend/stream Gate closes. Do not claim API integration from fixtures.

Preference: PF-1A writes and new-consumption disabled without changing Diagnosis/Prescription source files or medical algorithms. Preserve/version legacy auto-learning test evidence and historical snapshots. PF-1B remains dependent on 0012/0013 and owner/context interfaces.

Evidence: only isolated tests in `tests/sprint7_audit`; demonstrate counterfactual behavior, not medical truth. No core rules changed.

Account A: inspect installed security dependencies and benchmark only synthetic passwords. TTL/Argon2 parameters are candidates; Android/H5 adapters and deployment protections require evidence before enabling authentication. No network installation or unsafe fallback.
