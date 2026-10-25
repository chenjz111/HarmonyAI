import test from 'node:test'
import assert from 'node:assert/strict'
import * as runtimeModule from '../common/auth-runtime.js'
import {createRegisteredAuthClient} from '../common/registered-auth.js'
import {createUniMusicLibraryTransport} from '../common/music-library-transport.js'

function harness({now=Date.now,verifyGuest=async()=>({public_user_id:'guest-A',auth_type:'guest'}),request=async()=>{throw Object.assign(new Error('denied'),{code:'ACCOUNT_INPUT_INVALID'})}}={}){
 const values=new Map([['v3_access_token','legal-guest'],['v3_public_user_id','guest-A'],['v3_auth_epoch',0],['v3_flow_state','original-session']])
 const uni={getStorageSync:k=>values.get(k)??'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit(){}}
 let proof=null
 const secureStore={verified:true,keystoreBacked:true,atomicConsume:true,async take(){const p=proof;proof=null;return p},async clear(){proof=null},async write(p){proof=p}}
 const client=createRegisteredAuthClient({request,secureStore,enabled:true,now})
 const runtime=runtimeModule.createRegisteredIdentityRuntime({client,uniApi:uni,accepted:true,verifyGuest})
 return {values,uni,runtime,client}
}

test('failed bind recovers the same valid Guest only after server verification',async()=>{
 let verified=0
 const h=harness({verifyGuest:async token=>{verified++;assert.equal(token,'legal-guest');return {public_user_id:'guest-A',auth_type:'guest'}}})
 await assert.rejects(h.runtime.bind({}),{code:'ACCOUNT_INPUT_INVALID'})
 assert.equal(verified,1)
 assert.equal(runtimeModule.readRuntimeV3Credential(h.uni),'legal-guest')
 assert.equal(h.values.get('v3_flow_state'),'original-session')
 assert.equal(h.values.get('v3_public_user_id'),'guest-A')
})

test('failed login from Guest preserves its data after server verifies the original Guest',async()=>{
 const h=harness()
 await assert.rejects(h.runtime.login({}),{code:'ACCOUNT_INPUT_INVALID'})
 assert.equal(runtimeModule.readRuntimeV3Credential(h.uni),'legal-guest')
 assert.equal(h.values.get('v3_flow_state'),'original-session')
})

test('unknown bind retains original Guest credential but quarantines its authority',async()=>{
 const h=harness({verifyGuest:async()=>{throw new Error('offline')}})
 await assert.rejects(h.runtime.bind({}))
 assert.equal(h.values.get('v3_auth_mode'),'binding')
 assert.equal(h.values.get('v3_access_token'),'legal-guest')
 assert.equal(runtimeModule.readRuntimeV3Credential(h.uni),'')
})

test('401 cannot distinguish expired Guest from completed binding and must not declare registration',async()=>{
 const h=harness({verifyGuest:async()=>{throw Object.assign(new Error('invalid Guest'),{code:'UNAUTHENTICATED'})}})
 await assert.rejects(h.runtime.bind({}))
 assert.equal(runtimeModule.readRuntimeV3Credential(h.uni),'')
 assert.equal(h.values.get('v3_auth_mode'),'binding')
 assert.equal(h.values.get('v3_access_token'),'legal-guest')
})

test('retrying bind on the same page validates the quarantined Guest first',async()=>{
 let online=false,writes=0
 const h=harness({verifyGuest:async()=>{if(!online)throw new Error('offline');return {public_user_id:'guest-A',auth_type:'guest'}},
  request:async()=>{writes++;if(!online)throw new Error('offline');return {data:{public_user_id:'guest-A',access_token:'memory-access',refresh_token:'secure-proof',expires_at:new Date(Date.now()+60000).toISOString()}}}})
 await assert.rejects(h.runtime.bind({}))
 online=true
 await h.runtime.bind({})
 assert.equal(writes,2);assert.equal(h.values.get('v3_auth_mode'),'registered')
})

test('Home identity waits for registered startup before capturing credentials',async()=>{
 assert.equal(typeof runtimeModule.startAccountStartup,'function')
 assert.equal(typeof runtimeModule.waitForAccountStartup,'function')
 const h=harness();h.values.set('v3_auth_mode','registered')
 let finish,restores=0
 const active={available:true,restore:()=>{restores++;return new Promise(resolve=>{finish=()=>{h.values.set('v3_public_user_id','restored-A');resolve({public_user_id:'restored-A'})}})}}
 const first=runtimeModule.startAccountStartup(h.uni,active)
 const second=runtimeModule.startAccountStartup(h.uni,active)
 await Promise.resolve()
 assert.equal(restores,1)
 let completed=false
 const waiting=runtimeModule.waitForAccountStartup(h.uni).then(()=>{completed=true})
 await Promise.resolve();assert.equal(completed,false)
 finish();await Promise.all([first,second,waiting]);assert.equal(completed,true)
})

test('native account transport requires explicit HTTPS and redirect acceptance; H5 has no bearer fallback',async()=>{
 const transport=await import('../common/account-transport.js').catch(()=>({}))
 assert.equal(typeof transport.createNativeAccountTransport,'function')
 const calls=[],uniApi={request:args=>{calls.push(args);args.success({statusCode:200,data:{ok:true,data:{status:'ok'}}})}}
 const options={baseUrl:'https://accounts.example',uniApi,accepted:true,redirectsRejected:true}
 for(const settings of [{...options,accepted:false},{...options,baseUrl:'http://accounts.example'},{...options,redirectsRejected:false},{...options,platform:'h5'}]){
  await assert.rejects(transport.createNativeAccountTransport(settings)({method:'POST',path:'/api/v3/auth/login',data:{}}),{code:'ACCOUNT_FEATURE_UNAVAILABLE'})
 }
 assert.equal(calls.length,0)
 const request=transport.createNativeAccountTransport(options)
 await request({method:'POST',path:'/api/v3/auth/register-bind',data:{username:'alice',password:'synthetic-long-password'},accessToken:'legal-guest'})
 assert.equal(calls[0].header.Authorization,'Bearer legal-guest')
 assert.equal(calls[0].url,'https://accounts.example/api/v3/auth/register-bind')
 assert.equal(calls[0].timeout,15000)
 await assert.rejects(request({method:'POST',path:'https://evil.example/auth/login'}),{code:'ACCOUNT_FEATURE_UNAVAILABLE'})
 const secureStore={verified:true,keystoreBacked:true,atomicConsume:true,async take(){},async write(){},async clear(){}}
 assert.equal(transport.createNativeAccountRuntime({...options,baseUrl:'http://accounts.example',secureStore}).available,false)
})

test('actual App launch invokes restoration without enabling default account capability',async()=>{
 const {readFileSync}=await import('node:fs')
 const source=readFileSync(new URL('../App.vue',import.meta.url),'utf8')
 const {runInNewContext}=await import('node:vm')
 let starts=0
 const sandbox={uni:{},console:{log(){}},startAccountStartup:()=>{starts++;return Promise.resolve()},options:null}
 runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import[^\n]+\n/,'').replace('export default','options ='),sandbox)
 sandbox.options.onLaunch();sandbox.options.onShow()
 assert.equal(starts,2)
 assert.equal(runtimeModule.registeredAccountRuntime.available,false)
})

test('Guest recovery refuses authentication changes during server verification',async()=>{
 let finish
 const h=harness({verifyGuest:()=>new Promise(resolve=>{finish=resolve})})
 const binding=h.runtime.bind({})
 while(!finish)await Promise.resolve()
 h.values.set('v3_auth_epoch',h.values.get('v3_auth_epoch')+1)
 h.values.set('v3_public_user_id','other-owner')
 finish({public_user_id:'guest-A',auth_type:'guest'})
 await assert.rejects(binding)
 assert.equal(h.values.get('v3_auth_mode'),'binding','late verification cannot reauthorize a changed authentication instance')
 assert.equal(runtimeModule.readRuntimeV3Credential(h.uni),'')
})

test('identity call cannot adopt a new authentication instance before its first microtask',async()=>{
 const h=harness(),previous=globalThis.uni
 h.uni.request=args=>args.success({statusCode:200,data:{ok:true,data:{public_user_id:'other-owner',auth_type:'guest'}}})
 globalThis.uni=h.uni
 try{
  const {apiV3}=await import('../common/api-v3.js?startup-call-identity')
  const pending=apiV3.ensureIdentity()
  h.values.set('v3_access_token','other-token');h.values.set('v3_public_user_id','other-owner');h.values.set('v3_auth_epoch',1)
  await assert.rejects(pending,{code:'OWNER_CHANGED'})
 }finally{globalThis.uni=previous}
})

test('expired Access is refreshed before library mutation; old operation is never sent or replayed',async()=>{
 let clock=1000,refreshes=0,writes=0
 const h=harness({now:()=>clock,request:async args=>{
  if(args.path.endsWith('/refresh'))refreshes++
  return {data:{public_user_id:'guest-A',access_token:'access-'+clock,refresh_token:'proof-'+clock,expires_at:new Date(clock+10).toISOString()}}
 }})
 await h.runtime.login({})
 h.uni.request=args=>{writes++;args.success({statusCode:200,data:{ok:true,data:{status:'saved'}}})}
 const request=createUniMusicLibraryTransport({uniApi:h.uni,getAccessToken:()=>runtimeModule.readRuntimeV3Credential(h.uni)})
 clock+=20
 const first=await request({method:'PATCH',path:'/api/v3/music/assets/id/title',data:{user_title:'new',expected_version:0}})
 assert.equal(refreshes,1)
 assert.equal(writes,0)
 assert.equal(first.error.code,'AUTH_REFRESHED')
 assert.ok((await request({method:'PATCH',path:'/api/v3/music/assets/id/title',data:{user_title:'new',expected_version:0}})).data)
 assert.equal(writes,1)
 const previous=globalThis.uni;globalThis.uni=h.uni
 try {
  const {apiV3}=await import('../common/api-v3.js?ordinary-access-preflight')
  clock+=20
  await assert.rejects(apiV3.addFavorite('id','matched'),{code:'AUTH_REFRESHED'})
  assert.equal(refreshes,2);assert.equal(writes,1,'facade must also stop before mutation after refresh')
  await apiV3.addFavorite('id','matched');assert.equal(writes,2)
 }finally{globalThis.uni=previous}
})

test('unreadable startup identity storage cannot be mistaken for a first-time Guest',async()=>{
 const previous=globalThis.uni;let requests=0
 globalThis.uni={getStorageSync(){throw new Error('storage unavailable')},request(){requests++;throw new Error('unexpected network')}}
 try{
  const {apiV3}=await import('../common/api-v3.js?unreadable-startup')
  await assert.rejects(apiV3.ensureIdentity(),{code:'IDENTITY_REQUIRED'})
  await assert.rejects(apiV3.guestAuth(),{code:'IDENTITY_REQUIRED'})
  assert.equal(requests,0)
 }finally{globalThis.uni=previous}
})
