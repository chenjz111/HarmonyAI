const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const output = path.resolve(__dirname, '../../artifacts/feedback-reference')
  fs.mkdirSync(output, { recursive: true })
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
    page.setDefaultTimeout(10000)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      return ['127.0.0.1', 'localhost'].includes(url.hostname) ? route.continue() : route.abort()
    })

    await page.goto('http://127.0.0.1:5181/?harmonyai_demo=1#/pages/v3-feedback/v3-feedback')
    await page.getByText('聆听反馈', { exact: true }).waitFor()
    assert.equal(await page.locator('.feedback-section-card').count(), 5)
    assert.equal(await page.locator('.feedback-option-image').count(), 16)
    assert.deepEqual(
      await page.locator('.feedback-options').evaluateAll(nodes => nodes.map(node => node.children.length)),
      [4, 3, 5, 4],
    )
    assert.equal(await page.getByText('（可多选）', { exact: true }).count(), 2)
    assert.equal(await page.locator('.submit-arrow').count(), 0)
    assert.equal(await page.locator('.comment-textarea textarea').getAttribute('maxlength'), '200')

    const singleOptions = page.locator('.feedback-section-card').nth(0).locator('.feedback-option')
    await singleOptions.nth(0).click()
    await singleOptions.nth(1).click()
    assert.equal(await singleOptions.filter({ has: page.locator('.feedback-option-selected-marker') }).count(), 1)

    const likedOptions = page.locator('.feedback-section-card').nth(2).locator('.feedback-option')
    await likedOptions.nth(0).click()
    await likedOptions.nth(1).click()
    assert.equal(await likedOptions.filter({ has: page.locator('.feedback-option-selected-marker') }).count(), 2)

    const adjustmentOptions = page.locator('.feedback-section-card').nth(3).locator('.feedback-option')
    await adjustmentOptions.nth(0).click()
    await adjustmentOptions.nth(1).click()
    assert.equal(await adjustmentOptions.filter({ has: page.locator('.feedback-option-selected-marker') }).count(), 2)

    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      const type = await page.evaluate(() => ({
        question: Number.parseFloat(getComputedStyle(document.querySelector('.feedback-question')).fontSize),
        label: Number.parseFloat(getComputedStyle(document.querySelector('.feedback-option-label')).fontSize),
        subtitle: Number.parseFloat(getComputedStyle(document.querySelector('.feedback-option-subtitle')).fontSize),
      }))
      assert.ok(type.question >= 16)
      assert.ok(type.label >= 13)
      assert.ok(type.subtitle >= 11)
      for (const group of await page.locator('.feedback-options').all()) {
        const tops = await group.locator('.feedback-option').evaluateAll(nodes => nodes.map(node => Math.round(node.getBoundingClientRect().top)))
        assert.equal(new Set(tops).size, 1)
      }
      await page.screenshot({ path: path.join(output, `feedback-${width}.png`), fullPage: true })
    }
    assert.equal(await page.getByText('提交反馈', { exact: true }).count(), 1)
    assert.deepEqual(errors, [])
    console.log('PASS: feedback page matches the approved 4/3/5/4 mobile card layout at 320/390/430 widths')
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
