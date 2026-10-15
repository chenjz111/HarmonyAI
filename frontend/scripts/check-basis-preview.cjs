const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

async function reachBasis(page) {
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
  await page.getByText('暂时跳过', { exact: true }).click()
  await page.getByText('确认近期状态总结', { exact: true }).waitFor({ timeout: 10000 })
  await page.getByText('基本符合，继续', { exact: true }).click()
  await page.getByText('五音调适解析', { exact: true }).waitFor({ timeout: 10000 })
}

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const output = path.resolve(__dirname, '../../artifacts/basis-reference')
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

    await reachBasis(page)
    for (const title of ['近期状态', '状态解读', '调适依据', '本次五音配置', '音乐设计']) {
      await page.getByText(title, { exact: true }).waitFor()
    }
    assert.equal(await page.locator('.basis-section-card').count(), 5)
    assert.equal(await page.locator('.basis-icon-image').count(), 7)
    assert.equal(await page.locator('.tone-orb').count(), 5)
    assert.equal(await page.locator('.tone-orb--primary').count(), 1)
    assert.equal(await page.locator('.tone-orb--secondary').count(), 1)
    assert.equal(await page.locator('.design-card').count(), 4)
    await page.getByText('生成我的音乐', { exact: true }).waitFor()
    assert.equal(await page.locator('.stage-seal').count(), 0)
    assert.equal(await page.locator('.section-seal').count(), 0)

    for (const width of [320, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      const readableType = await page.evaluate(() => {
        const size = selector => Number.parseFloat(getComputedStyle(document.querySelector(selector)).fontSize)
        return {
          subtitle: size('.page-subtitle'),
          stateTag: size('.state-tag'),
          interpretation: size('.interpretation-text'),
          rationale: size('.rationale-source'),
          detailCopy: size('.tone-detail-copy'),
          paramValue: size('.param-value')
        }
      })
      assert.ok(readableType.subtitle >= 14)
      assert.ok(readableType.stateTag >= 13)
      assert.ok(readableType.interpretation >= 14)
      assert.ok(readableType.rationale >= 13)
      assert.ok(readableType.detailCopy >= 12)
      assert.ok(readableType.paramValue >= 14)
      const toneBottoms = await page.locator('.tone-orb').evaluateAll(nodes => nodes.map(node => Math.round(node.getBoundingClientRect().bottom)))
      assert.equal(new Set(toneBottoms).size, 1)
      const designTops = await page.locator('.design-card').evaluateAll(nodes => nodes.map(node => Math.round(node.getBoundingClientRect().top)))
      assert.equal(new Set(designTops).size, 2)
      await page.screenshot({ path: path.join(output, `basis-${width}.png`), fullPage: true })
    }
    assert.deepEqual(errors, [])
    console.log('PASS: five-tone analysis stays readable and uses a 2-by-2 music grid at 320/390/430 widths')
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
