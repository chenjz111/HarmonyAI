import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"


const source = readFileSync(
  new URL("../common/api-v2.js", import.meta.url),
  "utf8",
)


test("Sprint 3 API client uses only frozen v2 endpoints", () => {
  for (const endpoint of [
    "/api/v2/sessions",
    "/api/v2/documents",
    "/api/v2/assessments",
    "/api/v2/workflows",
    "/api/v2/music",
    "/api/v2/feedback",
  ]) {
    assert.match(source, new RegExp(endpoint.replaceAll("/", "\\/")))
  }

  for (const forbidden of [
    "/api/v2/records",
    "/api/v2/narrative",
    "/api/v2/analysis/",
    "/api/v2/prescription/audio",
    "assessment_agent_v2",
    "music_agent_v2",
    "feedback_agent_v2",
  ]) {
    assert.equal(source.includes(forbidden), false)
  }
})


test("real backend is the default and mock mode is explicit", () => {
  assert.match(source, /VITE_API_BASE_URL/)
  assert.match(source, /HARMONYAI_USE_MOCK/)
  assert.doesNotMatch(source, /USE_MOCK\s*=\s*true/)
})


test("client exposes every Sprint 3 operation", () => {
  for (const operation of [
    "createSession",
    "uploadDocument",
    "confirmDocument",
    "submitAssessment",
    "runWorkflow",
    "requestMusic",
    "submitFeedback",
    "getSession",
  ]) {
    assert.match(source, new RegExp(`export\\s+(?:async\\s+)?function\\s+${operation}\\b`))
  }
})
