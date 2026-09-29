# Sprint 6 Product Recovery — Questionnaire RAG Medical Review Pack

Status: **MEDICAL / OWNER APPROVED OFFLINE PACK — NOT RUNTIME ACTIVE**
Approval authority: Owner's 2026-09-28 takeover authorization records MR-01–MR-13 and OD-01–OD-07. MR-06 correction below is required before G2. Proposed corpus additions remain **PROPOSED — NOT APPROVED — NOT ACTIVE**.
Scope: Phase G1 offline acceptance only. No runtime, corpus, index, provider, schema, migration, or frontend behavior is changed by this pack.

## 1. Current production authority snapshot

| Authority | Frozen repository value |
| --- | --- |
| Query policy | `rag-query-policy-v3.2-r1` / schema `3.2.0` |
| Policy checksum | `sha256:aabee0682d47b4c3f1ade3dd3531b8dd4ce98b1ee86d6c8f911b343c20d7b495` |
| Query builder | `diagnosis_query_v3.2` |
| Top-K | `5` |
| Distance | cosine |
| Source cosine threshold | `0.65` |
| Runtime normalized threshold | `0.740741` |
| Conversion | `normalized_similarity = 1 / (2 - cosine)` |
| Embedding | `text-embedding-v4@1024` |
| Corpus | `medical_v3.1-approved.1` |
| Approved corpus checksum | `sha256:fbf2207de75b963d316fc4bc54cb3e8e6c91f475d7766d4b27adec237101961a` |
| Ingestion manifest checksum | `sha256:4ffef480fd66d38cd8f3cecc96ccce4e1135869cdccbbf7b2162cbf9139a8f76` |
| Approved chunks | `13` |
| Questionnaire mapping | questionnaire 3.0.1 / sha256:69a01d...51031 → claim dictionary 3.0.0 / sha256:9a2093...f77b9 → organ mapping organ_mapping_v3.0 / sha256:771ca8...a495 |

`build_diagnosis_query` sorts all approved active claim and organ codes into one `RagQuery`. `VersionedRagStore._query_text` maps those codes to approved Chinese labels, makes one sentence, then appends `confirmed_state_text`. There is no explicit query truncation or token clipping in this path. Retrieval embeds the resulting single text, takes Top-K, converts cosine distance to normalized similarity, and filters below `0.740741` or non-approved metadata.

## 2. Root-cause hypothesis

The strongest G1 hypothesis is **query formulation plus corpus coverage**. A questionnaire-only state can combine many unrelated organ/domain labels and a full confirmed summary into one embedding query. One vector must represent all domains; focused evidence can be diluted below the preserved threshold. Separately, three current Q1–Q10 claims have no approved supporting chunk. The existing 13-chunk corpus is intentionally compact explanatory material, not complete questionnaire-domain coverage.

This is not evidence for lowering the threshold. The historical threshold benchmark shows that `0.65` cosine is required to keep `gq_14`, `gq_15`, and `gq_17` empty together. It is also not evidence of an embedding/index identity mismatch: the manifest binds model, dimension, corpus checksum, count, and collection identity and the runtime fails closed on drift.

Evidence strength: **HIGH** for coverage gaps and single-query construction; **MEDIUM** for semantic dilution as the direct cause of every production empty result until G2 is tested with an approved offline/live index run.

## 3. Current corpus coverage matrix

The machine-readable complete 32-claim matrix is in `knowledge/v3/questionnaire-rag-gold-profiles-v1.json`.

| Scope | DIRECT_SUPPORT | BOUNDARY_SUPPORT | UNSUPPORTED | Total |
| --- | ---: | ---: | ---: | ---: |
| Full approved claim dictionary | 13 | 10 | 9 | 32 |
| Current questionnaire Q1–Q10 claims | 12 | 9 | 3 | 24 |

Direct means an approved chunk explicitly supports the claim wording/domain. Boundary means approved background exists but does not directly state the claim. Unsupported means no current approved chunk may be presented as support.

| Questionnaire domain | Claims | Current support |
| --- | --- | --- |
| Five emotions | `anger_tendency`, `agitation_tendency`, `overthinking_tendency`, `sadness_tendency`, `fear_tendency` | direct for anger/overthinking/fear; boundary for agitation/sadness |
| Liver/body | `flank_discomfort`, `tendon_stiffness`, `muscle_cramp`, `eye_discomfort` | direct except `flank_discomfort` unsupported |
| Heart signals | three palpitation claims, `tongue_tip_discomfort` | boundary only |
| Appetite/digestion | `poor_appetite`, `postmeal_bloating`, `loose_stool`, `postmeal_heaviness` | direct for bloating/loose stool; poor appetite boundary; heaviness unsupported |
| Respiratory | `throat_cough`, `exertional_breathlessness`, `nasal_discomfort`, `voice_change` | throat/cough and exertional breathlessness boundary; nasal/voice direct |
| Kidney | `lower_back_knee_weakness`, `tinnitus`, `nocturia` | direct for weakness/tinnitus; nocturia unsupported |

The three specifically audited claims remain: `flank_discomfort` = **UNSUPPORTED**, `postmeal_heaviness` = **UNSUPPORTED**, `nocturia` = **UNSUPPORTED**.

## 4. Gold profile matrix

| Profile | Kind | Active claims | Expected |
| --- | --- | ---: | --- |
| `qrag_positive_anger_liver` | positive | 2 | approved liver/anger evidence |
| `qrag_positive_appetite_digestion` | positive | 3 | approved digestion evidence |
| `qrag_positive_respiratory` | positive | 4 | approved respiratory evidence |
| `qrag_positive_kidney` | positive + unsupported boundary | 3 | existing kidney evidence; no invented nocturia support |
| `qrag_mixed_10_claims` | post-G2 target positive | 10 | POSITIVE target pending G2; current combined-query fixture is EMPTY/DILUTED |
| `qrag_negative_unsupported_only` | negative | 3 | empty |
| `qrag_negative_gq14` | Gold no-answer | 0 | empty |
| `qrag_negative_gq15` | Gold no-answer | 0 | empty |
| `qrag_negative_gq17` | Gold no-answer | 0 | empty |
| `qrag_confirmed_edit_removes_anger` | authority regression | 1 active / 1 provenance-only | digestion only; no anger retrieval input |

All texts are synthetic labels created for this acceptance pack. No production/user session text is present.

## 5. Baseline/current-query observations

- The current builder creates one query identity from the full sorted set of claims/organs; the store creates one embedding text and one retrieval call.
- The confirmed summary is appended to that same text. There is no per-domain isolation, so mixed profiles have a credible dilution mechanism.
- Current approved chunks have deliberately empty `claim_codes` and `organ_codes`; matching is semantic, not a structured claim filter.
- The repository contains no provider-free measured similarity matrix for the new synthetic profiles. G1 therefore does **not** claim measured scores.
- `tests/fixtures/questionnaire-rag-similarity-v1.json` is an explicitly synthetic boundary fixture. Its values exercise the frozen threshold/filter contract and encode the review hypothesis, not live model output.
- Historical Owner matrix evidence remains authoritative for existing Gold queries: at cosine `0.65`, relevant recall was 15/18 and all three no-answer queries were empty. `gq_14` had irrelevant `src_10` cosine `0.6184`; `gq_17` had irrelevant `src_11` cosine `0.6343`; both must remain filtered.
- Current observed production symptom—distinct questionnaire states with distinct hashes but zero approved hits—is consistent with the combined-query dilution hypothesis, but G1 does not alter runtime or claim causal proof from simulated values.

The mixed profile has two separate acceptance concepts: Gold `expected_result: POSITIVE` is the `POST_G2_FOCUSED_RETRIEVAL_TARGET`, with `target_verification_status: PENDING_G2`. The existing all-below-threshold fixture is the `CURRENT_COMBINED_QUERY_BASELINE`, with `expected_baseline_result: EMPTY_DILUTED`. It does not satisfy the future target. No focused similarity scores are available or invented. Fixture `routine_provider_counts` records the provider-free offline pack contract (all seven counters zero), not runtime telemetry or evidence of a live evaluation.

## 6. Proposed focused query groups

These groups retain approved `organ-mapping-v3.0.json` mappings with the explicit MR-06 reviewed exception: `exertional_breathlessness` activates both `focus_lung` and `focus_kidney`. Primary provenance is lung; secondary provenance is kidney. It is BOUNDARY_SUPPORT in both, never direct evidence. Existing src 08/12 references are retained as boundary references; no new chunk is approved. Group status is **APPROVED_OFFLINE_NOT_ACTIVE**.

| Group | Approved mapping-derived claims | Existing approved support | Unsupported |
| --- | --- | --- | --- |
| `focus_liver` | anger, flank discomfort, tendon stiffness, muscle cramp, eye discomfort | src 01/02/03/12 | flank discomfort |
| `focus_heart` | agitation, three palpitation claims, tongue-tip discomfort | src 01/04/11 boundary/background | none classified unsupported; several boundary-only |
| `focus_spleen` | overthinking, poor appetite, postmeal bloating, loose stool, postmeal heaviness | src 01/04/09/11 | postmeal heaviness |
| `focus_lung` | sadness, throat/cough, breathlessness, nasal discomfort, voice change | src 01/06/08/11/12 | none classified unsupported; some boundary-only |
| `focus_kidney` | fear, lower-back/knee weakness, tinnitus, nocturia, exertional breathlessness (MR-06 secondary) | src 01/05/06/11/13; MR-06 boundary provenance retained separately | nocturia |

Group membership and retrieval activation eligibility are distinct. `included_claim_codes` preserves approved membership and provenance, including unsupported claims. The additional `retrieval_activation` rule requires at least one confirmed active `DIRECT_SUPPORT` or `BOUNDARY_SUPPORT` member; its `eligible_claim_codes` excludes all `UNSUPPORTED` members. Removed/contradicted facts and unconfirmed facts cannot activate a group. Unsupported claims mixed with eligible claims do not suppress that group. Unsupported-only activates zero retrieval groups and remains EMPTY/NO_ANSWER.

Expected projection: include approved Chinese claim display names and the approved organ display name for **eligible active confirmed claims only**. Unsupported members retain provenance and cannot supply retrieval evidence. No group is activated by a historical/raw fact alone. MR-06 breathlessness remains eligible in both lung and kidney groups as boundary support, with lung primary and kidney secondary.

## 7. Unsupported and boundary claims

Boundary claims may retrieve approved background but must not be described as directly proven by that background. Unsupported claims must not receive a fabricated positive label or forced low-score hit. Full lists are frozen in the Gold asset; the present production questionnaire has 9 boundary and 3 unsupported claims. `postmeal_heaviness` means “超出当前语料覆盖”, not “无医学关联”.

The `flank_discomfort` item also has a known wording conflict between the questionnaire phrase and claim dictionary display name. Medical/Owner review must resolve that conflict before any new active corpus text is approved.

## 8. Proposed corpus additions

The following are review drafts only. Each is **PROPOSED — NOT APPROVED — NOT ACTIVE**. They must not enter runtime or an index without Medical Review, Owner approval, versioned assets, and separate G3 index-build authorization.

| Proposed chunk | Coverage | Exact proposed content | Source/review rationale | Why current corpus is insufficient |
| --- | --- | --- | --- | --- |
| `proposed_qrag_flank_001` | `flank_discomfort` | “胁肋胀闷不适可作为肝系状态相关表现的候选解释；该表现本身不能单独形成诊断结论。” | Requires Medical Review against an approved diagnostic textbook passage and resolution of the questionnaire/claim wording conflict. | Current src 12 mentions emotional regulation and liver but does not state flank discomfort. |
| `proposed_qrag_postmeal_heaviness_001` | `postmeal_heaviness` | “餐后困重可作为脾运化状态相关表现的候选解释；该表现本身不能单独形成诊断结论。” | Requires Medical Review against an approved diagnostic/internal-medicine textbook passage. | Current src 11 states postmeal bloating/loose stool, not postmeal heaviness. |
| `proposed_qrag_nocturia_001` | `nocturia` | “夜尿频多可作为肾系状态相关表现的候选解释；该表现本身不能单独形成诊断结论。” | Requires Medical Review against an approved diagnostic/internal-medicine textbook passage. | Current kidney chunks cover lower-back/knee weakness and tinnitus, not nocturia. |

No source is self-approved here; exact wording and source passage must be accepted or rejected by Medical Review.

## 9. Negative/no-answer safety matrix

| Case | Required outcome | Prohibited behavior |
| --- | --- | --- |
| Unsupported-only (`flank_discomfort`, `postmeal_heaviness`, `nocturia`) | zero retrieval-active groups; EMPTY/NO_ANSWER | force-recalling organ background as direct support |
| `gq_14` generation rules | NO_ANSWER | returning five-tone background as generation-rule evidence |
| `gq_15` questionnaire scoring | NO_ANSWER | returning five-organ theory as scoring evidence |
| `gq_17` unsupported syndrome detail | NO_ANSWER | returning generic heart/spleen background as syndrome detail |
| Confirmed edit removes anger | digestion query only | using provenance-only anger as active retrieval input |

## 10. Threshold preservation

G1 preserves source cosine `0.65`, normalized score `0.740741`, epsilon `1e-6`, Top-K `5`, and the existing conversion. No threshold value is modified or proposed for reduction. Focused-query evaluation must succeed without weakening the no-answer firewall.

## 11. Confirmed-state authority

The user-confirmed/edited state is downstream authority. Raw answers, historical facts, source refs, and evidence remain provenance. A removed or contradicted fact must not activate a focused group, enter the active query claims, or become current retrieval evidence. `qrag_confirmed_edit_removes_anger` freezes this rule.

## 12. Expected G2 runtime design (preview only)

Proposed flow:

`structured active confirmed claims → approved focused groups → existing RagQuery authority → same manifest/version/Top-K/threshold gates → approved-hit retrieval → deterministic merge`

Proposed merge contract:

- merge key: `chunk_id`;
- duplicates: retain the highest valid score;
- provenance: retain stable focused-query source order;
- approval, version, checksum, collection identity, and threshold validation: unchanged;
- unsupported-only groups: zero focused queries and EMPTY/NO_ANSWER;
- raw/provenance-only facts: never activate groups.

This is design material only. No G2 runtime code exists in this phase.

## 13. Is G3 needed?

**Conditional yes.** G2 can test whether focusing restores existing support for direct/boundary claims. G3 appears necessary only if Owner/Medical Review requires direct retrieval support for the three unsupported questionnaire claims. If those claims are intentionally abstention-only, G3 may be rejected. Any G3 corpus/index work needs new versioned assets and a separate explicit Owner authorization for real embedding/index build.

## 14. Medical Review decision table

Medical decisions received through the Owner takeover authorization:

| Decision | Item | Status |
| --- | --- | --- |
| MR-01/02 | Gold / coverage acceptance pack | Signed; received through Owner |
| MR-03 | focus_liver | APPROVE |
| MR-04 | focus_heart | APPROVE |
| MR-05 | focus_spleen | APPROVE; heaviness remains outside current corpus coverage |
| MR-06 | focus_lung / exertional_breathlessness | REVISE: lung primary + kidney secondary, BOUNDARY_SUPPORT |
| MR-07 | focus_kidney | APPROVE plus MR-06 reachability |
| MR-08/09/10 | flank/heaviness/nocturia unsupported classification | APPROVE no-answer only; proposed chunks NOT approved |
| MR-11 | thresholds | APPROVE 0.65 / 0.740741 |
| MR-12 | G2 | CONDITIONAL APPROVE after offline MR-06 correction passes |
| MR-13 | future G3 | useful future expansion; Owner execution NOT authorized |

## 15. Owner decision table

Owner decisions received (no new corpus or index authorization):

| Decision | Item | Status |
| --- | --- | --- |
| OD-01 | Freeze Gold benchmark | APPROVE |
| OD-02 | Preserve 0.65 / 0.740741 | APPROVE |
| OD-03 | Preserve Top-K 5 | APPROVE |
| OD-04 | Preserve unsupported-only and gq_14/15/17 empty | APPROVE |
| OD-05 | Confirmed-state authority | APPROVE |
| OD-06 | G2 | APPROVE WITH CONDITION: MR-06 verified; no boundary/unsupported promotion |
| OD-07 | G3 deferred | APPROVE; new corpus/embedding/index NOT authorized |

G2 may proceed only after the MR-06 offline correction and all safety gates pass. G3 remains unauthorized. Phase H engineering merged separately in PR #142; Android real-device acceptance remains pending. This pack changes no runtime, index or corpus.
