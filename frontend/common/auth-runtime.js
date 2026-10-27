/** Bridges the existing secure client to legacy readers; never stores registered credentials. */
import {releaseAllAuthorizedAudio} from './owned-audio.js'
const sources = new WeakMap()
const startups = new WeakMap()
const instances = new WeakMap()
const failure = code => Object.assign(new Error(code), {code})

export function readRuntimeV3Credential(uniApi) {
  if (!uniApi) return ''
  try {
    if (['binding','signed_out'].includes(uniApi.getStorageSync('v3_auth_mode'))) return ''
    if (sources.has(uniApi)) return sources.get(uniApi)()
    if (uniApi.getStorageSync('v3_auth_mode') === 'registered') return ''
    return uniApi.getStorageSync('v3_access_token') || ''
  } catch (error) { return '' }
}

export function createRegisteredIdentityRuntime({client=null,uniApi=null,accepted=false,verifyGuest=null}={}) {
  let generation = 0, refreshing = null, pendingTransition = null, pendingLogout = null, loggedOutGeneration = null, loggedOutEpoch = null
  function gate() {
    if (accepted !== true || !client || !uniApi ||
        !['getStorageSync','setStorageSync','removeStorageSync','$emit'].every(name=>typeof uniApi[name]==='function')) throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
  }
  function announce() {
    const epoch = Number(uniApi.getStorageSync('v3_auth_epoch'))
    if (!Number.isSafeInteger(epoch) || epoch < 0 || epoch >= Number.MAX_SAFE_INTEGER) throw failure('IDENTITY_REQUIRED')
    uniApi.setStorageSync('v3_auth_epoch',epoch+1)
    try { uniApi.$emit('harmonyai:v3-auth-changed') }
    finally { releaseAllAuthorizedAudio() }
  }
  function begin({preserveFlow=false,binding=false}={}) {
    gate()
    sources.set(uniApi,()=> '')
    try {
      uniApi.setStorageSync('v3_auth_mode',binding ? 'binding' : 'registered')
      if (!binding) for (const key of ['v3_access_token','v3_public_user_id']) uniApi.removeStorageSync(key)
      if (!preserveFlow) uniApi.removeStorageSync('v3_flow_state')
      announce()
    } catch (error) {
      // Runtime credentials are already closed. UI storage failure must not
      // leave an old Player running or prevent its temporary-file cleanup.
      releaseAllAuthorizedAudio()
      try { uniApi.$emit('harmonyai:v3-auth-changed') } catch (ignored) { /* continue secure invalidation */ }
      throw error
    }
  }
  async function recoverGuest(current=generation) {
    gate()
    if (uniApi.getStorageSync('v3_auth_mode') !== 'binding' || typeof verifyGuest !== 'function') throw failure('IDENTITY_REQUIRED')
    const token=uniApi.getStorageSync('v3_access_token'),owner=uniApi.getStorageSync('v3_public_user_id')
    const epoch=uniApi.getStorageSync('v3_auth_epoch')
    const matches=()=>current===generation && uniApi.getStorageSync('v3_auth_mode')==='binding' &&
      uniApi.getStorageSync('v3_access_token')===token && uniApi.getStorageSync('v3_public_user_id')===owner && uniApi.getStorageSync('v3_auth_epoch')===epoch
    try {
      if (!token || !owner) throw failure('IDENTITY_REQUIRED')
      const identity=await verifyGuest(token)
      if (!matches()) throw failure('OWNER_CHANGED')
      if (identity?.auth_type !== 'guest' || identity.public_user_id !== owner) throw failure('UNAUTHENTICATED')
      uniApi.setStorageSync('v3_auth_mode','guest')
      sources.delete(uniApi)
      announce()
      return identity
    } catch(error) {
      // A 401 also means expired Guest: it does not prove registration completed.
      throw error
    }
  }
  async function perform(operation,{preserveFlow=false,binding=false,switchOwner=false}={}) {
    gate()
    loggedOutGeneration = null
    const current = ++generation
    // Preserve a potentially unresolved flow until every required storage read
    // establishes whether its owner is known, including transient read errors.
    let quarantineFlow = preserveFlow && !binding && !switchOwner
    try {
      const expectedOwner = preserveFlow && !switchOwner ? uniApi.getStorageSync('v3_public_user_id') : null
      // A process can die after begin() removed the owner but before restore
      // finished. Never attach its retained assessment to an unknown Cookie or
      // secure proof; preserve the unresolved flow while closing authority.
      if (preserveFlow && !binding && !switchOwner && !expectedOwner &&
          uniApi.getStorageSync('v3_auth_mode') === 'registered' && uniApi.getStorageSync('v3_flow_state')) {
        throw failure('IDENTITY_REQUIRED')
      }
      quarantineFlow = false
      begin({preserveFlow,binding})
      const result = await operation()
      if (current !== generation) throw failure('OWNER_CHANGED')
      if (!result?.public_user_id || client.owner() !== result.public_user_id || !client.accessToken()) throw failure('INVALID_RESPONSE')
      if (expectedOwner && result.public_user_id !== expectedOwner) throw failure('OWNER_CHANGED')
      uniApi.setStorageSync('v3_auth_mode','registered')
      uniApi.removeStorageSync('v3_access_token')
      if (switchOwner) uniApi.removeStorageSync('v3_flow_state')
      uniApi.setStorageSync('v3_public_user_id',result.public_user_id)
      sources.set(uniApi,()=>client.accessToken())
      announce()
      return result
    } catch (error) {
      if (current === generation) {
        sources.set(uniApi,()=> '')
        if (quarantineFlow) {
          try { announce() } catch (ignored) {
            releaseAllAuthorizedAudio()
            try { uniApi.$emit('harmonyai:v3-auth-changed') } catch (ignored) { /* authority is already closed */ }
          }
        }
        for (const key of binding ? [] : quarantineFlow ? ['v3_public_user_id'] : ['v3_public_user_id','v3_flow_state']) {
          try { uniApi.removeStorageSync(key) } catch (ignored) { /* secure invalidation must still run */ }
        }
        try { await client.invalidate() } catch (ignored) { /* local authority already removed; no fallback */ }
        if (binding) { try { await recoverGuest(current) } catch (ignored) { /* unresolved journal stays quarantined */ } }
      }
      throw error
    }
  }
  function refresh(restore=false) {
    if (refreshing && refreshing.generation === generation) return refreshing.promise
    const entry = {generation:0,promise:null}
    entry.promise = perform(()=>restore ? client.restore() : client.refresh(),{preserveFlow:true}).finally(()=>{if(refreshing === entry) refreshing = null})
    entry.generation = generation
    refreshing = entry
    return entry.promise
  }
  function accountTransition(operation) {
    if (pendingTransition) return Promise.reject(failure('ACCOUNT_OPERATION_PENDING'))
    const intent=generation
    const pending=Promise.resolve().then(()=>{if(intent!==generation)throw failure('OWNER_CHANGED');return operation()})
      .finally(()=>{if(pendingTransition===pending)pendingTransition=null})
    pendingTransition=pending
    return pending
  }
  function canUseGuestAfterLogout() {
    try {
      return accepted === true && loggedOutGeneration === generation && !pendingTransition && !pendingLogout && !refreshing &&
        uniApi.getStorageSync('v3_auth_mode') === 'signed_out' && loggedOutEpoch === uniApi.getStorageSync('v3_auth_epoch') &&
        !uniApi.getStorageSync('v3_access_token') && !uniApi.getStorageSync('v3_public_user_id') && !uniApi.getStorageSync('v3_flow_state') &&
        !client.owner() && !client.accessToken()
    } catch (error) { return false }
  }
  const runtime=Object.freeze({
    available:accepted === true && !!client && !!uniApi,
    login(body) {
      return accountTransition(()=>{
        const switchingGuest=!!uniApi?.getStorageSync('v3_access_token') && uniApi?.getStorageSync('v3_auth_mode')!=='registered'
        return perform(()=>client.login(body),switchingGuest?{binding:true,preserveFlow:true,switchOwner:true}:{})
      })
    },
    bind(body) {
      try { gate() } catch(error) { return Promise.reject(error) }
      return accountTransition(async()=>{
        if (uniApi.getStorageSync('v3_auth_mode')==='binding') await recoverGuest()
        if (uniApi.getStorageSync('v3_auth_mode')==='registered') throw failure('IDENTITY_REQUIRED')
        const guest = readRuntimeV3Credential(uniApi)
        if (!guest) throw failure('IDENTITY_REQUIRED')
        return perform(()=>client.bind(body,guest),{preserveFlow:true,binding:true})
      })
    },
    refresh:()=>refresh(),
    restore:()=>refresh(true),
    recoverGuest:()=>recoverGuest(),
    ensureAccess:()=>client?.accessToken() ? Promise.resolve({public_user_id:client.owner()}) : client?.owner() ? refresh() : refresh(true),
    waitForTransition:()=>Promise.all([pendingTransition,pendingLogout].filter(Boolean).map(p=>p.catch(()=>{}))),
    logout(options) {
      if(pendingLogout)return Promise.reject(failure('ACCOUNT_OPERATION_PENDING'))
      const pending=(async()=>{
        gate()
        let wasRegistered = false
        try { wasRegistered = uniApi.getStorageSync('v3_auth_mode') === 'registered' && !!client.owner() }
        catch (error) { /* UI storage must not stop secure erasure/revocation. */ }
        const current = ++generation
        loggedOutGeneration = null
        sources.set(uniApi,()=> '')
        // Security operations run independently of fallible UI storage/event bookkeeping.
        const results = await Promise.allSettled([Promise.resolve().then(()=>begin()),client.logout(options)])
        const failed = results.find(result=>result.status === 'rejected')
        if (failed) throw failed.reason
        if (current === generation && wasRegistered) {
          uniApi.setStorageSync('v3_auth_mode','signed_out')
          loggedOutGeneration = current
          announce()
          loggedOutEpoch = uniApi.getStorageSync('v3_auth_epoch')
        }
      })().finally(()=>{if(pendingLogout===pending)pendingLogout=null})
      pendingLogout=pending
      return pending
    },
    restoreSignedOut() {
      if(canUseGuestAfterLogout())return Promise.resolve(null)
      return accountTransition(async()=>{
        gate()
        const epoch=uniApi.getStorageSync('v3_auth_epoch')
        const emptySignedOut=()=>uniApi.getStorageSync('v3_auth_mode')==='signed_out' &&
          !uniApi.getStorageSync('v3_access_token') && !uniApi.getStorageSync('v3_public_user_id') && !uniApi.getStorageSync('v3_flow_state')
        if(!emptySignedOut())throw failure('REAUTHENTICATION_REQUIRED')
        const current=++generation;loggedOutGeneration=null;sources.set(uniApi,()=> '')
        try { await client.confirmSignedOut() }
        catch (error) {
          // Never turn a corrupt marker/proof pair into a clean logout merely
          // because a failed check consumed the unexpected proof on first try.
          if(current===generation && uniApi.getStorageSync('v3_auth_mode')==='signed_out')uniApi.setStorageSync('v3_auth_mode','registered')
          throw error
        }
        if(current!==generation || epoch!==uniApi.getStorageSync('v3_auth_epoch') || !emptySignedOut())throw failure('OWNER_CHANGED')
        loggedOutGeneration=current
        announce()
        loggedOutEpoch=uniApi.getStorageSync('v3_auth_epoch')
        return null
      })
    },
    changePassword(body) {
      return accountTransition(async()=>{
        gate();loggedOutGeneration=null
        const current=++generation
        try { begin();return await client.changePassword(body) }
        finally {
          if(current===generation){
            sources.set(uniApi,()=> '')
            await client.invalidate()
            announce()
          }
        }
      })
    },
    canUseGuestAfterLogout,
    async useGuestAfterLogout({confirmed=false}={}) {
      gate()
      if (confirmed !== true) throw failure('EXPLICIT_CONFIRMATION_REQUIRED')
      if (!canUseGuestAfterLogout()) throw failure('GUEST_RETURN_UNAVAILABLE')
      // Only a successful explicit logout grants this one-shot transition.
      // Never applies to binding/unknown outcomes and never issues a credential.
      loggedOutGeneration = null; generation++
      for (const key of ['v3_access_token','v3_public_user_id','v3_flow_state']) uniApi.removeStorageSync(key)
      uniApi.setStorageSync('v3_auth_mode','guest')
      sources.delete(uniApi)
      announce()
    },
    owner:()=>accepted === true && client ? client.owner() : null,
  })
  if (runtime.available) instances.set(uniApi,runtime)
  return runtime
}

// No accepted production Keystore/HTTPS dependency has been supplied.
let installed = createRegisteredIdentityRuntime()
export const registeredAccountRuntime = Object.freeze({
  get available(){return installed.available},
  ...Object.fromEntries(['login','bind','refresh','restore','restoreSignedOut','recoverGuest','ensureAccess','waitForTransition','logout','changePassword','canUseGuestAfterLogout','useGuestAfterLogout','owner'].map(name=>[name,(...args)=>installed[name](...args)])),
})

// Explicit candidate composition seam, never called by the default build.
export function installRegisteredAccountRuntime(runtime,{accepted=false}={}) {
  if (accepted !== true || !runtime?.available || installed.available) throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
  installed=runtime
}

export function startAccountStartup(uniApi,runtime=null) {
  if (!uniApi) return Promise.resolve(null)
  if (startups.has(uniApi)) return startups.get(uniApi)
  let mode
  try {mode=uniApi.getStorageSync('v3_auth_mode')} catch(error) {return Promise.reject(failure('IDENTITY_REQUIRED'))}
  if (!['registered','binding','signed_out'].includes(mode)) return Promise.resolve(null)
  runtime=runtime || instances.get(uniApi) || registeredAccountRuntime
  const pending=Promise.resolve().then(async()=>{
    if (!runtime.available) throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
    if (runtime.waitForTransition) await runtime.waitForTransition()
    const selected=uniApi.getStorageSync('v3_auth_mode')
    if(selected==='signed_out')return runtime.restoreSignedOut()
    return selected==='guest' ? null : selected === 'binding' ? runtime.recoverGuest() : runtime.ensureAccess ? runtime.ensureAccess() : runtime.restore()
  }).finally(()=>{if(startups.get(uniApi)===pending)startups.delete(uniApi)})
  startups.set(uniApi,pending)
  return pending
}

export function waitForAccountStartup(uniApi) {
  return (uniApi && startups.get(uniApi)) || Promise.resolve(null)
}

export function hasAccountStartup(uniApi) {return !!uniApi && startups.has(uniApi)}

export function hasAccountRuntime(uniApi) {return !!uniApi && instances.has(uniApi)}

export function discardUninstalledAccountRuntime(uniApi,runtime) {
  if(instances.get(uniApi)===runtime && !runtime.owner())instances.delete(uniApi)
}

export async function prepareAccountRequest(uniApi) {
  await startAccountStartup(uniApi)
}
