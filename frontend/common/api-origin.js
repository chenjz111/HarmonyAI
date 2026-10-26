/** One late-bound backend origin. Native builds never inherit desktop HTTP defaults. */
let context={nativeApp:false,androidApp:false,origin:null,networkApi:null,usbGuestDebug:false}
const failure=()=>Object.assign(new Error('当前平台连接尚未就绪，请稍后重试'),{code:'PLATFORM_API_UNAVAILABLE'})
export function buildTarget(){try{return process.env.UNI_PLATFORM||''}catch(error){return ''}}
export function configuredApiOrigin(){try{return import.meta.env?.VITE_API_BASE_URL||''}catch(error){return ''}}
const USB_GUEST_ORIGIN='http://127.0.0.1:8000'
function usbGuestDebugBuild(){
 try{return import.meta.env.DEV===true&&import.meta.env.MODE==='development'&&import.meta.env.VITE_S7_USB_GUEST_DEBUG==='1'}catch(error){return false}
}
export function parseHttpsApiOrigin(value){
 try{
  if(typeof value!=='string'||!value||/[\s\\]/.test(value))return null
  if(typeof URL!=='function'){
   const match=/^https:\/\/([A-Za-z0-9.-]+)(?::([0-9]{1,5}))?\/?$/i.exec(value)
   if(!match)return null
   const host=match[1].toLowerCase(),labels=host.split('.')
   if(host.length>253||labels.some(label=>!label||label.length>63||!/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label)))return null
   if(/^[0-9.]+$/.test(host)){
    if(labels.length!==4||labels.some(label=>String(Number(label))!==label||Number(label)>255))return null
   }else if(!host.includes('.')&&host!=='localhost')return null
   const port=match[2]===undefined?443:Number(match[2])
   if(port<1||port>65535)return null
   return 'https://'+host+(port===443?'':':'+port)
  }
  const u=new URL(value)
  if(u.protocol!=='https:'||u.username||u.password||u.pathname!=='/'||u.search||u.hash)return null
  return u.origin
 }catch(error){return null}
}
export function initializeApiPlatform({target=buildTarget(),systemInfo={},apiOrigin=configuredApiOrigin()}={}){
 const nativeApp=target==='app'||target==='app-plus'||(!target&&systemInfo.uniPlatform==='app')
 const androidApp=nativeApp&&systemInfo.uniPlatform==='app'&&systemInfo.osName==='android'
 const usbGuestDebug=androidApp&&usbGuestDebugBuild()&&apiOrigin===USB_GUEST_ORIGIN
 context={nativeApp,androidApp,origin:nativeApp?(usbGuestDebug?USB_GUEST_ORIGIN:parseHttpsApiOrigin(apiOrigin)):null,networkApi:null,usbGuestDebug}
 return Object.freeze({...context})
}
export function getApiOrigin({explicit,fallback=configuredApiOrigin()||'http://localhost:8000'}={}){
 if(!context.nativeApp)return explicit||fallback
 if(!context.origin||(explicit&&(context.usbGuestDebug?explicit!==USB_GUEST_ORIGIN:parseHttpsApiOrigin(explicit)!==context.origin)))throw failure()
 return context.origin
}
export function isUsbGuestDebugOrigin(origin){return context.usbGuestDebug&&origin===USB_GUEST_ORIGIN}
export function nativeTlsOptions(){return context.nativeApp?{sslVerify:true}:{}}
export function platformNetworkApi(fallback){return context.nativeApp&&context.networkApi?context.networkApi:fallback}
export function installPlatformNetworkApi(api){
 if(!context.androidApp||context.usbGuestDebug||!['request','uploadFile','downloadFile'].every(name=>typeof api?.[name]==='function'))throw failure()
 context={...context,networkApi:api}
}
