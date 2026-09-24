/**
 * Sprint 6 Phase 6 — 音乐展示层（纯函数，可被 node:test 直接导入）
 *
 * 职责：把后端权威值转换成"可安全展示"的前端值。
 * 唯一原则：**展示层不发明任何事实**。
 *
 * 本模块（与其测试）共同守住这些被 Phase 6 明令删除 / 抑制的模式：
 *   1. 硬编码的疗愈 / 性格文案（把某个五音的性格结论当作本次结论展示）；
 *   2. 用正则切分 backend rationale 文本后编造语义
 *      （拆出 source / target、补 "作为本次调适依据" 之类的话）；
 *   3. 环境音为空时补一个编造的默认氛围；
 *   4. 用前端编造的"依据解释"文案冒充本次依据（见 FABRICATED_EXPLANATIONS）；
 *   5. 把主题表里的乐器 / 氛围 / 曲名当作"本次音乐"的事实兜底；
 *   6. 缺失 / 未知时回退成某个五音（尤其"宫"）。
 *
 * 缺失一律返回显式中性空状态（text = ""，displayText = NEUTRAL_DISPLAY），
 * 由页面决定呈现方式；本模块绝不补一个"看起来像事实"的默认值。
 *
 * 权威边界：
 *   - regulation_mode / primary_tone / secondary_tone / tone_weights / bpm /
 *     instruments / ambience / duration / title / disclaimer 一律来自后端 read model；
 *   - v31-tone-theme.js 只提供视觉元数据（code / imageCode / glyph / accent / soft）
 *     与 mode 词汇，不提供任何"本次音乐"的事实；
 *   - 技术失败（provider / schema / checksum / asset / safety）保持失败语义，
 *     绝不被展示成 basic_wellness（P6-D3 / Phase 1A 任务 4）。
 */
import {
  formatPlaybackTime,
  isPersonalizedMode,
  modeLabelFor,
  normalizeRegulationMode,
  personalizedToneTheme,
  toneThemeFor,
} from "./v31-tone-theme.js"
import { formatDuration } from "./v31-player-time.js"

/** 中性占位：字段确实缺失时页面该显示的东西（不是事实，是"没有"）。 */
export const NEUTRAL_DISPLAY = "—"
/** 时长未知时的时间占位（与 v31-player-time.js 的 UNKNOWN_TIME 同源语义）。 */
export const UNKNOWN_DURATION_TEXT = "--:--"

/** 后端 source_type / 任务状态给出的权威来源名（不是本模块发明的说法）。 */
export const SOURCE_LABEL_GENERATED = "AI生成音乐"
export const SOURCE_LABEL_FALLBACK = "审核曲库匹配音乐"

/** 折叠解析区标题（P6-D1：五音解析不再独立成页，收进播放器按需展开）。 */
export const ANALYSIS_TITLE = "为什么是这首音乐？"

export const FAILURE_TITLE = "暂时无法播放"
/** 权威失败信息缺失时的中性兜底：不解释原因、不声称任何模式。 */
export const FAILURE_NEUTRAL_MESSAGE = "本次音乐暂时不可用，请稍后重试。"

/** 前端历史上伪造过的"解释"文案：到达展示层必须被抑制，不当作依据展示。 */
const FABRICATED_EXPLANATIONS = Object.freeze([
  "由服务端处方生成。",
  "由服务端处方生成",
  "服务端默认生成。",
  "系统默认参数。",
])

/** 五音权威 code 的展示顺序（仅排序，不表示任何偏好或主导性）。 */
const TONE_ORDER = Object.freeze(["jiao", "zhi", "gong", "shang", "yu"])

const TEXT_LIMITS = Object.freeze({
  title: 60,
  message: 160,
  disclaimer: 220,
  rationale: 160,
  state: 200,
})

// ------------------------------------------------------------------ 基础工具

/** 只把真正可读的标量转成文本；对象 / 数组 / NaN 一律视为缺失。 */
function toPlainText(value) {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim()
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : ""
  if (typeof value === "boolean") return ""
  return ""
}

/** 秒数归一：null / undefined / "" / NaN / Infinity / 负数一律视为未知（0 是合法值）。 */
export function toFiniteSeconds(value) {
  if (value === null || value === undefined) return null
  if (typeof value === "string" && value.trim() === "") return null
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds < 0) return null
  return seconds
}

/**
 * 通用文本展示：缺失 / 非法 → 显式中性空状态，绝不编造。
 * displayText 是"页面可以直接渲染"的值：没有内容时就是 NEUTRAL_DISPLAY。
 */
export function presentText(value, { maxLength = 0 } = {}) {
  let text = toPlainText(value)
  if (text && maxLength > 0 && text.length > maxLength) {
    text = `${text.slice(0, maxLength).trimEnd()}…`
  }
  return { hasText: !!text, text, displayText: text || NEUTRAL_DISPLAY }
}

/** 该文本是否属于前端伪造的"依据解释"（应被抑制，不作为解释展示）。 */
export function isFabricatedExplanation(value) {
  const text = toPlainText(value).replace(/\s+/g, "")
  if (!text) return false
  return FABRICATED_EXPLANATIONS.some((item) => item.replace(/\s+/g, "") === text)
}

/** 解释文本展示：伪造解释一律降级成中性空状态，不冒充本次依据。 */
export function presentExplanation(value, options) {
  if (isFabricatedExplanation(value)) return presentText("", options)
  return presentText(value, options)
}

/** 值列表归一：只保留去空、去重后的字符串，绝不用任何默认值补位。 */
function normalizeValueList(values) {
  if (!Array.isArray(values)) return []
  const list = []
  for (const item of values) {
    const text = toPlainText(item)
    if (text && !list.includes(text)) list.push(text)
  }
  return list
}

// ------------------------------------------------------------------ 模式

/**
 * 权威模式展示：mode 只读后端 regulation_mode，绝不从主音 / 权重 / argmax 推断。
 * 未知或缺失 → known=false、label=""、toneClaimAllowed=false（中性不可用态）。
 */
export function presentRegulationMode(value) {
  const mode = normalizeRegulationMode(value)
  const personalized = isPersonalizedMode(mode)
  const label = modeLabelFor(mode)
  return {
    mode,
    known: !!mode,
    label,
    displayLabel: label || NEUTRAL_DISPLAY,
    isPersonalized: personalized,
    isIntegrated: mode === "integrated_regulation",
    isBasic: mode === "basic_wellness",
    // 印章文字：只有 personalized 才允许写"主音"，否则显示权威模式名，未知则空
    sealText: personalized ? "主音" : label,
    // 是否允许产生任何"某音为主"的主张
    toneClaimAllowed: personalized,
  }
}

// ------------------------------------------------------------------ 五音

/** 五音展示名（"角音"）：由视觉元数据的 glyph + 权威 code 组成，未知 code 返回 ""。 */
export function toneDisplayName(value) {
  const theme = toneThemeFor(value)
  if (!theme.code) return ""
  return `${theme.glyph}音`
}

/**
 * 主音 / 辅音展示：只有「后端明确 personalized_five_tone」且「存在真实主音」时才产生主张。
 * integrated / basic / 未知 mode / 未知音一律 hasTone=false，绝不回退成"宫"。
 * tone 可以是权威 code、中文展示名，或 {tone|code|value} 对象。
 */
export function presentTone(mode, tone, { role = "primary" } = {}) {
  const theme = personalizedToneTheme(mode, tone)
  if (!theme.code) {
    return {
      role,
      isPrimary: role === "primary",
      hasTone: false,
      code: "",
      imageCode: theme.imageCode,
      glyph: "",
      accent: theme.accent,
      soft: theme.soft,
      displayName: "",
      claim: "",
      displayText: "",
    }
  }
  const displayName = `${theme.glyph}音`
  const claim = role === "primary" ? `${displayName}为主` : displayName
  return {
    role,
    isPrimary: role === "primary",
    hasTone: true,
    code: theme.code,
    imageCode: theme.imageCode,
    glyph: theme.glyph,
    accent: theme.accent,
    soft: theme.soft,
    displayName,
    claim,
    displayText: claim,
  }
}

export function presentPrimaryTone(mode, tone) {
  return presentTone(mode, tone, { role: "primary" })
}

export function presentSecondaryTone(mode, tone) {
  return presentTone(mode, tone, { role: "secondary" })
}

/**
 * 五音权重展示：逐字保留后端权重，只做展示排序与百分比格式化。
 * 绝不 argmax、绝不据此合成主音、绝不因为某个权重最大就称其为主音。
 */
export function presentToneWeights(weights) {
  if (!weights || typeof weights !== "object" || Array.isArray(weights)) {
    return { hasWeights: false, entries: [], weights: null, text: "", displayText: NEUTRAL_DISPLAY }
  }
  const entries = []
  const kept = {}
  for (const code of TONE_ORDER) {
    const value = Number(weights[code])
    if (!Number.isFinite(value)) continue
    const theme = toneThemeFor(code)
    const glyph = theme.code ? theme.glyph : ""
    const percent = `${Math.round(value * 100)}%`
    kept[code] = value
    entries.push({
      code,
      glyph,
      weight: value,
      percentText: percent,
      text: glyph ? `${glyph} ${percent}` : percent,
    })
  }
  return {
    hasWeights: entries.length > 0,
    entries,
    weights: entries.length > 0 ? kept : null,
    text: entries.map((item) => item.text).join(" · "),
    displayText: entries.length > 0 ? entries.map((item) => item.text).join(" · ") : NEUTRAL_DISPLAY,
  }
}

// ------------------------------------------------------------------ 时长

/**
 * 时长展示：只有已知的有限正整数秒才会格式化成时间。
 * MP-T9 / MP-T10 / MP-T11：未知 → "--:--"，绝不出现 NaN / Infinity / 负数。
 */
export function presentDuration(seconds) {
  const value = toFiniteSeconds(seconds)
  const known = value !== null && value > 0
  if (!known) {
    return {
      known: false,
      seconds: null,
      text: UNKNOWN_DURATION_TEXT,
      displayText: UNKNOWN_DURATION_TEXT,
      minutes: null,
      minutesText: NEUTRAL_DISPLAY,
    }
  }
  const minutes = Math.max(1, Math.round(value / 60))
  return {
    known: true,
    seconds: value,
    text: formatDuration(value),
    displayText: formatDuration(value),
    minutes,
    minutesText: `${minutes}分钟`,
  }
}

/**
 * 播放时长权威（P6-D7）：实测 generated duration 是播放时长权威，
 * asset 持久化时长只在没有实测值时兜底；都没有 → unknown（页面显示 --:--）。
 */
export function resolvePlaybackDuration({ measuredSeconds, assetSeconds } = {}) {
  const measured = toFiniteSeconds(measuredSeconds)
  if (measured !== null && measured > 0) return { source: "measured", seconds: measured }
  const asset = toFiniteSeconds(assetSeconds)
  if (asset !== null && asset > 0) return { source: "asset", seconds: asset }
  return { source: "unknown", seconds: null }
}

/** 进度展示：总时长未知时不给百分比（0），绝不产生 NaN%。 */
export function presentProgress({ currentSeconds, totalSeconds } = {}) {
  const total = toFiniteSeconds(totalSeconds)
  const current = toFiniteSeconds(currentSeconds)
  const currentText = current === null ? UNKNOWN_DURATION_TEXT : formatPlaybackTime(current)
  if (total === null || total <= 0) {
    return { hasProgress: false, percent: 0, currentText, totalText: UNKNOWN_DURATION_TEXT }
  }
  const raw = ((current || 0) / total) * 100
  const percent = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0
  return { hasProgress: true, percent, currentText, totalText: formatPlaybackTime(total) }
}

// ------------------------------------------------------------------ 参数事实

/** BPM 展示：后端没给就不显示数字，也绝不补默认节奏。 */
export function presentBpm(bpm) {
  const source = bpm && typeof bpm === "object" ? bpm : { value: bpm }
  const value = Number(source.value)
  const hasValue = Number.isFinite(value) && value > 0
  return {
    hasValue,
    value: hasValue ? value : null,
    text: hasValue ? `${value} BPM` : "",
    displayText: hasValue ? `${value} BPM` : NEUTRAL_DISPLAY,
    explanation: presentExplanation(source.explanation, { maxLength: TEXT_LIMITS.message }),
  }
}

/** 乐器展示：只来自后端值列表；缺失 → 中性空状态，绝不用主题表兜底。 */
export function presentInstruments(values, { source = "" } = {}) {
  const list = normalizeValueList(values)
  return {
    source: list.length ? source : "",
    hasValues: list.length > 0,
    values: list,
    text: list.join(" · "),
    displayText: list.length ? list.join(" · ") : NEUTRAL_DISPLAY,
  }
}

/** 氛围 / 环境音展示：缺失 → 中性空状态；绝不用任何编造的默认氛围补位。 */
export function presentAmbience(values, { source = "" } = {}) {
  const list = normalizeValueList(values)
  return {
    source: list.length ? source : "",
    hasValues: list.length > 0,
    values: list,
    text: list.join(" · "),
    displayText: list.length ? list.join(" · ") : NEUTRAL_DISPLAY,
  }
}

/** 曲名展示：只显示后端 asset title；缺失 → 中性空状态，绝不用主题名充当曲名。 */
export function presentTitle(value) {
  return presentText(value, { maxLength: TEXT_LIMITS.title })
}

export function presentDisclaimer(value) {
  return presentText(value, { maxLength: TEXT_LIMITS.disclaimer })
}

// ------------------------------------------------------------------ 来源 / 兜底 / 失败

function isFallbackStatus(status) {
  return status === "matched_fallback"
}

/**
 * 来源标签（P6-D3）：fallback 保持 none；一旦后端返回过 fallback / matched_fallback，
 * 必须如实标注，绝不把匹配音乐说成实时 AI 生成。
 * 来源未知时不主张任何来源（text = ""）。
 */
export function presentSourceLabel({ sourceLabel, sourceType, status } = {}) {
  const given = toPlainText(sourceLabel)
  const isFallback = isFallbackStatus(status) || sourceType === "matched_fallback"
  if (isFallback) return { text: given || SOURCE_LABEL_FALLBACK, isFallback: true, isUnknown: false }
  const isGenerated = status === "succeeded" || sourceType === "generated"
  if (isGenerated) return { text: given || SOURCE_LABEL_GENERATED, isFallback: false, isUnknown: false }
  return { text: "", isFallback: null, isUnknown: true }
}

/**
 * 兜底信息展示：applied=true → 如实标注"审核曲库匹配音乐"；
 * applied=false → 不显示任何兜底标签；未知 → applied=null（既不承认也不否认）。
 * 任务状态 matched_fallback 是权威，即使 fallback 字段缺失也判为已兜底。
 */
export function presentFallback(fallback, { status, sourceType } = {}) {
  const source = fallback && typeof fallback === "object" ? fallback : {}
  let applied = typeof source.applied === "boolean" ? source.applied : null
  if (isFallbackStatus(status) || sourceType === "matched_fallback") applied = true
  const reasonCode = applied === true ? toPlainText(source.reason_code) : ""
  if (applied === true) {
    return { applied: true, reasonCode, label: SOURCE_LABEL_FALLBACK, displayText: SOURCE_LABEL_FALLBACK }
  }
  if (applied === false) {
    return { applied: false, reasonCode: "", label: "", displayText: NEUTRAL_DISPLAY }
  }
  return { applied: null, reasonCode: "", label: "", displayText: NEUTRAL_DISPLAY }
}

function isOpenTaskStatus(status) {
  return status === "queued" || status === "running" || status === "pending"
}

/**
 * 重试语义（P6-D2）：诚实失败 + 恢复已有任务；终态重试 = 一次新的生成请求。
 * 有可恢复任务时只提供"继续等待"，不诱导用户发起新的付费生成。
 */
export function presentRetryPolicy({ canResume, terminal, taskStatus } = {}) {
  const resumable = canResume === undefined ? isOpenTaskStatus(taskStatus) : !!canResume
  if (terminal === true) {
    return {
      resumeExistingTask: false,
      resumeLabel: "",
      retryCreatesNewAttempt: true,
      retryLabel: "重新生成音乐",
      notice: "重新生成将发起一次新的生成请求。",
    }
  }
  if (resumable) {
    return {
      resumeExistingTask: true,
      resumeLabel: "继续等待本次生成",
      retryCreatesNewAttempt: false,
      retryLabel: "",
      notice: "",
    }
  }
  return {
    resumeExistingTask: false,
    resumeLabel: "",
    retryCreatesNewAttempt: true,
    retryLabel: "重新生成音乐",
    notice: "重新生成将发起一次新的生成请求。",
  }
}

/**
 * 失败展示模型（MP-T13）：
 *   - 权威信息优先：后端 / agent 给出的 message 原样优先展示，缺失时才是中性兜底；
 *   - 技术失败保持失败语义，绝不伪装成 basic_wellness / 基础舒缓；
 *   - 明确给出重试语义，避免把"重试"说成"恢复"。
 */
export function presentFailureDisplay(error, { taskStatus, canResume, terminal } = {}) {
  const source = error && typeof error === "object" ? error : {}
  const message = presentText(source.message, { maxLength: TEXT_LIMITS.message })
  const code = toPlainText(source.code)
  return {
    isFailure: true,
    isTechnicalFailure: true,
    code,
    title: FAILURE_TITLE,
    message: message.hasText ? message.text : FAILURE_NEUTRAL_MESSAGE,
    messageSource: message.hasText ? "authoritative" : "neutral",
    // 技术失败不得降级成"基础舒缓"这类正常模式
    degradedToWellness: false,
    mode: "",
    modeLabel: "",
    retry: presentRetryPolicy({
      canResume: canResume === undefined ? source.canResume : canResume,
      terminal: terminal === undefined ? source.terminal : terminal,
      taskStatus,
    }),
  }
}

// ------------------------------------------------------------------ 折叠解析

/**
 * 解析依据展示（MP-T8）：summary 原样展示，绝不用正则切分后端文本、
 * 绝不拆出 source / target，也绝不补"作为本次调适依据"这类编造语义。
 */
export function presentRationales(items) {
  const rows = []
  for (const item of Array.isArray(items) ? items : []) {
    const raw = item && typeof item === "object" ? (item.summary !== undefined ? item.summary : item.text) : item
    const text = presentText(raw, { maxLength: TEXT_LIMITS.rationale })
    if (!text.hasText) continue
    rows.push({ index: rows.length + 1, text: text.text })
  }
  return { hasRows: rows.length > 0, rows }
}

/**
 * "为什么是这首音乐？"折叠视图模型（P6-D1 / MP-T15）：默认折叠，用户想看再展开。
 * 全部内容来自后端 read model；缺失项保持中性空状态。
 */
export function buildAnalysisViewModel(basis) {
  const source = basis && typeof basis === "object" ? basis : {}
  const mode = presentRegulationMode(source.regulation_mode)
  const primaryTone = presentPrimaryTone(mode.mode, source.primary_tone)
  const secondaryTone = presentSecondaryTone(mode.mode, source.secondary_tone)
  const parameterInstruments = source.instruments ? source.instruments.values : null
  const parameterAmbience = source.ambience ? source.ambience.values : null
  const parameterDuration = source.duration ? source.duration.seconds : null
  return {
    collapsed: true,
    title: ANALYSIS_TITLE,
    mode: mode.mode,
    modeLabel: mode.label,
    modeDisplayLabel: mode.displayLabel,
    hasPrimaryTone: primaryTone.hasTone,
    primaryTone,
    secondaryTone,
    toneWeights: presentToneWeights(source.tone_weights),
    stateSummary: presentText(source.confirmed_state, { maxLength: TEXT_LIMITS.state }),
    tendency: presentText(source.state_tendency, { maxLength: TEXT_LIMITS.state }),
    rationales: presentRationales(source.analysis_rationales),
    parameters: {
      bpm: presentBpm(source.bpm),
      instruments: presentInstruments(parameterInstruments, { source: "basis" }),
      ambience: presentAmbience(parameterAmbience, { source: "basis" }),
      duration: presentDuration(parameterDuration),
    },
    disclaimer: presentDisclaimer(source.disclaimer),
  }
}

// ------------------------------------------------------------------ 播放器视图模型

/** 全中性空状态：任何输入都没有时，页面拿到的是一个"什么都不断言"的模型。 */
export function emptyMusicPresentation() {
  return {
    isEmpty: true,
    isFailure: false,
    mode: "",
    modeLabel: "",
    modeDisplayLabel: NEUTRAL_DISPLAY,
    sealText: "",
    hasPrimaryTone: false,
    primaryTone: presentPrimaryTone("", ""),
    secondaryTone: presentSecondaryTone("", ""),
    toneWeights: presentToneWeights(null),
    title: presentText(""),
    sourceLabel: "",
    fallback: { applied: null, reasonCode: "", label: "", displayText: NEUTRAL_DISPLAY },
    instruments: presentInstruments(null),
    ambience: presentAmbience(null),
    duration: presentDuration(null),
    progress: presentProgress({}),
    disclaimer: presentText(""),
    analysis: buildAnalysisViewModel(null),
  }
}

/**
 * 播放器完整展示模型：把本次音乐 asset（权威）与本次 basis（解释来源）合成一份
 * 可直接渲染、且不含任何编造事实的模型。
 *
 * 权威优先级（全部为后端值，前端不重算、不猜）：
 *   mode       ：asset.regulation_mode → basis.regulation_mode
 *   tone       ：asset.tone_code → basis.primary_tone（仅 personalized 时有效）
 *   title      ：asset.title（缺失即空，绝不用主题名）
 *   instruments：asset.instrument_labels → basis.instruments.values
 *   ambience   ：basis.ambience.values
 *   duration   ：实测时长（P6-D7）→ asset.duration_seconds
 */
export function buildMusicPresentation({ music, basis, failure, measuredSeconds } = {}) {
  if (failure) {
    const model = emptyMusicPresentation()
    model.isEmpty = false
    model.isFailure = true
    model.failure = presentFailureDisplay(failure)
    return model
  }

  const track = music && typeof music === "object" ? music : null
  const analysisSource = basis && typeof basis === "object" ? basis : null
  if (!track && !analysisSource) return emptyMusicPresentation()

  const musicMode = track ? track.regulation_mode : null
  const basisMode = analysisSource ? analysisSource.regulation_mode : null
  const mode = presentRegulationMode(normalizeRegulationMode(musicMode) || normalizeRegulationMode(basisMode))

  const assetTone = track ? toPlainText(track.tone_code) : ""
  const basisTone =
    mode.isPersonalized && analysisSource && analysisSource.primary_tone ? analysisSource.primary_tone : ""
  const primaryTone = presentPrimaryTone(mode.mode, assetTone || basisTone)
  const secondaryTone = presentSecondaryTone(
    mode.mode,
    analysisSource && analysisSource.secondary_tone ? analysisSource.secondary_tone : "",
  )

  const assetInstruments = track && Array.isArray(track.instrument_labels) ? track.instrument_labels : null
  const basisInstruments = analysisSource && analysisSource.instruments ? analysisSource.instruments.values : null
  const instruments = presentInstruments(
    assetInstruments && assetInstruments.length ? assetInstruments : basisInstruments,
    { source: assetInstruments && assetInstruments.length ? "asset" : "basis" },
  )
  const ambience = presentAmbience(
    analysisSource && analysisSource.ambience ? analysisSource.ambience.values : null,
    { source: "basis" },
  )

  const playback = resolvePlaybackDuration({
    measuredSeconds,
    assetSeconds: track ? track.duration_seconds : null,
  })

  return {
    isEmpty: false,
    isFailure: false,
    mode: mode.mode,
    modeLabel: mode.label,
    modeDisplayLabel: mode.displayLabel,
    sealText: mode.sealText,
    hasPrimaryTone: primaryTone.hasTone,
    primaryTone,
    secondaryTone,
    toneWeights: analysisSource ? presentToneWeights(analysisSource.tone_weights) : presentToneWeights(null),
    title: presentTitle(track ? track.title : ""),
    sourceLabel: presentSourceLabel({
      sourceLabel: track ? track.source_label : "",
      sourceType: track && track.music_ref ? track.music_ref.source_type : "",
      status: track ? track.status : "",
    }),
    fallback: presentFallback(track ? track.fallback : null, {
      status: track ? track.status : "",
      sourceType: track && track.music_ref ? track.music_ref.source_type : "",
    }),
    instruments,
    ambience,
    duration: presentDuration(playback.seconds),
    playbackSource: playback.source,
    progress: presentProgress({ totalSeconds: playback.seconds }),
    disclaimer: presentDisclaimer(track ? track.disclaimer : ""),
    analysis: buildAnalysisViewModel(analysisSource),
  }
}

export default {
  NEUTRAL_DISPLAY,
  UNKNOWN_DURATION_TEXT,
  SOURCE_LABEL_GENERATED,
  SOURCE_LABEL_FALLBACK,
  ANALYSIS_TITLE,
  FAILURE_TITLE,
  FAILURE_NEUTRAL_MESSAGE,
  toFiniteSeconds,
  presentText,
  isFabricatedExplanation,
  presentExplanation,
  presentRegulationMode,
  toneDisplayName,
  presentTone,
  presentPrimaryTone,
  presentSecondaryTone,
  presentToneWeights,
  presentDuration,
  resolvePlaybackDuration,
  presentProgress,
  presentBpm,
  presentInstruments,
  presentAmbience,
  presentTitle,
  presentDisclaimer,
  presentSourceLabel,
  presentFallback,
  presentRetryPolicy,
  presentFailureDisplay,
  presentRationales,
  buildAnalysisViewModel,
  emptyMusicPresentation,
  buildMusicPresentation,
}
