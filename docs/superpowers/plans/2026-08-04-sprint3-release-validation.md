# HarmonyAI Sprint 3 Release Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用自动化测试和可重复人工步骤证明 Sprint 3 三条比赛场景可运行，并形成可追溯发布结果。

**Architecture:** 从最新 dev 创建 release/sprint3-competition，只接受阻断缺陷修复。后端测试、前端构建、真实服务烟测和失败注入全部通过后创建发布 PR。

**Tech Stack:** pytest、FastAPI TestClient、Node test、uni-app H5 build、PowerShell、GitHub CLI。

## Global Constraints

- 发布分支不增加新功能。
- 测试数、Commit SHA 和日期必须取自真实命令输出。
- 演示不得依赖真实患者资料或把 Stub OCR 描述为真实 OCR。
- 本地音乐必须声明 matched。
- 未通过失败降级场景时不得标记 Sprint 3 完成。

---

### Task 1: 创建发布分支与自动 E2E 骨架

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_sprint3_competition_flow.py`
- Create: `tests/e2e/fixtures/confirmed_document.txt`
- Create: `frontend/tests/sprint3-release-contract.test.mjs`

**Interfaces:**
- Consumes: 最新 dev 的 v2 API 和前端页面。
- Produces: 无材料、有材料、失败降级三条测试。

- [ ] **Step 1: 创建隔离 worktree**

```powershell
git fetch origin
git worktree add -b release/sprint3-competition C:/Users/ASUS/Desktop/HarmonyAI-worktrees/sprint3-release origin/dev
```

- [ ] **Step 2: 写 E2E 隔离数据库和标准问卷夹具**

```python
@pytest.fixture
def valid_answers():
    return {
        "q01_mood_weather": "cloudy", "q02_tension_worry": 3,
        "q03_overthinking": 3, "q04_irritability_anger": 1,
        "q05_low_mood": 1, "q06_interest_loss": 1,
        "q07_fear_unease": 2, "q08_sleep_disturbance": 3,
        "q09_low_energy": 3, "q10_appetite_change": 2,
        "q11_daily_impact": 2, "q12_physical_safety": ["none"],
    }
```

tests/e2e/conftest.py 的完整隔离夹具：

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.core.database import Base, get_db
from backend.app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 3: 写无材料场景测试**

```python
def test_questionnaire_narrative_flow(client, valid_answers):
    session = client.post("/api/v2/sessions", json={"entry_mode": "full"}).json()["data"]
    assessment = client.post("/api/v2/assessments", json={
        "session_id": session["session_id"],
        "user_id": "demo_user_001",
        "narrative_text": "考试临近，晚上脑子停不下来。",
        "questionnaire_answers": valid_answers,
    }).json()
    assert assessment["success"] is True
    assert assessment["data"]["analysis_mode"] == "narrative_questionnaire"
```

- [ ] **Step 4: 写有材料场景测试**

上传测试文件、确认 OCR 文本后提交 document_id、document_text、narrative_text、questionnaire_answers，并断言 evidence 只引用确认文本。

- [ ] **Step 5: 写 Qwen 失败场景测试**

注入超时 provider，断言 status=degraded、问卷画像仍存在、前端可用提示不包含内部异常。

- [ ] **Step 6: 运行测试确认实际缺口**

```powershell
python -m pytest tests/e2e/test_sprint3_competition_flow.py -v
node --test frontend/tests/sprint3-release-contract.test.mjs
```

### Task 2: 只修复端到端阻断问题

**Files:**
- Modify when implicated: `backend/app/routers/document_router.py`
- Modify when implicated: `backend/app/routers/feedback_router.py`
- Modify when implicated: `backend/ai_engine/assessment_v2.py`
- Modify when implicated: `backend/ai_engine/langgraph_workflow.py`
- Modify when implicated: `frontend/common/api-v2.js`
- Modify when implicated: `frontend/pages/result/result.vue`
- Test: `tests/e2e/test_sprint3_competition_flow.py`

**Interfaces:**
- Consumes: 可复现失败。
- Produces: 不扩大范围的最小修复。

- [ ] **Step 1: 为每个失败建立单独回归断言**

一个失败对应一个测试名称；禁止以放宽断言方式隐藏合同不一致。

- [ ] **Step 2: 运行单个测试确认失败**

```powershell
python -m pytest tests/e2e/test_sprint3_competition_flow.py -x -v
```

- [ ] **Step 3: 修改堆栈指向的最小生产文件**

若问题属于接口命名，修正调用方；若属于字段缺失，按 agent-contract-v2 补齐生产输出；不得在发布分支重新设计 Schema。

- [ ] **Step 4: 运行单测和全 E2E**

```powershell
python -m pytest tests/e2e/test_sprint3_competition_flow.py -v
```

- [ ] **Step 5: 每个独立缺陷单独提交**

```powershell
git add tests/e2e/test_sprint3_competition_flow.py
git add -u -- backend frontend
git diff --cached --name-status
git commit -m "fix: unblock Sprint 3 release scenario"
```

### Task 3: 完整自动化验收

**Files:**
- Verify: `tests/`
- Verify: `frontend/tests/`

**Interfaces:**
- Consumes: 通过的 E2E。
- Produces: 后端、AI、前端的完整证据。

- [ ] **Step 1: 运行后端完整测试**

```powershell
python -m pytest tests -v
```

Expected: 0 failed。

- [ ] **Step 2: 运行前端测试与 H5 构建**

```powershell
cd frontend
node --test tests/*.test.mjs
npm run build:h5
```

Expected: 0 failed，构建退出码 0。

- [ ] **Step 3: 检查旧 Sprint 2 兼容性**

```powershell
python -m pytest tests/ai_engine/test_sprint2_demo.py tests/api/test_v1_feedback_compatibility.py -v
```

- [ ] **Step 4: 安全扫描**

```powershell
git diff --check origin/dev...HEAD
git diff origin/dev...HEAD | rg -n "sk-[A-Za-z0-9._-]{16,}|QWEN_API_KEY=|DATABASE_URL=|真实姓名|身份证"
git status --short | rg "unpackage|dist|\\.venv|uploads"
```

Expected: 三条命令都没有风险输出。

### Task 4: 人工比赛演示验收

**Files:**
- Update: `docs/release-checklist.md`
- Update: `docs/demo-script-sprint3.md`

**Interfaces:**
- Consumes: 本地运行的 FastAPI 和 H5。
- Produces: 陈家智可复演的演示记录。

- [ ] **Step 1: 启动真实后端**

```powershell
$env:PYTHONPATH="."
$env:HARMONYAI_REAL_AGENTS="true"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

API Key 只通过当前 PowerShell 环境注入，不写入命令记录、文档或 Git。

- [ ] **Step 2: 演示无材料完整流程**

使用固定考试压力案例，记录页面、输入、analysis_mode、Music source_type、播放与 Feedback 结果。

- [ ] **Step 3: 演示材料确认流程**

只使用匿名测试材料，确认 OCR Stub 标识清晰；验证修改文字和跳过都可继续。

- [ ] **Step 4: 演示 Qwen 失败降级**

关闭 Qwen 配置后重新提交，确认页面明确显示“已使用问卷与规则完成评估”，而非“分析失败”。

- [ ] **Step 5: 更新演示文档**

只记录实际可见文案、路径和限制；明确“当前 OCR 为 Stub、本地音乐为 matched、结果不构成医学诊断”。

### Task 5: 发布 PR 与最终状态

**Files:**
- Update: `docs/sprint3-final-report.md`
- Update: `docs/release-checklist.md`
- Update: `docs/demo-script-sprint3.md`

**Interfaces:**
- Consumes: 自动化和人工证据。
- Produces: 可审查发布 PR、最终 merge commit 和 GitHub 状态报告。

- [ ] **Step 1: 写入真实证据**

```powershell
git rev-parse HEAD
git log -1 --format="%H %cI %s"
```

将输出的 SHA、时间和测试结果写入报告，不复制计划中的 Expected 数字。

- [ ] **Step 2: 提交文档并推送**

```powershell
git add tests/e2e frontend/tests docs/release-checklist.md docs/demo-script-sprint3.md docs/sprint3-final-report.md
git commit -m "test: validate Sprint 3 competition release"
git push -u origin release/sprint3-competition
```

- [ ] **Step 3: 创建发布 PR**

```powershell
gh pr create --repo chenjz111/HarmonyAI --base dev --head release/sprint3-competition --title "release: validate Sprint 3 competition build" --body "Validates no-document, confirmed-document and OCR/Qwen degradation scenarios; includes full backend tests, frontend tests, H5 build and documented competition limitations."
```

- [ ] **Step 4: 最终审查后普通 Merge Commit**

```powershell
$releasePr = gh pr list --repo chenjz111/HarmonyAI --head release/sprint3-competition --json number --jq '.[0].number'
gh pr merge $releasePr --repo chenjz111/HarmonyAI --merge
```

- [ ] **Step 5: 输出最终状态**

列出分支、各 PR、merge commit、完整测试、E2E 三场景、Milestone、Issues、未完成限制和需要陈家智人工处理的事项。
