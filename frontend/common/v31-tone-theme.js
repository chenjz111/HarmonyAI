const THEMES = Object.freeze({
  gong: Object.freeze({ code: "gong", glyph: "宫", title: "静水流深", accent: "#2f6b5e", soft: "#f7edd7", traits: "沉稳 · 平和 · 安定", partner: "羽音", instrument: "古琴", instruments: "古琴 · 洞箫", ambience: "流水" }),
  shang: Object.freeze({ code: "shang", glyph: "商", title: "清风和鸣", accent: "#9b6a22", soft: "#f4ead1", traits: "柔和 · 收敛 · 安养", partner: "羽音", instrument: "竹笛", instruments: "洞箫 · 古琴", ambience: "流水" }),
  jue: Object.freeze({ code: "jue", glyph: "角", title: "春山新绿", accent: "#326f62", soft: "#dfeee8", traits: "生机 · 向上 · 希望", partner: "宫音", instrument: "笙", instruments: "笙 · 古琴", ambience: "流水" }),
  zhi: Object.freeze({ code: "zhi", glyph: "徵", title: "秋山红叶", accent: "#ad2d24", soft: "#f6ded7", traits: "热情 · 光明 · 奋进", partner: "宫音", instrument: "琵琶", instruments: "琵琶 · 古琴", ambience: "流水" }),
  yu: Object.freeze({ code: "yu", glyph: "羽", title: "寒江映月", accent: "#2f678b", soft: "#dcebf4", traits: "智慧 · 柔和 · 深远", partner: "宫音", instrument: "排箫", instruments: "排箫 · 古琴", ambience: "流水" }),
})

const ALIASES = Object.freeze({
  宫: "gong", 宫音: "gong",
  商: "shang", 商音: "shang",
  角: "jue", 角音: "jue",
  徵: "zhi", 徵音: "zhi",
  羽: "yu", 羽音: "yu",
})

export function toneThemeFor(value) {
  const raw = String(value || "").trim().toLowerCase()
  const code = THEMES[raw] ? raw : (ALIASES[String(value || "").replace(/为主/g, "").trim()] || "gong")
  return THEMES[code]
}

export function formatPlaybackTime(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`
}

export { THEMES as V31_TONE_THEMES }
