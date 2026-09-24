/**
 * Sprint 6 Phase 1A — 三模式前端兼容（Issue #129 / backend PR #127）
 *
 * 覆盖冻结要求：
 *   1. personalized_five_tone + jiao  → 展示真实"角音"，允许主音专属表现
 *   2. personalized_five_tone + gong  → 仅当后端明确 personalized + 宫时才展示"宫音"
 *   3. integrated_regulation + primary_tone=null → 不崩、显示"综合调适"、无伪主音、无宫兜底
 *   4. basic_wellness + primary_tone=null → 不崩、显示"基础舒缓"、无五音主音主张
 *   5. 未知/缺失 mode → 不发明 mode、不合成主音、走中性不可用态
 *   6. API 归一化 → 保留 regulation_mode / null 主音 / tone_weights，绝不合成主音
 *   7. 既有 personalized 渲染回归（真实主音仍然可用）
 *
 * 运行方式与仓库其它前端测试一致：cd frontend && node --test tests/*.test.mjs
 */

import assert from "node:assert/strict"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

process.env.HARMONYAI_V3_MODE = "real"

const root = resolve(import.meta.dirname, "..")
const read = (rel) => readFileSync(resolve(root, rel), "utf8")

const storage = new Map()
let nextAssetToneProfile = null

globalThis.uni = {
  getStorageSync(key) { return storage.get(key) ?? "" },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
  request(options) {
    const path = new URL(options.url).pathname
    if (path === "/api/v3/music/generations" && options.method === "POST") {
      options.success({
        statusCode: 200,
        data: {
          ok: true,
          data: {
            task_id: "mtask_fe",
            status: "succeeded",
            message: "完成",
            progress: { value: 100, semantics: "provider_reported", indeterminate: false },
            poll_after_ms: null,
            fallback: { applied: false, reason_code: null },
            error_code: null,
            audio_asset: {
              music_ref: { music_id: "asset_fe", source_type: "generated" },
              title: "本次音乐",
              stream_url: "/api/v3/music/assets/asset_fe/stream",
              duration_seconds: 180,
              format: "mp3",
              checksum: "sha256:fe",
              tone_profile: nextAssetToneProfile,
              bpm: 60,
              instruments: ["古琴"],
            },
          },
        },
      })
      return
    }
    throw new Error(`unexpected request ${options.method} ${path}`)
  },
}

const { apiV3 } = await import("../common/api-v3.js?phase1a-frontend-compat")
const {
  modeLabelFor,
  normalizeRegulationMode,
  personalizedToneTheme,
  toneThemeFor,
} = await import("../common/v31-tone-theme.js?phase1a-frontend-compat")

const TONE_CODES = { jiao: "角音", zhi: "徵音", gong: "宫音", shang: "商音", yu: "羽音" }
const WEIGHTS = { jiao: 0.2, zhi: 0.2, gong: 0.2, shang: 0.2, yu: 0.2 }

function toneProfile({ mode, primary = null, secondary = null, weights = null } = {}) {
  const profile = { schema_version: "tone_profile_v3.2" }
  if (mode !== undefined) profile.regulation_mode = mode
  if (weights) profile.weights = weights
  profile.primary_tone = primary
  profile.secondary_tone = secondary
  profile.score_semantics = "relative_tone_distribution"
  profile.mapping_version = "five_tone_mapping_v3@3.0.0"
  return profile
}

/** 通过真实 flow-state 缓存分支驱动 apiV3.getMusicBasis()（无网络）。 */
function seedBasisState(profile, { ambientSounds = ["流水"], parameterSummaries = ["舒缓节奏"] } = {}) {
  const spec = {
    schema_version: "generation_spec_v3.0",
    tone_profile: profile,
    bpm: 60,
    duration_seconds: 180,
    instruments: ["古琴"],
    ambient_sounds: ambientSounds,
    structure: { intro_seconds: 30, main_seconds: 120, outro_seconds: 30 },
    energy_curve: "calm",
    forbidden_constraints: [],
    fallback_policy: { allow_local_matching: false },
  }
  storage.set(
    "v3_flow_state",
    JSON.stringify({
      session_id: "sess_fe",
      assessment: { status: "confirmed", state_summary: "近期思虑偏多。", revision: 1 },
      diagnosis: {
        presentation: {
          title: "辨证分析",
          primary_tendency: "思虑偏多",
          basis_summaries: ["思虑偏多"],
          disclaimer: "仅用于音乐调养参考，不构成医学诊断。",
        },
      },
      prescription: {
        prescription_id: "rx_fe",
        generation_spec: spec,
        presentation: {
          tone_summary: "本次以宫音为主。",
          parameter_summaries: parameterSummaries,
          personalization_summary: "未应用历史偏好。",
        },
      },
      generation_spec: spec,
    }),
  )
}

test("API basis 不为缺失的解释或 ambience 制造前端事实", async () => {
  seedBasisState(
    toneProfile({ mode: "integrated_regulation", weights: WEIGHTS }),
    { ambientSounds: [], parameterSummaries: [] },
  )

  const basis = await apiV3.getMusicBasis()
  assert.equal(basis.bpm.explanation, "")
  assert.equal(basis.instruments.explanation, "")
  assert.deepEqual(basis.ambience.values, [])
  assert.equal(basis.ambience.explanation, "")
  assert.equal(basis.duration.explanation, "")
})

async function basisFor(profile) {
  seedBasisState(profile)
  return apiV3.getMusicBasis()
}

// ---------------------------------------------------------------- 1 / 7

test("personalized_five_tone + jiao：保留 mode/权重与真实主音（既有回归）", async () => {
  const basis = await basisFor(toneProfile({ mode: "personalized_five_tone", primary: "jiao", weights: WEIGHTS }))
  assert.equal(basis.regulation_mode, "personalized_five_tone")
  assert.equal(basis.primary_tone.tone, "jiao")
  assert.equal(basis.primary_tone.display_name, TONE_CODES.jiao)
  assert.deepEqual(basis.tone_weights, WEIGHTS, "tone_weights 必须逐字保留")
  // 主音专属主题允许生效
  const theme = personalizedToneTheme(basis.regulation_mode, basis.primary_tone.tone)
  assert.equal(theme.code, "jiao")
  assert.equal(theme.glyph, "角")
})

// ---------------------------------------------------------------- 2

test("personalized_five_tone + gong：仅当后端明确 personalized + 宫时才展示宫音", async () => {
  const basis = await basisFor(toneProfile({ mode: "personalized_five_tone", primary: "gong", weights: WEIGHTS }))
  assert.equal(basis.regulation_mode, "personalized_five_tone")
  assert.equal(basis.primary_tone.display_name, "宫音")
  assert.equal(personalizedToneTheme(basis.regulation_mode, basis.primary_tone.tone).glyph, "宫")
})

// ---------------------------------------------------------------- 3

test("integrated_regulation + primary_tone=null：不崩、无伪主音、无宫兜底", async () => {
  const basis = await basisFor(toneProfile({ mode: "integrated_regulation", primary: null, weights: WEIGHTS }))
  assert.equal(basis.regulation_mode, "integrated_regulation")
  assert.equal(basis.primary_tone, null, "integrated 必须保留 null 主音，绝不合成")
  assert.equal(basis.secondary_tone, null)
  assert.deepEqual(basis.tone_weights, WEIGHTS, "integrated 保留均衡权重")
  assert.equal(modeLabelFor(basis.regulation_mode), "综合调适")
  // 主音主题不得生效，也绝不出宫
  const theme = personalizedToneTheme(basis.regulation_mode, basis.tone_weights && "gong")
  assert.equal(theme.code, "", "integrated 不得挂载任何五音主题")
  assert.doesNotMatch(JSON.stringify(basis), /宫音|角音|徵音|商音|羽音/, "不得出现任何主音文案")
})

// ---------------------------------------------------------------- 4

test("basic_wellness + primary_tone=null：不崩、无五音主音主张", async () => {
  const basis = await basisFor(toneProfile({ mode: "basic_wellness", primary: null, weights: null }))
  assert.equal(basis.regulation_mode, "basic_wellness")
  assert.equal(basis.primary_tone, null)
  assert.equal(basis.tone_weights, null)
  assert.equal(modeLabelFor(basis.regulation_mode), "基础舒缓")
  assert.equal(personalizedToneTheme(basis.regulation_mode, "gong").code, "")
  assert.doesNotMatch(JSON.stringify(basis), /宫音|角音|徵音|商音|羽音/)
})

// ---------------------------------------------------------------- 5

test("缺失/未知 mode：不发明 mode、不合成主音、不默认宫", async () => {
  // 后端只给了主音、没有 mode（1A 前 payload）：前端不得据此推断 personalized
  const legacy = await basisFor(toneProfile({ primary: "gong" }))
  assert.equal(legacy.regulation_mode, null)
  assert.equal(legacy.primary_tone, null, "缺少权威 mode 时不得暴露主音")
  assert.equal(modeLabelFor(legacy.regulation_mode), "")
  assert.equal(normalizeRegulationMode("not_a_mode"), "")
  assert.equal(personalizedToneTheme("not_a_mode", "gong").code, "")
  assert.doesNotMatch(JSON.stringify(legacy), /宫音/)

  // 只有权重、没有主音、没有 mode：绝不 argmax 合成主音
  const weightsOnly = await basisFor(toneProfile({ weights: { jiao: 0.1, zhi: 0.1, gong: 0.6, shang: 0.1, yu: 0.1 } }))
  assert.equal(weightsOnly.primary_tone, null)
  assert.equal(weightsOnly.regulation_mode, null)
  assert.deepEqual(weightsOnly.tone_weights, { jiao: 0.1, zhi: 0.1, gong: 0.6, shang: 0.1, yu: 0.1 })

  // personalized 但主音缺失：不得用权重补一个
  const personalizedNoTone = await basisFor(toneProfile({ mode: "personalized_five_tone", weights: WEIGHTS }))
  assert.equal(personalizedNoTone.primary_tone, null)
})

// ---------------------------------------------------------------- 6

test("API 归一化：播放器模型逐字保留 mode 且非 personalized 不产出主音文案", async () => {
  const seedMusicState = (profile) => {
    storage.set("v3_flow_state", JSON.stringify({
      session_id: "sess_fe",
      prescription_id: "rx_fe",
      generation_spec: { schema_version: "generation_spec_v3.0", tone_profile: profile },
    }))
    nextAssetToneProfile = profile
  }

  // personalized 资产：保留真实主音
  seedMusicState(toneProfile({ mode: "personalized_five_tone", primary: "jiao", weights: WEIGHTS }))
  await apiV3.startMusicGeneration()
  let music = await apiV3.getMusic()
  assert.equal(music.regulation_mode, "personalized_five_tone")
  assert.equal(music.tone_code, "jiao")
  assert.equal(music.tone_label, "角音为主")

  // integrated 资产：mode 保留、无 tone_code / 无"…为主"文案
  seedMusicState(toneProfile({ mode: "integrated_regulation", primary: null, weights: WEIGHTS }))
  await apiV3.startMusicGeneration()
  music = await apiV3.getMusic()
  assert.equal(music.regulation_mode, "integrated_regulation")
  assert.equal(music.tone_code, "")
  assert.equal(music.tone_label, "")
  assert.ok(!/为主/.test(JSON.stringify(music)), "不得出现主音文案")

  // basic 资产：同上，且不得出现任何五音
  seedMusicState(toneProfile({ mode: "basic_wellness", primary: null, weights: null }))
  await apiV3.startMusicGeneration()
  music = await apiV3.getMusic()
  assert.equal(music.regulation_mode, "basic_wellness")
  assert.equal(music.tone_code, "")
  assert.equal(music.tone_label, "")
  assert.doesNotMatch(JSON.stringify(music), /宫|角|徵|商|羽/)

  // 未带 mode 的资产：不得凭主音推断
  seedMusicState(toneProfile({ primary: "gong" }))
  await apiV3.startMusicGeneration()
  music = await apiV3.getMusic()
  assert.equal(music.regulation_mode, null)
  assert.equal(music.tone_code, "")
  assert.equal(music.tone_label, "")
})

// ---------------------------------------------------------------- helpers

test("主题表 mode 词汇：只在 personalized 且存在真实主音时生效", () => {
  assert.equal(normalizeRegulationMode("personalized_five_tone"), "personalized_five_tone")
  assert.equal(normalizeRegulationMode("INTEGRATED_REGULATION"), "integrated_regulation")
  assert.equal(normalizeRegulationMode(""), "")
  assert.equal(normalizeRegulationMode(null), "")
  assert.equal(normalizeRegulationMode(undefined), "")
  assert.equal(normalizeRegulationMode("legacy"), "")

  assert.equal(modeLabelFor("integrated_regulation"), "综合调适")
  assert.equal(modeLabelFor("basic_wellness"), "基础舒缓")
  assert.equal(modeLabelFor("personalized_five_tone"), "")
  assert.equal(modeLabelFor(""), "")

  assert.equal(personalizedToneTheme("personalized_five_tone", "jiao").code, "jiao")
  assert.equal(personalizedToneTheme("personalized_five_tone", "宫音").code, "gong")
  assert.equal(personalizedToneTheme("integrated_regulation", "gong").code, "")
  assert.equal(personalizedToneTheme("basic_wellness", "gong").code, "")
  assert.equal(personalizedToneTheme("", "gong").code, "")
  assert.equal(personalizedToneTheme(undefined, undefined).code, "")
  // 未知音仍然只是空状态，绝不回退成宫
  assert.equal(toneThemeFor("unknown-tone").glyph, "--")
})

// ---------------------------------------------------------------- static scans

function productionFiles(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    if (["node_modules", "dist", "unpackage", ".git"].includes(entry)) continue
    const full = resolve(dir, entry)
    if (statSync(full).isDirectory()) out.push(...productionFiles(full))
    else if (/\.(js|vue)$/.test(entry)) out.push(full)
  }
  return out
}

test("生产代码不存在任何宫兜底 / 前端 mode 推断", () => {
  const files = [
    ...productionFiles(resolve(root, "common")),
    ...productionFiles(resolve(root, "pages")),
    ...(statSync(resolve(root, "components"), { throwIfNoEntry: false }) ? productionFiles(resolve(root, "components")) : []),
  ]
  assert.ok(files.length > 20, "应扫描到全部生产前端文件")
  const forbidden = [
    /\|\|\s*["']gong["']/,
    /\?\?\s*["']gong["']/,
    /\bprimary_tone\s*(\|\||\?\?)\s*["'](?:gong|jiao|zhi|shang|yu)["']/,
    // ident 形式的 argmax 调用（注释里提到 argmax 是文档，不算实现）
    /\bargmax\s*\(|\.argmax\b/i,
    /dominant_tone/,
  ]
  for (const file of files) {
    const text = readFileSync(file, "utf8")
    for (const pattern of forbidden) {
      assert.doesNotMatch(text, pattern, `${file} 不得包含 ${pattern}`)
    }
  }
})

test("api-v3.js 归一化保留 regulation_mode / 权重，并 mode-aware 派生主音", () => {
  const api = read("common/api-v3.js")
  assert.match(api, /regulation_mode: regulationMode/)
  assert.match(api, /tone_weights: toneWeights/)
  assert.match(api, /const primary = personalized \? toneProfile\.primary_tone \|\| null : null/)
  assert.match(api, /isPersonalizedMode\(toneProfile\.regulation_mode\)/)
  assert.doesNotMatch(api, /toneProfile\.dominant_tone/)
})

test("v3-basis：主音区块通过 music-presentation 的 mode-aware view model 渲染", () => {
  const basis = read("pages/v3-basis/v3-basis.vue")
  assert.match(basis, /buildAnalysisViewModel/)
  assert.match(basis, /analysisPresentation\.primaryTone/)
  assert.match(basis, /analysisPresentation\.secondaryTone/)
  assert.match(basis, /v-else class="tone-detail tone-detail--neutral"/)
  assert.match(basis, /return this\.analysisPresentation\.hasPrimaryTone/)
  assert.doesNotMatch(basis, /toneThemeFor\(/)
})

test("v3-player：主音展示来自 music-presentation，且不存在宫兜底", () => {
  const player = read("pages/v3-player/v3-player.vue")
  assert.match(player, /buildMusicPresentation/)
  assert.match(player, /playerPresentation\.primaryTone/)
  assert.doesNotMatch(player, /v31-tone-theme/)
  assert.doesNotMatch(player, /["']gong["']/)
  assert.doesNotMatch(player, /<text class="tone-seal">主音<\/text>/)
})
