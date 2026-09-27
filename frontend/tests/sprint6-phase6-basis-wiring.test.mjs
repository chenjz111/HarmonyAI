import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const source = readFileSync(new URL("../pages/v3-basis/v3-basis.vue", import.meta.url), "utf8")

test("PR-031: v3-basis is a cached, read-only compatibility page", () => {
  assert.match(source, /apiV3\.getMusicBasis\(\)/)
  assert.doesNotMatch(source, /allowCreate\s*:\s*true/)
  assert.doesNotMatch(source, /createMusicGenerationSession/)
  assert.doesNotMatch(source, /ensureGeneration|startMusicGeneration|pollMusicGeneration|cancelMusicGeneration/)
})

test("v3-basis delegates read-model presentation and reads no theme facts", () => {
  assert.match(source, /buildAnalysisViewModel/)
  assert.doesNotMatch(source, /v31-tone-theme/)
  assert.doesNotMatch(source, /(?:primary|secondary)ToneTheme/)
  assert.doesNotMatch(source, /\.traits\b/)
  assert.doesNotMatch(source, /\.split\(\s*\/\[，。\]\?提示\//)
  assert.doesNotMatch(source, /作为本次调适依据/)
})

test("PR-031: v3-basis owns no task progress, retry, cancel, or Player navigation", () => {
  assert.doesNotMatch(source, /GENERATION_STATES|generationSnapshot|taskId|requestId/)
  assert.doesNotMatch(source, /\.retry\s*\(|\.cancel\s*\(|v3-player/)
})
