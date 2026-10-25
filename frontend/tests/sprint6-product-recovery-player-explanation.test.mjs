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
    .replace(
      /import \{ seekRatioFromEvent \} from [^\r\n]+\r?\n/,
      "const seekRatioFromEvent = __deps.seekRatioFromEvent\n",
    )
    // Sprint 7 FE-2B：历史音乐通道依赖（本测试不驱动历史分支，注入安全 stub）
    .replace(
      /import \{ createMusicLibraryApi \} from [^\r\n]+\r?\n/,
      "const createMusicLibraryApi = __deps.createMusicLibraryApi\n",
    )
    .replace(
      /import \{ createUniMusicLibraryTransport, readV3AccessToken, MUSIC_LIBRARY_LIVE_ENABLED \} from [^\r\n]+\r?\n/,
      "const { createUniMusicLibraryTransport, readV3AccessToken } = __deps; const MUSIC_LIBRARY_LIVE_ENABLED = false\n",
    )
    .replace(
      /import \{\s*createHistoricalMusicSession,\s*resolvePlayableAudio,\s*\} from [^\r\n]+\r?\n/,
      "const { createHistoricalMusicSession, resolvePlayableAudio } = __deps\n",
    )
    .replace(/import \{ putHistoricalFeedback \} from [^\r\n]+\r?\n/, "const putHistoricalFeedback = __deps.putHistoricalFeedback\n")
    .replace("export default {", "__pageOptions = {")

  const context = {
    __pageOptions: null,
    __deps: {
      putHistoricalFeedback: () => { throw new Error("Historical branch not configured in legacy fixture") },
      apiV3,
      createPlayerController,
      buildMusicPresentation,
      presentProgress,
      seekRatioFromEvent: () => null,
      createMusicLibraryApi: () => ({
        listMusicAssets: async () => ({ items: [], next_cursor: null, has_more: false }),
        getMusicAsset: async () => null,
        recordPlayStarted: async () => ({ ok: true }),
      }),
      createUniMusicLibraryTransport: () => async () => ({ data: {} }),
      readV3AccessToken: () => "",
      createHistoricalMusicSession: () => ({
        open: async () => null,
        reportPlayStarted: async () => ({ reported: false }),
        reset() {},
        hasOwnerChanged: () => false,
      }),
      resolvePlayableAudio: () => null,
    },
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
    getCurrentUserGoal: 0,
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
    mode_explanation: { label: "个性化五音方案", explanation: "本次确认信息已形成明确的音乐侧重点，因此采用个性化五音方案。" },
    confirmed_state: "睡眠欠佳，食欲不振。",
    state_tendency: "近期恢复状态不足。",
    analysis_rationales: [{ summary: "依据已确认的近期状态选择舒缓方案。" }],
    primary_tone: { tone: "gong", explanation: "宫音帮助形成稳定、舒缓的音乐基调。" },
    secondary_tone: { tone: "shang", explanation: "商音让整体听感更清透。" },
    tone_weights: { gong: 0.4, jiao: 0.2, zhi: 0.15, shang: 0.15, yu: 0.1 },
    bpm: { value: 58, explanation: "采用舒缓节奏。" },
    instruments: { values: ["古琴", "洞箫"], explanation: "温润音色减少听觉刺激。" },
    ambience: { values: ["流水"], explanation: "自然声营造安静氛围。" },
    energy: { value: "低能量", explanation: "采用平稳舒缓的能量走向，减少突兀变化。" },
    structure: { value: "渐入 · 稳定展开 · 渐收", explanation: "采用渐入、主体展开、渐收的结构，让音乐衔接自然。" },
    duration: { seconds: 300 },
    disclaimer: "本内容用于解释本次音乐生成依据，不构成医学诊断或治疗建议。",
  }
  const userGoal = { primary_goal: "relaxation", secondary_goal: "stress_relief", custom_goal_text: null }
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
    getCurrentUserGoal() { calls.getCurrentUserGoal += 1; return userGoal },
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
    userGoal,
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

test("F-R2: one authoritative state section shows a collapsed explanation", () => {
  const harness = createHarness()
  const page = instantiatePage(loadPlayerPage(harness))
  page.music = harness.music
  page.basis = { confirmed_state: "近期睡眠欠佳。" }

  assert.equal(page.analysisVisible, true)
  assert.equal(page.analysisExpanded, false)
  assert.deepEqual(
    Object.fromEntries(Object.entries(page.playerPresentation.analysis.playerSections).map(([key, section]) => [key, section.hasContent])),
    {
      recentState: true,
      interpretation: false,
      direction: false,
      fiveTonePlan: false,
      musicDesign: false,
      userGoal: false,
    },
  )

  page.toggleAnalysis()
  assert.equal(page.analysisExpanded, true)
})

test("latest Owner contract gives tendency and rationale their own Player sections", () => {
  const harness = createHarness()
  const page = instantiatePage(loadPlayerPage(harness))
  page.music = harness.music
  page.basis = {
    confirmed_state: "近期睡眠欠佳。",
    analysis_rationales: [{ summary: "依据已确认信息安排本次音乐。" }],
    state_tendency: "Qwen3.8",
  }

  assert.equal(page.analysisVisible, true)
  assert.equal(page.playerPresentation.analysis.playerSections.recentState.hasContent, true)
  assert.equal(page.playerPresentation.analysis.playerSections.interpretation.hasContent, false)
  assert.equal(page.playerPresentation.analysis.playerSections.direction.hasContent, true)
})

test("PR-013: repeated explanation toggles execute page behavior without changing playback authorities", async () => {
  const harness = createHarness()
  const options = loadPlayerPage(harness)
  const page = instantiatePage(options)
  await page.load()
  assert.equal(page.analysisVisible, true)
  assert.equal(harness.calls.getCurrentUserGoal, 1)

  const before = {
    api: [harness.calls.getMusic, harness.calls.getMusicBasis, harness.calls.getCurrentUserGoal],
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

  assert.deepEqual([harness.calls.getMusic, harness.calls.getMusicBasis, harness.calls.getCurrentUserGoal], before.api)
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

test("PR-012: Player re-entry resets explanation to the default collapsed state", () => {
  const harness = createHarness()
  const options = loadPlayerPage(harness)
  const page = instantiatePage(options)
  page.playerController = harness.controller
  page.analysisExpanded = true

  options.onShow.call(page)

  assert.equal(page.analysisExpanded, false)
})

test("expanded explanation renders the frozen 01-05 presentation without engineering labels or a preference claim", () => {
  const template = playerSource.match(/<template>([\s\S]*?)<\/template>/)[1]
  for (const heading of ["01", "资料状态", "02", "状态解读", "03", "本次调适方向", "04", "五音方案", "05", "音乐设计"]) {
    assert.match(template, new RegExp(heading))
  }
  for (const forbidden of ["状态解析", "调适依据", "本次五音配置", "主音依据：", "辅音依据：", "节奏依据：", "乐器依据：", "氛围依据："]) {
    assert.doesNotMatch(template, new RegExp(forbidden))
  }
  assert.match(template, /playerPresentation\.analysis\.stateSummary/)
  assert.match(template, /playerPresentation\.analysis\.tendency/)
  assert.match(template, /playerPresentation\.analysis\.rationales/)
  assert.match(template, /playerPresentation\.analysis\.modeExplanation/)
  assert.match(template, /playerPresentation\.analysis\.primaryTone/)
  assert.match(template, /playerPresentation\.analysis\.secondaryTone/)
  assert.doesNotMatch(template, /toneWeights/)
  assert.doesNotMatch(template, /sectionTwoTitle|planLabel/)
  assert.doesNotMatch(template, /偏好已纳入/)
  assert.doesNotMatch(template, /playerPresentation\.analysis\.userGoal/)
  assert.match(template, /playerPresentation\.analysis\.parameters/)
  assert.doesNotMatch(template, /\{\{\s*playerPresentation\.analysis\.mode\s*\}\}/)

  const model = buildMusicPresentation({ music: createHarness().music, basis: createHarness().basis })
  assert.equal(model.analysis.stateSummary.text, "睡眠欠佳，食欲不振。")
  assert.equal(model.analysis.tendency.text, "近期恢复状态不足。")
  assert.equal(model.analysis.modeExplanation.text, "本次确认信息已形成明确的音乐侧重点，因此采用个性化五音方案。")
  assert.equal(model.analysis.primaryTone.explanation.text, "宫音帮助形成稳定、舒缓的音乐基调。")
  assert.equal(model.analysis.secondaryTone.explanation.text, "商音让整体听感更清透。")
  assert.equal(model.analysis.parameters.bpm.text, "58 BPM")
  assert.deepEqual(model.analysis.parameters.instruments.values, ["古琴", "洞箫"])
  assert.deepEqual(model.analysis.parameters.ambience.values, ["流水"])
  assert.equal(model.analysis.parameters.energy.value, "低能量")
  assert.equal(model.analysis.parameters.structure.value, "渐入 · 稳定展开 · 渐收")
  assert.equal(Object.hasOwn(model.analysis, "toneWeights"), false)
  assert.doesNotMatch(JSON.stringify(model), /\b\d{1,3}%\b/)
})

test("personalized explanation does not invent a missing secondary tone", () => {
  const analysis = buildMusicPresentation({
    basis: {
      regulation_mode: "personalized_five_tone",
      confirmed_state: "近期状态已确认。",
      primary_tone: { tone: "gong", explanation: "后端主音解释。" },
      secondary_tone: null,
      mode_explanation: { label: "个性化五音方案", explanation: "后端模式解释。" },
    },
  }).analysis

  assert.equal(analysis.hasPrimaryTone, true)
  assert.equal(analysis.hasSecondaryTone, false)
  assert.equal(analysis.secondaryTone.displayName, "")
})

test("historical gong explanation preserves backend limitations and arrangement intent without rewriting", () => {
  const limitation = "该主要调适方向缺少可公开引用的具体状态依据，暂不作进一步医学解释。"
  const basis = {
    regulation_mode: "personalized_five_tone",
    confirmed_state: "资料中记录的状态：用户确认的历史资料摘要。",
    state_tendency: "资料记录中的胁肋不适，是本次音乐调适可参考的状态信息。",
    analysis_rationales: [{ summary: limitation }],
    mode_explanation: { label: "个性化五音方案", explanation: "本次采用宫调作为主音的个性化五音方案。" },
    primary_tone: { tone: "gong", explanation: "既定五音对应关系中，脾对应宫调；本次使用宫调作为主音。" },
    bpm: { value: 84, explanation: "围绕本次提振精神诉求，选择 84 BPM，希望形成轻快有活力的音乐推进。" },
    instruments: { values: ["笛"], explanation: "围绕本次提振精神诉求，采用笛作为主要音色，用于构成音乐主体，而非环境音背景。" },
    ambience: { values: ["微风"], explanation: "围绕本次情绪调适诉求，加入微风作为背景环境音层，希望营造轻柔的微风氛围。" },
  }
  const analysis = buildMusicPresentation({ basis }).analysis
  assert.equal(analysis.stateSummary.text, basis.confirmed_state)
  assert.equal(analysis.rationales.rows[0].text, limitation)
  assert.equal(analysis.modeExplanation.text, basis.mode_explanation.explanation)
  assert.equal(analysis.primaryTone.explanation.text, basis.primary_tone.explanation)
  for (const field of ["bpm", "instruments", "ambience"]) {
    assert.equal(analysis.parameters[field].explanation.text, basis[field].explanation)
  }
  assert.deepEqual(Object.values(analysis.playerSections).slice(0, 5).map(section => section.hasContent), [true, true, true, true, true])
  assert.equal(Object.hasOwn(analysis.parameters, "duration"), false)
})

test("integrated and basic explanations use only backend mode presentation", () => {
  for (const [mode, label, explanation] of [
    ["integrated_regulation", "综合调适", "后端综合调适解释。"],
    ["basic_wellness", "基础舒缓", "后端基础舒缓解释。"],
  ]) {
    const analysis = buildMusicPresentation({
      basis: {
        regulation_mode: mode,
        mode_explanation: { label, explanation },
        primary_tone: { tone: "gong", explanation: "不得展示。" },
        secondary_tone: { tone: "shang", explanation: "不得展示。" },
        tone_weights: { gong: 0.8, shang: 0.2 },
      },
    }).analysis

    assert.equal(analysis.modePlanLabel.text, label)
    assert.equal(analysis.modeExplanation.text, explanation)
    assert.equal(analysis.hasPrimaryTone, false)
    assert.equal(analysis.hasSecondaryTone, false)
    assert.equal(Object.hasOwn(analysis, "toneWeights"), false)
    assert.doesNotMatch(JSON.stringify(analysis), /宫音|商音|%/)
  }
})

test("missing backend explanation fields stay omitted without frontend prose", () => {
  const analysis = buildMusicPresentation({
    basis: {
      regulation_mode: "personalized_five_tone",
      primary_tone: { tone: "gong", explanation: "" },
      bpm: { value: 60, explanation: "" },
      instruments: { values: ["古琴"], explanation: "" },
      ambience: { values: [], explanation: "" },
    },
  }).analysis

  assert.equal(analysis.modePlanLabel.hasText, false)
  assert.equal(analysis.modeExplanation.hasText, false)
  assert.equal(analysis.primaryTone.explanation.hasText, false)
  assert.equal(analysis.parameters.bpm.explanation.hasText, false)
  assert.equal(analysis.parameters.energy.hasValue, false)
  assert.equal(analysis.parameters.structure.hasValue, false)
  assert.doesNotMatch(playerSource, /推荐时长|建议时长|调适时长/)
})

test("PR-024/PR-030: explanation remains local presentation and Player stays read-only", () => {
  assert.match(playerSource, /createPlayerController/)
  assert.doesNotMatch(playerSource, /allowCreate\s*:\s*true/)
  assert.doesNotMatch(playerSource, /createAssessment|createDiagnosis|createPrescription|startMusicGeneration|pollMusicGeneration|cancelMusicGeneration|createMusicGenerationSession|RAG|Qwen|Provider/)
  assert.doesNotMatch(playerSource, /v31-tone-theme/)
  assert.match(playerSource, /playerPresentation\.sourceLabel\.isFallback/)
  assert.doesNotMatch(playerSource, /\{\{\s*playerPresentation\.sourceLabel\s*\}\}/)
  assert.match(playerSource, /neutral-hero-frame/)
  assert.match(playerSource, /v-if="playerPresentation\.hasPrimaryTone" class="tone-hero-frame"/)
  const template = playerSource.match(/<template>([\s\S]*?)<\/template>/)[1]
  const top = template.split('<view class="music-summary-card">')[0]
  for (const duplicatedBinding of [
    /playerPresentation\.modeDisplayLabel/,
    /playerPresentation\.primaryTone\.displayText/,
    /playerPresentation\.instruments/,
    /playerPresentation\.ambience/,
    /playerPresentation\.sourceLabel/,
  ]) {
    assert.doesNotMatch(top, duplicatedBinding)
  }
  assert.doesNotMatch(top, /AI生成音乐/)
  assert.match(playerSource, /<view class="music-summary-card">[\s\S]*playerPresentation\.analysis\.parameters\.bpm/)
  assert.match(playerSource, /<view class="music-summary-card">[\s\S]*playerPresentation\.instruments/)
  assert.match(playerSource, /<view class="music-summary-card">[\s\S]*playerPresentation\.ambience/)
  assert.doesNotMatch(playerSource, /—　\{\{\s*playerPresentation\.instruments\.displayText/)
  assert.match(playerSource, /primaryTone\.explanation\.text/)
  assert.match(playerSource, /secondaryTone\.explanation\.text/)
})

test("Player places progress after the cover without a visible title row", () => {
  const presentation = buildMusicPresentation({
    music: { title: "生成音频 84 BPM" },
  })
  const template = playerSource.match(/<template>([\s\S]*?)<\/template>/)[1]

  assert.equal(presentation.title.displayText, "五音调适音乐")
  assert.doesNotMatch(template, /class="music-title"|playerPresentation\.title\.displayText/)
  assert.match(template, /class="hero-wrap"[\s\S]*class="progress-wrap"[\s\S]*class="controls"/)
  assert.match(template, /class="summary-heading"[\s\S]*?<text>本次音乐<\/text>/)
  assert.notEqual(presentation.title.displayText, "本次音乐")
})

test("omitted or null backend parameter explanations preserve values without blank copy", () => {
  const presentation = buildMusicPresentation({
    basis: {
      regulation_mode: "basic_wellness",
      bpm: { value: 60, explanation: null },
      instruments: { values: ["古琴"] },
      ambience: { values: ["溪流"], explanation: null },
    },
  })
  const parameters = presentation.analysis.parameters
  assert.equal(parameters.bpm.value, 60)
  assert.equal(parameters.instruments.hasValues, true)
  assert.equal(parameters.ambience.hasValues, true)
  for (const parameter of [parameters.bpm, parameters.instruments, parameters.ambience]) {
    assert.equal(parameter.explanation.hasText, false)
    assert.equal(parameter.explanation.text, "")
  }
  assert.equal(presentation.analysis.collapsed, true)
  assert.match(playerSource, /v-if="playerPresentation\.analysis\.parameters\.bpm\.explanation\.hasText"/)
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
