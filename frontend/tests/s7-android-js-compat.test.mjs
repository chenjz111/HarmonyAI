import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
function load(name,expression,extras={}){
 const source=readFileSync(new URL('../common/'+name,import.meta.url),'utf8')
 const sandbox={...extras,result:null}
 runInNewContext('Object.hasOwn=undefined;'+source.replace(/^import[^\n]+\n/gm,'').replaceAll('import.meta.env','env').replaceAll('export ','')+';result='+expression,sandbox)
 return sandbox.result
}
test('My page card projection works in the actual base engine without Object.hasOwn',()=>{
 const preview=load('music-library-state.js','createMusicLibraryPreview')
 const result=preview('ready',[{music_id:'one',availability:'ready',duration_seconds:24,is_favorite:true}])
 assert.equal(result.history.length,1);assert.equal(result.history[0].can_open,true)
 assert.equal(preview('ready',[{availability:'toString'}]).history[0].availability,'missing')
})
test('library and feedback adapters still require an own data property on older engines',async()=>{
 for(const [file,factory,method] of [['music-library-api.js','createMusicLibraryApi','listMusicAssets'],['feedback-api.js','createFeedbackApi','list']]){
  const create=load(file,factory)
  let response={data:{items:[]}}
  const api=create({request:async()=>response,getOwnerId:()=> 'synthetic-owner',getAccessToken:()=> 'synthetic-token',getAuthEpoch:()=>0,enabled:true})
  assert.equal((await api[method]()).items.length,0)
  response=Object.create({data:{items:[]}})
  await assert.rejects(()=>api[method](),{code:'INVALID_RESPONSE'})
 }
})
test('real library transport parses success on a base without Object.hasOwn',async()=>{
 const create=load('music-library-transport.js','createUniMusicLibraryTransport',{
  getApiOrigin:()=> 'https://synthetic.example',nativeTlsOptions:()=>({sslVerify:true}),platformNetworkApi:x=>x,
  hasAccountRuntime:()=>false,prepareAccountRequest:async()=>{},readRuntimeV3Credential:()=> 'synthetic-token'})
 const transport=create({uniApi:{request(args){args.success({statusCode:200,data:{ok:true,data:{items:[]}}})}},getAccessToken:()=> 'synthetic-token'})
 const response=await transport({method:'GET',path:'/api/v3/me/music-assets'})
 assert.equal(response.data.items.length,0)
})

test('real library is enabled only in the explicit USB Android development profile',()=>{
 const env={DEV:true,MODE:'development',VITE_S7_USB_GUEST_DEBUG:'1',VITE_S7_USB_LIBRARY_LIVE:'1',VITE_API_BASE_URL:'http://127.0.0.1:8000'}
 const value=(setting,info={uniPlatform:'app',osName:'android'})=>load('music-library-transport.js','MUSIC_LIBRARY_LIVE_ENABLED',{env:setting,uni:{getSystemInfoSync:()=>info}})
 assert.equal(value(env),true)
 for(const setting of [{...env,DEV:false},{...env,MODE:'production'},{...env,VITE_S7_USB_LIBRARY_LIVE:undefined},{...env,VITE_API_BASE_URL:'http://localhost:8000'}])assert.equal(value(setting),false)
 assert.equal(value(env,{uniPlatform:'app',osName:'ios'}),false)
 assert.equal(value(env,{uniPlatform:'web',osName:'android'}),false)
})
