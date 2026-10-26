import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
const info={uniPlatform:'app',osName:'android'}
function loadOrigin(env){
 const source=readFileSync(new URL('../common/api-origin.js',import.meta.url),'utf8')
 const sandbox={env,process:{env:{UNI_PLATFORM:'app'}},URL,result:null}
 runInNewContext(source.replaceAll('import.meta.env','env').replaceAll('export ','')+';result={initializeApiPlatform,getApiOrigin,nativeTlsOptions,installPlatformNetworkApi,isUsbGuestDebugOrigin:typeof isUsbGuestDebugOrigin==="function"?isUsbGuestDebugOrigin:()=>false}',sandbox)
 return sandbox.result
}
const development={DEV:true,MODE:'development',VITE_S7_USB_GUEST_DEBUG:'1',VITE_API_BASE_URL:'http://127.0.0.1:8000'}
test('explicit Android development USB build allows only the fixed loopback Guest origin',()=>{
 const origin=loadOrigin(development)
 const ctx=origin.initializeApiPlatform({systemInfo:info})
 assert.equal(ctx.usbGuestDebug,true)
 assert.equal(origin.getApiOrigin(),'http://127.0.0.1:8000')
 assert.equal(origin.nativeTlsOptions().sslVerify,true)
 assert.throws(()=>origin.getApiOrigin({explicit:'http://localhost:8000'}),{code:'PLATFORM_API_UNAVAILABLE'})
 assert.throws(()=>origin.installPlatformNetworkApi({request(){},downloadFile(){},uploadFile(){}}),{code:'PLATFORM_API_UNAVAILABLE'})
})
test('release, wrong mode/flag and non-Android cannot opt into HTTP using a debug flag',()=>{
 for(const env of [{...development,DEV:false},{...development,MODE:'production'},{...development,VITE_S7_USB_GUEST_DEBUG:'true'},{...development,VITE_S7_USB_GUEST_DEBUG:undefined}]){
  const origin=loadOrigin(env);origin.initializeApiPlatform({systemInfo:info})
  assert.throws(()=>origin.getApiOrigin(),{code:'PLATFORM_API_UNAVAILABLE'})
 }
 const origin=loadOrigin(development);origin.initializeApiPlatform({systemInfo:{uniPlatform:'app',osName:'ios'}})
 assert.throws(()=>origin.getApiOrigin(),{code:'PLATFORM_API_UNAVAILABLE'})
})
test('even USB debug rejects every non-exact HTTP endpoint and mixed origin',()=>{
 for(const value of ['http://127.0.0.1:8001','http://192.168.1.2:8000','http://localhost:8000','http://127.0.0.1:8000/path','http://user:pass@127.0.0.1:8000','http://127.0.0.1:8000?x=1']){
  const origin=loadOrigin({...development,VITE_API_BASE_URL:value});origin.initializeApiPlatform({systemInfo:info})
  assert.throws(()=>origin.getApiOrigin(),{code:'PLATFORM_API_UNAVAILABLE'})
 }
})
test('USB Guest composition rejects Registered installation even with accepted adapters',()=>{
 const origin=loadOrigin(development),source=readFileSync(new URL('../common/android-platform.js',import.meta.url),'utf8')
 let installs=0,creates=0
 const sandbox={...origin,configuredApiOrigin:()=>development.VITE_API_BASE_URL,buildTarget:()=> 'app',
  createNativeAccountRuntime(){creates++;return{available:true}},installRegisteredAccountRuntime(){installs++},
  registeredAccountRuntime:{available:false},hasAccountRuntime:()=>false,discardUninstalledAccountRuntime(){},result:null}
 runInNewContext(source.replace(/^import[^\n]+\n/gm,'').replaceAll('export ','')+';result=initializeAndroidPlatform',sandbox)
 const state=sandbox.result({uniApi:{getSystemInfoSync:()=>info},accountDependencies:{ownerApprovedForNonProduction:true,approvalRef:'synthetic',
  secureStore:{verified:true,keystoreBacked:true,atomicConsume:true},networkApi:{certificateValidationVerified:true,redirectsRejected:true,noAmbientCookies:true,request(){},downloadFile(){},uploadFile(){}}}})
 assert.equal(state.apiReady,true);assert.equal(state.accountInstalled,false)
 assert.ok(state.blockers.includes('USB_GUEST_DEBUG_ACCOUNT_DISABLED'))
 assert.equal(creates,0);assert.equal(installs,0)
})

test('actual authorized audio helper downloads only the approved USB origin without disabling SSL verification',async()=>{
 const origin=loadOrigin(development);origin.initializeApiPlatform({systemInfo:info})
 const source=readFileSync(new URL('../common/api-v3.js',import.meta.url),'utf8')
 const start=source.indexOf('  async fetchAuthorizedAudio(streamUrl) {'),end=source.indexOf('  // 会话辅助',start)
 assert.ok(start>=0 && end>start)
 const calls=[],sandbox={...origin,URL,BASE_URL:'',FRIENDLY_ERRORS:{NETWORK_ERROR:'network'},Promise,
  resolveMusicStreamUrl:url=>url.startsWith('/api/')?origin.getApiOrigin()+url:url,
  apiError:(message,code)=>Object.assign(new Error(message),{code}),
  hasAccountRuntime:()=>false,captureAuthentication:()=>()=>{},
  audioRemover:()=>()=>{},trackAuthorizedAudio(){},releaseAuthorizedAudio(){},
  platformNetworkApi:api=>api,authHeaders:()=>({Authorization:'Bearer synthetic-only'}),
  uni:{downloadFile(args){calls.push(args);args.success({statusCode:200,tempFilePath:'/synthetic/real-owned.mp3'})}},result:null}
 runInNewContext('const api={'+source.slice(start,end)+'};result=api.fetchAuthorizedAudio',sandbox)
 assert.equal(await sandbox.result('/api/v3/music/assets/one/stream'),'/synthetic/real-owned.mp3')
 assert.equal(calls.length,1);assert.equal(calls[0].sslVerify,true)
 sandbox.URL=undefined
 assert.equal(await sandbox.result('/api/v3/music/assets/one/stream'),'/synthetic/real-owned.mp3')
 for(const suffix of ['/api/v3/music/assets/one/stream?x=1','/api/v3/music/assets/one/stream#x','/api/v3/music/assets/a%2fb/stream','/api/v3/music/assets/../stream','/other']){
  await assert.rejects(()=>sandbox.result('http://127.0.0.1:8000'+suffix),{code:'AUDIO_FETCH_FAILED'})
 }
 sandbox.URL=URL

 assert.equal(calls[0].url,'http://127.0.0.1:8000/api/v3/music/assets/one/stream')
 for(const url of ['http://127.0.0.1:8001/audio','http://localhost:8000/audio','http://elsewhere.invalid/audio']){
  await assert.rejects(()=>sandbox.result(url),{code:'AUDIO_FETCH_FAILED'})
 }
 assert.equal(calls.length,2)
 origin.initializeApiPlatform({systemInfo:info,apiOrigin:'https://api.example'})
 await assert.rejects(()=>sandbox.result('http://127.0.0.1:8000/audio'),{code:'AUDIO_FETCH_FAILED'})
})
