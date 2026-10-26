import test from 'node:test'
import assert from 'node:assert/strict'
import {createPlayerController} from '../common/player-controller.js'
import {apiV3} from '../common/api-v3.js'
import {initializeApiPlatform} from '../common/api-origin.js'
import {trackAuthorizedAudio,releaseAuthorizedAudio,releaseAllAuthorizedAudio} from '../common/owned-audio.js'

const flush=()=>new Promise(setImmediate)
test('disposed Player releases a late downloaded file and never restores its src',async()=>{
 let finish;const removed=[]
 const controller=createPlayerController({downloadAudio:()=>new Promise(resolve=>{finish=resolve}),releaseAudio:path=>removed.push(path),createAudioContext:()=>{throw new Error('disposed')}})
 const pending=controller.play('/stream');await flush();controller.dispose();finish('/tmp/owned.mp3');await pending
 assert.equal(controller.getState().src,'');assert.deepEqual(removed,['/tmp/owned.mp3'])
})

test('hiding while download is pending never starts playback on completion or show',async()=>{
 let finish,plays=0
 const controller=createPlayerController({downloadAudio:()=>new Promise(resolve=>{finish=resolve}),createAudioContext:()=>({play(){plays++},destroy(){}})})
 const pending=controller.play('/stream');await flush();controller.handleHide();finish('/tmp/paused.mp3');await pending;controller.handleShow()
 assert.equal(plays,0);await controller.play('/stream');assert.equal(plays,1);controller.dispose()
})

test('resource cleanup only deletes owned downloads, shares leases and retries cleanup failures',async()=>{
 let removed=0,fail=true
 const path='/tmp/owned-lease.mp3',remove=()=>{removed++;if(fail)throw new Error('busy file')}
 trackAuthorizedAudio(path,remove);trackAuthorizedAudio(path,remove)
 assert.equal(await releaseAuthorizedAudio('/static/original.mp3'),false)
 await releaseAuthorizedAudio(path);assert.equal(removed,0)
 assert.equal(await releaseAuthorizedAudio(path),false);assert.equal(removed,1)
 fail=false;await releaseAllAuthorizedAudio();assert.equal(removed,2)
 assert.equal(await releaseAuthorizedAudio(path),false)
})

test('changing track cannot adopt the earlier late download and releases both resources exactly once',async()=>{
 const pending=new Map(),removed=[],ctx={src:'',play(){},destroy(){}}
 const controller=createPlayerController({downloadAudio:url=>new Promise(resolve=>pending.set(url,resolve)),releaseAudio:path=>removed.push(path),createAudioContext:()=>ctx})
 const a=controller.play('/a'),b=controller.play('/b');await flush()
 pending.get('/b')('/tmp/b.mp3');await b;pending.get('/a')('/tmp/a.mp3');await a
 assert.equal(ctx.src,'/tmp/b.mp3');assert.equal(controller.getState().streamUrl,'/b')
 controller.dispose();controller.dispose()
 assert.deepEqual(removed.sort(),['/tmp/a.mp3','/tmp/b.mp3'])
})

test('cached A cancels pending B intent without releasing the active A file',async()=>{
 let finishB;const removed=[],ctx={src:'',play(){},destroy(){}}
 const controller=createPlayerController({downloadAudio:url=>url==='/a'?Promise.resolve('/tmp/a.mp3'):new Promise(resolve=>{finishB=resolve}),releaseAudio:path=>removed.push(path),createAudioContext:()=>ctx})
 await controller.play('/a');const pending=controller.play('/b');await flush();await controller.play('/a')
 finishB('/tmp/b.mp3');await pending
 assert.equal(ctx.src,'/tmp/a.mp3');assert.equal(controller.getState().src,'/tmp/a.mp3');assert.equal(controller.getState().streamUrl,'/a')
 assert.deepEqual(removed,['/tmp/b.mp3']);controller.dispose();assert.deepEqual(removed,['/tmp/b.mp3','/tmp/a.mp3'])
})

test('identity change during authorized download rejects and cleans only that downloaded file',async()=>{
 const previous=globalThis.uni,values=new Map([['v3_public_user_id','A'],['v3_access_token','synthetic-a'],['v3_auth_epoch',0]])
 let finish;const removed=[]
 globalThis.uni={getStorageSync:key=>values.get(key)??'',downloadFile:options=>{finish=options.success},getFileSystemManager:()=>({unlink:options=>{removed.push(options.filePath);options.success()}})}
 initializeApiPlatform({target:'h5'})
 try{
  const audio=apiV3.fetchAuthorizedAudio('/api/v3/music/assets/id/stream')
  values.set('v3_public_user_id','B');values.set('v3_auth_epoch',1)
  finish({statusCode:200,tempFilePath:'/tmp/late.mp3'})
  await assert.rejects(audio,{code:'OWNER_CHANGED'})
  assert.deepEqual(removed,['/tmp/late.mp3'])
 }finally{globalThis.uni=previous}
})

test('native HTTPS canonical music route works without standard URL, unsafe syntax remains rejected',async()=>{
 const previous=globalThis.uni,previousURL=globalThis.URL;const calls=[]
 globalThis.uni={getStorageSync:key=>key==='v3_access_token'?'synthetic':'',downloadFile:options=>{calls.push(options);options.success({statusCode:200,tempFilePath:'/tmp/https.mp3'})}}
 initializeApiPlatform({target:'app',systemInfo:{uniPlatform:'app',osName:'android'},apiOrigin:'https://127.0.0.1:8443'})
 globalThis.URL=undefined
 try{
  assert.equal(await apiV3.fetchAuthorizedAudio('/api/v3/music/assets/id/stream'),'/tmp/https.mp3')
  assert.equal(calls.length,1);assert.equal(calls[0].header.Authorization,'Bearer synthetic');assert.equal(calls[0].sslVerify,true)
  for(const url of ['https://127.0.0.1:8443@evil.invalid/api/v3/music/assets/id/stream','https://127.0.0.1:8443/api/v3/music/assets/../stream','https://127.0.0.1:8443/api/v3/music/assets/id/stream?next=evil'])await assert.rejects(apiV3.fetchAuthorizedAudio(url))
  assert.equal(calls.length,1)
 }finally{globalThis.URL=previousURL;initializeApiPlatform({target:'h5'});globalThis.uni=previous}
})
