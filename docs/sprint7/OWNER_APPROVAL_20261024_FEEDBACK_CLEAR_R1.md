# Owner approval — Feedback V3.1 and Clear Receipt R1

Date: 2026-10-24, Asia/Shanghai. Source: Owner's explicit decision in this Codex chat, received during autonomous implementation. This is a new approved decision; older Draft documents remain historical evidence.

## Approved product semantics (Clear option A)

Clear only removes feedback at or before the cutoff from future long-term preference evidence eligibility. It does not delete or hide historical feedback, physically erase records, or modify historical Diagnosis, Prescription, MusicAsset or immutable snapshots. Undeleted history stays visible under existing owner/access rules. Individually deleted feedback remains tombstoned and cannot return through reads or replay. M1 learning remains OFF.

## Approved R1 technical contract

1. Use existing V3 success/error envelopes and R1 API paths/DTO/status/error adapters.
2. First save returns201; legitimate identical replay returns200. Cross-owner access does not disclose existence. Tombstone precedes replay.
3. Unknown COMMIT recovers with the original key and request; never invent a second write.
4. Clear namespace is `feedback_evidence.clear.v1`.
5. Persist receipt, cutoff and feedback epoch in one transaction.
6. Same key/body returns original operation_id, original cutoff and original resulting_feedback_epoch. Changed request with same key conflicts.
7. Clear-invalidated evidence cannot regain learning eligibility through a new request, old event or late computation.
8. No receipt automatic TTL/background cleanup. This temporary engineering behavior is not final retention policy.

## Authorized implementation

Formal0013 including necessary receipt persistence; public Feedback V3.1 DTO/router/errors; save/read/delete/clear transactions; V3.0 compatibility/tombstone protection; frontend adapters; offline/concurrency/regression tests and Draft PR preparation. Do not re-request these approved decisions.

## Still not authorized

Deployment, Live Flags, production migrations, paid Provider calls, PR merge, enabling long-term learning, final retention duration, backup cleanup or account erasure policy. Medical decisions and historical snapshots retain their existing boundaries.

## Execution update

Continue original autonomous Sprint workflow. Prioritize0013, qualified PR164 reuse, full Feedback V3.1/Clear Receipt, frontend/backend integration and acceptance preparation. Ask only for a new substantive policy conflict, safety blocker or additional permission requirement.
