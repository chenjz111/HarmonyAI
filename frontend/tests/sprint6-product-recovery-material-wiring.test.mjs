import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const material = readFileSync(resolve(root, "pages/v3-material/v3-material.vue"), "utf8")
const script = material.match(/<script>([\s\S]*?)<\/script>/)?.[1] || ""

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
