import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

import { buildMusicPresentation } from "../common/music-presentation.js"

const source = readFileSync(new URL("../pages/v3-player/v3-player.vue", import.meta.url), "utf8")

test("v3-player delegates every audio lifecycle action to player-controller", () => {
  assert.match(source, /createPlayerController/)
  assert.match(source, /playerController\.toggle\(/)
  assert.match(source, /playerController\.seek\(/)
  assert.match(source, /playerController\.handleHide\(\)/)
  assert.match(source, /playerController\.handleShow\(\)/)
  assert.match(source, /playerController\.dispose\(\)/)
  assert.match(source, /onStateChange:\s*snapshot\s*=>/)

  assert.doesNotMatch(source, /uni\.createInnerAudioContext\s*\(/)
  assert.doesNotMatch(source, /\.onCanplay\s*\(/)
  assert.doesNotMatch(source, /\.onTimeUpdate\s*\(/)
  assert.doesNotMatch(source, /\.onEnded\s*\(/)
  assert.doesNotMatch(source, /\.onError\s*\(/)
  assert.doesNotMatch(source, /\baudioCtx\b|resolvedAudioSrc|resolvedAudioStreamUrl/)
})

test("v3-player renders music facts, duration, progress, and failure through music-presentation", () => {
  assert.match(source, /buildMusicPresentation/)
  assert.match(source, /presentProgress/)
  assert.match(source, /playerPresentation\.title\.displayText/)
  assert.match(source, /playerPresentation\.instruments\.displayText/)
  assert.match(source, /playerPresentation\.ambience\.displayText/)
  assert.match(source, /playerPresentation\.duration\.minutesText/)
  assert.match(source, /progressPresentation\.currentText/)
  assert.match(source, /progressPresentation\.totalText/)
  assert.match(source, /failurePresentation\.failure\.message/)

  assert.doesNotMatch(source, /v31-tone-theme/)
  assert.doesNotMatch(source, /\.traits\b|\.instruments\s*\|\||\.ambience\s*\|\||\.title\s*\|\|/)
  assert.doesNotMatch(source, /\btotalSeconds\s*\(\)|\bprogressPercent\s*\(\)|\bsummaryDuration\s*\(\)/)
})

test("music-presentation carries visual-only tone metadata without page access to the theme table", () => {
  const model = buildMusicPresentation({
    music: { regulation_mode: "personalized_five_tone", tone_code: "jiao", title: "测试音乐" },
  })
  assert.equal(model.primaryTone.code, "jiao")
  assert.equal(model.primaryTone.imageCode, "jue")
  assert.equal(model.primaryTone.accent, "#326f62")
  assert.equal(model.primaryTone.soft, "#dfeee8")
})
