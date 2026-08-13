# S4-06 Manual Acceptance Result

> MySQL 已人工验收通过（2026-08-13）。OCR / Android 仍为人工 PENDING，禁止预填 PASS。

## Environment

| Field | Actual |
|---|---|
| Date | 2026-08-13 |
| Integration commit | `ed7c325a55c34fc292e61bd15fa907372c5ceaf5` |
| Tester | 陈家智（人工验收执行） |
| Windows / network | Windows 11；本机 MySQL 8.0.44 运行中 |

## MySQL 8

| Field | Result |
|---|---|
| Status | `PASS` |
| Database | `harmonyai_s4_acceptance`（utf8mb4） |
| Steps | 本机安全设置 `DATABASE_URL` → `python -m tools.s4_mysql_acceptance` → 真实 API 链路（创建评估 → 确认） |
| Expected | Migration、幂等、重连持久化、范围 CRUD、隐私钩子、清理全部通过 |
| Actual | 全部通过（见下表） |
| Evidence | 探针输出 `pass=true`；真实 API 链路 revision 1→2、`confirmation_level` 落库；验收行已清理 |
| Pass/Fail | **PASS** |
| Notes | 未记录用户名 / 密码 / DATABASE_URL / 敏感路径；探针只允许 `harmonyai_s4_acceptance` 库 |

### MySQL 8 checks（2026-08-13）

| Check | Result |
|---|---|
| MySQL version | 8.0.44 |
| connection | PASS |
| migration（首次 apply） | PASS |
| idempotency（二次 apply） | PASS |
| reconnect persistence | PASS |
| Session / Revision / Evidence / FollowUp / Feedback / AICallLog 持久化 | PASS |
| AI log privacy（input/output/error 均为空） | PASS |
| cleanup safety（按唯一 session_id 范围删除，0 残留） | PASS |
| real API → MySQL chain（Assessment → Confirmation） | PASS |

## OCR Manual POC

| Field | Result |
|---|---|
| Status | `MANUAL_OCR_POC_PENDING` |
| Materials | Authorized/redacted JPG, PNG and multi-page PDF; damaged-file fallback sample |
| Steps | Follow `docs/sprint4/s4-06-manual-gates.md` |
| Expected | Real OCR plus edit/confirm and failed/degraded/skip paths; no raw provider exception or sensitive log |
| Actual | NOT_RUN |
| Evidence | NOT_RUN |
| Pass/Fail | PENDING |
| Notes | Synthetic fixtures are not manual POC evidence |

## Android Real Device

| Field | Result |
|---|---|
| Status | `MANUAL_ANDROID_TEST_PENDING` |
| Device / Android | NOT_RUN |
| Build commit | NOT_RUN |
| API base | Set at runtime from `tools/start-s4-manual-acceptance.ps1`; do not commit LAN IP |
| Steps | Complete input → assessment/revision/confirmation → diagnosis → prescription → music → feedback and safety paths |
| Expected | Full chain works; authoritative safety/abstain/follow-up gates never reach Music |
| Actual | NOT_RUN |
| Evidence | NOT_RUN |
| Pass/Fail | PENDING |
| Notes | H5 PASS is not Android PASS |
