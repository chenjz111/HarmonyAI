import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { createMusicGenerationFlow, MUSIC_GENERATION_FLOW_PHASES } from "../common/music-generation-flow.js"
import { createMusicGenerationSession, GENERATION_STATES } from "../common/music-generation-session.js"

process.env.HARMONYAI_V3_MODE = "mock"

const storage = new Map()
const networkCalls = []
function blockNetwork(options) {
  networkCalls.push(options)
  throw new Error("mock fixture must not call a provider or backend")
}
globalThis.fetch = blockNetwork
globalThis.uni = {
  getStorageSync(key) { return storage.get(key) ?? "" },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
  request: blockNetwork,
  uploadFile: blockNetwork,
  downloadFile: blockNetwork,
}

const { apiV3 } = await import(`../common/api-v3.js?phase-i-fixture=${Date.now()}`)
const WAV_PATH = new URL("../static/music/jiao-demo.wav", import.meta.url)
const WAV_BYTES = readFileSync(WAV_PATH)
assert.equal(WAV_BYTES.toString("ascii", 0, 4), "RIFF")
assert.equal(WAV_BYTES.toString("ascii", 8, 12), "WAVE")
// Locate RIFF chunks rather than assuming a fixed 44-byte header.
const wavChunks = new Map()
for (let offset = 12; offset + 8 <= WAV_BYTES.length;) {
  const size = WAV_BYTES.readUInt32LE(offset + 4)
  wavChunks.set(WAV_BYTES.toString("ascii", offset, offset + 4), WAV_BYTES.subarray(offset + 8, offset + 8 + size))
  offset += 8 + size + (size % 2)
}
const WAV_DURATION_SECONDS = wavChunks.get("data").length / wavChunks.get("fmt ").readUInt32LE(8)
assert.ok(Math.abs(WAV_DURATION_SECONDS - 60.8816) < 0.0001)

function fullAnswers(schema) {
  return Object.fromEntries(schema.questions.map(q => [
    q.question_id,
    q.answer_type === "frequency_0_4" ? 2 : [q.options[0].option_code],
  ]))
}

async function reachConfirmedMock() {
  apiV3.__resetForTest()
  storage.clear()
  networkCalls.length = 0
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")
  const schema = await apiV3.getQuestionnaireSchema()
  await apiV3.submitQuestionnaire(fullAnswers(schema))
  await apiV3.createAssessment()
  await apiV3.confirmAssessment({ expected_revision: 1, decision: "confirm", changes: [] })
  await apiV3.getMusicBasis({ allowCreate: true })
}

function waitForPlayable(session, timeoutMs = 12000) {
  return new Promise((resolve, reject) => {
    const started = Date.now()
    const timer = setInterval(() => {
      const snapshot = session.snapshot()
      if (snapshot.state === GENERATION_STATES.PLAYABLE) {
        clearInterval(timer)
        resolve(snapshot)
      } else if (Date.now() - started > timeoutMs) {
        clearInterval(timer)
        reject(new Error(`session did not become playable: ${snapshot.state}`))
      }
    }, 25)
  })
}

test("mock generation returns a frontend-playable fixture and Player read model", async () => {
  await reachConfirmedMock()
  let task = await apiV3.startMusicGeneration()
  assert.equal(task.status, "queued")
  assert.equal(task.audio_asset ?? null, null)

  task = await apiV3.pollMusicGeneration(task.task_id)
  assert.equal(task.status, "running")
  for (let i = 0; i < 3; i += 1) task = await apiV3.pollMusicGeneration(task.task_id)

  assert.equal(task.status, "succeeded")
  assert.equal(task.audio_asset.music_ref.music_id, "asset_mock_001")
  assert.equal(task.audio_asset.music_ref.source_type, "generated")
  assert.equal(task.audio_asset.stream_url, "/static/music/jiao-demo.wav")
  assert.equal(task.audio_asset.tone_profile.primary_tone, "gong")
  assert.ok(Math.abs(task.audio_asset.duration_seconds - WAV_DURATION_SECONDS) < 0.001)
  assert.notEqual(task.audio_asset.duration_seconds, 300)
  assert.deepEqual(task.audio_asset.instruments, ["古琴", "洞箫"])

  const player = await apiV3.getMusic()
  assert.equal(player.music_ref.music_id, task.audio_asset.music_ref.music_id)
  assert.equal(player.stream_url, task.audio_asset.stream_url)
  assert.equal(player.duration_seconds, task.audio_asset.duration_seconds)
  assert.equal(player.duration_seconds, WAV_DURATION_SECONDS)
  assert.equal(player.tone_code, task.audio_asset.tone_profile.primary_tone)
  assert.equal((await apiV3.getMusicBasis()).duration.seconds, 300, "planned duration remains separate")
  assert.deepEqual((await apiV3.pollMusicGeneration(task.task_id)).audio_asset, task.audio_asset)
  assert.equal(networkCalls.length, 0)
  assert.ok(WAV_BYTES.length > 0)
})

test("mock session reaches PLAYABLE once, preserves asset identity on re-entry, and never starts twice", async t => {
  await reachConfirmedMock()
  let starts = 0
  const session = createMusicGenerationSession({
    pollIntervalMs: 1,
    api: {
      startGeneration: options => { starts += 1; return apiV3.startMusicGeneration(options) },
      syncTask: taskId => apiV3.pollMusicGeneration(taskId),
      cancelTask: taskId => apiV3.cancelMusicGeneration(taskId),
    },
  })

  t.after(() => session.dispose())

  session.ready()
  await session.ensureGeneration()
  const playable = await waitForPlayable(session)
  assert.equal(playable.state, GENERATION_STATES.PLAYABLE)
  assert.equal(playable.asset.stream_url, "/static/music/jiao-demo.wav")
  assert.ok(Math.abs(playable.asset.duration_seconds - WAV_DURATION_SECONDS) < 0.001)
  assert.equal(starts, 1)

  session.onHide()
  await session.onShow()
  await session.ensureGeneration()
  assert.equal(starts, 1)
  assert.equal(session.snapshot().asset.music_ref.music_id, "asset_mock_001")
  assert.equal(networkCalls.length, 0)
  session.dispose()
})

test("mock generation flow re-entry resumes the existing task without a second generation", async t => {
  await reachConfirmedMock()
  let starts = 0
  const makeApi = () => ({
    ensureMusicBasis: options => apiV3.getMusicBasis({ ...options, allowCreate: true }),
    findPersistedTask: taskId => apiV3.pollMusicGeneration(taskId),
    startGeneration: options => { starts += 1; return apiV3.startMusicGeneration(options) },
    syncTask: taskId => apiV3.pollMusicGeneration(taskId),
    cancelTask: taskId => apiV3.cancelMusicGeneration(taskId),
  })
  const first = createMusicGenerationFlow({ api: makeApi() })
  t.after(() => first.dispose())
  await first.start()
  const firstPlayable = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { clearInterval(timer); reject(new Error("flow did not become playable")) }, 12000)
    const timer = setInterval(() => {
      const snapshot = first.snapshot()
      if (snapshot.phase === MUSIC_GENERATION_FLOW_PHASES.PLAYABLE) {
        clearInterval(timer)
        clearTimeout(timeout)
        resolve(snapshot)
      }
    }, 25)
  })
  assert.equal(firstPlayable.asset.music_ref.music_id, "asset_mock_001")
  first.dispose()

  const reentered = createMusicGenerationFlow({ api: makeApi() })
  t.after(() => reentered.dispose())
  const resumed = await reentered.start()
  assert.equal(resumed.phase, MUSIC_GENERATION_FLOW_PHASES.PLAYABLE)
  assert.equal(resumed.asset.music_ref.music_id, firstPlayable.asset.music_ref.music_id)
  assert.equal(resumed.taskId, firstPlayable.taskId)
  assert.deepEqual((await apiV3.getMusic()).music_ref, resumed.asset.music_ref)
  assert.equal(starts, 1)
  assert.equal(networkCalls.length, 0)
})

test("real mode remains provider-backed and never exposes the demo asset", async () => {
  const realStorage = new Map()
  const realCalls = []
  globalThis.uni = {
    getStorageSync(key) { return realStorage.get(key) ?? "" },
    setStorageSync(key, value) { realStorage.set(key, value) },
    removeStorageSync(key) { realStorage.delete(key) },
    request(options) {
      realCalls.push(options)
      options.success({ statusCode: 404, data: { ok: false, error: { message: "fixture test" } } })
    },
  }
  process.env.HARMONYAI_V3_MODE = "real"
  const { apiV3: realApi } = await import(`../common/api-v3.js?phase-i-real=${Date.now()}`)
  await assert.rejects(() => realApi.getMusic(), /音乐尚未生成完成/)
  assert.equal(realCalls.length, 0)
  assert.equal(realApi.MODE, "real")
  assert.equal(realApi.INPUT_SIMULATED, false)
  process.env.HARMONYAI_V3_MODE = "mock"
})
