// Real ASGI cookie jar peer; not actual browser TLS/Cookie acceptance.
import assert from 'node:assert/strict'
import {createInterface} from 'node:readline'
import {createH5AccountRuntime} from '../common/h5-account.js'
import {initializeH5Platform} from '../common/h5-platform.js'
import {startAccountStartup,readRuntimeV3Credential,registeredAccountRuntime} from '../common/auth-runtime.js'
import {createMusicLibraryApi} from '../common/music-library-api.js'
import {createUniMusicLibraryTransport} from '../common/music-library-transport.js'
import {profile} from './s7-profile-harness.mjs'
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
 const listeners=new Map(),toasts=[]
 const uni={getStorageSync:k=>values.get(k)??'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit(){},
  request(options){rpc({method:options.method,path:new URL(options.url).pathname,data:options.data,header:options.header}).then(options.success,options.fail)}}
 uni.$on=(name,callback)=>listeners.set(name,callback);uni.$off=name=>listeners.delete(name);uni.$emit=name=>listeners.get(name)?.()
 uni.showToast=options=>toasts.push(options.title)
 return {uni,values,toasts}
}
const runtimeFor=h=>createH5AccountRuntime({uniApi:h.uni,baseUrl:origin,locationOrigin:origin,configuredOrigin:origin,
 fetchApi,readCsrfCookie:()=>csrf,accepted:true,target:'h5'})
const library=h=>createMusicLibraryApi({enabled:true,getOwnerId:()=>h.values.get('v3_public_user_id'),request:createUniMusicLibraryTransport({baseUrl:origin,uniApi:h.uni,getAccessToken:()=>readRuntimeV3Credential(h.uni)})})
const original=await guest(),a=platform(original)
const startup=initializeH5Platform({uniApi:a.uni,target:'h5',apiOrigin:origin,locationOrigin:origin,
 accountDependencies:{ownerApprovedForNonProduction:true,browserSecurityAccepted:true,approvalRef:'isolated-asgi-only',approvedOrigin:origin,fetchApi,readCsrfCookie:()=>csrf}})
assert.equal(startup.accountInstalled,true)
let runtime=registeredAccountRuntime
assert.equal((await library(a).listMusicAssets()).items.length,1)
const my=profile(a,{registeredAccountRuntime,startAccountStartup});my.options.onLoad.call(my.page);await my.options.onShow.call(my.page)
assert.equal(my.page.accountAvailable,true)
my.page.accountMode='bind';my.page.accountUsername='browser_a';my.page.accountPassword=password
await my.page.submitAccount()
assert.equal(my.page.accountError,'');assert.equal(my.page.accountPassword,'');assert.equal(my.page.accountOwner,original.public_user_id)
assert.ok(a.toasts.includes('身份验证已完成'))
my.options.onUnload.call(my.page)
assert.equal(runtime.owner(),original.public_user_id);assert.equal(a.values.has('v3_access_token'),false)
assert.equal(a.values.get('v3_flow_state'),'retained-guest-flow')
assert.equal((await library(a).listMusicAssets()).items.length,1)
const before=refreshes;runtime=runtimeFor(a);await startAccountStartup(a.uni)
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
await other.login({username:'browser_a',password:'synthetic-replaced-browser-password'})
for(const h of [a,b])for(const value of h.values.values())assert.ok(![...secrets].some(secret=>String(value).includes(secret)))
const restartState=Object.fromEntries(['v3_auth_mode','v3_public_user_id','v3_auth_epoch','v3_h5_account_transport_state'].map(key=>[key,b.values.get(key)]))
assert.equal(restartState.v3_auth_mode,'registered');assert.equal(restartState.v3_h5_account_transport_state,'ready')
// Only non-credential UI state crosses the test supervisor; HttpOnly Cookie
// remains exclusively in the backend TestClient cookie jar.
process.stdout.write('S7_RESTART_STATE '+JSON.stringify(restartState)+'\n')
process.stdout.write('S7_FRONTEND_VERIFIED\n');input.close()
