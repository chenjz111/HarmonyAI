/**
 * Sprint 6 Phase 6 — authority firewall for the supported V3 production flow.
 *
 * These are deliberately static checks. The frontend may present authoritative
 * backend values, but it must not recreate medical or tone decisions locally.
 */
import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const frontendRoot = resolve(import.meta.dirname, "..")
const pagesConfig = JSON.parse(readFileSync(resolve(frontendRoot, "pages.json"), "utf8"))
const registeredRoutes = new Set(pagesConfig.pages.map((page) => page.path))

const CURRENT_V3_ROUTES = [
  "pages/entry/entry",
  "pages/v3-material/v3-material",
  "pages/v3-material-error/v3-material-error",
  "pages/v3-summary/v3-summary",
  "pages/v3-supplement/v3-supplement",
  "pages/v3-questionnaire/v3-questionnaire",
  "pages/v3-goal/v3-goal",
  "pages/v3-confirm/v3-confirm",
  "pages/v3-basis/v3-basis",
  "pages/v3-player/v3-player",
  "pages/v3-feedback/v3-feedback",
  "pages/v3-profile/v3-profile",
]

const FORBIDDEN_LEGACY_ROUTES = [
  "pages/player/player",
  "pages/player-v2/player-v2",
  "pages/result/result",
  "pages/assessment-result/assessment-result",
]

const PRODUCTION_FILES = [
  "pages/welcome/welcome.vue",
  ...CURRENT_V3_ROUTES.map((route) => `${route}.vue`),
  "components/sprint3/han-side-nav.vue",
  "common/api-v3.js",
]

function readProductionFile(relativePath) {
  const absolutePath = resolve(frontendRoot, relativePath)
  assert.ok(existsSync(absolutePath), `missing production file: ${relativePath}`)
  return readFileSync(absolutePath, "utf8")
}

function stripComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|\s)\/\/.*$/gm, "$1")
}

const productionSource = PRODUCTION_FILES
  .map((relativePath) => ({ relativePath, source: stripComments(readProductionFile(relativePath)) }))

function assertNoProductionPattern(pattern, description) {
  for (const { relativePath, source } of productionSource) {
    assert.doesNotMatch(source, pattern, `${relativePath} must not ${description}`)
  }
}

test("registered routes do not include retired legacy routes", () => {
  for (const route of FORBIDDEN_LEGACY_ROUTES) {
    assert.ok(!registeredRoutes.has(route), `retired route is still registered: ${route}`)
  }
})

test("current V3 route registry is complete", () => {
  for (const route of CURRENT_V3_ROUTES) {
    assert.ok(registeredRoutes.has(route), `current V3 route is missing: ${route}`)
  }
})

test("production V3 flow does not synthesize a default primary tone", () => {
  assertNoProductionPattern(
    /(?:primary[_\s]?tone|primaryTone)[^;\n]{0,140}(?:\|\||\?\?)\s*["'`](?:gong|jiao|zhi|shang|yu)["'`]/i,
    "use a hard-coded primary tone fallback",
  )
  assertNoProductionPattern(
    /["'`](?:gong|jiao|zhi|shang|yu)["'`]\s*(?:\|\||\?\?)\s*(?:primary[_\s]?tone|primaryTone)/i,
    "use a hard-coded primary tone fallback",
  )
})

test("production V3 flow does not recompute argmax or dominance", () => {
  assertNoProductionPattern(/\bargmax\b|\.argmax\b/i, "recompute argmax")
  assertNoProductionPattern(/\b(?:dominant[_\s]?tone|dominance(?:[_\s]?(?:decision|score))?)\b/i, "recompute tone dominance")
  assertNoProductionPattern(/\bdominance\s*[:=]/i, "recompute a dominance decision")
})

test("production V3 flow does not infer organ or syndrome from tone", () => {
  assertNoProductionPattern(
    /(?:tone|五音)[\w\s._-]{0,80}(?:organ|syndrome|脏腑|证候)|(?:organ|syndrome|脏腑|证候)[\w\s._-]{0,80}(?:tone|五音)/i,
    "infer an organ or syndrome from a tone",
  )
})

test("production V3 flow does not derive clinical severity from a score", () => {
  assertNoProductionPattern(
    /(?:score|scores|severity_score|分数)[^;\n]{0,120}(?:severity|严重程度)|(?:severity|严重程度)[^;\n]{0,120}(?:score|scores|分数)/i,
    "derive clinical severity from a score",
  )
})

test("api-v3 retains the 8000 default and has no hard-coded 8010", () => {
  const apiV3 = readProductionFile("common/api-v3.js")
  assert.match(apiV3, /localhost:8000/)
  assert.doesNotMatch(apiV3, /8010/)
})
