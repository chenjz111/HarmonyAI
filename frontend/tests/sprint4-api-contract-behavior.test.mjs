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

