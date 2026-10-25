/** Bridges the existing secure client to legacy readers; never stores registered credentials. */
const sources = new WeakMap()
const failure = code => Object.assign(new Error(code), {code})

export function readRuntimeV3Credential(uniApi) {
  if (!uniApi) return ''
  try {
    if (sources.has(uniApi)) return sources.get(uniApi)()
    if (uniApi.getStorageSync('v3_auth_mode') === 'registered') return ''
    return uniApi.getStorageSync('v3_access_token') || ''
  } catch (error) { return '' }
}

export function createRegisteredIdentityRuntime({client=null,uniApi=null,accepted=false}={}) {
  let generation = 0, refreshing = null
  function gate() {
    if (accepted !== true || !client || !uniApi ||
        !['getStorageSync','setStorageSync','removeStorageSync','$emit'].every(name=>typeof uniApi[name]==='function')) throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
  }
  function announce() {
    const epoch = Number(uniApi.getStorageSync('v3_auth_epoch'))
    if (!Number.isSafeInteger(epoch) || epoch < 0 || epoch >= Number.MAX_SAFE_INTEGER) throw failure('IDENTITY_REQUIRED')
    uniApi.setStorageSync('v3_auth_epoch',epoch+1)
    uniApi.$emit('harmonyai:v3-auth-changed')
  }
  function begin({preserveFlow=false}={}) {
    gate()
    sources.set(uniApi,()=> '')
    uniApi.setStorageSync('v3_auth_mode','registered')
    for (const key of ['v3_access_token','v3_public_user_id']) uniApi.removeStorageSync(key)
    if (!preserveFlow) uniApi.removeStorageSync('v3_flow_state')
    announce()
  }
  async function perform(operation,{preserveFlow=false}={}) {
    gate()
    const current = ++generation
    try {
      const expectedOwner = preserveFlow ? uniApi.getStorageSync('v3_public_user_id') : null
      begin({preserveFlow})
      const result = await operation()
      if (current !== generation) throw failure('OWNER_CHANGED')
      if (!result?.public_user_id || client.owner() !== result.public_user_id || !client.accessToken()) throw failure('INVALID_RESPONSE')
      if (expectedOwner && result.public_user_id !== expectedOwner) throw failure('OWNER_CHANGED')
      uniApi.setStorageSync('v3_public_user_id',result.public_user_id)
      sources.set(uniApi,()=>client.accessToken())
      announce()
      return result
    } catch (error) {
      if (current === generation) {
        sources.set(uniApi,()=> '')
        for (const key of ['v3_public_user_id','v3_flow_state']) {
          try { uniApi.removeStorageSync(key) } catch (ignored) { /* secure invalidation must still run */ }
        }
        try { await client.invalidate() } catch (ignored) { /* local authority already removed; no fallback */ }
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
  return Object.freeze({
    available:accepted === true && !!client && !!uniApi,
    login:body=>perform(()=>client.login(body)),
    bind(body) {
      try { gate() } catch(error) { return Promise.reject(error) }
      if (uniApi.getStorageSync('v3_auth_mode') === 'registered') return Promise.reject(failure('IDENTITY_REQUIRED'))
      const guest = readRuntimeV3Credential(uniApi)
      if (!guest) return Promise.reject(failure('IDENTITY_REQUIRED'))
      return perform(()=>client.bind(body,guest))
    },
    refresh:()=>refresh(),
    restore:()=>refresh(true),
    async logout(options) {
      gate(); generation++
      sources.set(uniApi,()=> '')
      // Security operations run independently of fallible UI storage/event bookkeeping.
      const results = await Promise.allSettled([Promise.resolve().then(()=>begin()),client.logout(options)])
      const failed = results.find(result=>result.status === 'rejected')
      if (failed) throw failed.reason
    },
    owner:()=>accepted === true && client ? client.owner() : null,
  })
}

// No accepted production Keystore/HTTPS dependency has been supplied.
export const registeredAccountRuntime = createRegisteredIdentityRuntime()
