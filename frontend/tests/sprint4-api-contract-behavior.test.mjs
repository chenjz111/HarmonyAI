import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import {
  assessmentConfirmationRequest,
  assessmentFollowUpRequest,
  assessmentRequest,
  documentConfirmationRequest,
  musicRequest,
  workflowRequest,
} from "../common/api-contract-v2.js"
import { applyExclusiveChoice, safetyFlowForAnswer } from "../common/questionnaire-rules.js"


const questionnaire = JSON.parse(readFileSync(
  new URL("../../knowledge/questionnaire-v2.1.json", import.meta.url),
  "utf8",
))
const quickState = JSON.parse(readFileSync(
  new URL("../../knowledge/quick-state-questionnaire-v1.json", import.meta.url),
  "utf8",
))


test("frontend uses the repository canonical questionnaire artifacts", () => {
  assert.equal(questionnaire.schema_version, "questionnaire_v2.1")
  assert.equal(questionnaire.questions.length, 20)
  assert.equal(quickState.schema_version, "quick_state_v1")
  assert.equal(quickState.questions.length, 6)
  const q04 = questionnaire.questions.find((item) => item.question_id === "q04_worry_control")
  assert.equal(q04.scored, false)
  assert.equal(q04.weight, 0)
})


test("assessment request matches the real POST /api/v2/assessments schema", () => {
  const spec = assessmentRequest({
    sessionId: "sess-1", userId: "user-1", documentId: "doc-1",
    documentText: "confirmed text", narrativeText: "recent events",
    questionnaireAnswers: { schema_version: "questionnaire_v2.1", time_window_days: 14, answers: [] },
  })
  assert.equal(spec.path, "/api/v2/assessments")
  assert.equal(spec.method, "POST")
  assert.deepEqual(spec.data, {
    session_id: "sess-1", user_id: "user-1", document_id: "doc-1",
    document_text: "confirmed text", narrative_text: "recent events",
    questionnaire_answers: { schema_version: "questionnaire_v2.1", time_window_days: 14, answers: [] },
  })
})


test("document confirmation includes session and redaction confirmation", () => {
  assert.deepEqual(documentConfirmationRequest("doc-1", {
    sessionId: "sess-1", confirmed: true, documentText: "edited OCR",
  }), {
    path: "/api/v2/documents/doc-1/confirmation",
    method: "PATCH",
    data: { session_id: "sess-1", confirmed: true, document_text: "edited OCR", redactions_confirmed: true },
  })
})


test("follow-up and confirmation use assessment_id plus current revision", () => {
  assert.deepEqual(assessmentFollowUpRequest("asmt-1", 3, [
    { follow_up_id: "fu-1", answer: "1-2 weeks" },
  ]), {
    path: "/api/v2/assessments/asmt-1/follow-up",
    method: "POST",
    data: { revision: 3, answers: [{ follow_up_id: "fu-1", answer: "1-2 weeks" }] },
  })
  assert.deepEqual(assessmentConfirmationRequest("asmt-1", {
    revision: 4, confirmationLevel: "partially_accurate",
    corrections: [{ field: "emotion_profile.primary_states", from: ["worry"], to: ["fatigue"] }],
  }), {
    path: "/api/v2/assessments/asmt-1/confirmation",
    method: "PATCH",
    data: {
      revision: 4, confirmation_level: "partially_accurate",
      corrections: [{ field: "emotion_profile.primary_states", from: ["worry"], to: ["fatigue"] }],
    },
  })
})


test("confirmed workflow and music use real existing endpoints", () => {
  const workflow = workflowRequest({ session_id: "sess-1", assessment_confirmed: true })
  assert.equal(workflow.path, "/api/v2/workflows")
  assert.equal(workflow.method, "POST")
  const music = musicRequest("sess-1", { output: { music_feature: { tone_name: "角调" } } })
  assert.deepEqual(music, {
    path: "/api/v2/music", method: "POST",
    data: { session_id: "sess-1", prescription: { output: { music_feature: { tone_name: "角调" } } } },
  })
})



test("Frozen questionnaire safety and none exclusivity are enforced in the UI layer", () => {
  assert.deepEqual(applyExclusiveChoice("q16_physical_signals", ["neck_tension"], "none"), ["none"])
  assert.deepEqual(applyExclusiveChoice("q20_emergency", ["none"], "severe_chest_pain"), ["severe_chest_pain"])
  assert.equal(safetyFlowForAnswer("q19_self_harm", "never"), null)
  assert.equal(safetyFlowForAnswer("q19_self_harm", "fleeting"), "SAFETY_SELF_HARM")
  assert.equal(safetyFlowForAnswer("q20_emergency", ["none"]), null)
  assert.equal(safetyFlowForAnswer("q20_emergency", ["severe_breathing_difficulty"]), "SAFETY_EMERGENCY_PHYSICAL")
})

test("public API client sends real Frozen requests and unwraps responses", async () => {
  const calls = []
  globalThis.uni = {
    request(options) {
      calls.push(options)
      options.success({ data: { success: true, data: { accepted: true } } })
    },
  }
  const api = await import("../common/api-v2.js?behavior-test=1")
  await api.confirmDocument("doc-1", {
    sessionId: "sess-1", confirmed: true, documentText: "edited",
  })
  await api.submitFollowUpAnswers("asmt-1", 2, [
    { follow_up_id: "fu-1", answer: "answer" },
  ])
  await api.confirmAssessment("asmt-1", {
    revision: 3, confirmationLevel: "fully_accurate",
  })
  assert.deepEqual(calls.map(({ url, method, data }) => ({ url, method, data })), [
    {
      url: "http://localhost:8000/api/v2/documents/doc-1/confirmation",
      method: "PATCH",
      data: {
        session_id: "sess-1", confirmed: true, document_text: "edited",
        redactions_confirmed: true,
      },
    },
    {
      url: "http://localhost:8000/api/v2/assessments/asmt-1/follow-up",
      method: "POST",
      data: { revision: 2, answers: [{ follow_up_id: "fu-1", answer: "answer" }] },
    },
    {
      url: "http://localhost:8000/api/v2/assessments/asmt-1/confirmation",
      method: "PATCH",
      data: { revision: 3, confirmation_level: "fully_accurate", corrections: [] },
    },
  ])
  delete globalThis.uni
})

test("Sprint 4 Vue 3 pages do not call removed this.$set", () => {
  for (const page of [
    "../pages/questionnaire-v2/questionnaire-v2.vue",
    "../pages/quick-state/quick-state.vue",
    "../pages/assessment-result/assessment-result.vue",
  ]) {
    const source = readFileSync(new URL(page, import.meta.url), "utf8")
    assert.equal(source.includes("this.$set"), false, page + " still uses Vue 2 this.$set")
  }
})