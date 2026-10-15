import assert from "node:assert/strict"
import test from "node:test"

test("mock one-click contract: legal edit commits one revision; stale input and rejected edit do not commit", async () => {
  process.env.HARMONYAI_V3_MODE = "mock"
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.__resetForTest()
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")
  await apiV3.uploadDocument(null, "资料.jpg")
  const before = await apiV3.getCaseSummary()
  const session = await apiV3.getSession()
  await assert.rejects(() => apiV3.confirmUnderstanding({
    expected_revision: before.revision, expected_input_revision: session.input_revision - 1,
    decision: "confirm_with_changes", edited_summary_text: "睡眠恢复不足。", reprocess_requested: true,
  }), error => error.code === "INPUT_REVISION_CONFLICT")
  await assert.rejects(() => apiV3.confirmUnderstanding({
    expected_revision: before.revision, decision: "confirm_with_changes",
    edited_summary_text: "无睡眠恢复不足。", reprocess_requested: true,
  }), error => error.code === "EVIDENCE_ADMISSION_FAILED")
  assert.equal((await apiV3.getCaseSummary()).revision, before.revision)
  const edited = await apiV3.confirmUnderstanding({
    expected_revision: before.revision, decision: "confirm_with_changes", changes: [],
    edited_summary_text: "用户修改后的资料。", reprocess_requested: true,
  })
  // Controlled mock candidates test transport/state semantics, not real AI accuracy.
  assert.equal(edited.status, "confirmed")
  assert.equal(edited.revision, before.revision + 1)
  assert.equal(edited.previous_revision, before.revision)
  assert.equal(edited.input_revision, session.input_revision + 1)
  assert.equal((await apiV3.getSession()).input_revision, edited.input_revision)
  assert.equal("evidence_admission" in edited, false)
  await assert.rejects(() => apiV3.confirmUnderstanding({
    expected_revision: before.revision, decision: "confirm", changes: [],
  }), error => error.code === "REVISION_CONFLICT")
})
