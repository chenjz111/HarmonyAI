-- Fail closed: do not discard credentials, revocations or replay evidence.
SELECT ACCOUNT_EVIDENCE_DOWNGRADE_REQUIRES_REVIEWED_OPERATOR_RECOVERY();
