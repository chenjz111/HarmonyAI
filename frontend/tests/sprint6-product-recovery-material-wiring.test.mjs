import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

import { createMaterialRecoveryFlow, MATERIAL_PHASES } from "../common/material-recovery-flow.js"

const root = resolve(import.meta.dirname, "..")
const material = readFileSync(resolve(root, "pages/v3-material/v3-material.vue"), "utf8")
const script = material.match(/<script>([\s\S]*?)<\/script>/)?.[1] || ""

function deferred() {
  let resolvePromise
  let rejectPromise
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })
  return { promise, resolve: resolvePromise, reject: rejectPromise }
}

function loadMaterialComponent(apiV3) {
  const executable = script
    .replace(/import[\s\S]*?from\s+["'][^"']+["']\s*/g, "")
    .replace("export default", "return")

  return new Function(
    "apiV3",
    "buildEvidenceChanges",
    "evidenceDecisionFor",
    "EVIDENCE_DECISION_KEEP",
    "EVIDENCE_DECISION_DROP",
    "MATERIAL_PHASES",
    "createMaterialRecoveryFlow",
    "DocumentHeader",
    executable,
  )(
    apiV3,
    () => [],
    () => "confirmed",
    "confirmed",
    "rejected",
    MATERIAL_PHASES,
    createMaterialRecoveryFlow,
    {},
  )
}

function createMaterialVm(confirmUnderstanding) {
  const redirects = []
  const toasts = []
  const switches = []
  const previousUni = globalThis.uni
  globalThis.uni = {
    redirectTo: payload => redirects.push(payload),
    showToast: payload => toasts.push(payload),
    switchTab: payload => switches.push(payload),
  }

  const component = loadMaterialComponent({ confirmUnderstanding })
  const vm = component.data()
  for (const [name, method] of Object.entries(component.methods)) {
    vm[name] = method.bind(vm)
  }
  for (const [name, getter] of Object.entries(component.computed)) {
    Object.defineProperty(vm, name, { get: getter.bind(vm) })
  }
  vm.setupMaterialFlow()
  vm.summaryModel = { revision: 7 }
  vm.editText = "用户确认后的摘要"

  return {
    component,
    vm,
    redirects,
    toasts,
    switches,
    restore() {
      if (vm.materialFlow) vm.materialFlow.dispose()
      globalThis.uni = previousUni
    },
  }
}

test("PR-002/PR-003 normal document success stays on v3-material through inline summary", () => {
  assert.match(script, /createMaterialRecoveryFlow/)
  assert.doesNotMatch(material, /\/pages\/v3-summary\/v3-summary/)
  assert.match(material, /摘要基本准确，继续下一步/)
  assert.match(material, /修改资料摘要/)
  assert.match(material, /重新上传资料/)
  assert.match(material, /inline-summary-editor/)
  assert.match(script, /reupload\(\)[\s\S]*resetMaterialFlow\(\)/)
})

test("existing upload and canonical DocumentSet API order is preserved exactly once", () => {
  const upload = script.indexOf("apiV3.uploadDocument(f.path, f.name)")
  const collect = script.indexOf("documentIds.push(doc.document_id)")
  const createSet = script.indexOf("apiV3.createDocumentSet(documentIds)")
  const summary = script.indexOf("apiV3.getCaseSummary()")

  assert.ok(upload >= 0 && upload < collect)
  assert.ok(collect < createSet)
  assert.ok(createSet < summary)
  assert.equal(script.split("apiV3.createDocumentSet(").length - 1, 1)
  assert.equal(script.split("apiV3.getCaseSummary(").length - 1, 1)
  assert.match(script, /if \(!this\.materialFlow\.beginUpload\(\)\) return/)
})

test("complete backend summary enters presentation flow without frontend rewriting", () => {
  assert.match(script, /const summaryModel\s*=\s*await apiV3\.getCaseSummary\(\)/)
  assert.match(script, /const summaryText\s*=\s*this\.resolvedSummaryText/)
  assert.match(script, /this\.materialFlow\.summaryReady\(summaryText\)/)
  assert.doesNotMatch(script, /30%|60%|provider progress|Agent|RAG/)
})

test("confirmation and full-text edit preserve the existing API payload contract", () => {
  assert.match(script, /confirmUnderstanding\(\{[\s\S]*?expected_revision:\s*this\.summaryModel\.revision,[\s\S]*?decision:\s*changes\.length\s*\?\s*"confirm_with_changes"\s*:\s*"confirm",[\s\S]*?changes,/)
  assert.match(script, /confirmUnderstanding\(\{[\s\S]*?expected_revision:\s*this\.summaryModel\.revision,[\s\S]*?decision:\s*"confirm_with_changes",[\s\S]*?changes:\s*this\.structuredChanges,[\s\S]*?edited_summary_text:\s*text,[\s\S]*?reprocess_requested:\s*true,/)
  assert.match(script, /if \(!text\)/)
  assert.match(script, /text\.length\s*>\s*2000/)
})

test("re-upload and unload clean the single presentation state machine", () => {
  assert.match(script, /onUnload\(\)[\s\S]*materialFlow\.dispose\(\)/)
  assert.match(script, /resetMaterialFlow\(\)[\s\S]*materialFlow\.reset\(\)/)
  assert.match(script, /reupload\(\)[\s\S]*resetMaterialFlow\(\)/)
  assert.doesNotMatch(script, /setTimeout\s*\(/)
})

test("late API responses cannot mutate a disposed or reset material flow", () => {
  assert.match(script, /operationToken:\s*0/)
  assert.match(script, /onUnload\(\)[\s\S]*this\.operationToken \+= 1/)
  assert.match(script, /const runToken = \+\+this\.operationToken/)
  assert.match(script, /isCurrentRun\(runToken\)/)
  assert.match(script, /const summaryModel = await apiV3\.getCaseSummary\(\)[\s\S]*?if \(!this\.isCurrentRun\(runToken\)\) return[\s\S]*?this\.summaryModel = summaryModel/)
  assert.match(script, /resetMaterialFlow\(\)[\s\S]*this\.operationToken \+= 1/)
})

test("existing OCR/network failure routes remain explicit and recoverable", () => {
  assert.match(material, /\/pages\/v3-material-error\/v3-material-error\?type=ocr/)
  assert.match(material, /\/pages\/v3-material-error\/v3-material-error\?type=network/)
})

test("pending confirm success cannot redirect after reset", async () => {
  const confirmation = deferred()
  const harness = createMaterialVm(() => confirmation.promise)
  try {
    const pending = harness.vm.confirmOk()
    assert.equal(harness.vm.submitting, true)
    harness.vm.resetMaterialFlow()

    confirmation.resolve({ revision: 8 })
    await pending

    assert.deepEqual(harness.redirects, [])
    assert.equal(harness.vm.submitting, false)
  } finally {
    harness.restore()
  }
})

test("pending confirm failure cannot show a stale toast after unload", async () => {
  const confirmation = deferred()
  const harness = createMaterialVm(() => confirmation.promise)
  try {
    const pending = harness.vm.confirmOk()
    harness.component.onUnload.call(harness.vm)

    confirmation.reject(new Error("late failure"))
    await pending

    assert.deepEqual(harness.toasts, [])
  } finally {
    harness.restore()
  }
})

test("pending edited confirmation cannot redirect or overwrite a newer reset state", async () => {
  const confirmation = deferred()
  const harness = createMaterialVm(() => confirmation.promise)
  try {
    const pending = harness.vm.saveEdit()
    harness.vm.resetMaterialFlow()
    harness.vm.submitting = true

    confirmation.resolve({ revision: 8 })
    await pending

    assert.deepEqual(harness.redirects, [])
    assert.equal(harness.vm.submitting, true, "stale finally must not clear a newer submission")
  } finally {
    harness.restore()
  }
})

test("current confirmation still redirects once and duplicate click stays suppressed", async () => {
  const confirmation = deferred()
  let calls = 0
  const harness = createMaterialVm(() => {
    calls += 1
    return confirmation.promise
  })
  try {
    const first = harness.vm.confirmOk()
    const duplicate = harness.vm.confirmOk()
    confirmation.resolve({ revision: 8 })
    await Promise.all([first, duplicate])

    assert.equal(calls, 1)
    assert.deepEqual(harness.redirects, [{ url: "/pages/v3-supplement/v3-supplement" }])
    assert.equal(harness.vm.submitting, false)
  } finally {
    harness.restore()
  }
})

test("page-header back action is inert while confirmation is pending", async () => {
  const confirmation = deferred()
  const harness = createMaterialVm(() => confirmation.promise)
  try {
    harness.vm.materialState = { ...harness.vm.materialState, phase: MATERIAL_PHASES.SUMMARY_READY }
    const pending = harness.vm.confirmOk()
    const tokenBeforeBack = harness.vm.operationToken

    harness.vm.handleBack()

    assert.equal(harness.vm.operationToken, tokenBeforeBack)
    assert.equal(harness.vm.summaryModel.revision, 7)
    assert.deepEqual(harness.switches, [])
    confirmation.resolve({ revision: 8 })
    await pending
  } finally {
    harness.restore()
  }
})
