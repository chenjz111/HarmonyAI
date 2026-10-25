# S6 asset restoration and S7 primary-instrument illustration

Owner decision:2026-10-25, supersedes the earlier abbreviated recovery instruction. Reuse S6 assets/pages; S7 central illustration follows verified persisted primary instrument, background remains the S6 tone theme. No generation/medical/Provider/Live Flag change.

## Provenance and exact restoration

Source:[codex/s6-player-seek-final@4d935bb88475560617b2a6014192012407f78e9c](https://github.com/chenjz111/HarmonyAI/tree/4d935bb88475560617b2a6014192012407f78e9c). No merge/cherry-pick/page checkout. Asset history includes33ed464 (accepted visual integration), d8b87e4 (visual checkpoint),9a0b2fa (demo audio). Approval evidence: source `v31-home/ASSETS.md`, `v31-document/README.md`, current S6 contract/requirements matrix, and this explicit Owner instruction.

[Full file manifest](S6_ASSET_RESTORE_MANIFEST_20261025.json):113 exact original blobs,38,013,477 bytes; per-path Git Blob SHA1, SHA256, size and image dimensions/audio metadata. Restored109 static files plus the three canonical Owner reference PNGs whose SHA256 already appears in the frozen S6 contract, and their historical approved plan. That plan is evidence only, not an instruction to redo S6. No Sprint7 page/source was replaced. `.gitattributes` preserves restored artifact bytes across Windows/Linux.32 protected page/rule/Provider sources remain unchanged (LF-normalized source hashes).

| Static directory | Restored files |
|---|---:|
|music|1|
|v31-basis|7|
|v31-document|5|
|v31-feedback|17|
|v31-goal|6|
|v31-home|7|
|v31-material|2|
|v31-player|10|
|v31-questionnaire|50|
|v31-supplement|4|

Excluded `v31-home/home-icons-v1.png` (source Blob f1581adcf32b3f4995ca65bb3504f1db4979db74): explicitly rejected baked-checkerboard draft. Runtime uses v2. The restored60.881632653s WAV remains an explicit mock/test fixture; never a real-generation fallback.

## Independent instrument and tone semantics

| Legacy tone filename | Frozen background | Actual central image contents | S7 central lookup |
|---|---|---|---|
|gong|gong-1.png|gong-2.png: guqin|guqin only|
|jue (backend tone jiao)|jue-1.png|jue-2.png: sheng|sheng only|
|shang|shang-1.png|shang-2.png: bamboo flute|dizi only|
|yu|yu-1.png|yu-2.png: panpipes|No invented canonical mapping; never xiao/dongxiao|
|zhi|zhi-1.png|zhi-2.png: pipa|pipa only|

`music-presentation` accepts existing Provider canonical vocabulary only when `primary_instrument_origin` is persisted or unambiguous legacy_single. No tone/label/argmax inference. Only guqin/sheng/dizi/pipa have confirmed art. xun/xiao/guzheng/erhu/bianzhong remain neutral; missing/unknown/untrusted fields are neutral. Yangqin was stale frontend vocabulary and is now rejected, not a requested new asset. All Player Vue layout, circular dimensions, animations, controller, explanation and S7 controls are unchanged.

## Coverage audit — distinct authorities

- Approved `knowledge/v3/music-generation-rules-v3.1.json`: default guqin; emotion_regulation guqin+pipa; energy dizi; stress_relief guqin+xun. No active rule evidence for guzheng/erhu/yangqin. File/checksum unchanged.
- `music_provider.py`: canonical guqin/xiao/pipa/dizi/xun/guzheng/erhu/sheng/bianzhong. Capability/normalization support does not mean the approved rules select all nine. No code/prompt change.
- Existing library DTO exposes dizi/guqin/guzheng/sheng/xiao/pipa/unknown. Its legacy single-instrument projection lacks some Provider aliases/codes (including xun/erhu/bianzhong); multi-instrument lists intentionally cannot establish one primary instrument. This read-model limitation is reported, not repaired by guessing in the UI or altering generation rules.
- No real historical-user database inspected: actual historical distribution/primary provenance NOT RUN. Tests use controlled persisted-style metadata; no claims about real inventory.
- Missing confirmed art: xun is a genuine active-rule candidate; xiao/guzheng/erhu/bianzhong are Provider-supported but not shown to be active in this rule asset. Neutral fallback remains valid. No yangqin or panpipes asset request is made.

## Visual inspection and Owner decisions

Viewed all ten actual Player images together. Five `*-1.png` backgrounds show landscape/water/vegetation; no fixed instrument contradiction was identified. Example gong+dizi keeps gong-1 landscape with shang-2 bamboo flute; non-gong+dizi still uses bamboo flute. Do not change background selection to instrument selection.

Existing image-quality issue: gong-2 is RGB1254×1254 with baked checkerboard outside its circular illustration; it is not transparent. The unchanged circular UI may retain a rim of that pattern. This is a legacy central-image artifact, not an instrument conflict in the landscape. No repaint/crop/zoom applied. Owner options: retain exact original; approve guqin-only centered CSS enlargement/circular masking inside the unchanged outer disc; or provide an approved transparent derivative with original provenance preserved. Pixel quality/crop on actual devices remains NOT RUN. yu/zhi backgrounds retain original349px widths; no unapproved upscaling or regeneration.

## Verification

Resource/mapping RED7f→GREEN. Frontend specialty168p; full638p/0f/0skip, including all seven former missing-resource/evidence failures. All literal runtime/Tab paths and every actual Q1–Q10 dynamic option resolve. All PNGs decoded/verified during inventory preparation; restored blobs and build-bundle bytes are checked independently. No test assertions were deleted; the previous dizi-neutral expectation was explicitly updated for this new Owner-approved art.

Trusted launcher44p, H5 parent-audit9p and original guarded probes24p passed via their proper separate entry points. One earlier broad unittest discovery incorrectly included the Guard-only probe module and was rejected by its existing safety check; no probe/Guard was changed to bypass that rejection.

H5 uses a compiler-only adapter while the original offline Node Guard stays byte-identical. The existing pinned esbuild service is the only permitted child process; optional Windows Rollup report-header and Vite network-drive discovery are still blocked, never executed. Exact blocked-probe audit distinguishes them from any unknown denial, which still fails acceptance. Independent review found arbitrary spawn-options forwarding; safe RED reproduced it without executing a shell, then the service predicate/options were narrowed and fixed options reconstructed with shell:false. Compiler selftests cover shell overrides and unknown commands/network; parent audit tests cover forged/duplicate/unclassified events.

Final local H5:compiler0, index generated,109/109 static SHA256 matched,0 unresolved resource warnings, original Node Guard and questionnaire manifest unchanged. Original Guard selftests5p, compiler refusal selftests9p, parent audit9p. Both Windows discovery probes remain blocked and explicitly audited; unknown denials fail the build. Hosted CI runs full frontend and this exact H5 verification on Windows/Linux; its exact commit/run result is recorded in the PR and persistent task state. Android/device UI, real audio, MySQL/HTTPS and complete Sprint7 acceptance remain NOT RUN; no deployment, Merge, paid Provider, production migration or Live Flag activation.

Hosted run40175930951: Linux passed; Windows compiler0/109 assets passed but strict audit correctly rejected an extra blocked execFileSync. The dependency os-locale-s-fix probes WMIC when LC_ALL/LANG are absent. Added RED2→GREEN9 environment/audit tests and pinned only the compiler child locale to C.UTF-8, without allowing WMIC or relaxing denial classification. Reproduction with all host locale variables removed: H5 PASSED,109 hashes,0 unresolved warnings, only the two expected still-blocked probes. Follow-up Hosted result is tracked on the PR/current task state.
