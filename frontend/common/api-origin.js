/** One late-bound backend origin. Native builds never inherit desktop HTTP defaults. */
let context={nativeApp:false,androidApp:false,origin:null,networkApi:null}
const failure=()=>Object.assign(new Error('当前平台连接尚未就绪，请稍后重试'),{code:'PLATFORM_API_UNAVAILABLE'})
export function buildTarget(){try{return process.env.UNI_PLATFORM||''}catch(error){return ''}}
export function configuredApiOrigin(){try{return import.meta.env?.VITE_API_BASE_URL||''}catch(error){return ''}}
function httpsOrigin(value){
 try{
  if(typeof value!=='string'||!value||/[\s\\]/.test(value))return null
  const u=new URL(value)
  if(u.protocol!=='https:'||u.username||u.password||u.pathname!=='/'||u.search||u.hash)return null
  return u.origin
 }catch(error){return null}
}
export function initializeApiPlatform({target=buildTarget(),systemInfo={},apiOrigin=configuredApiOrigin()}={}){
 const nativeApp=target==='app'||target==='app-plus'||(!target&&systemInfo.uniPlatform==='app')
 context={nativeApp,androidApp:nativeApp&&systemInfo.uniPlatform==='app'&&systemInfo.osName==='android',origin:nativeApp?httpsOrigin(apiOrigin):null,networkApi:null}
 return Object.freeze({...context})
}
export function getApiOrigin({explicit,fallback=configuredApiOrigin()||'http://localhost:8000'}={}){
 if(!context.nativeApp)return explicit||fallback
 if(!context.origin||(explicit&&httpsOrigin(explicit)!==context.origin))throw failure()
 return context.origin
}
export function nativeTlsOptions(){return context.nativeApp?{sslVerify:true}:{}}
export function platformNetworkApi(fallback){return context.nativeApp&&context.networkApi?context.networkApi:fallback}
export function installPlatformNetworkApi(api){
 if(!context.androidApp||!['request','uploadFile','downloadFile'].every(name=>typeof api?.[name]==='function'))throw failure()
 context={...context,networkApi:api}
}
