-- 0002_v3_business rollback — reverse dependency order.

DROP TABLE IF EXISTS favorites;
DROP TABLE IF EXISTS preference_events;
DROP TABLE IF EXISTS user_preference_items;
DROP TABLE IF EXISTS user_music_preference_versions;
DROP TABLE IF EXISTS user_music_preferences;
DROP TABLE IF EXISTS feedback_v3;

DROP TABLE IF EXISTS generation_tasks;
DROP TABLE IF EXISTS music_assets;
DROP TABLE IF EXISTS prescription_v3;

DROP TABLE IF EXISTS ai_provider_runs;
DROP TABLE IF EXISTS rag_retrieval_hits;
DROP TABLE IF EXISTS rag_retrieval_runs;
DROP TABLE IF EXISTS knowledge_chunks_v3;
DROP TABLE IF EXISTS knowledge_manifests;
DROP TABLE IF EXISTS diagnosis_candidate_evidence;
DROP TABLE IF EXISTS diagnosis_candidates;
DROP TABLE IF EXISTS diagnosis_runs;

DROP TABLE IF EXISTS organ_evidence;
DROP TABLE IF EXISTS fact_evidence;
DROP TABLE IF EXISTS assessment_revisions_v3;
DROP TABLE IF EXISTS assessment_v3;

DROP TABLE IF EXISTS fact_source_refs;
DROP TABLE IF EXISTS normalized_facts;
DROP TABLE IF EXISTS questionnaire_submissions_v3;
DROP TABLE IF EXISTS understanding_revisions;
DROP TABLE IF EXISTS understanding_sources;
DROP TABLE IF EXISTS understanding_runs;
