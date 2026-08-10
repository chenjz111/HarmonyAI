# HarmonyAI Sprint 3 Backend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏 v1 的前提下，把 session、document upload 和 Feedback 2.0 稳定集成到 dev，并消除 PR #46 的 4 个失败。

**Architecture:** 从最新 dev 建立修复分支，以 origin/feat/caizx 为来源进行普通合并；先用测试固定 v1 错误壳、测试数据库、反馈和错误脱敏，再做最小实现。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy、SQLite 测试数据库、pytest、TestClient。

## Global Constraints

- 分支名固定为 fix/sprint3-backend-integration。
- v1 路由和 UniversalOutput 保持兼容。
- v2 统一返回 success/data/error/meta。
- 上传只允许 JPG、PNG、PDF，最大 10 MB，PDF 最大 3 页。
- 对外错误不得包含数据库连接信息或堆栈。
- 反馈只能更新个人偏好，global_rule_update 必须为 false。

---

### Task 1: 建立干净修复分支并复现失败

**Files:**
- Merge source: `origin/feat/caizx`
- Test: `tests/api/test_feedback_v2.py`
- Test: `tests/api/test_v1_feedback_compatibility.py`

**Interfaces:**
- Consumes: 最新 origin/dev。
- Produces: 包含成员原始实现、尚未修复的可复现基线。

- [ ] **Step 1: 创建隔离 worktree**

```powershell
git fetch origin
git worktree add -b fix/sprint3-backend-integration C:/Users/ASUS/Desktop/HarmonyAI-worktrees/sprint3-backend origin/dev
```

- [ ] **Step 2: 普通合并成员分支**

```powershell
git merge --no-ff origin/feat/caizx -m "merge: integrate Sprint 3 backend contribution"
```

- [ ] **Step 3: 运行失败测试并保存证据**

```powershell
python -m pytest tests/api/test_feedback_v2.py tests/api/test_v1_feedback_compatibility.py -v
```

Expected: 修复前复现 4 个失败；不能在未复现时猜测修改。

### Task 2: 为 API 测试隔离数据库

**Files:**
- Create: `tests/api/conftest.py`
- Modify if required: `backend/app/core/database.py`
- Test: `tests/api/test_feedback_v2.py`
- Test: `tests/api/test_v1_feedback_compatibility.py`

**Interfaces:**
- Consumes: FastAPI dependency `get_db`。
- Produces: 每个测试使用临时 SQLite schema，不访问本机 MySQL。

- [ ] **Step 1: 写数据库隔离夹具**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: 在 fixture 中创建表、覆盖依赖并在结束时恢复**

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 3: 运行目标测试**

```powershell
python -m pytest tests/api/test_feedback_v2.py tests/api/test_v1_feedback_compatibility.py -v
```

Expected: 不再出现 MySQL root 登录错误；剩余失败只反映业务逻辑。

- [ ] **Step 4: 提交测试基础设施**

```powershell
git add tests/api/conftest.py backend/app/core/database.py
git commit -m "test: isolate Sprint 3 API database"
```

### Task 3: 修复 v1 UniversalOutput 错误响应

**Files:**
- Modify: `backend/app/core/exceptions.py`
- Test: `tests/api/test_v1_feedback_compatibility.py`
- Test: `tests/ai_engine/test_agent_stubs.py`

**Interfaces:**
- Consumes: UniversalOutput.warnings 为 list[str]。
- Produces: 可序列化、无二次 ValidationError 的 v1 降级响应。

- [ ] **Step 1: 增加错误响应回归断言**

```python
def test_v1_internal_error_uses_string_warnings(monkeypatch, client):
    response = client.post("/api/v1/feedback", json={
        "session_id": "sess_error",
        "rating": 4,
    })
    payload = response.json()
    assert isinstance(payload["warnings"], list)
    assert all(isinstance(item, str) for item in payload["warnings"])
    assert "mysql" not in " ".join(payload["reason"]).lower()
```

- [ ] **Step 2: 确认测试在旧实现失败**

```powershell
python -m pytest tests/api/test_v1_feedback_compatibility.py -v
```

- [ ] **Step 3: 让 build_error_response 使用安全字符串**

```python
public_message = error.message if isinstance(error, AgentException) else "服务暂时不可用，请稍后重试"
warnings = [f"{error_code}: {public_message}"]
```

UniversalOutput 的 reason 和 warnings 只能使用 public_message；原始异常用 logger.exception 记录，不返回客户端。

- [ ] **Step 4: 运行兼容测试并提交**

```powershell
python -m pytest tests/api/test_v1_feedback_compatibility.py tests/ai_engine/test_agent_stubs.py -v
git add backend/app/core/exceptions.py tests/api/test_v1_feedback_compatibility.py
git commit -m "fix: preserve v1 error response compatibility"
```

### Task 4: 修复 Feedback 2.0 成功路径和错误脱敏

**Files:**
- Modify: `backend/app/routers/feedback_router.py`
- Modify: `backend/app/schemas/v2.py`
- Modify: `backend/app/models/feedback.py`
- Test: `tests/api/test_feedback_v2.py`

**Interfaces:**
- Consumes: FeedbackV2Request、PlaybackData 和 SQLAlchemy Session。
- Produces: personal_preference_patch、subjective_change、global_rule_update=false。

- [ ] **Step 1: 增加无 playback、数据库失败和边界值测试**

```python
def test_v2_feedback_without_playback_succeeds(client):
    payload = {
        "session_id": "sess_no_playback",
        "pre_state": {"tension": 7, "body_tension": 6, "mental_fatigue": 8, "goal": "sleep"},
        "post_state": {"tension": 5, "body_tension": 4, "mental_fatigue": 6, "change_label": "better"},
        "experience": {"continue_use": "yes", "favorite": False},
    }
    data = client.post("/api/v2/feedback", json=payload).json()
    assert data["success"] is True
    assert data["data"]["global_rule_update"] is False
```

- [ ] **Step 2: 运行测试确认旧实现失败**

```powershell
python -m pytest tests/api/test_feedback_v2.py -v
```

- [ ] **Step 3: 导入 PlaybackData 并使用验证后的可选值**

```python
from backend.app.schemas.v2 import (
    FeedbackV2Request,
    PlaybackData,
    v2_err,
    v2_ok,
)

pb = validated.playback or PlaybackData(
    listened_seconds=0,
    duration_seconds=0,
    completion_rate=0,
)
```

- [ ] **Step 4: 统一异常响应为公共文案**

```python
except Exception:
    db.rollback()
    logger.exception("feedback_v2 failed", extra={"session_id": session_id})
    return v2_err(
        "FEEDBACK_FAILED",
        "反馈保存失败，请稍后重试",
        req_id,
        retryable=True,
        next_actions=["retry_feedback"],
    )
```

- [ ] **Step 5: 运行测试并提交**

```powershell
python -m pytest tests/api/test_feedback_v2.py tests/api/test_v1_feedback_compatibility.py -v
git add backend/app/routers/feedback_router.py backend/app/schemas/v2.py backend/app/models/feedback.py tests/api/test_feedback_v2.py
git commit -m "fix: stabilize Feedback 2.0 persistence"
```

### Task 5: 固化文档上传安全与清理

**Files:**
- Modify: `backend/app/routers/document_router.py`
- Modify: `backend/app/core/ocr.py`
- Create: `tests/api/test_document_v2.py`

**Interfaces:**
- Consumes: multipart file、session_id、document_type、consent_confirmed。
- Produces: document_id、ocr_status、extracted_text、warnings 和可确认状态。

- [ ] **Step 1: 创建上传边界测试**

```python
def test_document_rejects_signature_mismatch(client):
    files = {"file": ("fake.pdf", b"not-a-pdf", "application/pdf")}
    data = client.post(
        "/api/v2/documents",
        data={"session_id": "sess_doc", "consent_confirmed": "true"},
        files=files,
    ).json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_SIGNATURE"
```

同时覆盖无授权、超过 10 MB、超过 3 页、OCR stub、确认、跳过和删除。

- [ ] **Step 2: 运行上传测试确认缺口**

```powershell
python -m pytest tests/api/test_document_v2.py -v
```

- [ ] **Step 3: 使用临时上传根目录并保证失败清理**

上传目录从配置或依赖注入获得；测试使用 tmp_path。数据库失败、OCR 失败和删除操作都断言文件不会残留。

- [ ] **Step 4: 对错误消息脱敏并运行测试**

```powershell
python -m pytest tests/api/test_document_v2.py -v
git add backend/app/routers/document_router.py backend/app/core/ocr.py tests/api/test_document_v2.py
git commit -m "test: enforce document upload safety"
```

### Task 6: 完整验证、PR 和替代说明

**Files:**
- Verify: `backend/`
- Verify: `tests/`

**Interfaces:**
- Consumes: Tasks 1-5。
- Produces: 可合并后端 PR 和 PR #46 的可追溯替代关系。

- [ ] **Step 1: 运行完整测试**

```powershell
python -m pytest tests -v
```

Expected: 0 failed；测试数以本次命令真实输出为准。

- [ ] **Step 2: 检查范围与敏感信息**

```powershell
git diff --check origin/dev...HEAD
git diff --name-status origin/dev...HEAD
git diff origin/dev...HEAD | rg -n "sk-[A-Za-z0-9._-]{16,}|DATABASE_URL=|QWEN_API_KEY"
```

- [ ] **Step 3: 推送并创建 PR**

```powershell
git push -u origin fix/sprint3-backend-integration
gh pr create --repo chenjz111/HarmonyAI --base dev --head fix/sprint3-backend-integration --title "fix: stabilize Sprint 3 backend integration" --body "Integrates PR #46 on latest dev; fixes isolated test DB, v1 error shell, Feedback 2.0, upload safety and public error sanitization. Verification: python -m pytest tests -v."
```

PR 正文记录原 PR #46、失败复现、修复提交、完整测试和未实现的真实 OCR。

- [ ] **Step 4: 审查通过后普通 Merge Commit**

```powershell
$backendPr = gh pr list --repo chenjz111/HarmonyAI --head fix/sprint3-backend-integration --json number --jq '.[0].number'
gh pr merge $backendPr --repo chenjz111/HarmonyAI --merge
```

- [ ] **Step 5: 关闭 PR #46 但保留分支**

```powershell
gh pr comment 46 --repo chenjz111/HarmonyAI --body "有效实现已通过新的稳定集成 PR 合并；新 PR 同时修复测试数据库、v1 错误壳、Feedback 2.0 和错误脱敏问题。保留原分支用于追溯。"
gh pr close 46 --repo chenjz111/HarmonyAI
```
