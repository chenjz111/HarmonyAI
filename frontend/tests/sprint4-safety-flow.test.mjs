import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'

import { safetyDestination, safetySupportState, safetyVerificationPayload } from '../common/safety-flow.js'

test('ambiguous OCR safety routes to dedicated verification', () => {
  const assessment = { assessment_id: 'a1', revision: 2, safety_status: 'needs_verification' }
  assert.equal(safetyDestination(assessment), '/pages/safety-verification/safety-verification')
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
  const verify = readFileSync(new URL('../pages/safety-verification/safety-verification.vue', import.meta.url), 'utf8')
  const support = readFileSync(new URL('../pages/safety-support/safety-support.vue', import.meta.url), 'utf8')
  const api = readFileSync(new URL('../common/api-v2.js', import.meta.url), 'utf8')
  const pages = readFileSync(new URL('../pages.json', import.meta.url), 'utf8')
  assert.match(result, /safetyDestination/)
  assert.match(verify, /verifyAssessmentSafety/)
  assert.match(support, /requestComfortAudio/)
  assert.equal(/\.play\(\)/.test(support.split('async requestAudio')[1].split('toggleAudio')[0]), false)
  assert.match(api, /safety-verification/)
  assert.match(api, /comfort-audio/)
  assert.match(pages, /pages\/safety-verification\/safety-verification/)
  assert.match(pages, /pages\/safety-support\/safety-support/)
})
