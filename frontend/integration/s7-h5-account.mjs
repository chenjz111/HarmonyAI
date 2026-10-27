// Real ASGI cookie jar peer; not actual browser TLS/Cookie acceptance.
import assert from 'node:assert/strict'
import {createInterface} from 'node:readline'
import {createH5AccountRuntime} from '../common/h5-account.js'
import {startAccountStartup,readRuntimeV3Credential} from '../common/auth-runtime.js'
import {createMusicLibraryApi} from '../common/music-library-api.js'
import {createUniMusicLibraryTransport} from '../common/music-library-transport.js'
const origin='https://testserver',password='synthetic-safe-long-passphrase'
const pending=new Map(),secrets=new Set();let serial=0,csrf='',dropRefresh=false,refreshes=0,guestCreations=0
const input=createInterface({input:process.stdin})
input.on('line',line=>{
 const response=JSON.parse(line),entry=pending.get(response.id);assert.ok(entry);pending.delete(response.id)
 assert.equal(response.headers?.['set-cookie'],undefined,'HttpOnly credentials never enter JS RPC')
 assert.equal(response.data?.data?.refresh_token,undefined)
 csrf=response.csrfCookie||''
 if(entry.path!=='/api/v3/auth/guest'&&response.data?.data?.access_token)secrets.add(response.data.data.access_token)
 entry.resolve(response)
})
const rpc=args=>new Promise(resolve=>{const id=++serial;pending.set(id,{resolve,path:args.path});process.stdout.write('S7_REQUEST '+JSON.stringify({id,...args})+'\n')})
const guest=async()=>{guestCreations++;const r=await rpc({method:'POST',path:'/api/v3/auth/guest'});assert.equal(r.statusCode,201);return r.data.data}
const fetchApi=async(url,options)=>{
 assert.equal(new URL(url).origin,origin);assert.equal(options.credentials,'include');assert.equal(options.redirect,'error')
 const path=new URL(url).pathname,data=JSON.parse(options.body);assert.equal(data.refresh_token,undefined)
 if(path.endsWith('/refresh'))refreshes++
 const r=await rpc({method:'POST',path,data,header:{...options.headers,Origin:origin}})
 if(dropRefresh&&path.endsWith('/refresh')){dropRefresh=false;throw new Error('synthetic lost refresh response')}
 return {status:r.statusCode,json:async()=>r.data}
}
function platform(guest){
 const values=new Map([['v3_access_token',guest.access_token],['v3_public_user_id',guest.public_user_id],['v3_auth_epoch',0],['v3_flow_state','retained-guest-flow']])
 const uni={getStorageSync:k=>values.get(k)??'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit(){},
  request(options){rpc({method:options.method,path:new URL(options.url).pathname,data:options.data,header:options.header}).then(options.success,options.fail)}}
 return {uni,values}
}
const runtimeFor=h=>createH5AccountRuntime({uniApi:h.uni,baseUrl:origin,locationOrigin:origin,configuredOrigin:origin,
 fetchApi,readCsrfCookie:()=>csrf,accepted:true,target:'h5'})
const library=h=>createMusicLibraryApi({enabled:true,getOwnerId:()=>h.values.get('v3_public_user_id'),request:createUniMusicLibraryTransport({baseUrl:origin,uniApi:h.uni,getAccessToken:()=>readRuntimeV3Credential(h.uni)})})
const original=await guest(),a=platform(original)
let runtime=runtimeFor(a)
assert.equal((await library(a).listMusicAssets()).items.length,1)
await runtime.bind({username:'browser_a',password})
assert.equal(runtime.owner(),original.public_user_id);assert.equal(a.values.has('v3_access_token'),false)
assert.equal(a.values.get('v3_flow_state'),'retained-guest-flow')
assert.equal((await library(a).listMusicAssets()).items.length,1)
const before=refreshes;runtime=runtimeFor(a);await startAccountStartup(a.uni,runtime)
assert.equal(refreshes,before+1);assert.equal(runtime.owner(),original.public_user_id)
assert.equal((await library(a).listMusicAssets()).items.length,1)
await runtime.refresh()
const invalid=await rpc({method:'POST',path:'/api/v3/auth/browser/refresh',data:{},header:{Origin:origin,'X-CSRF-Token':'B'.repeat(43)}})
assert.equal(invalid.statusCode,401)
assert.equal((await library(a).listMusicAssets()).items.length,1)
await runtime.logout({allDevices:false});assert.equal(runtime.canUseGuestAfterLogout(),true)
runtime=runtimeFor(a);await startAccountStartup(a.uni,runtime);assert.equal(runtime.canUseGuestAfterLogout(),true)
const creations=guestCreations;await runtime.useGuestAfterLogout({confirmed:true});assert.equal(guestCreations,creations)

const another=await guest(),b=platform(another);let other=runtimeFor(b)
assert.equal((await library(b).listMusicAssets()).items.length,0)
await assert.rejects(other.login({username:'browser_a',password:'synthetic-wrong-passphrase'}))
assert.equal(b.values.get('v3_public_user_id'),another.public_user_id,'failed login preserves verified Guest')
await other.login({username:'browser_a',password});assert.equal(other.owner(),original.public_user_id)
assert.equal((await library(b).listMusicAssets()).items.length,1,'login selects account without importing Guest data')
dropRefresh=true;await assert.rejects(other.refresh())
const count=refreshes;other=runtimeFor(b);await assert.rejects(startAccountStartup(b.uni,other));assert.equal(refreshes,count)
assert.equal(readRuntimeV3Credential(b.uni),'');assert.equal(guestCreations,2)
await other.login({username:'browser_a',password})
await other.changePassword({current_password:password,new_password:'synthetic-replaced-browser-password'})
assert.equal(readRuntimeV3Credential(b.uni),'')
await assert.rejects(other.login({username:'browser_a',password}))
await other.login({username:'browser_a',password:'synthetic-replaced-browser-password'})
assert.equal((await library(b).listMusicAssets()).items.length,1)
await other.logout({allDevices:true})
other=runtimeFor(b);await startAccountStartup(b.uni,other)
assert.equal(other.canUseGuestAfterLogout(),true)
for(const h of [a,b])for(const value of h.values.values())assert.ok(![...secrets].some(secret=>String(value).includes(secret)))
process.stdout.write('S7_FRONTEND_VERIFIED\n');input.close()
