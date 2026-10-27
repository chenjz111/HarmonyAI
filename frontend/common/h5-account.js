/** Same-origin H5 candidate. No refresh credential is readable or persisted by JS. */
import {parseHttpsApiOrigin,configuredApiOrigin} from './api-origin.js'
import {createAccountLifecycle} from './account-client-lifecycle.js'
import {createRegisteredIdentityRuntime} from './auth-runtime.js'
import {createUniMusicLibraryTransport} from './music-library-transport.js'
const failure=code=>Object.assign(new Error(code),{code})
const prefix='/api/v3/auth/browser/'
const paths=new Set(['bootstrap','register-bind','login','refresh','logout','password','signed-out'].map(value=>prefix+value))

export function createH5AccountTransport({baseUrl,locationOrigin,fetchApi=globalThis.fetch,AbortController:Controller=globalThis.AbortController,accepted=false,timeout=15000}={}){
 const base=parseHttpsApiOrigin(baseUrl)
 const available=accepted===true&&!!base&&base===parseHttpsApiOrigin(locationOrigin)&&typeof fetchApi==='function'&&typeof Controller==='function'
 let queue=Promise.resolve()
 const request=args=>{
  if(!available||args?.method!=='POST'||!paths.has(args.path)||!args.data||typeof args.data!=='object'||Array.isArray(args.data)||
    ['refresh_token','access_token'].some(key=>Object.prototype.hasOwnProperty.call(args.data,key)))return Promise.reject(failure('ACCOUNT_FEATURE_UNAVAILABLE'))
  let body
  const {path,accessToken,csrfToken}=args
  try{body=JSON.stringify(args.data)}catch(error){return Promise.reject(failure('INVALID_REQUEST'))}
  const execute=async()=>{
   const controller=new Controller();let timer
   try{
    const header={'Content-Type':'application/json'}
    if(accessToken){if(typeof accessToken!=='string'||/\s/.test(accessToken))throw failure('IDENTITY_REQUIRED');header.Authorization='Bearer '+accessToken}
    if(csrfToken){if(typeof csrfToken!=='string'||!/^[A-Za-z0-9_.-]{1,256}$/.test(csrfToken))throw failure('REAUTHENTICATION_REQUIRED');header['X-CSRF-Token']=csrfToken}
    const pending=(async()=>{
     const response=await fetchApi(base+path,{method:'POST',body,headers:header,
      credentials:'include',redirect:'error',cache:'no-store',signal:controller.signal})
     if(response.status>=300&&response.status<400)throw failure('ACCOUNT_TRANSPORT_UNAVAILABLE')
     const envelope=await response.json()
     if(response.status>=200&&response.status<300&&envelope?.ok===true&&envelope.data)return {data:envelope.data}
     const code=envelope?.error?.code
     return {error:{code:typeof code==='string'&&/^[A-Z][A-Z0-9_]{0,63}$/.test(code)?code:'INVALID_RESPONSE'}}
    })()
    const deadline=new Promise((resolve,reject)=>{timer=setTimeout(()=>{controller.abort();reject(failure('NETWORK_ERROR'))},Math.max(1,Math.min(15000,timeout)))})
    return await Promise.race([pending,deadline])
   }catch(error){throw failure(typeof error?.code==='string'&&/^[A-Z][A-Z0-9_]{0,63}$/.test(error.code)?error.code:'NETWORK_ERROR')}
   finally{clearTimeout(timer)}
  }
  // Cookie writes belong to one browser jar: serialize actual exchanges too.
  const pending=queue.then(execute);queue=pending.catch(()=>{});return pending
 }
 Object.defineProperty(request,'available',{value:available})
 return request
}

export function readH5CsrfCookie(cookieText=globalThis.document?.cookie||''){
 const matches=String(cookieText).split(';').map(value=>value.trim()).filter(value=>value.startsWith('__Host-harmonyai-csrf='))
 if(matches.length!==1)return ''
 const value=matches[0].slice('__Host-harmonyai-csrf='.length)
 return /^[A-Za-z0-9_-]{43}$/.test(value)?value:''
}

export function createH5AccountClient({request,journal,readCsrfCookie=readH5CsrfCookie,enabled=false,now=Date.now}={}){
 function gate(){if(enabled!==true||typeof request!=='function'||typeof readCsrfCookie!=='function'||!['read','write'].every(name=>typeof journal?.[name]==='function'))throw failure('ACCOUNT_FEATURE_UNAVAILABLE')}
 function csrf(){const value=readCsrfCookie();if(typeof value!=='string'||!/^[A-Za-z0-9_-]{43}$/.test(value))throw failure('REAUTHENTICATION_REQUIRED');return value}
 const driver={gate,pathPrefix:prefix,
  validate(data){if(Object.prototype.hasOwnProperty.call(data,'refresh_token'))throw failure('INVALID_RESPONSE')},
  async prepareRequest(args){
   if(args.path===prefix+'login'||args.path===prefix+'register-bind'){
    const bootstrap=await request({method:'POST',path:prefix+'bootstrap',data:{action:args.path.endsWith('register-bind')?'bind':'login'},...(args.accessToken?{accessToken:args.accessToken}:{})})
    if(bootstrap?.error)throw failure(bootstrap.error.code)
    if(typeof bootstrap?.data?.csrf_token!=='string')throw failure('INVALID_RESPONSE')
    return {...args,csrfToken:bootstrap.data.csrf_token}
   }
   return {...args,csrfToken:csrf()}
  },
  async adopt(){csrf();journal.write('ready')},
  async invalidate(){journal.write('uncertain')},
  async refreshBody(){if(journal.read()!=='ready')throw failure('REAUTHENTICATION_REQUIRED');csrf();journal.write('uncertain');return {}},
  async confirmSignedOut(){
   if(journal.read()!=='signed_out')throw failure('REAUTHENTICATION_REQUIRED')
   try{
    const result=await request({method:'POST',path:prefix+'signed-out',data:{}})
    if(result?.error)throw failure(result.error.code)
    if(result?.data?.status!=='signed_out')throw failure('INVALID_RESPONSE')
   }catch(error){journal.write('uncertain');throw error}
  },
  async noteSignedOut(result){if(result?.status!=='logged_out')throw failure('INVALID_RESPONSE');journal.write('signed_out')},
 }
 return createAccountLifecycle({request,driver,now})
}

export function createH5AccountRuntime({uniApi,baseUrl,locationOrigin,configuredOrigin=configuredApiOrigin(),fetchApi,readCsrfCookie,accepted=false,target=''}={}){
 const origin=parseHttpsApiOrigin(baseUrl)
 const request=createH5AccountTransport({baseUrl,locationOrigin,fetchApi,accepted:accepted===true&&target==='h5'&&origin===parseHttpsApiOrigin(configuredOrigin)})
 const ready=request.available&&['getStorageSync','setStorageSync','removeStorageSync','$emit'].every(name=>typeof uniApi?.[name]==='function')
 const journal={read:()=>uniApi.getStorageSync('v3_h5_account_transport_state'),write:value=>uniApi.setStorageSync('v3_h5_account_transport_state',value)}
 const client=createH5AccountClient({request,journal,readCsrfCookie,enabled:ready})
 const verifyGuest=async token=>{
  const result=await createUniMusicLibraryTransport({baseUrl,uniApi,getAccessToken:()=>token,prepareAuthentication:false})({method:'GET',path:'/api/v3/auth/identity'})
  if(result.error)throw failure(result.error.code)
  return result.data
 }
 return createRegisteredIdentityRuntime({client,uniApi,accepted:ready,verifyGuest})
}
