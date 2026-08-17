import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  applyGoalChoice,
  applyPhysicalChoice,
  isAnswerComplete,
  serializeAnswer,
} from '../common/questionnaire-rules.js'

const questionnaireV22 = JSON.parse(
  readFileSync(new URL('../../knowledge/questionnaire-v2.2.json', import.meta.url), 'utf8'),
)

const byId = (id) => questionnaireV22.questions.find((question) => question.question_id === id)

test('questionnaire v2.2 keeps 20 questions and the frozen safety questions', () => {
  assert.equal(questionnaireV22.schema_version, 'questionnaire_v2.2')
  assert.equal(questionnaireV22.total_questions, 20)
  assert.equal(byId('q19_self_harm').safety_only, true)
  assert.equal(byId('q20_emergency').safety_only, true)
})

test('Q1 requires one primary goal and permits one different secondary goal', () => {
  const question = byId('q01_user_goal')
  let answer = applyGoalChoice(undefined, 'relaxation')
  assert.deepEqual(answer, {
    primary_goal: 'relaxation',
    secondary_goal: null,
    custom_goal_text: null,
  })
  answer = applyGoalChoice(answer, 'sleep')
  assert.equal(answer.primary_goal, 'relaxation')
  assert.equal(answer.secondary_goal, 'sleep')
  answer = applyGoalChoice(answer, 'focus')
  assert.equal(answer.primary_goal, 'relaxation')
  assert.equal(answer.secondary_goal, 'focus')
  assert.equal(isAnswerComplete(question, answer), true)
})

test('Q1 other requires custom text before continuing and serializes structured value', () => {
  const question = byId('q01_user_goal')
  const incomplete = applyGoalChoice(undefined, 'other')
  assert.equal(isAnswerComplete(question, incomplete), false)
  const complete = { ...incomplete, custom_goal_text: '希望减少睡前胡思乱想' }
  assert.equal(isAnswerComplete(question, complete), true)
  assert.deepEqual(serializeAnswer(question, complete), { value: complete })
})

test('Q14 exposes five ordered energy levels with the intended scores', () => {
  assert.deepEqual(
    byId('q14_low_energy').options.map(({ value, score }) => [value, score]),
    [['full', 0], ['three_quarters', 1], ['half', 2], ['quarter', 3], ['empty', 4]],
  )
})

test('Q16 keeps none exclusive and requires free text only for other', () => {
  const question = byId('q16_physical_signals')
  let answer = applyPhysicalChoice(undefined, 'stomach_discomfort')
  answer = applyPhysicalChoice(answer, 'other')
  assert.equal(isAnswerComplete(question, answer), false)
  answer = { ...answer, custom_text: '最近偶尔耳鸣' }
  assert.equal(isAnswerComplete(question, answer), true)
  answer = applyPhysicalChoice(answer, 'none')
  assert.deepEqual(answer, { selected: ['none'], custom_text: null })
})

test('real questionnaire page submits v2.2 and presents Q19/Q20 as final safety confirmation', () => {
  const source = readFileSync(new URL('../pages/questionnaire-v2/questionnaire-v2.vue', import.meta.url), 'utf8')
  assert.match(source, /questionnaireV22/)
  assert.match(source, /schema_version:\s*['"]questionnaire_v2\.2['"]/)
  assert.match(source, /最后两题用于安全确认/)
  assert.match(source, /不参与普通状态或音乐评分，只用于安全确认/)
  assert.match(source, /custom_goal_text/)
  assert.match(source, /custom_text/)
})
