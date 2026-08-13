import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { rendererModeFor, applyExclusiveChoice, safetyFlowForAnswer } from '../common/questionnaire-rules.js'

// Canonical questionnaire (Frozen contract data source). Read via fs so the
// ESM JSON import in common/questionnaire-data.js is not exercised here.
const questionnaire = JSON.parse(
  readFileSync(new URL('../../knowledge/questionnaire-v2.1.json', import.meta.url), 'utf8')
)

const byId = (id) => questionnaire.questions.find((q) => q.question_id === id)
const q17 = byId('q17_duration')
const q18 = byId('q18_daily_impact')
const q19 = byId('q19_self_harm')
const q20 = byId('q20_emergency')
const q16 = byId('q16_physical_signals')

const DURATION_OPTIONS = [
  'less_than_3_days',
  '3_to_6_days',
  '1_to_2_weeks',
  '2_weeks_to_1_month',
  '1_to_3_months',
  'over_3_months',
  'recurrent_unclear',
]

test('20 questions walk in order 1..20 and every required question has options', () => {
  assert.equal(questionnaire.total_questions, 20)
  assert.equal(questionnaire.questions.length, 20)
  assert.deepEqual(
    questionnaire.questions.map((q) => q.order),
    Array.from({ length: 20 }, (_, i) => i + 1)
  )
  for (const q of questionnaire.questions) {
    assert.ok(Array.isArray(q.options) && q.options.length > 0, `${q.question_id} must have selectable options`)
  }
})

test('every question maps to a concrete renderer mode (no blank deadlock)', () => {
  const MODES = new Set(['visual', 'multi', 'button-row', 'button-grid', 'button-list'])
  for (const q of questionnaire.questions) {
    const mode = rendererModeFor(q)
    assert.ok(MODES.has(mode), `${q.question_id} (type=${q.type}) must render; got ${mode}`)
  }
})

test('q17 duration_choice renders button-row with the 7 Frozen options', () => {
  assert.equal(q17.type, 'duration_choice')
  assert.equal(q17.ui.layout, 'button-row')
  assert.equal(rendererModeFor(q17), 'button-row')
  assert.deepEqual(q17.options.map((o) => o.value), DURATION_OPTIONS)
})

test('q18 frequency_0_4 renders button-row with 5 levels', () => {
  assert.equal(q18.type, 'frequency_0_4')
  assert.equal(rendererModeFor(q18), 'button-row')
  assert.equal(q18.options.length, 5)
})

test('q19 self-harm is single_choice safety with 5 options', () => {
  assert.equal(q19.type, 'single_choice')
  assert.equal(q19.safety_only, true)
  assert.equal(rendererModeFor(q19), 'button-row')
  assert.equal(q19.options.length, 5)
})

test('q20 emergency is multi_choice safety with 6 options and none mutex', () => {
  assert.equal(q20.type, 'multi_choice')
  assert.equal(q20.safety_only, true)
  assert.equal(rendererModeFor(q20), 'multi')
  assert.equal(q20.options.length, 6)
  assert.equal(q20.mutually_exclusive_value, 'none')
})

test('q16 and q20 none option is mutually exclusive with other choices', () => {
  assert.equal(q16.mutually_exclusive_value, 'none')
  assert.deepEqual(applyExclusiveChoice('q16_physical_signals', ['neck_tension'], 'none'), ['none'])
  assert.deepEqual(applyExclusiveChoice('q16_physical_signals', ['none'], 'neck_tension'), ['neck_tension'])
  assert.deepEqual(applyExclusiveChoice('q20_emergency', ['severe_chest_pain'], 'none'), ['none'])
  assert.deepEqual(applyExclusiveChoice('q20_emergency', ['none'], 'severe_chest_pain'), ['severe_chest_pain'])
})

test('q19/q20 safety semantics: only non-never / non-none answers flag safety', () => {
  assert.equal(safetyFlowForAnswer('q19_self_harm', 'never'), null)
  assert.equal(safetyFlowForAnswer('q19_self_harm', 'specific_plan'), 'SAFETY_SELF_HARM')
  assert.equal(safetyFlowForAnswer('q20_emergency', ['none']), null)
  assert.equal(safetyFlowForAnswer('q20_emergency', ['severe_chest_pain']), 'SAFETY_EMERGENCY_PHYSICAL')
})

test('questionnaire-v2 renderer is wired to the generic rendererModeFor', () => {
  const source = readFileSync(new URL('../pages/questionnaire-v2/questionnaire-v2.vue', import.meta.url), 'utf8')
  assert.match(source, /rendererModeFor/)
  assert.match(source, /rendererMode\(\)/)
  assert.match(source, /isCheckboxGrid\(\) \{ return this\.rendererMode === "multi" \}/)
})

test('narrative page never shows misleading 0-evidence / 0% confidence before Assessment', () => {
  const source = readFileSync(new URL('../pages/narrative/narrative.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /evidence_count/)
  assert.doesNotMatch(source, /条证据/)
  assert.doesNotMatch(source, /提取置信度/)
  assert.doesNotMatch(source, /已处理完成/)
  assert.match(source, /描述已记录/)
  assert.match(source, /结合接下来的问卷/)
})

test('no browser-only API leaks into the Android/H5 shared pages', () => {
  for (const rel of ['../pages/narrative/narrative.vue', '../pages/questionnaire-v2/questionnaire-v2.vue']) {
    const source = readFileSync(new URL(rel, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /\bwindow\./, `${rel} must not use window.*`)
    assert.doesNotMatch(source, /\bdocument\./, `${rel} must not use document.*`)
    assert.doesNotMatch(source, /\bFormData\b/, `${rel} must not use browser FormData`)
  }
})
