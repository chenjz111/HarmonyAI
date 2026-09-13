// Local-only demo verification; never sends production/provider traffic.
const { chromium } = require('playwright')
const { mkdirSync } = require('node:fs')
const { resolve } = require('node:path')
const assert = require('node:assert/strict')

async function main() {
  const output = resolve(__dirname, '../../artifacts/home-reference')
  mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
    await context.route('**/*', route => {
      const url = new URL(route.request().url())
      return ['127.0.0.1', 'localhost'].includes(url.hostname) || ['data:', 'blob:'].includes(url.protocol)
        ? route.continue() : route.abort()
    })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('http://127.0.0.1:5181/?harmonyai_demo=1#/pages/entry/entry')
    const cards = page.locator('.choice-card')
    page.on('framenavigated', frame => { if (frame === page.mainFrame()) console.log('NAV ' + frame.url()) })
    await cards.first().waitFor({ state: 'visible' })
    assert.equal(await cards.count(), 2)
    for (const width of [320, 360, 390, 430, 900]) {
      await page.setViewportSize({ width, height: 844 })
      await page.screenshot({ path: resolve(output, `home-${width}.png`), fullPage: true })
      const metrics = await page.evaluate(() => ({
        viewport: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        pageWidth: document.querySelector('.v31-home').getBoundingClientRect().width,
        cards: [...document.querySelectorAll('.choice-card')].map(el => ({ width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height })),
        background: getComputedStyle(document.querySelector('.v31-home')).backgroundImage,
      }))
      assert.ok(metrics.scrollWidth <= width, `horizontal overflow at ${width}`)
      assert.ok(metrics.pageWidth <= 430.5, `mobile canvas too wide at ${width}`)
      console.log(JSON.stringify({ width, ...metrics }))
    }
    await page.setViewportSize({ width: 390, height: 844 })
    for (const [index, route] of [[0, 'v3-material'], [1, 'v3-questionnaire'], [0, 'v3-material']]) {
      await cards.nth(index).click()
      await page.waitForURL(url => url.hash.includes(route))
      await page.getByText(index === 0 ? '开始识别' : '下一题', { exact: true }).waitFor({ state: 'visible' })
      console.log(`entry ${index}: ${route} PASS`)
      await page.goBack()
      await page.waitForURL(url => url.hash.includes('pages/entry/entry'))
      try {
        await cards.first().waitFor({ state: 'visible', timeout: 10000 })
      } catch (error) {
        await page.screenshot({ path: resolve(output, 'return-failure.png'), fullPage: true })
        console.log(JSON.stringify({ url: page.url(), errors, body: await page.locator('body').innerText(), cards: await cards.count() }))
        throw error
      }
    }
    await page.getByText('我的', { exact: true }).click()
    await page.getByText('功能升级中', { exact: true }).waitFor({ state: 'visible' })
    console.log('My upgrade placeholder PASS')
    assert.deepEqual(errors, [], 'browser runtime errors')
    console.log(`PASS: responsive screenshots and entry reselection; screenshots=${output}`)
  } finally {
    await browser.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
