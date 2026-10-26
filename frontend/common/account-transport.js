/** Candidate native adapter. H5 remains closed; capabilities require platform evidence. */
import {parseHttpsApiOrigin} from './api-origin.js'
import {createRegisteredAuthClient} from './registered-auth.js'
import {createRegisteredIdentityRuntime} from './auth-runtime.js'
import {createUniMusicLibraryTransport} from './music-library-transport.js'

const failure=code=>Object.assign(new Error(code),{code})
const paths=new Set(['register-bind','login','refresh','logout','password'].map(name=>'/api/v3/auth/'+name))

export function createNativeAccountTransport({baseUrl,uniApi,accepted=false,platform='android',redirectsRejected=false}={}) {
  const base=parseHttpsApiOrigin(baseUrl)
  const available=accepted===true && platform==='android' && redirectsRejected===true && !!base && typeof uniApi?.request==='function'
  const request=async function({method,path,data,accessToken}={}) {
    if (!available || method!=='POST' || !paths.has(path)) throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
    if (accessToken!==undefined && (typeof accessToken!=='string' || !accessToken || /\s/.test(accessToken))) throw failure('IDENTITY_REQUIRED')
    return new Promise((resolve,reject)=>{
      const header={'Content-Type':'application/json',...(accessToken?{Authorization:'Bearer '+accessToken}:{})}
      try {
        uniApi.request({url:base+path,method,data,header,timeout:15000,sslVerify:true,
          success(response) {
            const status=response?.statusCode,body=response?.data
            if (status>=300 && status<400) {reject(failure('ACCOUNT_TRANSPORT_UNAVAILABLE'));return}
            if (status>=200 && status<300 && body?.ok===true && body.data) {resolve({data:body.data});return}
            const code=body?.error?.code
            resolve({error:{code:typeof code==='string' && /^[A-Z][A-Z0-9_]{0,63}$/.test(code)?code:'INVALID_RESPONSE'}})
          },fail(){reject(failure('NETWORK_ERROR'))}})
      } catch(error) {reject(failure('NETWORK_ERROR'))}
    })
  }
  Object.defineProperty(request,'available',{value:available})
  return request
}

export function createNativeAccountRuntime(options={}) {
  const {uniApi,secureStore}=options
  const networkApi=options.networkApi||uniApi
  const request=createNativeAccountTransport({...options,uniApi:networkApi})
  const accepted=request.available && secureStore?.verified===true && secureStore?.keystoreBacked===true && secureStore?.atomicConsume===true &&
    ['take','write','clear'].every(key=>typeof secureStore[key]==='function') &&
    ['getStorageSync','setStorageSync','removeStorageSync','$emit'].every(key=>typeof uniApi[key]==='function')
  const client=createRegisteredAuthClient({request,secureStore,enabled:accepted,platform:options.platform||'android'})
  const verifyGuest=async token=>{
    const response=await createUniMusicLibraryTransport({baseUrl:options.baseUrl,uniApi:networkApi,getAccessToken:()=>token,prepareAuthentication:false})({method:'GET',path:'/api/v3/auth/identity'})
    if(response.error)throw failure(response.error.code)
    return response.data
  }
  return createRegisteredIdentityRuntime({client,uniApi,accepted,verifyGuest})
}
