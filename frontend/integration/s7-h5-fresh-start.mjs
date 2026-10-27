// A fresh Node process models an app restart; it is not a real browser/TLS test.
import assert from 'node:assert/strict'
import {createInterface} from 'node:readline'
import {initializeH5Platform} from '../common/h5-platform.js'
import {registeredAccountRuntime,startAccountStartup,readRuntimeV3Credential} from '../common/auth-runtime.js'
import {createMusicLibraryApi} from '../common/music-library-api.js'
import {createUniMusicLibraryTransport} from '../common/music-library-transport.js'

const origin='https://testserver',pending=new Map();let serial=0,csrf='',restartState
let receiveState
const received=new Promise(resolve=>{receiveState=resolve})
const input=createInterface({input:process.stdin})
input.on('line',line=>{
 const frame=JSON.parse(line)
 if(frame.restartState){restartState=frame.restartState;receiveState();return}
 const entry=pending.get(frame.id);assert.ok(entry);pending.delete(frame.id)
 assert.equal(frame.headers?.['set-cookie'],undefined);assert.equal(frame.data?.data?.refresh_token,undefined)
 csrf=frame.csrfCookie||'';entry(frame)
})
const rpc=args=>new Promise(resolve=>{const id=++serial;pending.set(id,resolve);process.stdout.write('S7_REQUEST '+JSON.stringify({id,...args})+'\n')})
await received
const values=new Map(Object.entries(restartState))
assert.equal(values.get('v3_auth_mode'),'registered');assert.equal(values.get('v3_h5_account_transport_state'),'ready')
assert.equal(values.has('v3_access_token'),false)
const uniApi={getStorageSync:key=>values.get(key)??'',setStorageSync:(key,value)=>values.set(key,value),removeStorageSync:key=>values.delete(key),$emit(){},
 request(options){rpc({method:options.method,path:new URL(options.url).pathname,data:options.data,header:options.header}).then(options.success,options.fail)}}
// This unauthorized GET returns no identity; it exposes only the same readable
// CSRF helper that document.cookie would expose. HttpOnly Refresh stays in Python.
const probe=await rpc({method:'GET',path:'/api/v3/auth/identity'})
assert.equal(probe.statusCode,401);assert.match(csrf,/^[A-Za-z0-9_-]{43}$/)
let refreshes=0
const fetchApi=async(url,options)=>{
 assert.equal(new URL(url).origin,origin);assert.equal(options.credentials,'include');assert.equal(options.redirect,'error')
 const path=new URL(url).pathname;if(path.endsWith('/refresh'))refreshes++
 const frame=await rpc({method:'POST',path,data:JSON.parse(options.body),header:{...options.headers,Origin:origin}})
 return {status:frame.statusCode,json:async()=>frame.data}
}
const result=initializeH5Platform({uniApi,target:'h5',apiOrigin:origin,locationOrigin:origin,
 accountDependencies:{ownerApprovedForNonProduction:true,browserSecurityAccepted:true,approvalRef:'isolated-asgi-only',approvedOrigin:origin,fetchApi,readCsrfCookie:()=>csrf}})
assert.equal(result.accountInstalled,true);assert.equal(registeredAccountRuntime.available,true)
await startAccountStartup(uniApi)
assert.equal(refreshes,1);assert.equal(registeredAccountRuntime.owner(),restartState.v3_public_user_id)
const token=readRuntimeV3Credential(uniApi);assert.ok(token)
const library=createMusicLibraryApi({enabled:true,getOwnerId:()=>values.get('v3_public_user_id'),request:createUniMusicLibraryTransport({baseUrl:origin,uniApi,getAccessToken:()=>readRuntimeV3Credential(uniApi)})})
assert.equal((await library.listMusicAssets()).items.length,1)
for(const value of values.values())assert.ok(!String(value).includes(token))
process.stdout.write('S7_FRONTEND_VERIFIED\n');input.close()
