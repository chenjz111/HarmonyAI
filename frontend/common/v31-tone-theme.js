/**
 * V3.1 五音展示主题表（唯一的五音 code → 文案/配色来源）
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
 * 未知 / 缺失的主音绝不静默回退成"宫"：返回 UNKNOWN_TONE_THEME（glyph = "--"），
 * 页面应显示空状态，或改用它处明确存在的服务端主音。
 */
const THEMES = Object.freeze({
  gong: Object.freeze({ code: "gong", imageCode: "gong", glyph: "宫", title: "静水流深", accent: "#2f6b5e", soft: "#f7edd7", traits: "沉稳 · 平和 · 安定", instrument: "古琴", instruments: "古琴 · 洞箫", ambience: "流水" }),
  shang: Object.freeze({ code: "shang", imageCode: "shang", glyph: "商", title: "清风和鸣", accent: "#9b6a22", soft: "#f4ead1", traits: "柔和 · 收敛 · 安养", instrument: "竹笛", instruments: "洞箫 · 古琴", ambience: "流水" }),
  jiao: Object.freeze({ code: "jiao", imageCode: "jue", glyph: "角", title: "春山新绿", accent: "#326f62", soft: "#dfeee8", traits: "生机 · 向上 · 希望", instrument: "笙", instruments: "笙 · 古琴", ambience: "流水" }),
  zhi: Object.freeze({ code: "zhi", imageCode: "zhi", glyph: "徵", title: "秋山红叶", accent: "#ad2d24", soft: "#f6ded7", traits: "热情 · 光明 · 奋进", instrument: "琵琶", instruments: "琵琶 · 古琴", ambience: "流水" }),
  yu: Object.freeze({ code: "yu", imageCode: "yu", glyph: "羽", title: "寒江映月", accent: "#2f678b", soft: "#dcebf4", traits: "智慧 · 柔和 · 深远", instrument: "排箫", instruments: "排箫 · 古琴", ambience: "流水" }),
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
export const UNKNOWN_TONE_THEME = Object.freeze({
  code: "", imageCode: "", glyph: "--", title: "", accent: "#5f6f6a", soft: "#f1f4f3",
  traits: "", instrument: "", instruments: "", ambience: "",
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

export function formatPlaybackTime(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`
}

export { THEMES as V31_TONE_THEMES }
