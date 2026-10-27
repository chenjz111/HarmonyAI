# H5 account startup composition

Owner Account Security R1 already approves a same-origin HTTPS Cookie design, but requires the registered route to stay closed until deployment Origin, CSRF/Cookie and browser security acceptance. The existing candidate is exercised through direct test injection and is not installed by App startup. Make that startup connection explicitly configurable in code while keeping the default unavailable.

1. RED: exercise H5 bootstrap with absent approval, wrong target, mismatched/non-HTTPS origins, missing browser dependencies, failed installation, repeat initialization and backend switch. Existing Guest storage must survive every refusal.
2. Implement a small H5-specific composition seam which uses the existing browser client and registered runtime, requiring explicit acceptance and an approved origin reference. No URL/storage-driven flag and no default approval. Install before existing App launch recovery; do not alter Android's composition.
3. GREEN: run the original Node Guard tests, an actual-ASGI Cookie journey through the new composition and App startup, full frontend regression and H5 compiler. Record device/browser/deployment boundaries; no platform acceptance from injected tests.
4. Review, commit own branch, update Draft PR only after verification. Preserve source-hash pins, approved R1, feature flags and Owner policy gates.
