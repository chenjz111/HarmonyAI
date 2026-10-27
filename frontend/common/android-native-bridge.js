/** Candidate UTS callback-to-uni bridge. Availability is NEVER device acceptance. */
const failure=code=>Object.assign(new Error(code),{code})
export function createAndroidNativeBridge({invoke,resolveFilePath=value=>value}={}){
 if(typeof invoke!=='function')throw failure('NATIVE_BRIDGE_UNAVAILABLE')
 function call(operation,input,callback){
  let settled=false
  const complete=result=>{if(settled)return;settled=true;callback(result)}
  try{invoke(operation,JSON.stringify(input),raw=>{
   let result
   try{result=JSON.parse(raw)}catch(error){complete({ok:false,code:'INVALID_NATIVE_RESPONSE'});return}
   complete(result?.ok===true?result:{ok:false,code:typeof result?.code==='string'&&/^[A-Z_]{1,64}$/.test(result.code)?result.code:'NATIVE_OPERATION_UNAVAILABLE'})
  })}catch(error){complete({ok:false,code:'NATIVE_OPERATION_UNAVAILABLE'})}
 }
 const promise=(operation,input={})=>new Promise((resolve,reject)=>call(operation,input,result=>result.ok?resolve(result.data):reject(failure(result.code))))
 function network(operation,options={}){
  let finished=false
  const finish=(ok,result)=>{
   if(finished)return;finished=true
   try{(ok?options.success:options.fail)?.(result)}finally{options.complete?.(result)}
  }
  // Current facade does not use RequestTask.abort. Do not offer fake cancellation.
  const task=undefined
  let input
  try{
   input={url:options.url,method:(options.method||'GET').toUpperCase(),header:options.header||{},timeout:options.timeout||15000}
   if(operation==='network.upload')Object.assign(input,{filePath:resolveFilePath(options.filePath),name:options.name||'file',formData:options.formData||{}})
   else if(operation==='network.request'&&options.data!==undefined){
    if(['GET','HEAD'].includes(input.method)){
     if(!options.data||typeof options.data!=='object'||Array.isArray(options.data))throw failure('NATIVE_INPUT_INVALID')
     const query=Object.keys(options.data).map(key=>encodeURIComponent(key)+'='+encodeURIComponent(typeof options.data[key]==='object'?JSON.stringify(options.data[key]):String(options.data[key]))).join('&')
     if(query)input.url+=(input.url.includes('?')?'&':'?')+query
    }else input.body=typeof options.data==='string'?options.data:JSON.stringify(options.data)
   }
  }catch(error){finish(false,{code:'NATIVE_INPUT_INVALID',errMsg:'request:fail input'});return task}
  call(operation,input,result=>{
   if(!result.ok){finish(false,{code:result.code,errMsg:'request:fail '+result.code});return}
   const response={...result.data}
   if(operation==='network.request'&&options.dataType!=='text'&&typeof response.data==='string'){
    try{response.data=JSON.parse(response.data)}catch(error){/* uni-compatible non-JSON response stays text */}
   }
   finish(true,response)
  })
  return task
 }
 return Object.freeze({
  secureStore:Object.freeze({verified:false,keystoreBacked:false,atomicConsume:false,
   write:proof=>promise('vault.write',{proof}),take:()=>promise('vault.take').then(result=>result.proof),clear:()=>promise('vault.clear')}),
  networkApi:Object.freeze({certificateValidationVerified:false,redirectsRejected:false,noAmbientCookies:false,
   request:options=>network('network.request',options),uploadFile:options=>network('network.upload',options),downloadFile:options=>network('network.download',options),
   releaseAudioFile:filePath=>promise('audio.releaseTemporary',{filePath})}),
  runSyntheticVaultChecks:()=>promise('vault.syntheticChecks'),
  probeTls:url=>promise('network.probe',{url}),
  clearTemporaryAudio:()=>promise('audio.clearTemporary'),
 })
}
