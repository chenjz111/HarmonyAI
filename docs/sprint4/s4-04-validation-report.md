# S4-04 AI Understanding 验证报告

> **任务**：GitHub #55
> **分支**：`feat/zhongrc`（当前工作区直接开发）
> **日期**：2026-08-06
> **状态**：代码与本地回归完成，等待 S4-02 评估数据和团队 Review

## 1. 已完成能力

- `sprint4_contracts.py`：Provider、Evidence、Conflict、Missing、Follow-up、Revision canonical 类型。
- `providers.py`：Async Qwen gateway、Mock Provider、超时/网络/JSON/Schema 错误分类、同步兼容适配器。
- `questionnaire_v2.py`：V2.0 保持兼容，新增 V2.1 20 题和 Quick State 6 题评分入口。
- `narrative_schema.py`：13 类结构化文本证据、quote 可追溯、否定和时间范围校验。
- `assessment_v2.py`：多源 EvidenceItem、coverage、冲突、缺失、追问决策树、确认门禁和 revision 元数据。
- `diagnosis_v2.py`：白名单候选、支持/反对证据、`abstained` 和安全/确认门禁。
- `real_workflow.py`：新增显式 opt-in `run_real_workflow_v21`，不替换 V2.0 工作流。
- `evals/metrics.py`、`evals/run_sprint4_eval.py`：离线指标函数和 JSONL runner。
- `prompt/assessment/`、`prompt/diagnosis/`：版本化 Prompt 元数据和输出约束。

## 2. 验证命令与结果

```text
python -m pytest -p no:cacheprovider -q
338 passed in 2.35s

python -m pytest -p no:cacheprovider -q tests/ai_engine/test_real_workflow_v2.py tests/ai_engine/test_real_workflow.py
16 passed

python -m compileall -q backend/ai_engine evals tests/ai_engine tests/evals tests/integration
PASS

python -m json.tool <three prompt files>
PASS

git diff --check
PASS for tracked changes
```

## 3. 兼容性检查

- Sprint 2/3 既有入口未删除。
- V2.0 Questionnaire、Assessment、Diagnosis 和 Real Workflow 回归通过。
- V2.1 只有显式调用 `run_real_workflow_v21` 才会启用。
- 未上传或未确认的材料不会作为可靠 document evidence 进入融合。
- 用户未确认、Safety Block、证据不足或未解决 major 冲突时不会继续普通 Diagnosis/Prescription 流程。

## 4. 当前依赖和剩余项

- 当前工作区未同步 S4-02 的三个正式 JSON：`questionnaire-v2.1.json`、`questionnaire-scoring-v2.1.json`、`quick-state-questionnaire-v1.json`。当前评分入口使用明确命名的兼容定义；正式 JSON 合入后应替换定义来源，不改变调用接口。
- 当前工作区未同步 `evals/sprint4/cases.jsonl` 和 `evals/sprint4/safety-cases.jsonl`，因此尚未运行正式 60 案例统计；runner 已用临时 JSONL 完成离线 smoke test。
- 全量测试需要项目声明的 `langgraph` 和 `chromadb` 运行时依赖；两者已安装到当前工作区绑定 Python，不写入仓库。

## 5. Review 重点

1. 确认 S4-02 正式题目 ID、评分权重和时间窗口是否替换当前兼容定义。
2. 确认追问首版最多 4 道、契约上限 6 道的决策。
3. 确认 `run_real_workflow_v21` 是否由后端 API 以 opt-in 方式暴露。
4. S4-02 评估数据合入后，重新运行 runner 并把真实指标补入本报告。
