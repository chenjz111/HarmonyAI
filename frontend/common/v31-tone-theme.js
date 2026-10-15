/**
 * V3.1 五音展示主题表（唯一的五音 code → 视觉元数据来源）
 *
 * code 必须使用后端权威拼写：gong / shang / jiao / zhi / yu
 *   - backend/app/schemas/v3/common.py::ToneCode
 *   - knowledge/v3/five-tone-mapping-v3.0.json（organ_tone_table）
 *   - diagnosis/prescription/music asset 的 tone_profile.primary_tone
 * 历史遗留的前端拼写 "jue"（角）只作为别名兼容，不再是主题键。
 *
 * imageCode 仅用于 /static/v31-player/<imageCode>-*.png 静态插画文件名
 * （角的插画文件历史上叫 jue-1.png / jue-2.png，未重命名以免动二进制资源）。
 *
 * Sprint 6 Phase 6（P6 展示层加固）：本表**只允许保留视觉元数据**
 * （code / imageCode / glyph / accent / soft）。
 * 曲名（title）、性格文案（traits）、乐器（instrument(s)）、氛围（ambience）
 * 曾经被播放页当作"本次音乐"的事实兜底，属于编造会话事实，已全部移除：
 *   这些字段必须来自后端 read model，并由 common/music-presentation.js 统一产出。
 *
 * 未知 / 缺失的主音绝不静默回退成"宫"：返回 UNKNOWN_TONE_THEME（glyph = "--"），
 * 页面应显示空状态，或改用它处明确存在的服务端主音。
 */
const THEMES = Object.freeze({
  gong: Object.freeze({ code: "gong", imageCode: "gong", glyph: "宫", accent: "#2f6b5e", soft: "#f7edd7" }),
  shang: Object.freeze({ code: "shang", imageCode: "shang", glyph: "商", accent: "#9b6a22", soft: "#f4ead1" }),
  jiao: Object.freeze({ code: "jiao", imageCode: "jue", glyph: "角", accent: "#326f62", soft: "#dfeee8" }),
  zhi: Object.freeze({ code: "zhi", imageCode: "zhi", glyph: "徵", accent: "#ad2d24", soft: "#f6ded7" }),
  yu: Object.freeze({ code: "yu", imageCode: "yu", glyph: "羽", accent: "#2f678b", soft: "#dcebf4" }),
})

// 中文（含"角调/角音/…为主"等展示写法）与历史拼音拼写 → 权威 code
const ALIASES = Object.freeze({
  宫: "gong", 宫音: "gong",
  商: "shang", 商音: "shang",
  角: "jiao", 角音: "jiao",
  徵: "zhi", 徵音: "zhi",
  羽: "yu", 羽音: "yu",
  jue: "jiao",
})

// 未知主音的空状态主题：不携带任何五音语义，glyph 明确显示占位符。
// 与 THEMES 保持完全相同的键集合（只有视觉元数据），便于静态校验。
export const UNKNOWN_TONE_THEME = Object.freeze({
  code: "", imageCode: "", glyph: "--", accent: "#5f6f6a", soft: "#f1f4f3",
})

/**
 * 把服务端给出的主音（code / 中文展示名 / 历史拼写 / {code|tone|value} 对象）
 * 规范化成权威 code；无法识别时返回 ""（绝不返回 "gong"）。
 */
export function normalizeToneCode(value) {
  if (value && typeof value === "object") {
    return normalizeToneCode(value.code || value.tone || value.value || "")
  }
  const raw = String(value === null || value === undefined ? "" : value).trim()
  if (!raw) return ""
  const direct = raw.toLowerCase()
  if (THEMES[direct]) return direct
  const label = raw.replace(/(为主|音调|音|调)$/g, "").trim()
  const lowered = label.toLowerCase()
  if (THEMES[lowered]) return lowered
  return ALIASES[label] || ALIASES[lowered] || ""
}

export function toneThemeFor(value) {
  const code = normalizeToneCode(value)
  return code ? THEMES[code] : UNKNOWN_TONE_THEME
}

/**
 * Sprint 6 三模式（后端权威字段 regulation_mode）。
 *
 * 前端只读该字段：绝不从 primary_tone 是否存在、tone_weights、argmax 或默认音推断 mode。
 * 缺失 / 未知 mode 一律规范化为 ""（未知即未知，不在前端发明第三态之外的结论）。
 */
export const REGULATION_MODES = Object.freeze({
  personalized: "personalized_five_tone",
  integrated: "integrated_regulation",
  basic: "basic_wellness",
})

export const REGULATION_MODE_LABELS = Object.freeze({
  integrated_regulation: "综合调适",
  basic_wellness: "基础舒缓",
})

const KNOWN_REGULATION_MODES = Object.freeze(Object.values(REGULATION_MODES))

export function normalizeRegulationMode(value) {
  const raw = String(value === null || value === undefined ? "" : value).trim().toLowerCase()
  return KNOWN_REGULATION_MODES.includes(raw) ? raw : ""
}

export function isPersonalizedMode(value) {
  return normalizeRegulationMode(value) === REGULATION_MODES.personalized
}

/** 综合调适 / 基础舒缓 的中文展示名；personalized 与未知 mode 返回 ""。 */
export function modeLabelFor(value) {
  return REGULATION_MODE_LABELS[normalizeRegulationMode(value)] || ""
}

/**
 * 主音专属视觉主题只允许在「后端明确给出 personalized_five_tone 且存在真实主音」时生效。
 * 其余情况（integrated / basic / 未知 mode / 未知音）一律返回中性空状态，绝不回退成"宫"。
 */
export function personalizedToneTheme(mode, tone) {
  return isPersonalizedMode(mode) ? toneThemeFor(tone) : UNKNOWN_TONE_THEME
}

export function formatPlaybackTime(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`
}

export { THEMES as V31_TONE_THEMES }
