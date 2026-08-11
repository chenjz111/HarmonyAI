import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { createAssessmentFlow, applyFollowUpRevision, applyCorrectionRevision, workflowPayload } from '../common/assessment-page-flow.js'
import { resolveAuthoritativeMusic } from '../common/workflow-gate.js'

const fixture = JSON.parse(readFileSync(new URL('./fixtures/assessment-v2.1-response.json', import.meta.url), 'utf8'))

test('canonical v2.1 response fixture reaches the page state without field renaming', () => {
  const state = createAssessmentFlow(fixture)
  assert.equal(state.assessment.assessment_id, 'asmt_fixture_001')
  assert.equal(state.assessment.revision, 1)
  assert.equal(state.assessment.emotion_profile.dimension_scores.tension_worry, 3)
  assert.equal(state.assessment.evidence_items[0].source_type, 'questionnaire')
  assert.equal(state.assessment.conflicts[0].conflict_id, 'cf_fixture_001')
  assert.equal(state.assessment.missing_information[0].field, 'duration')
})

test('follow-up then correction always sends the latest revision to workflow', () => {
  let state = createAssessmentFlow(fixture)
  state = applyFollowUpRevision(state, { assessment: { ...fixture, revision: 2, previous_revision: 1 } })
  state = applyCorrectionRevision(state, { assessment: { ...state.assessment, revision: 3, previous_revision: 2 } }, '保留修正')
  assert.deepEqual(workflowPayload(state, { session_id: fixture.session_id }), {
    session_id: fixture.session_id,
    assessment_confirmed: true,
    assessment_id: fixture.assessment_id,
    assessment_revision: 3
  })
})

test('missing prescription never calls music', async () => {
  let calls = 0
  await assert.rejects(() => resolveAuthoritativeMusic({ confirmation: { status: 'confirmed' }, diagnosis: { abstained: false } }, 's', async () => { calls += 1 }))
  assert.equal(calls, 0)
})
