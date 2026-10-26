import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
const source=readFileSync(new URL('../common/api-origin.js',import.meta.url),'utf8')
function native(){const box={env:{},process:{env:{UNI_PLATFORM:'app'}},URL:undefined,result:null};runInNewContext(source.replaceAll('import.meta.env','env').replaceAll('export ','')+';result={initializeApiPlatform,getApiOrigin,parseHttpsApiOrigin:typeof parseHttpsApiOrigin==="function"?parseHttpsApiOrigin:()=>null}',box);return box.result}
test('actual Android without URL accepts strictly parsed HTTPS Origin and preserves origin isolation',()=>{
 const api=native()
 for(const [input,expected] of [['https://127.0.0.1:8443','https://127.0.0.1:8443'],['https://API.Example:443/','https://api.example'],['https://api.example:8443/','https://api.example:8443']]){
  api.initializeApiPlatform({systemInfo:{uniPlatform:'app',osName:'android'},apiOrigin:input})
  assert.equal(api.getApiOrigin(),expected)
  assert.throws(()=>api.getApiOrigin({explicit:'https://different.example'}),{code:'PLATFORM_API_UNAVAILABLE'})
 }
})
test('native parser never accepts ambiguous authorities, credentials, path or non-HTTPS',()=>{
 const api=native()
 for(const input of ['http://127.0.0.1:8443','https://user:pass@api.example','https://api.example/path','https://api.example?x=1','https://api.example#x','https://api.example\\@other.example','https://api.example%2f.other','https://api..example','https://-api.example','https://api.example:0','https://api.example:65536','https://127.1','https://0177.0.0.1','https://2130706433','https://0x7f000001',' https://api.example','https://api.example\n']){
  assert.equal(api.parseHttpsApiOrigin(input),null,input)
 }
})
test('account transport shares native parser and remains unavailable without accepted secure platform',async()=>{
 const {createNativeAccountTransport}=await import('../common/account-transport.js')
 const previous=globalThis.URL;let wire
 try{
  globalThis.URL=undefined
  const common={baseUrl:'https://127.0.0.1:8443',platform:'android',redirectsRejected:true,uniApi:{request(args){wire=args;args.success({statusCode:200,data:{ok:true,data:{synthetic:true}}})}}}
  const closed=createNativeAccountTransport({...common,accepted:false});assert.equal(closed.available,false)
  const request=createNativeAccountTransport({...common,accepted:true});assert.equal(request.available,true)
  await request({method:'POST',path:'/api/v3/auth/login',data:{username:'synthetic',password:'synthetic-only'}})
  assert.equal(wire.url,'https://127.0.0.1:8443/api/v3/auth/login');assert.equal(wire.sslVerify,true)
 }finally{globalThis.URL=previous}
})
