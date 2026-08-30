/**
 * Sprint 5 V3 owner-flow-1 前端契约测试
 * 依据：docs/contracts/harmonyai-v3-owner-flow-amendment-001.md
 *      docs/contracts/frontend-read-model-contract-v3.md
 */
import assert from "node:assert/strict"
import { readFileSync, existsSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const frontendRoot = resolve(import.meta.dirname, "..")
const pagesConfig = JSON.parse(readFileSync(resolve(frontendRoot, "pages.json"), "utf8"))
const routes = pagesConfig.pages.map((p) => p.path)

function readPage(name) {
  const file = resolve(frontendRoot, "pages", name)
  assert.ok(existsSync(file), `missing page file: ${name}`)
  return readFileSync(file, "utf8")
}

// ===== 路由注册 =====

test("V3 owner-flow pages are all registered", () => {
  const v3Routes = [
    "pages/entry/entry",
    "pages/v3-material/v3-material",
    "pages/v3-summary/v3-summary",
    "pages/v3-narrative/v3-narrative",
    "pages/v3-questionnaire/v3-questionnaire",
    "pages/v3-confirm/v3-confirm",
    "pages/v3-basis/v3-basis",
    "pages/v3-player/v3-player",
  ]
  for (const route of v3Routes) {
    assert.ok(routes.includes(route), `missing V3 route: ${route}`)
    assert.ok(existsSync(resolve(frontendRoot, `${route}.vue`)), `missing V3 page: ${route}`)
  }
})

test("welcome routes into the V3 entry page", () => {
  const welcome = readPage("welcome/welcome.vue")
  assert.ok(welcome.includes("/pages/entry/entry"), "welcome must navigate to V3 entry")
})

test("Sprint 3/4 legacy routes remain (compatibility not removed)", () => {
  for (const route of [
    "pages/material/material",
    "pages/narrative/narrative",
    "pages/questionnaire-v2/questionnaire-v2",
    "pages/assessment-result/assessment-result",
    "pages/player-v2/player-v2",
    "pages/feedback-v2/feedback-v2",
    "pages/safety-support/safety-support",
  ]) {
    assert.ok(routes.includes(route), `legacy route removed: ${route}`)
  }
})

// ===== Owner Amendment 文案约束 =====

test("entry page uses the approved dual-entry wording", () => {
  const entry = readPage("entry/entry.vue")
  assert.ok(entry.includes("我有近期就诊资料"), "entry must use approved wording: with document")
  assert.ok(entry.includes("我没有近期就诊资料"), "entry must use approved wording: without document")
  assert.ok(!entry.includes("有近期材料"), "obsolete wording must not appear")
  assert.ok(!entry.includes("无近期材料"), "obsolete wording must not appear")
})

test("OCR failure page follows Amendment 3.1 standard wording", () => {
  const material = readPage("v3-material/v3-material.vue")
  assert.ok(material.includes("资料暂未识别成功"), "failure title")
  assert.ok(material.includes("重新上传资料"), "primary action")
  assert.ok(material.includes("改用描述与问卷"), "secondary action")
  assert.ok(material.includes("自由描述可以跳过，10道状态问卷需要完成"), "side note")
})

test("summary page exposes the four approved actions", () => {
  const summary = readPage("v3-summary/v3-summary.vue")
  assert.ok(summary.includes("内容基本准确，继续"), "primary action")
  assert.ok(summary.includes("修改资料摘要"), "edit action")
  assert.ok(summary.includes("重新上传资料"), "reupload action")
  assert.ok(summary.includes("改用描述与问卷"), "discard action")
  assert.ok(summary.includes("保存修改并继续"), "editor save")
  assert.ok(summary.includes("取消修改"), "editor cancel")
  assert.ok(summary.includes("edited_summary_text"), "editor must submit edited_summary_text")
  assert.ok(summary.includes("reprocess_requested"), "editor must set reprocess_requested")
})

test("V3 pages do not leak internal fields to users", () => {
  for (const page of [
    "v3-material/v3-material.vue",
    "v3-summary/v3-summary.vue",
    "v3-confirm/v3-confirm.vue",
    "v3-basis/v3-basis.vue",
    "v3-player/v3-player.vue",
  ]) {
    const src = readPage(page)
    // 模板区域不得出现内部技术字段名
    const template = (src.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
    for (const forbidden of ["provider", "confidence", "revision", "target_id", "safety_policy", "evidence_coverage"]) {
      assert.ok(!template.includes(forbidden), `${page} template leaks internal field: ${forbidden}`)
    }
  }
})

test("no music goal wording or fields in V3 flow", () => {
  for (const page of [
    "entry/entry.vue",
    "v3-material/v3-material.vue",
    "v3-summary/v3-summary.vue",
    "v3-narrative/v3-narrative.vue",
    "v3-questionnaire/v3-questionnaire.vue",
    "v3-confirm/v3-confirm.vue",
    "v3-basis/v3-basis.vue",
    "v3-player/v3-player.vue",
  ]) {
    const src = readPage(page)
    for (const forbidden of ["音乐目标", "music_goal", "user_goal", "MusicGoal"]) {
      assert.ok(!src.includes(forbidden), `${page} contains removed music-goal concept: ${forbidden}`)
    }
  }
})

test("single final confirmation: assessment confirm page has exactly one primary confirm", () => {
  const confirm = readPage("v3-confirm/v3-confirm.vue")
  assert.ok(confirm.includes("基本符合，继续"), "confirm button")
  assert.ok(confirm.includes("有些地方不对，我要修改"), "correction entry")
  assert.ok(confirm.includes("expected_revision"), "must validate expected_revision")
  // 唯一确认：确认动作只出现一次（不允许二次确认页文案）
  assert.ok(!confirm.includes("再次确认"), "no double confirmation")
})

test("player only renders backend-provided asset and keeps disclaimer", () => {
  const player = readPage("v3-player/v3-player.vue")
  assert.ok(player.includes("stream_url"), "player must use backend stream_url")
  assert.ok(player.includes("source_label"), "player must show source label from backend")
  assert.ok(player.includes("music.disclaimer"), "player must render backend disclaimer text")
})

// ===== api-v3 mock 状态机行为 =====

test("api-v3 mock: without-document flow requires full questionnaire", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  const session = await apiV3.createSession()
  assert.equal(session.flow_contract_version, "v3-owner-flow-1")
  assert.equal(session.input_mode, null)

  await apiV3.selectMode("without_document")
  const schema = await apiV3.getQuestionnaireSchema()
  assert.equal(schema.required_for_flow, true, "without document: questionnaire required")
  assert.equal(schema.skip_action, null, "without document: no skip action")

  // 未完成问卷不能创建评估（FLOW-02）
  await assert.rejects(
    () => apiV3.createAssessment(),
    (e) => e.code === "QUESTIONNAIRE_REQUIRED",
  )
})

test("api-v3 mock: with-document flow allows skipping optional questionnaire", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")

  const doc = await apiV3.uploadDocument(null, "病历报告.jpg")
  assert.equal(doc.state, "ready")

  const summary = await apiV3.getCaseSummary()
  assert.equal(summary.status, "needs_confirmation")

  const confirmed = await apiV3.confirmUnderstanding({ expected_revision: 1, decision: "confirm", changes: [] })
  assert.equal(confirmed.status, "confirmed")
  assert.equal(confirmed.revision, 2)

  // 有资料模式：问卷选填（可跳过直接评估，FLOW-01）
  const schema = await apiV3.getQuestionnaireSchema()
  assert.equal(schema.required_for_flow, false)
  const assessment = await apiV3.createAssessment()
  assert.equal(assessment.status, "needs_confirmation")
})

test("api-v3 mock: OCR failure never reaches summary (FLOW-04)", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")

  const doc = await apiV3.uploadDocument(null, "scan-fail.jpg")
  assert.equal(doc.state, "failed")

  await assert.rejects(
    () => apiV3.getCaseSummary(),
    (e) => e.code === "SOURCE_NOT_READY",
  )
})

test("api-v3 mock: discard_document switches to without-document mode", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")
  await apiV3.uploadDocument(null, "资料.jpg")

  const session = await apiV3.discardDocument()
  assert.equal(session.input_mode, "without_document")
  assert.equal(session.active_document_id, null)
})

test("api-v3 mock: full questionnaire submission succeeds with 10 answers", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")

  const schema = await apiV3.getQuestionnaireSchema()
  assert.equal(schema.questions.length, 10, "questionnaire must have exactly 10 questions")
  const answers = {}
  schema.questions.forEach((q) => { answers[q.question_id] = ["none"] })
  const submission = await apiV3.submitQuestionnaire(answers)
  assert.ok(submission.questionnaire_submission_id)
  assert.equal(submission.schema_id, "questionnaire_v3")

  const assessment = await apiV3.createAssessment()
  assert.equal(assessment.status, "needs_confirmation")
})

test("api-v3 mock: confirmed assessment unlocks music basis and generation", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")
  await apiV3.uploadDocument(null, "资料.jpg")
  await apiV3.getCaseSummary()
  await apiV3.confirmUnderstanding({ expected_revision: 1, decision: "confirm", changes: [] })

  // 未确认时不能拿到依据（FLOW-08：Agent1 先评估、确认后才进入后续）
  await assert.rejects(() => apiV3.getMusicBasis())

  await apiV3.createAssessment()
  await apiV3.confirmAssessment({ expected_revision: 1, decision: "confirm", changes: [] })

  const basis = await apiV3.getMusicBasis()
  assert.ok(basis.tendency.disclaimer.includes("不构成医学诊断"))

  let task = await apiV3.startMusicGeneration()
  assert.ok(["queued", "running"].includes(task.status))
  // 轮询直到成功
  for (let i = 0; i < 6; i++) {
    task = await apiV3.pollMusicGeneration()
    if (task.status === "succeeded") break
  }
  assert.equal(task.status, "succeeded")

  const music = await apiV3.getMusic()
  assert.ok(music.stream_url, "player needs stream_url")
  assert.ok(music.disclaimer.includes("不能替代专业"))
})

test("api-v3 mock: revision conflict rejected on understanding confirm", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")
  await apiV3.uploadDocument(null, "资料.jpg")
  await apiV3.getCaseSummary()

  await assert.rejects(
    () => apiV3.confirmUnderstanding({ expected_revision: 99, decision: "confirm", changes: [] }),
    (e) => e.code === "REVISION_CONFLICT",
  )
})

// ===== Safety 暂缓兼容 =====

test("safety deferred_v3 policy never routes to safety pages (Amendment 6)", async () => {
  const { safetyDestination, isSafetyDeferred } = await import("../common/safety-flow.js")
  // V3 会话：即使带上旧风险状态字段也不分流（policy 权威）
  assert.equal(isSafetyDeferred({ safety_policy: "deferred_v3" }), true)
  assert.equal(
    safetyDestination({ safety_policy: "deferred_v3", safety_status: "confirmed_mental_health_risk" }),
    "",
    "deferred_v3 must not route to safety support",
  )
  // Sprint4 会话：不传 policy，原行为保留
  assert.equal(
    safetyDestination({ safety_status: "confirmed_mental_health_risk" }),
    "/pages/safety-support/safety-support",
    "legacy safety routing must be preserved",
  )
})
