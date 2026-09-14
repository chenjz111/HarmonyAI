/**
 * V3.1 confirmed-summary authority regressions.
 *
 * The frontend test suite inspects uni-app SFCs directly because it has no DOM
 * runtime. These assertions protect the user-visible binding and submission
 * contracts at the page boundary.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")
const stripStyles = (source) => source.replace(/<style[\s\S]*?<\/style>/g, "")

const documentSummary = read("pages/v3-summary/v3-summary.vue")
const questionnaireSummary = read("pages/v3-confirm/v3-confirm.vue")
const supplement = read("pages/v3-supplement/v3-supplement.vue")
const documentMarkup = stripStyles(documentSummary)
const questionnaireMarkup = stripStyles(questionnaireSummary)

test("document summary body and editor prefill use the normalized backend summary", () => {
  assert.match(documentSummary, /summaryText\(\)\s*\{/, "document page normalizes the read model")
  assert.match(
    documentSummary,
    /presentation\.summary\s*\|\|\s*model\.state_summary\s*\|\|\s*model\.summary/,
    "confirmed state_summary wins over the legacy summary fallback",
  )
  assert.match(documentMarkup, /\{\{\s*summaryText\s*\}\}/, "body renders the normalized summary")
  assert.match(documentSummary, /this\.editText\s*=\s*this\.summaryText\s*\|\|\s*""/, "editor prefill matches the displayed summary")
})

test("questionnaire summary renders and pre-fills authoritative text, never a generic fallback", () => {
  assert.match(
    questionnaireSummary,
    /presentation\.summary\s*\|\|\s*model\.state_summary\s*\|\|\s*model\.summary/,
    "confirmed state_summary wins over a legacy summary fallback",
  )
  assert.match(questionnaireMarkup, /\{\{\s*summaryText\s*\}\}/, "body renders normalized summary text")
  assert.match(questionnaireSummary, /this\.draftSummaryText\s*=\s*this\.summaryText\s*\|\|\s*""/, "editor prefill matches displayed text")
  assert.doesNotMatch(
    questionnaireMarkup,
    /已根据你本次提供并确认的信息完成状态评估。/,
    "generic status copy must not masquerade as a questionnaire summary",
  )
})

test("both confirmation editors remain full-text-only and guard empty submissions", () => {
  for (const [name, page, markup, draft] of [
    ["document", documentSummary, documentMarkup, "editText"],
    ["questionnaire", questionnaireSummary, questionnaireMarkup, "draftSummaryText"],
  ]) {
    assert.match(markup, /<textarea[\s\S]*?inline-summary-editor/, `${name} editor is a textarea`)
    assert.doesNotMatch(markup, /severity-row|allowed_values|organ-editor/, `${name} has no structured medical editor`)
    assert.match(page, new RegExp(`const\\s+\\w+\\s*=\\s*\\(this\\.${draft}\\s*\\|\\|\\s*["']{2}\\)\\.trim\\(\\)`), `${name} trims before save`)
    assert.match(page, /if\s*\(!\w+\)\s*\{[\s\S]{0,180}uni\.showToast/, `${name} blocks an empty save locally`)
    assert.match(page, /edited_summary_text:\s*\w+/, `${name} submits only edited full text`)
  }
})

test("document edits keep the frozen request shape without exposing provider failure copy", () => {
  assert.match(documentSummary, /reprocess_requested:\s*true/, "frozen full-edit request shape stays valid")
  assert.doesNotMatch(documentSummary, /FACT_EXTRACTION_UNAVAILABLE|重新解析/, "document editor must not show re-parse-unavailable copy")
})

test("document-only creates and confirms once before going directly to analysis", () => {
  assert.match(supplement, /apiV3\.createAssessment\(\)/)
  assert.match(supplement, /apiV3\.confirmAssessment\(/)
  assert.match(supplement, /pages\/v3-basis\/v3-basis/)
  assert.doesNotMatch(supplement, /url:\s*["']\/pages\/v3-confirm\/v3-confirm/, "document-only must not open a second confirmation page")
})

test("summary editors preserve narrow-screen containment", () => {
  for (const [name, page] of [["document", documentSummary], ["questionnaire", questionnaireSummary]]) {
    assert.match(page, /\.edit-textarea\s*\{[^}]*min-width:\s*0/, `${name} textarea can shrink inside its flex row`)
    assert.match(page, /\.edit-textarea\s*\{[^}]*width:\s*100%/, `${name} textarea uses its available width`)
    assert.match(page, /\.edit-textarea\s*\{[^}]*padding:\s*0/, `${name} editor does not add width beyond its flex row`)
  }
})
