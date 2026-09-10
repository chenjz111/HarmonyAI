# V3.1 Reviewed Corpus and Chroma Index Design

**Status:** Approved for planning on 2026-09-09
**Branch:** `feat/s5-v3.1-ai-backend-integration`
**PR:** #118
**Medical source authority:** PR #114 / `knowledge/v3/rag-corpus-manifest-v3.1.json`

## 1. Goal

Prepare a traceable V3.1 RAG corpus package from the 13 medically reviewed source registrations in PR #114, provide a production-gated `text-embedding-v4` 1024-dimensional Chroma index builder, and give the Owner a safe command for the real Embedding → Chroma → Qwen smoke run.

This change does not claim that a real index or Real Provider smoke has succeeded. The repository contains no DashScope key and cannot produce a real 1024-dimensional index in the development environment.

## 2. Authority and hard boundary

PR #114 explicitly delivers a source registry, not source正文 or production chunks. Its 13 entries contain:

- `source_id`;
- title, grade, version and source reference;
- a medically reviewed `use` statement;
- source `content_hash` and review metadata.

The corpus preparation step may copy the `use` value verbatim. It must not quote unprovided source正文, paraphrase the `use` value, add a diagnosis, add a syndrome mapping, or infer extra organ/claim labels.

Therefore the first committed corpus is a **candidate corpus** with status `PENDING_MEDICAL_CONTENT_REVIEW`. It is reviewable by 肖宇翔 but is rejected by the production ingestion gate until every chunk and the release manifest are explicitly approved.

## 3. Chosen approach

### 3.1 Candidate corpus asset

Create `knowledge/v3/rag-corpus-chunks-v3.1-candidate.json` as a canonical JSON document, not JSONL. A single JSON document lets the existing checksum convention cover the complete package and avoids line-order ambiguity.

Each of the 13 source registry rows produces exactly one candidate chunk:

```json
{
  "chunk_id": "v31_src_01_scope_001",
  "source_id": "src_01",
  "source_title": "《素问·阴阳应象大论》",
  "source_reference": "《黄帝内经·素问·阴阳应象大论》（篇），通行校注本（人民卫生出版社，中医古籍整理系列）",
  "source_content_hash": "sha256:f1f29c74e482d97675ef46f9dba40d66c886947fd0c544baea8ec7c63d26478b",
  "section": "source_registry_use",
  "text": "五志五脏对应（怒肝/喜心/思脾/悲肺/恐肾）与五脏开窍（肝目/心舌/脾口/肺鼻/肾耳）",
  "display_summary": "五志五脏对应（怒肝/喜心/思脾/悲肺/恐肾）与五脏开窍（肝目/心舌/脾口/肺鼻/肾耳）",
  "claim_codes": [],
  "organ_codes": [],
  "review_status": "pending_medical_review",
  "source_registry_review_status": "medically_reviewed",
  "source_registry_reviewed_at": "2026-09-06",
  "source_registry_reviewer": "nob（肖宇翔，Medical Knowledge Engineer）",
  "knowledge_version": "medical_v3.1-candidate.1"
}
```

The stored row additionally includes `content_checksum`, calculated after all other fields are fixed by removing only that checksum field and hashing canonical compact UTF-8 JSON.

Empty `claim_codes` and `organ_codes` are intentional. Adding those labels would introduce medical interpretation not present as structured fields in PR #114.

### 3.2 Candidate package manifest

Create `knowledge/v3/rag-ingestion-manifest-v3.1-candidate.json` with:

- candidate schema/version and status;
- the exact PR #114 source-registry checksum;
- candidate corpus checksum;
- ordered chunk IDs and per-chunk checksums;
- `embedding_model = text-embedding-v4`;
- `embedding_dimension = 1024`;
- `embedding_version = text-embedding-v4@1024`;
- `distance_metric = cosine`;
- `index_status = NOT_BUILT_OWNER_PENDING`;
- a canonical manifest checksum.

This candidate manifest is not an `IngestionManifest` accepted by `load_production_corpus()`. Promotion requires an explicit reviewed release artifact; changing an environment variable cannot promote a candidate corpus.

### 3.3 Medical review and production promotion

The promotion command validates, without rewriting medical content, that:

1. all 13 source IDs are present exactly once and in registry order;
2. each chunk `text` and `display_summary` equal the registry `use` value byte-for-byte;
3. source title/reference/hash and review metadata match PR #114;
4. every chunk checksum and the package checksum are valid;
5. every chunk has `review_status = approved` and a non-empty `medical_review_version` supplied by the medical reviewer;
6. the release manifest has `review_status = approved` and the Owner-approved retrieval configuration.

The code never changes `pending_medical_review` to `approved` automatically. 肖宇翔 reviews the candidate content and the Owner supplies the signed-off release manifest.

### 3.4 Chroma index builder

Add a CLI module at `backend/ai_engine/v3/rag_index_cli.py`:

```text
python -m backend.ai_engine.v3.rag_index_cli build \
  --manifest knowledge/v3/rag-ingestion-manifest-v3.1-approved.json \
  --chunks knowledge/v3/rag-corpus-chunks-v3.1-approved.json \
  --persist-directory .chroma-v31 \
  --collection harmony_v31 \
  --receipt .chroma-v31/index-receipt.json
```

The builder:

- reads Provider credentials only from environment variables;
- requires `HARMONYAI_REAL_AGENTS=true`;
- requires `text-embedding-v4`, dimension 1024 and `input_type=document`;
- calls the existing production `load_production_corpus()` and `VersionedRagStore`;
- refuses candidate/pending chunks before any Provider call;
- writes no key, endpoint, full embedding vector or user text to logs or the receipt;
- does not load `knowledge/demo_chunks.jsonl` and never switches to Mock;
- stores the Chroma directory outside Git.

### 3.5 Index receipt and checksum

The physical Chroma database is not committed and is not byte-stable across platforms. “Index checksum” therefore means the checksum of a canonical index receipt that proves the indexed logical content and embedding identity:

The receipt contains `schema_version=v31_chroma_index_receipt_v1`, the resolved versioned collection name, `knowledge_version=medical_v3.1`, `embedding_model=text-embedding-v4`, `embedding_dimension=1024`, `embedding_version=text-embedding-v4@1024`, `distance_metric=cosine`, the approved corpus manifest checksum, all 13 ordered chunk checksums and the calculated index checksum.

The checksum excludes only `index_checksum`. It does not hash raw vectors. On repeated builds of the same approved corpus and embedding identity, the logical index checksum is stable.

### 3.6 Owner real smoke command

Add `backend/ai_engine/v3/real_provider_smoke.py`. It performs:

```text
approved corpus validation
→ text-embedding-v4 document embedding
→ Chroma upsert
→ text-embedding-v4 query embedding
→ Top-K retrieval from the current collection
→ Qwen structured DiagnosisProviderResponse
→ Schema Validation
→ Medical Rule Validation
```

The smoke input is a repository-owned, synthetic, non-user fixture containing only approved code identifiers. The command prints safe status, model identity, dimensions, manifest checksum, index checksum, retrieval count and Provider result status. It prints no key, prompt, vector, source正文 or user text.

Real smoke is successful only when the Owner executes it with real credentials and a production-approved corpus. Unit tests use fakes and remain labelled Mock integration tests.

## 4. Data flow

```text
PR #114 source registry
        │ exact-field validation
        ▼
candidate corpus (13 source-scope chunks)
        │ medical reviewer approval
        ▼
approved chunks + approved ingestion manifest
        │ checksum and Provider readiness gates
        ▼
text-embedding-v4 @ 1024
        │ document vectors
        ▼
versioned Chroma collection + index receipt
        │ synthetic query / current production query
        ▼
Top-K approved hits → Qwen → schema/medical validation
```

## 5. Failure semantics

| Condition | Result |
| --- | --- |
| candidate or pending corpus | `CORPUS_NOT_PRODUCTION_APPROVED` before Provider call |
| source registry mismatch | `CORPUS_SOURCE_REGISTRY_MISMATCH` |
| chunk text differs from PR #114 `use` | `CORPUS_SOURCE_SCOPE_MISMATCH` |
| manifest/chunk checksum mismatch | existing explicit checksum error |
| model/dimension differs from v4/1024 | `EMBEDDING_NOT_APPROVED` |
| missing DashScope/Chroma/Qwen configuration | explicit readiness failure |
| Chroma build/query unavailable | `RAG_INDEX_UNAVAILABLE` |
| no approved retrieval hit | medical abstain; no fabricated candidate |
| Qwen/schema/medical validation failure | failed with existing retryable semantics |

No failure path silently loads demo content or changes Real mode to Mock.

## 6. Security and repository hygiene

- Keys and workspace IDs stay in environment variables.
- `.env`, Chroma SQLite files, vector payloads and smoke outputs are not committed.
- Logs contain identifiers and checksums only.
- The committed candidate corpus contains only fields already present in PR #114.
- No full copyrighted source text is introduced.

## 7. Test strategy

Automated tests cover:

1. exactly 13 registry sources, in order, with no unknown source;
2. byte-for-byte equality between chunk text/summary and PR #114 `use`;
3. source title/reference/hash provenance equality;
4. canonical candidate corpus, chunk, manifest and index-receipt checksums;
5. candidate corpus rejection by production ingestion;
6. approved release acceptance and tamper rejection;
7. `text-embedding-v4`, 1024 dimensions and document/query input types;
8. Chroma collection identity and repeat-ingest reuse;
9. safe receipt/log content;
10. Owner smoke CLI dependency wiring with fake transports, explicitly labelled non-Real;
11. existing V3.1 contract, knowledge, migration and full backend regression suites.

## 8. Deliverables and acceptance

The PR is ready for medical review when it contains the candidate corpus, candidate manifest, validation/index tooling, tests and Owner commands. It remains `NOT_REAL_VALIDATED` and Draft.

Production readiness requires all of the following outside this implementation:

- 肖宇翔 approves the candidate chunk content and supplies the medical review version;
- Owner supplies an approved ingestion manifest including retrieval threshold;
- Owner builds the real Chroma index with DashScope credentials;
- Owner records the generated index receipt/checksum;
- Owner runs and records the real Embedding → Chroma → Qwen smoke result.
