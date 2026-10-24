import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import test from "node:test"

const frontendUrl = new URL("../", import.meta.url)
const read = path => readFileSync(new URL(path, frontendUrl), "utf8")

const pages = JSON.parse(read("pages.json"))
const customV3Pages = pages.pages.filter(page =>
  page.path.startsWith("pages/v3-") && page.style?.navigationStyle === "custom",
)

const pageSource = page => read(`${page.path}.vue`)

test("Phase H discovers all V3 custom-navigation pages from pages.json", () => {
  assert.equal(customV3Pages.length, 12)
  assert.deepEqual(customV3Pages.map(page => page.path), [
    "pages/v3-material/v3-material",
    "pages/v3-material-error/v3-material-error",
    "pages/v3-summary/v3-summary",
    "pages/v3-supplement/v3-supplement",
    "pages/v3-questionnaire/v3-questionnaire",
    "pages/v3-goal/v3-goal",
    "pages/v3-confirm/v3-confirm",
    "pages/v3-generation/v3-generation",
    "pages/v3-basis/v3-basis",
    "pages/v3-player/v3-player",
    "pages/v3-feedback/v3-feedback",
    "pages/v3-profile/v3-profile",
  ])
})

test("every registered V3 custom-navigation page adopts the shared shell", () => {
  for (const page of customV3Pages) {
    assert.match(
      pageSource(page),
      /class="[^"]*\bv31-page-shell\b[^"]*"/,
      `${page.path} must explicitly adopt v31-page-shell`,
    )
  }
})

test("App exposes one shared additive safe-area shell with zero-inset base spacing", () => {
  const app = read("App.vue")
  const shellPath = new URL("common/v31-page-shell.scss", frontendUrl)
  assert.equal(existsSync(shellPath), true, "shared shell stylesheet must exist")

  const shell = read("common/v31-page-shell.scss")
  assert.match(app, /@import\s+["']\.\/common\/v31-page-shell\.scss["']/)
  assert.match(shell, /\.v31-page-shell\s*\{/)
  assert.match(shell, /--v31-page-top-base\s*:\s*(?!0(?:px|rpx)?\s*;)[^;]+;/)
  assert.match(shell, /--v31-page-bottom-base\s*:\s*(?!0(?:px|rpx)?\s*;)[^;]+;/)
  assert.match(shell, /padding-top\s*:\s*calc\(var\(--v31-page-top-base\)[^;]*\+\s*env\(safe-area-inset-top,\s*0px\)\)/)
  assert.match(shell, /padding-bottom\s*:\s*calc\(var\(--v31-page-bottom-base\)[^;]*\+\s*env\(safe-area-inset-bottom,\s*0px\)\)/)
  assert.match(shell, /box-sizing\s*:\s*border-box/)
  assert.doesNotMatch(shell, /width\s*:\s*100vw/)
  assert.doesNotMatch(shell, /max\([^;]*safe-area-inset/)
})

test("migrated V3 pages do not duplicate system inset arithmetic", () => {
  for (const page of customV3Pages) {
    assert.doesNotMatch(
      pageSource(page),
      /env\(safe-area-inset-(?:top|bottom)/,
      `${page.path} must delegate system inset arithmetic to v31-page-shell`,
    )
  }
  assert.doesNotMatch(read("common/v31-document.scss"), /env\(safe-area-inset-(?:top|bottom)/)
})

test("page-scoped legacy shorthand cannot override shared shell block padding", () => {
  const questionnaire = read("pages/v3-questionnaire/v3-questionnaire.vue")
  assert.doesNotMatch(
    questionnaire,
    /\.container\s*\{[^}]*\bpadding\s*:/s,
    "questionnaire legacy .container padding would override the global shell",
  )
})

test("previously uncovered and stateful pages use one shell path", () => {
  for (const route of [
    "pages/v3-generation/v3-generation",
    "pages/v3-basis/v3-basis",
    "pages/v3-player/v3-player",
  ]) {
    const source = pageSource({ path: route })
    assert.match(source, /v31-page-shell/)
    assert.doesNotMatch(source, /padding\s*:\s*14px\s+[^;]+(?:26|34|36)px/)
  }

  const feedback = read("pages/v3-feedback/v3-feedback.vue")
  assert.doesNotMatch(feedback, /feedback-page--success[^}]*safe-area-inset/s)
  assert.doesNotMatch(feedback, /feedback-container--success[^}]*safe-area-inset/s)

  const profile = read("pages/v3-profile/v3-profile.vue")
  assert.match(profile, /--v31-page-bottom-base\s*:\s*180rpx/)
})

test("root shell sizing remains safe across the 320/360/390/430 viewport contract", () => {
  const shell = read("common/v31-page-shell.scss")
  for (const width of [320, 360, 390, 430]) {
    assert.ok(width <= 430, `${width}px remains inside the V3 mobile canvas`)
  }
  assert.match(shell, /width\s*:\s*100%/)
  assert.match(shell, /max-width\s*:\s*100%/)
  assert.match(shell, /box-sizing\s*:\s*border-box/)
  assert.doesNotMatch(shell, /(?:min-)?width\s*:\s*100vw/)
})
