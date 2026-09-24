import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const source = readFileSync(new URL("../pages/v3-basis/v3-basis.vue", import.meta.url), "utf8")

test("v3-basis delegates generation lifecycle to music-generation-session", () => {
  assert.match(source, /createMusicGenerationSession/)
  assert.match(source, /generationSession\.ensureGeneration\(\)/)
  assert.match(source, /generationSession\.retry\(\)/)
  assert.match(source, /generationSession\.cancel\(\)/)
  assert.match(source, /generationSession\.onHide\(\)/)
  assert.match(source, /generationSession\.onShow\(\)/)
  assert.match(source, /generationSession\.dispose\(\)/)

  assert.doesNotMatch(source, /\bpollTimer\b/)
  assert.doesNotMatch(source, /\bschedulePoll\b/)
  assert.doesNotMatch(source, /\bstopPoll\b/)
  assert.doesNotMatch(source, /\bsetInterval\s*\(/)
})

test("v3-basis delegates read-model presentation and reads no theme facts", () => {
  assert.match(source, /buildAnalysisViewModel/)
  assert.doesNotMatch(source, /v31-tone-theme/)
  assert.doesNotMatch(source, /(?:primary|secondary)ToneTheme/)
  assert.doesNotMatch(source, /\.traits\b/)
  assert.doesNotMatch(source, /\.split\(\s*\/\[，。\]\?提示\//)
  assert.doesNotMatch(source, /作为本次调适依据/)
})

test("v3-basis keeps task progress and terminal navigation driven by session snapshots", () => {
  assert.match(source, /generationSession\.subscribe/)
  assert.match(source, /GENERATION_STATES\.PLAYABLE/)
  assert.match(source, /GENERATION_STATES\.MATCHED_FALLBACK/)
  assert.match(source, /snapshot\.task/)
  assert.match(source, /snapshot\.copy/)
  assert.match(
    source,
    /snapshot\.state === GENERATION_STATES\.SYNC_ERROR && !snapshot\.taskId[\s\S]*?this\.phase = "cancelled"/,
    "a POST with an unknown outcome must expose the session retry that reuses its request id",
  )
})
