# HarmonyAI Sprint 6 — Canonical Acceptance Runtime Contract

> Status: **FROZEN CONTRACT (non-secret)**
> Phase: Sprint 6 Phase 0
> This document contains **no secret values**. Only host/port/path/key-name information is recorded.
> Runtime env values stay outside git, permanently.

---

## 1. Network contract

| Item | Value |
|---|---|
| Backend host | `127.0.0.1` |
| Acceptance backend port | `8010` |
| Acceptance backend base URL | `http://127.0.0.1:8010` |
| Health check | `GET http://127.0.0.1:8010/health` |
| API docs | `http://127.0.0.1:8010/docs` |
| Android device bridge | `adb reverse tcp:8010 tcp:8010` |

**Android acceptance procedure:** establish the reverse tunnel **before** exercising the app on
the device, so the device's `127.0.0.1:8010` resolves to the host backend:

```
adb reverse tcp:8010 tcp:8010
```

The backend must be launched bound to `127.0.0.1` on port `8010`, for example:

```
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

`--host 0.0.0.0` is **not** part of the Sprint 6 acceptance contract; the accepted Sprint 5
Android run used `127.0.0.1` plus `adb reverse`, and Sprint 6 keeps that.

---

## 2. Port policy (important)

| Context | Port | Where it lives |
|---|---|---|
| **Repo / frontend default** | **`8000`** | `frontend/common/api-v3.js` (`BASE_URL` fallback), `frontend/common/api-v2.js`, `frontend/common/api.js`, `README.md`, `HANDOFF.md` |
| **Acceptance runtime only** | **`8010`** | runtime configuration, supplied via `VITE_API_BASE_URL` at build/serve time, plus `adb reverse` |

Rules:

1. The **repo frontend default remains port `8000`.** The committed default must not be changed.
2. **Android acceptance port `8010` is runtime configuration.**
3. **Do not hardcode `8010` into `frontend/common/api-v3.js` again.** Sprint 5's working tree
   contained exactly such an edit (`localhost:8000` / `127.0.0.1:8000` → `127.0.0.1:8010`); it was
   deliberately **not committed** during closeout, and its diff was preserved outside the repo
   (see §5). Acceptance must select the port through `VITE_API_BASE_URL`, not by editing the
   committed default.

Any change to the committed default port requires an explicit Owner decision and a documentation
update in this file.

---

## 3. Canonical acceptance DB

```
C:\Users\ASUS\HarmonyAI-acceptance-runtime\final-e2e.db
```

- Owner-designated canonical acceptance DB from Sprint 6 onward.
- All acceptance evidence must name this path.
- Acceptance runs must use an **absolute** `DATABASE_URL` (as the runtime env already does). The
  in-repo default `sqlite:///./harmonyai.db` is CWD-relative and silently creates a second, empty
  database when the backend is launched from a different directory.
- The DB must be opened read-only when used for baseline/reporting purposes.
- Sprint 6 must not modify this DB for baseline purposes.

---

## 4. External runtime env file

```
C:\Users\ASUS\HarmonyAI-acceptance-runtime\acceptance-async-final.env
```

- This file lives **outside the repository** and is **never committed**.
- `runtime env values stay outside git.` No value from this file may be copied into the repo,
  into a doc, into a fixture, into a test, or into a commit message.

### 4.1 Env key names (names only — no values)

Required keys for a Sprint 6 acceptance runtime:

| Key | Purpose |
|---|---|
| `HARMONYAI_REAL_AGENTS` | master switch for the real AI chain |
| `DATABASE_URL` | absolute path to the canonical acceptance DB |
| `DASHSCOPE_BASE_URL` | DashScope-compatible API base |
| `DASHSCOPE_API_KEY` | DashScope credential — **secret** |
| `DASHSCOPE_WORKSPACE_ID` | DashScope workspace identifier |
| `QWEN_MODEL` | Qwen model id used by Agent 1/2 providers |
| `EMBEDDING_PROVIDER` | embedding provider selection |
| `EMBEDDING_MODEL` | embedding model id |
| `EMBEDDING_DIMENSION` | embedding vector dimension |
| `CHROMA_PERSIST_DIRECTORY` | Chroma persistence directory |
| `CHROMA_COLLECTION` | Chroma collection name |
| `MUSIC_PROVIDER` | music generation provider selection |
| `TOKENHUB_BASE_URL` | music provider base URL |
| `TOKENHUB_API_KEY` | music provider credential — **secret** |
| `TOKENHUB_MUSIC_MODEL` | music model id |

Additional keys present in the Sprint 5 acceptance env (also names only, for completeness):
`QWEN_BASE_URL`, `RAG_CORPUS_MANIFEST_PATH`, `RAG_CORPUS_CHUNKS_PATH`, `HARMONY_MEDIA_ROOT`,
`V31_MEDICAL_RULE_VERSION`, `V31_MEDICAL_RULE_ASSET_PATH`, `V31_MEDICAL_RULE_ASSET_CHECKSUM`,
`V31_MUSIC_GENERATION_RULES_PATH`, `V31_MUSIC_GENERATION_RULES_VERSION`,
`V31_MUSIC_GENERATION_RULES_CHECKSUM`.

**Secret handling:** `DASHSCOPE_API_KEY` and `TOKENHUB_API_KEY` (and any equivalent credential)
are secrets. They are never printed, logged, echoed in reports, or committed. Reports may
reference the key **name** and whether a value is present; never the value.

---

## 5. Local acceptance-config reference patch

During Sprint 5 closeout the two machine-local acceptance edits were captured outside the repo
before being reverted to HEAD:

```
C:\Users\ASUS\HarmonyAI-acceptance-runtime\s5-local-acceptance-config.patch
```

It contains only the local diff of `frontend/common/api-v3.js` (port 8000 → 8010) and
`frontend/manifest.json` (HBuilderX `appid` + `ios.dSYMs` + re-indent). It is **not** in git and
exists solely as a local reference for rebuilding the acceptance runtime.

---

## 6. Runtime paths that must stay outside the repository

| Path | Content |
|---|---|
| `C:\Users\ASUS\HarmonyAI-acceptance-runtime\final-e2e.db` | canonical acceptance DB |
| `C:\Users\ASUS\HarmonyAI-acceptance-runtime\acceptance-async-final.env` | runtime env (secrets) |
| `C:\Users\ASUS\HarmonyAI-acceptance-runtime\chroma-v31\` | runtime vector index |
| `C:\Users\ASUS\HarmonyAI-acceptance-runtime\media\`, `media-final\` | generated audio |
| `C:\Users\ASUS\HarmonyAI-acceptance-runtime\*.log` | backend/H5 run logs (may contain OCR text) |
| `C:\Users\ASUS\HarmonyAI-acceptance-runtime\s5-local-acceptance-config.patch` | local config reference |

In-repo runtime artifacts (`uploads/`, `media/`, `.chroma-v31/`, `*.db`) are root-ignored and must
never be staged.

---

## 7. Chroma / knowledge baseline (read-only, unchanged)

| Item | Value |
|---|---|
| Collection | `harmony_v31_medical_v3.1-approved.1_text-embedding-v4_1024_d1024` |
| Embedding model / dimension | `text-embedding-v4` / `1024` |
| Distance metric | `cosine` |
| Chunks indexed | 13 (matches the approved corpus and ingestion manifest) |
| Knowledge version | `medical_v3.1-approved.1` |
| Score semantics | `normalized_similarity` = `1 / (2 - cosine)`; `minimum_score` = `0.740741` |

The runtime vector index is a rebuildable artifact and is never committed. Source knowledge assets
under `knowledge/**` are tracked and are the only committable knowledge source of truth. No
reindexing or index modification is part of Phase 0.
