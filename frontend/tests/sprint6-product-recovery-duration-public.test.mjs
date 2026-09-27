import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import { buildAnalysisViewModel, buildMusicPresentation } from "../common/music-presentation.js"

const playerSource = readFileSync(new URL("../pages/v3-player/v3-player.vue", import.meta.url), "utf8")
const basisSource = readFileSync(new URL("../pages/v3-basis/v3-basis.vue", import.meta.url), "utf8")

test("PR-014: recommendation duration is not projected into public analysis", () => {
  const analysis = buildAnalysisViewModel({
    regulation_mode: "integrated_regulation",
    duration: { seconds: 420 },
  })

  assert.equal(Object.hasOwn(analysis.parameters, "duration"), false)
})

test("PR-015: Player duration uses measured audio then verified asset only", () => {
  const measured = buildMusicPresentation({
    music: { duration_seconds: 240 },
    basis: { duration: { seconds: 420 } },
    measuredSeconds: 301,
  })
  assert.equal(measured.duration.seconds, 301)

  const asset = buildMusicPresentation({
    music: { duration_seconds: 240 },
    basis: { duration: { seconds: 420 } },
  })
  assert.equal(asset.duration.seconds, 240)

  const noPlaybackAuthority = buildMusicPresentation({
    music: {},
    basis: { duration: { seconds: 420 } },
  })
  assert.equal(noPlaybackAuthority.duration.seconds, null)
  assert.equal(noPlaybackAuthority.duration.known, false)
})

test("PR-014/PR-015: recommendation duration is absent from public page cards", () => {
  const playerTemplate = playerSource.match(/<template>([\s\S]*?)<\/template>/)[1]
  const basisTemplate = basisSource.match(/<template>([\s\S]*?)<\/template>/)[1]

  assert.doesNotMatch(playerTemplate, /聆听时长/)
  assert.doesNotMatch(playerTemplate, /analysis\.parameters\.duration/)
  assert.doesNotMatch(basisTemplate, /analysisPresentation\.parameters\.duration/)
  assert.doesNotMatch(basisTemplate, /<text class="param-label">时长<\/text>/)
})

test("PR-014: Generation Spec duration remains internal generation input", () => {
  const apiSource = readFileSync(new URL("../common/api-v3.js", import.meta.url), "utf8")

  assert.match(apiSource, /duration:\s*\{\s*seconds:\s*spec\.duration_seconds/)
})
