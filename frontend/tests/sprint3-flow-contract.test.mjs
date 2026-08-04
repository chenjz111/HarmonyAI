import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"


const frontendRoot = resolve(import.meta.dirname, "..")
const pagesConfig = JSON.parse(readFileSync(resolve(frontendRoot, "pages.json"), "utf8"))
const routes = pagesConfig.pages.map((page) => page.path)


test("welcome starts an eight-page Sprint 3 flow", () => {
  const sprint3Routes = [
    "pages/welcome/welcome",
    "pages/material/material",
    "pages/narrative/narrative",
    "pages/survey-v2/survey-v2",
    "pages/result/result",
    "pages/player-v2/player-v2",
    "pages/feedback-v2/feedback-v2",
    "pages/complete/complete",
  ]
  assert.equal(routes[0], sprint3Routes[0])
  for (const route of sprint3Routes) {
    assert.ok(routes.includes(route), `missing route: ${route}`)
    assert.ok(existsSync(resolve(frontendRoot, `${route}.vue`)), `missing page: ${route}`)
  }
})


test("Sprint 2 pages remain reachable", () => {
  for (const route of [
    "pages/index/index",
    "pages/emotion/emotion",
    "pages/survey/survey",
    "pages/player/player",
  ]) {
    assert.ok(routes.includes(route), `legacy route removed: ${route}`)
  }
})
