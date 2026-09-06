import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"


const frontendRoot = resolve(import.meta.dirname, "..")
const pagesConfig = JSON.parse(readFileSync(resolve(frontendRoot, "pages.json"), "utf8"))
const routes = pagesConfig.pages.map((page) => page.path)


test("V3.1: entry is the launch home page; welcome keeps a registered sprint-3 entry", () => {
  const sprint3Routes = [
    "pages/welcome/welcome",
    "pages/material/material",
    "pages/narrative/narrative",
    "pages/survey-v2/survey-v2",
    "pages/result/result",
    "pages/player-v2/player-v2",
    "pages/feedback-v2/feedback-v2",
    "pages/complete/complete",
  ]
  // Issue #100: Welcome leaves the main flow; entry becomes the home/launch page.
  assert.equal(routes[0], "pages/entry/entry")
  for (const route of sprint3Routes) {
    assert.ok(routes.includes(route), `missing route: ${route}`)
    assert.ok(existsSync(resolve(frontendRoot, `${route}.vue`)), `missing page: ${route}`)
  }
})


test("Sprint 2 pages remain reachable", () => {
  for (const route of [
    "pages/index/index",
    "pages/emotion/emotion",
    "pages/survey/survey",
    "pages/player/player",
  ]) {
    assert.ok(routes.includes(route), `legacy route removed: ${route}`)
  }
})

const sprint3Source = [
  "welcome/welcome.vue",
  "material/material.vue",
  "narrative/narrative.vue",
  "survey-v2/survey-v2.vue",
  "result/result.vue",
  "player-v2/player-v2.vue",
  "feedback-v2/feedback-v2.vue",
  "complete/complete.vue",
].map((file) => readFileSync(resolve(frontendRoot, "pages", file), "utf8")).join("\n")


test("Sprint 3 pages use the frozen field contract", () => {
  for (const field of [
    "document_id",
    "document_text",
    "narrative_text",
    "questionnaire_answers",
    "analysis_mode",
    "emotion_profile",
    "extracted_evidence",
    "stream_url",
    "source_type",
    "pre_state",
    "post_state",
  ]) {
    assert.ok(sprint3Source.includes(field), `missing contract field: ${field}`)
  }

  for (const forbidden of [
    "record_id",
    "assessment_agent_v2",
    "music_agent_v2",
    "feedback_agent_v2",
    "/api/v2/records",
    "/api/v2/narrative",
    "/api/v2/prescription/audio",
  ]) {
    assert.equal(sprint3Source.includes(forbidden), false, `obsolete contract: ${forbidden}`)
  }
})


test("questionnaire and Feedback 2.0 fields are complete", () => {
  const survey = readFileSync(resolve(frontendRoot, "pages/survey-v2/survey-v2.vue"), "utf8")
  const ids = [...survey.matchAll(/id:\s*'(q\d{2}_[a-z_]+)'/g)].map((match) => match[1])
  assert.deepEqual(ids, [
    "q01_mood_weather", "q02_tension_worry", "q03_overthinking",
    "q04_irritability_anger", "q05_low_mood", "q06_interest_loss",
    "q07_fear_unease", "q08_sleep_disturbance", "q09_low_energy",
    "q10_appetite_change", "q11_daily_impact", "q12_physical_safety",
  ])

  const feedback = readFileSync(resolve(frontendRoot, "pages/feedback-v2/feedback-v2.vue"), "utf8")
  for (const field of [
    "overall_rating", "relaxation_rating", "music_match_rating", "continue_use",
    "favorite", "disliked_features", "disliked_instruments", "comment",
  ]) {
    assert.ok(feedback.includes(field), `missing Feedback 2.0 field: ${field}`)
  }
})
