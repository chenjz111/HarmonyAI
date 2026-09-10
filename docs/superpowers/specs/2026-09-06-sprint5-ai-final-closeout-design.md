# Sprint 5 V3.1 AI Final Closeout Design

## Status and authority

This design covers GitHub Issue #109 on top of `V3.1_FREEZE_BASELINE` at
`origin/integration/sprint4-real-input@83fe2f4`. The frozen V3.1 flow,
questionnaire, executable schemas, persistence semantics, and public read
model remain authoritative. This work may adapt implementations to those
contracts but must not modify them.

The approved provider direction is recorded in
`docs/sprint5/s5-v3.1-provider-decision-final.md` on the Owner closeout
documentation branch. Medical Issue #108 supplies the corpus and medical
acceptance; this work must not invent missing source text, syndrome codes, or
medical rules.

## Scope

Issue #109 owns the AI-side implementation of:

1. production embedding boundary for `text-embedding-v4`, 1024 dimensions;
2. versioned Chroma ingestion and retrieval over an approved V3.1 corpus;
3. deterministic RAG query construction;
4. Qwen Agent2 candidate diagnosis with bounded retry, JSON/schema repair,
   whitelist, evidence-reference, conflict, and medical-rule validation;
5. deterministic V3.1 Agent3 ToneProfile and provider-neutral GenerationSpec;
6. the public Five-Tone Analysis read-model assembler and safe-expression
   checks, where no persistence or frontend ownership is required.

The following are explicitly out of scope: changing frozen contracts,
DocumentSet/Relevance/ConfirmedUserState ORM ownership, new migrations,
frontend pages, MiniMax or audio materialization, ASR in the primary V3.1
flow, or compatibility rewrites of V3.0.

## Existing boundaries to reuse

- `backend/ai_engine/providers.py` remains the transport boundary for
  Qwen-compatible JSON calls.
- `backend/ai_engine/v3/understanding_provider.py` supplies the established
  typed Provider failure, retry/repair, health, and privacy patterns.
- `backend/app/schemas/v3/diagnosis.py` supplies `RagQuery`, `RagResult`,
  `DiagnosisProviderRequest`, `DiagnosisProviderResponse`, and the diagnosis
  result union.
- `backend/app/schemas/v3/flow_v31.py` supplies `ToneProfileV31` and
  `FiveToneAnalysisReadModel`.
- Existing V3 persistence models remain the audit target for diagnosis,
  retrieval, provider runs, and candidate evidence. The AI module must not
  create a competing persistence schema.

## Data flow

### Agent2

The service receives only an owner-scoped, confirmed V3.1 assessment/state
snapshot. It derives a query from approved claim codes, organ evidence,
supporting/contradicting Fact IDs, and the frozen query-builder version. It
requests a query embedding with `input_type=query`, retrieves only from a
collection whose corpus version, embedding model, dimension, metric, and
manifest checksum match the approved ingestion manifest, then sends only
validated facts and approved RAG references to Qwen. The formal diagnosis
service reaches this seam through an owner-scoped projection adapter until
the reviewed #104/#105 state loader is available; it does not copy those
persistence implementations.

Qwen output is advisory. The validator rejects unknown syndrome codes,
unknown Fact IDs or Chunk IDs, mismatched evidence directions, unsupported
knowledge versions, duplicate or contradictory references, and any result
outside the frozen response Schema. A valid result is then converted to the
V3 diagnosis response and persisted with provider/RAG audit metadata. An
empty retrieval is an evidence-gated abstention; provider failure,
unavailable index, schema/rule failure, or missing approved assets is an
explicit failed/readiness result; it never fabricates a syndrome.

### Agent3

Agent3 consumes the current confirmed state and a validated Agent2 result.
Approved deterministic mappings compute all five tone weights and select the
primary tone. The secondary tone is emitted only when an approved versioned
threshold rule permits it; otherwise it is `null`. UserGoal is a preference
input only and may affect sound parameters, never medical evidence, tone
mapping, or diagnosis. The output is a provider-neutral `GenerationSpec` and
the frozen public read model. Provider prompts, raw RAG text, model metadata,
private reasoning, and internal failure enums are excluded from the public
model.

## Provider and asset gates

Production mode requires explicit environment configuration:

- runtime credentials: `HARMONYAI_REAL_AGENTS=true`, `DASHSCOPE_API_KEY`,
  and `DASHSCOPE_WORKSPACE_ID`;
- DashScope endpoint: `DASHSCOPE_BASE_URL` may override the default
  compatible endpoint; the same workspace header is sent to Embedding and
  Qwen requests;
- Embedding identity: `text-embedding-v4` and `1024` dense dimensions;
- Qwen model: `QWEN_MODEL` or `DASHSCOPE_QWEN_MODEL`;
- Chroma: `CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION`;
- corpus: `RAG_CORPUS_MANIFEST_PATH` and `RAG_CORPUS_CHUNKS_PATH`;
- medical release: `V31_ALLOWED_SYNDROME_CODES`, `V31_MEDICAL_RULE_VERSION`,
  and an approved `V31_MUSIC_GENERATION_RULES_PATH`.

Legacy `EMBEDDING_*` and `QWEN_*` values may override endpoint/model details
only when the DashScope credentials are also present and the resulting
identity remains approved.

Credentials never enter source, fixtures, screenshots, CI output, or normal
logs. Production must reject missing or inconsistent configuration rather
than silently selecting mock mode or `hash-v1`.

The #108 corpus issue currently provides medically reviewed source
registration, but its source approval is still pending production release and
its ingestion fields are incomplete. Until Owner-approved chunk payloads and
the completed ingestion manifest exist, the implementation may validate the
boundary and run against non-medical test doubles only in explicit tests; it
must report production RAG as not ready.

## Failure semantics

- Embedding timeout/auth/rate-limit/dimension errors map to stable provider
  failures without exposing raw input.
- Chroma unavailable, stale, corrupt, or manifest-mismatched indexes are
  explicit failures; an empty retrieval is an evidence-gated abstention.
- Qwen timeout and transient provider errors follow the existing bounded
  retry policy. Invalid JSON/schema is repaired at most once, then rejected.
- Diagnosis with insufficient evidence abstains. RAG/provider/schema/rule
  failures are failed/readiness outcomes; they are not rewritten as
  abstentions.
- Agent3 never converts a failed or abstained diagnosis into a syndrome-based
  tone profile. It uses only the frozen conservative fallback modes.

## Test and acceptance strategy

Tests are written first for each new boundary and must be observed failing
before implementation. The suite must cover provider error mapping, embedding
dimensions and input types, collection identity, manifest/checksum gates,
retrieval references, diagnosis validation, Agent3 tone invariants, UserGoal
separation, privacy logging, and V3.0 compatibility.

Real-mode smoke evidence is separate from unit/contract evidence. The PR may
be Draft while upstream medical assets are pending, but it must label the
actual mode as `REAL_VALIDATED`, `MIXED/DEGRADED`, or `NOT_REAL_VALIDATED`.
No `REAL_RAG_QWEN` claim is permitted without real embedding, approved corpus
ingestion, Chroma retrieval, Qwen diagnosis, and end-to-end validator
evidence.

## Handoff and dependency policy

The AI PR is based on the frozen integration baseline. It may consume the
approved output of #108 and the backend interfaces from #104/#105 after those
are available, but it must not merge their entire unreviewed branches or
duplicate their persistence models. Any missing contract field, medical
threshold, or incompatible interface is recorded in the owning Issue and
reported to the Owner before implementation changes scope.
