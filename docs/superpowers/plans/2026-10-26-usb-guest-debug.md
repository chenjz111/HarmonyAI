# USB Guest Local Debug Plan

Goal: restore Sprint6 loopback + ADB reverse for synthetic Guest basics without changing release transport.
Owner specification: explicit chat instruction 2026-10-26; Sprint6 acceptance-runtime at origin/codex/s6-player-seek-final (4d935bb) is historical mechanism evidence, not permission to reuse its DB/keys/Provider config.
Existing isolated branch codex/s7-android-resource-build-20261025, baseline b6bda0e. Keep all existing dirty configuration/assets/signing caches.

- [x] Confirm historic 127.0.0.1:8010 + adb reverse; current authorized device already maps8000, phone curl health200. Do not alter8001.
- [x] RED: release and non-Android remain HTTPS-only; explicit development+USB flag+exact127.0.0.1:8000 allows Guest; all otherHTTP rejected; no Registered composition in USB mode.
- [x] Minimal changes api-origin.js/android-platform.js; isolated .env.development.local only. No new dependencies/plugins, no cloud build, no global SSL bypass.
- [x] GREEN existing Android regression and new boundary checks; production resource compile proves dev mode cannot be activated by environment flag alone.
- [x] HBuilder standard base run and actual native uni.request health/Guest/identity/session; Guest continuity on restart if same valid synthetic credential. Never discard existing unknown Guest automatically.
- [x] Record proven phone/network vs code-only results, default feature gates and remaining scope. No real Provider/DB or account activation.

Release acceptance still requires HTTPS/Keystore/TLS verification. Nonproduction backend remains restricted and loopback only. UI automation follows CUA; Owner performs phone prompts as necessary.
