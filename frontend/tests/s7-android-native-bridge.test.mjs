import test from 'node:test'
import assert from 'node:assert/strict'
async function create(invoke){const mod=await import('../common/android-native-bridge.js');return mod.createAndroidNativeBridge({invoke})}
test('native candidate never claims security acceptance from mere availability',async()=>{const bridge=await create(()=>{});assert.equal(bridge.secureStore.verified,false);assert.equal(bridge.networkApi.certificateValidationVerified,false);assert.equal(bridge.networkApi.noAmbientCookies,false)})
test('native request converts actual callback JSON to uni contract, one completion',async()=>{
 let wire,completed=0,result
 const bridge=await create((operation,input,callback)=>{wire={operation,input:JSON.parse(input)};callback(JSON.stringify({ok:true,data:{statusCode:200,data:'{"ok":true,"data":{"synthetic":true}}'}}))})
 bridge.networkApi.request({url:'https://127.0.0.1:8443/api/v3/auth/login',method:'POST',data:{username:'synthetic'},success:r=>result=r,complete:()=>completed++})
 assert.equal(wire.operation,'network.request');assert.equal(wire.input.body,'{"username":"synthetic"}');assert.equal(result.data.data.synthetic,true);assert.equal(completed,1)
})
test('native upload preserves raw envelope and download preserves local temporary file',async()=>{
 const bridge=await create((operation,input,callback)=>callback(JSON.stringify({ok:true,data:operation==='network.upload'?{statusCode:200,data:'{"success":true}'}:{statusCode:200,tempFilePath:'/private/cache/test.mp3'}})))
 let uploaded,downloaded
 bridge.networkApi.uploadFile({url:'https://127.0.0.1:8443/api/v2/documents',filePath:'/synthetic/image.png',name:'file',success:r=>uploaded=r})
 bridge.networkApi.downloadFile({url:'https://127.0.0.1:8443/api/v3/music/assets/a/stream',success:r=>downloaded=r})
 assert.equal(uploaded.data,'{"success":true}');assert.equal(downloaded.tempFilePath,'/private/cache/test.mp3')
})
test('missing proof returns null and native failure is not retried or logged as success',async()=>{
 let calls=0,failed=0,completed=0
 const bridge=await create((operation,input,callback)=>{calls++;callback(JSON.stringify(operation==='vault.take'?{ok:true,data:{proof:null}}:{ok:false,code:'TLS_VALIDATION_FAILED'}))})
 assert.equal(await bridge.secureStore.take(),null)
 bridge.networkApi.request({url:'https://127.0.0.1:8443/health',fail:r=>{failed++;assert.equal(r.code,'TLS_VALIDATION_FAILED')},complete:()=>completed++})
 assert.equal(calls,2);assert.equal(failed,1);assert.equal(completed,1)
})

test('GET/HEAD encode data into query, never a request body',async()=>{
 let input
 const bridge=await create((op,raw,callback)=>{input=JSON.parse(raw);callback(JSON.stringify({ok:true,data:{statusCode:200,data:'{}'}}))})
 bridge.networkApi.request({url:'https://127.0.0.1:8443/api/v3/me/music-assets',method:'GET',data:{limit:2,label:'a b'}})
 assert.equal(input.body,undefined);assert.ok(input.url.endsWith('?limit=2&label=a%20b'))
})
