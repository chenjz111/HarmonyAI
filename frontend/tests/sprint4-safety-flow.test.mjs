import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'

import {
  COMFORT_FEEDBACK_OPTIONS,
  comfortFeedbackState,
  safetyDestination,
  safetySupportState,
  safetyVerificationPayload,
} from '../common/safety-flow.js'

test('ambiguous OCR safety stays on the final assessment confirmation page', () => {
  const assessment = { assessment_id: 'a1', revision: 2, safety_status: 'needs_verification' }
  assert.equal(safetyDestination(assessment), '')
  assert.deepEqual(safetyVerificationPayload(assessment, 'past_resolved'), { revision: 2, resolution: 'past_resolved' })
})

test('mental safety support offers only non-personalized comfort audio', () => {
  const state = safetySupportState({ safety_status: 'confirmed_mental_health_risk', comfort_audio_allowed: true })
  assert.equal(state.mode, 'mental')
  assert.equal(state.comfortAudioVisible, true)
  assert.equal(state.personalizedPrescriptionAllowed, false)
})

test('acute physical risk is emergency first and hides comfort audio', () => {
  const state = safetySupportState({ safety_status: 'confirmed_acute_physical_risk', comfort_audio_allowed: false })
  assert.equal(state.mode, 'acute')
  assert.equal(state.comfortAudioVisible, false)
  assert.equal(state.personalizedPrescriptionAllowed, false)
})

test('real pages wire dedicated API and never autoplay comfort audio', () => {
  const result = readFileSync(new URL('../pages/assessment-result/assessment-result.vue', import.meta.url), 'utf8')
  const support = readFileSync(new URL('../pages/safety-support/safety-support.vue', import.meta.url), 'utf8')
  const api = readFileSync(new URL('../common/api-v2.js', import.meta.url), 'utf8')
  const pages = readFileSync(new URL('../pages.json', import.meta.url), 'utf8')
  assert.match(result, /safetyDestination/)
  assert.match(result, /verifyAssessmentSafety/)
  assert.match(support, /requestComfortAudio/)
  assert.equal(/\.play\(\)/.test(support.split('async requestAudio')[1].split('toggleAudio')[0]), false)
  assert.match(api, /safety-verification/)
  assert.match(api, /comfort-audio/)
  assert.doesNotMatch(pages, /pages\/safety-verification\/safety-verification/)
  assert.match(pages, /pages\/safety-support\/safety-support/)
})

test('safety support copy avoids medicalized music wording', () => {
  const support = readFileSync(new URL('../pages/safety-support/safety-support.vue', import.meta.url), 'utf8')
  const safetyUi = support
  for (const forbidden of ['个性化音乐处方', '个性化处方', '治疗音乐', '音乐处方', '疗愈方案', '疗愈音乐']) {
    assert.equal(safetyUi.includes(forbidden), false, `forbidden Safety UI wording: ${forbidden}`)
  }
  assert.match(support, /安抚音频不能替代专业帮助/)
})

test('comfort feedback always remains in Safety Support without clearing risk', () => {
  assert.deepEqual(
    COMFORT_FEEDBACK_OPTIONS.map((item) => item.label),
    ['稍微稳定一些', '没有变化', '感觉更糟', '我现在需要帮助'],
  )

  for (const item of COMFORT_FEEDBACK_OPTIONS) {
    const state = comfortFeedbackState(item.value)
    assert.equal(state.destination, '/pages/safety-support/safety-support')
    assert.equal(state.clearsSafety, false)
  }

  assert.equal(comfortFeedbackState('slightly_stable').prominentHelp, false)
  assert.equal(comfortFeedbackState('no_change').prominentHelp, false)
  assert.equal(comfortFeedbackState('feeling_worse').prominentHelp, true)
  assert.equal(comfortFeedbackState('need_help_now').prominentHelp, true)
})

test('comfort feedback page does not call ordinary confirmation or prescription paths', () => {
  const support = readFileSync(new URL('../pages/safety-support/safety-support.vue', import.meta.url), 'utf8')
  assert.match(support, /comfortFeedbackState/)
  assert.doesNotMatch(support, /confirmAssessment|runWorkflow|requestMusic|personalizedPrescription/)
})

test('comfort feedback appears only after audio playback ends', () => {
  const support = readFileSync(new URL('../pages/safety-support/safety-support.vue', import.meta.url), 'utf8')
  assert.match(support, /v-if="audio && showFeedback"/)
  assert.match(support, /context\.onEnded\(\(\) => \{[\s\S]*showFeedback = true/)
})
