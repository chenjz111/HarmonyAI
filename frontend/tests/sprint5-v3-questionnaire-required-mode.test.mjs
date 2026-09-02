import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const page = fs.readFileSync(path.join(here, "../pages/v3-questionnaire/v3-questionnaire.vue"), "utf8")
const narrative = fs.readFileSync(path.join(here, "../pages/v3-narrative/v3-narrative.vue"), "utf8")

test("questionnaire reads the authoritative session mode before deciding whether skip is allowed", () => {
  assert.match(page, /apiV3\.getSession\(\)/)
  assert.match(page, /this\.required\s*=\s*session\.input_mode\s*!==\s*["']with_document["']/)
})

test("questionnaire only renders skip for an explicitly optional flow and guards the action", () => {
  assert.match(page, /v-if=["']!required["']/)
  assert.match(page, /if\s*\(this\.required\s*\|\|\s*this\.submitting\)\s*return/)
})

test("no-document narrative is required and blocks empty continuation", () => {
  assert.match(narrative, /apiV3\.getSession\(\)/)
  assert.match(narrative, /this\.required\s*=\s*s\.input_mode\s*!==\s*["']with_document["']/)
  assert.match(narrative, /if\s*\(this\.required\s*&&\s*!this\.text\.trim\(\)\)/)
})

test("no-document narrative with text can continue", () => {
  assert.match(narrative, /if\s*\(this\.text\s*&&\s*this\.text\.trim\(\)\)/)
  assert.match(narrative, /uni\.redirectTo\(\{\s*url:\s*["']\/pages\/v3-questionnaire\/v3-questionnaire["']/)
})

test("with-document narrative remains optional", () => {
  assert.match(narrative, /v-if=["']!required["']/)
  assert.match(narrative, /if\s*\(this\.required\s*\|\|\s*this\.submitting\)\s*return/)
})
