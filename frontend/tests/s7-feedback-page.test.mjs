import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {createFeedbackApi} from '../common/feedback-api.js'
import {putHistoricalFeedback,consumeHistoricalFeedback} from '../common/feedback-context.js'
import * as transport from '../common/music-library-transport.js'

const context = {session_id:'historical-session',music_ref:{music_id:'historical-music',source_type:'matched'},
  source_context_id:'ctx-a',playback_event_id:'event-a',pre_state_snapshot:{snapshot_id:'snap-a',source:'player_session',captured_at:'2026-10-24T00:00:00Z'}}
const flush=()=>new Promise(setImmediate)
function harness(handler,{subscriptionFalse=false}={}) {
  const storage = new Map([['v3_public_user_id','A'],['v3_access_token','synthetic-A'],['v3_auth_epoch',0]])
  const listeners = new Set(),calls=[]
  const uni={getStorageSync:key=>storage.get(key) ?? '',$on:(name,fn)=>{listeners.add(fn);if(subscriptionFalse)return false},$off:(name,fn)=>listeners.delete(fn),$emit:()=>{for(const fn of listeners)fn()},
    showModal:args=>args.success({confirm:true}),showToast(){},pageScrollTo(){},navigateBack(){},reLaunch(){},
    request(args){calls.push(args);Promise.resolve().then(()=>handler(args)).then(data=>{if(data?.feedback_id && args.method==='POST')data={status:'saved',replayed:false,learning_applied:false,...data};args.success({statusCode:data?.error?503:200,data:data?.error?{ok:false,error:data.error}:{ok:true,data}})})}}
  const script=readFileSync(new URL('../pages/v3-feedback/v3-feedback.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g,(_,names)=>`const {${names}}=deps;`)
    .replace(/export function/g,'function').replace('export default {','options = {')
  const sandbox={uni,options:null,deps:{apiV3:{submitFeedback(){throw new Error('historical feedback reached legacy current flow')}},
    createFeedbackApi,putHistoricalFeedback,consumeHistoricalFeedback,MUSIC_LIBRARY_LIVE_ENABLED:true,
    createUniMusicLibraryTransport:options=>transport.createUniMusicLibraryTransport({...options,uniApi:uni}),
    readV3AccessToken:()=>transport.readV3AccessToken(uni)}}
  runInNewContext(script,sandbox)
  const options=sandbox.options,page=options.data()
  for(const [name,fn] of Object.entries(options.methods))page[name]=fn.bind(page)
  for(const [name,fn] of Object.entries(options.computed))Object.defineProperty(page,name,{get:()=>fn.call(page)})
  return {page,calls,storage,uni,options,
    async start(mode='v31', source=context){const handoff=putHistoricalFeedback(source,()=>true);await options.onLoad.call(page,mode==='history'?{mode:'history',music_id:source.music_ref.music_id}:{handoff});await flush()},
    auth(){storage.set('v3_auth_epoch',2);uni.$emit()},unload(){options.onUnload.call(page)}}
}

test('W4: both per-song history and V3.1 form list only the selected music',async()=>{
 for(const mode of ['history','v31']){const h=harness(()=>({items:[],total:0,current_feedback_epoch:0,next_cursor:null}));await h.start(mode);assert.ok(h.calls[0].url.endsWith('&music_id=historical-music'));h.unload()}
})

test('W4: unscoped history cannot issue an owner-wide feedback read',async()=>{
 const h=harness(()=>{throw new Error('unscoped read')});await h.options.onLoad.call(h.page,{mode:'history'});assert.equal(h.calls.length,0);assert.equal(h.page.feedbackReady,false);h.unload()
})

test('historical form sends explicit server context and unknown-commit retry preserves exact body/key',async()=>{
  let posts=0
  const h=harness(args=>args.method==='GET'?{items:[],total:0,current_feedback_epoch:4,next_cursor:null}:
    ++posts===1?{error:{code:'FEEDBACK_COMMIT_UNVERIFIED',message:'unknown'}}:{feedback_id:'fb-a',replayed:true,current_feedback_epoch:5})
  await h.start();h.page.pickChange('no_change');await h.page.submit()
  h.page.pickChange('worse');h.page.pickContinue('yes');h.page.toggleLiked('melody');h.page.toggleAdjust('slower_tempo')
  assert.equal(h.page.changeLabel,'no_change');assert.equal(h.page.continueUse,'')
  assert.equal(h.page.likedFeatures.length,0);assert.equal(h.page.adjustments.length,0)
  await h.page.submit()
  const requests=h.calls.filter(x=>x.method==='POST')
  assert.equal(requests.length,2)
  assert.equal(requests[0].header['Idempotency-Key'],requests[1].header['Idempotency-Key'])
  assert.deepEqual(requests[0].data,requests[1].data)
  assert.equal(requests[0].data.session_id,'historical-session')
  assert.equal(requests[0].data.playback_event_id,'event-a')
  assert.equal(requests[0].data.expected_evidence_epoch,4)
  assert.equal(requests[0].data.learning_consent,false)
  assert.equal(h.page.submitted,true);h.unload()
})

test('unknown commit followed by closing and reopening cannot send a new key for the same listening event',async()=>{
 let posts=0
 const handler=args=>args.method==='GET'?{items:[],total:0,current_feedback_epoch:4,next_cursor:null}:
   (++posts,{error:{code:'FEEDBACK_COMMIT_UNVERIFIED',message:'unknown'}})
 const source={...context,playback_event_id:'event-unknown-page'}
 const first=harness(handler);await first.start('v31',source);first.page.pickChange('no_change');await first.page.submit();first.unload()
 const second=harness(handler);await second.start('v31',source);second.page.pickChange('worse');await second.page.submit()
 assert.equal(posts,1);assert.match(second.page.submitError,/提交结果待确认/);second.unload()
})

test('only one destructive confirmation can be pending',async()=>{
 const h=harness(()=>({items:[],total:0,current_feedback_epoch:0,next_cursor:null}))
 await h.start('history')
 const dialogs=[];h.uni.showModal=args=>dialogs.push(args)
 const first=h.page.deleteFeedback('fb-a');const second=h.page.clearEvidence()
 assert.equal(dialogs.length,1)
 dialogs[0].success({confirm:false});await Promise.all([first,second])
 assert.equal(h.page.submitting,false);h.unload()
})

test('ABA authentication change clears private form and ignores late save',async()=>{
  let resolve
  const pending=new Promise(r=>{resolve=r})
  const h=harness(args=>args.method==='GET'?{items:[],total:0,current_feedback_epoch:0,next_cursor:null}:pending)
  await h.start('v31',{...context,playback_event_id:'event-aba-late'});h.page.pickChange('no_change');const saving=h.page.submit();await flush()
  h.auth();resolve({feedback_id:'late',current_feedback_epoch:1});await saving
  assert.equal(h.page.submitted,false);assert.equal(h.page.feedbackContext,null)
  assert.equal(h.page.changeLabel,'');h.unload()
})

test('history deletion updates records and clear preserves remaining history',async()=>{
  let epoch=1,rows=[{feedback_id:'fb-a',music_ref:{music_id:'m'},post_state:{change_label:'no_change'},submitted_at:'2026-10-24T00:00:00Z'}]
  const h=harness(args=>{
    if(args.method==='GET')return {items:rows,total:rows.length,current_feedback_epoch:epoch,next_cursor:null}
    if(args.method==='DELETE'){rows=[];return {status:'deleted',current_feedback_epoch:++epoch}}
    return {status:'cleared',operation_id:'clear-a',cutoff:'2026-10-24T00:00:00Z',resulting_feedback_epoch:++epoch}
  })
  await h.start('history');assert.equal(h.page.feedbackItems.length,1)
  await h.page.clearEvidence();assert.equal(h.page.feedbackItems.length,1)
  await h.page.deleteFeedback('fb-a');assert.equal(h.page.feedbackItems.length,0);h.unload()
})


test('definitive epoch conflict refreshes before a new intent but unknown commit keeps its request',async()=>{
  let posts=0,epoch=1
  const h=harness(args=>args.method==='GET'?{items:[],total:0,current_feedback_epoch:epoch,next_cursor:null}:
    ++posts===1?(epoch=2,{error:{code:'FEEDBACK_EPOCH_CONFLICT',message:'conflict'}}):{feedback_id:'fb',current_feedback_epoch:3})
  await h.start();h.page.pickChange('no_change');await h.page.submit()
  h.page.pickChange('worse');await h.page.submit()
  const requests=h.calls.filter(x=>x.method==='POST')
  assert.notEqual(requests[0].header['Idempotency-Key'],requests[1].header['Idempotency-Key'])
  assert.equal(requests[1].data.expected_evidence_epoch,2)
  assert.equal(requests[1].data.post_state.change_label,'worse');h.unload()
})


test('later detail choice wins even when an earlier request returns last',async()=>{
  let resolveA
  const pendingA=new Promise(resolve=>{resolveA=resolve})
  const h=harness(args=>args.url.endsWith('/a')?pendingA:args.url.endsWith('/b')?{feedback_id:'b'}:{items:[],total:0,current_feedback_epoch:0,next_cursor:null})
  await h.start('history');const a=h.page.viewFeedback('a');await flush()
  await h.page.viewFeedback('b');resolveA({feedback_id:'a'});await a
  assert.equal(h.page.feedbackDetail.feedback_id,'b');h.unload()
})


test('rejected auth notification subscription fails closed before all requests',async()=>{
  const h=harness(()=>{throw new Error('must not request')},{subscriptionFalse:true})
  await h.start();assert.equal(h.calls.length,0);assert.equal(h.page.feedbackReady,false)
  assert.equal(h.page.feedbackContext,null);h.unload()
})
