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
import * as healingIntent from "../common/v3-healing-intent.js"
import {
  INTENT_CODES,
  MAX_CUSTOM_LEN,
  HEALING_INTENT_REASON_MESSAGE,
} from "../common/v3-healing-intent.js"

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
    "pages/v3-material-error/v3-material-error",
    "pages/v3-summary/v3-summary",
    "pages/v3-supplement/v3-supplement",
    "pages/v3-narrative/v3-narrative",
    "pages/v3-questionnaire/v3-questionnaire",
    "pages/v3-goal/v3-goal",
    "pages/v3-confirm/v3-confirm",
    "pages/v3-basis/v3-basis",
    "pages/v3-player/v3-player",
    "pages/v3-feedback/v3-feedback",
  ]
  for (const route of v3Routes) {
    assert.ok(routes.includes(route), `missing V3 route: ${route}`)
    assert.ok(existsSync(resolve(frontendRoot, `${route}.vue`)), `missing V3 page: ${route}`)
  }
  // Issue #100：entry 是启动首页（见 pages[0]）
  assert.equal(routes[0], "pages/entry/entry", "entry must be the launch home page")
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

test("V3.1: material page uploads 1-3 files; OCR failure routes to the standalone error page", () => {
  const material = readPage("v3-material/v3-material.vue")
  // Issue #100: 多文件（1~3 张）上传
  assert.ok(material.includes("count: remain"), "must allow adding up to the remaining slots")
  assert.ok(material.includes("MAX_FILES = 3"), "must cap the selection at 3 files")
  assert.ok(material.includes("removeFile"), "each thumbnail must be removable")
  assert.ok(material.includes("识别并继续"), "bulk upload action")
  // 失败不再内嵌本页，统一跳独立异常页
  assert.ok(
    material.includes('/pages/v3-material-error/v3-material-error?type=ocr'),
    "OCR failure must redirect to the standalone error page",
  )
  assert.ok(
    material.includes('/pages/v3-material-error/v3-material-error?type=network'),
    "network failure must redirect to the standalone error page",
  )
})

test("OCR failure page (v3-material-error) follows Amendment 3.1 + Sprint 5 wording", () => {
  const errPage = readPage("v3-material-error/v3-material-error.vue")
  assert.ok(errPage.includes("资料暂未识别成功"), "failure title")
  assert.ok(errPage.includes("重新上传资料"), "primary action")
  assert.ok(errPage.includes("暂不使用资料，通过描述和问卷继续"), "secondary action (Sprint 5 wording)")
  assert.ok(errPage.includes("描述可以跳过，状态问卷需要完成"), "side note")
  // 暂不使用资料必须调用后端 Input Transition（discard_document），不是前端隐藏
  assert.ok(errPage.includes("discardDocument"), "must call backend input transition")
  // 网络错误与 OCR 失败分流（?type=network）
  assert.ok(errPage.includes('query.type === "network"'), "must distinguish network error from OCR failure")
  // 原内嵌失败卡片已从 material 页移除
  const material = readPage("v3-material/v3-material.vue")
  assert.ok(!material.includes("资料暂未识别成功"), "failure copy must live on the error page, not material")
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
    "v3-material-error/v3-material-error.vue",
    "v3-summary/v3-summary.vue",
    "v3-supplement/v3-supplement.vue",
    "v3-goal/v3-goal.vue",
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
  // V3.1：网络/OCR 失败收敛到独立异常页，出口同样提供"不用资料继续"，避免用户被卡死
  const errPage = readPage("v3-material-error/v3-material-error.vue")
  assert.ok(
    errPage.includes("暂不使用资料，通过描述和问卷继续"),
    "error page must offer the continue-without-material action",
  )
  assert.ok(
    errPage.includes("switchToQuestionnaire"),
    "the action must call the backend input transition",
  )
  assert.ok(errPage.includes("discardDocument"), "must call discard_document transition")
  assert.ok(errPage.includes("retry"), "error page must offer a retry/back-to-upload entry")
})

test("P1-2: V3 pages and API errors use stable user copy without internal dev info", () => {
  for (const page of [
    "entry/entry.vue",
    "v3-material/v3-material.vue",
    "v3-material-error/v3-material-error.vue",
    "v3-summary/v3-summary.vue",
    "v3-supplement/v3-supplement.vue",
    "v3-goal/v3-goal.vue",
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
    "v3-material-error/v3-material-error.vue",
    "v3-summary/v3-summary.vue",
    "v3-supplement/v3-supplement.vue",
    "v3-goal/v3-goal.vue",
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

test("V3.1: final confirm is titled 完成近期状态总结 and sits after optional goal page", () => {
  const confirm = readPage("v3-confirm/v3-confirm.vue")
  assert.ok(confirm.includes("完成近期状态总结"), "Issue #100: confirm page title")
  // 问卷页评估创建完成后（答完 10 题路径）先进入疗愈诉求（选填），再到最终确认
  const questionnaire = readPage("v3-questionnaire/v3-questionnaire.vue")
  assert.ok(questionnaire.includes('"/pages/v3-goal/v3-goal"'), "questionnaire must route to goal page")
  const goal = readPage("v3-goal/v3-goal.vue")
  assert.ok(goal.includes('"/pages/v3-confirm/v3-confirm"'), "goal page must route to the final confirm")
})

test("V3.1: with-document skip in questionnaire bypasses goal and lands on confirm", () => {
  // 复审修订：有资料用户**跳过**问卷时，直接进入"完成近期状态总结"（v3-confirm），
  // 不经过疗愈诉求（v3-goal）。无资料用户这条分支走不到（required 守卫 + skip-row
  // 仅在 !required 时渲染）。
  const questionnaire = readPage("v3-questionnaire/v3-questionnaire.vue")
  // skip 的"继续"路径必须包含 v3-confirm
  assert.ok(
    questionnaire.includes('"/pages/v3-confirm/v3-confirm"'),
    "skip path must land on v3-confirm",
  )
  // 提取 skip() 函数体，单独断言其内 redirectTo 目标
  const m = questionnaire.match(/async skip\(\)\s*\{[\s\S]*?\n\s{4}\}/)
  assert.ok(m, "skip() method must exist in v3-questionnaire")
  const skipBody = m[0]
  assert.ok(skipBody.includes("/pages/v3-confirm/v3-confirm"), "skip() must redirect to v3-confirm")
  assert.ok(
    !skipBody.includes("/pages/v3-goal/v3-goal"),
    "skip() must not route to v3-goal",
  )
  // 守卫：required 或 submitting 时 skip 立即返回
  assert.match(
    skipBody,
    /if\s*\(this\.required\s*\|\|\s*this\.submitting\)\s*return/,
    "skip() must guard against required or in-flight state",
  )
})

test("V3.1: questionnaire required comes from authoritative session, not stale cache", () => {
  // 复审修订：必填性必须读当前权威 Session，防止 schema.required_for_flow / 本地缓存 /
  // 上一个会话的选项误判当前 10 题。
  const questionnaire = readPage("v3-questionnaire/v3-questionnaire.vue")
  assert.match(
    questionnaire,
    /apiV3\.getSession\(\)/,
    "load() must call apiV3.getSession()",
  )
  assert.match(
    questionnaire,
    /session\.input_mode\s*!==\s*["']with_document["']/,
    "required must be derived from session.input_mode",
  )
  assert.ok(
    !/this\.required\s*=\s*!!this\.schema\.required_for_flow/.test(questionnaire),
    "schema.required_for_flow must no longer be the source of truth",
  )
})

test("V3.1: goal page is an optional healing-intent page without removed goal concepts", () => {
  const goal = readPage("v3-goal/v3-goal.vue")
  assert.ok(goal.includes("疗愈诉求"), "page title")
  assert.ok(goal.includes("主要诉求"), "primary intent section")
  assert.ok(goal.includes("次要诉求"), "secondary intent section")
  assert.ok(goal.includes("选填"), "must be marked optional")
  assert.ok(goal.includes("submitHealingIntent"), "must persist via api submitHealingIntent")
  assert.ok(goal.includes("skip"), "must allow skipping the whole step")
  // 复审：校验逻辑集中在 common/v3-healing-intent.js，.vue 不再硬编码校验字符串
  assert.ok(goal.includes("decideHealingIntent"), "must delegate validation to decideHealingIntent")
  assert.ok(goal.includes("INTENT_CODES"), "must import INTENT_CODES from validation module")
  // 不再使用旧字段名 primary / secondary / custom 作为最终字段（data 字段已对齐合同）
  assert.ok(goal.includes("primary_goal:"), "data must use primary_goal")
  assert.ok(goal.includes("secondary_goal:"), "data must use secondary_goal")
  assert.ok(goal.includes("custom_goal_text:"), "data must use custom_goal_text")
  // 复审修订：意图代码与 Read Model 合同权威枚举对齐（现在集中在校验模块）
  for (const code of ["sleep", "relaxation", "emotion_regulation", "focus", "energy", "stress_relief", "other"]) {
    assert.ok(INTENT_CODES.some((it) => it.code === code), `intent module must declare canonical code: ${code}`)
  }
  for (const legacy of ["relax", "soothe", "lift_mood"]) {
    assert.ok(!INTENT_CODES.some((it) => it.code === legacy), `intent module must not reuse removed code: ${legacy}`)
  }
  // 200 字补充输入上限
  assert.ok(goal.includes("maxlength=\"200\""), "supplement text must cap at 200 chars")
  assert.equal(MAX_CUSTOM_LEN, 200, "MAX_CUSTOM_LEN must be 200 in validation module")
})

test("api-v3 mock: healing intent is stored without fabricating defaults", async () => {
  const { apiV3 } = await import("../common/api-v3.js")
  await apiV3.guestAuth()
  await apiV3.createSession()
  // 复审：payload 字段对齐 Read Model §10（primary_goal / secondary_goal / custom_goal_text）
  const res = await apiV3.submitHealingIntent({ primary_goal: "sleep", secondary_goal: null, custom_goal_text: null })
  assert.equal(res.received, true)
  // 未选择时提交 null 等同跳过，不产生记录
  const skipped = await apiV3.submitHealingIntent(null)
  assert.equal(skipped.saved_locally, false)
})

// ===== 疗愈诉求合同校验（Issue #100 复审指令 1~8） =====

test("V3.1 review: 疗愈诉求合同校验 - 全空允许整页跳过", () => {
  const { decideHealingIntent } = healingIntent
  const d = decideHealingIntent({ primary_goal: null, secondary_goal: null, custom_goal_text: "" })
  assert.equal(d.ok, true, "全空应当 ok")
  assert.equal(d.skip, true, "全空应当 skip = true（整页跳过）")
  assert.equal(d.payload, null, "全空 payload 为 null")
  assert.equal(d.reason, null, "全空无 reason")
})

test("V3.1 review: 疗愈诉求合同校验 - 只填文字、不选主要诉求 → 阻止", () => {
  const { decideHealingIntent } = healingIntent
  const d = decideHealingIntent({ primary_goal: null, secondary_goal: null, custom_goal_text: "希望更舒缓一些" })
  assert.equal(d.ok, false, "仅文字必须阻止")
  assert.equal(d.reason, "primary_required", "reason 必须是 primary_required")
})

test("V3.1 review: 疗愈诉求合同校验 - 选择 other 但文字为空 → 阻止", () => {
  const { decideHealingIntent } = healingIntent
  const d = decideHealingIntent({ primary_goal: "other", secondary_goal: null, custom_goal_text: "" })
  assert.equal(d.ok, false, "other + 空文字必须阻止")
  assert.equal(d.reason, "other_needs_text", "reason 必须是 other_needs_text")
})

test("V3.1 review: 疗愈诉求合同校验 - other + 合法文字 → 通过", () => {
  const { decideHealingIntent } = healingIntent
  const d = decideHealingIntent({
    primary_goal: "other",
    secondary_goal: null,
    custom_goal_text: "希望节奏更慢一些，像清晨山雾那种感觉",
  })
  assert.equal(d.ok, true, "other + 合法文字必须通过")
  assert.equal(d.skip, false)
  assert.equal(d.reason, null)
  assert.equal(d.payload.primary_goal, "other")
  assert.equal(typeof d.payload.custom_goal_text, "string")
  assert.ok(d.payload.custom_goal_text.length > 0)
})

test("V3.1 review: 疗愈诉求合同校验 - 只有次要诉求、没有主要诉求 → 阻止", () => {
  const { decideHealingIntent } = healingIntent
  const d = decideHealingIntent({ primary_goal: null, secondary_goal: "relaxation", custom_goal_text: "" })
  assert.equal(d.ok, false, "无主诉求必须阻止")
  assert.equal(d.reason, "primary_required", "reason 必须是 primary_required")
})

test("V3.1 review: 疗愈诉求合同校验 - 普通主要/次要诉求 → 正常通过", () => {
  const { decideHealingIntent } = healingIntent
  const d = decideHealingIntent({
    primary_goal: "sleep",
    secondary_goal: "stress_relief",
    custom_goal_text: null,
  })
  assert.equal(d.ok, true)
  assert.equal(d.skip, false)
  assert.equal(d.payload.primary_goal, "sleep")
  assert.equal(d.payload.secondary_goal, "stress_relief")
  assert.equal(d.payload.custom_goal_text, null)
})

test("V3.1 review: 疗愈诉求合同校验 - 自由文字超过 200 字 → 阻止", () => {
  const { decideHealingIntent, MAX_CUSTOM_LEN } = healingIntent
  // 构造恰好 201 字（maxlength=200 是物理限制，JS 校验兜底拦 201）
  const longText = "舒".repeat(MAX_CUSTOM_LEN + 1)
  assert.equal(longText.length, MAX_CUSTOM_LEN + 1, "测试数据必须 > 200 字")
  const d = decideHealingIntent({
    primary_goal: "relaxation",
    secondary_goal: null,
    custom_goal_text: longText,
  })
  assert.equal(d.ok, false, "超长文字必须阻止")
  assert.equal(d.reason, "custom_too_long", "reason 必须是 custom_too_long")
})

test("V3.1 review: 疗愈诉求合同校验 - 边界：恰好 200 字 → 通过", () => {
  const { decideHealingIntent, MAX_CUSTOM_LEN } = healingIntent
  const exactText = "舒".repeat(MAX_CUSTOM_LEN)
  assert.equal(exactText.length, 200, "边界值必须正好 200 字")
  const d = decideHealingIntent({
    primary_goal: "relaxation",
    secondary_goal: null,
    custom_goal_text: exactText,
  })
  assert.equal(d.ok, true, "200 字边界值必须通过")
})

test("V3.1 review: 疗愈诉求合同校验 - 防御 secondary === primary → 阻止", () => {
  const { decideHealingIntent } = healingIntent
  // pickSecondary 已拦截，但校验模块做兜底防御
  const d = decideHealingIntent({
    primary_goal: "sleep",
    secondary_goal: "sleep",
    custom_goal_text: null,
  })
  assert.equal(d.ok, false, "secondary 与 primary 同值必须阻止")
  assert.equal(d.reason, "primary_required")
})

test("V3.1 review: 疗愈诉求合同校验 - serialize 字段名对齐合同", () => {
  const { serializeHealingIntent } = healingIntent
  const out = serializeHealingIntent({
    primary_goal: "sleep",
    secondary_goal: "relaxation",
    custom_goal_text: "  abc  ",
  })
  // 必须使用合同权威字段名
  assert.ok("primary_goal" in out, "必须含 primary_goal 字段")
  assert.ok("secondary_goal" in out, "必须含 secondary_goal 字段")
  assert.ok("custom_goal_text" in out, "必须含 custom_goal_text 字段")
  // 不得出现已弃用字段
  assert.ok(!("primary" in out), "不得出现已弃用字段 primary")
  assert.ok(!("secondary" in out), "不得出现已弃用字段 secondary")
  assert.ok(!("custom_text" in out), "不得出现已弃用字段 custom_text")
  // 自定义文本应被 trim
  assert.equal(out.custom_goal_text, "abc", "custom_goal_text 应 trim 首尾空白")
})

test("V3.1 review: v3-goal.vue 不再使用已弃用字段名 primary/secondary/custom_text 作为最终提交", () => {
  const goal = readPage("v3-goal/v3-goal.vue")
  // data 必须使用合同权威字段名
  assert.ok(goal.includes("primary_goal:"), "data 中必须声明 primary_goal 字段")
  assert.ok(goal.includes("secondary_goal:"), "data 中必须声明 secondary_goal 字段")
  assert.ok(goal.includes("custom_goal_text:"), "data 中必须声明 custom_goal_text 字段")
  // next() 中调用校验模块
  assert.ok(goal.includes("decideHealingIntent"), "next() 必须走校验模块 decideHealingIntent")
  assert.ok(goal.includes("HEALING_INTENT_REASON_MESSAGE"), "toast 提示必须使用 reason 文案映射")
  // 不再使用旧字段名作为最终提交字段
  assert.ok(!goal.includes("primary: this.primary"), "不应再使用 primary: this.primary")
  assert.ok(!goal.includes("secondary: this.secondary"), "不应再使用 secondary: this.secondary")
  assert.ok(!goal.includes("custom_text: this."), "不应再使用 custom_text: this.xxx")
  // 校验逻辑（reason 字符串集中在 common/v3-healing-intent.js，.vue 通过 HEALING_INTENT_REASON_MESSAGE 映射）
  assert.ok(HEALING_INTENT_REASON_MESSAGE.primary_required, "reason 文案映射必须含 primary_required")
  assert.ok(HEALING_INTENT_REASON_MESSAGE.other_needs_text, "reason 文案映射必须含 other_needs_text")
  assert.ok(HEALING_INTENT_REASON_MESSAGE.custom_too_long, "reason 文案映射必须含 custom_too_long")
})

test("V3.1: basis page is 五音调适解析 without a Generation Complete stopover", () => {
  const basis = readPage("v3-basis/v3-basis.vue")
  // Issue #100：依据页升级为"五音调适解析"，随近期状态总结生成解析与方案
  assert.ok(basis.includes("五音调适解析"), "Issue #100: page title must be 五音调适解析")
  assert.ok(basis.includes("生成本次调适的解析与方案"), "subtitle must frame generation output")
  // 生成成功后直接进入播放器，删除独立"生成完成"中间步骤
  assert.ok(basis.includes("goPlayer()"), "must still have the goPlayer method")
  assert.ok(basis.includes("switchTab"), "must keep switchTab to open tab page v3-player")
  const template = (basis.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
  assert.ok(!template.includes("生成完成"), "template must not show a Generation Complete stopover")
  assert.ok(!template.includes("done-card") && !template.includes("done-icon"), "done card markup removed")
  assert.ok(!template.includes('phase === "done"') && !basis.includes("phase === 'done'"), "done phase removed")
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

test("V3.1: player footer offers feedback vs end-session as an explicit choice", () => {
  const player = readPage("v3-player/v3-player.vue")
  // Issue #100：底部二选一 —— 反馈本次体验 / 结束本次聆听
  assert.ok(player.includes("反馈本次体验"), "primary footer action must label feedback")
  assert.ok(player.includes("结束本次聆听"), "secondary footer action must offer ending the session")
  assert.ok(player.includes("exitSession"), "end-session must be implemented in methods")
  // 结束本次聆听不留在页内，而是退出主流程回到入口
  assert.ok(player.includes('url: "/pages/entry/entry"'), "exit must relaunch back to entry home")
  assert.ok(player.includes("reLaunch"), "exit must use reLaunch (tab page escape)")
  assert.ok(player.includes("stopAudio"), "exit must stop playback before leaving")
})

// ===== V3 反馈页（feedback_v3.0） =====

test("feedback page: optional 2x2 change cards with deep-green selected state (V3.1)", () => {
  const feedback = readPage("v3-feedback/v3-feedback.vue")
  const template = (feedback.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
  // 2×2 状态变化卡片：四个 change label
  for (const label of ["much_better", "slightly_better", "no_change", "worse"]) {
    assert.ok(feedback.includes(label), `feedback must include change label: ${label}`)
  }
  // 深绿色选中态（#2f5d43）+ 白字 + ✓
  assert.ok(feedback.includes("#2f5d43"), "selected state must use deep green")
  assert.ok(feedback.includes("change-card-active"), "change cards need active state")
  assert.ok(feedback.includes("change-label-active"), "active label must turn white")
  assert.ok(feedback.includes("change-check"), "active card must show check mark")
  // Issue #100：反馈改为选填，允许一条不填直接提交或跳过（校验用户可见文案）
  assert.ok(feedback.includes("选填"), "feedback must be marked optional")
  assert.ok(template.includes("暂不反馈，返回首页"), "must offer skipping feedback to home")
  assert.ok(!template.includes("必填"), "change selection must no longer be required (user copy)")
  assert.ok(feedback.includes("post_state"), "must submit post_state")
  assert.ok(feedback.includes("change_label"), "must include change_label field")
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

test("V3.1: questionnaire is paginated 5 pages x 2 questions with step progress", () => {
  const page = readPage("v3-questionnaire/v3-questionnaire.vue")
  // Issue #100：10 题拆 5 页，每页 2 题
  assert.ok(page.includes("PAGE_SIZE = 2"), "page must define PAGE_SIZE = 2")
  assert.ok(page.includes("pageQuestions"), "page must derive the current 2-question slice")
  assert.ok(page.includes("totalSteps"), "page must compute total steps (5)")
  assert.ok(page.includes("pageAnswered"), "page must gate on both questions answered")
  // 进度以页为单位 1/5 ~ 5/5
  assert.ok(page.includes("第 {{ current + 1 }} / {{ totalSteps }} 页"), "progress must show step x / 5")
  // 分页导航文案
  assert.ok(page.includes("上一页"), "pagination must offer prev-page")
  assert.ok(page.includes("下一页"), "pagination must offer next-page")
  // 一次作答收集，仍提交全部 10 题（answers 对象贯穿所有页）
  assert.ok(page.includes("submitQuestionnaire(this.answers)"), "submit must send the whole answer set once")
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

// ===== Issue #100 复审修订 P8 剩余：依赖注记 + 多资料/补充近况依赖边界 =====

test("V3.1: material page documents the multi-document ownership dependency without restoring legacy required rule", () => {
  // 复审要求：与蔡子鑫对齐 DocumentSet/API **不擅自调用聚合端点**；本页头部必须明确记录该依赖
  const material = readPage("v3-material/v3-material.vue")
  assert.match(
    material,
    /DocumentSet/,
    "material page must name the DocumentSet dependency in its header",
  )
  assert.match(
    material,
    /owner-aware/,
    "material page must surface the owner-aware upload dependency",
  )
  assert.match(
    material,
    /蔡子鑫/,
    "material page must surface the alignment owner (蔡子鑫) in the header",
  )
  // 不允许擅自聚合 / 不允许伪造成功 —— 真实模式仍逐张失败跳转 v3-material-error
  assert.match(
    material,
    /如实失败并跳转异常页/,
    "material page must keep failing honestly in real mode",
  )
})

test("V3.1: supplement page documents the narrative endpoint dependency without restoring legacy required rule", () => {
  // 复审要求：与钟睿宸对齐补充信息字段 / 保存位置 / 调用方式**不擅自恢复旧规则**；
  // 本页头部必须明确记录该依赖。
  const supplement = readPage("v3-supplement/v3-supplement.vue")
  assert.match(
    supplement,
    /等待钟睿宸对齐|与钟睿宸对齐/,
    "supplement page must surface the alignment owner (钟睿宸) in the header",
  )
  assert.match(
    supplement,
    /source_type:\s*["']narrative["']|source_type\s*=\s*["']narrative["']/,
    "supplement header must reference the narrative source_type on /api/v3/understandings",
  )
  // V3.1：supplement 整页选填 / 两条路径均可整步跳过 —— 不得恢复旧 narrative 必填规则
  assert.ok(
    !/必填[\s\S]*?narrative|narrative[\s\S]*?必填/.test(
      supplement
        // 只看用户可见文案（template 区），防止注释中\"必填\"被误判
        .match(/<template>[\s\S]*?<\/template>/)[0],
    ),
    "supplement template must not reintroduce the legacy narrative required rule",
  )
  // 补充近况 fail-fast：失败 / 缺口仍按 apiV3.submitNarrative 抛错（NARRATIVE_APPEND_UNSUPPORTED 等）
  assert.match(
    supplement,
    /apiV3\.submitNarrative/,
    "supplement must keep calling apiV3.submitNarrative on the no-document path",
  )
})

test("V3.1: supplement page must not fake successful narrative submission in the with-document gap path", () => {
  // 接口未确定前**绝不**把本机暂存伪装成已提交（NARRATIVE_APPEND_UNSUPPORTED 错误码保留）
  const supplement = readPage("v3-supplement/v3-supplement.vue")
  assert.match(
    supplement,
    /NARRATIVE_APPEND_UNSUPPORTED|apiV3\.submitNarrative|提交失败/,
    "supplement must keep honest failure semantics for the with-document append gap",
  )
})
