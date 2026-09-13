const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const THEMES = [
  { code: 'gong', glyph: '宫', title: '静水流深' },
  { code: 'shang', glyph: '商', title: '清风和鸣' },
  { code: 'jue', glyph: '角', title: '春山新绿' },
  { code: 'zhi', glyph: '徵', title: '秋山红叶' },
  { code: 'yu', glyph: '羽', title: '寒江映月' },
]

async function reachPlayer(page) {
  await page.goto('http://127.0.0.1:5181/?harmonyai_demo=1#/pages/entry/entry')
  await page.locator('.choice-card').nth(1).click()
  await page.getByText('Q1', { exact: true }).waitFor()
  for (let step = 1; step <= 5; step += 1) {
    const cards = page.locator('.q-card')
    await cards.nth(0).locator('.q-option').first().click()
    await cards.nth(1).locator('.q-option').first().click()
    await page.getByText(step === 5 ? '完成问卷' : '下一题', { exact: true }).click()
    if (step < 5) await page.getByText(`${step + 1}/5`, { exact: true }).waitFor()
  }
  await page.getByText('暂时跳过', { exact: true }).click()
  await page.getByText('基本符合，继续', { exact: true }).click()
  await page.getByText('生成我的音乐', { exact: true }).click()
  await page.locator('.tone-player-page').waitFor({ timeout: 20000 })
}

async function setTheme(page, theme) {
  await page.locator('.tone-player-page').evaluate((element, next) => {
    let component = element.__vueParentComponent
    while (component && !(component.proxy && component.proxy.music)) component = component.parent
    if (!component || !component.proxy) throw new Error('player component instance not found')
    component.proxy.music.tone_code = next.code
    component.proxy.music.title = next.title
  }, theme)
  await page.getByText(theme.title, { exact: true }).waitFor()
  await page.waitForFunction(expected => {
    const image = document.querySelector('.tone-hero-image img')
    return image && image.getAttribute('src') === expected
  }, `/static/v31-player/${theme.code}-2.png`)
}

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const output = path.resolve(__dirname, '../../artifacts/player-reference')
  fs.mkdirSync(output, { recursive: true })
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
    page.setDefaultTimeout(12000)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      return ['127.0.0.1', 'localhost'].includes(url.hostname) ? route.continue() : route.abort()
    })

    await reachPlayer(page)
    await page.getByText('本次音乐', { exact: true }).waitFor()
    assert.equal(await page.locator('.music-summary-cell').count(), 5)
    assert.equal(await page.locator('.ctrl-fav').count(), 0)
    await page.getByText('反馈本次体验', { exact: true }).waitFor()
    await page.getByText('结束本次聆听', { exact: true }).waitFor()

    for (const theme of THEMES) {
      await setTheme(page, theme)
      assert.equal(await page.locator('.tone-glyph').innerText(), theme.glyph)
      assert.equal(await page.locator('.tone-hero-image img').getAttribute('src'), `/static/v31-player/${theme.code}-2.png`)
      const background = await page.locator('.tone-player-page').evaluate(element => getComputedStyle(element).backgroundImage)
      assert.match(background, new RegExp(`${theme.code}-1\\.png`))
      await page.screenshot({ path: path.join(output, `${theme.code}-390.png`), fullPage: true })
    }

    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    }
    assert.deepEqual(errors, [])
    console.log('PASS: one player renders all five tone themes and stays usable at 320/390/430 widths')
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
