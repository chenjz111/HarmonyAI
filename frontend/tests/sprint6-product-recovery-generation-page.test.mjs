import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { runInNewContext } from "node:vm"

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8")
const generation = read("pages/v3-generation/v3-generation.vue")
const routes = JSON.parse(read("pages.json"))
const supplement = read("pages/v3-supplement/v3-supplement.vue")
const goal = read("pages/v3-goal/v3-goal.vue")
const confirm = read("pages/v3-confirm/v3-confirm.vue")
const basis = read("pages/v3-basis/v3-basis.vue")
const player = read("pages/v3-player/v3-player.vue")

const phases = Object.freeze({
  IDLE: "idle",
  PREPARING: "preparing",
  GENERATING: "generating",
  PLAYABLE: "playable",
  FAILED: "failed",
  CANCELLED: "cancelled",
})

const snapshot = (phase, asset = null) => ({
  phase,
  asset,
  copy: "",
  canCancel: false,
})

const playable = musicId => snapshot(phases.PLAYABLE, musicId
  ? { music_ref: { music_id: musicId } }
  : null)

function createFakeFlow(initial = snapshot(phases.IDLE)) {
  let current = initial
  const listeners = new Set()
  return {
    startCalls: 0,
    hideCalls: 0,
    showCalls: 0,
    disposeCalls: 0,
    subscribe(listener) {
      listeners.add(listener)
      listener(current)
      return () => listeners.delete(listener)
    },
    async start() {
      this.startCalls += 1
      return current
    },
    onHide() {
      this.hideCalls += 1
      return current
    },
    async onShow() {
      this.showCalls += 1
      return current
    },
    dispose() {
      this.disposeCalls += 1
      listeners.clear()
      return current
    },
    emit(next) {
      current = next
      for (const listener of listeners) listener(current)
    },
  }
}

function loadGenerationPage(flowQueue, calls) {
  const script = generation.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(
      /import \{ apiV3 \} from [^\r\n]+\r?\n/,
      "const apiV3 = __deps.apiV3\n",
    )
    .replace(
      /import \{\s*MUSIC_GENERATION_FLOW_PHASES,\s*createMusicGenerationFlow,\s*\} from [^\r\n]+\r?\n/,
      "const { MUSIC_GENERATION_FLOW_PHASES, createMusicGenerationFlow } = __deps\n",
    )
    .replace("export default {", "__pageOptions = {")

  const context = {
    __pageOptions: null,
    __deps: {
      apiV3: {},
      MUSIC_GENERATION_FLOW_PHASES: phases,
      createMusicGenerationFlow() {
        const flow = flowQueue.shift()
        assert.ok(flow, "page must consume one supplied fake flow")
        return flow
      },
    },
    uni: {
      redirectTo(payload) { calls.redirects.push(payload) },
      showToast(payload) { calls.toasts.push(payload) },
    },
  }
  runInNewContext(script, context)
  return context.__pageOptions
}

function instantiatePage(options) {
  const page = { ...options.data() }
  for (const [name, handler] of Object.entries(options.methods || {})) {
    page[name] = handler.bind(page)
  }
  return page
}

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

test("D-R1: generation page disables navigation while hidden and replays current state on show", () => {
  assert.match(generation, /onHide\(\)\s*\{\s*this\.pageActive\s*=\s*false\s+if\s*\(this\.generationFlow\)\s*this\.generationFlow\.onHide\(\)/)
  assert.match(generation, /async onShow\(\)\s*\{\s*this\.pageActive\s*=\s*true/)
  assert.match(generation, /const snapshot\s*=\s*await this\.generationFlow\.onShow\(\)/)
  assert.match(generation, /this\.applyFlowSnapshot\(snapshot\)/)
  assert.match(generation, /applyFlowSnapshot\(snapshot\)\s*\{\s*if\s*\(!this\.pageActive\)\s*return/)
})

test("D-R2: hidden playable redirects zero times, then show redirects exactly once", async () => {
  const calls = { redirects: [], toasts: [] }
  const flow = createFakeFlow()
  const options = loadGenerationPage([flow], calls)
  const page = instantiatePage(options)

  options.onLoad.call(page)
  options.onHide.call(page)
  flow.emit(playable("music_hidden"))
  assert.equal(calls.redirects.length, 0)

  await options.onShow.call(page)
  assert.equal(calls.redirects.length, 1)
  assert.deepEqual(
    { ...calls.redirects[0] },
    { url: "/pages/v3-player/v3-player" },
  )

  flow.emit(playable("music_hidden"))
  await options.onShow.call(page)
  assert.equal(calls.redirects.length, 1, "duplicate playable callbacks must not redirect twice")
})

test("D-R2: hidden failure produces no stale navigation or toast", async () => {
  const calls = { redirects: [], toasts: [] }
  const flow = createFakeFlow()
  const options = loadGenerationPage([flow], calls)
  const page = instantiatePage(options)

  options.onLoad.call(page)
  options.onHide.call(page)
  flow.emit(snapshot(phases.FAILED))

  assert.equal(calls.redirects.length, 0)
  assert.equal(calls.toasts.length, 0)

  await options.onShow.call(page)
  assert.equal(page.phase, phases.FAILED)
  assert.equal(calls.redirects.length, 0)
  assert.equal(calls.toasts.length, 0)
})

test("D-R2: unloaded page ignores stale playable and a new page has isolated navigation state", async () => {
  const calls = { redirects: [], toasts: [] }
  const oldFlow = createFakeFlow()
  const newFlow = createFakeFlow()
  const options = loadGenerationPage([oldFlow, newFlow], calls)
  const oldPage = instantiatePage(options)

  options.onLoad.call(oldPage)
  options.onUnload.call(oldPage)
  oldFlow.emit(playable("music_obsolete"))
  assert.equal(calls.redirects.length, 0)
  assert.equal(oldFlow.disposeCalls, 1)

  const newPage = instantiatePage(options)
  options.onLoad.call(newPage)
  newFlow.emit(playable("music_current"))
  assert.equal(calls.redirects.length, 1)
  assert.equal(newPage.playerNavigationStarted, true)
  assert.equal(oldPage.playerNavigationStarted, false)

  oldFlow.emit(playable("music_obsolete_again"))
  assert.equal(calls.redirects.length, 1)
})

test("D-R2: playable phase without a valid music identity never redirects", () => {
  const calls = { redirects: [], toasts: [] }
  const flow = createFakeFlow()
  const options = loadGenerationPage([flow], calls)
  const page = instantiatePage(options)

  options.onLoad.call(page)
  flow.emit(playable(null))
  flow.emit(snapshot(phases.PLAYABLE, { music_ref: {} }))

  assert.equal(calls.redirects.length, 0)
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
