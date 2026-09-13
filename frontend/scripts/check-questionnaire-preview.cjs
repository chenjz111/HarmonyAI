const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const output = path.resolve(__dirname, '../../artifacts/questionnaire-reference')
  fs.mkdirSync(output, { recursive: true })
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      return ['127.0.0.1', 'localhost'].includes(url.hostname) ? route.continue() : route.abort()
    })
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      await page.goto('http://127.0.0.1:5181/?harmonyai_demo=1#/pages/entry/entry')
      await page.locator('.choice-card').nth(1).click()
      await page.getByText('Q1', { exact: true }).waitFor({ timeout: 10000 })
      assert.equal(await page.locator('.nav-arrow').count(), 0)
      assert.equal(await page.getByText('怒', { exact: true }).count(), 0)
      assert.equal(await page.getByText('喜', { exact: true }).count(), 0)
      assert.equal(await page.locator('.q-score').count(), 0)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `q1q2-${width}.png`), fullPage: true })
    }
    await page.locator('.q-card').nth(0).locator('.q-option').first().click()
    await page.locator('.q-card').nth(1).locator('.q-option').first().click()
    await page.getByText('下一题', { exact: true }).click()
    await page.getByText('2/5', { exact: true }).waitFor()
    await page.getByText('上一题', { exact: true }).waitFor()
    assert.equal(await page.locator('.option-image').count(), 10)
    const q34Sources = await page.locator('.option-image').evaluateAll(images => images.map(image => image.querySelector('img')?.getAttribute('src')))
    assert.deepEqual(q34Sources, [
      '/static/v31-questionnaire/q3-0.png', '/static/v31-questionnaire/q3-1.png',
      '/static/v31-questionnaire/q3-2.png', '/static/v31-questionnaire/q3-3.png',
      '/static/v31-questionnaire/q3-4.png', '/static/v31-questionnaire/q4-0.png',
      '/static/v31-questionnaire/q4-1.png', '/static/v31-questionnaire/q4-2.png',
      '/static/v31-questionnaire/q4-3.png', '/static/v31-questionnaire/q4-4.png',
    ])
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `q3q4-${width}.png`), fullPage: true })
    }
    await page.locator('.q-card').nth(0).locator('.q-option').first().click()
    await page.locator('.q-card').nth(1).locator('.q-option').first().click()
    await page.getByText('下一题', { exact: true }).click()
    await page.getByText('3/5', { exact: true }).waitFor()
    assert.equal(await page.locator('.option-image').count(), 10)
    await page.getByText('都很少出现，很轻松', { exact: true }).waitFor()
    assert.equal(await page.locator('.q-option-none').count(), 1)
    assert.equal(await page.locator('.multi-hint').count(), 1)
    assert.equal(await page.locator('.q-card').nth(1).locator('.q-option').count(), 5)
    assert.equal(await page.locator('.q-card').nth(1).locator('.q-option').evaluateAll(options => new Set(options.map(option => option.getBoundingClientRect().top)).size), 1)
    assert.equal(await page.locator('.q-card').nth(1).locator('.q-option').last().locator('img').getAttribute('src'), '/static/v31-questionnaire/q7-4.png')
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `q5q6-${width}.png`), fullPage: true })
    }
    await page.locator('.q-card').nth(0).locator('.q-option').first().click()
    await page.locator('.q-card').nth(1).locator('.q-option').first().click()
    await page.getByText('下一题', { exact: true }).click()
    await page.getByText('4/5', { exact: true }).waitFor()
    await page.getByText('身体状态', { exact: true }).waitFor()
    assert.equal(await page.locator('.option-image').count(), 10)
    assert.equal(await page.locator('.multi-hint').count(), 2)
    assert.deepEqual(await page.locator('.q-card').evaluateAll(cards => cards.map(card => card.querySelectorAll('.q-option').length)), [5, 5])
    assert.deepEqual(await page.locator('.q-card').evaluateAll(cards => cards.map(card => new Set([...card.querySelectorAll('.q-option')].map(option => option.getBoundingClientRect().top)).size)), [1, 1])
    const q78Sources = await page.locator('.option-image').evaluateAll(images => images.map(image => image.querySelector('img')?.getAttribute('src')))
    assert.deepEqual(q78Sources, [
      '/static/v31-questionnaire/q7-0.png', '/static/v31-questionnaire/q7-1.png',
      '/static/v31-questionnaire/q7-2.png', '/static/v31-questionnaire/q7-3.png',
      '/static/v31-questionnaire/q7-4.png', '/static/v31-questionnaire/q8-0.png',
      '/static/v31-questionnaire/q8-1.png', '/static/v31-questionnaire/q8-2.png',
      '/static/v31-questionnaire/q8-3.png', '/static/v31-questionnaire/q8-4.png',
    ])
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `q7q8-${width}.png`), fullPage: true })
    }
    await page.locator('.q-card').nth(0).locator('.q-option').first().click()
    await page.locator('.q-card').nth(1).locator('.q-option').first().click()
    await page.getByText('下一题', { exact: true }).click()
    await page.getByText('5/5', { exact: true }).waitFor()
    await page.getByText('完成问卷', { exact: true }).waitFor()
    assert.equal(await page.locator('.option-image').count(), 9)
    assert.equal(await page.locator('.multi-hint').count(), 2)
    assert.deepEqual(await page.locator('.q-card').evaluateAll(cards => cards.map(card => card.querySelectorAll('.q-option').length)), [5, 4])
    assert.deepEqual(await page.locator('.q-card').evaluateAll(cards => cards.map(card => new Set([...card.querySelectorAll('.q-option')].map(option => option.getBoundingClientRect().top)).size)), [1, 1])
    assert.equal(await page.locator('.nav-arrow').count(), 0)
    const q910Sources = await page.locator('.option-image').evaluateAll(images => images.map(image => image.querySelector('img')?.getAttribute('src')))
    assert.deepEqual(q910Sources, [
      '/static/v31-questionnaire/q9-0.png', '/static/v31-questionnaire/q9-1.png',
      '/static/v31-questionnaire/q9-2.png', '/static/v31-questionnaire/q9-3.png',
      '/static/v31-questionnaire/q9-4.png', '/static/v31-questionnaire/q10-0.png',
      '/static/v31-questionnaire/q10-1.png', '/static/v31-questionnaire/q10-2.png',
      '/static/v31-questionnaire/q10-3.png',
    ])
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `q9q10-${width}.png`), fullPage: true })
    }
    assert.deepEqual(errors, [])
    console.log('PASS: Q1-Q10 assets, one-row layouts, multi-select hints, navigation, and 320/390/430 screenshots')
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
