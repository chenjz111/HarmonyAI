import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  rendererModeFor, severityScaleFor, isDirectionalComplete, serializeDirectional,
  serializeAnswer, isAnswerComplete, applyExclusiveChoice,
} from '../common/questionnaire-rules.js'

const questionnaire = JSON.parse(readFileSync(
  new URL('../../knowledge/questionnaire-v2.1.json', import.meta.url), 'utf8'
))
const byId = (id) => questionnaire.questions.find((q) => q.question_id === id)
const q03 = byId('q03_tension_worry')
const q14 = byId('q14_low_energy')
const q15 = byId('q15_appetite_change')
const q16 = byId('q16_physical_signals')
const q17 = byId('q17_duration')
const q18 = byId('q18_daily_impact')
const q19 = byId('q19_self_harm')
const q20 = byId('q20_emergency')

function records(answers) {
  return questionnaire.questions.map((q) => {
    const { value, score } = serializeAnswer(q, answers[q.question_id])
    return { question_id: q.question_id, value, type: q.type, ...(score === undefined ? {} : { score }) }
  })
}
function fullAnswers() {
  return Object.fromEntries(questionnaire.questions.map((q) => {
    const first = q.options[0]
    if (q.type === 'visual_single') return [q.question_id, { value: first.value, score: first.score }]
    if (q.type === 'multi_choice') return [q.question_id, [first.value]]
    if (q.severity_scale) return [q.question_id, { direction: 'decrease', severity: 3 }]
    return [q.question_id, first.value]
  }))
}

test('q15 stays single_choice and uses directional renderer with severity 1-4', () => {
  assert.equal(q15.type, 'single_choice')
  assert.equal(rendererModeFor(q15), 'directional')
  assert.deepEqual(severityScaleFor(q15).map((step) => step.value), [1, 2, 3, 4])
})
test('full q01-q20 serialization preserves ids and frozen q15 shape', () => {
  const result = records(fullAnswers())
  assert.equal(result.length, 20)
  assert.deepEqual(result.map((item) => item.question_id), questionnaire.questions.map((q) => q.question_id))
  assert.deepEqual(result.find((item) => item.question_id === q15.question_id).value, { direction: 'decrease', severity: 3 })
})
test('q15 increase/decrease serializes to object', () => {
  assert.deepEqual(serializeDirectional('decrease', 3), { direction: 'decrease', severity: 3 })
  assert.deepEqual(serializeAnswer(q15, { direction: 'increase', severity: 2 }), { value: { direction: 'increase', severity: 2 } })
})
test('q15 none forces severity zero', () => assert.deepEqual(serializeDirectional('none', 4), { direction: 'none', severity: 0 }))
test('q15 accepts none/zero and directional severity 1-4', () => {
  assert.equal(isDirectionalComplete({ direction: 'none', severity: 0 }), true)
  assert.equal(isDirectionalComplete({ direction: 'decrease', severity: 1 }), true)
  assert.equal(isDirectionalComplete({ direction: 'increase', severity: 4 }), true)
})
test('q15 rejects missing direction or severity', () => {
  assert.equal(isDirectionalComplete({ severity: 2 }), false)
  assert.equal(isDirectionalComplete({ direction: 'decrease' }), false)
})
test('q15 rejects invalid combinations', () => {
  assert.equal(isDirectionalComplete({ direction: 'other', severity: 2 }), false)
  assert.equal(isDirectionalComplete({ direction: 'decrease', severity: 0 }), false)
  assert.equal(isDirectionalComplete({ direction: 'none', severity: 2 }), false)
})
test('frequency zero is answered and preserved', () => {
  assert.equal(isAnswerComplete(q03, 0), true)
  assert.deepEqual(serializeAnswer(q03, 0), { value: 0 })
})
test('q14 visual answer keeps value and score', () => assert.deepEqual(serializeAnswer(q14, { value: 'half', score: 2 }), { value: 'half', score: 2 }))
test('q16 remains array and empty array is unanswered', () => {
  assert.deepEqual(serializeAnswer(q16, ['none']), { value: ['none'] })
  assert.equal(isAnswerComplete(q16, []), false)
})
test('q17 remains flat duration enum', () => assert.deepEqual(serializeAnswer(q17, '1_to_2_weeks'), { value: '1_to_2_weeks' }))
test('q18 remains integer', () => assert.deepEqual(serializeAnswer(q18, 0), { value: 0 }))
test('q19 never remains valid', () => {
  assert.equal(isAnswerComplete(q19, 'never'), true)
  assert.deepEqual(serializeAnswer(q19, 'never'), { value: 'never' })
})
test('q20 none stays exclusive with emergency choices', () => {
  assert.deepEqual(serializeAnswer(q20, ['none']), { value: ['none'] })
  assert.deepEqual(applyExclusiveChoice(q20.question_id, ['none'], 'severe_chest_pain'), ['severe_chest_pain'])
  assert.deepEqual(applyExclusiveChoice(q20.question_id, ['severe_chest_pain'], 'none'), ['none'])
})
