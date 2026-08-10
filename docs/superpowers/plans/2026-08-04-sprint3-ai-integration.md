# HarmonyAI Sprint 3 AI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 feat/zhongrc 的三源 Assessment、问卷计分、安全规则和五 Agent V2 工作流集成到最新 dev，同时保留 Sprint 2 行为。

**Architecture:** 从已完成后端集成的 dev 建立 integration/sprint3-ai-v2，普通合并成员分支，逐文件解决 3 个 add/add 冲突。Assessment 先运行确定性问卷和安全规则，再尝试 Qwen；不可用或不可解析时返回 degraded 的问卷结果。

**Tech Stack:** Python、pytest、Pydantic、LangGraph、Qwen-compatible API、现有五 Agent 架构。

## Global Constraints

- Agent ID 固定为 assessment_agent、diagnosis_agent、prescription_agent、music_agent、feedback_agent。
- questionnaire_answers 是 P0 基线；document_text 和 narrative_text 可选。
- 不使用未确认 OCR 文本作为评估证据。
- 不展示模型内部思维链。
- confidence 不得描述为医学诊断准确率。
- Music P0 使用本地曲库匹配，source_type=matched。
- Qwen 未配置、超时、限流、非法 JSON 均须降级。

---

### Task 1: 建立集成分支并记录冲突

**Files:**
- Conflict: `backend/ai_engine/agent_stubs.py`
- Conflict: `tests/ai_engine/test_agent_stubs.py`
- Conflict: `tests/ai_engine/test_sprint2_demo.py`

**Interfaces:**
- Consumes: 最新 origin/dev 与 origin/feat/zhongrc。
- Produces: 可人工解决的 merge state。

- [ ] **Step 1: 创建 worktree**

```powershell
git fetch origin
git worktree add -b integration/sprint3-ai-v2 C:/Users/ASUS/Desktop/HarmonyAI-worktrees/sprint3-ai origin/dev
```

- [ ] **Step 2: 普通合并成员分支**

```powershell
git merge --no-ff origin/feat/zhongrc -m "merge: integrate Sprint 3 AI contribution"
```

Expected: 只出现已知的 3 个 add/add 冲突；若冲突集合扩大，停止并重新审查 dev 变化。

- [ ] **Step 3: 导出双方版本用于逐段比较**

```powershell
git show :2:backend/ai_engine/agent_stubs.py
git show :3:backend/ai_engine/agent_stubs.py
git diff --name-only --diff-filter=U
```

### Task 2: 兼容合并 agent_stubs

**Files:**
- Modify: `backend/ai_engine/agent_stubs.py`
- Modify: `tests/ai_engine/test_agent_stubs.py`
- Modify: `tests/ai_engine/test_sprint2_demo.py`

**Interfaces:**
- Consumes: Sprint 2 stub 函数与 Sprint 3 V2 stub。
- Produces: 旧调用签名继续工作，新 V2 workflow 可导入。

- [ ] **Step 1: 先合并双方测试用例**

保留 dev 的全部 Sprint 2 断言，再加入 feat/zhongrc 的 V2 断言；不要删除任何一方来获得绿色结果。

- [ ] **Step 2: 运行冲突相关测试确认实现尚未满足**

```powershell
python -m pytest tests/ai_engine/test_agent_stubs.py tests/ai_engine/test_sprint2_demo.py -v
```

- [ ] **Step 3: 在同一模块保留稳定导出**

```python
__all__ = [
    "assessment_stub",
    "diagnosis_stub",
    "prescription_stub",
    "generation_stub",
    "feedback_stub",
]
```

如 Sprint 3 使用不同内部实现，用私有函数适配，不改变上述 Sprint 2 公共入口。

- [ ] **Step 4: 运行双方测试并完成 merge commit**

```powershell
python -m pytest tests/ai_engine/test_agent_stubs.py tests/ai_engine/test_sprint2_demo.py -v
git add backend/ai_engine/agent_stubs.py tests/ai_engine/test_agent_stubs.py tests/ai_engine/test_sprint2_demo.py
git commit
```

Expected: Git 完成原 merge commit，测试全部通过。

### Task 3: 固化 Assessment 三源合同

**Files:**
- Modify: `backend/ai_engine/assessment_v2.py`
- Modify: `backend/ai_engine/questionnaire_v2.py`
- Modify: `backend/ai_engine/safety_rules.py`
- Modify: `backend/app/schemas/assessment_v2.py`
- Test: `tests/ai_engine/test_assessment_v2.py`
- Test: `tests/api/test_assessment_v2_schema.py`

**Interfaces:**
- Consumes: document_id、document_text、narrative_text、questionnaire_answers。
- Produces: analysis_mode、emotion_profile、physical_profile、extracted_evidence、safety_flags。

- [ ] **Step 1: 添加标准三源输入测试**

```python
submission = {
    "session_id": "sess_three_sources",
    "user_id": "u_001",
    "document_id": "doc_001",
    "document_text": "近一周入睡困难。",
    "narrative_text": "考试前脑子停不下来。",
    "questionnaire_answers": questionnaire_answers(),
}
llm = RecordingJsonLLM(valid_model_response())
result = run_assessment_v2(submission, llm=llm)
assert result["agent_id"] == "assessment_agent"
assert result["analysis_mode"] == "document_narrative_questionnaire"
assert set(result) >= {
    "emotion_profile", "physical_profile",
    "extracted_evidence", "safety_flags", "confidence",
}
assert 0.0 <= result["confidence"] <= 1.0
```

- [ ] **Step 2: 添加来源可信边界测试**

未确认 OCR 文本不能出现在 extracted_evidence；空 narrative_text 视为缺失；questionnaire_answers 缺失必须产生验证错误。

- [ ] **Step 3: 运行目标测试**

```powershell
python -m pytest tests/ai_engine/test_assessment_v2.py tests/api/test_assessment_v2_schema.py -v
```

- [ ] **Step 4: 最小修复字段和枚举**

analysis_mode 只允许 questionnaire_only、narrative_questionnaire、document_questionnaire、document_narrative_questionnaire。所有 Agent ID 删除 v2 后缀。confidence 使用可解释组合：问卷完整度占 0.50、已确认输入来源完整度占 0.20、来源一致性占 0.15、模型 JSON 通过合同验证占 0.15；降级时模型部分记 0。该数值是系统证据充分度，不是医学准确率。

- [ ] **Step 5: 复测并提交**

```powershell
python -m pytest tests/ai_engine/test_assessment_v2.py tests/api/test_assessment_v2_schema.py -v
git add backend/ai_engine/assessment_v2.py backend/ai_engine/questionnaire_v2.py backend/ai_engine/safety_rules.py backend/app/schemas/assessment_v2.py tests/ai_engine/test_assessment_v2.py tests/api/test_assessment_v2_schema.py
git commit -m "feat: integrate three-source assessment contract"
```

### Task 4: 验证 Qwen 降级与安全阻断

**Files:**
- Modify: `backend/ai_engine/providers.py`
- Modify: `backend/ai_engine/assessment_v2.py`
- Modify: `backend/ai_engine/safety_rules.py`
- Test: `tests/ai_engine/test_ai_degradation_v2.py`
- Test: `tests/ai_engine/test_safety_rules.py`

**Interfaces:**
- Consumes: JsonLLMProvider 或空 provider。
- Produces: status=degraded 或 blocked_safety，并保留确定性问卷结果。

- [ ] **Step 1: 参数化失败模式**

```python
@pytest.mark.parametrize("failure", [
    TimeoutError(),
    json.JSONDecodeError("bad", "x", 0),
    LLMProviderError("provider failed"),
])
def test_assessment_degrades_to_questionnaire(failure):
    llm = ErrorJsonLLM(failure)
    result = run_assessment_v2(assessment_submission(), llm=llm)
    assert result["status"] == "degraded"
    assert result["analysis_mode"] == "questionnaire_only"
    assert result["emotion_profile"]
```

- [ ] **Step 2: 添加高风险阻断测试**

自伤表达、严重胸痛和严重呼吸困难任一命中时，status=blocked_safety、safety_flags 非空、普通音乐建议不得继续生成。

- [ ] **Step 3: 运行测试并修复**

```powershell
python -m pytest tests/ai_engine/test_ai_degradation_v2.py tests/ai_engine/test_safety_rules.py -v
```

- [ ] **Step 4: 提交降级和安全规则**

```powershell
git add backend/ai_engine/providers.py backend/ai_engine/assessment_v2.py backend/ai_engine/safety_rules.py tests/ai_engine/test_ai_degradation_v2.py tests/ai_engine/test_safety_rules.py
git commit -m "fix: guarantee AI degradation and safety blocking"
```

### Task 5: 对齐 Diagnosis、Prescription、Music 与 Feedback

**Files:**
- Modify: `backend/ai_engine/diagnosis_v2.py`
- Modify: `backend/ai_engine/prescription_v2.py`
- Modify: `backend/ai_engine/music_agent.py`
- Modify: `backend/ai_engine/feedback_v2.py`
- Test: `tests/ai_engine/test_diagnosis_v2.py`
- Test: `tests/ai_engine/test_music_agent.py`
- Test: `tests/ai_engine/test_feedback_v2.py`

**Interfaces:**
- Consumes: Assessment V2 结构化输出。
- Produces: 辅助辨证倾向、参数化处方、matched 音乐和个人偏好补丁。

- [ ] **Step 1: 添加 Music 标准输出断言**

```python
assert music == {
    "music_id": "music_jiao_001",
    "title": "角调·舒心",
    "source_type": "matched",
    "stream_url": "/static/music/jiao-demo.mp3",
    "mode": "角调",
    "bpm": 68,
    "duration_seconds": 900,
    "instruments": ["古琴", "古筝"],
}
```

- [ ] **Step 2: 添加反馈边界断言**

Feedback 输出 personal_preference_patch，但 global_rule_update 始终为 false；五星评分不能改变辨证规则或被表述为医学正确率。

- [ ] **Step 3: 运行四 Agent 测试并最小修复**

```powershell
python -m pytest tests/ai_engine/test_diagnosis_v2.py tests/ai_engine/test_music_agent.py tests/ai_engine/test_feedback_v2.py -v
```

- [ ] **Step 4: 提交**

```powershell
git add backend/ai_engine/diagnosis_v2.py backend/ai_engine/prescription_v2.py backend/ai_engine/music_agent.py backend/ai_engine/feedback_v2.py tests/ai_engine/test_diagnosis_v2.py tests/ai_engine/test_music_agent.py tests/ai_engine/test_feedback_v2.py
git commit -m "feat: align Sprint 3 agent outputs"
```

### Task 6: 暴露冻结的 V2 HTTP 接口

**Files:**
- Create: `backend/app/routers/workflow_v2_router.py`
- Create: `backend/app/schemas/workflow_v2.py`
- Create: `backend/app/core/music_catalog.py`
- Create: `backend/app/data/music_catalog.json`
- Modify: `backend/app/routers/session_router.py`
- Modify: `backend/app/main.py`
- Create: `tests/api/test_workflow_v2.py`

**Interfaces:**
- Consumes: run_assessment_v2、LangGraph workflow、music_agent 和 SessionModel。
- Produces: POST /api/v2/assessments、POST /api/v2/workflows、POST /api/v2/music、GET /api/v2/sessions/{session_id}。

- [ ] **Step 1: 先写四个路由合同测试**

```python
def test_v2_routes_exist(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v2/assessments" in paths
    assert "/api/v2/workflows" in paths
    assert "/api/v2/music" in paths
    assert "/api/v2/sessions/{session_id}" in paths
```

另加成功、degraded、blocked_safety 和 session not found 的响应壳断言。

- [ ] **Step 2: 运行路由测试确认失败**

```powershell
python -m pytest tests/api/test_workflow_v2.py -v
```

- [ ] **Step 3: 创建单一 V2 workflow router**

```python
router = APIRouter()

@router.post("/assessments")
async def create_assessment(body: AssessmentV2Request):
    result = run_assessment_v2(body.model_dump())
    return v2_ok(result, make_request_id("assessment"))

@router.post("/workflows")
async def run_workflow(body: WorkflowV2Request):
    result = run_real_workflow_v2(
        **body.model_dump(),
        music_catalog=load_music_catalog(),
    )
    return v2_ok(result, make_request_id("workflow"))

@router.post("/music")
async def match_music(body: MusicV2Request):
    result = match_music_v2(
        body.prescription,
        load_music_catalog(),
    )
    return v2_ok(result, make_request_id("music"))
```

workflow_v2.py 定义稳定的 HTTP 请求模型：

```python
class WorkflowV2Request(AssessmentV2Request):
    assessment_confirmed: bool = False
    feedback_payload: dict[str, object] | None = None

class MusicV2Request(BaseModel):
    session_id: str = Field(min_length=1)
    prescription: dict[str, object]
```

music_catalog.json 至少登记实际存在的演示音频：music_id=music_jiao_001、source_type=matched、stream_url=/static/music/jiao-demo.wav、mode=角调、bpm=68、duration_seconds=30、instruments=[古琴,古筝]。music_catalog.py 只读取该受控文件并在启动或测试时验证必填字段，不接收用户自定义文件路径。

- [ ] **Step 4: 增加会话查询并注册 router**

session_router 返回 session_id、status、current_step 和可用的 document/assessment/music/feedback 标识；main.py 以 prefix=/api/v2 注册 workflow_v2_router，不能产生 /api/v2/v2 重复前缀。

- [ ] **Step 5: 运行 API 与完整 AI 测试并提交**

```powershell
python -m pytest tests/api/test_workflow_v2.py tests/ai_engine -v
git add backend/app/routers/workflow_v2_router.py backend/app/schemas/workflow_v2.py backend/app/core/music_catalog.py backend/app/data/music_catalog.json backend/app/routers/session_router.py backend/app/main.py tests/api/test_workflow_v2.py
git commit -m "feat: expose Sprint 3 workflow APIs"
```

### Task 7: 完整工作流与 PR

**Files:**
- Modify: `backend/ai_engine/langgraph_workflow.py`
- Modify: `backend/ai_engine/real_workflow.py`
- Test: `tests/ai_engine/test_langgraph_workflow.py`
- Test: `tests/ai_engine/test_real_workflow_v2.py`
- Test: `tests/ai_engine/test_sprint3_v2_stability.py`

**Interfaces:**
- Consumes: Tasks 2-5 的稳定 Agent。
- Produces: 可合并 AI PR。

- [ ] **Step 1: 运行 V2 工作流测试**

```powershell
python -m pytest tests/ai_engine/test_langgraph_workflow.py tests/ai_engine/test_real_workflow_v2.py tests/ai_engine/test_sprint3_v2_stability.py -v
```

- [ ] **Step 2: 运行完整仓库测试**

```powershell
python -m pytest tests -v
```

Expected: 0 failed；不能只引用 feat/zhongrc 原分支的 324 passed。

- [ ] **Step 3: 范围和敏感信息检查**

```powershell
git diff --check origin/dev...HEAD
git diff origin/dev...HEAD | rg -n "sk-[A-Za-z0-9._-]{16,}|QWEN_API_KEY=|DATABASE_URL="
```

- [ ] **Step 4: 推送、建 PR、普通合并**

```powershell
git push -u origin integration/sprint3-ai-v2
gh pr create --repo chenjz111/HarmonyAI --base dev --head integration/sprint3-ai-v2 --title "feat: integrate Sprint 3 AI workflow" --body "Integrates feat/zhongrc on latest dev; preserves Sprint 2, adds three-source assessment, safety blocking, Qwen degradation and matched music output. Verification: python -m pytest tests -v."
$aiPr = gh pr list --repo chenjz111/HarmonyAI --head integration/sprint3-ai-v2 --json number --jq '.[0].number'
gh pr merge $aiPr --repo chenjz111/HarmonyAI --merge
```
