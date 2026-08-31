import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"


const frontendRoot = resolve(import.meta.dirname, "..")
const repositoryRoot = resolve(frontendRoot, "..")
const read = (relativePath) => readFileSync(resolve(frontendRoot, relativePath), "utf8")


test("release validation includes the three competition paths", () => {
  const e2ePath = resolve(repositoryRoot, "tests/e2e/test_sprint3_competition_flow.py")
  assert.ok(existsSync(e2ePath), "release E2E suite is missing")

  const e2eSource = readFileSync(e2ePath, "utf8")
  for (const scenario of [
    "test_document_narrative_questionnaire_flow",
    "test_narrative_questionnaire_flow",
    "test_questionnaire_only_flow",
  ]) {
    assert.match(e2eSource, new RegExp(`def ${scenario}\\b`))
  }
})


test("material step supports confirmed, skipped, and failed fallback states", () => {
  const material = read("pages/material/material.vue")
  assert.match(material, /confirmDocument/)
  assert.match(material, /document_skipped:\s*true/)
  assert.match(material, /@fallback="skip"/)
})


test("release flow exposes safe degradation and safety blocking to the client", () => {
  const result = read("pages/result/result.vue")
  const api = read("common/api-v2.js")
  assert.match(result, /blocked_safety/)
  assert.match(result, /status === 'error'/)
  assert.match(result, /assessment_confirmed:\s*true/)
  assert.match(api, /HARMONYAI_USE_MOCK/)
})
