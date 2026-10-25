import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'

let sequence=0
const flush=()=>new Promise(setImmediate)
async function harness({storage=new Map(),intercept=null}={}) {
 const previous=globalThis.uni,requests=[],identities=new Map([['old-guest','A'],['registered-access','registered-A']])
 let minted=0,sessions=0
 const uni={getStorageSync:key=>storage.get(key)??'',setStorageSync:(key,value)=>storage.set(key,value),removeStorageSync:key=>storage.delete(key),$emit(){},
  request(args){
   requests.push(args)
   const answer=(status,data)=>args.success({statusCode:status,data:status<300?{ok:true,data}:{ok:false,error:{code:data}}})
   if(intercept?.(args,answer))return
   const path=new URL(args.url).pathname,token=(args.header.Authorization||'').slice(7)
   if(path==='/api/v3/auth/guest'){const access_token='minted-'+(++minted);identities.set(access_token,'guest-'+minted);answer(201,{access_token,public_user_id:'guest-'+minted});return}
   if(path==='/api/v3/auth/identity'){const owner=identities.get(token);answer(owner?200:401,owner?{public_user_id:owner,auth_type:token==='registered-access'?'registered':'guest'}:'UNAUTHENTICATED');return}
   if(path==='/api/v3/sessions'){answer(201,{session_id:'session-'+(++sessions)});return}
   throw new Error('unexpected synthetic route '+path)
  }}
 globalThis.uni=uni
 const api=(await import(`../common/api-v3.js?continuity=${++sequence}`)).apiV3
 function page(){
  const script=readFileSync(new URL('../pages/entry/entry.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
   .replace(/import\s*\{ apiV3 \}\s*from[^\n]+/,'const apiV3=api').replace('export default {','options = {')
  const sandbox={api,uni,options:null};runInNewContext(script,sandbox)
  const options=sandbox.options,value=options.data();for(const [name,fn] of Object.entries(options.methods))value[name]=fn.bind(value)
  return {value,show:()=>options.onShow.call(value)}
 }
 return {api,page,storage,requests,minted:()=>minted,sessions:()=>sessions,close(){globalThis.uni=previous}}
}

test('home re-entry starts a new assessment without replacing the guest owner',async()=>{
 const h=await harness();try{const p=h.page();await p.value.init();const owner=h.storage.get('v3_public_user_id'),token=h.storage.get('v3_access_token');await p.value.init()
 assert.equal(h.minted(),1);assert.equal(h.sessions(),2);assert.equal(h.storage.get('v3_public_user_id'),owner);assert.equal(h.storage.get('v3_access_token'),token)
 }finally{h.close()}
})
test('restart validates the existing four-claim guest with the server and never renews it',async()=>{
 const storage=new Map([['v3_access_token','old-guest'],['v3_public_user_id','A'],['v3_auth_epoch',4]])
 const h=await harness({storage});try{await h.page().value.init();assert.equal(h.minted(),0);assert.equal(storage.get('v3_access_token'),'old-guest');assert.equal(storage.get('v3_auth_epoch'),4);assert.equal(h.requests[0].method,'GET');assert.ok(h.requests[0].url.endsWith('/auth/identity'))}finally{h.close()}
})
for(const status of [401,503])test(`identity verification ${status} retains credentials and never silently creates another owner`,async()=>{
 const storage=new Map([['v3_access_token','old-guest'],['v3_public_user_id','A']])
 const h=await harness({storage,intercept:(args,answer)=>{if(args.url.endsWith('/auth/identity')){answer(status,status===401?'UNAUTHENTICATED':'UNAVAILABLE');return true}}});try{
 const p=h.page();await p.value.init();assert.ok(p.value.error);assert.equal(h.minted(),0);assert.equal(h.sessions(),0);assert.equal(storage.get('v3_access_token'),'old-guest')
 }finally{h.close()}
})
test('a public owner label without a credential cannot recover or replace an identity',async()=>{
 const h=await harness({storage:new Map([['v3_public_user_id','A']])});try{const p=h.page();await p.value.init();assert.ok(p.value.error);assert.equal(h.requests.length,0)}finally{h.close()}
})
test('concurrent home startup creates only one guest and one assessment session',async()=>{
 const h=await harness();try{const p=h.page();await Promise.all([p.value.init(),p.value.init()]);assert.equal(h.minted(),1);assert.equal(h.sessions(),1)}finally{h.close()}
})
test('registered access is validated without being overwritten by guest initialization',async()=>{
 const storage=new Map([['v3_access_token','registered-access'],['v3_public_user_id','registered-A']])
 const h=await harness({storage});try{await h.page().value.init();assert.equal(h.minted(),0);assert.equal(storage.get('v3_access_token'),'registered-access')}finally{h.close()}
})
test('late identity verification cannot restore a previous authentication instance',async()=>{
 let release
 const storage=new Map([['v3_access_token','old-guest'],['v3_public_user_id','A'],['v3_auth_epoch',0]])
 const h=await harness({storage,intercept:(args,answer)=>{if(args.url.endsWith('/auth/identity')){release=()=>answer(200,{public_user_id:'A',auth_type:'guest'});return true}}});try{
 const p=h.page(),pending=p.value.init();for(let i=0;i<10&&!release;i++)await flush();assert.equal(typeof release,'function');storage.set('v3_access_token','registered-access');storage.set('v3_public_user_id','registered-A');storage.set('v3_auth_epoch',2);release();await pending
 assert.ok(p.value.error);assert.equal(h.sessions(),0);assert.equal(storage.get('v3_public_user_id'),'registered-A')
 }finally{h.close()}
})
test('late session creation cannot overwrite the newly selected owner flow',async()=>{
 let release
 const storage=new Map([['v3_access_token','old-guest'],['v3_public_user_id','A'],['v3_auth_epoch',0]])
 const h=await harness({storage,intercept:(args,answer)=>{if(args.url.endsWith('/sessions')){release=()=>answer(201,{session_id:'old-session'});return true}}});try{
 const p=h.page(),pending=p.value.init();for(let i=0;i<10&&!release;i++)await flush();assert.equal(typeof release,'function');storage.set('v3_access_token','registered-access');storage.set('v3_public_user_id','registered-A');storage.set('v3_auth_epoch',2);storage.set('v3_flow_state',JSON.stringify({session_id:'new-owner-session'}));release();await pending
 assert.ok(p.value.error);assert.equal(JSON.parse(storage.get('v3_flow_state')).session_id,'new-owner-session')
 }finally{h.close()}
})
test('identity switch after session settlement but before page continuation cannot overwrite the new flow',async()=>{
 const storage=new Map([['v3_access_token','old-guest'],['v3_public_user_id','A'],['v3_auth_epoch',0]])
 const h=await harness({storage,intercept:(args,answer)=>{if(args.url.endsWith('/sessions')){
  setImmediate(()=>{answer(201,{session_id:'old-session'});queueMicrotask(()=>{
   storage.set('v3_access_token','registered-access');storage.set('v3_public_user_id','registered-A');storage.set('v3_auth_epoch',2)
   storage.set('v3_flow_state',JSON.stringify({session_id:'new-owner-session'}))
  })});return true
 }}});try{const p=h.page();await p.value.init();assert.ok(p.value.error);assert.equal(JSON.parse(storage.get('v3_flow_state')).session_id,'new-owner-session');assert.equal(p.value.entry,null)}finally{h.close()}
})
