import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import { buildAnalysisViewModel } from "../common/music-presentation.js"

const playerSource = readFileSync(new URL("../pages/v3-player/v3-player.vue", import.meta.url), "utf8")
const basisSource = readFileSync(new URL("../pages/v3-basis/v3-basis.vue", import.meta.url), "utf8")

test("PR-016: technical audit copy is suppressed at the public presentation boundary", () => {
  const model = buildAnalysisViewModel({
    confirmed_state: "近期睡眠欠佳。",
    state_tendency: "RAG_EMPTY：当前检索证据不足，已进入医学性暂缓。",
    analysis_rationales: [
      { summary: "Embedding 检索未返回 approved chunk。" },
      { summary: "依据已确认的近期状态采用舒缓节奏。" },
    ],
  })

  assert.equal(model.stateSummary.text, "近期睡眠欠佳。")
  assert.equal(model.tendency.hasText, false)
  assert.deepEqual(model.rationales.rows.map(item => item.text), ["依据已确认的近期状态采用舒缓节奏。"])
  assert.doesNotMatch(JSON.stringify(model), /RAG|检索证据|医学性暂缓|Embedding|approved chunk/i)
})

test("PR-017: every public analysis section computes hasContent independently", () => {
  const empty = buildAnalysisViewModel({
    state_tendency: "RAG_EMPTY",
    analysis_rationales: [{ summary: "Qwen Provider 未执行。" }],
    duration: { seconds: 300 },
  })

  assert.deepEqual(
    Object.fromEntries(Object.entries(empty.sections).map(([key, value]) => [key, value.hasContent])),
    {
      recentState: false,
      interpretation: false,
      rationales: false,
      toneConfiguration: false,
      musicDesign: false,
    },
  )
  assert.equal(empty.hasContent, false)

  const resolved = buildAnalysisViewModel({
    confirmed_state: "近期容易疲倦。",
    state_tendency: "本次未形成明确的状态倾向",
    analysis_rationales: [{ summary: "依据已确认信息安排本次音乐。" }],
    regulation_mode: "integrated_regulation",
    bpm: { value: 58 },
  })
  assert.equal(resolved.sections.recentState.hasContent, true)
  assert.equal(resolved.sections.interpretation.hasContent, true)
  assert.equal(resolved.sections.rationales.hasContent, true)
  assert.equal(resolved.sections.toneConfiguration.hasContent, true)
  assert.equal(resolved.sections.musicDesign.hasContent, true)
  assert.equal(resolved.hasContent, true)
})

test("PR-017: Player and compatibility basis render sections only through section flags", () => {
  for (const [name, source] of [["Player", playerSource], ["Basis", basisSource]]) {
    assert.match(source, /sections\.recentState\.hasContent/, `${name} recent-state gate`)
    assert.match(source, /sections\.interpretation\.hasContent/, `${name} interpretation gate`)
    assert.match(source, /sections\.rationales\.hasContent/, `${name} rationale gate`)
    assert.match(source, /sections\.toneConfiguration\.hasContent/, `${name} tone gate`)
    assert.match(source, /sections\.musicDesign\.hasContent/, `${name} music-design gate`)
  }
})

test("PR-016: public projection has no technical fallback literals", () => {
  const source = readFileSync(new URL("../common/music-presentation.js", import.meta.url), "utf8")
  const publicModel = buildAnalysisViewModel({
    state_tendency: "FACT_EXTRACTION_SCHEMA_INVALID",
    analysis_rationales: [{ summary: "TokenHub/Minimax provider error" }],
  })

  assert.equal(publicModel.hasContent, false)
  assert.doesNotMatch(JSON.stringify(publicModel), /FACT_EXTRACTION|TokenHub|Minimax/i)
  assert.match(source, /presentPublic/)
})
