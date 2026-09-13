import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"
import { INTENT_CODES } from "../common/v3-healing-intent.js"
import * as toneTheme from "../common/v31-tone-theme.js"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("mobile tab bar exposes Home and the upgrade placeholder, never Player", () => {
  const pages = JSON.parse(read("pages.json"))
  assert.deepEqual(
    pages.tabBar.list.map((item) => [item.text, item.pagePath]),
    [
      ["首页", "pages/entry/entry"],
      ["我的", "pages/v3-profile/v3-profile"],
    ],
  )
  assert.ok(existsSync(resolve(root, "pages/v3-profile/v3-profile.vue")))
  assert.match(read("pages/v3-profile/v3-profile.vue"), /功能升级中/)
  assert.equal(pages.tabBar.color, "#989fa0")
  assert.equal(pages.tabBar.selectedColor, "#079777")
  assert.equal(pages.tabBar.backgroundColor, "#ffffff")
  for (const item of pages.tabBar.list) {
    assert.ok(item.iconPath && existsSync(resolve(root, item.iconPath)), "tab icon must exist")
    assert.ok(item.selectedIconPath && existsSync(resolve(root, item.selectedIconPath)), "selected icon must exist")
  }
})

test("homepage uses separated reference artwork with real labels and controls", () => {
  const entry = read("pages/entry/entry.vue")
  assert.deepEqual([...entry.matchAll(/\{ id: "([^"]+)"/g)].map(match => match[1]), ["with_document", "without_document"])
  for (const asset of ["home-watercolor-v1.png", "home-icons-v2.png"]) {
    assert.ok(entry.includes(asset))
    assert.ok(existsSync(resolve(root, "static/v31-home", asset)))
  }
  assert.doesNotMatch(entry, /home-icons-v1\.png/)
  assert.match(entry, /background-size:\s*300%\s+100%/)
  assert.match(entry, /max-width:\s*430px/)
  assert.match(entry, /让音乐，陪你回到更好的自己/)
  assert.match(entry, /以中医为本 · 用音乐疗愈身心/)
  assert.match(entry, /MUSIC HEALS A BETTER YOU/)
  assert.match(entry, /@click="choose\(choice\)"/)
  assert.match(entry, /apiV3\.selectMode\(choice\.id\)/)
  assert.match(entry, /uni\.navigateTo\(\{ url: choice\.route \}\)/)
})

test("Owner visual override hides Other and free text but keeps six structured healing intents", () => {
  const goal = read("pages/v3-goal/v3-goal.vue")
  const template = goal.match(/<template>[\s\S]*?<\/template>/)?.[0] || ""
  assert.doesNotMatch(template, /<textarea/)
  assert.doesNotMatch(template, /其他想法|你还想补充什么|other/)
  assert.deepEqual(
    INTENT_CODES.filter((item) => item.code !== "other").map((item) => item.code),
    ["sleep", "relaxation", "emotion_regulation", "focus", "energy", "stress_relief"],
  )
  assert.match(goal, /INTENT_CODES\.filter\(\(item\)\s*=>\s*item\.code\s*!==\s*"other"\)/)
  assert.match(goal, /custom_goal_text:\s*""/)
})

test("material flow keeps explicit 1-3 upload interaction and standalone error branch", () => {
  const upload = read("pages/v3-material/v3-material.vue")
  const error = read("pages/v3-material-error/v3-material-error.vue")
  assert.match(upload, /MAX_FILES\s*=\s*3/)
  assert.match(upload, /file-remove--top-right/)
  assert.match(upload, /开始识别/)
  assert.match(error, /这份资料暂时无法用于本次分析/)
  assert.match(error, /重新选择资料/)
  assert.match(error, /我没有合适的资料/)
  assert.match(error, /discardDocument/)
})

test("questionnaire is five scrollable pages with two approved questions per page", () => {
  const questionnaire = read("pages/v3-questionnaire/v3-questionnaire.vue")
  assert.match(questionnaire, /PAGE_SIZE\s*=\s*2/)
  assert.match(questionnaire, /下一题/)
  assert.match(questionnaire, /完成问卷/)
  assert.match(questionnaire, /apiV3\.getQuestionnaireSchema\(\)/)
  assert.match(questionnaire, /v31-scroll-page/)
  assert.match(questionnaire, /questionnaire-page/)
  assert.match(questionnaire, /questionnaire-background\.png/)
  assert.match(questionnaire, /optionImage\(q, opt, optIndex\)/)
  assert.match(questionnaire, /\{\{ current \+ 1 \}\}\/\{\{ totalSteps \|\| 5 \}\}/)
  assert.match(questionnaire, />下一题</)
  for (const question of [1, 2]) {
    for (let score = 0; score <= 4; score += 1) {
      assert.ok(existsSync(resolve(root, `static/v31-questionnaire/q${question}-${score}.png`)))
    }
  }
})

test("both summaries edit inline and the document-only path skips duplicate confirmation", () => {
  const summary = read("pages/v3-summary/v3-summary.vue")
  const confirm = read("pages/v3-confirm/v3-confirm.vue")
  const supplement = read("pages/v3-supplement/v3-supplement.vue")
  assert.match(summary, /inline-summary-editor/)
  assert.match(confirm, /inline-summary-editor/)
  assert.match(supplement, /直接进入分析/)
  assert.match(supplement, /pages\/v3-basis\/v3-basis/)
})

test("Five-Tone analysis generates on-page and transitions directly to Player", () => {
  const basis = read("pages/v3-basis/v3-basis.vue")
  assert.match(basis, /生成我的音乐/)
  assert.match(basis, /音乐生成中/)
  assert.match(basis, /pages\/v3-player\/v3-player/)
  assert.doesNotMatch(basis, /音乐已生成完成|开始试听/)
})

test("one player uses five data-driven themes and real duration", () => {
  const player = read("pages/v3-player/v3-player.vue")
  const theme = read("common/v31-tone-theme.js")
  for (const tone of ["gong", "shang", "jue", "zhi", "yu"]) {
    assert.match(theme, new RegExp(`\\b${tone}\\b`))
  }
  assert.match(player, /toneThemeFor/)
  assert.match(player, /duration_seconds/)
  assert.match(player, /toggleFavorite/)
  assert.match(player, /反馈本次体验/)
  assert.match(player, /结束本次聆听/)
  assert.doesNotMatch(player, />\s*5\s*分钟\s*</)
})

test("player time floors fractional seconds and leaves minutes unpadded", () => {
  assert.equal(typeof toneTheme.formatPlaybackTime, "function")
  assert.equal(toneTheme.formatPlaybackTime(0.907008), "0:00")
  assert.equal(toneTheme.formatPlaybackTime(60.881633000000008), "1:00")
  assert.equal(toneTheme.formatPlaybackTime(123.99), "2:03")
})
