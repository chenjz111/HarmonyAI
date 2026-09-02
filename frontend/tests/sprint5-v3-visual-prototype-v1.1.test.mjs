import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const frontend = path.resolve(here, "..")
const read = (relativePath) => fs.readFileSync(path.join(frontend, relativePath), "utf8")

test("Entry V1.1 uses restrained brand, supporting metadata and privacy hint", () => {
  const page = read("pages/entry/entry.vue")
  assert.match(page, />HarmonyAI · 个性化音乐</)
  assert.match(page, /class="[^"]*choice-meta[^"]*supporting-text[^"]*"/)
  assert.match(page, /class="[^"]*privacy-panel[^"]*privacy-hint[^"]*"/)
  assert.match(page, /\.hero-eyebrow[^}]*letter-spacing:\s*\.04em/s)
  assert.match(page, /\.choice-arrow[^}]*background:\s*transparent/s)
})

test("Questionnaire V1.1 presents a friendly title and restrained selectable cards", () => {
  const page = read("pages/v3-questionnaire/v3-questionnaire.vue")
  assert.match(page, />近期状态问卷</)
  assert.match(page, /\.q-prompt[^}]*font-weight:\s*600/s)
  assert.match(page, /\.q-option-active[^}]*rgba\(78,\s*116,\s*104,\s*\.0[3-6]\)/s)
  assert.match(page, /\.questionnaire-page[^}]*padding-bottom:\s*calc\(/s)
})

test("Player V1.1 provides a compact friendly error state with the existing retry action", () => {
  const page = read("pages/v3-player/v3-player.vue")
  assert.match(page, />音乐暂时还没有准备好</)
  assert.match(page, />生成服务可能暂时繁忙，你可以重新尝试。</)
  assert.match(page, /class="[^"]*error-actions[^"]*"/)
  assert.match(page, /@click="load"/)
  assert.doesNotMatch(page, /<slider|progress-percent|buffer-progress|fake-progress/)
})
