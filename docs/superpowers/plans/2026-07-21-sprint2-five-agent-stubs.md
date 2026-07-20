# Sprint 2 Five-Agent LangGraph Stub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic five-Agent LangGraph workflow that demonstrates HarmonyAI's Day 4 stubbed end-to-end path and its low-confidence safety branch.

**Architecture:** `agent_stubs.py` creates uniform Agent envelopes without external dependencies. `langgraph_workflow.py` uses a real `StateGraph` to route normal input across Assessment, Diagnosis, Prescription, Generation, and Feedback; diagnosis confidence below `0.4` routes to a review handler and stops safely.

**Tech Stack:** Python 3.10+, LangGraph, pytest, existing PromptEngine.

## Global Constraints

- Do not call Qwen, Chroma, databases, FastAPI, frontend services, or music-generation APIs.
- Every Agent result must include the universal fields from `docs/agent-architecture.md`.
- Normal flow must contain result keys `assessment`, `diagnosis`, `prescription`, `generation`, and `feedback`.
- Empty emotion input must produce `assessment.status == "degraded"` and route to `low_confidence` without prescription or generation.
- Do not stage or modify `guangzhou_news_2026-07-16/`.

---

## File Map

- Modify: `pyproject.toml` — declare the runtime dependency `langgraph`.
- Create: `backend/ai_engine/agent_stubs.py` — uniform envelope factory and five deterministic Agent node functions.
- Create: `backend/ai_engine/langgraph_workflow.py` — workflow State, graph compilation, conditional routing, and `run_stub_workflow`.
- Create: `backend/ai_engine/sprint2_demo.py` — executable normal-flow demo JSON.
- Create: `tests/ai_engine/test_agent_stubs.py` — universal envelope tests.
- Create: `tests/ai_engine/test_langgraph_workflow.py` — normal and low-confidence workflow tests.
- Create: `tests/ai_engine/test_sprint2_demo.py` — demo result test.
- Modify: `README.md` — document the Sprint 2 demo command.

### Task 1: Add the LangGraph dependency and define Agent envelopes

**Files:**

- Modify: `pyproject.toml`
- Create: `backend/ai_engine/agent_stubs.py`
- Create: `tests/ai_engine/test_agent_stubs.py`

**Interfaces:**

- `make_agent_result(*, agent_id: str, agent_name: str, agent_layer: str, run_id: str, session_id: str, user_id: str, status: str, confidence: float, reason: list[str], warnings: list[str], input_data: dict[str, object], output_data: dict[str, object]) -> dict[str, object]`
- `assessment_stub(state: dict[str, object]) -> dict[str, object]`
- `diagnosis_stub(state: dict[str, object]) -> dict[str, object]`
- `prescription_stub(state: dict[str, object]) -> dict[str, object]`
- `generation_stub(state: dict[str, object]) -> dict[str, object]`
- `feedback_stub(state: dict[str, object]) -> dict[str, object]`

- [ ] **Step 1: Write the failing envelope test**

```python
from backend.ai_engine.agent_stubs import assessment_stub


def test_assessment_stub_returns_universal_agent_envelope():
    result = assessment_stub(
        {
            "run_id": "run-1",
            "session_id": "session-1",
            "user_id": "user-1",
            "emotion_scores": {"anxiety": 82},
        }
    )["assessment"]

    required = {
        "agent_id", "agent_version", "agent_name", "agent_layer", "run_id",
        "session_id", "user_id", "status", "confidence", "reason", "warnings",
        "input", "output", "processing_time_ms", "timestamp", "retry_count",
    }
    assert required.issubset(result)
    assert result["agent_id"] == "evaluation_agent"
    assert result["status"] == "success"
```

- [ ] **Step 2: Verify the test fails before implementation**

Run: `python -m pytest tests/ai_engine/test_agent_stubs.py -q`

Expected: collection fails because `backend.ai_engine.agent_stubs` does not exist.

- [ ] **Step 3: Add the dependency and minimal stub implementation**

Add `"langgraph>=0.2"` to `[project].dependencies` in `pyproject.toml`. Implement `make_agent_result` with `agent_version="1.0.0"`, `processing_time_ms=0`, an ISO-8601 UTC timestamp, and `retry_count=0`. Implement `assessment_stub` so a non-empty `emotion_scores` mapping returns `success`, confidence `0.85`, and `output.emotion_profile` containing the submitted scores; empty input returns `degraded`, confidence `0.3`, and warning `"输入不足，建议补充问卷"`.

- [ ] **Step 4: Verify the test passes**

Run: `python -m pytest tests/ai_engine/test_agent_stubs.py -q`

Expected: 1 passed.

- [ ] **Step 5: Commit the isolated task**

```powershell
git add pyproject.toml backend/ai_engine/agent_stubs.py tests/ai_engine/test_agent_stubs.py
git commit -m "feat: add agent stub envelopes"
```

### Task 2: Implement five deterministic Agent nodes

**Files:**

- Modify: `backend/ai_engine/agent_stubs.py`
- Modify: `tests/ai_engine/test_agent_stubs.py`

**Interfaces:**

- `diagnosis_stub` consumes `state["assessment"]` and returns `{"diagnosis": envelope}`.
- `prescription_stub` consumes `state["diagnosis"]` and returns `{"prescription": envelope}`.
- `generation_stub` consumes `state["prescription"]` and returns `{"generation": envelope}`.
- `feedback_stub` consumes `state["generation"]` and returns `{"feedback": envelope}`.

- [ ] **Step 1: Write failing node tests**

```python
from backend.ai_engine.agent_stubs import (
    assessment_stub,
    diagnosis_stub,
    feedback_stub,
    generation_stub,
    prescription_stub,
)


def test_stub_nodes_produce_schema_shaped_handoff_data():
    state = {"run_id": "run-1", "session_id": "session-1", "user_id": "user-1", "emotion_scores": {"anxiety": 82}}
    state.update(assessment_stub(state))
    state.update(diagnosis_stub(state))
    state.update(prescription_stub(state))
    state.update(generation_stub(state))
    state.update(feedback_stub(state))

    assert state["diagnosis"]["output"]["syndrome_diagnosis"]["primary"]["name"] == "肝郁化火"
    assert state["prescription"]["output"]["music_feature"]["tone_id"] == "jiao"
    assert state["generation"]["output"]["audio"]["url"].startswith("local://")
    assert state["feedback"]["output"]["decision"]["action"] == "continue"
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `python -m pytest tests/ai_engine/test_agent_stubs.py -q`

Expected: FAIL because diagnosis, prescription, generation, and feedback stub functions are missing.

- [ ] **Step 3: Implement deterministic handoff outputs**

`diagnosis_stub` must output primary syndrome `肝郁化火`, element `木`, organ `肝`, severity level `3`, and confidence `0.85` for normal input. `prescription_stub` must output `music_feature` with `tone_id="jiao"`, `bpm=68`, and instruments `古筝` and `古琴`; it must render `CN_V1` using the existing `PromptEngine`. `generation_stub` must output `audio.url="local://music/jiao-demo.mp3"`. `feedback_stub` must output `decision.action="continue"`.

- [ ] **Step 4: Verify the tests pass**

Run: `python -m pytest tests/ai_engine/test_agent_stubs.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit the isolated task**

```powershell
git add backend/ai_engine/agent_stubs.py tests/ai_engine/test_agent_stubs.py
git commit -m "feat: add five deterministic agent stubs"
```

### Task 3: Build the LangGraph workflow and low-confidence route

**Files:**

- Create: `backend/ai_engine/langgraph_workflow.py`
- Create: `tests/ai_engine/test_langgraph_workflow.py`

**Interfaces:**

- `build_stub_graph() -> CompiledStateGraph`
- `run_stub_workflow(*, user_id: str, session_id: str, emotion_scores: dict[str, int]) -> dict[str, object]`
- `low_confidence_handler(state: dict[str, object]) -> dict[str, object]`

- [ ] **Step 1: Write failing workflow tests**

```python
from backend.ai_engine.langgraph_workflow import run_stub_workflow


def test_normal_input_runs_all_five_agents_in_order():
    result = run_stub_workflow(
        user_id="user-1",
        session_id="session-1",
        emotion_scores={"anxiety": 82},
    )

    assert [key for key in ("assessment", "diagnosis", "prescription", "generation", "feedback") if key in result] == [
        "assessment", "diagnosis", "prescription", "generation", "feedback"
    ]
    assert result["feedback"]["status"] == "success"


def test_empty_input_routes_to_low_confidence_handler():
    result = run_stub_workflow(user_id="user-1", session_id="session-1", emotion_scores={})

    assert result["assessment"]["status"] == "degraded"
    assert result["low_confidence"]["status"] == "success"
    assert "prescription" not in result
    assert "generation" not in result
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `python -m pytest tests/ai_engine/test_langgraph_workflow.py -q`

Expected: collection fails because `langgraph_workflow` does not exist.

- [ ] **Step 3: Implement the graph**

Create a `TypedDict` State with optional Agent result keys. Add nodes `assessment`, `diagnosis`, `prescription`, `generation`, `feedback`, and `low_confidence`. Use `START -> assessment -> diagnosis`; add a conditional edge after diagnosis that returns `"low_confidence"` when `state["diagnosis"]["confidence"] < 0.4`, otherwise `"prescription"`. Connect normal nodes in order and terminate both feedback and low-confidence nodes with `END`. `low_confidence_handler` must produce a success envelope with warning `"建议专业人员复核"` and output `{"action": "recommend_professional"}`.

- [ ] **Step 4: Verify the tests pass**

Run: `python -m pytest tests/ai_engine/test_langgraph_workflow.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit the isolated task**

```powershell
git add backend/ai_engine/langgraph_workflow.py tests/ai_engine/test_langgraph_workflow.py
git commit -m "feat: add LangGraph agent stub workflow"
```

### Task 4: Add the Sprint 2 demo and operator documentation

**Files:**

- Create: `backend/ai_engine/sprint2_demo.py`
- Create: `tests/ai_engine/test_sprint2_demo.py`
- Modify: `README.md`

**Interfaces:**

- `run_demo() -> dict[str, object]`

- [ ] **Step 1: Write the failing demo test**

```python
from backend.ai_engine.sprint2_demo import run_demo


def test_sprint2_demo_returns_full_stubbed_closed_loop():
    result = run_demo()

    assert result["generation"]["output"]["audio"]["url"] == "local://music/jiao-demo.mp3"
    assert result["feedback"]["output"]["decision"]["action"] == "continue"
```

- [ ] **Step 2: Verify the test fails before implementation**

Run: `python -m pytest tests/ai_engine/test_sprint2_demo.py -q`

Expected: collection fails because `sprint2_demo` does not exist.

- [ ] **Step 3: Implement the demo and README instructions**

`run_demo()` must call `run_stub_workflow(user_id="demo-user", session_id="sprint2-demo", emotion_scores={"anxiety": 82, "anger": 60})`. When executed as a module, print pretty UTF-8 JSON. Add `python -m backend.ai_engine.sprint2_demo` to the README's AI Engineering section, and label it as the Sprint 2 Day 4 stub demo.

- [ ] **Step 4: Verify demo and full test suite**

Run: `python -m pytest -q`

Expected: all existing and new tests pass.

Run: `python -m backend.ai_engine.sprint2_demo`

Expected: JSON containing `assessment`, `diagnosis`, `prescription`, `generation`, and `feedback`.

- [ ] **Step 5: Commit the isolated task**

```powershell
git add backend/ai_engine/sprint2_demo.py tests/ai_engine/test_sprint2_demo.py README.md
git commit -m "feat: add Sprint 2 stub demo"
```

## Final Verification

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m backend.ai_engine.sprint2_demo`.
- [ ] Run `git diff --check`.
- [ ] Run `git status --short` and confirm only Sprint 2 files are staged/committed; preserve `guangzhou_news_2026-07-16/` as untracked.
- [ ] Push only `feat/zhongrc` and update PR #23 after review approval.

