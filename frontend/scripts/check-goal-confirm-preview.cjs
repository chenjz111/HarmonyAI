const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function answerQuestionnaire(page) {
  await page.goto('http://127.0.0.1:5181/?harmonyai_demo=1#/pages/entry/entry')
  await page.locator('.choice-card').nth(1).click()
  await page.getByText('Q1', { exact: true }).waitFor({ timeout: 10000 })
  for (let step = 1; step <= 5; step += 1) {
    const cards = page.locator('.q-card')
    await cards.nth(0).locator('.q-option').first().click()
    await cards.nth(1).locator('.q-option').first().click()
    await page.getByText(step === 5 ? '完成问卷' : '下一题', { exact: true }).click()
    if (step < 5) await page.getByText(`${step + 1}/5`, { exact: true }).waitFor()
  }
  await page.getByText('疗愈诉求', { exact: true }).waitFor({ timeout: 10000 })
}

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const output = path.resolve(__dirname, '../../artifacts/goal-confirm-reference')
  fs.mkdirSync(output, { recursive: true })
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      return ['127.0.0.1', 'localhost'].includes(url.hostname) ? route.continue() : route.abort()
    })

    await answerQuestionnaire(page)
    await page.getByText('选择你的诉求', { exact: true }).waitFor()
    assert.equal(await page.locator('.intent-card').count(), 6)
    assert.equal(await page.locator('.intent-icon-image').count(), 6)
    assert.equal(await page.getByText('其他', { exact: true }).count(), 0)
    assert.equal(await page.locator('textarea').count(), 0)
    assert.equal(await page.locator('.action-arrow').count(), 0)
    await page.getByText('完成', { exact: true }).waitFor()
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `goal-${width}.png`), fullPage: true })
    }

    await page.getByText('暂时跳过', { exact: true }).click()
    await page.getByText('完成近期状态总结', { exact: true }).waitFor({ timeout: 10000 })
    assert.equal(await page.locator('.summary-icon-image img').getAttribute('src'), '/static/v31-goal/intent-2.png')
    const summaryIconBox = await page.locator('.summary-icon-image').boundingBox()
    assert.ok(summaryIconBox && summaryIconBox.width <= 64 && summaryIconBox.height <= 64)
    assert.equal(await page.locator('.section').count(), 0)
    assert.equal(await page.getByText('选择修改方式', { exact: true }).count(), 0)
    await page.getByText('有些地方不对，我要修改', { exact: true }).click()
    const editor = page.locator('.inline-summary-editor textarea')
    await editor.waitFor()
    assert.equal(await page.locator('.confirm-card').count(), 1)
    assert.equal(await page.getByText('直接编辑文本', { exact: true }).count(), 0)
    assert.equal(await page.getByText('调整各项程度', { exact: true }).count(), 0)
    assert.equal(await editor.evaluate(element => document.activeElement === element), true)
    assert.equal(await editor.evaluate(element => element.selectionStart === element.value.length), true)
    await page.getByText('取消修改', { exact: true }).waitFor()
    await page.getByText('保存修改并继续', { exact: true }).waitFor()
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, `confirm-edit-${width}.png`), fullPage: true })
    }
    assert.deepEqual(errors, [])
    console.log('PASS: healing intent and inline summary editing at 320/390/430 widths')
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
