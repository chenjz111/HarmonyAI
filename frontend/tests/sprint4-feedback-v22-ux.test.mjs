import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../pages/feedback-v2/feedback-v2.vue', import.meta.url), 'utf8')

test('change label is the only required feedback field and is a large 2x2 grid', () => {
  for (const label of ['明显好一些', '稍微好一些', '差不多', '感觉更不舒服']) {
    assert.match(page, new RegExp(label))
  }
  assert.match(page, /变化感受.*必填/s)
  assert.match(page, /change-card-grid/)
  assert.match(page, /grid-template-columns:\s*repeat\(2/)
  assert.match(page, /return Boolean\(this\.changeLabel\)/)
})

test('all other feedback groups are optional and include positive plus adjustment input', () => {
  assert.match(page, /整体满意度（选填）/)
  assert.match(page, /听前与听后状态（选填）/)
  assert.match(page, /喜欢的音乐特点（选填）/)
  assert.match(page, /希望下次调整（选填）/)
  assert.match(page, /还有什么想告诉我们？（选填）/)
  assert.match(page, /liked_features/)
  assert.match(page, /adjustment_preferences/)
  for (const preference of ['音量舒适', '调整音量', '调整环境音', '其他建议']) {
    assert.match(page, new RegExp(preference))
  }
})

test('optional ratings are omitted rather than filled with fake defaults', () => {
  assert.doesNotMatch(page, /preState:\s*\{\s*tension:\s*5/)
  assert.doesNotMatch(page, /continueUse:\s*['"]maybe['"]/)
  assert.match(page, /compactObject/)
})
