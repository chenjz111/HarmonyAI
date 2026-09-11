# V3.1 Reviewed Corpus and Chroma Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PR #114-bound candidate medical corpus, production approval gates, a `text-embedding-v4` 1024-dimensional Chroma index builder, deterministic index receipts and an Owner-executable Real Provider smoke command without storing credentials or claiming a fake Real result.

**Architecture:** Candidate assets are derived byte-for-byte from the PR #114 source registry and are never accepted by the production loader. Existing `IngestionManifest`, `KnowledgeChunk`, `VersionedRagStore`, Embedding and Qwen boundaries remain authoritative; new tooling validates promotion, builds the versioned Chroma collection, emits a logical index receipt, and runs a safe Owner smoke only when the approved release and real environment are present.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, ChromaDB, DashScope OpenAI-compatible APIs, canonical SHA-256 JSON checksums.

**Spec:** `docs/superpowers/specs/2026-09-09-v31-rag-corpus-chroma-index-design.md`

## Global Constraints

- Source authority is exactly `knowledge/v3/rag-corpus-manifest-v3.1.json` from PR #114.
- Candidate `text` and `display_summary` must equal the corresponding registry `use` value byte-for-byte.
- Do not add source正文, syndrome mappings, diagnoses, organ labels, claim labels or other medical conclusions.
- Candidate status is `PENDING_MEDICAL_CONTENT_REVIEW`; production ingestion requires explicit medical and Owner approval.
- Production embedding identity is `text-embedding-v4`, dimension `1024`, version `text-embedding-v4@1024`.
- Real mode never reads demo chunks, hash embeddings or Mock Providers.
- No API key, workspace ID, endpoint, prompt, vector, user text, Chroma database or test output is committed.
- PR #118 remains Draft and is not merged by this plan.

---

### Task 1: Add the PR #114-bound candidate corpus assets

**Files:**
- Create: `knowledge/v3/rag-corpus-chunks-v3.1-candidate.json`
- Create: `knowledge/v3/rag-ingestion-manifest-v3.1-candidate.json`
- Create: `tests/knowledge/test_v31_candidate_corpus.py`

**Interfaces:**
- Consumes: `knowledge/v3/rag-corpus-manifest-v3.1.json` fields `content_checksum` and `sources[]`.
- Produces: immutable candidate package with 13 chunk payloads, ordered chunk checksums, package checksum and candidate manifest checksum.

- [ ] **Step 1: Write the source-boundary tests**

```python
def test_candidate_chunks_are_exact_pr114_source_scope_rows():
    registry = _load("rag-corpus-manifest-v3.1.json")
    candidate = _load("rag-corpus-chunks-v3.1-candidate.json")
    assert candidate["source_registry_checksum"] == registry["content_checksum"]
    assert [row["source_id"] for row in candidate["chunks"]] == [
        row["source_id"] for row in registry["sources"]
    ]
    assert len(candidate["chunks"]) == 13
    for source, chunk in zip(registry["sources"], candidate["chunks"]):
        assert chunk["text"] == source["use"]
        assert chunk["display_summary"] == source["use"]
        assert chunk["source_title"] == source["title"]
        assert chunk["source_reference"] == source["source_reference"]
        assert chunk["source_content_hash"] == source["content_hash"]
        assert chunk["claim_codes"] == []
        assert chunk["organ_codes"] == []
        assert chunk["review_status"] == "pending_medical_review"
```

Add checksum assertions using the repository canonical JSON algorithm: remove only the checksum field, serialize with sorted keys and compact UTF-8 separators, then calculate SHA-256.

- [ ] **Step 2: Run the tests and verify the assets are missing**

Run:

```text
python -m pytest tests/knowledge/test_v31_candidate_corpus.py -q
```

Expected: FAIL because the two candidate asset files do not exist.

- [ ] **Step 3: Create the 13 exact candidate chunks**

Use the design schema. For each registry row:

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

After fixing every copied field, calculate and add `content_checksum` using the canonical JSON helper tested in Step 1.

The candidate manifest records `embedding_model=text-embedding-v4`, `embedding_dimension=1024`, `embedding_version=text-embedding-v4@1024`, `distance_metric=cosine`, `index_status=NOT_BUILT_OWNER_PENDING`, the 13 ordered chunk checksums and its own canonical checksum.

- [ ] **Step 4: Run the candidate asset tests**

Run:

```text
python -m pytest tests/knowledge/test_v31_candidate_corpus.py tests/knowledge/test_s5final_medical_assets.py -q
```

Expected: all tests PASS; the existing PR #114 test continues to assert that its registry itself contains no chunks.

- [ ] **Step 5: Commit the candidate assets**

```text
git add knowledge/v3/rag-corpus-chunks-v3.1-candidate.json knowledge/v3/rag-ingestion-manifest-v3.1-candidate.json tests/knowledge/test_v31_candidate_corpus.py
git commit -m "feat(rag): add PR114-bound candidate corpus"
```

---

### Task 2: Add candidate validation and explicit production promotion gates

**Files:**
- Create: `backend/ai_engine/v3/corpus_release.py`
- Modify: `backend/ai_engine/v3/rag_ingestion.py`
- Create: `tests/ai_engine/v3/test_corpus_release_v31.py`
- Modify: `tests/ai_engine/v3/test_rag_ingestion_v31.py`

**Interfaces:**
- Consumes: `load_candidate_corpus(candidate_manifest_path, candidate_chunks_path, source_registry_path)`.
- Produces: `CandidateCorpusPackage`, `validate_candidate_against_source_registry` and `validate_approved_release_metadata`; production loader still returns `tuple[IngestionManifest, list[KnowledgeChunk]]`.

- [ ] **Step 1: Write failing candidate validation tests**

```python
def test_candidate_validator_rejects_text_not_equal_to_registry_use(tmp_path):
    package = valid_candidate_payload()
    package["chunks"][0]["text"] += "新增医学解释"
    with pytest.raises(CorpusReleaseFailure, match="CORPUS_SOURCE_SCOPE_MISMATCH"):
        validate_candidate_against_source_registry(package, approved_registry())


def test_candidate_cannot_be_loaded_as_production_corpus(candidate_paths):
    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_NOT_PRODUCTION_APPROVED"):
        load_production_corpus(*candidate_paths)
```

Also test unknown source IDs, duplicate/missing source IDs, source hash mismatch, registry checksum mismatch and candidate checksum mismatch.

- [ ] **Step 2: Run the tests and verify the new module is absent**

Run:

```text
python -m pytest tests/ai_engine/v3/test_corpus_release_v31.py tests/ai_engine/v3/test_rag_ingestion_v31.py -q
```

Expected: FAIL on import of `backend.ai_engine.v3.corpus_release`.

- [ ] **Step 3: Implement candidate validation without medical transformation**

Implement:

```python
class CorpusReleaseFailure(RuntimeError):
    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


@dataclass(frozen=True)
class CandidateCorpusPackage:
    manifest: Mapping[str, object]
    chunks: Sequence[Mapping[str, object]]
    source_registry_checksum: str


def load_candidate_corpus(
    candidate_manifest_path: str | Path,
    candidate_chunks_path: str | Path,
    source_registry_path: str | Path,
) -> CandidateCorpusPackage:
    manifest = json.loads(Path(candidate_manifest_path).read_text(encoding="utf-8"))
    candidate = json.loads(Path(candidate_chunks_path).read_text(encoding="utf-8"))
    registry = json.loads(Path(source_registry_path).read_text(encoding="utf-8"))
    package = validate_candidate_against_source_registry(candidate, registry)
    validate_candidate_manifest(manifest, package)
    return package
```

Compare all authority fields exactly. Do not normalize, translate, tokenize or infer medical labels.

- [ ] **Step 4: Make the production loader reject candidate wrappers explicitly**

Before Pydantic parsing in `load_production_corpus()`, inspect wrapper status. Return `CORPUS_NOT_PRODUCTION_APPROVED` for `pending_medical_review` instead of the generic `CORPUS_FILES_INVALID`. Preserve all existing approved manifest/chunk behavior.

- [ ] **Step 5: Run candidate and production-ingestion tests**

Run:

```text
python -m pytest tests/ai_engine/v3/test_corpus_release_v31.py tests/ai_engine/v3/test_rag_ingestion_v31.py -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit validation gates**

```text
git add backend/ai_engine/v3/corpus_release.py backend/ai_engine/v3/rag_ingestion.py tests/ai_engine/v3/test_corpus_release_v31.py tests/ai_engine/v3/test_rag_ingestion_v31.py
git commit -m "feat(rag): gate candidate corpus promotion"
```

---

### Task 3: Build the production Chroma index and deterministic receipt

**Files:**
- Create: `backend/ai_engine/v3/rag_index_receipt.py`
- Create: `backend/ai_engine/v3/rag_index_cli.py`
- Modify: `backend/ai_engine/v3/rag_store.py`
- Create: `tests/ai_engine/v3/test_rag_index_cli_v31.py`
- Modify: `tests/ai_engine/v3/test_rag_store_v31.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: approved `IngestionManifest`, approved `KnowledgeChunk[]`, real `EmbeddingProvider`, Chroma persistence path and collection base name.
- Produces: `IndexReceipt`, `canonical_index_checksum(receipt) -> str`, CLI exit code `0` only after validated ingest and count verification.

- [ ] **Step 1: Write failing receipt and builder tests**

```python
def test_index_receipt_checksum_is_stable_and_contains_no_secret_or_vector():
    receipt = build_index_receipt(valid_manifest(), valid_chunks(), "collection_v31")
    payload = receipt.model_dump(mode="json")
    assert payload["index_checksum"] == canonical_index_checksum(payload)
    serialized = json.dumps(payload)
    assert "api_key" not in serialized.lower()
    assert "embedding_vector" not in serialized.lower()


def test_index_builder_uses_document_embedding_and_verifies_count(fake_chroma):
    result = build_index(valid_paths(), fake_real_embedding(), fake_chroma)
    assert fake_real_embedding.input_types == ["document"] * 13
    assert result.chunk_count == 13
```

Add tests for pending corpus rejection before Provider calls, dimension mismatch, collection count mismatch and repeat build reuse.

- [ ] **Step 2: Run the tests and verify the CLI/receipt modules are absent**

Run:

```text
python -m pytest tests/ai_engine/v3/test_rag_index_cli_v31.py tests/ai_engine/v3/test_rag_store_v31.py -q
```

Expected: FAIL on imports of the new modules.

- [ ] **Step 3: Implement the logical index receipt**

Define a strict Pydantic model whose checksum excludes only `index_checksum`. Sort chunk checksum rows by `chunk_id`. Do not include timestamps in the checksum projection.

```python
class IndexReceipt(V3BaseModel):
    schema_version: Literal["v31_chroma_index_receipt_v1"]
    collection_name: NonEmptyString
    knowledge_version: NonEmptyString
    embedding_model: Literal["text-embedding-v4"]
    embedding_dimension: Literal[1024]
    embedding_version: Literal["text-embedding-v4@1024"]
    distance_metric: Literal["cosine"]
    corpus_manifest_checksum: str
    chunk_count: int
    chunk_checksums: list[IndexChunkChecksum]
    index_checksum: str
```

- [ ] **Step 4: Add a count-verifying index build boundary**

Expose the current collection name and count from `VersionedRagStore` through read-only properties. The CLI must:

1. call `load_production_corpus()`;
2. create the real embedding Provider from environment;
3. require dimension 1024;
4. ingest with `production=True`;
5. verify Chroma count equals manifest chunk count;
6. write the receipt to the explicit `--receipt` path;
7. emit only safe IDs, counts and checksums.

- [ ] **Step 5: Ignore generated local index artifacts**

Add narrowly scoped patterns:

```text
.chroma-v31/
*.v31-index-receipt.local.json
```

Do not ignore committed knowledge manifests or candidate chunks.

- [ ] **Step 6: Run index tests**

Run:

```text
python -m pytest tests/ai_engine/v3/test_rag_index_cli_v31.py tests/ai_engine/v3/test_rag_store_v31.py tests/ai_engine/v3/test_embedding_provider.py -q
```

Expected: all tests PASS and use fake transports only.

- [ ] **Step 7: Commit index tooling**

```text
git add .gitignore backend/ai_engine/v3/rag_index_receipt.py backend/ai_engine/v3/rag_index_cli.py backend/ai_engine/v3/rag_store.py tests/ai_engine/v3/test_rag_index_cli_v31.py tests/ai_engine/v3/test_rag_store_v31.py
git commit -m "feat(rag): add versioned Chroma index builder"
```

---

### Task 4: Add the Owner real-provider smoke command

**Files:**
- Create: `backend/ai_engine/v3/real_provider_smoke.py`
- Create: `tests/fixtures/v31-real-provider-smoke-input.json`
- Create: `tests/integration/test_v31_real_provider_smoke_cli.py`
- Modify: `tests/integration/test_s5_v31_real_provider_chain.py`

**Interfaces:**
- Consumes: environment-backed V3.1 Provider config, approved corpus/chunks, Chroma directory, index receipt and synthetic fixture.
- Produces: process exit code plus safe JSON summary; no production state mutation beyond the explicitly selected Chroma directory.

- [ ] **Step 1: Write failing smoke orchestration tests**

```python
def test_smoke_runs_embedding_chroma_qwen_and_validators_with_safe_output(fakes):
    result = run_real_provider_smoke(config=fakes.config, dependencies=fakes.dependencies)
    assert result["embedding_model"] == "text-embedding-v4"
    assert result["embedding_dimension"] == 1024
    assert result["retrieved_chunk_count"] >= 1
    assert result["schema_validation"] == "passed"
    assert result["medical_rule_validation"] == "passed"
    assert "api_key" not in json.dumps(result).lower()


def test_smoke_missing_real_configuration_fails_without_mock(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(V31ReadinessFailure, match="DASHSCOPE_PROVIDER_NOT_CONFIGURED"):
        run_real_provider_smoke_from_environment()
```

Rename descriptions in the existing fake-chain tests so they cannot be reported as Real Smoke evidence.

- [ ] **Step 2: Run tests and verify the smoke module is absent**

Run:

```text
python -m pytest tests/integration/test_v31_real_provider_smoke_cli.py tests/integration/test_s5_v31_real_provider_chain.py -q
```

Expected: FAIL on import of `real_provider_smoke`.

- [ ] **Step 3: Implement the safe smoke orchestration**

Use existing Provider and validation boundaries. Do not duplicate Embedding, Chroma, Qwen, schema or medical rule logic. Permit `success` or a contract-valid medical `abstained` result; fail the smoke on readiness, transport, schema or medical-rule errors.

The output keys are limited to:

```text
status, embedding_model, embedding_dimension, corpus_manifest_checksum,
index_checksum, collection_name, retrieved_chunk_count,
qwen_model, provider_status, schema_validation, medical_rule_validation
```

- [ ] **Step 4: Add the synthetic fixture**

Use only approved identifiers already present in repository rule assets. Include no person, document, questionnaire response, diagnosis assertion or free-text medical narrative.

- [ ] **Step 5: Run smoke orchestration tests**

Run:

```text
python -m pytest tests/integration/test_v31_real_provider_smoke_cli.py tests/integration/test_s5_v31_real_provider_chain.py -q
```

Expected: all automated fake-transport tests PASS and are labelled `NOT_REAL_VALIDATED`.

- [ ] **Step 6: Commit the Owner smoke command**

```text
git add backend/ai_engine/v3/real_provider_smoke.py tests/fixtures/v31-real-provider-smoke-input.json tests/integration/test_v31_real_provider_smoke_cli.py tests/integration/test_s5_v31_real_provider_chain.py
git commit -m "feat(rag): add owner real-provider smoke command"
```

---

### Task 5: Document Owner commands and run release verification

**Files:**
- Create: `docs/sprint5/s5-v3.1-rag-corpus-index-handoff.md`
- Modify: `docs/sprint5/s5-v3.1-ai-109-closeout.md`

**Interfaces:**
- Consumes: the CLI commands and checksums generated by Tasks 1–4.
- Produces: Owner handoff with exact PowerShell commands, expected safe output and status distinctions.

- [ ] **Step 1: Write the Owner index-build command**

Document this PowerShell sequence. The Owner sets the two secret environment variables and the approved Qwen model before running it; the command checks presence without printing values:

```powershell
if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) { throw "DASHSCOPE_API_KEY is not configured" }
if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_WORKSPACE_ID)) { throw "DASHSCOPE_WORKSPACE_ID is not configured" }
if ([string]::IsNullOrWhiteSpace($env:QWEN_MODEL)) { throw "QWEN_MODEL is not configured" }

$env:HARMONYAI_REAL_AGENTS = "true"
$env:DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:EMBEDDING_MODEL = "text-embedding-v4"
$env:EMBEDDING_DIMENSION = "1024"
$env:CHROMA_PERSIST_DIRECTORY = (Join-Path (Get-Location) ".chroma-v31")
$env:CHROMA_COLLECTION = "harmony_v31"

python -m backend.ai_engine.v3.rag_index_cli build `
  --manifest "knowledge/v3/rag-ingestion-manifest-v3.1-approved.json" `
  --chunks "knowledge/v3/rag-corpus-chunks-v3.1-approved.json" `
  --persist-directory $env:CHROMA_PERSIST_DIRECTORY `
  --collection $env:CHROMA_COLLECTION `
  --receipt ".chroma-v31/index-receipt.json"
```

The documentation must say the command fails while the committed package remains pending medical review.

- [ ] **Step 2: Write the Owner end-to-end smoke command**

```powershell
python -m backend.ai_engine.v3.real_provider_smoke `
  --manifest "knowledge/v3/rag-ingestion-manifest-v3.1-approved.json" `
  --chunks "knowledge/v3/rag-corpus-chunks-v3.1-approved.json" `
  --index-receipt ".chroma-v31/index-receipt.json" `
  --fixture "tests/fixtures/v31-real-provider-smoke-input.json"
```

Document that only Owner output from real credentials may change status from `NOT_REAL_VALIDATED`.

- [ ] **Step 3: Run targeted tests**

Run:

```text
python -m pytest tests/knowledge/test_v31_candidate_corpus.py tests/knowledge/test_s5final_medical_assets.py tests/ai_engine/v3/test_corpus_release_v31.py tests/ai_engine/v3/test_rag_ingestion_v31.py tests/ai_engine/v3/test_rag_index_cli_v31.py tests/ai_engine/v3/test_rag_store_v31.py tests/ai_engine/v3/test_embedding_provider.py tests/integration/test_v31_real_provider_smoke_cli.py tests/integration/test_s5_v31_real_provider_chain.py -q --tb=short
```

Expected: all tests PASS with no real network call.

- [ ] **Step 4: Run required regression suites**

Run separately:

```text
python -m pytest tests/contract -q --tb=short
python -m pytest tests/knowledge -q --tb=short
python -m pytest tests/api/v3/test_v3_business_migrations.py tests/api/v3/test_v3_migrations.py -q --tb=short
python -m pytest tests -q --tb=short
git diff --check
```

Expected: every command exits `0`. Record exact pass counts from this execution in the handoff and PR body.

- [ ] **Step 5: Verify repository hygiene**

Run:

```text
git status --short
git diff --name-only origin/integration/sprint4-real-input...HEAD
git grep -n -E "DASHSCOPE_API_KEY=|sk-[A-Za-z0-9]|embedding_vector" -- . ":(exclude)docs/superpowers/plans/2026-09-09-v31-rag-corpus-chroma-index.md"
```

Expected: no secret, vector, Chroma database or runtime receipt is tracked.

- [ ] **Step 6: Commit the handoff documentation**

```text
git add docs/sprint5/s5-v3.1-rag-corpus-index-handoff.md docs/sprint5/s5-v3.1-ai-109-closeout.md
git commit -m "docs(rag): add corpus index owner handoff"
```

- [ ] **Step 7: Push the existing PR branch without rewriting history**

```text
git push origin feat/s5-v3.1-ai-backend-integration
```

Keep PR #118 Draft. Do not rebase, force push or merge.
