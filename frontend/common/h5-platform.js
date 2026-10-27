/** Explicit H5 composition; the default build provides no browser approval. */
import {buildTarget,configuredApiOrigin,parseHttpsApiOrigin} from './api-origin.js'
import {createH5AccountRuntime} from './h5-account.js'
import {installRegisteredAccountRuntime,registeredAccountRuntime,hasAccountRuntime,discardUninstalledAccountRuntime} from './auth-runtime.js'

const installations=new WeakMap()
let configuredDependencies=null
// Future reviewed code may supply an approved deployment; never read a flag from storage or URL.
export function configureH5AcceptanceDependencies(dependencies){configuredDependencies=dependencies}

export function initializeH5Platform({uniApi=null,target=buildTarget(),apiOrigin=configuredApiOrigin(),
 locationOrigin=globalThis.location?.origin,accountDependencies=configuredDependencies,installRuntime=installRegisteredAccountRuntime}={}){
 const result={h5:target==='h5',accountInstalled:false,browserAcceptance:'NOT_RUN',blockers:[]}
 if(!result.h5)return Object.freeze(result)
 const deps=accountDependencies
 const origin=parseHttpsApiOrigin(apiOrigin)
 if(deps?.ownerApprovedForNonProduction!==true||deps?.browserSecurityAccepted!==true||typeof deps?.approvalRef!=='string'||!deps.approvalRef.trim())result.blockers.push('BROWSER_ACCOUNT_APPROVAL_MISSING')
 if(!origin||origin!==parseHttpsApiOrigin(locationOrigin)||origin!==parseHttpsApiOrigin(deps?.approvedOrigin))result.blockers.push('APPROVED_HTTPS_ORIGIN_MISSING')
 if(typeof deps?.fetchApi!=='function')result.blockers.push('BROWSER_TRANSPORT_UNAVAILABLE')
 if(result.blockers.length)return Object.freeze(result)
 if(!uniApi||typeof uniApi!=='object'){result.blockers.push('BROWSER_PLATFORM_UNAVAILABLE');return Object.freeze(result)}
 const previous=installations.get(uniApi)
 if(previous){
  if(previous.origin!==origin){result.blockers.push('BACKEND_RECONFIGURATION_REQUIRES_RESTART');return Object.freeze(result)}
  return previous.result
 }
 if(hasAccountRuntime(uniApi)||registeredAccountRuntime.available){result.blockers.push('ACCOUNT_RUNTIME_ALREADY_CONFIGURED');return Object.freeze(result)}
 const runtime=createH5AccountRuntime({uniApi,baseUrl:origin,locationOrigin,configuredOrigin:origin,
  fetchApi:deps.fetchApi,readCsrfCookie:deps.readCsrfCookie,accepted:true,target:'h5'})
 if(!runtime.available){result.blockers.push('BROWSER_ACCOUNT_RUNTIME_UNAVAILABLE');return Object.freeze(result)}
 try{installRuntime(runtime,{accepted:true})}catch(error){
  discardUninstalledAccountRuntime(uniApi,runtime)
  result.blockers.push('ACCOUNT_INSTALLATION_FAILED');return Object.freeze(result)
 }
 result.accountInstalled=true
 const installed=Object.freeze(result)
 installations.set(uniApi,{origin,result:installed})
 return installed
}
