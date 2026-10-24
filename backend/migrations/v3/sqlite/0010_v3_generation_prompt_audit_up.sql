PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- Sprint 6 Phase 5 (Prompt Compiler V2): persist the ops-internal prompt
-- identity (compiler_version / dialect_id / prompt_checksum /
-- input_spec_checksum) on the generation task. Nullable, so historical rows stay
-- valid and no backfill is required. The full prompt text is never persisted.
ALTER TABLE generation_tasks ADD COLUMN prompt_audit_json TEXT;

COMMIT;
PRAGMA foreign_keys=ON;
