/**
 * Sprint 5 / V3.1 —— 音乐生成页 / 播放器页主音显示权威性回归
 *
 * 真机缺陷：后端 Diagnosis / Prescription / MusicAsset 的 tone_profile.primary_tone
 * 都是 "jiao"（角），播放器却显示"宫"。根因是前端主题表把角写成历史拼写 "jue"，
 * 于是 toneThemeFor("jiao") 查不到主题，被 `|| "gong"` 静默回退成"宫"。
 *
 * 本测试锁定：
 *   1. 五音 code → 汉字映射使用后端权威拼写（gong/shang/jiao/zhi/yu）
 *   2. 历史拼写 / 中文展示名 / "…为主" 等写法仍能解析（别名，不改变权威 code）
 *   3. 未知或缺失主音不得回退成"宫"，只能是空状态
 *   4. 播放器主音来源优先级：本次 asset tone_profile → 本次 prescription read model
 *   5. 端到端：API/asset 的 primary_tone = "jiao" 时，页面渲染文本必须是"角"且不含"宫"
 *
 * 纯静态 + 纯函数 + 一次本地 uni.request mock；不联网、不调用任何 Provider。
 * 运行：cd frontend && node --test "tests/sprint5-v31-player-tone-authority.test.mjs"
 */
import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

import {
  UNKNOWN_TONE_THEME,
  normalizeToneCode,
  toneThemeFor,
} from "../common/v31-tone-theme.js"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")
const stripStyles = (source) => source.replace(/<style[\s\S]*?<\/style>/g, "")

const player = read("pages/v3-player/v3-player.vue")
const playerMarkup = stripStyles(player)
const basisMarkup = stripStyles(read("pages/v3-basis/v3-basis.vue"))

// 后端权威映射：backend/app/schemas/v3/common.py::ToneCode
//              + knowledge/v3/five-tone-mapping-v3.0.json::organ_tone_table
const AUTHORITATIVE_TONES = { gong: "宫", shang: "商", jiao: "角", zhi: "徵", yu: "羽" }

test("五音 code → 汉字使用后端权威拼写，角是 jiao 而不是 jue", () => {
  for (const [code, glyph] of Object.entries(AUTHORITATIVE_TONES)) {
    const theme = toneThemeFor(code)
    assert.equal(theme.code, code, `${code} 必须解析为自身`)
    assert.equal(theme.glyph, glyph, `${code} 必须显示 ${glyph}`)
  }
  // 真机缺陷回归：jiao 必须显示角，绝不能显示宫
  assert.equal(toneThemeFor("jiao").glyph, "角")
  assert.notEqual(toneThemeFor("jiao").glyph, "宫")
  assert.equal(normalizeToneCode("jiao"), "jiao")
})

test("中文展示名 / 历史拼写 / 对象形态都归一到权威 code", () => {
  for (const value of ["jiao", "JIAO", " jiao ", "jue", "角", "角音", "角调", "角音为主"]) {
    assert.equal(normalizeToneCode(value), "jiao", `${value} 应归一为 jiao`)
    assert.equal(toneThemeFor(value).glyph, "角", `${value} 应显示角`)
  }
  assert.equal(normalizeToneCode("徵音为主"), "zhi")
  assert.equal(normalizeToneCode("宫调"), "gong")
  assert.equal(normalizeToneCode({ code: "jiao" }), "jiao")
  assert.equal(normalizeToneCode({ tone: "jiao", display_name: "角调" }), "jiao")
  assert.equal(normalizeToneCode({ value: "shang" }), "shang")
})

test("未知 / 缺失主音显示空状态，绝不静默回退成宫", () => {
  for (const value of ["", "   ", null, undefined, 0, {}, "unknown", "未定", "--"]) {
    const theme = toneThemeFor(value)
    assert.equal(theme.code, "", `${JSON.stringify(value)} 不应解析出任何五音 code`)
    assert.equal(theme.glyph, "--", `${JSON.stringify(value)} 应显示占位符`)
    assert.notEqual(theme.glyph, "宫")
    assert.equal(normalizeToneCode(value), "")
  }
  assert.equal(toneThemeFor(undefined), UNKNOWN_TONE_THEME)
  assert.doesNotMatch(toneThemeFor(undefined).glyph, /[宫商角徵羽]/)
})

test("静态插画按 imageCode 取图：角的 code 是 jiao、插画仍是 jue-*.png", () => {
  for (const code of Object.keys(AUTHORITATIVE_TONES)) {
    const theme = toneThemeFor(code)
    assert.ok(theme.imageCode, `${code} 需要 imageCode`)
    assert.ok(
      existsSync(resolve(root, `static/v31-player/${theme.imageCode}-1.png`)),
      `${code} 的背景插画必须存在: ${theme.imageCode}-1.png`,
    )
    assert.ok(
      existsSync(resolve(root, `static/v31-player/${theme.imageCode}-2.png`)),
      `${code} 的主视觉插画必须存在: ${theme.imageCode}-2.png`,
    )
  }
  assert.equal(toneThemeFor("jiao").imageCode, "jue")
})

test("播放器主音来源优先级：本次 asset tone_profile → 本次 prescription", () => {
  // asset 优先
  assert.match(player, /if \(music\.tone_code\) return music\.tone_code/)
  // asset 未暴露时用本次 prescription / read model 的 primary_tone
  assert.match(player, /basis\.primary_tone/)
  // 不得把缺失的主音静默回退成宫
  assert.doesNotMatch(player, /["']gong["']/, "播放器不得出现 gong 常量")
  assert.doesNotMatch(player, /toneThemeFor\([^)]*\|\|/, "toneThemeFor 的参数不得带 || 回退")
  // 渲染的主音汉字只能来自主题表
  assert.match(playerMarkup, /\{\{\s*toneTheme\.glyph\s*\}\}/)
  assert.match(playerMarkup, /\{\{\s*tonePairText\s*\}\}/)
  assert.match(playerMarkup, /\{\{\s*toneSummaryValue\s*\}\}/)
  // 空状态：主音未知时显示占位符（或本次调适方向），绝不显示具体五音
  assert.match(player, /if \(!this\.toneTheme\.code\) return this\.modeLabel \|\| "—"/)
  assert.match(player, /return `\$\{this\.toneTheme\.glyph\}音`/)
  assert.match(player, /return `\$\{this\.toneTheme\.glyph\}音主调`/)
  // Sprint 6：主音主题只在后端明确 personalized_five_tone 时生效（mode 权威，前端不推断）
  assert.match(player, /personalizedToneTheme\(this\.regulationMode, this\.toneSource\)/)
  assert.match(player, /normalizeRegulationMode/)
})

test("五音解析页五音条使用权威 code，主音角色能被标记出来", () => {
  for (const code of Object.keys(AUTHORITATIVE_TONES)) {
    assert.match(basisMarkup, new RegExp(`code: "${code}"`), `五音条必须包含 ${code}`)
  }
  assert.doesNotMatch(basisMarkup, /code: "jue"/, "五音条不得再使用历史拼写 jue")
  // 主音/辅音性格文案取自主题表，不再写死某个音的旧文案
  assert.match(basisMarkup, /\{\{\s*primaryToneTheme\.traits\s*\}\}/)
  assert.match(basisMarkup, /\{\{\s*secondaryToneTheme\.traits\s*\}\}/)
  assert.doesNotMatch(basisMarkup, /沉稳 · 平和 · 安定/, "不得把宫的性格文案写死在主音下")
})

// ---------------------------------------------------------------------------
// 端到端（本地 mock，无网络）：asset tone_profile.primary_tone = "jiao"
// 页面渲染文本必须出现"角"，且不得出现"宫"
// ---------------------------------------------------------------------------

process.env.HARMONYAI_V3_MODE = "real"

const storage = new Map()
const calls = []

const JIAO_TONE_PROFILE = {
  schema_version: "tone_profile_v3.2",
  regulation_mode: "personalized_five_tone",
  weights: { jiao: 0.7, zhi: 0.15, gong: 0, shang: 0.15, yu: 0 },
  primary_tone: "jiao",
  secondary_tone: null,
  score_semantics: "relative_tone_distribution",
  mapping_version: "five_tone_mapping_v3@3.0.0",
}

const ASSET = {
  music_ref: { music_id: "asset_62f9178ffb4d4a7cafa133f08c42eb44", source_type: "generated" },
  title: "角调安神曲",
  stream_url: "/api/v3/music/assets/asset_62f9178ffb4d4a7cafa133f08c42eb44/stream",
  duration_seconds: 180,
  format: "mp3",
  checksum: "sha256:test",
  tone_profile: JIAO_TONE_PROFILE,
  bpm: 60,
  instruments: ["古琴"],
}

globalThis.uni = {
  getStorageSync(key) { return storage.get(key) ?? "" },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
  request(options) {
    const path = new URL(options.url).pathname
    calls.push(path)
    if (path === "/api/v3/music/generations" && options.method === "POST") {
      options.success({
        statusCode: 200,
        data: {
          ok: true,
          data: {
            task_id: "mtask_test",
            status: "succeeded",
            message: "完成",
            progress: { value: 100, semantics: "provider_reported", indeterminate: false },
            poll_after_ms: null,
            fallback: { applied: false, reason_code: null },
            error_code: null,
            audio_asset: ASSET,
          },
        },
      })
      return
    }
    throw new Error(`unexpected request ${options.method} ${path}`)
  },
}

// 真实模式：播放器数据来自 flow state（persistMusicTask 写入）
storage.set(
  "v3_flow_state",
  JSON.stringify({
    session_id: "sess_tone",
    prescription_id: "rx_e8212759e0d94320b2b9ed9ee673205d",
    generation_spec: { schema_version: "generation_spec_v3.0", tone_profile: JIAO_TONE_PROFILE },
  }),
)

const { apiV3 } = await import("../common/api-v3.js?tone-authority")

test("API/asset primary_tone=jiao 时播放器显示角、不显示宫", async () => {
  const task = await apiV3.startMusicGeneration()
  assert.equal(task.status, "succeeded")

  const music = await apiV3.getMusic()
  assert.equal(music.tone_code, "jiao", "播放器模型必须固化 asset 的 primary_tone")
  assert.equal(music.tone_label, "角音为主")

  const theme = toneThemeFor(music.tone_code)
  assert.equal(theme.glyph, "角")

  // 页面实际渲染的三处主音文本
  const rendered = [theme.glyph, `${theme.glyph}音`, `${theme.glyph}音主调`]
  for (const text of rendered) {
    assert.match(text, /角/, `渲染文本应含角: ${text}`)
    assert.doesNotMatch(text, /宫/, `渲染文本不得含宫: ${text}`)
  }
  // 中央插画也随主音切换（角的插画文件名为 jue-*）
  assert.equal(theme.imageCode, "jue")

  // 只调用了音乐生成接口：没有额外 Provider / 后端调用
  assert.deepEqual(calls, ["/api/v3/music/generations"])
})
