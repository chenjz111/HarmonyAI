import test from 'node:test'
import assert from 'node:assert/strict'
import {createH5AccountTransport,createH5AccountClient} from '../common/h5-account.js'

const response=()=>({data:{public_user_id:'owner-A',access_token:'synthetic-access',expires_at:'2099-01-01T00:00:00Z'}})
function journal(){let value='';return {read:()=>value,write:next=>{value=next},value:()=>value}}

test('H5 transport refuses HTTP, cross-origin and unaccepted environments before fetch',async()=>{
 for(const options of [{accepted:false},{baseUrl:'http://h5.test.invalid'},{locationOrigin:'https://other.test.invalid'}]){
  let calls=0;const request=createH5AccountTransport({baseUrl:'https://h5.test.invalid',locationOrigin:'https://h5.test.invalid',accepted:true,AbortController,fetchApi:()=>{calls++},...options})
  await assert.rejects(request({method:'POST',path:'/api/v3/auth/browser/login',data:{}}))
  assert.equal(calls,0)
 }
})

test('actual H5 transport uses credentials include and rejects JSON refresh credentials',async()=>{
 let wire;const request=createH5AccountTransport({baseUrl:'https://h5.test.invalid',locationOrigin:'https://h5.test.invalid',accepted:true,AbortController,fetchApi:async(url,options)=>{wire={url,options};return {status:200,json:async()=>({ok:true,...response()})}}})
 await request({method:'POST',path:'/api/v3/auth/browser/refresh',data:{},csrfToken:'A'.repeat(43)})
 assert.equal(wire.options.credentials,'include');assert.equal(wire.options.redirect,'error');assert.equal(wire.options.headers['X-CSRF-Token'],'A'.repeat(43))
 assert.equal(wire.options.body,'{}');assert.equal(wire.options.cache,'no-store')
 await assert.rejects(request({method:'POST',path:'/api/v3/auth/browser/refresh',data:{refresh_token:'must-not-send'}}))
})

test('queued H5 request cannot change its checked path or credentials by caller mutation',async()=>{
 let wire
 const request=createH5AccountTransport({baseUrl:'https://h5.test.invalid',locationOrigin:'https://h5.test.invalid',accepted:true,AbortController,fetchApi:async(url,options)=>{wire={url,options};return {status:200,json:async()=>({ok:true,...response()})}}})
 const args={method:'POST',path:'/api/v3/auth/browser/login',data:{username:'original'},csrfToken:'A'.repeat(43)}
 const pending=request(args);args.path='/outside';args.data.username='changed';args.csrfToken='B'.repeat(43)
 await pending
 assert.equal(wire.url,'https://h5.test.invalid/api/v3/auth/browser/login')
 assert.equal(JSON.parse(wire.options.body).username,'original');assert.equal(wire.options.headers['X-CSRF-Token'],'A'.repeat(43))
})

test('H5 shares account lifecycle without ordinary-storage Access or Refresh',async()=>{
 const state=journal(),calls=[];let csrf='A'.repeat(43)
 const request=async args=>{calls.push(args);if(args.path.endsWith('bootstrap'))return {data:{csrf_token:'signed-preauth'}};if(args.path.endsWith('logout')){csrf='';return {data:{status:'logged_out'}}}return response()}
 const client=createH5AccountClient({request,journal:state,readCsrfCookie:()=>csrf,enabled:true})
 await client.login({username:'synthetic',password:'synthetic-long-password'})
 assert.equal(client.accessToken(),'synthetic-access');assert.equal(state.value(),'ready')
 assert.ok(!JSON.stringify(state.value()).includes('synthetic-access'))
 assert.equal(calls[1].csrfToken,'signed-preauth')
 await client.refresh();assert.deepEqual(calls.at(-1).data,{})
 assert.equal(calls.at(-1).csrfToken,'A'.repeat(43))
 await client.logout();assert.equal(client.accessToken(),'');assert.equal(state.value(),'signed_out')
})

test('unknown Cookie refresh blocks automatic retry across reconstructed clients',async()=>{
 const state=journal();state.write('ready');let calls=0
 const options={enabled:true,journal:state,readCsrfCookie:()=>'A'.repeat(43),request:async()=>{calls++;throw new Error('ACK lost')}}
 const first=createH5AccountClient(options);await assert.rejects(first.restore())
 const restarted=createH5AccountClient(options);await assert.rejects(restarted.restore())
 assert.equal(calls,1);assert.equal(state.value(),'uncertain');assert.equal(restarted.accessToken(),'')
})

test('H5 signed-out restore asks server to prove absence of usable Cookie authority',async()=>{
 const state=journal();state.write('signed_out');let calls=0
 const client=createH5AccountClient({enabled:true,journal:state,readCsrfCookie:()=>'',request:async args=>{calls++;assert.ok(args.path.endsWith('/signed-out'));return {error:{code:'REAUTHENTICATION_REQUIRED'}}}})
 await assert.rejects(client.confirmSignedOut(),{code:'REAUTHENTICATION_REQUIRED'})
 assert.equal(calls,1);assert.equal(state.value(),'uncertain')
})

test('late logout cannot overwrite the journal of a newer explicit login',async()=>{
 const state=journal();let finish
 const request=async args=>args.path.endsWith('/bootstrap')?{data:{csrf_token:'challenge'}}:args.path.endsWith('/logout')?new Promise(resolve=>{finish=resolve}):response()
 const client=createH5AccountClient({enabled:true,journal:state,readCsrfCookie:()=>'A'.repeat(43),request})
 await client.login({username:'a',password:'synthetic-password'})
 const pending=client.logout();await new Promise(setImmediate)
 await client.login({username:'b',password:'synthetic-password'})
 finish({data:{status:'logged_out'}})
 await assert.rejects(pending,{code:'OWNER_CHANGED'})
 assert.equal(state.value(),'ready');assert.equal(client.accessToken(),'synthetic-access')
})
