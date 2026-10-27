# Owner approval: Player return from feedback

Owner explicitly approved changing the two `goFeedback` calls from `dispose()` to `handleHide()` and separately approved the exact normalized source SHA update. The previous decision and hash remain in `OWNER_APPROVAL_20261027_SOURCE_SHA_REVISION.md`.

| File | Previous SHA-256 (UTF-8/LF) | Approved new SHA-256 (UTF-8/LF) |
|---|---|---|
| frontend/pages/v3-player/v3-player.vue | 0e98d0af3f774927aa4672e0c1e0e3199836bde538edc3cc965ba37c5648c087 | 6b1e532e937199ec9c7683ec3b13344cdabcf69d8935c3cdb550f00a9e101700 |

Only these two calls changed in the protected page. Profile and the original manifest, 113 assets and all other protected-source checks remain unchanged. No release, merge or Live Flag is approved by this decision.
