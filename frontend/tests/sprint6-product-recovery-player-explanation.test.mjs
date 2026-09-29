import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { runInNewContext } from "node:vm"

import { buildMusicPresentation, presentProgress } from "../common/music-presentation.js"

const playerSource = readFileSync(new URL("../pages/v3-player/v3-player.vue", import.meta.url), "utf8")

function loadPlayerPage({ apiV3, createPlayerController, uni }) {
  const script = playerSource.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import \{ apiV3 \} from [^\r\n]+\r?\n/, "const apiV3 = __deps.apiV3\n")
    .replace(
      /import \{ createPlayerController \} from [^\r\n]+\r?\n/,
      "const createPlayerController = __deps.createPlayerController\n",
    )
    .replace(
      /import \{ buildMusicPresentation, presentProgress \} from [^\r\n]+\r?\n/,
      "const { buildMusicPresentation, presentProgress } = __deps\n",
    )
    .replace("export default {", "__pageOptions = {")

  const context = {
    __pageOptions: null,
    __deps: { apiV3, createPlayerController, buildMusicPresentation, presentProgress },
    uni,
  }
  runInNewContext(script, context)
  return context.__pageOptions
}

function instantiatePage(options) {
  const page = { ...options.data() }
  for (const [name, handler] of Object.entries(options.methods || {})) {
    page[name] = handler.bind(page)
  }
  for (const [name, getter] of Object.entries(options.computed || {})) {
    Object.defineProperty(page, name, { get: getter.bind(page) })
  }
  return page
}

function createHarness() {
  const calls = {
    getMusic: 0,
    getMusicBasis: 0,
    controllerCreates: 0,
    audioCreates: 0,
    controllerActions: 0,
    generationWrites: 0,
    toasts: 0,
  }
  let taskIdentity = "task_001"
  const music = {
    status: "succeeded",
    title: "山水清和",
    stream_url: "https://example.invalid/resolved.mp3",
    music_ref: { music_id: "music_001", source_type: "generated" },
    duration_seconds: 300,
    instrument_labels: ["古琴", "洞箫"],
    regulation_mode: "personalized_five_tone",
    tone_code: "gong",
  }
  const basis = {
    regulation_mode: "personalized_five_tone",
    confirmed_state: "睡眠欠佳，食欲不振。",
    state_tendency: "近期恢复状态不足。",
    analysis_rationales: [{ summary: "依据已确认的近期状态选择舒缓方案。" }],
    primary_tone: { tone: "gong" },
    secondary_tone: { tone: "jiao" },
    tone_weights: { gong: 0.4, jiao: 0.2, zhi: 0.15, shang: 0.15, yu: 0.1 },
    bpm: { value: 58, explanation: "采用舒缓节奏。" },
    instruments: { values: ["古琴", "洞箫"] },
    ambience: { values: ["自然声"] },
    duration: { seconds: 300 },
  }
  const audioContext = { identity: "audio_001", src: music.stream_url }
  const snapshot = { playing: true, currentTime: 73, duration: 300, error: null }
  const controller = {
    audioContext,
    getState: () => snapshot,
    toggle() { calls.controllerActions += 1 },
    seek() { calls.controllerActions += 1 },
    handleHide() { calls.controllerActions += 1 },
    handleShow() { calls.controllerActions += 1 },
    dispose() { calls.controllerActions += 1 },
  }
  const apiV3 = {
    AGENT_SIMULATED: false,
    async getMusic() { calls.getMusic += 1; return music },
    async getMusicBasis() { calls.getMusicBasis += 1; return basis },
    fetchAuthorizedAudio() { throw new Error("toggle must not download audio") },
    startMusicGeneration() { calls.generationWrites += 1; taskIdentity = "task_changed" },
    pollMusicGeneration() { calls.generationWrites += 1; taskIdentity = "task_changed" },
    cancelMusicGeneration() { calls.generationWrites += 1; taskIdentity = "task_changed" },
  }
  const uni = {
    createInnerAudioContext() { calls.audioCreates += 1; return audioContext },
    showToast() { calls.toasts += 1 },
    navigateTo() {},
    reLaunch() {},
  }
  const createPlayerController = options => {
    calls.controllerCreates += 1
    assert.equal(options.createAudioContext, uni.createInnerAudioContext)
    return controller
  }
  return {
    calls,
    music,
    basis,
    audioContext,
    snapshot,
    controller,
    apiV3,
    uni,
    createPlayerController,
    getTaskIdentity: () => taskIdentity,
  }
}

test("PR-011/PR-012: Player exposes the approved explanation entry and starts collapsed", () => {
  const harness = createHarness()
  const options = loadPlayerPage(harness)
  const page = instantiatePage(options)

  assert.equal(page.analysisExpanded, false)
  assert.match(playerSource, /为什么是这首音乐？/)
  assert.match(playerSource, /查看本次音乐的生成依据/)
  assert.match(playerSource, /v-if="analysisVisible"\s+class="analysis-card"/)
  assert.match(playerSource, /v-if="analysisVisible && analysisExpanded"/)
})

test("F-R2: all-empty analysis hides the explanation card and details", () => {
  const harness = createHarness()
  const page = instantiatePage(loadPlayerPage(harness))
  page.music = harness.music
  page.basis = {}

  assert.equal(page.playerPresentation.analysis.hasContent, false)
  assert.equal(page.analysisVisible, false)
  assert.equal(page.analysisExpanded, false)
})

test("F-R2: one valid section shows a collapsed explanation with only that section", () => {
  const harness = createHarness()
  const page = instantiatePage(loadPlayerPage(harness))
  page.music = harness.music
  page.basis = { confirmed_state: "近期睡眠欠佳。" }

  assert.equal(page.analysisVisible, true)
  assert.equal(page.analysisExpanded, false)
  assert.deepEqual(
    Object.fromEntries(Object.entries(page.playerPresentation.analysis.sections).map(([key, section]) => [key, section.hasContent])),
    {
      recentState: true,
      interpretation: false,
      rationales: false,
      toneConfiguration: false,
      musicDesign: false,
    },
  )

  page.toggleAnalysis()
  assert.equal(page.analysisExpanded, true)
})

test("F-R2: multiple valid sections keep only their independent visibility", () => {
  const harness = createHarness()
  const page = instantiatePage(loadPlayerPage(harness))
  page.music = harness.music
  page.basis = {
    confirmed_state: "近期睡眠欠佳。",
    analysis_rationales: [{ summary: "依据已确认信息安排本次音乐。" }],
    state_tendency: "Qwen3.8",
  }

  assert.equal(page.analysisVisible, true)
  assert.equal(page.playerPresentation.analysis.sections.recentState.hasContent, true)
  assert.equal(page.playerPresentation.analysis.sections.rationales.hasContent, true)
  assert.equal(page.playerPresentation.analysis.sections.interpretation.hasContent, false)
})

test("PR-013: repeated explanation toggles execute page behavior without changing playback authorities", async () => {
  const harness = createHarness()
  const options = loadPlayerPage(harness)
  const page = instantiatePage(options)
  await page.load()
  assert.equal(page.analysisVisible, true)

  const before = {
    api: [harness.calls.getMusic, harness.calls.getMusicBasis],
    controller: page.playerController,
    audio: page.playerController.audioContext,
    music: page.music,
    taskId: harness.getTaskIdentity(),
    basis: page.basis,
    playerState: page.playerState,
    playing: page.playing,
    currentTime: page.playerState.currentTime,
    progressPercent: page.progressPresentation.percent,
  }

  page.toggleAnalysis()
  assert.equal(page.analysisExpanded, true)
  page.toggleAnalysis()
  assert.equal(page.analysisExpanded, false)
  page.toggleAnalysis()
  assert.equal(page.analysisExpanded, true)

  assert.deepEqual([harness.calls.getMusic, harness.calls.getMusicBasis], before.api)
  assert.equal(harness.calls.controllerCreates, 1)
  assert.equal(harness.calls.audioCreates, 0)
  assert.equal(harness.calls.controllerActions, 0)
  assert.equal(harness.calls.generationWrites, 0)
  assert.equal(harness.calls.toasts, 0)
  assert.equal(page.playerController, before.controller)
  assert.equal(page.playerController.audioContext, before.audio)
  assert.equal(page.music, before.music)
  assert.equal(harness.getTaskIdentity(), before.taskId)
  assert.equal(page.basis, before.basis)
  assert.equal(page.playerState, before.playerState)
  assert.equal(page.playing, before.playing)
  assert.equal(page.playerState.currentTime, before.currentTime)
  assert.equal(page.progressPresentation.percent, before.progressPercent)
})

test("expanded explanation renders only resolved presentation fields and no internal mode name", () => {
  const template = playerSource.match(/<template>([\s\S]*?)<\/template>/)[1]
  for (const heading of ["近期状态", "状态解析", "调适依据", "本次五音配置", "音乐设计"]) {
    assert.match(template, new RegExp(heading))
  }
  assert.match(template, /playerPresentation\.analysis\.stateSummary/)
  assert.match(template, /playerPresentation\.analysis\.tendency/)
  assert.match(template, /playerPresentation\.analysis\.rationales/)
  assert.match(template, /playerPresentation\.analysis\.primaryTone/)
  assert.match(template, /playerPresentation\.analysis\.parameters/)
  assert.doesNotMatch(template, /\{\{\s*playerPresentation\.analysis\.mode\s*\}\}/)

  const model = buildMusicPresentation({ music: createHarness().music, basis: createHarness().basis })
  assert.equal(model.analysis.stateSummary.text, "睡眠欠佳，食欲不振。")
  assert.equal(model.analysis.tendency.text, "近期恢复状态不足。")
  assert.equal(model.analysis.rationales.rows[0].text, "依据已确认的近期状态选择舒缓方案。")
  assert.equal(model.analysis.parameters.bpm.text, "58 BPM")
  assert.deepEqual(model.analysis.parameters.instruments.values, ["古琴", "洞箫"])
  assert.deepEqual(model.analysis.parameters.ambience.values, ["自然声"])
})

test("PR-024/PR-030: explanation remains local presentation and Player stays read-only", () => {
  assert.match(playerSource, /createPlayerController/)
  assert.doesNotMatch(playerSource, /allowCreate\s*:\s*true/)
  assert.doesNotMatch(playerSource, /createAssessment|createDiagnosis|createPrescription|startMusicGeneration|pollMusicGeneration|cancelMusicGeneration|createMusicGenerationSession|RAG|Qwen|Provider/)
  assert.doesNotMatch(playerSource, /v31-tone-theme/)
  assert.match(playerSource, /playerPresentation\.sourceLabel\.text/)
  assert.doesNotMatch(playerSource, /\{\{\s*playerPresentation\.sourceLabel\s*\}\}/)
  assert.match(playerSource, /neutral-hero-frame/)
  assert.match(playerSource, /v-if="playerPresentation\.hasPrimaryTone" class="tone-hero-frame"/)
  assert.match(playerSource, /v-if="playerPresentation\.instruments\.hasValues \|\| playerPresentation\.ambience\.hasValues"/)
  assert.doesNotMatch(playerSource, /—　\{\{\s*playerPresentation\.instruments\.displayText/)
  assert.match(playerSource, /primaryTone\.explanation\.text/)
  assert.match(playerSource, /secondaryTone\.explanation\.text/)
})

test("PR-024: detached authorized audio callback does not depend on Player this binding", async () => {
  const previous = globalThis.uni
  const downloads = []
  globalThis.uni = {
    downloadFile(options) {
      downloads.push(options)
      options.success({ statusCode: 200, tempFilePath: "/tmp/audio.mp3" })
    },
  }
  try {
    const { apiV3 } = await import(`../common/api-v3.js?detached-${Date.now()}`)
    const download = apiV3.fetchAuthorizedAudio
    assert.equal(await download("/api/v3/music/assets/music_1/stream"), "/tmp/audio.mp3")
    assert.equal(downloads.length, 1)
    assert.equal(downloads[0].url, "http://localhost:8000/api/v3/music/assets/music_1/stream")
  } finally {
    globalThis.uni = previous
  }
})
