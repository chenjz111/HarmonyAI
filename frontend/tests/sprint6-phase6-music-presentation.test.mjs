/**
 * Sprint 6 Phase 6 — 蔡子鑫 Presentation Lane
 * 音乐展示层契约测试（MP-T1 ~ MP-T15 + 静态护栏）
 *
 * 被测对象：frontend/common/music-presentation.js（纯函数，无 uni / 无网络 / 无副作用）
 *
 * 覆盖冻结要求（S6-P6-caizixin-presentation.md）：
 *   MP-T1  null tone safe
 *   MP-T2  personalized tone displayed from backend only
 *   MP-T3  integrated / basic makes no false tone claim
 *   MP-T4  no invented ambience
 *   MP-T5  no invented instruments
 *   MP-T6  no invented track title
 *   MP-T7  no therapeutic clause
 *   MP-T8  no rationale regex invention
 *   MP-T9  measured duration finite
 *   MP-T10 null duration safe
 *   MP-T11 no NaN
 *   MP-T12 fallback labelled honestly
 *   MP-T13 failure copy uses authoritative message first
 *   MP-T14 empty fields produce neutral display
 *   MP-T15 analysis defaults collapsed
 *
 * 运行方式：cd frontend && node --test tests/sprint6-phase6-music-presentation.test.mjs
 * （沙箱内 node --test 子进程 spawn 受限时，可直接 `node tests/<file>` 等价执行）
 */

import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

import {
  ANALYSIS_TITLE,
  FAILURE_NEUTRAL_MESSAGE,
  FAILURE_TITLE,
  NEUTRAL_DISPLAY,
  SOURCE_LABEL_FALLBACK,
  SOURCE_LABEL_GENERATED,
  buildAnalysisViewModel,
  buildMusicPresentation,
  emptyMusicPresentation,
  presentAmbience,
  presentDuration,
  presentFallback,
  presentFailureDisplay,
  presentInstruments,
  presentPrimaryTone,
  presentProgress,
  presentRationales,
  presentSecondaryTone,
  presentSourceLabel,
  presentText,
  presentTitle,
  presentTone,
  presentToneWeights,
  resolvePlaybackDuration,
  toneDisplayName,
} from "../common/music-presentation.js"
import { UNKNOWN_TONE_THEME, toneThemeFor } from "../common/v31-tone-theme.js"

const TONE_CODES = ["gong", "shang", "jiao", "zhi", "yu"]
const WEIGHTS = { jiao: 0.1, zhi: 0.1, gong: 0.6, shang: 0.1, yu: 0.1 }
const TONE_NAME_PATTERN = /宫音|商音|角音|徵音|羽音/

/** 主题表历史上硬编码过的疗愈 / 性格文案：Phase 6 后不得再出现在任何展示结果里。 */
const RETIRED_TRAIT_WORDS = [
  "沉稳", "平和", "安定",
  "柔和", "收敛", "安养",
  "生机", "向上", "希望",
  "热情", "光明", "奋进",
  "智慧", "深远",
]
const RETIRED_THEME_TITLES = ["静水流深", "清风和鸣", "春山新绿", "秋山红叶", "寒江映月"]

const root = resolve(import.meta.dirname, "..")

// ------------------------------------------------------------------ MP-T1

test("MP-T1 null 主音安全：不崩、不主张、不回退成宫", () => {
  for (const mode of ["personalized_five_tone", "integrated_regulation", "basic_wellness", "", undefined, null]) {
    for (const tone of [null, undefined, "", "  "]) {
      const primary = presentPrimaryTone(mode, tone)
      assert.equal(primary.hasTone, false, `${mode} + ${JSON.stringify(tone)} 不得产生主音`)
      assert.equal(primary.code, "")
      assert.equal(primary.glyph, "")
      assert.equal(primary.displayText, "")
      const secondary = presentSecondaryTone(mode, tone)
      assert.equal(secondary.hasTone, false)
      assert.equal(secondary.displayText, "")
    }
  }

  // 未知音同样是空状态，绝不回退成"宫"
  for (const tone of ["unknown-tone", "宫音x", 42, {}, []]) {
    const primary = presentTone("personalized_five_tone", tone)
    assert.equal(primary.hasTone, false, `${JSON.stringify(tone)} 应保持空状态`)
    assert.notEqual(primary.glyph, "宫")
  }

  // 模型层：personalized 但后端没给主音 → 整份展示模型不出现任何五音文案
  const model = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "", title: "" },
    basis: { regulation_mode: "personalized_five_tone", primary_tone: null, secondary_tone: null },
  })
  assert.equal(model.hasPrimaryTone, false)
  assert.equal(model.primaryTone.displayText, "")
  assert.doesNotMatch(JSON.stringify(model), TONE_NAME_PATTERN)
  assert.doesNotMatch(JSON.stringify(model), /[宫商角徵羽]/)
})

// ------------------------------------------------------------------ MP-T2

test("MP-T2 主音只来自后端权威：personalized + 真实主音才展示", () => {
  const primary = presentPrimaryTone("personalized_five_tone", "jiao")
  assert.equal(primary.hasTone, true)
  assert.equal(primary.code, "jiao")
  assert.equal(primary.glyph, "角")
  assert.equal(primary.displayName, "角音")
  assert.equal(primary.claim, "角音为主")

  // 中文展示名 / 对象形态也可被归一，但仍以权威 code 为准
  assert.equal(presentPrimaryTone("personalized_five_tone", "宫音").code, "gong")
  assert.equal(presentPrimaryTone("personalized_five_tone", { tone: "zhi" }).code, "zhi")
  assert.equal(toneDisplayName("jiao"), "角音")
  assert.equal(toneDisplayName("unknown-tone"), "")

  // 缺少权威 mode 时：即使有主音也不得展示（前端不推断 mode）
  assert.equal(presentPrimaryTone("", "jiao").hasTone, false)
  assert.equal(presentPrimaryTone(undefined, { tone: "gong" }).hasTone, false)
  assert.equal(presentPrimaryTone("legacy_mode", "gong").hasTone, false)

  // 模型层：mode 来自 basis、tone 来自 asset tone_code
  const model = buildMusicPresentation({
    music: { tone_code: "jiao" },
    basis: { regulation_mode: "personalized_five_tone", primary_tone: { tone: "jiao" } },
  })
  assert.equal(model.mode, "personalized_five_tone")
  assert.equal(model.sealText, "主音")
  assert.equal(model.primaryTone.code, "jiao")
  assert.equal(model.primaryTone.displayName, "角音")

  // asset 只有 tone_code、basis 缺失时仍以 asset 为准（不因缺 basis 而丢主音）
  const assetOnly = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "yu" },
    basis: null,
  })
  assert.equal(assetOnly.primaryTone.code, "yu")
  assert.equal(assetOnly.primaryTone.displayName, "羽音")
})

// ------------------------------------------------------------------ MP-T3

test("MP-T3 integrated / basic 不产生任何虚假主音主张（权重仍保留）", () => {
  const integrated = buildMusicPresentation({
    music: { regulation_mode: "integrated_regulation", tone_code: "gong" },
    basis: {
      regulation_mode: "integrated_regulation",
      primary_tone: { tone: "gong" },
      secondary_tone: null,
      tone_weights: WEIGHTS,
    },
  })
  assert.equal(integrated.modeLabel, "综合调适")
  assert.equal(integrated.hasPrimaryTone, false)
  assert.equal(integrated.primaryTone.claim, "")
  assert.equal(integrated.sealText, "综合调适")
  assert.doesNotMatch(JSON.stringify(integrated), TONE_NAME_PATTERN)
  // Phase 1A 不变量：integrated 仍保留完整 tone weights（逐字）
  assert.deepEqual(integrated.toneWeights.weights, WEIGHTS)
  assert.equal(integrated.toneWeights.hasWeights, true)

  const basic = buildMusicPresentation({
    music: { regulation_mode: "basic_wellness", tone_code: "gong" },
    basis: { regulation_mode: "basic_wellness", primary_tone: { tone: "gong" }, tone_weights: null },
  })
  assert.equal(basic.modeLabel, "基础舒缓")
  assert.equal(basic.hasPrimaryTone, false)
  assert.equal(basic.sealText, "基础舒缓")
  assert.doesNotMatch(JSON.stringify(basic), TONE_NAME_PATTERN)
  assert.equal(basic.toneWeights.hasWeights, false)

  // 未知 mode：不发明 mode、不合成主音（中性不可用态）
  const unknown = buildMusicPresentation({
    music: { tone_code: "gong" },
    basis: { tone_weights: WEIGHTS },
  })
  assert.equal(unknown.mode, "")
  assert.equal(unknown.modeLabel, "")
  assert.equal(unknown.modeDisplayLabel, NEUTRAL_DISPLAY)
  assert.equal(unknown.sealText, "")
  assert.equal(unknown.hasPrimaryTone, false)
  assert.deepEqual(unknown.toneWeights.weights, WEIGHTS)
})

// ------------------------------------------------------------------ MP-T4

test("MP-T4 不发明氛围 / 环境音", () => {
  const empty = presentAmbience([])
  assert.equal(empty.hasValues, false)
  assert.equal(empty.text, "")
  assert.equal(empty.displayText, NEUTRAL_DISPLAY)
  assert.deepEqual(empty.values, [])

  for (const value of [null, undefined, "流水", 123, {}]) {
    const neutral = presentAmbience(value)
    assert.equal(neutral.hasValues, false, `${JSON.stringify(value)} 不是值列表，应保持中性`)
    assert.equal(neutral.displayText, NEUTRAL_DISPLAY)
  }

  // 后端给了就原样透出（去空 / 去重），不增不减
  const given = presentAmbience(["流水", "  ", "流水", "雨声"], { source: "basis" })
  assert.deepEqual(given.values, ["流水", "雨声"])
  assert.equal(given.text, "流水 · 雨声")
  assert.equal(given.source, "basis")

  const model = buildMusicPresentation({
    music: { regulation_mode: "basic_wellness" },
    basis: { regulation_mode: "basic_wellness", ambience: { values: [] } },
  })
  assert.equal(model.ambience.hasValues, false)
  assert.equal(model.ambience.displayText, NEUTRAL_DISPLAY)
  assert.doesNotMatch(JSON.stringify(model), /安静环境/)
})

// ------------------------------------------------------------------ MP-T5

test("MP-T5 不发明乐器（绝不用主题表乐器兜底）", () => {
  const none = presentInstruments([])
  assert.equal(none.hasValues, false)
  assert.equal(none.text, "")
  assert.equal(none.displayText, NEUTRAL_DISPLAY)

  const model = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "jiao", instrument_labels: [] },
    basis: { regulation_mode: "personalized_five_tone", primary_tone: { tone: "jiao" } },
  })
  assert.equal(model.instruments.hasValues, false)
  assert.equal(model.instruments.displayText, NEUTRAL_DISPLAY)
  // 主题表历史上按音硬编码的乐器（古琴 / 洞箫 / 笙 …）不得出现
  assert.doesNotMatch(JSON.stringify(model), /古琴|洞箫|笙|琵琶|排箫|竹笛/)

  // 后端给了乐器：asset 优先，缺失时回落到本次 basis，并标注来源
  const fromAsset = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "jiao", instrument_labels: ["古琴"] },
    basis: { regulation_mode: "personalized_five_tone", primary_tone: { tone: "jiao" }, instruments: { values: ["笙"] } },
  })
  assert.deepEqual(fromAsset.instruments.values, ["古琴"])
  assert.equal(fromAsset.instruments.source, "asset")

  const fromBasis = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "jiao", instrument_labels: [] },
    basis: { regulation_mode: "personalized_five_tone", primary_tone: { tone: "jiao" }, instruments: { values: ["笙"] } },
  })
  assert.deepEqual(fromBasis.instruments.values, ["笙"])
  assert.equal(fromBasis.instruments.source, "basis")
})

// ------------------------------------------------------------------ MP-T6

test("MP-T6 不发明曲名（绝不用主题名充当本次曲名）", () => {
  const empty = presentTitle("")
  assert.equal(empty.hasText, false)
  assert.equal(empty.text, "")
  assert.equal(empty.displayText, NEUTRAL_DISPLAY)

  for (const value of [null, undefined, "   ", {}, []]) {
    assert.equal(presentTitle(value).hasText, false, `${JSON.stringify(value)} 不得产生曲名`)
  }

  const model = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "gong", title: "" },
    basis: null,
  })
  assert.equal(model.title.hasText, false)
  assert.equal(model.title.displayText, NEUTRAL_DISPLAY)
  for (const retired of RETIRED_THEME_TITLES) {
    assert.doesNotMatch(JSON.stringify(model), new RegExp(retired))
  }

  assert.equal(presentTitle("本次音乐").text, "本次音乐")
})

// ------------------------------------------------------------------ MP-T7

test("MP-T7 不出现硬编码疗愈 / 性格结论文案", () => {
  const model = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "gong", title: "本次音乐" },
    basis: {
      regulation_mode: "personalized_five_tone",
      primary_tone: { tone: "gong" },
      secondary_tone: { tone: "shang" },
    },
  })
  const text = JSON.stringify(model)
  for (const word of RETIRED_TRAIT_WORDS) {
    assert.doesNotMatch(text, new RegExp(word), `展示模型不得包含疗愈结论文案「${word}」`)
  }
  // 主题表本身也不再携带事实 / 结论字段
  for (const code of TONE_CODES) {
    const theme = toneThemeFor(code)
    for (const key of ["traits", "instruments", "ambience", "title", "instrument"]) {
      assert.equal(theme[key], undefined, `${code} 主题不得携带事实字段 ${key}`)
    }
  }
})

// ------------------------------------------------------------------ MP-T8

test("MP-T8 不用正则编造解析依据语义", () => {
  const summary = "近期睡眠偏浅，提示心神不宁。"
  const rationales = presentRationales([{ summary, evidence_refs: [] }])
  assert.equal(rationales.hasRows, true)
  assert.equal(rationales.rows.length, 1)
  assert.equal(rationales.rows[0].index, 1)
  // 原样展示，不切分、不补语义
  assert.equal(rationales.rows[0].text, summary)
  assert.equal(rationales.rows[0].source, undefined)
  assert.equal(rationales.rows[0].target, undefined)
  assert.doesNotMatch(JSON.stringify(rationales), /作为本次调适依据/)

  const second = presentRationales([{ summary: "提示A" }, { summary: "提示B" }, { text: "提示C" }])
  assert.deepEqual(second.rows.map((row) => row.text), ["提示A", "提示B", "提示C"])
  assert.deepEqual(second.rows.map((row) => row.index), [1, 2, 3])

  for (const items of [null, undefined, [], "summary", [{}, null, { summary: "   " }]]) {
    const empty = presentRationales(items)
    assert.equal(empty.hasRows, false, `${JSON.stringify(items)} 不得产生依据行`)
    assert.deepEqual(empty.rows, [])
  }
})

// ------------------------------------------------------------------ MP-T9

test("MP-T9 实测时长是播放时长权威（有限、可格式化）", () => {
  const playback = resolvePlaybackDuration({ measuredSeconds: 238.99428571, assetSeconds: 60 })
  assert.equal(playback.source, "measured")
  assert.equal(playback.seconds, 238.99428571)
  assert.ok(Number.isFinite(playback.seconds))

  const duration = presentDuration(playback.seconds)
  assert.equal(duration.known, true)
  assert.equal(duration.text, "03:58")
  assert.equal(duration.minutes, 4)
  assert.equal(duration.minutesText, "4分钟")

  // 没有实测值时才是 asset 时长兜底；都没有 → unknown
  assert.deepEqual(resolvePlaybackDuration({ assetSeconds: 180 }), { source: "asset", seconds: 180 })
  assert.deepEqual(resolvePlaybackDuration({}), { source: "unknown", seconds: null })
  assert.deepEqual(resolvePlaybackDuration(), { source: "unknown", seconds: null })
  // 实测值非法（0 / 非数）时不得抢占权威
  assert.equal(resolvePlaybackDuration({ measuredSeconds: 0, assetSeconds: 180 }).source, "asset")
  assert.equal(resolvePlaybackDuration({ measuredSeconds: "abc", assetSeconds: 180 }).source, "asset")

  const model = buildMusicPresentation({ music: { duration_seconds: 60 }, measuredSeconds: 238.99428571 })
  assert.equal(model.playbackSource, "measured")
  assert.equal(model.duration.text, "03:58")
  assert.equal(model.duration.minutesText, "4分钟")
})

// ------------------------------------------------------------------ MP-T10

test("MP-T10 时长缺失 / 非法一律安全（显示 --:--）", () => {
  for (const value of [null, undefined, "", "abc", NaN, Infinity, -5, -0.1, {}, []]) {
    const duration = presentDuration(value)
    assert.equal(duration.known, false, `${JSON.stringify(value)} 应视为未知时长`)
    assert.equal(duration.seconds, null)
    assert.equal(duration.text, "--:--")
    assert.equal(duration.displayText, "--:--")
    assert.equal(duration.minutes, null)
    assert.equal(duration.minutesText, NEUTRAL_DISPLAY)
  }

  // 0 是合法秒数但不足以作为"已知时长"展示（不编造 0 分钟）
  assert.equal(presentDuration(0).known, false)
  assert.equal(presentDuration(0).text, "--:--")

  const model = buildMusicPresentation({ music: { duration_seconds: null } })
  assert.equal(model.duration.text, "--:--")
  assert.equal(model.playbackSource, "unknown")
})

// ------------------------------------------------------------------ MP-T11

test("MP-T11 进度 / 百分比绝不产生 NaN 或 Infinity", () => {
  const cases = [
    presentProgress({ currentSeconds: 0, totalSeconds: 0 }),
    presentProgress({ currentSeconds: null, totalSeconds: null }),
    presentProgress({ currentSeconds: -1, totalSeconds: -1 }),
    presentProgress({ currentSeconds: NaN, totalSeconds: NaN }),
    presentProgress({ currentSeconds: Infinity, totalSeconds: Infinity }),
    presentProgress({ currentSeconds: 999, totalSeconds: 100 }),
    presentProgress({ currentSeconds: 30, totalSeconds: 120 }),
    presentProgress({}),
  ]
  for (const item of cases) {
    assert.equal(Number.isFinite(item.percent), true)
    assert.doesNotMatch(`${item.percent}|${item.currentText}|${item.totalText}`, /NaN|Infinity/)
    assert.equal(typeof item.hasProgress, "boolean")
  }

  assert.equal(presentProgress({ currentSeconds: 30, totalSeconds: 120 }).percent, 25)
  assert.equal(presentProgress({ currentSeconds: 999, totalSeconds: 100 }).percent, 100)
  assert.equal(presentProgress({ currentSeconds: 30, totalSeconds: 0 }).percent, 0)
  assert.equal(presentProgress({ currentSeconds: 30, totalSeconds: 0 }).hasProgress, false)
  assert.equal(presentProgress({ currentSeconds: 30, totalSeconds: 0 }).totalText, "--:--")

  const model = buildMusicPresentation({ music: { duration_seconds: null } })
  assert.doesNotMatch(JSON.stringify(model), /NaN|Infinity/)
  assert.equal(model.progress.hasProgress, false)
})

// ------------------------------------------------------------------ MP-T12

test("MP-T12 fallback 如实标注，绝不伪装成实时生成", () => {
  const applied = presentFallback({ applied: true, reason_code: "PROVIDER_UNAVAILABLE" })
  assert.equal(applied.applied, true)
  assert.equal(applied.label, SOURCE_LABEL_FALLBACK)
  assert.equal(applied.reasonCode, "PROVIDER_UNAVAILABLE")
  assert.doesNotMatch(applied.label, /AI生成/)

  const notApplied = presentFallback({ applied: false, reason_code: null })
  assert.equal(notApplied.applied, false)
  assert.equal(notApplied.label, "")

  // 后端任务状态是权威：即使 fallback 字段缺失，matched_fallback 也必须如实标注
  const fromStatus = presentFallback(null, { status: "matched_fallback", sourceType: "matched_fallback" })
  assert.equal(fromStatus.applied, true)
  assert.equal(fromStatus.label, SOURCE_LABEL_FALLBACK)

  // 未知：既不承认也不否认，不产生任何标签
  assert.equal(presentFallback(null, {}).applied, null)
  assert.equal(presentFallback(null, {}).label, "")

  assert.equal(presentSourceLabel({ status: "matched_fallback" }).text, SOURCE_LABEL_FALLBACK)
  assert.equal(presentSourceLabel({ status: "succeeded", sourceType: "generated" }).text, SOURCE_LABEL_GENERATED)
  const unknownSource = presentSourceLabel({})
  assert.equal(unknownSource.text, "")
  assert.equal(unknownSource.isUnknown, true)

  const model = buildMusicPresentation({
    music: {
      status: "matched_fallback",
      source_label: SOURCE_LABEL_FALLBACK,
      music_ref: { source_type: "matched_fallback" },
      fallback: { applied: true, reason_code: "PROVIDER_UNAVAILABLE" },
    },
  })
  assert.equal(model.sourceLabel.text, SOURCE_LABEL_FALLBACK)
  assert.equal(model.sourceLabel.isFallback, true)
  assert.equal(model.fallback.applied, true)
  assert.doesNotMatch(JSON.stringify(model.sourceLabel), /AI生成/)
})

// ------------------------------------------------------------------ MP-T13

test("MP-T13 失败文案以权威信息为先，且技术失败不伪装成基础舒缓", () => {
  const authoritative = presentFailureDisplay({
    code: "PROVIDER_ERROR",
    message: "生成服务暂时不可用，请稍后重试。",
  })
  assert.equal(authoritative.isFailure, true)
  assert.equal(authoritative.isTechnicalFailure, true)
  assert.equal(authoritative.messageSource, "authoritative")
  assert.equal(authoritative.message, "生成服务暂时不可用，请稍后重试。")
  assert.equal(authoritative.code, "PROVIDER_ERROR")
  assert.equal(authoritative.title, FAILURE_TITLE)
  assert.equal(authoritative.degradedToWellness, false)
  assert.equal(authoritative.mode, "")
  assert.equal(authoritative.modeLabel, "")

  const neutral = presentFailureDisplay({ code: "UNKNOWN" })
  assert.equal(neutral.messageSource, "neutral")
  assert.equal(neutral.message, FAILURE_NEUTRAL_MESSAGE)
  assert.doesNotMatch(neutral.message, /基础舒缓|综合调适|五音|宫/)

  // 长文本与对象 message 也安全
  const weird = presentFailureDisplay({ message: { text: "不该被当成文案" } })
  assert.equal(weird.messageSource, "neutral")
  assert.equal(weird.message, FAILURE_NEUTRAL_MESSAGE)

  // 重试语义（P6-D2）：有可恢复任务只给"继续等待"，终态重试=新的生成请求
  const running = presentFailureDisplay({}, { taskStatus: "running" })
  assert.equal(running.retry.resumeExistingTask, true)
  assert.equal(running.retry.retryCreatesNewAttempt, false)
  assert.equal(running.retry.resumeLabel, "继续等待本次生成")

  const terminal = presentFailureDisplay({}, { taskStatus: "failed" })
  assert.equal(terminal.retry.retryCreatesNewAttempt, true)
  assert.equal(terminal.retry.resumeExistingTask, false)
  assert.match(terminal.retry.notice, /新的生成请求/)
  assert.equal(presentFailureDisplay({}, { terminal: true }).retry.retryCreatesNewAttempt, true)

  // 失败模型不携带任何音乐事实（不把上次的音乐当成这次的结果）
  const model = buildMusicPresentation({
    music: { title: "本次音乐", instrument_labels: ["古琴"], duration_seconds: 180 },
    failure: { code: "X", message: "服务不可用" },
  })
  assert.equal(model.isFailure, true)
  assert.equal(model.title.hasText, false)
  assert.equal(model.instruments.hasValues, false)
  assert.equal(model.duration.text, "--:--")
  assert.equal(model.hasPrimaryTone, false)
  assert.doesNotMatch(JSON.stringify(model), /古琴|本次音乐/)
  assert.equal(model.failure.message, "服务不可用")
})

// ------------------------------------------------------------------ MP-T14

test("MP-T14 空字段一律产生中性展示，长文本被安全截断", () => {
  const empty = emptyMusicPresentation()
  assert.equal(empty.isEmpty, true)
  assert.equal(empty.isFailure, false)
  assert.equal(empty.mode, "")
  assert.equal(empty.modeLabel, "")
  assert.equal(empty.modeDisplayLabel, NEUTRAL_DISPLAY)
  assert.equal(empty.sealText, "")
  assert.equal(empty.hasPrimaryTone, false)
  assert.equal(empty.primaryTone.displayText, "")
  assert.equal(empty.secondaryTone.displayText, "")
  assert.equal(empty.toneWeights.hasWeights, false)
  assert.equal(empty.toneWeights.displayText, NEUTRAL_DISPLAY)
  assert.equal(empty.title.displayText, NEUTRAL_DISPLAY)
  assert.equal(empty.instruments.displayText, NEUTRAL_DISPLAY)
  assert.equal(empty.ambience.displayText, NEUTRAL_DISPLAY)
  assert.equal(empty.duration.text, "--:--")
  assert.equal(empty.sourceLabel, "")
  assert.equal(empty.fallback.applied, null)
  assert.equal(empty.disclaimer.displayText, NEUTRAL_DISPLAY)
  assert.equal(empty.analysis.collapsed, true)
  assert.doesNotMatch(JSON.stringify(empty), /NaN|Infinity|[宫商角徵羽]/)

  const built = buildMusicPresentation({ music: {}, basis: {} })
  assert.equal(built.isEmpty, false)
  assert.equal(built.title.displayText, NEUTRAL_DISPLAY)
  assert.equal(built.hasPrimaryTone, false)
  assert.equal(built.instruments.displayText, NEUTRAL_DISPLAY)
  assert.doesNotMatch(JSON.stringify(built), /NaN|undefined/)

  assert.equal(buildMusicPresentation().isEmpty, true)
  assert.equal(buildMusicPresentation({ music: null, basis: null }).isEmpty, true)

  const long = presentText("测".repeat(200), { maxLength: 10 })
  assert.equal(long.hasText, true)
  assert.equal(long.text.length, 11)
  assert.ok(long.text.endsWith("…"))
  assert.equal(presentText("  多   空格  ").text, "多 空格")
  assert.equal(presentText({}).hasText, false)
  assert.equal(presentText(Number.NaN).displayText, NEUTRAL_DISPLAY)
})

// ------------------------------------------------------------------ MP-T15

test("MP-T15 解析视图默认折叠，且空 / integrated 下不发明事实", () => {
  const personalized = buildAnalysisViewModel({
    regulation_mode: "personalized_five_tone",
    primary_tone: { tone: "jiao" },
    secondary_tone: { tone: "zhi" },
    tone_weights: { jiao: 0.3, zhi: 0.25, gong: 0.2, shang: 0.15, yu: 0.1 },
    confirmed_state: "近期思虑偏多。",
    state_tendency: "思虑偏多",
    analysis_rationales: [{ summary: "近期思虑偏多。" }],
    bpm: { value: 60, explanation: "舒缓节奏" },
    instruments: { values: ["古琴"] },
    ambience: { values: [] },
    duration: { seconds: 240 },
    disclaimer: "仅用于音乐调养参考。",
  })
  assert.equal(personalized.collapsed, true)
  assert.equal(personalized.title, ANALYSIS_TITLE)
  assert.equal(personalized.hasPrimaryTone, true)
  assert.equal(personalized.primaryTone.displayName, "角音")
  assert.equal(personalized.secondaryTone.displayName, "徵音")
  assert.equal(personalized.secondaryTone.claim, "徵音")
  assert.equal(personalized.parameters.bpm.text, "60 BPM")
  assert.equal(personalized.parameters.duration.text, "04:00")
  assert.equal(personalized.parameters.ambience.displayText, NEUTRAL_DISPLAY)
  assert.equal(personalized.rationales.rows.length, 1)
  assert.equal(personalized.disclaimer.text, "仅用于音乐调养参考。")

  const integrated = buildAnalysisViewModel({
    regulation_mode: "integrated_regulation",
    primary_tone: null,
    tone_weights: WEIGHTS,
  })
  assert.equal(integrated.collapsed, true)
  assert.equal(integrated.hasPrimaryTone, false)
  assert.equal(integrated.modeLabel, "综合调适")
  assert.deepEqual(integrated.toneWeights.weights, WEIGHTS)
  assert.doesNotMatch(JSON.stringify(integrated), TONE_NAME_PATTERN)

  const none = buildAnalysisViewModel(null)
  assert.equal(none.collapsed, true)
  assert.equal(none.hasPrimaryTone, false)
  assert.equal(none.toneWeights.hasWeights, false)
  assert.equal(none.parameters.bpm.displayText, NEUTRAL_DISPLAY)
  assert.equal(none.parameters.instruments.displayText, NEUTRAL_DISPLAY)
  assert.equal(none.parameters.ambience.displayText, NEUTRAL_DISPLAY)
  assert.equal(none.parameters.duration.text, "--:--")
  assert.equal(none.stateSummary.displayText, NEUTRAL_DISPLAY)
  assert.equal(none.rationales.hasRows, false)
  assert.doesNotMatch(JSON.stringify(none), /NaN|[宫商角徵羽]/)
})

// ------------------------------------------------------------------ 静态护栏

test("MP-STATIC 展示层不引用主题表事实字段，也不存在宫兜底", () => {
  const source = readFileSync(resolve(root, "common/music-presentation.js"), "utf8")

  // 不得从主题对象上取任何"事实"
  assert.doesNotMatch(source, /Theme\.(traits|instruments|ambience|instrument|title)\b/)
  // 不得存在任何宫兜底
  assert.doesNotMatch(source, /\|\|\s*["']gong["']/)
  assert.doesNotMatch(source, /\?\?\s*["']gong["']/)
  // 不得从权重合成主音
  assert.doesNotMatch(source, /\bargmax\s*\(|\.argmax\b/i)

  // 主题表只保留视觉元数据，且键集合与未知音空状态完全一致
  const visualKeys = ["accent", "code", "glyph", "imageCode", "soft"]
  for (const code of TONE_CODES) {
    assert.deepEqual(Object.keys(toneThemeFor(code)).sort(), visualKeys, `${code} 只允许视觉元数据`)
  }
  assert.deepEqual(Object.keys(UNKNOWN_TONE_THEME).sort(), visualKeys)

  // 伪造解释被抑制：bpm / instruments / ambience 的假解释不得冒充本次依据
  const fabricated = buildAnalysisViewModel({
    regulation_mode: "personalized_five_tone",
    primary_tone: { tone: "gong" },
    bpm: { value: 60, explanation: "由服务端处方生成。" },
    instruments: { values: ["古琴"], explanation: "由服务端处方生成。" },
  })
  assert.equal(fabricated.parameters.bpm.explanation.hasText, false)
  assert.equal(fabricated.parameters.bpm.explanation.text, "")
  assert.equal(fabricated.parameters.bpm.text, "60 BPM")
  assert.equal(fabricated.parameters.instruments.text, "古琴")
  // 真实的后端解释仍然透出
  const real = buildAnalysisViewModel({
    regulation_mode: "personalized_five_tone",
    primary_tone: { tone: "gong" },
    bpm: { value: 60, explanation: "本次采用舒缓节奏。" },
  })
  assert.equal(real.parameters.bpm.explanation.text, "本次采用舒缓节奏。")
})
