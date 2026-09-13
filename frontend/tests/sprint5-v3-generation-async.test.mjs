// Agent 4 async generation semantics (P1 regression).
//
// A real provider (Tencent Cloud TokenHub / minimax-music-v3.0) takes minutes, so the POST must
// return a queued task and the client must reach the Player through the polling path — without
// reusing a stale task id and without a second paid POST.

import assert from "node:assert/strict"
import test from "node:test"

process.env.HARMONYAI_V3_MODE = "real"

const storage = new Map()
const calls = []
let scenario = "poll"
let pollCount = 0

const toneProfile = {
  schema_version: "tone_profile_v3.1",
  primary_tone: "gong",
  secondary_tone: null,
  mapping_version: "five_tone_mapping_v3@3.0.0",
}
const spec = {
  schema_version: "generation_spec_v3.0",
  tone_profile: toneProfile,
  bpm: 60,
  duration_seconds: 180,
  instruments: ["guqin"],
  ambient_sounds: ["rain"],
  structure: { intro_seconds: 30, main_seconds: 120, outro_seconds: 30 },
  energy_curve: "calm",
  forbidden_constraints: [],
  fallback_policy: { allow_local_matching: false },
}
const audioAsset = {
  music_ref: { music_id: "music_async", source_type: "generated" },
  title: "生成音频 60 BPM",
  stream_url: "/api/v3/music/assets/music_async/stream",
  duration_seconds: 222,
  format: "mp3",
  checksum: "sha256:async-asset",
  tone_profile: toneProfile,
  bpm: 60,
  instruments: ["guqin"],
}
const assessment = {
  schema_version: "assessment_v3.1",
  assessment_id: "asmt_async",
  revision: 1,
  status: "needs_confirmation",
  flow_contract_version: "v3-owner-flow-1",
  input_revision: 3,
  safety_policy: "deferred_v3",
  safety_evaluation_status: "not_run",
  safety_status: null,
  understanding_ref: null,
  state_summary: "近期思虑偏多。",
  recent_context_summary: "",
  organ_profile: { status: "available", weights: { liver: 0, heart: 0, spleen: 1, lung: 0, kidney: 0 }, score_semantics: "relative_evidence_distribution" },
  fact_evidence: [],
  organ_evidence_links: [],
  conflicts: [],
  missing_information: [],
  evidence_coverage: 1,
  evidence_coverage_semantics: "confirmed_available_source_coverage",
  source_diversity: 1,
  requires_user_confirmation: true,
  degradation: { active: false, reason_codes: [] },
  presentation: { title: "近期状态评估", summary: "近期思虑偏多。", body_summaries: ["思虑偏多"], recent_context: "" },
}

function taskResponse(overrides) {
  return Object.assign(
    {
      task_id: "mtask_queued",
      status: "queued",
      progress: { value: null, semantics: "provider_reported", indeterminate: true },
      poll_after_ms: 1500,
      fallback: { applied: false, reason_code: null },
      error_code: null,
      audio_asset: null,
    },
    overrides,
  )
}

globalThis.uni = {
  getStorageSync(key) {
    return storage.get(key) ?? ""
  },
  setStorageSync(key, value) {
    storage.set(key, value)
  },
  removeStorageSync(key) {
    storage.delete(key)
  },
  request(options) {
    calls.push({ url: options.url, method: options.method, data: options.data })
    const path = new URL(options.url).pathname
    let data
    if (path === "/api/v3/auth/guest") data = { access_token: "token", public_user_id: "user" }
    else if (path === "/api/v3/sessions" && options.method === "POST") data = { session_id: "sess_async" }
    else if (path.endsWith("/input-transitions")) data = { input_mode: "without_document", input_revision: 2, active_document_id: null, understanding_ref: null, questionnaire_ref: null }
    else if (path.endsWith("/questionnaire")) data = { questionnaire_submission_id: "qsub_async", schema_id: "questionnaire_v3", schema_version: "3.0.1", manifest_version: "medical_v3.0.1", content_checksum: options.data.content_checksum, input_revision: 3, status: "submitted" }
    else if (path === "/api/v3/assessments" && options.method === "POST") data = assessment
    else if (path === "/api/v3/assessments/asmt_async") data = assessment
    else if (path.endsWith("/confirmations")) data = { ...assessment, status: "confirmed", requires_user_confirmation: false }
    else if (path === "/api/v3/diagnoses") data = { schema_version: "diagnosis_v3.0", diagnosis_id: "diag_async", status: "success", presentation: { title: "辨证分析", primary_tendency: "思虑偏多", basis_summaries: ["思虑偏多"], knowledge_references: [], disclaimer: "仅用于音乐调养参考，不构成医学诊断。" }, candidate_tendencies: [], element_profile: { status: "available", weights: { wood: 0, fire: 0, earth: 1, metal: 0, water: 0 }, score_semantics: "relative_evidence_distribution" } }
    else if (path === "/api/v3/prescriptions") data = { schema_version: "prescription_v3.0", prescription_id: "rx_async", diagnosis_id: "diag_async", status: "success", generation_spec: spec, presentation: { title: "五音调适解析", tone_summary: "本次以宫音为主。", parameter_summaries: ["舒缓节奏"], personalization_summary: "未应用历史偏好。" } }
    else if (path === "/api/v3/music/generations" && options.method === "POST") {
      if (scenario === "immediate") data = taskResponse({ status: "succeeded", progress: { value: 100, semantics: "provider_reported", indeterminate: false }, poll_after_ms: null, audio_asset: audioAsset })
      else data = taskResponse({})
    } else if (path === "/api/v3/music/generations/mtask_queued") {
      pollCount += 1
      if (scenario === "failed") data = taskResponse({ status: "failed", poll_after_ms: null, error_code: "GENERATION_PROVIDER_REJECTED" })
      else if (pollCount === 1) data = taskResponse({ status: "running" })
      else data = taskResponse({ status: "succeeded", progress: { value: 100, semantics: "provider_reported", indeterminate: false }, poll_after_ms: null, audio_asset: audioAsset })
    } else throw new Error(`unexpected request ${options.method} ${path}`)
    options.success({ statusCode: 200, data: { ok: true, data } })
  },
}

let importSeq = 0

async function freshApi() {
  importSeq += 1
  return (await import(`../common/api-v3.js?async-${importSeq}`)).apiV3
}

function fullAnswers(schema) {
  return Object.fromEntries(
    schema.questions.map((q) => [q.question_id, q.answer_type === "frequency_0_4" ? 2 : [q.options[0].option_code]]),
  )
}

async function reachGeneration(apiV3) {
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")
  const schema = await apiV3.getQuestionnaireSchema()
  await apiV3.submitQuestionnaire(fullAnswers(schema))
  await apiV3.createAssessment()
  await apiV3.getAssessment()
  await apiV3.confirmAssessment({ expected_revision: 1, decision: "confirm", changes: [] })
  await apiV3.getMusicBasis()
}

function flowState() {
  return JSON.parse(storage.get("v3_flow_state") || "{}")
}

test("queued POST caches the new task id instead of a stale one", async () => {
  scenario = "poll"
  pollCount = 0
  storage.clear()
  calls.length = 0
  const apiV3 = await freshApi()
  await reachGeneration(apiV3)

  // a previous failed generation left a stale task id in local state
  const stale = flowState()
  storage.set("v3_flow_state", JSON.stringify({ ...stale, task_id: "mtask_old_failed" }))

  const task = await apiV3.startMusicGeneration()
  assert.equal(task.status, "queued")
  assert.equal(flowState().task_id, "mtask_queued", "the new task id must replace the stale one")
  assert.notEqual(flowState().task_id, "mtask_old_failed")
})

test("polling advances running -> succeeded and persists the generated music", async () => {
  scenario = "poll"
  pollCount = 0
  storage.clear()
  calls.length = 0
  const apiV3 = await freshApi()
  await reachGeneration(apiV3)
  await apiV3.startMusicGeneration()

  const running = await apiV3.pollMusicGeneration()
  assert.equal(running.status, "running")
  assert.equal(running.audio_asset, null)
  assert.equal(flowState().music, undefined, "no music before success")

  const done = await apiV3.pollMusicGeneration()
  assert.equal(done.status, "succeeded")
  assert.equal(done.audio_asset.music_ref.source_type, "generated")

  const music = await apiV3.getMusic()
  assert.equal(music.music_ref.music_id, "music_async")
  assert.equal(music.duration_seconds, 222)

  // every poll targeted the task id returned by the POST
  const polls = calls.filter((c) => new URL(c.url).pathname.startsWith("/api/v3/music/generations/mtask_"))
  assert.ok(polls.length >= 2)
  for (const poll of polls) {
    assert.equal(new URL(poll.url).pathname, "/api/v3/music/generations/mtask_queued")
  }
  assert.equal(calls.filter((c) => new URL(c.url).pathname === "/api/v3/music/generations" && c.method === "POST").length, 1)
})

test("a failed generation is explicit and never fakes music", async () => {
  scenario = "failed"
  pollCount = 0
  storage.clear()
  calls.length = 0
  const apiV3 = await freshApi()
  await reachGeneration(apiV3)
  await apiV3.startMusicGeneration()

  const failed = await apiV3.pollMusicGeneration()
  assert.equal(failed.status, "failed")
  assert.equal(failed.error_code, "GENERATION_PROVIDER_REJECTED")
  assert.equal(failed.audio_asset, null)
  await assert.rejects(() => apiV3.getMusic())
  assert.equal(calls.filter((c) => new URL(c.url).pathname === "/api/v3/music/generations" && c.method === "POST").length, 1)
})

test("an immediately succeeded POST still exposes playable music", async () => {
  scenario = "immediate"
  pollCount = 0
  storage.clear()
  calls.length = 0
  const apiV3 = await freshApi()
  await reachGeneration(apiV3)

  const task = await apiV3.startMusicGeneration()
  assert.equal(task.status, "succeeded")
  const music = await apiV3.getMusic()
  assert.equal(music.music_ref.music_id, "music_async")
  assert.ok(music.stream_url.includes("/stream"))
})
