import test from 'node:test'
import assert from 'node:assert/strict'
import { createFeedbackApi } from '../common/feedback-api.js'
import { createHistoricalMusicSession } from '../common/music-library-player.js'

function setup(request) {
  const identity = { owner:'A', token:'synthetic-A', epoch:0 }
  const api = createFeedbackApi({ request, enabled:true, getOwnerId:()=>identity.owner,
    getAccessToken:()=>identity.token, getAuthEpoch:()=>identity.epoch })
  return {api,identity}
}

test('V31 adapter sends approved paths, explicit body and original idempotency key', async () => {
  const calls = []
  const {api} = setup(async args => { calls.push(args); return {data:args.path==='/api/v3/feedback-records'?{feedback_id:'fb-1',status:'saved',current_feedback_epoch:1,replayed:false,learning_applied:false}:{current_feedback_epoch:1}} })
  const body = {session_id:'historical-session',music_ref:{music_id:'historical-music',source_type:'matched'},source_context_id:'ctx-a',playback_event_id:'event-a',expected_evidence_epoch:0}
  await api.save(body,'same-key')
  await api.clear({expected_evidence_epoch:1},'clear-key')
  await api.remove('fb-1',2)
  assert.deepEqual(calls,[
    {method:'POST',path:'/api/v3/feedback-records',data:body,idempotencyKey:'same-key'},
    {method:'POST',path:'/api/v3/me/feedback-evidence/clear',data:{expected_evidence_epoch:1},idempotencyKey:'clear-key'},
    {method:'DELETE',path:'/api/v3/feedback-records/fb-1',data:{expected_evidence_epoch:2}},
  ])
})

test('unknown save rejects changed body and malformed acknowledgement without releasing the barrier',async()=>{
 let calls=0
 const {api}=setup(async()=>{calls++;return calls===1?{error:{code:'FEEDBACK_COMMIT_UNVERIFIED'}}:{data:{}}})
 const body={music_ref:{music_id:'m-uncertain'},source_context_id:'ctx',playback_event_id:'event-uncertain',expected_evidence_epoch:0,post_state:{change_label:'no_change'}}
 await assert.rejects(api.save(body,'key'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 body.post_state.change_label='worse'
 await assert.rejects(api.save(body,'key'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 assert.equal(calls,1)
 body.post_state.change_label='no_change'
 await assert.rejects(api.save(body,'key'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 await assert.rejects(api.save(body,'different'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 assert.equal(calls,2)
})

test('pending event blocks concurrent same-owner writes but not another owner or new event',async()=>{
 let release,requests=0
 const pending=new Promise(resolve=>{release=resolve})
 const first=setup(async()=>{requests++;return pending})
 const body={music_ref:{music_id:'m'},source_context_id:'ctx',playback_event_id:'event-race',expected_evidence_epoch:0}
 const saving=first.api.save(body,'first')
 const sameOwner=setup(async()=>{requests++;return {data:{feedback_id:'unexpected',status:'saved',current_feedback_epoch:1,replayed:false,learning_applied:false}}})
 await assert.rejects(sameOwner.api.save(body,'other'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 const secondOwner=setup(async()=>{requests++;return {data:{feedback_id:'other-owner',status:'saved',current_feedback_epoch:1,replayed:false,learning_applied:false}}})
 secondOwner.identity.owner='B';secondOwner.identity.token='synthetic-B'
 await secondOwner.api.save(body,'other')
 const newEvent=setup(async()=>{requests++;return {data:{feedback_id:'new-event',status:'saved',current_feedback_epoch:1,replayed:false,learning_applied:false}}})
 await newEvent.api.save({...body,playback_event_id:'event-race-new'},'new')
 assert.equal(requests,3)
 release({data:{feedback_id:'first',status:'saved',current_feedback_epoch:1,replayed:false,learning_applied:false}});await saving
})

test('one owner exhausting unresolved capacity cannot block another owner',async()=>{
 let attempts=0,confirmed=false,firstBody
 const failed=setup(async()=>{attempts++;return confirmed?{data:{feedback_id:'fb-recovered',status:'saved',current_feedback_epoch:1,replayed:true,learning_applied:false}}:{error:{code:'FEEDBACK_COMMIT_UNVERIFIED'}}})
 failed.identity.owner='capacity-owner';failed.identity.token='capacity-token'
 for(let i=0;i<256;i++){
  const body={music_ref:{music_id:'m'},source_context_id:'ctx',playback_event_id:`capacity-${i}`}
  if(i===0)firstBody=body
  await assert.rejects(failed.api.save(body,`key-${i}`),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 }
 await assert.rejects(failed.api.save({music_ref:{music_id:'m'},source_context_id:'ctx',playback_event_id:'overflow'},'overflow'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 await assert.rejects(failed.api.save(firstBody,'new-key'),{code:'FEEDBACK_COMMIT_UNVERIFIED'})
 assert.equal(attempts,256)
 let otherPosts=0
 const other=setup(async()=>{otherPosts++;return {data:{feedback_id:'fb',status:'saved',current_feedback_epoch:1,replayed:false,learning_applied:false}}})
 other.identity.owner='other-capacity-owner';other.identity.token='other-token'
 await other.api.save({music_ref:{music_id:'m'},source_context_id:'ctx',playback_event_id:'other-event'},'other-key')
 assert.equal(otherPosts,1)
 confirmed=true;assert.equal((await failed.api.save(firstBody,'key-0')).feedback_id,'fb-recovered')
})

test('V31 API rejects late A→B→A results and never adopts the new identity', async () => {
  let resolve
  const pending = new Promise(r=>{resolve=r})
  const {api,identity} = setup(()=>pending)
  const call = api.list()
  identity.owner='B'; identity.token='synthetic-B'; identity.epoch=1
  identity.owner='A'; identity.token='synthetic-A'; identity.epoch=2
  resolve({data:{items:[],total:0,current_feedback_epoch:0,next_cursor:null}})
  await assert.rejects(call,{code:'OWNER_CHANGED'})
  await assert.rejects(api.list(),{code:'OWNER_CHANGED'})
})

test('a list launched before delete cannot restore its stale rows', async () => {
  let resolve
  const pending = new Promise(r=>{resolve=r})
  const {api} = setup(args=>args.method === 'GET' ? pending : Promise.resolve({data:{current_feedback_epoch:2}}))
  const listing = api.list()
  await api.remove('fb-1',1)
  resolve({data:{items:[{feedback_id:'fb-1'}],total:1,current_feedback_epoch:1,next_cursor:null}})
  await assert.rejects(listing,{code:'STALE_RESPONSE'})
})

test('historical feedback requires selected server session and exact acknowledged onPlay event', async () => {
  const detail = {card:{music_id:'music-a',source_type:'matched'},
    source_contexts:[{context_id:'ctx-a',session_id:'historical-session'}],selected_context_id:'ctx-a'}
  const session = createHistoricalMusicSession({api:{getMusicAsset:async()=>detail,
    recordPlayStarted:async()=>({event_id:'event-a',music_id:'music-a',event_type:'play_started'})},
    getOwnerId:()=> 'A',getAccessToken:()=> 'synthetic',getAuthEpoch:()=>0,newEventId:()=> 'event-a'})
  await session.open('music-a',{context:'ctx-a'})
  assert.throws(()=>session.getFeedbackContext(),{code:'FEATURE_NOT_READY'})
  await session.reportPlayStarted('music-a')
  const context = session.getFeedbackContext()
  assert.equal(context.session_id,'historical-session')
  assert.equal(context.source_context_id,'ctx-a')
  assert.equal(context.playback_event_id,'event-a')
  assert.equal(context.music_ref.music_id,'music-a')
  assert.ok(context.pre_state_snapshot.captured_at)
  session.reset()
  assert.throws(()=>session.getFeedbackContext())
})

test('missing server session never falls back to a current-flow session', async () => {
  const session = createHistoricalMusicSession({api:{getMusicAsset:async()=>({card:{music_id:'m',source_type:'matched'},source_contexts:[],selected_context_id:'c'}),
    recordPlayStarted:async()=>({event_id:'e',music_id:'m',event_type:'play_started'})},
    getOwnerId:()=> 'A',getAccessToken:()=> 'synthetic',getAuthEpoch:()=>0,newEventId:()=> 'e'})
  await session.open('m',{context:'c'}); await session.reportPlayStarted('m')
  assert.throws(()=>session.getFeedbackContext(),{code:'FEATURE_NOT_READY'})
})
