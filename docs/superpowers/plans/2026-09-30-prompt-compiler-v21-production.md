# Prompt Compiler V2.1 Productionization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Productionize Owner-frozen Candidate D for the TokenHub and MiniMax provider dialects while preserving GenerationSpec authority, provider isolation, and zero network calls.

**Architecture:** Keep `GenerationSpec`, `CanonicalMusicPrompt`, and `CompiledPrompt` unchanged. Add a dialect-scoped V2.1 renderer in the existing production compiler: TokenHub and MiniMax emit Candidate D, while Stability retains its existing V2 text. Reuse the current audit identity and input checksum pipeline, changing only the compiler version and prompt checksum implied by the new provider text.

**Tech Stack:** Python 3, Pydantic v2, pytest, existing HarmonyAI V3 provider adapters.

**Spec:** `C:/Users/ASUS/.codex/attachments/d3b53ea5-a4d5-460d-b1cb-1061344a1086/已粘贴的文本.txt`

## Global Constraints

- Provider call budget is `0`; use deterministic local tests only.
- Do not modify GenerationSpec, tone-profile, medical mapping, threshold, Top-K, dominance, corpus, index, G3, or frontend manifest contracts.
- TokenHub and direct MiniMax use Candidate D; Stability behavior remains unchanged.
- Primary and secondary tones and their weights come only from authoritative fields; never infer, normalize, reorder, or argmax.
- Unknown V2.1 energy or ambience values fail closed with `UNMAPPED_PROVIDER_LANGUAGE_VALUE`.
- Do not render medical terms, `healing music`, or `instrumental only` in Candidate D.
- Keep full tone weights in the input checksum/audit data while omitting the full distribution from provider text.
- Bump only `prompt-compiler-v2.0-r1` to `prompt-compiler-v2.1-r1`.

## Review Focus

- Personalized profiles with missing secondary authority must not invent a supporting tone; production tests exercise the no-inference path.
- Unknown energy and ambience values must reject before adapter transport; compiler and adapter tests exercise the failure cause and zero calls.
- A no-ambience sentinel mixed with approved real ambience must ignore the sentinel and render only the approved ambience, matching the frozen evaluator.
- Integrated and basic profiles with weights must not leak full distributions or fake dominant tones; tests exercise both modes.
- Forbidden constraints must remain rendered and subject to medical-neutrality and provider-length guards; existing and updated tests exercise both.

---

### Task 1: Lock Candidate D Production Contract with RED Tests

**Files:**
- Modify: `tests/ai_engine/v3/test_prompt_compiler_v2.py`
- Modify: `tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py`
- Modify: `tests/ai_engine/v3/test_minimax_music_provider.py`
- Modify: `tests/ai_engine/v3/test_stability_music_provider.py`

**Interfaces:**
- Consumes: `compile_music_prompt(spec, dialect) -> CompiledPrompt` and adapter `create_task()` APIs.
- Produces: failing assertions for the exact V2.1 compiler text, authority, translations, error codes, dialect isolation, and version identity.

- [ ] **Step 1: Add Candidate D compiler tests**

Add structured assertions for all five primary tones, exact primary/secondary weights, frozen ordering, integrated/basic directions, omitted full distribution, deterministic output, provider caps, forbidden constraints, medical neutrality, and `prompt-compiler-v2.1-r1`.

- [ ] **Step 2: Add translation and fail-closed tests**

Parametrize all approved energy and ambience translations. Assert unknown values raise `MusicProviderFailureV3` whose `cause.reason_code` is `UNMAPPED_PROVIDER_LANGUAGE_VALUE`, and assert mixed no-ambience/real-ambience input renders only the approved real ambience.

- [ ] **Step 3: Add provider path and dialect isolation tests**

Assert TokenHub and direct MiniMax send Candidate D text and preserve the 2000-character cap without making real calls. Assert Stability still renders its existing V2 text with the 10000-character cap.

- [ ] **Step 4: Run focused tests and verify RED**

Run: `python -m pytest tests/ai_engine/v3/test_prompt_compiler_v2.py tests/ai_engine/v3/test_tokenhub_minimax_music_provider.py tests/ai_engine/v3/test_minimax_music_provider.py tests/ai_engine/v3/test_stability_music_provider.py -q`

Expected: Candidate D/version/translation tests fail because production still emits V2.0 text; existing provider tests remain locally deterministic.

### Task 2: Implement Dialect-Scoped Candidate D

**Files:**
- Modify: `backend/ai_engine/v3/prompt_compiler.py`

**Interfaces:**
- Consumes: unchanged GenerationSpec fields and existing instrument normalization.
- Produces: `CompiledPrompt` with Candidate D text for TokenHub/MiniMax, unchanged Stability V2 text, compiler version `prompt-compiler-v2.1-r1`, and existing four-field audit identity.

- [ ] **Step 1: Add fixed provider-language mappings**

Define frozen energy, ambience, no-ambience, mode-direction, and global-style constants. Map only approved values and raise `PromptCompilerContractError("UNMAPPED_PROVIDER_LANGUAGE_VALUE")` for unknown inputs.

- [ ] **Step 2: Add Candidate D fragments in frozen order**

Build fragments in the order action, primary, secondary, tempo, instruments, form, energy, atmosphere, global style, then existing forbidden constraints. Render weights as exact percentages by multiplying authoritative fractional weights by 100 without normalization or ranking.

- [ ] **Step 3: Preserve neutral modes and full authority**

Render the frozen integrated/basic direction strings without individual distribution values. Keep complete weights unchanged in `input_spec_checksum()` and avoid mutating the input spec.

- [ ] **Step 4: Scope routing to TokenHub/MiniMax and bump version**

Route `PromptDialect.TOKENHUB_MINIMAX` and `PromptDialect.MINIMAX` to Candidate D. Keep Stability on the existing canonical builder. Change only `PROMPT_COMPILER_VERSION` to `prompt-compiler-v2.1-r1`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Task 1 pytest command. Expected: all focused compiler/provider tests pass with no network calls.

### Task 3: Regression, Review, and Integration Gate

**Files:**
- Verify: backend and frontend Sprint 6 test surfaces
- Verify: `frontend/common/questionnaire-v3-manifest.js`

**Interfaces:**
- Consumes: the V2.1 compiler and unchanged Product Recovery contracts.
- Produces: reviewed PR, normal merge commit, and merged-base verification evidence.

- [ ] **Step 1: Run backend regressions**

Run the complete relevant V3 backend compiler, provider, generation, prescription, session, Player/read-model, and Product Recovery contract suites. Record exact pass counts and any authoritative environment-only skips.

- [ ] **Step 2: Run frontend regressions and H5 build**

Run the repository frontend suite and `node scripts/run-uni.mjs build`; do not invoke the manifest-generating wrapper.

- [ ] **Step 3: Verify repository protections**

Run `git diff --check`, verify the protected manifest hash remains `e98d1b3639ba546e542a51c3118ff4e0372c184a`, and confirm no audio artifact or provider call was created.

- [ ] **Step 4: Perform adversarial review**

Review the diff against every Owner question, fix material findings with a new RED test first, and repeat review if production behavior changes.

- [ ] **Step 5: Commit, PR, CI, normal merge, and merged-base gate**

Stage explicit paths only, create a focused commit, open a PR to `feat/s6-product-recovery`, wait for CI, mark ready, merge with a merge commit, and rerun the focused plus required merged-base gates on the new integration head.

- [ ] **Step 6: Prepare Owner Android checklist**

Document the final real-device flow and Candidate D observations without triggering real provider generation. End with `PROMPT_COMPILER_V21_PRODUCTIONIZED_AND_MERGED` and `OWNER_ANDROID_ACCEPTANCE_PENDING` only after every engineering gate passes.
