# AI Engineering Sprint 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable, dependency-light Prompt Engine and two-node AI workflow with replaceable LLM/vector adapters and deterministic fallbacks.

**Architecture:** Keep the business workflow independent from LangGraph, Qwen, and Chroma through small protocols. Use a versioned text template for runtime prompt assembly, deterministic rules for the local demo, and JSON-compatible structured results matching the repository's Agent Schema conventions.

**Tech Stack:** Python 3.10+, standard library dataclasses/protocols, pytest, optional LangGraph/Qwen/Chroma adapters deferred behind interfaces.

## Global Constraints

- Follow Knowledge First, Explainability, Human in the Loop, Modular Design, and Fail Gracefully.
- Do not implement FastAPI, databases, frontend, real medical diagnosis, or real audio generation.
- Prompt is assembled at runtime and is not persisted in the Agent Schema object.
- Low confidence below `0.4` must produce a professional-review warning.
- Tests must run without network access, model services, or a persistent vector database.

## File Map

- Create: `backend/__init__.py` — package marker.
- Create: `backend/ai_engine/__init__.py` — public AI engine exports.
- Create: `backend/ai_engine/models.py` — typed state and result dataclasses.
- Create: `backend/ai_engine/prompt_engine.py` — template loading and safe assembly.
- Create: `backend/ai_engine/providers.py` — provider protocols and fallbacks.
- Create: `backend/ai_engine/workflow.py` — evaluation and prescription nodes.
- Create: `prompt/v1/CN_V1.txt` — versioned prompt template.
- Create: `tests/ai_engine/test_prompt_engine.py` — prompt behavior tests.
- Create: `tests/ai_engine/test_providers.py` — fallback behavior tests.
- Create: `tests/ai_engine/test_workflow.py` — workflow behavior tests.
- Create: `tests/ai_engine/test_package.py` — package import smoke test.
- Create: `tests/ai_engine/test_demo.py` — offline demo smoke test.
- Create: `pyproject.toml` — test and package configuration.
- Create: `README.md` additions — local AI engineering demo instructions.

### Task 1: Add package and test configuration

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/ai_engine/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/ai_engine/__init__.py`
- Create: `pyproject.toml`

- [ ] **Step 1: Write the package smoke test**

```python
def test_ai_engine_package_imports():
    import backend.ai_engine

    assert backend.ai_engine is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/ai_engine/test_package.py -q`
Expected: FAIL because the package and test file do not exist yet.

- [ ] **Step 3: Add the package markers and pytest configuration**

Use empty package markers and configure pytest with `pythonpath = ["."]` in `pyproject.toml`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/ai_engine/test_package.py -q`
Expected: PASS.

### Task 2: Implement versioned Prompt Engine

**Files:**
- Create: `backend/ai_engine/prompt_engine.py`
- Create: `prompt/v1/CN_V1.txt`
- Create: `tests/ai_engine/test_prompt_engine.py`

**Interfaces:**
- `PromptEngine(template_root: Path)`
- `PromptEngine.render(template_id: str, params: Mapping[str, object]) -> RenderedPrompt`
- `RenderedPrompt.text: str`
- `RenderedPrompt.template_id: str`
- `RenderedPrompt.template_version: str`
- `TemplateNotFoundError`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

import pytest

from backend.ai_engine.prompt_engine import PromptEngine, TemplateNotFoundError


def test_render_includes_structured_music_parameters():
    engine = PromptEngine(Path("prompt/v1"))

    result = engine.render("CN_V1", {"duration": 15, "bpm": 68, "tone": "角调式"})

    assert result.template_version == "1.0.0"
    assert "15分钟" in result.text
    assert "68 BPM" in result.text
    assert "角调式" in result.text


def test_missing_template_raises_explicit_error():
    engine = PromptEngine(Path("prompt/v1"))

    with pytest.raises(TemplateNotFoundError):
        engine.render("MISSING", {})


def test_missing_optional_parameter_uses_safe_fallback():
    engine = PromptEngine(Path("prompt/v1"))

    result = engine.render("CN_V1", {"duration": 15})

    assert "60 BPM" in result.text
    assert "纯音乐" in result.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/ai_engine/test_prompt_engine.py -q`
Expected: FAIL with import or missing implementation errors.

- [ ] **Step 3: Add the template and minimal renderer**

The template must declare `template_version=1.0.0` and use `{duration}`, `{bpm}`, `{tone}`, and `{style}` placeholders. The renderer must provide defaults `duration=15`, `bpm=60`, `tone=宫调式`, `style=纯音乐`, and raise `TemplateNotFoundError` when `CN_V1.txt` is absent.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/ai_engine/test_prompt_engine.py -q`
Expected: 3 passed.

### Task 3: Add provider protocols and deterministic fallbacks

**Files:**
- Create: `backend/ai_engine/providers.py`
- Create: `tests/ai_engine/test_providers.py`

**Interfaces:**
- `LLMProvider.complete(prompt: str) -> str`
- `VectorStore.search(query: str, limit: int = 5) -> list[KnowledgeHit]`
- `FallbackLLMProvider.complete(prompt: str) -> str`
- `InMemoryVectorStore.add(text: str, metadata: Mapping[str, str]) -> None`
- `InMemoryVectorStore.search(query: str, limit: int = 5) -> list[KnowledgeHit]`

- [ ] **Step 1: Write failing tests**

```python
from backend.ai_engine.providers import FallbackLLMProvider, InMemoryVectorStore


def test_fallback_llm_returns_explainable_rule_response():
    result = FallbackLLMProvider().complete("请分析肝郁化火")

    assert "规则引擎" in result
    assert "仅供参考" in result


def test_memory_vector_store_returns_matching_knowledge_first():
    store = InMemoryVectorStore()
    store.add("角调与木、肝相关", {"source": "demo-source"})
    store.add("宫调与土、脾相关", {"source": "other-source"})

    hits = store.search("肝 角调", limit=1)

    assert len(hits) == 1
    assert hits[0].metadata["source"] == "demo-source"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/ai_engine/test_providers.py -q`
Expected: FAIL because provider types are not implemented.

- [ ] **Step 3: Implement minimal protocols and fallbacks**

Use token overlap scoring in `InMemoryVectorStore`; return an empty list for blank queries. The fallback LLM must never claim a medical diagnosis and must include a review disclaimer.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/ai_engine/test_providers.py -q`
Expected: 2 passed.

### Task 4: Implement the two-node structured workflow

**Files:**
- Create: `backend/ai_engine/models.py`
- Create: `backend/ai_engine/workflow.py`
- Create: `tests/ai_engine/test_workflow.py`

**Interfaces:**
- `WorkflowInput(user_id: str, session_id: str, emotion_scores: Mapping[str, int])`
- `run_workflow(input: WorkflowInput, prompt_engine: PromptEngine) -> WorkflowResult`
- `WorkflowResult.evaluation: EvaluationResult`
- `WorkflowResult.prescription: PrescriptionResult`
- `WorkflowResult.to_dict() -> dict[str, object]`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

from backend.ai_engine.prompt_engine import PromptEngine
from backend.ai_engine.models import WorkflowInput
from backend.ai_engine.workflow import run_workflow


def test_workflow_maps_highest_emotion_to_structured_prescription():
    result = run_workflow(
        WorkflowInput("u1", "s1", {"anxiety": 82, "anger": 60}),
        PromptEngine(Path("prompt/v1")),
    )

    assert result.evaluation.agent_id == "evaluation_agent"
    assert result.prescription.agent_id == "prescription_agent"
    assert result.prescription.tone_id == "jiao"
    assert result.prescription.bpm == 68
    assert "角调式" in result.prescription.prompt.text


def test_empty_emotions_use_fallback_and_review_warning():
    result = run_workflow(
        WorkflowInput("u1", "s1", {}),
        PromptEngine(Path("prompt/v1")),
    )

    assert result.evaluation.confidence < 0.4
    assert result.evaluation.warnings["recommend_professional"] is True
    assert any("fallback" in reason for reason in result.evaluation.reason)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/ai_engine/test_workflow.py -q`
Expected: FAIL because workflow models and nodes are not implemented.

- [ ] **Step 3: Implement models and nodes**

The evaluation node selects the highest emotion score, maps `anxiety` to `jiao`, `anger` to `jiao`, `fear` to `yu`, and blank input to `gong` with confidence `0.3`. The prescription node maps `jiao` to `角调式`, `yu` to `羽调式`, and `gong` to `宫调式`, then renders `CN_V1`. Every result includes `agent_id`, `agent_version`, `confidence`, `reason`, `processing_time_ms`, and `timestamp`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/ai_engine/test_workflow.py -q`
Expected: 2 passed.

### Task 5: Add an offline demo and documentation

**Files:**
- Create: `backend/ai_engine/demo.py`
- Modify: `README.md`

- [ ] **Step 1: Write a failing demo smoke test**

```python
def test_offline_demo_returns_json_compatible_result():
    from backend.ai_engine.demo import run_demo

    result = run_demo()

    assert result["prescription"]["tone_id"] == "jiao"
    assert isinstance(result["prescription"]["prompt"]["text"], str)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/ai_engine/test_demo.py -q`
Expected: FAIL because `run_demo` does not exist.

- [ ] **Step 3: Implement the offline demo and document the command**

`run_demo()` must instantiate only local components and return `WorkflowResult.to_dict()`. Add the command `python -m backend.ai_engine.demo` and the test command `python -m pytest -q` to README.

- [ ] **Step 4: Run the test and demo**

Run: `python -m pytest -q`
Expected: all tests pass.

Run: `python -m backend.ai_engine.demo`
Expected: JSON output containing `evaluation` and `prescription`.

## Final Verification

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m backend.ai_engine.demo` with network disabled.
- [ ] Inspect `git diff --check` for whitespace errors.
- [ ] Confirm no external API keys or personal data are committed.
- [ ] Report the `.git` permission limitation if committing remains blocked.
