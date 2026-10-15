-- Sprint 6 Phase 5 (Prompt Compiler V2): ops-internal prompt identity only
-- (compiler_version / dialect_id / prompt_checksum / input_spec_checksum).
-- Nullable => historical rows stay valid, no backfill, no full prompt text.
ALTER TABLE generation_tasks ADD COLUMN prompt_audit_json JSON NULL;
