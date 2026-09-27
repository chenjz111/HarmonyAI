import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8")
const generation = read("pages/v3-generation/v3-generation.vue")
const routes = JSON.parse(read("pages.json"))
const supplement = read("pages/v3-supplement/v3-supplement.vue")
const goal = read("pages/v3-goal/v3-goal.vue")
const confirm = read("pages/v3-confirm/v3-confirm.vue")
const basis = read("pages/v3-basis/v3-basis.vue")
const player = read("pages/v3-player/v3-player.vue")

test("PR-010/PR-029: v3-generation is registered and visibly renders public flow states", () => {
  assert.ok(routes.pages.some(item => item.path === "pages/v3-generation/v3-generation"))
  assert.match(generation, /createMusicGenerationFlow/)
  assert.match(generation, /正在准备你的音乐/)
  assert.match(generation, /正在生成你的音乐/)
  assert.match(generation, /retry/)
  assert.match(generation, /cancel/)
  assert.match(generation, /MUSIC_GENERATION_FLOW_PHASES\.PLAYABLE/)
  assert.match(generation, /\/pages\/v3-player\/v3-player/)
})

test("generation page exposes no internal/provider terminology and owns no task state machine", () => {
  for (const internal of ["RAG", "Diagnosis", "Prescription", "Provider", "Qwen", "Minimax", "TokenHub", "Embedding", "Generation Spec"]) {
    assert.doesNotMatch(generation, new RegExp(internal, "i"))
  }
  assert.doesNotMatch(generation, /apiV3\.(?:startMusicGeneration|pollMusicGeneration|cancelMusicGeneration)\s*\(/)
  assert.doesNotMatch(generation, /setInterval\s*\(|pollTimer|requestId|idempotency/i)
})

test("PR-009: document and questionnaire navigation use explicit goal continuation", () => {
  assert.match(supplement, /\/pages\/v3-goal\/v3-goal\?next=generation/)
  assert.doesNotMatch(supplement, /\/pages\/v3-basis\/v3-basis/)

  assert.match(goal, /nextStep/)
  assert.match(goal, /options\.next === "generation"/)
  assert.match(goal, /\/pages\/v3-confirm\/v3-confirm/)
  assert.match(goal, /\/pages\/v3-generation\/v3-generation/)

  assert.match(confirm, /\/pages\/v3-generation\/v3-generation/)
  assert.doesNotMatch(confirm, /\/pages\/v3-basis\/v3-basis/)
})

test("PR-031: v3-basis compatibility page is cached/read-only and side-effect free", () => {
  assert.match(basis, /apiV3\.getMusicBasis\(\)/)
  assert.doesNotMatch(basis, /allowCreate\s*:\s*true/)
  assert.doesNotMatch(basis, /createMusicGenerationSession|ensureGeneration\s*\(|\.retry\s*\(|\.cancel\s*\(/)
  assert.doesNotMatch(basis, /startMusicGeneration|pollMusicGeneration|cancelMusicGeneration/)
})

test("PR-030: Player consumes resolved data and performs zero preparation/generation writes", () => {
  assert.match(player, /apiV3\.getMusic\(\)/)
  assert.match(player, /apiV3\.getMusicBasis\(\)/)
  assert.doesNotMatch(player, /allowCreate\s*:\s*true/)
  assert.doesNotMatch(player, /createMusicGenerationSession|startMusicGeneration|pollMusicGeneration|cancelMusicGeneration/)
  assert.doesNotMatch(player, /createAssessment|confirmAssessment|Diagnosis|Prescription|RAG|Provider/)
})
