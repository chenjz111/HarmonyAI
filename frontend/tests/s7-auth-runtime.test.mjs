import test from 'node:test'
import assert from 'node:assert/strict'
import {createRegisteredAuthClient} from '../common/registered-auth.js'
import {createRegisteredIdentityRuntime,startAccountStartup} from '../common/auth-runtime.js'
import {readV3AccessToken,createUniMusicLibraryTransport} from '../common/music-library-transport.js'

function harness({accepted=true,request=null}={}){
 const values=new Map([['v3_access_token','old-guest'],['v3_public_user_id','guest-A'],['v3_auth_epoch',0],['v3_flow_state','old-flow']]),events=[],calls=[]
 const uni={getStorageSync:k=>values.get(k)??'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit:name=>events.push(name)}
 let proof=null,clock=0
 const secureStore={verified:true,keystoreBacked:true,atomicConsume:true,async take(){const v=proof;proof=null;return v},async clear(){proof=null},async write(v){proof=v}}
 const client=createRegisteredAuthClient({enabled:true,secureStore,now:()=>clock,request:async args=>{calls.push(args);if(request)return request(args);return {data:{public_user_id:args.path.endsWith('/register-bind')?'guest-A':'registered-B',access_token:'memory-access',refresh_token:'secure-proof',expires_at:'2026-10-25T12:00:00Z'}}}})
 const runtime=createRegisteredIdentityRuntime({client,uniApi:uni,accepted})
 const restart=()=>createRegisteredIdentityRuntime({client:createRegisteredAuthClient({enabled:true,secureStore,now:()=>clock,request:async args=>{calls.push(args);throw new Error('unexpected restart network')}}),uniApi:uni,accepted})
 return {values,events,calls,uni,runtime,client,restart,proof:()=>proof,expire:()=>{clock=Date.parse('2026-10-26T00:00:00Z')}}
}

test('default unavailable account integration issues no request and preserves valid Guest',async()=>{
 const h=harness({accepted:false});await assert.rejects(h.runtime.login({}),{code:'ACCOUNT_FEATURE_UNAVAILABLE'});assert.equal(h.calls.length,0);assert.equal(readV3AccessToken(h.uni),'old-guest')
})

test('registered login shares runtime-only bearer with the existing facade and library transport',async()=>{
 const h=harness();await h.runtime.login({username:'alice',password:'synthetic-long-password'})
 assert.equal(readV3AccessToken(h.uni),'memory-access');assert.equal(h.values.get('v3_public_user_id'),'registered-B');assert.equal(h.values.has('v3_flow_state'),false);assert.equal(h.proof(),'secure-proof')
 assert.ok(!JSON.stringify([...h.values]).includes('memory-access'));assert.ok(!JSON.stringify([...h.values]).includes('secure-proof'))
 const previous=globalThis.uni;let authorization
 h.uni.request=args=>{authorization=args.header.Authorization;args.success({statusCode:200,data:{ok:true,data:{public_user_id:'registered-B',auth_type:'registered'}}})}
 globalThis.uni=h.uni
 try{const {apiV3}=await import('../common/api-v3.js?runtime-read');await apiV3.ensureIdentity();assert.equal(authorization,'Bearer memory-access')
 const transport=createUniMusicLibraryTransport({uniApi:h.uni,getAccessToken:()=>readV3AccessToken(h.uni)});await transport({method:'GET',path:'/synthetic'});assert.equal(authorization,'Bearer memory-access')
 }finally{globalThis.uni=previous}
})

test('expired registered selection cannot fall back to a leftover Guest credential',async()=>{
 const h=harness();await h.runtime.login({});h.values.set('v3_access_token','stale-guest');h.expire();assert.equal(readV3AccessToken(h.uni),'')
})

test('restart marker without an installed verified adapter never mints another Guest',async()=>{
 const values=new Map([['v3_auth_mode','registered'],['v3_access_token','stale-guest']]);let calls=0
 const previous=globalThis.uni;globalThis.uni={getStorageSync:k=>values.get(k)??'',request(){calls++}}
 try{const {apiV3}=await import('../common/api-v3.js?runtime-restart');assert.equal(readV3AccessToken(globalThis.uni),'');await assert.rejects(apiV3.ensureIdentity(),{code:'IDENTITY_REQUIRED'});assert.equal(calls,0)}finally{globalThis.uni=previous}
})

test('binding captures the legitimate Guest bearer and never sends it as a data merge request',async()=>{
 const h=harness();await h.runtime.bind({username:'alice',password:'synthetic-long-password'});assert.equal(h.calls[0].path,'/api/v3/auth/register-bind');assert.equal(h.calls[0].accessToken,'old-guest');assert.deepEqual(Object.keys(h.calls[0].data).sort(),['password','username']);assert.equal(h.values.has('v3_access_token'),false)
})

test('unknown login result quarantines original Guest until authenticated server verification',async()=>{
 const h=harness({request:async()=>{throw new Error('lost response')}});await assert.rejects(h.runtime.login({}));assert.equal(readV3AccessToken(h.uni),'');assert.equal(h.values.get('v3_auth_mode'),'binding');assert.equal(h.values.get('v3_access_token'),'old-guest');assert.equal(h.proof(),null)
})

test('refresh advances UI isolation epoch without persisting the new access',async()=>{
 const h=harness();await h.runtime.login({});const before=h.values.get('v3_auth_epoch');await h.runtime.refresh();assert.ok(h.values.get('v3_auth_epoch')>before);assert.equal(readV3AccessToken(h.uni),'memory-access');assert.ok(h.events.every(name=>name==='harmonyai:v3-auth-changed'))
})

test('concurrent refresh callers share the same safe runtime transition',async()=>{
 const h=harness();await h.runtime.login({});await Promise.all([h.runtime.refresh(),h.runtime.refresh()]);assert.equal(h.calls.filter(r=>r.path.endsWith('/refresh')).length,1);assert.equal(readV3AccessToken(h.uni),'memory-access')
})

test('registered selection cannot be overwritten by the legacy Guest issuance facade',async()=>{
 const h=harness();await h.runtime.login({});let calls=0;h.uni.request=()=>{calls++;throw new Error('unexpected Guest request')}
 const previous=globalThis.uni;globalThis.uni=h.uni
 try{const {apiV3}=await import('../common/api-v3.js?runtime-no-guest');await assert.rejects(apiV3.guestAuth(),{code:'IDENTITY_REQUIRED'});assert.equal(calls,0)}finally{globalThis.uni=previous}
})

test('same-owner refresh preserves the current registered assessment flow',async()=>{
 const h=harness();await h.runtime.login({});h.values.set('v3_flow_state','current-registered-session');await h.runtime.refresh();assert.equal(h.values.get('v3_flow_state'),'current-registered-session')
})

for(const method of ['getStorageSync','setStorageSync'])test(`ordinary UI ${method} failure cannot prevent secure logout or server revocation attempt`,async()=>{
 const h=harness();await h.runtime.login({});h.uni[method]=()=>{throw new Error('ordinary storage unavailable')}
 const eventsBefore=h.events.length
 await assert.rejects(h.runtime.logout());assert.equal(h.calls.at(-1).path,'/api/v3/auth/logout');assert.equal(h.proof(),null);assert.equal(h.client.accessToken(),'');assert.equal(readV3AccessToken(h.uni),'')
 assert.ok(h.events.length>eventsBefore,'media/page authority must close even when UI bookkeeping fails')
})

test('confirmed Guest return is available only after successful registered logout and never issues Guest itself',async()=>{
 const h=harness();await h.runtime.login({})
 await h.runtime.logout()
 assert.equal(h.runtime.canUseGuestAfterLogout?.(),true)
 await assert.rejects(h.runtime.useGuestAfterLogout({confirmed:false}),{code:'EXPLICIT_CONFIRMATION_REQUIRED'})
 const before=h.calls.length
 await h.runtime.useGuestAfterLogout({confirmed:true})
 assert.equal(h.values.get('v3_auth_mode'),'guest')
 assert.equal(h.values.has('v3_access_token'),false)
 assert.equal(h.values.has('v3_public_user_id'),false)
 assert.equal(h.values.has('v3_flow_state'),false)
 assert.equal(readV3AccessToken(h.uni),'')
 assert.equal(h.proof(),null)
 assert.equal(h.calls.length,before,'only the normal Home flow may create the new Guest')
 assert.equal(h.runtime.canUseGuestAfterLogout(),false)
})

test('Guest return cannot abandon a quarantined binding or an unconfirmed logout',async()=>{
 const binding=harness({request:async()=>{throw new Error('offline')}})
 await assert.rejects(binding.runtime.bind({}))
 await assert.rejects(binding.runtime.useGuestAfterLogout({confirmed:true}),{code:'GUEST_RETURN_UNAVAILABLE'})
 assert.equal(binding.values.get('v3_auth_mode'),'binding')
 assert.equal(binding.values.get('v3_access_token'),'old-guest')
 const logout=harness({request:async args=>args.path.endsWith('/logout')?{error:{code:'NETWORK_ERROR'}}:{data:{public_user_id:'B',access_token:'access',refresh_token:'proof',expires_at:'2026-10-25T12:00:00Z'}}})
 await logout.runtime.login({});await assert.rejects(logout.runtime.logout())
 await assert.rejects(logout.runtime.useGuestAfterLogout({confirmed:true}),{code:'GUEST_RETURN_UNAVAILABLE'})
 assert.equal(logout.values.get('v3_auth_mode'),'registered')
})

test('a later login invalidates earlier permission to enter Guest',async()=>{
 const h=harness();await h.runtime.login({});await h.runtime.logout();await h.runtime.login({})
 await assert.rejects(h.runtime.useGuestAfterLogout({confirmed:true}),{code:'GUEST_RETURN_UNAVAILABLE'})
 assert.equal(readV3AccessToken(h.uni),'memory-access')
 assert.equal(h.values.get('v3_public_user_id'),'registered-B')
})

test('password change closes local authority and never grants logout-to-Guest permission',async()=>{
 const h=harness({request:async args=>args.path.endsWith('/password')?{data:{status:'password_changed',reauthentication_required:true}}:{data:{public_user_id:'B',access_token:'access',refresh_token:'proof',expires_at:'2026-10-25T12:00:00Z'}}})
 await h.runtime.login({})
 await h.runtime.changePassword({current_password:'synthetic-long-password',new_password:'synthetic-new-long-password'})
 assert.equal(readV3AccessToken(h.uni),'');assert.equal(h.proof(),null)
 assert.equal(h.values.get('v3_auth_mode'),'registered')
 assert.equal(h.runtime.canUseGuestAfterLogout(),false)
 assert.equal(h.calls.at(-1).path,'/api/v3/auth/password')
})

test('successful logout survives restart without Refresh or automatic Guest creation',async()=>{
 const h=harness();await h.runtime.login({});await h.runtime.logout()
 assert.equal(h.values.get('v3_auth_mode'),'signed_out')
 const runtime=h.restart(),before=h.calls.length
 await startAccountStartup(h.uni,runtime)
 assert.equal(runtime.canUseGuestAfterLogout(),true)
 assert.equal(h.calls.length,before)
 const previous=globalThis.uni;globalThis.uni=h.uni
 try{
  const {apiV3}=await import('../common/api-v3.js?explicit-signed-out')
  await assert.rejects(apiV3.ensureIdentity(),{code:'SIGNED_OUT'})
  await assert.rejects(apiV3.guestAuth(),{code:'IDENTITY_REQUIRED'})
  assert.equal(apiV3.canStartNewGuest(),false)
  assert.equal(h.calls.length,before)
  await runtime.useGuestAfterLogout({confirmed:true})
  assert.equal(h.values.get('v3_auth_mode'),'guest')
 }finally{globalThis.uni=previous}
})

test('startup during a pending logout waits rather than restoring another session',async()=>{
 let finishLogout
 const h=harness({request:async args=>{
  if(args.path.endsWith('/logout'))return new Promise(resolve=>{finishLogout=()=>resolve({data:{revoked:true}})})
  return {data:{public_user_id:'B',access_token:'access',refresh_token:'proof',expires_at:'2026-10-25T12:00:00Z'}}
 }})
 await h.runtime.login({})
 const logout=h.runtime.logout()
 const startup=startAccountStartup(h.uni,h.runtime)
 await Promise.resolve();await Promise.resolve()
 finishLogout();await Promise.all([logout,startup])
 assert.equal(h.runtime.canUseGuestAfterLogout(),true)
 assert.equal(h.calls.filter(c=>c.path.endsWith('/refresh')).length,0)
})

test('signed-out marker with leftover Guest authority cannot bypass binding quarantine',async()=>{
 const h=harness();h.values.set('v3_auth_mode','signed_out')
 await assert.rejects(startAccountStartup(h.uni,h.runtime),{code:'REAUTHENTICATION_REQUIRED'})
 assert.equal(readV3AccessToken(h.uni),'')
 assert.equal(h.values.get('v3_access_token'),'old-guest')
 assert.equal(h.runtime.canUseGuestAfterLogout(),false)
 assert.equal(h.calls.length,0)
})

test('unexpected secure proof under signed-out marker requires login even after retry',async()=>{
 const h=harness();await h.runtime.login({})
 h.values.set('v3_auth_mode','signed_out');h.values.delete('v3_public_user_id');h.values.delete('v3_flow_state')
 const runtime=h.restart(),before=h.calls.length
 await assert.rejects(startAccountStartup(h.uni,runtime),{code:'REAUTHENTICATION_REQUIRED'})
 await assert.rejects(startAccountStartup(h.uni,runtime),{code:'REAUTHENTICATION_REQUIRED'})
 assert.equal(runtime.canUseGuestAfterLogout(),false)
 assert.equal(h.calls.length,before)
})

test('Guest return permission is invalidated by an external UI authentication epoch change',async()=>{
 const h=harness();await h.runtime.login({});await h.runtime.logout()
 h.values.set('v3_auth_epoch',h.values.get('v3_auth_epoch')+1)
 await assert.rejects(h.runtime.useGuestAfterLogout({confirmed:true}),{code:'GUEST_RETURN_UNAVAILABLE'})
 assert.equal(h.values.get('v3_auth_mode'),'signed_out')
})
