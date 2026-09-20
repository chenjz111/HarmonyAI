/**
 * Sprint 6 Phase 6 — route safety and legacy-route quarantine.
 *
 * This test intentionally checks the route registry and the supported V3
 * production navigation surface only. Legacy page source files remain on disk
 * for compatibility, but their routes must not be registered as supported
 * V3 entry points.
 */
import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const frontendRoot = resolve(import.meta.dirname, "..")
const pagesConfig = JSON.parse(readFileSync(resolve(frontendRoot, "pages.json"), "utf8"))
const registeredRoutes = pagesConfig.pages.map((page) => page.path)

const FORBIDDEN_LEGACY_ROUTES = [
  "pages/player/player",
  "pages/player-v2/player-v2",
  "pages/result/result",
  "pages/assessment-result/assessment-result",
]

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

const CURRENT_V3_PRODUCTION_FILES = [
  "pages/welcome/welcome.vue",
  ...CURRENT_V3_ROUTES.map((route) => `${route}.vue`),
  "components/sprint3/han-side-nav.vue",
]

function readFrontendFile(relativePath) {
  const absolutePath = resolve(frontendRoot, relativePath)
  assert.ok(existsSync(absolutePath), `missing expected frontend file: ${relativePath}`)
  return readFileSync(absolutePath, "utf8")
}

test("the four retired legacy routes are not registered", () => {
  for (const route of FORBIDDEN_LEGACY_ROUTES) {
    assert.ok(!registeredRoutes.includes(route), `retired route must be unregistered: ${route}`)
  }
})

test("retired page source files remain available for compatibility", () => {
  for (const route of FORBIDDEN_LEGACY_ROUTES) {
    assert.ok(existsSync(resolve(frontendRoot, `${route}.vue`)), `do not delete legacy source: ${route}.vue`)
  }
})

test("all current V3 routes remain registered and have source files", () => {
  for (const route of CURRENT_V3_ROUTES) {
    assert.ok(registeredRoutes.includes(route), `missing current V3 route: ${route}`)
    assert.ok(existsSync(resolve(frontendRoot, `${route}.vue`)), `missing current V3 source: ${route}.vue`)
  }
})

test("the supported V3 production navigation surface has no retired-route references", () => {
  for (const relativePath of CURRENT_V3_PRODUCTION_FILES) {
    const source = readFrontendFile(relativePath)
    for (const route of FORBIDDEN_LEGACY_ROUTES) {
      assert.ok(!source.includes(route), `${relativePath} must not navigate to retired route ${route}`)
    }
  }
})

test("tab bar remains anchored to the current V3 entry and profile pages", () => {
  const tabRoutes = pagesConfig.tabBar.list.map((item) => item.pagePath)
  assert.deepEqual(tabRoutes, ["pages/entry/entry", "pages/v3-profile/v3-profile"])
})

test("the default backend port remains 8000 and api-v3 has no 8010 fallback", () => {
  const apiV3 = readFrontendFile("common/api-v3.js")
  assert.match(apiV3, /localhost:8000/)
  assert.doesNotMatch(apiV3, /8010/)
})
