# Sprint 5 Owner Final Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the Owner-controlled Provider decision and an evidence-based Sprint 5 integration/acceptance checkpoint without changing the frozen V3.1 contract or claiming unfinished real-mode work as complete.

**Architecture:** Keep governance outputs under `docs/sprint5/`. Provider choices are configuration-level decisions behind existing interfaces; implementation remains assigned to AI and Backend closeout issues. The checkpoint consumes GitHub PR/CI facts and frozen repository authorities and records blocked gates honestly.

**Tech Stack:** Markdown governance records, Git/GitHub CLI, existing Python/Vue test commands only where relevant.

**Spec:** GitHub Issue #107 and `docs/sprint5/s5-v3.1-integration-gate.md`

## Global Constraints

- Base is `V3.1_FREEZE_BASELINE=83fe2f42069e126dbbfdccc252266964a58ce895`.
- Do not modify frozen flow, questionnaire, executable schema, business code, API, or database schema.
- Mock/fallback must never be reported as real provider success.
- Do not merge implementation PRs #102–#105.
- Provider credentials remain environment-only and must never enter repository files or logs.

---

### Task 1: Freeze the Owner Provider Decision

**Files:**
- Create: `docs/sprint5/s5-v3.1-provider-decision-final.md`

**Interfaces:**
- Consumes: existing Qwen-compatible LLM boundary, Chroma boundary, PaddleOCR adapter, MusicGenerationProvider protocol.
- Produces: approved provider/model/config/fallback policy for Issues #109 and #110.

- [ ] Record every provider capability, selected implementation, configuration names, fallback, and acceptance evidence.
- [ ] State that ASR is out of the V3.1 primary-flow scope.
- [ ] Separate `APPROVED_FOR_IMPLEMENTATION` from `REAL_VALIDATED`.

### Task 2: Record the Owner Integration Checkpoint

**Files:**
- Create: `docs/sprint5/s5-v3.1-owner-integration-checkpoint.md`

**Interfaces:**
- Consumes: PR #102–#105 status/CI, Issues #108–#111, frozen contract authorities.
- Produces: dependency order, merge gates, E2E matrix, Android status, and explicit blockers.

- [ ] Record exact base commit and PR states.
- [ ] Map Medical → AI/Backend → Frontend → Real E2E dependencies.
- [ ] Keep all unexecuted real provider, H5, Android, and asset gates blocked/not run.

### Task 3: Verify Governance Scope

**Files:**
- Verify: both new documents and repository diff.

- [ ] Confirm no frozen authority or business file changed.
- [ ] Confirm provider decision contains no credentials.
- [ ] Confirm PR #102–#105 remain open and unmerged.
- [ ] Run `git diff --check`.

### Task 4: Publish Owner Governance PR

**Files:**
- Commit only the plan and two Owner governance documents.

- [ ] Create one exact-scope commit.
- [ ] Push `docs/s5-final-owner-closeout`.
- [ ] Create a Draft PR against `integration/sprint4-real-input`.
- [ ] Post the current completion/blocker report to Issue #107.
