import test from 'node:test'
import assert from 'node:assert/strict'
import {createRegisteredAuthClient} from '../common/registered-auth.js'

const response=(owner='a',proof='synthetic-proof')=>({data:{public_user_id:owner,access_token:'synthetic-access-'+owner,refresh_token:proof,expires_at:'2026-10-24T20:00:00Z'}})
function storage(){let value=null;return {verified:true,keystoreBacked:true,async write(v){value=v},async read(){return value},async clear(){value=null},value:()=>value}}

test('registered credentials stay in memory/verified secure store and never ordinary storage',async()=>{
 const store=storage(),calls=[]
 const client=createRegisteredAuthClient({now:()=>0,enabled:true,secureStore:store,request:async args=>{calls.push(args);return response()}})
 await client.login({username:'alice',password:'synthetic-long-password'})
 assert.equal(client.accessToken(),'synthetic-access-a');assert.equal(store.value(),'synthetic-proof')
 assert.equal(calls[0].path,'/api/v3/auth/login')
 assert.equal(JSON.stringify(client).includes('synthetic-access'),false)
})

test('missing verified Keystore or H5 transport fails closed',async()=>{
 for(const options of [{enabled:false,secureStore:storage()},{enabled:true,secureStore:{...storage(),verified:false}},{enabled:true,platform:'h5',secureStore:storage()}]){
  const client=createRegisteredAuthClient({now:()=>0,...options,request:()=>{throw new Error('must not request')}})
  await assert.rejects(client.login({username:'alice',password:'synthetic-long-password'}),{code:'ACCOUNT_FEATURE_UNAVAILABLE'})
 }
})

test('logout invalidation rejects late identity responses including ABA',async()=>{
 let resolve;const pending=new Promise(r=>{resolve=r}),store=storage()
 const client=createRegisteredAuthClient({now:()=>0,enabled:true,secureStore:store,request:()=>pending})
 const logging=client.login({username:'alice',password:'synthetic-long-password'})
 await client.invalidate();resolve(response());await assert.rejects(logging,{code:'OWNER_CHANGED'})
 assert.equal(client.accessToken(),'');assert.equal(store.value(),null)
})

test('unknown refresh outcome clears local authority and never retries old proof',async()=>{
 let calls=0;const store=storage()
 const client=createRegisteredAuthClient({now:()=>0,enabled:true,secureStore:store,request:async args=>{calls++;if(args.path.endsWith('/login'))return response();throw new Error('synthetic ACK lost')}})
 await client.login({username:'alice',password:'synthetic-long-password'})
 await assert.rejects(client.refresh());await assert.rejects(client.refresh())
 assert.equal(calls,2);assert.equal(store.value(),null);assert.equal(client.accessToken(),'')
})

test('logout clears local credentials and requests revocation even when secure clearing fails',async()=>{
 const store=storage(),calls=[]
 const client=createRegisteredAuthClient({now:()=>0,enabled:true,secureStore:store,request:async args=>{calls.push(args);return args.path.endsWith('/login')?response():{data:{status:'logged_out'}}}})
 await client.login({username:'alice',password:'synthetic-long-password'})
 store.clear=async()=>{throw new Error('synthetic unavailable key')}
 await assert.rejects(client.logout())
 assert.equal(client.accessToken(),'');assert.equal(calls.at(-1).path,'/api/v3/auth/logout')
})


test('concurrent refresh callers share one consumption request',async()=>{
 const store=storage();let calls=0,resolve
 const pending=new Promise(r=>{resolve=r})
 const client=createRegisteredAuthClient({now:()=>0,enabled:true,secureStore:store,request:async args=>{calls++;return args.path.endsWith('/login')?response():pending}})
 await client.login({username:'alice',password:'synthetic-long-password'})
 const first=client.refresh(),second=client.refresh();assert.equal(first,second)
 resolve(response('a','rotated-synthetic-proof'));await first
 assert.equal(calls,2);assert.equal(store.value(),'rotated-synthetic-proof')
})

test('late secure write cannot overwrite a newer identity credential',async()=>{
 const store=storage();let release,writing=false,first=true
 const original=store.write
 store.write=async value=>{if(first){first=false;writing=true;await new Promise(r=>{release=r})}await original(value)}
 let calls=0
 const client=createRegisteredAuthClient({now:()=>0,enabled:true,secureStore:store,request:async()=>++calls===1?response('a','proof-a'):response('b','proof-b')})
 const a=client.login({username:'alice',password:'synthetic-long-password'});const rejected=assert.rejects(a,{code:'OWNER_CHANGED'})
 while(!writing)await new Promise(setImmediate)
 const clearing=client.invalidate();const b=client.login({username:'bob',password:'synthetic-long-password'})
 release();await rejected;await clearing;await b
 assert.equal(client.accessToken(),'synthetic-access-b');assert.equal(store.value(),'proof-b')
})
