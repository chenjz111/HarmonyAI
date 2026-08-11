import assert from 'node:assert/strict'
import test from 'node:test'

import { createDocumentPageState, applyOcrResponse, enterManualMode, documentActions } from '../common/document-page-state.js'
import { createAssessmentFlow, applyFollowUpRevision, applyCorrectionRevision, workflowPayload, confirmationFailed } from '../common/assessment-page-flow.js'
import { resolveAuthoritativeMusic, workflowGate } from '../common/workflow-gate.js'
import { safeUiError } from '../common/safe-ui-error.js'

test('OCR failed exposes retry/manual/skip and never success or assessment navigation', () => {
  const state = applyOcrResponse(createDocumentPageState(), { status: 'failed', error_code: 'OCR_FAILED', message: '识别暂不可用' })
  assert.equal(state.mode, 'failed'); assert.equal(state.errorCode, 'OCR_FAILED'); assert.equal(state.message, '识别暂不可用')
  assert.deepEqual(documentActions(state), ['retry', 'manual', 'skip']); assert.equal(state.canConfirm, false); assert.equal(state.navigateAssessment, false)
})

test('OCR degraded keeps partial text editable with confirm retry and manual actions', () => {
  const state = applyOcrResponse(createDocumentPageState(), { status: 'degraded', extracted_text: '部分文字' })
  assert.equal(state.mode, 'degraded'); assert.equal(state.text, '部分文字'); assert.equal(state.canConfirm, true)
  assert.deepEqual(documentActions(state), ['confirm', 'retry', 'manual', 'skip'])
})

test('manual OCR editor stays visible when text is empty', () => {
  const state = enterManualMode(createDocumentPageState())
  assert.equal(state.mode, 'manual'); assert.equal(state.text, ''); assert.equal(state.editorVisible, true)
})

test('assessment flow preserves real schema fields', () => {
  const assessment = { assessment_id:'a1', revision:1, assessment_summary:'摘要', emotion_profile:{dimension_scores:{tension_worry:3}}, evidence_items:[{evidence_id:'e1'}], conflicts:[{conflict_id:'c1'}], missing_information:[{field:'duration'}] }
  const state = createAssessmentFlow(assessment)
  assert.equal(state.assessment.assessment_id,'a1'); assert.equal(state.assessment.revision,1); assert.equal(state.assessment.assessment_summary,'摘要')
  assert.equal(state.assessment.evidence_items.length,1); assert.equal(state.assessment.conflicts.length,1); assert.equal(state.assessment.missing_information.length,1)
})

test('follow-up revision 2 is the revision sent to workflow', () => {
  let state=createAssessmentFlow({assessment_id:'a1',revision:1}); state=applyFollowUpRevision(state,{assessment:{assessment_id:'a1',revision:2}})
  assert.equal(workflowPayload(state,{session_id:'s1'}).assessment_revision,2)
})

test('correction revision 3 replaces revision 2 for workflow', () => {
  let state=createAssessmentFlow({assessment_id:'a1',revision:2}); state=applyCorrectionRevision(state,{assessment:{assessment_id:'a1',revision:3}},'保留我的修正')
  assert.equal(workflowPayload(state,{session_id:'s1'}).assessment_revision,3)
})

test('confirmation failure preserves input and restores retry', () => {
  const state=confirmationFailed({...createAssessmentFlow({assessment_id:'a1',revision:3}), correctionText:'不要删掉', confirmationStatus:'submitting'}, {code:'BACKEND_UNAVAILABLE',message:'服务暂不可用'})
  assert.equal(state.correctionText,'不要删掉'); assert.equal(state.confirmationStatus,'error'); assert.equal(state.canRetry,true)
})

for (const [name, workflow, code] of [
  ['safety blocked',{confirmation:{status:'blocked_safety'}},'SAFETY_BLOCKED'],
  ['diagnosis abstained',{confirmation:{status:'confirmed'},diagnosis:{abstained:true}},'DIAGNOSIS_ABSTAINED'],
  ['needs follow-up',{confirmation:{status:'needs_follow_up'}},'NEEDS_FOLLOW_UP'],
]) test(name+' blocks music API', async () => {
  let calls=0; assert.equal(workflowGate(workflow).code,code)
  await assert.rejects(()=>resolveAuthoritativeMusic(workflow,'s',async()=>{calls++})); assert.equal(calls,0)
})

test('valid full flow requests music exactly once with backend prescription', async () => {
  const prescription={id:'backend-rx'}; let calls=0; let received
  await resolveAuthoritativeMusic({confirmation:{status:'confirmed'},diagnosis:{abstained:false},prescription},'s',async p=>{calls++;received=p;return{stream_url:'/ok.mp3'}})
  assert.equal(calls,1); assert.equal(received,prescription)
})

test('music not matched becomes explicit no-music error without fallback', async () => {
  const workflow={confirmation:{status:'confirmed'},diagnosis:{abstained:false},prescription:{id:'backend-rx'}}; let calls=0
  await assert.rejects(()=>resolveAuthoritativeMusic(workflow,'s',async()=>{calls++;return{status:'not_matched'}}),e=>e.code==='NO_MUSIC'); assert.equal(calls,1)
})

test('frontend error mapping never exposes provider internals or credentials', () => {
  const safe=safeUiError({code:'WORKFLOW_FAILED',message:'Provider stack trace https://internal.local sk-secret database password'})
  assert.equal(safe.code,'WORKFLOW_FAILED'); assert.equal(safe.message,'AI 分析暂时不可用，请稍后重试。')
  assert.equal(/stack|https?:|sk-|password/i.test(safe.message),false)
})

test('real Vue pages import and render the tested state transitions', async () => {
  const { readFileSync } = await import('node:fs')
  const material=readFileSync(new URL('../pages/material/material.vue',import.meta.url),'utf8')
  const assessment=readFileSync(new URL('../pages/assessment-result/assessment-result.vue',import.meta.url),'utf8')
  const player=readFileSync(new URL('../pages/player-v2/player-v2.vue',import.meta.url),'utf8')
  assert.match(material,/applyOcrResponse/); assert.match(material,/ocrMode === 'failed'/); assert.match(material,/@retry="retryOcr"/); assert.match(material,/retryOcr\(\)/); assert.match(material,/@fallback="useManualInput"/); assert.match(material,/useManualInput\(\)/); assert.match(material,/if \(ocrState\.mode === 'degraded'\)/)
  assert.match(assessment,/applyFollowUpRevision/); assert.match(assessment,/applyCorrectionRevision/); assert.match(assessment,/workflowPayload/); assert.match(assessment,/confirmationFailed/)
  assert.match(player,/status === 'business'/); assert.match(player,/this\.status = 'business'/); assert.match(player,/resolveAuthoritativeMusic/); assert.equal(player.includes('playFallback()'),false)
})
