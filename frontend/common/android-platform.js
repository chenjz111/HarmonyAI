/** Android composition only; never loads a plugin, certificate or stored config. */
import {initializeApiPlatform,getApiOrigin,configuredApiOrigin,buildTarget,installPlatformNetworkApi} from './api-origin.js'
import {createNativeAccountRuntime} from './account-transport.js'
import {installRegisteredAccountRuntime,registeredAccountRuntime,hasAccountRuntime,discardUninstalledAccountRuntime} from './auth-runtime.js'

const installations=new WeakMap()
let configuredDependencies=null
// Called only by a future explicitly approved native composition module, never storage/URL.
export function configureAndroidAcceptanceDependencies(dependencies){configuredDependencies=dependencies}

export function initializeAndroidPlatform({uniApi=null,target,apiOrigin,accountDependencies=configuredDependencies,installRuntime=installRegisteredAccountRuntime}={}){
 const resolvedTarget=target===undefined?buildTarget():target
 let systemInfo={}
 try{systemInfo=uniApi?.getSystemInfoSync?.()||{}}catch(error){/* target app still fails closed below */}
 if(['app','app-plus',''].includes(resolvedTarget)&&uniApi&&installations.has(uniApi)&&systemInfo.uniPlatform==='app'&&systemInfo.osName==='android'){
  try{getApiOrigin({explicit:apiOrigin||configuredApiOrigin()||undefined});return installations.get(uniApi)}
  catch(error){return Object.freeze({androidApp:true,apiReady:false,accountInstalled:false,deviceAcceptance:'NOT_RUN',blockers:['BACKEND_RECONFIGURATION_REQUIRES_RESTART']})}
 }
 // Reject before mutating the process-wide origin or network provider.
 if(['app','app-plus',''].includes(resolvedTarget)&&(hasAccountRuntime(uniApi)||registeredAccountRuntime.available)){
  return Object.freeze({androidApp:systemInfo.uniPlatform==='app'&&systemInfo.osName==='android',apiReady:false,accountInstalled:false,deviceAcceptance:'NOT_RUN',blockers:['ACCOUNT_RUNTIME_ALREADY_CONFIGURED']})
 }
 const platform=initializeApiPlatform({target:resolvedTarget,systemInfo,apiOrigin})
 const result={androidApp:platform.androidApp,apiReady:false,accountInstalled:false,deviceAcceptance:'NOT_RUN',blockers:[]}
 if(!platform.nativeApp)return Object.freeze(result)
 try{getApiOrigin();result.apiReady=true}catch(error){result.blockers.push('HTTPS_API_ORIGIN_MISSING')}
 if(!platform.androidApp){result.blockers.push('ANDROID_RUNTIME_UNVERIFIED');return Object.freeze(result)}
 if(platform.usbGuestDebug){
  result.usbGuestDebug=true
  result.blockers.push('USB_GUEST_DEBUG_ACCOUNT_DISABLED')
  console.warn('[S7 USB GUEST DEBUG] 非生产 USB 本地联调，仅限合成游客数据；账号关闭。')
  try{console.info('[S7 USB GUEST DEBUG] URL parser',typeof URL,new URL(getApiOrigin()).origin===getApiOrigin())}catch(error){console.warn('[S7 USB GUEST DEBUG] URL parser unavailable')}

  uniApi?.request?.({url:getApiOrigin()+'/health',method:'GET',sslVerify:true,
   success(response){console.info('[S7 USB GUEST DEBUG] health',response.statusCode,response.data?.status==='healthy')},
   fail(){console.warn('[S7 USB GUEST DEBUG] health request failed')}
  })
  return Object.freeze(result)
 }
 const deps=accountDependencies
 if(deps?.ownerApprovedForNonProduction!==true||typeof deps?.approvalRef!=='string'||!deps.approvalRef.trim())result.blockers.push('NONPRODUCTION_ACCOUNT_APPROVAL_MISSING')
 if(deps?.secureStore?.verified!==true||deps?.secureStore?.keystoreBacked!==true||deps?.secureStore?.atomicConsume!==true)result.blockers.push('KEYSTORE_ADAPTER_UNACCEPTED')
 if(deps?.networkApi?.certificateValidationVerified!==true||deps?.networkApi?.redirectsRejected!==true||deps?.networkApi?.noAmbientCookies!==true||
  !['request','uploadFile','downloadFile'].every(name=>typeof deps?.networkApi?.[name]==='function'))result.blockers.push('NETWORK_ADAPTER_UNACCEPTED')
 if(result.blockers.length)return Object.freeze(result)
 if(hasAccountRuntime(uniApi)||registeredAccountRuntime.available){result.blockers.push('ACCOUNT_RUNTIME_ALREADY_CONFIGURED');return Object.freeze(result)}
 const runtime=createNativeAccountRuntime({uniApi,networkApi:deps.networkApi,secureStore:deps.secureStore,
  baseUrl:getApiOrigin(),accepted:true,platform:'android',redirectsRejected:true})
 if(!runtime.available){result.blockers.push('ACCOUNT_ADAPTER_UNAVAILABLE');return Object.freeze(result)}
 try{installRuntime(runtime,{accepted:true})}catch(error){
  discardUninstalledAccountRuntime(uniApi,runtime)
  result.blockers.push('ACCOUNT_INSTALLATION_FAILED');return Object.freeze(result)
 }
 installPlatformNetworkApi(deps.networkApi)
 result.accountInstalled=true
 const installed=Object.freeze(result)
 installations.set(uniApi,installed)
 return installed
}
