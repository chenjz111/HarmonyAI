import assert from "node:assert/strict"
import test from "node:test"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

process.env.HARMONYAI_V3_MODE = "real"

const storage = new Map()
const calls = []
const assessment = {
  schema_version: "assessment_v3.1", assessment_id: "asmt_real", revision: 1,
  status: "needs_confirmation", flow_contract_version: "v3-owner-flow-1",
  input_revision: 3, safety_policy: "deferred_v3", safety_evaluation_status: "not_run",
  safety_status: null, understanding_ref: null,
  state_summary: "近期思虑偏多。", recent_context_summary: "",
  organ_profile: { status: "available", weights: { liver: 0, heart: 0, spleen: 1, lung: 0, kidney: 0 }, score_semantics: "relative_evidence_distribution" },
  fact_evidence: [], organ_evidence_links: [], conflicts: [], missing_information: [],
  evidence_coverage: 1, evidence_coverage_semantics: "confirmed_available_source_coverage",
  source_diversity: 1, requires_user_confirmation: true,
  degradation: { active: false, reason_codes: [] },
  presentation: { title: "近期状态评估", summary: "近期思虑偏多。", body_summaries: ["思虑偏多"], recent_context: "" },
}
const toneProfile = { schema_version: "tone_profile_v3.2", regulation_mode: "personalized_five_tone", primary_tone: "gong", secondary_tone: null, mapping_version: "five_tone_mapping_v3.0" }
const spec = { schema_version: "generation_spec_v3.0", tone_profile: toneProfile, bpm: 58, duration_seconds: 300, instruments: ["古琴"], ambient_sounds: ["流水"], structure: { intro_seconds: 30, main_seconds: 240, outro_seconds: 30 }, energy_curve: "calm", forbidden_constraints: [], fallback_policy: { allow_local_matching: false } }

globalThis.uni = {
  getStorageSync(key) { return storage.get(key) ?? "" },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
  request(options) {
    calls.push({ url: options.url, method: options.method, data: options.data, header: options.header })
    const path = new URL(options.url).pathname
    let data
    if (path === "/api/v3/auth/guest") data = { access_token: "token", public_user_id: "user" }
    else if (path === "/api/v3/sessions") data = { session_id: "sess_real" }
    else if (path.endsWith("/input-transitions")) data = { input_mode: "without_document", input_revision: 2, active_document_id: null, understanding_ref: null, questionnaire_ref: null }
    else if (path === "/api/v3/sessions/sess_real") data = { page: "entry", session_id: "sess_real", title: "开始了解你最近的状态", description: "请选择入口。", choices: [], flow_contract_version: "v3-owner-flow-1", input_mode: "without_document", input_revision: 2 }
    else if (path.endsWith("/questionnaire")) data = { questionnaire_submission_id: "qsub_real", schema_id: "questionnaire_v3", schema_version: "3.0.1", manifest_version: "medical_v3.0.1", content_checksum: options.data.content_checksum, input_revision: 3, status: "submitted" }
    else if (path === "/api/v3/assessments" && options.method === "POST") data = assessment
    else if (path === "/api/v3/assessments/asmt_real") data = assessment
    else if (path.endsWith("/confirmations")) data = { ...assessment, status: "confirmed", requires_user_confirmation: false }
    else if (path === "/api/v3/diagnoses") data = { schema_version: "diagnosis_v3.0", diagnosis_id: "diag_real", status: "success", presentation: { title: "辨证分析", primary_tendency: "思虑偏多", basis_summaries: ["思虑偏多"], knowledge_references: [], disclaimer: "仅用于音乐调养参考，不构成医学诊断。" }, candidate_tendencies: [], element_profile: { status: "available", weights: { wood: 0, fire: 0, earth: 1, metal: 0, water: 0 }, score_semantics: "relative_evidence_distribution" } }
    else if (path === "/api/v3/prescriptions") data = { schema_version: "prescription_v3.0", prescription_id: "rx_real", diagnosis_id: "diag_real", status: "success", generation_spec: spec, presentation: { title: "五音调适解析", tone_summary: "本次以宫音为主。", parameter_summaries: ["舒缓节奏"], personalization_summary: "未应用历史偏好。" } }
    else if (path.endsWith("/user-goal")) data = { user_goal: options.data?.user_goal ?? null }
    else if (path === "/api/v3/music/generations") data = { task_id: "task_real", status: "succeeded", message: "完成", progress: { value: 100, semantics: "provider_reported", indeterminate: false }, poll_after_ms: null, fallback: { applied: false, reason_code: null }, error_code: null, audio_asset: { music_ref: { music_id: "music_real", source_type: "generated" }, title: "静水流深", stream_url: "/api/v3/music/assets/music_real/stream", duration_seconds: 297, format: "mp3", checksum: "sha256:abc", tone_profile: toneProfile, bpm: 58, instruments: ["古琴"] } }
    else if (path === "/api/v3/feedback") data = { feedback_id: "fb_real" }
    else throw new Error(`unexpected request ${options.method} ${path}`)
    options.success({ statusCode: 200, data: { ok: true, data } })
  },
}

const { apiV3 } = await import("../common/api-v3.js?real-wiring")

function fullAnswers(schema) {
  return Object.fromEntries(schema.questions.map((q) => [q.question_id, q.answer_type === "frequency_0_4" ? 2 : [q.options[0].option_code]]))
}

test("real questionnaire through player and feedback uses server resources in order", async () => {
  await apiV3.guestAuth(); await apiV3.createSession(); await apiV3.selectMode("without_document")
  const schema = await apiV3.getQuestionnaireSchema()
  await apiV3.submitQuestionnaire(fullAnswers(schema))
  await apiV3.createAssessment(); await apiV3.getAssessment()
  await apiV3.submitHealingIntent({ primary_goal: "relaxation" })
  await apiV3.confirmAssessment({ expected_revision: 1, decision: "confirm", changes: [] })
  // Sprint 6 Phase 6 (R7): this is the generation step, so creating the basis is explicit here.
  const basis = await apiV3.getMusicBasis({ allowCreate: true })
  assert.equal(basis.primary_tone.tone, "gong")
  const task = await apiV3.startMusicGeneration()
  assert.equal(task.status, "succeeded")
  const music = await apiV3.getMusic()
  assert.equal(music.music_ref.music_id, "music_real")
  assert.equal(music.duration_seconds, 297)
  await apiV3.submitFeedback({ post_state: { change_label: "slightly_better" }, continue_use: "yes", liked_features: [], adjustment_preferences: [] })

  assert.deepEqual(calls.map((call) => new URL(call.url).pathname), [
    "/api/v3/auth/guest", "/api/v3/sessions", "/api/v3/sessions/sess_real/input-transitions",
    "/api/v3/sessions/sess_real/questionnaire", "/api/v3/assessments", "/api/v3/assessments/asmt_real",
    "/api/v3/sessions/sess_real/user-goal", "/api/v3/assessments/asmt_real/confirmations",
    "/api/v3/diagnoses", "/api/v3/prescriptions", "/api/v3/music/generations", "/api/v3/feedback",
  ])
  assert.deepEqual(calls.find((c) => new URL(c.url).pathname === "/api/v3/music/generations").data.generation_spec, spec)
})

test("basis page sends an immediately successful generation directly to Player", () => {
  const page = readFileSync(resolve(import.meta.dirname, "../pages/v3-basis/v3-basis.vue"), "utf8")
  assert.match(page, /snapshot\.state === GENERATION_STATES\.PLAYABLE/)
  assert.match(page, /snapshot\.state === GENERATION_STATES\.MATCHED_FALLBACK/)
  assert.match(page, /this\.goPlayer\(\)/)
})

// P0 regression: Frozen Contract §3 requires the session read model to carry the server-owned
// flow_contract_version / input_mode / input_revision. Before the backend fix those keys were
// absent, getSession() merged `undefined` and deleted them from the cached flow state, and the
// questionnaire submit fell back to expected_input_revision = 1 -> 409 INPUT_REVISION_CONFLICT.
test("session read model keeps the server revision in client state and submit reuses it", async () => {
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")

  const session = await apiV3.getSession()
  assert.equal(session.input_revision, 2)
  assert.equal(session.input_mode, "without_document")

  const cached = JSON.parse(storage.get("v3_flow_state"))
  assert.equal(cached.input_mode, "without_document", "getSession must not drop input_mode")
  assert.equal(cached.input_revision, 2, "getSession must not drop input_revision")

  calls.length = 0
  const schema = await apiV3.getQuestionnaireSchema()
  await apiV3.submitQuestionnaire(fullAnswers(schema))
  const submit = calls.find((c) => new URL(c.url).pathname.endsWith("/questionnaire"))
  assert.ok(submit, "questionnaire submit must be sent")
  assert.equal(
    submit.data.expected_input_revision,
    2,
    "submit must use the current server revision, never the 1 fallback",
  )
})
