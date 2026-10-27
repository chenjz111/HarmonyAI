// Existing Account R1 client/runtime against actual ASGI; secure storage is a substitute.
import assert from 'node:assert/strict'
import {createInterface} from 'node:readline'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {createNativeAccountRuntime} from '../common/account-transport.js'
import {startAccountStartup,readRuntimeV3Credential} from '../common/auth-runtime.js'
import {createMusicLibraryApi} from '../common/music-library-api.js'
import {createUniMusicLibraryTransport} from '../common/music-library-transport.js'

const pending=new Map();let serial=0,refreshRequests=0,drop=null,offline=false
const registeredSecrets=new Set()
const input=createInterface({input:process.stdin})
input.on('line',line=>{
 const response=JSON.parse(line),entry=pending.get(response.id);assert.ok(entry);pending.delete(response.id)
 if(entry.path!=='/api/v3/auth/guest')for(const key of ['access_token','refresh_token']){
  const secret=response.data?.data?.[key];if(secret)registeredSecrets.add(secret)
 }
 entry.resolve(response)
})
const rpc=args=>new Promise(resolve=>{const id=++serial;pending.set(id,{resolve,path:args.path});process.stdout.write('S7_REQUEST '+JSON.stringify({id,...args})+'\n')})
const PASSWORD='synthetic-safe-long-passphrase'
function store(){let proof=null;return {verified:true,keystoreBacked:true,atomicConsume:true,
 async take(){const value=proof;proof=null;return value},async write(value){proof=value},async clear(){proof=null},peek:()=>proof}}
function platform(guest){
 const values=new Map([['v3_access_token',guest.access_token],['v3_public_user_id',guest.public_user_id],['v3_auth_epoch',0],['v3_flow_state','retained-Guest-flow']])
 const uni={getStorageSync:k=>values.get(k)??'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit(){},
  request(args){
   if(offline){args.fail();return}
   const path=new URL(args.url).pathname
   if(path.endsWith('/refresh'))refreshRequests++
   rpc({method:args.method,path,data:args.data,header:args.header}).then(response=>{
    if(drop===path){drop=null;args.fail();return}args.success(response)
   },args.fail)
  }}
 return {uni,values,secureStore:store()}
}
const options=h=>({baseUrl:'https://testserver',uniApi:h.uni,secureStore:h.secureStore,accepted:true,redirectsRejected:true})
const guest=async()=>{const r=await rpc({method:'POST',path:'/api/v3/auth/guest'});assert.equal(r.statusCode,201);return r.data.data}
const requestFor=h=>createUniMusicLibraryTransport({baseUrl:'https://testserver',uniApi:h.uni,getAccessToken:()=>readRuntimeV3Credential(h.uni)})
const libraryFor=h=>createMusicLibraryApi({request:requestFor(h),getOwnerId:()=>h.values.get('v3_public_user_id'),enabled:true})
const identity=(token)=>rpc({method:'GET',path:'/api/v3/auth/identity',header:{Authorization:'Bearer '+token}})

const original=await guest(),a=platform(original)
let runtime=createNativeAccountRuntime(options(a))
assert.equal((await libraryFor(a).listMusicAssets()).items.length,1)
await runtime.bind({username:'account_a',password:PASSWORD})
assert.ok(runtime.owner()===original.public_user_id)
assert.equal(a.values.has('v3_access_token'),false)
assert.equal((await identity(original.access_token)).statusCode,401)
assert.equal((await libraryFor(a).listMusicAssets()).items.length,1,'binding retains owner history')
assert.equal(a.values.get('v3_flow_state'),'retained-Guest-flow')
let oldProof=a.secureStore.peek()
runtime=createNativeAccountRuntime(options(a)) // simulated process restart: no old in-memory Access
const before=refreshRequests
globalThis.uni=a.uni
const {apiV3}=await import('../common/api-v3.js')
const appScript=readFileSync(new URL('../App.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
const app={options:null,uni:a.uni,console:{log(){}},startAccountStartup:uni=>startAccountStartup(uni,runtime)}
runInNewContext(appScript.replace(/import[^\n]+\n/,'').replace('export default','options ='),app)
app.options.onLaunch();app.options.onShow()
assert.equal((await apiV3.ensureIdentity()).public_user_id,original.public_user_id,'Home waits for actual App startup restoration')
assert.equal(refreshRequests,before+1)
assert.ok(a.secureStore.peek()!==oldProof)
assert.equal((await libraryFor(a).listMusicAssets()).items.length,1)
const refreshBefore=refreshRequests
await Promise.all([runtime.refresh(),runtime.refresh()])
assert.equal(refreshRequests,refreshBefore+1)
let access=readRuntimeV3Credential(a.uni)
await rpc({method:'POST',path:'/api/v3/__test__/expire-session',header:{Authorization:'Bearer '+access}})
assert.equal((await identity(access)).statusCode,401)
await assert.rejects(runtime.refresh(),{code:'UNAUTHENTICATED'})
assert.equal(readRuntimeV3Credential(a.uni),'')
await runtime.login({username:'account_a',password:PASSWORD})

const b=platform(await guest()),bob=createNativeAccountRuntime(options(b))
await bob.bind({username:'account_b',password:PASSWORD})
assert.equal((await libraryFor(b).listMusicAssets()).items.length,0)
await bob.login({username:'account_a',password:PASSWORD})
assert.equal((await libraryFor(b).listMusicAssets()).items.length,1)
await bob.login({username:'account_b',password:PASSWORD})
assert.equal((await libraryFor(b).listMusicAssets()).items.length,0,'login never merges Guest/other-owner music')

const cGuest=await guest(),c=platform(cGuest),charlie=createNativeAccountRuntime(options(c))
await assert.rejects(charlie.bind({username:'account_a',password:PASSWORD}))
assert.ok(readRuntimeV3Credential(c.uni)===cGuest.access_token,'conflicting bind recovers lawful Guest')
offline=true
await assert.rejects(charlie.bind({username:'account_c',password:PASSWORD}))
assert.equal(c.values.get('v3_auth_mode'),'binding')
assert.equal(readRuntimeV3Credential(c.uni),'')
offline=false
await assert.rejects(charlie.bind({username:'account_a',password:PASSWORD}))
assert.ok(readRuntimeV3Credential(c.uni)===cGuest.access_token)
await rpc({method:'POST',path:'/api/v3/__test__/expire-guest',header:{Authorization:'Bearer '+cGuest.access_token}})
globalThis.uni=c.uni
await assert.rejects(apiV3.ensureIdentity(),{code:'UNAUTHENTICATED'})
assert.ok(c.values.get('v3_access_token')===cGuest.access_token,'expired Guest is not silently replaced')
await assert.rejects(charlie.bind({username:'account_c',password:PASSWORD}))
assert.equal(c.values.get('v3_auth_mode'),'binding','expired Guest 401 is not proof of registration')
assert.equal(apiV3.canStartNewGuest(),false)
await charlie.login({username:'account_a',password:PASSWORD})
assert.equal((await libraryFor(c).listMusicAssets()).items.length,1)

const lostGuest=await guest(),lost=platform(lostGuest)
let lostRuntime=createNativeAccountRuntime(options(lost))
drop='/api/v3/auth/register-bind'
await assert.rejects(lostRuntime.bind({username:'lost_bind',password:PASSWORD}))
assert.equal(lost.values.get('v3_auth_mode'),'binding')
assert.ok(readRuntimeV3Credential(lost.uni)==='')
lostRuntime=createNativeAccountRuntime(options(lost))
await assert.rejects(startAccountStartup(lost.uni,lostRuntime))
await lostRuntime.login({username:'lost_bind',password:PASSWORD})
drop='/api/v3/auth/refresh'
await assert.rejects(lostRuntime.refresh())
assert.ok(lost.secureStore.peek()===null)
const countAfterLoss=refreshRequests
lostRuntime=createNativeAccountRuntime(options(lost))
await assert.rejects(startAccountStartup(lost.uni,lostRuntime))
assert.equal(refreshRequests,countAfterLoss,'lost Refresh response must not retry consumed proof')

// A consumed proof replay revokes the real family, including its current Access.
await runtime.login({username:'account_a',password:PASSWORD})
oldProof=a.secureStore.peek();await runtime.refresh();access=readRuntimeV3Credential(a.uni)
assert.equal((await rpc({method:'POST',path:'/api/v3/auth/refresh',data:{refresh_token:oldProof}})).statusCode,401)
assert.equal((await identity(access)).statusCode,401)
await runtime.login({username:'account_a',password:PASSWORD});access=readRuntimeV3Credential(a.uni)
await runtime.logout({allDevices:true})
assert.equal((await identity(access)).statusCode,401)
assert.equal(readRuntimeV3Credential(a.uni),'')
assert.ok(a.secureStore.peek()===null)
// Explicit logout -> normal Home Guest issuance; account history stays owned.
runtime=createNativeAccountRuntime(options(a)) // app process restarted after logout
const refreshesAfterLogout=refreshRequests
await startAccountStartup(a.uni,runtime)
assert.equal(refreshRequests,refreshesAfterLogout,'signed-out startup must not send Refresh')
assert.equal(runtime.canUseGuestAfterLogout(),true)
globalThis.uni=a.uni
await assert.rejects(apiV3.ensureIdentity(),{code:'SIGNED_OUT'})
await runtime.useGuestAfterLogout({confirmed:true})
globalThis.uni=a.uni
const newGuest=await apiV3.ensureIdentity()
assert.notEqual(newGuest.public_user_id,original.public_user_id)
assert.equal((await libraryFor(a).listMusicAssets()).items.length,0)
await runtime.login({username:'account_a',password:PASSWORD})
assert.equal((await libraryFor(a).listMusicAssets()).items.length,1,'returning to Guest never transfers account history')

offline=true
await assert.rejects(bob.logout())
assert.equal(bob.canUseGuestAfterLogout(),false,'unknown logout cannot authorize identity replacement')
assert.equal(readRuntimeV3Credential(b.uni),'')
assert.ok(b.secureStore.peek()===null)
offline=false
// Real R1 password endpoint: all old session authority dies, no client replay.
await bob.login({username:'account_b',password:PASSWORD})
const beforePasswordAccess=readRuntimeV3Credential(b.uni),beforePasswordProof=b.secureStore.peek()
const NEW_PASSWORD='synthetic-replacement-long-passphrase'
await bob.changePassword({current_password:PASSWORD,new_password:NEW_PASSWORD})
assert.equal(readRuntimeV3Credential(b.uni),'');assert.equal(b.secureStore.peek(),null)
assert.equal((await identity(beforePasswordAccess)).statusCode,401)
assert.equal((await rpc({method:'POST',path:'/api/v3/auth/refresh',data:{refresh_token:beforePasswordProof}})).statusCode,401)
await assert.rejects(bob.login({username:'account_b',password:PASSWORD}),{code:'UNAUTHENTICATED'})
await bob.login({username:'account_b',password:NEW_PASSWORD})
assert.equal((await libraryFor(b).listMusicAssets()).items.length,0)

for(const h of [a,b,c,lost]){
 const ordinary=JSON.stringify([...h.values])
 assert.ok(!ordinary.includes(PASSWORD),'password must never persist in ordinary storage')
 assert.ok(!ordinary.includes(NEW_PASSWORD),'replacement password must never persist in ordinary storage')
 for(const secret of registeredSecrets)assert.ok(!ordinary.includes(secret),'registered credential must never persist in ordinary storage')
}
process.stdout.write('S7_FRONTEND_VERIFIED\n');input.close()
