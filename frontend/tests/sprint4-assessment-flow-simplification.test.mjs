import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const assessmentPage = readFileSync(
  new URL('../pages/assessment-result/assessment-result.vue', import.meta.url),
  'utf8',
)
const safetyFlow = readFileSync(new URL('../common/safety-flow.js', import.meta.url), 'utf8')
const materialPage = readFileSync(new URL('../pages/material/material.vue', import.meta.url), 'utf8')
const assessmentTemplate = assessmentPage.split('<script>')[0]

test('assessment result is one plain-language confirmation page without internal metrics', () => {
  assert.match(assessmentPage, /确认一下我们对你当前状态的理解/)
  assert.match(assessmentPage, /基本符合，继续/)
  assert.match(assessmentPage, /有些地方不对，我要修改/)
  assert.match(assessmentPage, /当前已使用问卷规则完成基础分析/)
  assert.match(assessmentPage, /最近的情况/)
  assert.match(assessmentPage, /本次音乐目标/)
  assert.match(assessmentPage, /recentContextText/)
  assert.match(assessmentPage, /musicGoalText/)
  for (const internalCopy of ['可信度', '证据来源', '冲突信息', '缺失信息', '补充追问']) {
    assert.equal(assessmentTemplate.includes(internalCopy), false, `internal copy leaked: ${internalCopy}`)
  }
  assert.doesNotMatch(assessmentTemplate, /assessment\.confidence\s*\*\s*100/)
  assert.doesNotMatch(materialPage.split('<script>')[0], /置信度|confidence/)
})

test('needs_verification is embedded in the final confirmation page', () => {
  assert.match(assessmentPage, /verifyAssessmentSafety/)
  assert.match(assessmentPage, /safetyVerificationPayload/)
  assert.match(assessmentPage, /这条材料信息描述的是现在的你吗/)
  assert.match(assessmentPage, /暂时无法确认/)
  assert.match(safetyFlow, /needs_verification[\s\S]*return ''/)
  assert.doesNotMatch(assessmentPage, /pages\/safety-verification\/safety-verification/)
})

test('ordinary confirmation keeps backend revision and workflow authority', () => {
  assert.match(assessmentPage, /confirmAssessment/)
  assert.match(assessmentPage, /workflowPayload/)
  assert.match(assessmentPage, /runWorkflow/)
  assert.match(assessmentPage, /assessment_revision/)
})
