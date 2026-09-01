/**
 * Sprint 5 V3 owner-flow-1 前端契约测试
 * 依据：docs/contracts/harmonyai-v3-owner-flow-amendment-001.md
 *      docs/contracts/frontend-read-model-contract-v3.md
 *      backend/app/schemas/v3/feedback.py（feedback_v3.0 冻结契约）
 *
 * 重要：mock 必须显式开启（HARMONYAI_V3_MODE=mock），默认 real。
 * 本文件在顶部显式设置 mock 后再动态 import api-v3.js。
 */
import assert from "node:assert/strict"
import { readFileSync, existsSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

// mock 必须显式开启：在首次 import api-v3.js 之前设置
process.env.HARMONYAI_V3_MODE = "mock"

const frontendRoot = resolve(import.meta.dirname, "..")
const pagesConfig = JSON.parse(readFileSync(resolve(frontendRoot, "pages.json"), "utf8"))
const routes = pagesConfig.pages.map((p) => p.path)

function readPage(name) {
  const file = resolve(frontendRoot, "pages", name)
  assert.ok(existsSync(file), `missing page file: ${name}`)
  return readFileSync(file, "utf8")
}

// 构造符合权威清单题型的答案（频率题 0-4 整数；多选题非空 option_code 数组）
function buildFullAnswers(schema) {
  const answers = {}
  schema.questions.forEach((q) => {
    if (q.answer_type === "frequency_0_4") {
      answers[q.question_id] = 2
    } else {
      answers[q.question_id] = [q.options[0].option_code]
    }
  })
  return answers
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
    "pages/v3-feedback/v3-feedback",
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

// ===== Owner Amendment 文案约束（Sprint 5 组长指令版本） =====

test("entry page uses the approved dual-entry wording", () => {
  const entry = readPage("entry/entry.vue")
  assert.ok(entry.includes("我有近期就诊资料"), "entry must use approved wording: with document")
  assert.ok(entry.includes("我没有近期就诊资料"), "entry must use approved wording: without document")
  assert.ok(!entry.includes("有近期材料"), "obsolete wording must not appear")
  assert.ok(!entry.includes("无近期材料"), "obsolete wording must not appear")
})

test("OCR failure page follows Amendment 3.1 + Sprint 5 wording", () => {
  const material = readPage("v3-material/v3-material.vue")
  assert.ok(material.includes("资料暂未识别成功"), "failure title")
  assert.ok(material.includes("重新上传资料"), "primary action")
  assert.ok(material.includes("暂不使用资料，通过描述和问卷继续"), "secondary action (Sprint 5 wording)")
  assert.ok(material.includes("自由描述可以跳过，10道状态问卷需要完成"), "side note")
  // 暂不使用资料必须调用后端 Input Transition（discard_document），不是前端隐藏
  assert.ok(material.includes("discardDocument"), "must call backend input transition")
  // 网络错误与 OCR 失败分流
  assert.ok(material.includes("network_error"), "must distinguish network error from OCR failure")
})

test("summary page exposes the four approved actions (Sprint 5 wording)", () => {
  const summary = readPage("v3-summary/v3-summary.vue")
  assert.ok(summary.includes("资料摘要基本无误"), "primary action")
  assert.ok(summary.includes("修改资料摘要"), "edit action")
  assert.ok(summary.includes("重新上传资料"), "reupload action")
  assert.ok(summary.includes("暂不使用这份资料，继续评估"), "discard action")
  assert.ok(summary.includes("保存修改并继续"), "editor save")
  assert.ok(summary.includes("取消修改"), "editor cancel")
  assert.ok(summary.includes("edited_summary_text"), "editor must submit edited_summary_text")
  assert.ok(summary.includes("reprocess_requested"), "editor must set reprocess_requested")
  assert.ok(summary.includes("discardDocument"), "discard must call backend input transition")
  // FACT_EXTRACTION_UNAVAILABLE 友好处理
  assert.ok(summary.includes("FACT_EXTRACTION_UNAVAILABLE"), "must handle FACT_EXTRACTION_UNAVAILABLE")
})

test("V3 pages do not leak internal fields to users", () => {
  for (const page of [
    "v3-material/v3-material.vue",
    "v3-summary/v3-summary.vue",
    "v3-confirm/v3-confirm.vue",
    "v3-basis/v3-basis.vue",
    "v3-player/v3-player.vue",
    "v3-feedback/v3-feedback.vue",
  ]) {
    const src = readPage(page)
    // 模板区域不得出现内部技术字段名
    const template = (src.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
    for (const forbidden of ["provider", "confidence", "revision", "target_id", "safety_policy", "evidence_coverage"]) {
      assert.ok(!template.includes(forbidden), `${page} template leaks internal field: ${forbidden}`)
    }
  }
})

// ===== PR #92 Review 修复回归（P0-1/P0-2/P0-3/P1-1/P1-2/P1-3） =====

test("P1-3: tabBar and feedback go-home route to V3 pages, never Sprint 3", () => {
  const tabs = pagesConfig.tabBar.list.map((t) => t.pagePath)
  assert.equal(tabs.length, 2, "tabBar keeps two items")
  assert.equal(tabs[0], "pages/entry/entry", "home tab must be the V3 entry page")
  assert.equal(tabs[1], "pages/v3-player/v3-player", "player tab must align with the V3 player entry")
  for (const legacy of ["pages/index/index", "pages/player/player"]) {
    assert.ok(!tabs.includes(legacy), `tabBar must not point to Sprint 3 page: ${legacy}`)
  }

  const feedback = readPage("v3-feedback/v3-feedback.vue")
  assert.ok(feedback.includes('"/pages/entry/entry"'), "feedback goHome must reLaunch to V3 entry")
  assert.ok(!feedback.includes("/pages/index/index"), "feedback must not route back to Sprint 3 home")

  // tab 页面入口必须使用合法导航方式（navigateTo/redirectTo 打不开 tab 页）
  const welcome = readPage("welcome/welcome.vue")
  assert.ok(welcome.includes("reLaunch"), "welcome must use reLaunch to open the tab page entry")
  const basis = readPage("v3-basis/v3-basis.vue")
  assert.ok(basis.includes("switchTab"), "basis must use switchTab to open the tab page v3-player")

  // Sprint 3 旧页面保留用于兼容（页面文件与路由不删）
  assert.ok(routes.includes("pages/index/index"), "legacy home page remains for compatibility")
  assert.ok(routes.includes("pages/player/player"), "legacy player page remains for compatibility")
})

test("P0-1: narrative voice input never fabricates transcripts outside explicit mock", () => {
  const src = readPage("v3-narrative/v3-narrative.vue")
  // 语音入口按显式 mock 模式分流：INPUT_SIMULATED 才提供模拟转写
  assert.ok(src.includes("voiceSimulated: apiV3.INPUT_SIMULATED"), "voice must be gated by explicit mock mode")
  assert.ok(src.includes('v-if="voiceSimulated"'), "recording UI must be inside the simulated branch")
  assert.ok(src.includes("语音描述暂不可用"), "non-mock mode must show voice-unavailable notice")
  // 模拟转写必须标注演示数据，不得伪装成真实 ASR 结果
  assert.ok(src.includes("演示数据"), "simulated transcript must be labeled as demo data")
})

test("P1-1: with-document narrative keeps honest local-save wording (backend gap)", () => {
  const src = readPage("v3-narrative/v3-narrative.vue")
  assert.ok(
    src.includes("保存在本机"),
    "with-document path must tell users the text is saved locally (append-source is a backend gap)",
  )
  // 本机暂存提示只能出现在有资料路径（无资料路径为真实提交，不得使用暂存话术）
  assert.ok(
    /v-if="!voiceSimulated && withDocument"/.test(src),
    "local-save note must be scoped to the with-document path",
  )
})

test("narrative real submission: without-document path submits on continue (Sprint 5 review fix)", () => {
  const src = readPage("v3-narrative/v3-narrative.vue")
  // 无资料路径必须调用真实提交（narrative 源 → Understanding → 确认绑定会话）
  assert.ok(src.includes("apiV3.submitNarrative"), "narrative page must call the real submission API")
  // 提交失败必须如实报错并停留本页（不静默当作已提交）
  assert.ok(src.includes("提交失败"), "submission failure must surface an honest error and stay on page")
  // API 层必须存在真实提交实现（POST /api/v3/understandings + narrative inline text + confirm）
  const apiSrc = readFileSync(resolve(frontendRoot, "common/api-v3.js"), "utf8")
  assert.ok(
    /async submitNarrative[\s\S]*?source_type: "narrative"[\s\S]*?decision: "confirm"/.test(apiSrc),
    "api-v3 must implement real narrative submission (create + auto-confirm)",
  )
  // 有资料路径后端缺口必须如实报错，不把本机暂存伪装成已提交
  assert.ok(
    apiSrc.includes("NARRATIVE_APPEND_UNSUPPORTED"),
    "with-document append must fail honestly instead of faking submission",
  )
})

test("api-v3 mock: without-document narrative submission creates and binds an understanding", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")

  const und = await apiV3.submitNarrative("最近两周入睡偏慢，白天容易疲惫。")
  assert.ok(und.understanding_id, "narrative submission returns an understanding")
  const session = await apiV3.getSession()
  assert.ok(session.understanding_ref, "confirmed narrative binds the session understanding ref")
  assert.equal(session.understanding_ref.understanding_id, und.understanding_id)

  // 有资料路径：后端暂不支持向已确认摘要追加描述源 → 如实报错
  await apiV3.__resetForTest()
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("with_document")
  await apiV3.uploadDocument(null, "资料.jpg")
  await assert.rejects(
    () => apiV3.submitNarrative("补充描述"),
    (e) => e.code === "NARRATIVE_APPEND_UNSUPPORTED",
  )
})

test("P0-3: backend audio streams are fetched with auth headers before playback", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  // 本地/直链资源不需要鉴权，原样返回
  assert.equal(await apiV3.fetchAuthorizedAudio("/static/demo.mp3"), "/static/demo.mp3")
  // 后端流地址必须走带鉴权的下载通道；无下载通道时如实报错，不降级为无鉴权直连
  await assert.rejects(
    () => apiV3.fetchAuthorizedAudio("/api/v3/music/assets/m_1/stream"),
    (e) => e.code === "NETWORK_ERROR" || e.code === "AUDIO_FETCH_FAILED",
    "backend stream must go through the authorized fetch path",
  )
  // 播放页必须经授权拉取后再播放（audio 标签无法携带 Bearer 头）
  const player = readPage("v3-player/v3-player.vue")
  assert.ok(player.includes("fetchAuthorizedAudio"), "player must play audio via authorized fetch")
  const apiSrc = readFileSync(resolve(frontendRoot, "common/api-v3.js"), "utf8")
  assert.ok(apiSrc.includes("downloadFile"), "authorized fetch must use downloadFile")
  assert.ok(
    /header:\s*authHeaders\(\)/.test(apiSrc),
    "authorized fetch must attach auth headers",
  )
})

test("P0-2: upload failures still offer the describe-and-questionnaire path", () => {
  const material = readPage("v3-material/v3-material.vue")
  // network_error 分支必须提供"暂不使用资料"出口（不能只有重试，避免用户被卡死）
  const networkCard = (material.match(/state === 'network_error'[\s\S]*?<\/view>\s*<\/view>/) || [""])[0]
  assert.ok(
    networkCard.includes("暂不使用资料，通过描述和问卷继续"),
    "network error card must also offer the continue-without-material action",
  )
  assert.ok(
    networkCard.includes("switchToQuestionnaire"),
    "the action must call the backend input transition",
  )
})

test("P1-2: V3 pages and API errors use stable user copy without internal dev info", () => {
  for (const page of [
    "entry/entry.vue",
    "v3-material/v3-material.vue",
    "v3-summary/v3-summary.vue",
    "v3-narrative/v3-narrative.vue",
    "v3-questionnaire/v3-questionnaire.vue",
    "v3-confirm/v3-confirm.vue",
    "v3-basis/v3-basis.vue",
    "v3-player/v3-player.vue",
    "v3-feedback/v3-feedback.vue",
  ]) {
    const src = readPage(page)
    const template = (src.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
    for (const forbidden of [
      "PR #", "尚未合并", "待补齐", "真实接口模式", "Agent 服务", "Agent1", "Agent2", "prescription",
    ]) {
      assert.ok(!template.includes(forbidden), `${page} template leaks internal dev info: ${forbidden}`)
    }
    // Sprint 5 复审追加：整个源文件（含注释）也不得携带内部开发术语
    for (const forbidden of ["PR #", "Agent1", "Agent2", "prescription", "尚未合并", "待补齐"]) {
      assert.ok(!src.includes(forbidden), `${page} source leaks internal dev info: ${forbidden}`)
    }
  }
  // API 层用户可见错误文案同样不泄漏内部开发信息
  const apiSrc = readFileSync(resolve(frontendRoot, "common/api-v3.js"), "utf8")
  assert.ok(!apiSrc.includes("后端访客上传接口待补齐"), "friendly errors must not leak backend status")
  assert.ok(!/agentPendingError[\s\S]{0,200}尚未合并/.test(apiSrc), "AGENT_PENDING copy must not mention PR state")
  // Sprint 5 复审追加：api-v3.js 源码不得引用内部开发术语
  // （prescription_id 为后端 Read Model §10 契约字段名，出现在 mock 数据中属合法，不在扫描之列）
  for (const forbidden of ["PR #", "Agent1", "Agent2", "尚未合并", "待补齐"]) {
    assert.ok(!apiSrc.includes(forbidden), `api-v3.js source leaks internal dev info: ${forbidden}`)
  }
  // 权威清单模块同样不携带 PR 引用
  const manifestSrc = readFileSync(resolve(frontendRoot, "common/questionnaire-v3-manifest.js"), "utf8")
  assert.ok(!manifestSrc.includes("PR #"), "manifest must not reference PR numbers")
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
    "v3-feedback/v3-feedback.vue",
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

test("player only renders backend-provided asset, wires favorites and V3 feedback", () => {
  const player = readPage("v3-player/v3-player.vue")
  assert.ok(player.includes("stream_url"), "player must use backend stream_url")
  assert.ok(player.includes("musicStreamUrl"), "player must resolve stream url via api")
  assert.ok(player.includes("source_label"), "player must show source label from backend")
  assert.ok(player.includes("music.disclaimer"), "player must render backend disclaimer text")
  assert.ok(player.includes("addFavorite"), "favorites must use backend API")
  assert.ok(player.includes("/pages/v3-feedback/v3-feedback"), "feedback entry must route to V3 feedback page")
  assert.ok(!player.includes("/pages/feedback-v2/feedback-v2"), "V3 flow must not reuse V2 feedback page")
})

// ===== V3 反馈页（feedback_v3.0） =====

test("feedback page: required 2x2 change cards with deep-green selected state", () => {
  const feedback = readPage("v3-feedback/v3-feedback.vue")
  // 2×2 必填状态变化卡片：四个 change label
  for (const label of ["much_better", "slightly_better", "no_change", "worse"]) {
    assert.ok(feedback.includes(label), `feedback must include change label: ${label}`)
  }
  // 深绿色选中态（#2f5d43）+ 白字 + ✓
  assert.ok(feedback.includes("#2f5d43"), "selected state must use deep green")
  assert.ok(feedback.includes("change-card-active"), "change cards need active state")
  assert.ok(feedback.includes("change-label-active"), "active label must turn white")
  assert.ok(feedback.includes("change-check"), "active card must show check mark")
  // 必填标识
  assert.ok(feedback.includes("必填"), "change selection must be marked required")
  assert.ok(feedback.includes("post_state"), "must submit post_state.change_label")
})

test("feedback page: mutex adjustment groups match backend contract", () => {
  const feedback = readPage("v3-feedback/v3-feedback.vue")
  // 后端 FeedbackV3 校验的互斥对
  assert.ok(feedback.includes('["slower_tempo", "faster_tempo"]'), "tempo mutex group")
  assert.ok(feedback.includes('["shorter_duration", "longer_duration"]'), "duration mutex group")
  assert.ok(feedback.includes("MUTEX_GROUPS"), "mutex groups defined")
  // 调整项全集与后端 AdjustmentPreference 一致
  for (const adj of [
    "slower_tempo",
    "faster_tempo",
    "change_instruments",
    "adjust_volume",
    "adjust_ambient",
    "shorter_duration",
    "longer_duration",
  ]) {
    assert.ok(feedback.includes(`"${adj}"`), `feedback must include adjustment option: ${adj}`)
  }
  assert.ok(feedback.includes("adjustment_preferences"), "must submit adjustment_preferences")
  assert.ok(feedback.includes("continue_use"), "must submit continue_use")
  assert.ok(feedback.includes("liked_features"), "must submit liked_features")
})

// ===== 问卷题型（权威清单） =====

test("questionnaire page renders frequency questions from the canonical manifest", () => {
  const page = readPage("v3-questionnaire/v3-questionnaire.vue")
  assert.ok(page.includes("FREQUENCY_OPTIONS"), "page must import FREQUENCY_OPTIONS")
  assert.ok(page.includes("frequency_0_4"), "page must branch on frequency question type")
  assert.ok(page.includes("answer_type"), "page must dispatch by answer_type")
})

test("manifest matches the authoritative questionnaire structure", async () => {
  const { apiV3, FREQUENCY_OPTIONS } = await import("../common/api-v3.js")
  const schema = await apiV3.getQuestionnaireSchema()
  assert.equal(schema.questions.length, 10)
  const freq = schema.questions.filter((q) => q.answer_type === "frequency_0_4")
  const multi = schema.questions.filter((q) => q.answer_type === "multi_choice_evidence")
  assert.equal(freq.length, 5, "q01-q05 are frequency questions")
  assert.equal(multi.length, 5, "q06-q10 are multi-choice questions")
  assert.equal(FREQUENCY_OPTIONS.length, 5, "5 frequency labels (0..4)")
  assert.ok(schema.content_checksum, "manifest checksum required")
  assert.equal(schema.schema_id, "questionnaire_v3")
})

// ===== api-v3 mock 状态机行为（显式 mock 模式） =====

test("api-v3 mock: without-document flow requires full questionnaire", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  assert.equal(apiV3.MODE, "mock", "mock must be explicitly enabled via env")
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

test("api-v3 mock: frequency answers validate by type (frequency=number, multi=array)", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")

  // 频率题传数组必须被拒绝
  const bad = {}
  const schema = await apiV3.getQuestionnaireSchema()
  schema.questions.forEach((q) => {
    bad[q.question_id] = q.answer_type === "frequency_0_4" ? [0] : ["x"]
  })
  await assert.rejects(
    () => apiV3.submitQuestionnaire(bad),
    (e) => e.code === "QUESTIONNAIRE_INCOMPLETE",
  )
})

test("api-v3 mock: full questionnaire submission succeeds with typed answers", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  await apiV3.selectMode("without_document")

  const schema = await apiV3.getQuestionnaireSchema()
  assert.equal(schema.questions.length, 10, "questionnaire must have exactly 10 questions")
  const answers = buildFullAnswers(schema)
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
  assert.ok(music.music_ref && music.music_ref.music_id, "favorites need music_ref.music_id")
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

test("api-v3 mock: feedback submission accepts feedback_v3.0 payload", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  const result = await apiV3.submitFeedback({
    post_state: { change_label: "slightly_better" },
    continue_use: "maybe",
    liked_features: ["melody"],
    adjustment_preferences: ["slower_tempo", "longer_duration"],
  })
  assert.ok(result)
})

// ===== real 模式网关（默认模式：Agent 段 AGENT_PENDING，不伪造） =====

test("api-v3 real mode (default): agent functions return AGENT_PENDING without faking", async () => {
  // 清除显式 mock 设置，用缓存穿透 query 导入独立实例
  const prev = process.env.HARMONYAI_V3_MODE
  delete process.env.HARMONYAI_V3_MODE
  try {
    const { apiV3 } = await import("../common/api-v3.js?mode=real")
    assert.equal(apiV3.MODE, "real", "default mode must be real (mock requires explicit opt-in)")
    assert.equal(apiV3.AGENT_SIMULATED, false, "real mode must not claim simulated data")
    assert.equal(apiV3.INPUT_SIMULATED, false, "real mode must not simulate input (voice transcript)")

    // 智能化能力（后端尚未交付）：明确等待状态
    for (const fn of ["submitQuestionnaire", "createAssessment", "getAssessment", "getMusicBasis"]) {
      await assert.rejects(
        () => apiV3[fn](),
        (e) => e.code === "AGENT_PENDING" && e.agentPending === true && !e.message.includes("PR"),
        `${fn} must reject with AGENT_PENDING (stable user copy) in real mode`,
      )
    }
    await assert.rejects(
      () => apiV3.startMusicGeneration(),
      (e) => e.code === "AGENT_PENDING",
      "music generation depends on the syndrome-analysis capability (not yet delivered)",
    )
  } finally {
    process.env.HARMONYAI_V3_MODE = prev
  }
})

test("api-v3 real mode: guest auth and session creation use real endpoints", async () => {
  const prev = process.env.HARMONYAI_V3_MODE
  delete process.env.HARMONYAI_V3_MODE
  try {
    const { apiV3 } = await import("../common/api-v3.js?mode=real-endpoints")
    // 无后端运行时应抛网络错误，而不是静默返回 mock 数据
    await assert.rejects(() => apiV3.guestAuth(), (e) => e.code === "NETWORK_ERROR" || e.code === "REQUEST_FAILED")
  } finally {
    process.env.HARMONYAI_V3_MODE = prev
  }
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
