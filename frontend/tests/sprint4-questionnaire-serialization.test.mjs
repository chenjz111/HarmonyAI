import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  rendererModeFor,
  severityScaleFor,
  isDirectionalComplete,
  serializeDirectional,
  serializeAnswer,
  isAnswerComplete,
  applyExclusiveChoice,
} from '../common/questionnaire-rules.js'

const questionnaire = JSON.parse(
  readFileSync(new URL('../../knowledge/questionnaire-v2.1.json', import.meta.url), 'utf8')
)

const byId = (id) => questionnaire.questions.find((q) => q.question_id === id)
const q03 = byId('q03_tension_worry')
const q14 = byId('q14_low_energy')
const q15 = byId('q15_appetite_change')
const q16 = byId('q16_physical_signals')
const q17 = byId('q17_duration')
const q18 = byId('q18_daily_impact')
const q19 = byId('q19_self_harm')
const q20 = byId('q20_emergency')

// 复刻 questionnaire-v2.vue handleSubmit 的序列化逻辑（纯函数版本）。
function buildAnswerRecords(questions, answers) {
  return questions.map((q) => {
    const { value, score } = serializeAnswer(q, answers[q.question_id])
    return { question_id: q.question_id, value, type: q.type, ...(score === undefined ? {} : { score }) }
  })
}

// 一组“用户从头做完 20 题”的原始答案（与前端内部存储结构一致）。
function fullRawAnswers() {
  const answers = {}
  for (const q of questionnaire.questions) {
    const first = q.options[0].value
    if (q.type === 'visual_single') {
      answers[q.question_id] = { value: first, score: q.options[0].score }
    } else if (q.type === 'multi_choice') {
      answers[q.question_id] = [first]
    } else if (q.severity_scale) {
      answers[q.question_id] = { direction: 'decrease', severity: 3 }
    } else {
      answers[q.question_id] = first
    }
  }
  return answers
}

test('q15 renders as directional (single_choice + severity_scale) and exposes a 1-4 severity scale', () => {
  assert.equal(q15.type, 'single_choice')
  assert.ok(q15.severity_scale)
  assert.equal(rendererModeFor(q15), 'directional')
  assert.deepEqual(severityScaleFor(q15).map((s) => s.value), [1, 2, 3, 4])
  assert.deepEqual(q15.options.map((o) => o.value), ['decrease', 'increase', 'none'])
})

test('full 20-question submission serializes every question with the frozen value shape', () => {
  const records = buildAnswerRecords(questionnaire.questions, fullRawAnswers())
  assert.equal(records.length, 20)
  assert.deepEqual(
    records.map((r) => r.question_id).sort(),
    questionnaire.questions.map((q) => q.question_id).sort()
  )
  const q15Record = records.find((r) => r.question_id === 'q15_appetite_change')
  assert.deepEqual(q15Record.value, { direction: 'decrease', severity: 3 })
})

test('q15 directional: decrease+severity serializes to {direction, severity}', () => {
  assert.deepEqual(serializeDirectional('decrease', 3), { direction: 'decrease', severity: 3 })
  assert.deepEqual(serializeAnswer(q15, { direction: 'increase', severity: 2 }), {
    value: { direction: 'increase', severity: 2 },
  })
})

test('q15 directional: none forces severity 0 (never incomplete, never non-zero)', () => {
  assert.deepEqual(serializeDirectional('none', 99), { direction: 'none', severity: 0 })
  assert.deepEqual(serializeAnswer(q15, { direction: 'none', severity: 0 }), {
    value: { direction: 'none', severity: 0 },
  })
})

test('q15 directional completeness: none-only and decrease+severity are complete', () => {
  assert.equal(isDirectionalComplete({ direction: 'none', severity: 0 }), true)
  assert.equal(isDirectionalComplete({ direction: 'decrease', severity: 3 }), true)
  assert.equal(isAnswerComplete(q15, { direction: 'none', severity: 0 }), true)
})

test('q15 directional completeness: missing/invalid severity stays blocked', () => {
  assert.equal(isDirectionalComplete({ direction: 'decrease' }), false)
  assert.equal(isDirectionalComplete({ direction: 'decrease', severity: 0 }), false)
  assert.equal(isDirectionalComplete({ direction: 'none', severity: 3 }), false)
  assert.equal(isDirectionalComplete({ direction: 'other', severity: 1 }), false)
  assert.equal(isAnswerComplete(q15, undefined), false)
})

test('frequency_0_4 value=0 is a legal answered value (falsy-value audit)', () => {
  assert.equal(isAnswerComplete(q03, 0), true)
  assert.deepEqual(serializeAnswer(q03, 0), { value: 0 })
  const records = buildAnswerRecords([q03], { [q03.question_id]: 0 })
  assert.equal(records[0].value, 0)
})

test('duration_choice (q17) stays a flat string and is never dropped', () => {
  assert.equal(q17.type, 'duration_choice')
  assert.deepEqual(serializeAnswer(q17, '1_to_2_weeks'), { value: '1_to_2_weeks' })
  assert.equal(isAnswerComplete(q17, '1_to_2_weeks'), true)
})

test('visual_single (q14) still expands to value + independent score', () => {
  assert.deepEqual(serializeAnswer(q14, { value: 'half', score: 2 }), { value: 'half', score: 2 })
})

test('q19 never is a legal single_choice answer', () => {
  assert.deepEqual(serializeAnswer(q19, 'never'), { value: 'never' })
  assert.equal(isAnswerComplete(q19, 'never'), true)
})

test('q20 none-only is valid; none + emergency is mutually exclusive', () => {
  assert.deepEqual(serializeAnswer(q20, ['none']), { value: ['none'] })
  assert.equal(isAnswerComplete(q20, ['none']), true)
  assert.deepEqual(applyExclusiveChoice('q20_emergency', ['none'], 'severe_chest_pain'), ['severe_chest_pain'])
  assert.deepEqual(applyExclusiveChoice('q20_emergency', ['severe_chest_pain'], 'none'), ['none'])
})

test('q16 multi_choice keeps an array and empty array is treated as unanswered', () => {
  assert.deepEqual(serializeAnswer(q16, ['neck_tension']), { value: ['neck_tension'] })
  assert.equal(isAnswerComplete(q16, []), false)
  assert.equal(isAnswerComplete(q16, ['none']), true)
})

test('q18 frequency_0_4 serializes an integer 0-4', () => {
  assert.equal(q18.type, 'frequency_0_4')
  assert.deepEqual(serializeAnswer(q18, 3), { value: 3 })
})

test('renderer maps every question to a concrete mode including directional', () => {
  const MODES = new Set(['visual', 'multi', 'directional', 'button-row', 'button-grid', 'button-list'])
  for (const q of questionnaire.questions) {
    assert.ok(MODES.has(rendererModeFor(q)), `${q.question_id} (type=${q.type}) must render`)
  }
})
