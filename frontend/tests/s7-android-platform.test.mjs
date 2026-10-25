import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {createUniMusicLibraryTransport,MUSIC_LIBRARY_LIVE_ENABLED} from '../common/music-library-transport.js'
import {registeredAccountRuntime,hasAccountRuntime,readRuntimeV3Credential} from '../common/auth-runtime.js'
import {createNativeAccountRuntime} from '../common/account-transport.js'

async function modules(){
 const origin=await import('../common/api-origin.js').catch(()=>({}))
 const android=await import('../common/android-platform.js').catch(()=>({}))
 assert.equal(typeof origin.initializeApiPlatform,'function')
 assert.equal(typeof android.initializeAndroidPlatform,'function')
 return {origin,android}
}
const info={uniPlatform:'app',osName:'android'}

test('Android never uses the desktop localhost/HTTP fallback or a mixed backend',async()=>{
 const {origin}=await modules()
 try{
  origin.initializeApiPlatform({target:'app',systemInfo:info})
  assert.throws(()=>origin.getApiOrigin(),{code:'PLATFORM_API_UNAVAILABLE'})
  for(const value of ['http://api.example','https://user:secret@api.example','https://api.example/path','https://api.example?token=secret']){
   origin.initializeApiPlatform({target:'app',systemInfo:info,apiOrigin:value})
   assert.throws(()=>origin.getApiOrigin(),{code:'PLATFORM_API_UNAVAILABLE'})
  }
  origin.initializeApiPlatform({target:'app',systemInfo:info,apiOrigin:'https://api.example'})
  assert.equal(origin.getApiOrigin(),'https://api.example')
  assert.throws(()=>origin.getApiOrigin({explicit:'https://other.example'}),{code:'PLATFORM_API_UNAVAILABLE'})
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('transport created before Android bootstrap uses the configured HTTPS origin at request time',async()=>{
 const {origin}=await modules();let wire
 const uniApi={request:args=>{wire=args;args.success({statusCode:200,data:{ok:true,data:{items:[]}}})}}
 const request=createUniMusicLibraryTransport({uniApi,getAccessToken:()=> 'synthetic-Guest'})
 try{
  origin.initializeApiPlatform({target:'app',systemInfo:info,apiOrigin:'https://api.example'})
  assert.ok((await request({method:'GET',path:'/api/v3/me/music-assets'})).data)
  assert.equal(wire.url,'https://api.example/api/v3/me/music-assets')
  assert.equal(wire.sslVerify,true)
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('H5 on Android stays H5 and missing native dependencies do not enable accounts or music',async()=>{
 const {origin,android}=await modules()
 try{
  const web=android.initializeAndroidPlatform({target:'h5',uniApi:{getSystemInfoSync:()=>({uniPlatform:'web',osName:'android'})},apiOrigin:'https://api.example'})
  assert.equal(web.androidApp,false)
  const native=android.initializeAndroidPlatform({target:'app',uniApi:{getSystemInfoSync:()=>info},apiOrigin:'https://api.example'})
  assert.equal(native.androidApp,true);assert.equal(native.accountInstalled,false)
  assert.ok(native.blockers.includes('KEYSTORE_ADAPTER_UNACCEPTED'))
  assert.equal(registeredAccountRuntime.available,false);assert.equal(MUSIC_LIBRARY_LIVE_ENABLED,false)
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('main initializes platform wiring before constructing the actual App',async()=>{
 const source=readFileSync(new URL('../main.js',import.meta.url),'utf8')
 const calls=[];const sandbox={result:null,uni:{},App:{},createSSRApp(){calls.push('app');return{}},initializeAndroidPlatform(){calls.push('platform')}}
 const code=source.replace(/^import[^\n]+\n/gm,'').replace('export function createApp','function createApp')
 runInNewContext(code+';result=createApp()',sandbox)
 assert.deepEqual(calls,['platform','app'])
})

test('facade and authorized audio share Android HTTPS and explicitly request certificate verification',async()=>{
 const {origin}=await modules(),previous=globalThis.uni,calls=[]
 globalThis.uni={getStorageSync:key=>({v3_access_token:'synthetic-Guest',v3_public_user_id:'owner'})[key]||'',
  request:args=>{calls.push(args);args.success({statusCode:200,data:{ok:true,data:{public_user_id:'owner',auth_type:'guest'}}})},
  downloadFile:args=>{calls.push(args);args.success({statusCode:200,tempFilePath:'/synthetic.wav'})}}
 try{
  const {apiV3}=await import('../common/api-v3.js?android-origin')
  origin.initializeApiPlatform({target:'app',systemInfo:info,apiOrigin:'https://api.example'})
  await apiV3.ensureIdentity();await apiV3.fetchAuthorizedAudio('/api/v3/music/assets/id/stream')
  for(const call of calls){assert.equal(new URL(call.url).origin,'https://api.example');assert.equal(call.sslVerify,true)}
  await assert.rejects(()=>apiV3.fetchAuthorizedAudio('http://audio.example/track.mp3'),{code:'AUDIO_FETCH_FAILED'})
 }finally{origin.initializeApiPlatform({target:'h5'});globalThis.uni=previous}
})

test('missing Android origin rejects audio with a Promise and makes no credentialed request',async()=>{
 const {origin}=await modules(),previous=globalThis.uni
 globalThis.uni={getStorageSync:()=> 'synthetic',downloadFile(){assert.fail('no download permitted')}}
 try{
  origin.initializeApiPlatform({target:'app',systemInfo:info})
  const {apiV3}=await import('../common/api-v3.js?android-missing-origin')
  await assert.rejects(()=>apiV3.fetchAuthorizedAudio('/api/v3/music/assets/id/stream'),{code:'PLATFORM_API_UNAVAILABLE'})
 }finally{origin.initializeApiPlatform({target:'h5'});globalThis.uni=previous}
})

function nativeDependencies(){
 const values=new Map([['v3_access_token','lawful-Guest'],['v3_public_user_id','owner'],['v3_auth_epoch',0]])
 const uniApi={getSystemInfoSync:()=>info,getStorageSync:k=>values.get(k)||'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit(){}}
 const secureStore={verified:true,keystoreBacked:true,atomicConsume:true,async take(){},async write(){},async clear(){}}
 const networkApi={certificateValidationVerified:true,redirectsRejected:true,noAmbientCookies:true,
  request(){assert.fail('bootstrap never authenticates or makes network requests')},
  downloadFile(){assert.fail('bootstrap never downloads')},uploadFile(){assert.fail('bootstrap never uploads')}}
 return {uniApi,values,accountDependencies:{ownerApprovedForNonProduction:true,approvalRef:'synthetic-review-only',secureStore,networkApi}}
}

test('native capability metadata must be exact booleans, not truthy strings',async()=>{
 const {origin,android}=await modules(),deps=nativeDependencies();let installs=0
 deps.accountDependencies.networkApi.redirectsRejected='false'
 try{
  const result=android.initializeAndroidPlatform({...deps,target:'app',apiOrigin:'https://api.example',installRuntime(){installs++}})
  assert.equal(result.accountInstalled,false);assert.equal(installs,0)
  assert.equal(readRuntimeV3Credential(deps.uniApi),'lawful-Guest')
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('repeated main/bootstrap setup does not replace an installed identity runtime',async()=>{
 const {origin,android}=await modules(),deps=nativeDependencies();let installs=0
 const options={...deps,target:'app',apiOrigin:'https://api.example',installRuntime(){installs++}}
 try{
  assert.equal(android.initializeAndroidPlatform(options).accountInstalled,true)
  assert.equal(android.initializeAndroidPlatform(options).accountInstalled,true)
  assert.equal(installs,1)
  assert.equal(android.initializeAndroidPlatform({...options,target:'h5'}).androidApp,false,'H5 cannot inherit cached native capability')
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('failed native installation leaves Guest storage and runtime registry unchanged',async()=>{
 const {origin,android}=await modules(),deps=nativeDependencies()
 try{
  const result=android.initializeAndroidPlatform({...deps,target:'app',apiOrigin:'https://api.example',installRuntime(){throw new Error('adapter installation failed')}})
  assert.equal(result.accountInstalled,false)
  assert.equal(hasAccountRuntime(deps.uniApi),false)
  assert.equal(readRuntimeV3Credential(deps.uniApi),'lawful-Guest')
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('rejected platform setup cannot rebind an existing authentication runtime to a different backend',async()=>{
 const {origin,android}=await modules(),deps=nativeDependencies()
 try{
  origin.initializeApiPlatform({target:'app',systemInfo:info,apiOrigin:'https://old.example'})
  const runtime=createNativeAccountRuntime({uniApi:deps.uniApi,networkApi:deps.accountDependencies.networkApi,baseUrl:'https://old.example',secureStore:deps.accountDependencies.secureStore,accepted:true,redirectsRejected:true})
  assert.equal(runtime.available,true)
  assert.equal(hasAccountRuntime(deps.uniApi),true)
  const result=android.initializeAndroidPlatform({...deps,target:'app',apiOrigin:'https://new.example',installRuntime(){assert.fail('must reject')}})
  assert.equal(result.accountInstalled,false)
  assert.equal(origin.getApiOrigin(),'https://old.example')
 }finally{origin.initializeApiPlatform({target:'h5'})}
})

test('all Android Registered traffic uses the accepted network provider including upload and audio',async()=>{
 const {origin,android}=await modules(),deps=nativeDependencies(),previous=globalThis.uni,calls=[]
 const net=deps.accountDependencies.networkApi
 net.request=args=>{calls.push(args);const data=args.url.endsWith('/login')
  ?{public_user_id:'registered-owner',access_token:'synthetic-memory-access',refresh_token:'synthetic-proof',expires_at:new Date(Date.now()+60000).toISOString()}
  :{public_user_id:'registered-owner',auth_type:'registered'};args.success({statusCode:200,data:{ok:true,data}})}
 net.downloadFile=args=>{calls.push(args);args.success({statusCode:200,tempFilePath:'/approved.wav'})}
 net.uploadFile=args=>{calls.push(args);args.fail()}
 for(const method of ['request','downloadFile','uploadFile'])deps.uniApi[method]=()=>assert.fail('unreviewed uni network bypass')
 globalThis.uni=deps.uniApi;let runtime
 try{
  android.initializeAndroidPlatform({...deps,target:'app',apiOrigin:'https://api.example',installRuntime(value){runtime=value}})
  await runtime.login({username:'example',password:'synthetic-long-password'})
  const {apiV3}=await import('../common/api-v3.js?accepted-native-network')
  await apiV3.ensureIdentity()
  const request=createUniMusicLibraryTransport({uniApi:deps.uniApi,getAccessToken:()=>readRuntimeV3Credential(deps.uniApi)})
  assert.ok((await request({method:'GET',path:'/api/v3/me/music-assets'})).data)
  assert.equal(await apiV3.fetchAuthorizedAudio('/api/v3/music/assets/id/stream'),'/approved.wav')
  deps.values.set('v3_flow_state',JSON.stringify({session_id:'registered-session'}))
  await assert.rejects(apiV3.uploadDocument('/synthetic.png'),{code:'NETWORK_ERROR'})
  assert.ok(calls.some(c=>c.url.endsWith('/api/v2/documents')))
  for(const call of calls){assert.equal(new URL(call.url).origin,'https://api.example');assert.equal(call.sslVerify,true)}
 }finally{origin.initializeApiPlatform({target:'h5'});globalThis.uni=previous}
})
