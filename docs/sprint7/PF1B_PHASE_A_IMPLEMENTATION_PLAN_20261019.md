# PF-1B Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 PF-1B 当前不依赖正式 0013 的三项可复用、可独立测试的基础能力：严格逐条 consent 解析、服务端政策判定、V3.1 请求指纹；保持旧反馈及 PF-1A 安全边界不变。

**Architecture:** 将新输入片段放在独立 V3.1 schema，把纯政策判定与纯指纹计算分别放在小服务模块。Phase A 不注册路由、不读写数据库、不产生学习结果；正式保存、tombstone 与 clear 待共享合同冻结后另列 Phase B 计划。

**Tech Stack:** Python 3.12+/3.13、Pydantic v2、pytest、现有 V3 `V3BaseModel`；定向回归使用隔离 SQLite、合成数据与已验证离线保护。

**Spec:** `docs/sprint7/PF1B_FEEDBACK_CONSENT_DELETE_DESIGN_20261019.md`

## Global Constraints

- 目标 Issue 为 #152；最终 PR base 为 `team/s7-m1-w2-baseline`，不指向 `main`，不 rebase、force push 或自动 merge。
- #150 独占正式 0013、共享 ORM exports 与 `main.py` 注册；#151 独占 owner/context/state helper。Phase A 不修改这些文件。
- M1 长期学习和新生成读取旧 preference snapshot 持续关闭；旧 `feedback_v3.0` 合法请求和历史 profile 读能力保持不变。
- `learning_consent` 省略为 `false`，显式值只接受 JSON 布尔；`true` 不触发学习；无 active policy 时 `false` 不受阻。
- 不保存/打印 API Key、真实病历、自由文本评论、完整请求；不使用真实 Provider、生产库或未确认版权的素材。
- 先写失败测试，再实现；保留旧断言；每个提交仅含本 lane 文件。任何依赖正式字段、事件授权或公开错误码的变更停在 Phase B Gate。

## Review Focus

以下五类输入最容易造成误授权或不稳定重放，相关测试分别在 Task 1～3 固化：

1. 显式 `null`、`0/1`、`"true"` 不得被当成授权；Task 1 的参数化校验拒绝它们。
2. 未配置政策、空版本或回显旧版本不得批准 `true`；Task 2 测试 fail closed，而 `false` 仍可继续。
3. 服务端政策版本前后含空白或时间不是 UTC 不得产生有效同意时间；Task 2 测试配置和时间边界。
4. 同一规范化 payload 的键顺序或“省略 false / 显式 false”不得改变指纹；Task 3 测试规范化等价。
5. 嵌套值变化、非有限数字或隐私文本不得导致错误重放或原文泄露；Task 3 测试指纹差异、拒绝 NaN、输出仅 digest。

---

## File map and execution preflight

| File | Single responsibility |
|---|---|
| `backend/app/schemas/v3/feedback_v31.py` | 内部 consent 输入片段；不宣称完整公开请求 DTO |
| `backend/app/services/v3/feedback_consent_policy.py` | 无 DB 的服务端政策判定与同意时间决定 |
| `backend/app/services/v3/feedback_request_fingerprint.py` | 对已规范化 JSON payload 计算版本域隔离的 SHA-256 指纹 |
| `tests/api/v3/test_s7_feedback_consent.py` | consent schema 与政策判定的纯测试 |
| `tests/api/v3/test_s7_feedback_fingerprint.py` | 指纹稳定性、差异与隐私边界测试 |

执行前在现有隔离 worktree 中确认 `feat/s7-pf1b-feedback`、工作区干净，记录当前 `HEAD` 和 `origin/team/s7-m1-w2-baseline`。该分支已有设计文档提交，不能假定 `git merge --ff-only` 可用；执行 `git fetch origin team/s7-m1-w2-baseline` 后做**普通 merge**，不得 rebase/force push。若合并有业务冲突，停止并核对 Owner 最新合同。使用合成环境、无真实凭据、已验证离线保护重跑：

```text
python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_preference_invalidation.py tests/api/v3/test_feedback.py --tb=short
```

只有本次合并后实际结果可称为新基线；之前的 11 passed 仅属于旧 HEAD。测试无法在本机执行时记录原因，不删除断言，也不把历史结果写成本次通过。

### Task 1: Strict consent input fragment

**Files:** Create `backend/app/schemas/v3/feedback_v31.py`; create `tests/api/v3/test_s7_feedback_consent.py`.

**Interfaces:** Consumes `V3BaseModel`、`NonEmptyString`、Pydantic `StrictBool`。Produces `FeedbackConsentFields(V3BaseModel)`，字段 `learning_consent: StrictBool = False`、`consent_policy_version: NonEmptyString | None = None`。它只是内部可复用片段，不能在 #150 注册为正式请求。

- [ ] 写 `test_consent_defaults_false_and_accepts_literal_booleans`：`FeedbackConsentFields()` 为 `False`；显式 `True/False` 保持原值。
- [ ] 写参数化 `test_consent_rejects_coerced_values`：`None`、`0`、`1`、`"true"`、`"false"` 均抛 Pydantic `ValidationError`；额外字段同样拒绝。
- [ ] 运行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_feedback_consent.py --tb=short`，先确认缺失类型导致 RED，而不是收集环境错误。
- [ ] 只添加上述内部模型，不添加 music/context/event 等未冻结公开字段，也不注册路由。
- [ ] 同一命令确认 GREEN；再运行旧 `test_feedback.py` 与 `test_s7_preference_invalidation.py`，记录实际通过/警告。
- [ ] `git add` 仅本任务两文件，`git diff --cached --check` 为零输出后提交 `feat(s7): define strict PF-1B consent input`。

### Task 2: Server-owned policy decision

**Files:** Create `backend/app/services/v3/feedback_consent_policy.py`; extend `tests/api/v3/test_s7_feedback_consent.py`.

**Interfaces:** Consumes Task 1 验证后的 `bool`。Produces frozen `ConsentDecision(learning_consent: bool, policy_version: str | None, consented_at: datetime | None)`、内部 `ConsentPolicyUnavailable` / `ConsentPolicyMismatch`，以及 `resolve_consent_policy(*, consent: bool, echoed_version: str | None, active_version: str | None, now_utc: datetime) -> ConsentDecision`。这里的异常不是公开 HTTP 错误码。

- [ ] 写 `test_false_does_not_require_policy`：无 active policy、客户端回显旧版本仍返回 `False/None/None`，不把回显版本写成权威版本。
- [ ] 写 `test_true_requires_exact_active_policy`：完全匹配返回服务端版本和传入的 UTC 时间；无 active、空/空白 active、回显缺失或不匹配分别抛内部异常；`True` 的 naive/non-UTC 时间拒绝。
- [ ] 运行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_feedback_consent.py --tb=short`，确认新测试先 RED。
- [ ] 实现纯判定函数；不从环境变量随意发明政策版本，不读取数据库，不调学习器，不在错误信息中记录回显内容。
- [ ] 同一命令确认 GREEN，并回归 Task 1 的全部严格布尔样例。
- [ ] `git add` 仅本任务两文件，`git diff --cached --check` 后提交 `feat(s7): validate server-owned feedback consent policy`。

### Task 3: Canonical request fingerprint primitive

**Files:** Create `backend/app/services/v3/feedback_request_fingerprint.py`; create `tests/api/v3/test_s7_feedback_fingerprint.py`.

**Interfaces:** Produces `fingerprint_feedback_request(normalized_payload: Mapping[str, object]) -> str`。调用方将来必须先用正式 V3.1 DTO 的 `model_dump(mode="json")` 得到规范化请求；本函数不读取 key、owner、DB、时间或当前政策，也不记录原文。输出格式固定为 `sha256:<64 lowercase hex>`。

- [ ] 写 `test_fingerprint_ignores_mapping_order_and_normalized_default`：相同嵌套 JSON 的键顺序不同得到相同指纹；Task 1 模型省略 consent 与显式 `False` 的规范化输出得到相同指纹。
- [ ] 写 `test_fingerprint_changes_with_payload_and_never_returns_text`：更换嵌套值或 consent 得到不同指纹，结果不含输入隐私字符串；NaN/不可 JSON 序列化对象分别显式失败。
- [ ] 运行 `python -m pytest -q -p no:cacheprovider tests/api/v3/test_s7_feedback_fingerprint.py --tb=short`，确认 RED。
- [ ] 实现固定算法：`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` 转 UTF-8；哈希输入前缀为 `b"feedback_v3.1\0"`，再计算 SHA-256。只接受规范化 JSON 映射，不把完整请求写日志或落库。
- [ ] 同一命令确认 GREEN；合并运行两个新测试文件及旧反馈/PF-1A 回归，记录本次 Passed/Failed/Skipped/Warnings。
- [ ] `git add` 仅本任务两文件，`git diff --cached --check` 后提交 `feat(s7): fingerprint normalized feedback requests`。

## Phase A final verification and handoff

- [ ] 在最新已合并团队基线上运行两个新测试文件、`test_feedback.py`、`test_s7_preference_invalidation.py`；测试前确认使用隔离 SQLite/合成数据和有效离线保护。运行 `git diff origin/team/s7-m1-w2-baseline...HEAD --check`，确认无额外文件、密钥、缓存或测试产物。
- [ ] Review 每个新模块：无 DB 写入、无路由注册、无自动学习、无宽松 consent、无政策字符串硬编码、无完整请求/用户原文日志；旧测试断言未删除。
- [ ] 若需要阶段性交付，只开关联 #152 的 Draft PR，base 为 `team/s7-m1-w2-baseline`，标题/正文明确 `PF-1B Phase A primitives only`；列出依赖、真实测试命令与数量、0 真实 Provider/生产库、Phase B 未完成。不得写成 PF-1B 完整交付或转 Ready。

## Phase B stop gate and subsequent plan boundary

此文件**不授权执行持久化、列表、删除或 clear**。这些任务需要另一份经 Owner 审阅的 Phase B 实施计划，并以以下可核验事实作为其输入；若任何一项缺失，保持功能门禁关闭：

1. #150 正式 0013 已在团队基线公布，`feedback_v3`/偏好版本字段、约束、旧行默认、SQLite/MySQL up/down 和生产 ORM 一致；不能从 PR #155 Draft 复制并自行注册。
2. Owner 确认 active consent policy 的权威来源与撤销规则，批准 V3.1 请求/响应字段、路由、tombstone replay、旧无指纹行及 comment 的公开错误语义。
3. #151/Owner 确认是否需要绑定指定 `playback_event_id`；如果需要，由 Backend 提供统一 owner+asset+context+event 校验 helper，PF 不自己做第二套授权查询。
4. Owner 明确 clear 后历史 profile 可读与当前应用指针失效如何并存；#151 明确预期 epoch/CAS 比较及首写 owner-state 冲突恢复。

Phase B 另拆为可独立评审的 POST+幂等、owner-scoped 读取、tombstone、clear/epoch、确定性并发和迁移/合同回归；每项先 RED 再实现。对上述未冻结接口，本计划只列验收方向，不编造签名、字段、HTTP 状态或成功测试数量。
