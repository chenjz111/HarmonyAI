/**
 * Sprint 6 Phase 6 — Feedback Lane 契约测试（肖宇翔）
 *
 * Owner 冻结决定 P6-D4：Q1 / post_state 必填；Q2–Q5 选填；skip 保留。
 * 覆盖 FB-T1 ~ FB-T8（另含 422 防御一条）。
 *
 * 断言分两层：
 *   1. 行为层——从 pages/v3-feedback/v3-feedback.vue 提取组件 options，
 *      注入 mock apiV3 / uni 后真实调用 submit()，观察请求次数与载荷；
 *   2. 静态层——模板必填标记、就地校验、跳过入口、成功态，
 *      以及页面源码不触碰本次聆听的权威接口。
 *
 * 运行方式与仓库其它前端测试一致：cd frontend && node --test tests/sprint6-phase6-feedback.test.mjs
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const frontendRoot = resolve(import.meta.dirname, "..")
const pagePath = resolve(frontendRoot, "pages/v3-feedback/v3-feedback.vue")
const source = readFileSync(pagePath, "utf8")
const markup = source.replace(/<style[\s\S]*?<\/style>/g, "")

const REQUIRED_COPY = "请先选择听完这段音乐后的感受"

/**
 * 提取 .vue 的 <script> 并注入依赖执行，得到组件 options。
 * 处理点：去掉 import 行（改为注入参数）、export default → return、
 * export function → function（Function 体内不允许 export）。
 */
function loadPageOptions(apiV3, uni) {
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const body = script
    .replace(/^\s*import[^\n]*$/gm, "")
    .replace(/export function/g, "function")
    .replace(/export default/, "return")
  // eslint-disable-next-line no-new-func
  return new Function("apiV3", "uni", body)(apiV3, uni)
}

/** 构造带 computed/methods 的组件实例，并记录 apiV3 调用与 uni 调用 */
function createVm(options = {}) {
  const calls = []
  const uniCalls = { reLaunch: [], pageScrollTo: [], navigateBack: [] }
  let pendingReject = options.rejectWith || null
  let holding = null
  const holdPromise = options.hold
    ? new Promise((res) => { holding = res })
    : null

  const apiV3 = {
    async submitFeedback(payload) {
      calls.push(payload)
      if (pendingReject) {
        const err = pendingReject
        pendingReject = null
        throw err
      }
      if (holdPromise) await holdPromise
      return { received: true }
    },
  }
  const uni = {
    navigateBack() { uniCalls.navigateBack.push(true) },
    reLaunch(arg) { uniCalls.reLaunch.push(arg) },
    pageScrollTo(arg) { uniCalls.pageScrollTo.push(arg) },
  }

  const comp = loadPageOptions(apiV3, uni)
  const vm = comp.data()
  for (const [key, fn] of Object.entries(comp.computed || {})) {
    Object.defineProperty(vm, key, { get: () => fn.call(vm), configurable: true })
  }
  for (const [key, fn] of Object.entries(comp.methods || {})) {
    vm[key] = fn.bind(vm)
  }
  return { vm, calls, uniCalls, release: () => { if (holding) holding() } }
}

// ---------------------------------------------------------------- 行为层

test("FB-T1 empty submit => 0 POST", async () => {
  const { vm, calls } = createVm()
  await vm.submit()
  assert.equal(calls.length, 0, "空提交不得产生任何请求")
})

test("FB-T2 validation shown on empty submit", async () => {
  const { vm, uniCalls } = createVm()
  await vm.submit()
  assert.equal(vm.showValidation, true, "空提交后必须置校验态")
  assert.equal(vm.q1Missing, true, "Q1 缺失应为真")
  assert.equal(vm.submitted, false, "校验失败不得进入成功态")
  assert.equal(uniCalls.pageScrollTo.length, 1, "校验时就地滚动到 Q1")
  assert.equal(uniCalls.pageScrollTo[0].selector, "#feedback-q1")
  // 静态：校验文案与节点存在
  assert.match(markup, /v-if="q1Missing"/, "模板包含就地校验节点")
  assert.match(source, new RegExp(REQUIRED_COPY), "校验文案存在")
})

test("FB-T3 Q1 only => POST allowed with required post_state", async () => {
  const { vm, calls } = createVm()
  vm.pickChange("slightly_better")
  await vm.submit()
  assert.equal(calls.length, 1, "仅填 Q1 应允许提交一次")
  assert.deepEqual(calls[0].post_state, { change_label: "slightly_better" }, "post_state 必填且携带 change_label")
  assert.equal(vm.submitted, true)
  assert.equal(vm.showValidation, false)
})

test("FB-T4 Q2–Q5 remain optional and stay out of the payload when empty", async () => {
  const { vm, calls } = createVm()
  vm.pickChange("much_better")
  await vm.submit()
  const payload = calls[0]
  assert.equal(payload.continue_use, undefined, "Q2 未选不得进入载荷")
  assert.deepEqual(payload.liked_features, [], "Q3 未选为空数组")
  assert.deepEqual(payload.adjustment_preferences, [], "Q4 未选为空数组")
  assert.equal(payload.comment, undefined, "Q5 未填不得进入载荷")
  assert.equal(payload.post_state.change_label, "much_better")
  // 静态：必填/选填标记
  assert.match(markup, /（必填）/, "Q1 需可见标注必填")
  assert.match(markup, /（选填）/, "其余题保持选填标注")
  assert.doesNotMatch(markup, /全部选填|可一条不填直接提交/, "不得保留“全部可选填”的旧表述")
})

test("FB-T5 duplicate click => one POST", async () => {
  const { vm, calls, release } = createVm({ hold: true })
  vm.pickChange("no_change")
  const first = vm.submit()
  const second = vm.submit()
  release()
  await Promise.all([first, second])
  assert.equal(calls.length, 1, "提交中重复点击只能产生一次请求")
})

test("FB-T6 skip remains available", () => {
  assert.match(markup, /暂时跳过/, "跳过入口保留")
  const { vm, uniCalls } = createVm()
  vm.goHome()
  assert.deepEqual(uniCalls.reLaunch, [{ url: "/pages/entry/entry" }], "跳过回到入口页")
})

test("FB-T7 success state unchanged", () => {
  assert.match(markup, /feedback-success/, "成功态区块保留")
  assert.match(markup, /反馈已提交/, "成功文案保留")
  assert.match(markup, /返回首页/, "成功态返回入口保留")
})

test("FB-T8 no current-run authority mutation", async () => {
  const { vm, calls } = createVm()
  vm.pickChange("slightly_better")
  await vm.submit()
  assert.equal(calls.length, 1)
  // 载荷只包含反馈自身字段，不携带任何本次聆听的权威对象
  const allowed = new Set([
    "post_state",
    "continue_use",
    "favorite",
    "liked_features",
    "adjustment_preferences",
    "comment",
  ])
  for (const key of Object.keys(calls[0])) {
    assert.ok(allowed.has(key), `反馈载荷不得携带额外字段：${key}`)
  }
  assert.equal(calls[0].favorite, null)
  // 静态：只调用反馈接口，不触碰判定/处方/生成等权威接口
  assert.match(source, /apiV3\.submitFeedback\(/, "通过反馈接口提交")
  for (const forbidden of ["createAssessment", "confirmAssessment", "startMusicGeneration", "getMusicBasis", "getMusic"]) {
    assert.doesNotMatch(source, new RegExp(`apiV3\\.${forbidden}`), `反馈页不得调用 ${forbidden}`)
  }
})

test("FB-T9 server 422 is not surfaced as raw validation UX", async () => {
  const { vm } = createVm({
    rejectWith: { status: 422, message: "Unprocessable Entity: body.post_state field required" },
  })
  vm.pickChange("much_better")
  await vm.submit()
  assert.equal(vm.submitted, false, "服务端拒绝不得进入成功态")
  assert.doesNotMatch(vm.submitError, /422|Unprocessable|field required/, "不得直接暴露原始报文")
  assert.match(vm.submitError, new RegExp(REQUIRED_COPY), "转换为页面校验文案")
})

// ---------------------------------------------------------------- 静态层

test("FB-S1 page keeps explicit required marker on Q1 and keeps Q1 anchor", () => {
  assert.match(markup, /id="feedback-q1"/, "Q1 具有滚动锚点")
  assert.match(markup, /feedback-choice-note--required/, "Q1 必填样式")
  assert.match(source, /post_state:\s*\{\s*change_label:\s*this\.changeLabel\s*\}/, "post_state 直接构造，不再三元 null")
  assert.doesNotMatch(source, /post_state:\s*this\.changeLabel\s*\?/, "不得保留条件 null 的 post_state")
})

test("FB-S2 validation copy is single-sourced from the module constant", () => {
  assert.match(source, /const REQUIRED_QUESTION_MESSAGE\s*=\s*"[^"]+"/, "存在模块级校验文案常量")
  assert.match(source, /requiredMessage:\s*REQUIRED_QUESTION_MESSAGE/, "模板文案取自同一常量")
})
