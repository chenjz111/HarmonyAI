// uni's platform I/O is bridged to real ASGI responses, never response fixtures.
import assert from 'node:assert/strict'
import {createInterface} from 'node:readline'
import {readFileSync,writeFileSync} from 'node:fs'
import {join} from 'node:path'
import {runInNewContext} from 'node:vm'
import * as libraryState from '../common/music-library-state.js'
import * as libraryTransport from '../common/music-library-transport.js'
import {MUSIC_CARD_V1_PREVIEW_FIXTURE} from '../common/music-card-v1-preview-fixture.js'
import {registeredAccountRuntime} from '../common/auth-runtime.js'
import {createPlayerController} from '../common/player-controller.js'
import * as musicPresentation from '../common/music-presentation.js'
import {seekRatioFromEvent} from '../common/player-seek.js'
import * as libraryPlayer from '../common/music-library-player.js'
import * as feedbackContext from '../common/feedback-context.js'
import {initializeAndroidPlatform} from '../common/android-platform.js'
import {createMusicLibraryApi} from '../common/music-library-api.js'
import {createUniMusicLibraryTransport, MUSIC_LIBRARY_LIVE_ENABLED} from '../common/music-library-transport.js'
import {createMusicLibraryStore} from '../common/music-library-state.js'
import {createHistoricalMusicSession} from '../common/music-library-player.js'
import {createFeedbackApi} from '../common/feedback-api.js'

const pending=new Map(), storage=new Map()
const androidContext=process.env.S7_JOURNEY_PLATFORM==='android'
let serial=0
const input=createInterface({input:process.stdin})
input.on('line',line=>{const response=JSON.parse(line);const callback=pending.get(response.id);assert.ok(callback);pending.delete(response.id);callback(response)})
function rpc(args){return new Promise(resolve=>{const id=++serial;pending.set(id,resolve);process.stdout.write('S7_REQUEST '+JSON.stringify({id,...args})+'\n')})}
const navigation=[], listeners=new Map()
let disconnected=false
globalThis.uni={getStorageSync:key=>storage.get(key)||'',setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),
 $on:(name,callback)=>listeners.set(name,callback),$off:name=>listeners.delete(name),$emit:name=>listeners.get(name)?.(),
 navigateTo:args=>navigation.push(args.url),showToast(){},showModal:args=>args.success({confirm:true,content:'Page title'}),
 request(args){if(disconnected){args.fail();return}const url=new URL(args.url);if(androidContext){assert.equal(url.origin,'https://testserver');assert.equal(args.sslVerify,true)}rpc({method:args.method,path:url.pathname+url.search,data:args.data,header:args.header}).then(args.success,args.fail)}}
if(androidContext){
 globalThis.uni.getSystemInfoSync=()=>({uniPlatform:'app',osName:'android'})
 const readiness=initializeAndroidPlatform({uniApi:globalThis.uni,target:'app',apiOrigin:'https://testserver'})
 assert.equal(readiness.accountInstalled,false);assert.equal(readiness.deviceAcceptance,'NOT_RUN')
}
const {apiV3}=await import('../common/api-v3.js')
assert.equal(apiV3.MODE,'real')
assert.equal(MUSIC_LIBRARY_LIVE_ENABLED,false)
await apiV3.ensureIdentity()
const token=storage.get('v3_access_token'), owner=storage.get('v3_public_user_id')
assert.ok(token && owner)
await apiV3.ensureIdentity()
assert.ok(storage.get('v3_access_token')===token,'reopen must retain actual Guest credential')
await apiV3.createSession()
const identity={getOwnerId:()=>storage.get('v3_public_user_id'),getAccessToken:()=>storage.get('v3_access_token'),getAuthEpoch:()=>storage.get('v3_auth_epoch')||0}
const request=createUniMusicLibraryTransport({baseUrl:androidContext?'https://testserver':'http://isolated.invalid',uniApi:globalThis.uni,getAccessToken:identity.getAccessToken})
const disabled=createMusicLibraryApi({request,...identity})
await assert.rejects(disabled.listMusicAssets(),{code:'FEATURE_NOT_READY'})
const api=createMusicLibraryApi({request,...identity,enabled:true}) // isolated test injection only
const history=createMusicLibraryStore({fetchPage:api.listMusicAssets,getOwnerId:identity.getOwnerId})
await history.refresh()
assert.equal(history.getState().status,'ready')
let card=history.getState().items[0]
assert.equal(card.music_id,'music_shared')
assert.equal(card.last_played_at,null)
assert.equal((await api.listMusicFavorites()).items.length,1)
await api.setFavorite({music_id:card.music_id,source_type:'matched'},false)
assert.equal((await api.listMusicFavorites()).items.length,0)
await api.setFavorite({music_id:card.music_id,source_type:'matched'},true)
const renamed=await api.setMusicTitle(card.music_id,'Integration title',card.metadata_version)
await assert.rejects(api.setMusicTitle(card.music_id,'stale title',card.metadata_version),{code:'TITLE_VERSION_CONFLICT'})
assert.equal((await api.listMusicAssets()).items[0].display_title,'Integration title')
assert.equal((await api.listMusicFavorites()).items[0].display_title,'Integration title')
const playback=createHistoricalMusicSession({api,...identity,newEventId:()=> 'integration-play-1'})
const detail=await playback.open(card.music_id,{context:'ctx_a'})
assert.equal(detail.selected_context_id,'ctx_a')
assert.throws(()=>playback.getFeedbackContext(),{code:'FEATURE_NOT_READY'})
const bytes=await rpc({method:'GET',path:'/api/v3/music/assets/music_shared/stream',header:{Authorization:'Bearer '+token,Range:'bytes=0-31'}})
assert.equal(bytes.statusCode,206)
assert.equal(Buffer.from(bytes.data.bytes_base64,'base64').length,32)
await playback.reportPlayStarted(card.music_id) // platform audio itself is NOT RUN
const context=playback.getFeedbackContext()
const feedback=createFeedbackApi({request,...identity,enabled:true})
const form={schema_version:'feedback_v3.1',...context,expected_evidence_epoch:0,post_state:{change_label:'no_change'}}
const saved=await feedback.save(form,'integration-feedback-1')
assert.equal((await feedback.save(form,'integration-feedback-1')).feedback_id,saved.feedback_id)
assert.equal((await feedback.list({musicId:card.music_id})).total,1)
const clearBody={expected_evidence_epoch:feedback.currentEpoch()}
const receipt=await feedback.clear(clearBody,'integration-clear')
assert.deepEqual(await feedback.clear(clearBody,'integration-clear'),receipt)
assert.equal((await feedback.list({musicId:card.music_id})).total,1,'Clear preserves history')
await feedback.remove(saved.feedback_id,feedback.currentEpoch())
await assert.rejects(feedback.save(form,'integration-feedback-1'),{code:'FEEDBACK_DELETED'})
assert.equal((await feedback.list({musicId:card.music_id})).total,0)
const other=await rpc({method:'POST',path:'/api/v3/auth/guest'})
storage.set('v3_access_token',other.data.data.access_token);storage.set('v3_public_user_id',other.data.data.public_user_id)
assert.equal(history.getState().items.length,0)
assert.equal((await api.listMusicAssets()).items.length,0)
await assert.rejects(api.getMusicAsset(card.music_id))
assert.throws(()=>playback.getFeedbackContext(),{code:'OWNER_CHANGED'})
storage.set('v3_access_token',token);storage.set('v3_public_user_id',owner)
assert.equal((await api.listMusicAssets()).items[0].display_title,'Integration title')
// Execute the real My page script with only platform I/O and the isolated flag injected.
const source=readFileSync(new URL('../pages/v3-profile/v3-profile.vue',import.meta.url),'utf8')
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g,(_,names)=>`const {${names}}=deps;`).replace('export default {','options = {')
function vuePage(script,deps){
 const sandbox={options:null,uni:globalThis.uni,deps}
 runInNewContext(script.replace(/export function /g,'function '),sandbox)
 const page=sandbox.options.data()
 for(const [key,fn] of Object.entries(sandbox.options.methods))page[key]=fn.bind(page)
 for(const [key,fn] of Object.entries(sandbox.options.computed))Object.defineProperty(page,key,{get:()=>fn.call(page)})
 return {page,options:sandbox.options}
}
function profile(enabled){return vuePage(script,{...libraryState,...libraryTransport,MUSIC_LIBRARY_LIVE_ENABLED:enabled,
 MUSIC_CARD_V1_PREVIEW_FIXTURE,registeredAccountRuntime,createMusicLibraryApi})}
function actualPage(file){
 const code=readFileSync(new URL(file,import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g,(_,names)=>`const {${names}}=deps;`).replace('export default {','options = {')
 return vuePage(code,{...libraryTransport,...libraryPlayer,...feedbackContext,...musicPresentation,
  MUSIC_LIBRARY_LIVE_ENABLED:true,apiV3,createMusicLibraryApi,createFeedbackApi,createPlayerController,seekRatioFromEvent})
}
const closed=profile(false)
assert.match(closed.page.sourceBadge,/虚构数据/)
assert.equal(closed.page.accountAvailable,false)
const live=profile(true),page=live.page
live.options.onLoad.call(page);await page.reload()
assert.equal(page.visibleItems.length,1)
disconnected=true;await page.reload()
assert.equal(page.library.status,'error')
assert.ok(storage.get('v3_access_token')===token,'network error must retain identity')
disconnected=false;await page.reload()
assert.equal(page.library.status,'ready')
assert.equal((await rpc({method:'POST',path:'/api/v3/auth/login',data:{}})).statusCode,404,'production account route must remain unregistered')
page.openMusic(page.visibleItems[0])
assert.equal(navigation.at(-1),'/pages/v3-player/v3-player?music_id=music_shared')
await page.editTitle(page.visibleItems[0])
assert.equal(page.visibleItems[0].display_title,'Page title')
page.selectSection('favorites');await page.reload()
assert.equal(page.visibleItems[0].display_title,'Page title')
await page.toggleFavorite(page.visibleItems[0])
assert.equal(page.visibleItems.length,0)
page.selectSection('history');await page.reload()
assert.equal(page.visibleItems[0].is_favorite,false)
page.openMusicFeedback(page.visibleItems[0])
assert.equal(navigation.at(-1),'/pages/v3-feedback/v3-feedback?mode=history&music_id=music_shared')
storage.set('v3_access_token',other.data.data.access_token);storage.set('v3_public_user_id',other.data.data.public_user_id)
assert.equal(page.visibleItems.length,0,'actual page discards previous owner before rendering')
live.options.onShow.call(page);await page.reload()
assert.equal(page.visibleItems.length,0)
storage.set('v3_access_token',token);storage.set('v3_public_user_id',owner)
live.options.onShow.call(page);await page.reload()
assert.equal(page.visibleItems[0].display_title,'Page title')
// Real Player/controller and Feedback page methods; only native audio is substituted.
const audioHandlers={}
let contextsCreated=0
globalThis.uni.createInnerAudioContext=()=>{
 contextsCreated++
 const audio={duration:60.881,currentTime:0,play(){audioHandlers.play?.()},pause(){},seek(value){audio.currentTime=value},destroy(){}}
 for(const event of ['Play','Canplay','TimeUpdate','Ended','Error'])audio['on'+event]=callback=>{audioHandlers[event.toLowerCase()]=callback}
 return audio
}
globalThis.uni.downloadFile=args=>{
 const url=new URL(args.url)
 if(androidContext){assert.equal(url.origin,'https://testserver');assert.equal(args.sslVerify,true)}
 rpc({method:'GET',path:url.pathname,header:args.header}).then(response=>{
  if(response.statusCode!==200){args.success({statusCode:response.statusCode});return}
  const bytes=Buffer.from(response.data.bytes_base64,'base64');assert.equal(bytes.subarray(0,4).toString(),'RIFF')
  const file=join(process.env.CI_DB_SANDBOX,'downloaded-test-audio.wav');writeFileSync(file,bytes)
  args.success({statusCode:200,tempFilePath:file})
 },args.fail)
}
const player=actualPage('../pages/v3-player/v3-player.vue'),p=player.page
p.historicalMusicId='music_shared';p.selectedHistoricalContext='ctx_a'
await p.load()
assert.equal(p.loadFailure,null)
assert.equal(p.music.title,'Page title')
assert.equal(contextsCreated,0,'opening music must not autoplay')
await p.togglePlay()
// onPlay schedules the actual proof request; await that same in-flight report.
await p.historicalSession.reportPlayStarted('music_shared')
assert.equal(contextsCreated,1)
audioHandlers.canplay();p.seekToRatio(0.5)
assert.equal(p.playerController.getState().currentTime,60.881/2)
await p.togglePlay()
assert.equal(p.playing,false)
p.goFeedback()
const handoff=new URL('http://isolated.invalid'+navigation.at(-1)).searchParams.get('handoff')
assert.ok(handoff)
const feedbackPage=actualPage('../pages/v3-feedback/v3-feedback.vue'),f=feedbackPage.page
await feedbackPage.options.onLoad.call(f,{handoff})
assert.equal(f.feedbackReady,true)
f.pickChange('no_change');await f.submit()
assert.equal(f.submitted,true,f.submitError)
await f.refreshFeedback()
assert.equal(f.feedbackItems.length,1)
await f.viewFeedback(f.feedbackItems[0].feedback_id)
assert.equal(f.feedbackDetail.music_ref.music_id,'music_shared')
await f.clearEvidence()
assert.equal(f.feedbackItems.length,1)
await f.deleteFeedback(f.feedbackItems[0].feedback_id)
assert.equal(f.feedbackItems.length,0)
feedbackPage.options.onUnload.call(f);player.options.onUnload.call(p)
live.options.onUnload.call(page)
process.stdout.write('S7_FRONTEND_VERIFIED\n')
input.close()
