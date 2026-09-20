// Sprint 6 Phase 6 — R7 regression: reading the music basis must never re-create server-side
// medical artifacts, and a non-terminal retry must reuse one idempotency key.
//
// Mocked `uni.request` only: no backend, no provider, no LLM/embedding call.

import assert from "node:assert/strict"
import test from "node:test"

process.env.HARMONYAI_V3_MODE = "real"

const storage = new Map()
const calls = []

const toneProfile = {
  schema_version: "tone_profile_v3.2",
  regulation_mode: "personalized_five_tone",
  primary_tone: "jiao",
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
const assessment = {
  schema_version: "assessment_v3.1",
  assessment_id: "asmt_r7",
  revision: 2,
  status: "confirmed",
  flow_contract_version: "v3-owner-flow-1",
  input_revision: 3,
  safety_policy: "deferred_v3",
  safety_status: null,
  state_summary: "近期思虑偏多。",
  organ_profile: { status: "available", weights: { liver: 0.4, heart: 0, spleen: 0.6, lung: 0, kidney: 0 }, score_semantics: "relative_evidence_distribution" },
  fact_evidence: [],
  organ_evidence_links: [],
  conflicts: [],
  missing_information: [],
  presentation: { title: "近期状态评估", summary: "近期思虑偏多。", body_summaries: ["思虑偏多"], recent_context: "" },
}
const diagnosis = {
  schema_version: "diagnosis_v3.0",
  diagnosis_id: "diag_r7",
  status: "success",
  presentation: {
    title: "辨证分析",
    primary_tendency: "思虑偏多",
    basis_summaries: ["思虑偏多，提示需要安定。"],
    knowledge_references: [],
    disclaimer: "仅用于音乐调养参考，不构成医学诊断。",
  },
}
const prescription = {
  schema_version: "prescription_v3.0",
  prescription_id: "rx_r7",
  diagnosis_id: "diag_r7",
  status: "success",
  generation_spec: spec,
  presentation: {
    title: "五音调适解析",
    tone_summary: "本次以角音为主。",
    parameter_summaries: ["舒缓节奏"],
    personalization_summary: "未应用历史偏好。",
  },
}

function flowState(extra = {}) {
  return Object.assign(
    {
      session_id: "sess_r7",
      input_revision: 3,
      assessment,
      diagnosis,
      prescription,
      prescription_id: "rx_r7",
      generation_spec: spec,
    },
    extra,
  )
}

function taskResponse(overrides = {}) {
  return Object.assign(
    {
      task_id: "mtask_r7",
      status: "queued",
      message: "音乐生成任务已排队",
      progress: null,
      poll_after_ms: 2000,
      fallback: { applied: false, reason_code: null },
      error_code: null,
      audio_asset: null,
    },
    overrides,
  )
}

globalThis.uni = {
  getStorageSync(key) {
    return storage.has(key) ? storage.get(key) : ""
  },
  setStorageSync(key, value) {
    storage.set(key, value)
  },
  removeStorageSync(key) {
    storage.delete(key)
  },
  request(options) {
    const path = new URL(options.url).pathname
    calls.push({ method: options.method || "GET", path, data: options.data })
    let data
    if (path === "/api/v3/auth/guest") data = { access_token: "token", public_user_id: "user" }
    else if (path === "/api/v3/sessions" && options.method === "POST") data = { session_id: "sess_r7" }
    else if (path === "/api/v3/diagnoses") data = diagnosis
    else if (path === "/api/v3/prescriptions") data = prescription
    else if (path === "/api/v3/music/generations" && options.method === "POST") data = taskResponse()
    else if (path === "/api/v3/music/generations/mtask_r7") data = taskResponse({ status: "running" })
    else throw new Error(`unexpected request ${options.method} ${path}`)
    options.success({ statusCode: 200, data: { ok: true, data } })
  },
}

let importSeq = 0

async function freshApi() {
  importSeq += 1
  return (await import(`../common/api-v3.js?r7-${importSeq}`)).apiV3
}

function seed(state) {
  storage.clear()
  calls.length = 0
  storage.set("v3_access_token", "token")
  if (state) storage.set("v3_flow_state", JSON.stringify(state))
}

function countCalls(method, path) {
  return calls.filter((c) => c.method === method && c.path === path).length
}

test("R7: a cached basis reads with ZERO POST /diagnoses and ZERO POST /prescriptions", async () => {
  const apiV3 = await freshApi()
  seed(flowState())

  const basis = await apiV3.getMusicBasis()

  assert.equal(countCalls("POST", "/api/v3/diagnoses"), 0)
  assert.equal(countCalls("POST", "/api/v3/prescriptions"), 0)
  assert.equal(calls.length, 0, "a cached basis read performs no network request at all")
  assert.equal(basis.page, "five_tone_analysis")
  assert.equal(basis.regulation_mode, "personalized_five_tone")
  assert.equal(basis.primary_tone.tone, "jiao")
  assert.equal(basis.duration.seconds, 180)
})

test("R7: an incomplete cache fails closed with a typed code instead of creating anything", async () => {
  const apiV3 = await freshApi()
  seed(flowState({ diagnosis: undefined, prescription: undefined, prescription_id: null, generation_spec: null }))

  await assert.rejects(() => apiV3.getMusicBasis(), (error) => {
    assert.equal(error.code, "BASIS_NOT_CACHED")
    return true
  })

  assert.equal(countCalls("POST", "/api/v3/diagnoses"), 0)
  assert.equal(countCalls("POST", "/api/v3/prescriptions"), 0)
  assert.equal(calls.length, 0)
})

test("R7: a prescription without its generation spec is not a cache hit and creates nothing", async () => {
  const apiV3 = await freshApi()
  seed(flowState({ prescription: { ...prescription, generation_spec: null }, generation_spec: null }))

  await assert.rejects(() => apiV3.getMusicBasis(), (error) => error.code === "BASIS_NOT_CACHED")
  assert.equal(countCalls("POST", "/api/v3/diagnoses"), 0)
  assert.equal(countCalls("POST", "/api/v3/prescriptions"), 0)
})

test("only an explicit allowCreate caller may create the diagnosis/prescription (exactly once)", async () => {
  const apiV3 = await freshApi()
  seed(flowState({ diagnosis: undefined, prescription: undefined, prescription_id: null, generation_spec: null }))

  await assert.rejects(() => apiV3.getMusicBasis({ allowCreate: false }), (error) => error.code === "BASIS_NOT_CACHED")
  assert.equal(calls.length, 0)

  const basis = await apiV3.getMusicBasis({ allowCreate: true })
  assert.equal(countCalls("POST", "/api/v3/diagnoses"), 1)
  assert.equal(countCalls("POST", "/api/v3/prescriptions"), 1)
  assert.equal(basis.page, "five_tone_analysis")

  // The created artifacts are now cached: a second read creates nothing.
  calls.length = 0
  await apiV3.getMusicBasis()
  assert.equal(calls.length, 0)
})

test("an unconfirmed assessment is refused before any network call", async () => {
  const apiV3 = await freshApi()
  seed(flowState({ assessment: { ...assessment, status: "needs_confirmation" } }))

  await assert.rejects(() => apiV3.getMusicBasis(), (error) => error.code === "ASSESSMENT_NOT_CONFIRMED")
  await assert.rejects(() => apiV3.getMusicBasis({ allowCreate: true }), (error) => error.code === "ASSESSMENT_NOT_CONFIRMED")
  assert.equal(calls.length, 0)
})

test("generation keeps the frozen no-fallback policy and honours a caller-supplied request id", async () => {
  const apiV3 = await freshApi()
  seed(flowState())

  const first = await apiV3.startMusicGeneration({ requestId: "music_req_fixed" })
  assert.equal(first.task_id, "mtask_r7")

  const post = calls.find((c) => c.method === "POST" && c.path === "/api/v3/music/generations")
  assert.ok(post, "exactly one generation POST")
  assert.equal(countCalls("POST", "/api/v3/music/generations"), 1)
  assert.equal(post.data.request_id, "music_req_fixed")
  assert.equal(post.data.idempotency_key, "sha256:music_req_fixed")
  assert.deepEqual(post.data.provider_policy, { mode: "prefer_real_generation", fallback: "none" }, "P6-D3")
  assert.equal(post.data.prescription_id, "rx_r7")
})

test("retrying the same request id replays one idempotency key instead of paying twice", async () => {
  const apiV3 = await freshApi()
  seed(flowState())

  await apiV3.startMusicGeneration({ requestId: "music_req_same" })
  await apiV3.startMusicGeneration({ requestId: "music_req_same" })

  const posts = calls.filter((c) => c.method === "POST" && c.path === "/api/v3/music/generations")
  assert.equal(posts.length, 2)
  assert.equal(posts[0].data.idempotency_key, posts[1].data.idempotency_key)
  assert.equal(posts[0].data.idempotency_key, "sha256:music_req_same")
})

test("generation without a prepared prescription fails before any network call", async () => {
  const apiV3 = await freshApi()
  seed(flowState({ prescription_id: null, generation_spec: null }))

  await assert.rejects(() => apiV3.startMusicGeneration({ requestId: "music_req_x" }), (error) => {
    assert.equal(error.code, "PRESCRIPTION_NOT_READY")
    return true
  })
  assert.equal(calls.length, 0)
})

test("the player read surface never touches diagnoses/prescriptions when nothing is cached", async () => {
  const apiV3 = await freshApi()
  seed(flowState({ diagnosis: undefined, prescription: undefined, prescription_id: null, generation_spec: null }))

  // Mirrors the player load order: read the basis (cache only), then read the cached music.
  await assert.rejects(() => apiV3.getMusicBasis())
  await assert.rejects(() => apiV3.getMusic())

  assert.equal(countCalls("POST", "/api/v3/diagnoses"), 0)
  assert.equal(countCalls("POST", "/api/v3/prescriptions"), 0)
  assert.equal(calls.length, 0)
})
