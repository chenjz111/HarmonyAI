# HarmonyAI Sprint 6 — Rule Freeze Questions

> Status: **OPEN — awaiting human decisions**
> Phase: Sprint 6 Phase 0
> Only questions that genuinely require a human (Product Owner / Medical Owner / AI Owner
> sign-off) are listed. Nothing here may be resolved by reading code.
>
> Phase 0 deliberately fixes **no numeric thresholds**. Where a number is needed, this document
> states who must propose it and who must approve it.

---

## Q1 — May `integrated_regulation` carry balanced five-tone weights with **no** primary tone?

**Question.** When there is enough evidence but no clearly dominant organ, may the system present a
**balanced five-tone weight distribution with no single primary tone** (mode
`integrated_regulation`, user-facing 「综合调适」, `primary_tone = null`)?

**Context.** Today `primary_tone` is a required contract field
(`backend/app/schemas/v3/flow_v31.py` → `ToneProfileV31.primary_tone: ToneCode`), and the tone is
always resolved by argmax with a tuple-order tie-break (`agent3.build_tone_profile_v31`). With the
approved mapping a uniform organ profile makes `gong` and `shang` tie and the tie resolves to
`gong`. So the current contract **cannot express** "enough evidence, no dominant tone".

**Current Product Owner decision:** **YES** — balanced weights with no primary tone are allowed.

**Still required before implementation:**
- **Medical Owner review:** is presenting a balanced five-tone mix with no single primary tone
  medically acceptable, and what is the approved user-facing wording?
- Contract consequence: `primary_tone` must become nullable (or a mode-scoped union), and every
  consumer must handle the null case (see risk R10).

**Blocking:** Phase 1.

---

## Q2 — `basic_wellness` must not claim a single five-tone primary tone

**Question.** When evidence is insufficient (abstained / `EVIDENCE_INSUFFICIENT` / no organ reaches
the candidate threshold), must the system **avoid** asserting any single five-tone primary tone, and
instead present a non-personalized 「基础舒缓」 result with `primary_tone = null`?

**Context.** Today the fallback **fabricates** `primary_tone=gong` with weights
`{gong: 0.6, others: 0.1}` (`prescription_service._conservative_wellness_spec`). In the canonical
baseline, 15 of 15 `wellness` prescriptions are `gong`.

**Current Product Owner decision:** **YES** — no single primary tone may be claimed on insufficient
evidence.

**Still required before implementation:**
- **Medical Owner review of the wording.** What exactly may be said to the user for
  `basic_wellness`? Candidate vocabulary must avoid implying diagnosis/treatment and must not
  present a tone as a conclusion. (`knowledge/v3/five-tone-safe-expression-rules-v3.1.json`
  approves neutral words such as 调适/舒缓/放松; the exact phrasing still needs sign-off.)
- Confirmation that keeping the approved deterministic music parameters (bpm/duration/instruments)
  for a fallback is acceptable, since only the *tone claim* is being removed.

**Blocking:** Phase 1.

---

## Q3 — `flank_discomfort`: questionnaire wording vs claim definition conflict

**Question.** Which side changes, given that the two approved assets disagree?

| Asset | Current content |
|---|---|
| `knowledge/v3/claim-dictionary-v3.0.json` → `flank_discomfort` | display name 「胁肋胀闷不适」 (flank / hypochondriac distension) |
| `knowledge/v3/questionnaire-v3.0.1.json` → q06 option `flank_discomfort` | 「胸口附近有时会觉得闷闷的，想长舒一口气」 (chest-area tightness / wanting to sigh) |

**Why it matters.** This is the concrete mechanism behind "胸闷 → flank_discomfort". A user's
chest-tightness answer becomes a flank/liver claim, and any AI extraction reading the same
dictionary reproduces the same conflation. It affects **deterministic questionnaire facts** as well
as AI-extracted facts, so it cannot be fixed by prompting alone.

**Decision required from the Medical Owner — choose one:**
1. **Change the questionnaire wording** so the option text matches the flank/胁肋 meaning;
2. **Change the claim** definition/display name to the chest/胸闷 meaning;
3. **Add a new distinct claim** (e.g. a separate chest-tightness / 胸闷 claim) and re-point the
   questionnaire option;
4. **Add an explicit alias mapping** if the two are to be treated as one concept for medical
   reasons.

**Constraints on whichever option is chosen:**
- Either asset is checksum-pinned and covered by knowledge tests; changing it requires a version bump
  and checksum update plus Medical review.
- Phase 4 (Understanding grounding) must not be validated until this is decided.
- No asset may be edited before the decision is recorded.

**Blocking:** Rule Freeze → Phase 4.

---

## Q4 — Dominance / ambiguity thresholds

**Question.** What numeric rule decides that a profile has a **dominant** organ (→
`personalized_five_tone`) versus being **ambiguous / balanced** (→ `integrated_regulation`)?

**Phase 0 position:** **no number is fixed here.** Fixing one now would invent a medical rule.

**Proposal process required:**
1. **AI Owner** proposes candidate rule(s) — e.g. a top1-minus-top2 margin on organ weights and/or
   on tone weights, plus a minimum-support condition — and evaluates them against the frozen
   acceptance cases A–H (`sprint6-acceptance-cases.md`).
2. The proposal must show, on A–H, that:
   - A/B/C stay `personalized_five_tone` with the expected tone,
   - D becomes `integrated_regulation` with `primary_tone = null`,
   - E/G become `basic_wellness` with `primary_tone = null`,
   - F keeps its clear directional difference.
3. **Owner + Medical** review and freeze the rule. Any subsequent change requires a new review and
   a version bump of the rule asset / mapping version.

**Constraints:**
- The rule must be expressed as explicit, versioned configuration (rule asset), **not** as code
  tuple/iteration order.
- Changing the approved organ→tone numeric mapping is **out of scope** unless Q5 is triggered.

**Blocking:** Phase 1 implementation detail; Phase 2 supplies the questionnaire-side margin signal.

---

## Q5 — Organ→tone numeric mapping changes

**Question.** May the approved `organ_tone_weights` numeric values in
`knowledge/v3/five-tone-mapping-v3.0.json` be changed in Sprint 6?

**Phase 0 position:** **default NO.** Sprint 6 does not change the approved numeric mapping. The
`gong`/`shang` symmetry (raw sums 1.15 / 1.15 / 1.00 / 0.85 / 0.85) is treated as *approved medical
content*, and Sprint 6 addresses the resulting behaviour through the mode/ambiguity rule (Q1/Q4)
rather than by re-tuning the mapping.

**If a mapping change is later judged necessary:**
- Requires **Medical review** of the change, plus **Owner** approval.
- Requires a `mapping_version` bump **and** a `content_checksum` update, with the knowledge-asset
  checksum tests updated accordingly.
- Requires re-validating acceptance cases A–H and re-recording the baseline.
- The RAG corpus/chunk checksums and the Chroma runtime index may be affected; re-indexing is a
  separate, Owner-approved activity.

**Blocking:** only if triggered; otherwise no action.

---

## Decision log

| ID | Question | Current status | Awaiting |
|---|---|---|---|
| Q1 | `integrated_regulation` may have no primary tone | Product Owner: **YES** | Medical Owner review |
| Q2 | `basic_wellness` must not claim a single primary tone | Product Owner: **YES** | Medical Owner wording review |
| Q3 | `flank_discomfort` wording vs claim conflict | **OPEN** | Medical Owner: choose option 1–4 |
| Q4 | dominance / ambiguity thresholds | **OPEN — no number in Phase 0** | AI Owner proposal, then Owner + Medical review |
| Q5 | organ→tone numeric mapping change | Default **NO** | triggered only by explicit Medical + Owner decision |
