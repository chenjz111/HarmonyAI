/**
 * Sprint 6 Product Recovery Phase C — PR-006 / PR-007 summary interaction.
 *
 * These assertions protect the page boundary: users operate one summary text,
 * while structured evidence remains an internal backend concern.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")
const markupOnly = (source) => source
  .replace(/<script[\s\S]*?<\/script>/g, "")
  .replace(/<style[\s\S]*?<\/style>/g, "")
  .replace(/<!--[\s\S]*?-->/g, "")

const material = read("pages/v3-material/v3-material.vue")
const legacySummary = read("pages/v3-summary/v3-summary.vue")
const questionnaireConfirm = read("pages/v3-confirm/v3-confirm.vue")

const pages = [
  ["material", material],
  ["legacy document summary", legacySummary],
  ["questionnaire confirmation", questionnaireConfirm],
]

test("PR-006/PR-007: summary pages expose no user evidence-retention controls", () => {
  for (const [name, source] of pages) {
    const markup = markupOnly(source)
    assert.doesNotMatch(markup, /保留|不采用/, `${name} must not expose retention decisions`)
    assert.doesNotMatch(markup, /evidence-(?:block|list|item|toggle|choice|hint)/, `${name} must not render evidence controls`)
    assert.doesNotMatch(source, /buildEvidenceChanges|evidenceDecisionFor|structuredChanges|setEvidence|isKept|isDropped/, `${name} must not maintain a second evidence-decision UI state`)
  }
})

test("PR-006: document summary offers only confirm, full-text edit, and re-upload", () => {
  const markup = markupOnly(material)
  assert.match(markup, /摘要基本准确，继续下一步/)
  assert.match(markup, /修改资料摘要/)
  assert.match(markup, /重新上传资料/)
  assert.match(material, /edited_summary_text:\s*text/, "full-text edit remains the correction path")
  assert.match(material, /changes:\s*\[\]/, "UI sends no user-authored evidence decisions")
})

test("PR-007: questionnaire confirmation renders one summary and full-text edit only", () => {
  const markup = markupOnly(questionnaireConfirm)
  assert.match(markup, /\{\{\s*summaryText\s*\}\}/, "one authoritative summary is rendered")
  assert.doesNotMatch(markup, /v-for=.*summaryItems|summary-facts-list/, "no duplicate structured-fact representation is rendered")
  assert.match(questionnaireConfirm, /edited_summary_text:\s*editedSummaryText/)
  assert.match(questionnaireConfirm, /changes:\s*\[\]/, "UI sends no user-authored evidence decisions")
})

test("GAP-10: legacy summary compatibility page has no second fact representation", () => {
  const markup = markupOnly(legacySummary)
  assert.match(markup, /\{\{\s*summaryText\s*\}\}/)
  assert.doesNotMatch(markup, /v-for=.*evidence|evidence-list/)
  assert.match(legacySummary, /edited_summary_text:\s*text/)
  assert.match(legacySummary, /changes:\s*\[\]/)
})

test("full-text editors retain their non-empty local guards", () => {
  for (const [name, source, draft] of [
    ["material", material, "editText"],
    ["legacy document summary", legacySummary, "editText"],
    ["questionnaire confirmation", questionnaireConfirm, "draftSummaryText"],
  ]) {
    assert.match(source, new RegExp(`const\\s+\\w+\\s*=\\s*\\(this\\.${draft}\\s*\\|\\|\\s*["']{2}\\)\\.trim\\(\\)`), `${name} trims edited text`)
    assert.match(source, /if\s*\(!\w+\)\s*\{[\s\S]{0,180}uni\.showToast/, `${name} blocks an empty edit`)
  }
})
