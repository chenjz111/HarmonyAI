import test from 'node:test'
import assert from 'node:assert/strict'
import {initializeH5Platform} from '../common/h5-platform.js'
import {hasAccountRuntime,readRuntimeV3Credential} from '../common/auth-runtime.js'

const origin='https://h5.test.invalid'
function setup(){
 const values=new Map([['v3_access_token','lawful-guest'],['v3_public_user_id','guest-owner'],['v3_auth_epoch',0]])
 const uniApi={getStorageSync:k=>values.get(k)||'',setStorageSync:(k,v)=>values.set(k,v),removeStorageSync:k=>values.delete(k),$emit(){},request(){assert.fail('startup must not issue an unsolicited request')}}
 const accountDependencies={ownerApprovedForNonProduction:true,browserSecurityAccepted:true,approvalRef:'isolated-contract-only',approvedOrigin:origin,fetchApi:()=>assert.fail('startup must not issue an unsolicited request')}
 return {uniApi,values,accountDependencies}
}
function options(deps){return {...deps,target:'h5',apiOrigin:origin,locationOrigin:origin}}

test('default H5 startup is closed and preserves the existing Guest',()=>{
 const s=setup();let calls=0
 const result=initializeH5Platform({...options(s),accountDependencies:null,installRuntime(){calls++}})
 assert.equal(result.accountInstalled,false);assert.equal(calls,0);assert.equal(hasAccountRuntime(s.uniApi),false)
 assert.equal(readRuntimeV3Credential(s.uniApi),'lawful-guest');assert.equal(s.values.get('v3_public_user_id'),'guest-owner')
})

test('H5 account candidate requires exact approval, target and matching HTTPS origins',()=>{
 for(const change of [
  {target:'app'}, {apiOrigin:'http://h5.test.invalid'}, {locationOrigin:'https://other.test.invalid'},
  {accountDependencies:{ownerApprovedForNonProduction:true,browserSecurityAccepted:'true',approvalRef:'test',approvedOrigin:origin}},
  {accountDependencies:{ownerApprovedForNonProduction:true,browserSecurityAccepted:true,approvalRef:' ',approvedOrigin:origin}},
  {accountDependencies:{ownerApprovedForNonProduction:true,browserSecurityAccepted:true,approvalRef:'test',approvedOrigin:'https://other.test.invalid'}},
 ]){
  const s=setup();let calls=0
  const result=initializeH5Platform({...options(s),...change,installRuntime(){calls++}})
  assert.equal(result.accountInstalled,false);assert.equal(calls,0);assert.equal(hasAccountRuntime(s.uniApi),false)
  assert.equal(readRuntimeV3Credential(s.uniApi),'lawful-guest')
 }
})

test('missing browser transport cannot create a registered runtime',()=>{
 const s=setup();s.accountDependencies.fetchApi=null;let calls=0
 const result=initializeH5Platform({...options(s),installRuntime(){calls++}})
 assert.equal(result.accountInstalled,false);assert.equal(calls,0);assert.equal(hasAccountRuntime(s.uniApi),false)
})

test('accepted H5 startup installs one existing account runtime without replacing Guest',()=>{
 const s=setup();let calls=0,installed
 const opts={...options(s),installRuntime(runtime){calls++;installed=runtime}}
 assert.equal(initializeH5Platform(opts).accountInstalled,true)
 assert.equal(initializeH5Platform(opts).accountInstalled,true)
 assert.equal(calls,1);assert.equal(installed.available,true);assert.equal(readRuntimeV3Credential(s.uniApi),'lawful-guest')
 assert.equal(s.values.get('v3_public_user_id'),'guest-owner')
})

test('reinitialization cannot silently rebind an existing runtime to another backend',()=>{
 const s=setup();let calls=0
 const opts={...options(s),installRuntime(){calls++}}
 assert.equal(initializeH5Platform(opts).accountInstalled,true)
 const next=initializeH5Platform({...opts,apiOrigin:'https://other.test.invalid',locationOrigin:'https://other.test.invalid',accountDependencies:{...s.accountDependencies,approvedOrigin:'https://other.test.invalid'}})
 assert.equal(next.accountInstalled,false);assert.equal(calls,1);assert.equal(readRuntimeV3Credential(s.uniApi),'lawful-guest')
})

test('failed installation removes its candidate runtime without replacing Guest credentials',()=>{
 const s=setup()
 const result=initializeH5Platform({...options(s),installRuntime(){throw new Error('installation failed')}})
 assert.equal(result.accountInstalled,false);assert.equal(hasAccountRuntime(s.uniApi),false)
 assert.equal(readRuntimeV3Credential(s.uniApi),'lawful-guest');assert.equal(s.values.get('v3_public_user_id'),'guest-owner')
})
