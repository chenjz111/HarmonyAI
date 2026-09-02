import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const frontend = path.resolve(here, "..")
const read = (relativePath) => fs.readFileSync(path.join(frontend, relativePath), "utf8")

test("V3 visual tokens define the approved palette, typography and responsive container", () => {
  const tokens = read("styles/v3-visual-tokens.scss").toLowerCase()
  for (const value of [
    "#f6f7f3", "#ffffff", "#4e7468", "#36584f", "#b99b63",
    "#25312d", "#69756f", "#98a29e", "#e3e7e2", "#a8645e",
  ]) {
    assert.ok(tokens.includes(value), `missing approved token ${value}`)
  }
  assert.ok(tokens.includes("720px"), "desktop flow container must be capped near 720px")
  assert.match(tokens, /harmonyos sans sc/i)
  assert.match(tokens, /safe-area-inset-left/)
  assert.match(tokens, /prefers-reduced-motion/)
})

test("V3 Entry uses a hero and two large mode cards while preserving selectMode", () => {
  const page = read("pages/entry/entry.vue")
  assert.match(page, /class="[^"]*entry-hero[^"]*"/)
  assert.match(page, /class="[^"]*mode-card[^"]*"/)
  assert.match(page, /class="[^"]*privacy-panel[^"]*"/)
  assert.match(page, /apiV3\.selectMode\(choice\.id\)/)
  assert.match(page, /@click="choose\(c\)"/)
  assert.doesNotMatch(page, /🎵|🎤|📄|📝/)
})

test("V3 Questionnaire has a calm question layout and preserves answer behavior", () => {
  const page = read("pages/v3-questionnaire/v3-questionnaire.vue")
  assert.match(page, /class="[^"]*question-shell[^"]*"/)
  assert.match(page, /class="[^"]*question-support[^"]*"/)
  assert.match(page, /class="[^"]*bottom-navigation[^"]*"/)
  assert.match(page, /question\.max_selections/)
  assert.match(page, /toggleOption\(opt\)/)
  assert.match(page, /currentFrequencyValue === opt\.value/)
  assert.match(page, /apiV3\.submitQuestionnaire\(this\.answers\)/)
})

test("V3 Player uses immersive visual regions without inventing playback progress", () => {
  const page = read("pages/v3-player/v3-player.vue")
  assert.match(page, /class="[^"]*music-identity[^"]*"/)
  assert.match(page, /class="[^"]*breathing-artwork[^"]*"/)
  assert.match(page, /class="[^"]*music-parameter-summary[^"]*"/)
  assert.match(page, /apiV3\.fetchAuthorizedAudio/)
  assert.match(page, /apiV3\.addFavorite/)
  assert.match(page, /@click="togglePlay"/)
  assert.doesNotMatch(page, /<slider|progress-percent|buffer-progress|fake-progress/)
})
