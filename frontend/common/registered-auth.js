/** Disabled integration adapter. No real Keystore plugin or H5 deployment is accepted here.
 * Access is runtime-only; refresh goes solely to an explicitly verified secure adapter.
 * Test fakes exercise behavior and never establish Android/device acceptance.
 */
const failure=code=>Object.assign(new Error(code),{code})
export function createRegisteredAuthClient({request,secureStore,enabled=false,platform='android',now=Date.now}) {
  let memory=null,generation=0,queue=Promise.resolve(),refreshing=null,reauthenticationRequired=false
  function gate(){
    if(enabled!==true || platform!=='android' || secureStore?.verified!==true || secureStore?.keystoreBacked!==true || secureStore?.atomicConsume!==true ||
      !['write','take','clear'].every(name=>typeof secureStore?.[name]==='function'))throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
  }
  function current(g){if(g!==generation)throw failure('OWNER_CHANGED')}
  function serialized(operation){const next=queue.then(operation);queue=next.catch(()=>{});return next}
  async function call(path,data,accessToken){
    const response=await request({method:'POST',path:'/api/v3/auth/'+path,data,...(accessToken?{accessToken}:{})})
    if(response?.error)throw Object.assign(new Error(response.error.message||response.error.code),{code:response.error.code})
    if(!response?.data)throw failure('INVALID_RESPONSE')
    return response.data
  }
  function validate(data){
    if(!data || !['public_user_id','access_token','refresh_token','expires_at'].every(key=>typeof data[key]==='string' && data[key]) || !Number.isFinite(Date.parse(data.expires_at)))throw failure('INVALID_RESPONSE')
  }
  async function eraseProof(){gate();await secureStore.take();await secureStore.clear()}
  async function discard(g){
    if(g!==generation)return
    generation++;memory=null;reauthenticationRequired=true
    await serialized(()=>eraseProof())
  }
  async function adopt(data,g){
    validate(data);current(g)
    await serialized(async()=>{
      current(g);gate()
      await secureStore.write(data.refresh_token)
      if(g!==generation){await eraseProof();throw failure('OWNER_CHANGED')}
      reauthenticationRequired=false
      memory=Object.freeze({owner:data.public_user_id,access:data.access_token,expires:Date.parse(data.expires_at)})
    })
    return {public_user_id:data.public_user_id}
  }
  async function authenticate(path,body,guestToken){
    gate();const g=++generation;memory=null
    try {
      await serialized(()=>eraseProof());current(g)
      return await adopt(await call(path,body,guestToken),g)
    } catch(error){await discard(g);throw error}
  }
  async function doRefresh(restore=false){
    gate();const g=generation,expectedOwner=memory?.owner
    if(!memory && !restore)throw failure('REAUTHENTICATION_REQUIRED')
    try {
      // take must durably and atomically remove the proof before any network request.
      // A restart after an unknown outcome therefore cannot retry that credential.
      const proof=await serialized(()=>secureStore.take());current(g)
      if(!proof)throw failure('REAUTHENTICATION_REQUIRED')
      const result=await call('refresh',{refresh_token:proof})
      if(expectedOwner && result.public_user_id!==expectedOwner)throw failure('OWNER_CHANGED')
      return await adopt(result,g)
    } catch(error){await discard(g);throw error}
  }
  function startRefresh(restore=false){
    try{gate()}catch(error){return Promise.reject(error)}
    if(reauthenticationRequired)return Promise.reject(failure('REAUTHENTICATION_REQUIRED'))
    if(refreshing?.generation===generation)return refreshing.promise
    if(restore && !memory)generation++
    const entry={generation,promise:null}
    entry.promise=doRefresh(restore).finally(()=>{if(refreshing===entry)refreshing=null})
    refreshing=entry;return entry.promise
  }
  return Object.freeze({
    login:body=>authenticate('login',body),
    bind:(body,guestToken)=>{if(!guestToken)return Promise.reject(failure('IDENTITY_REQUIRED'));return authenticate('register-bind',body,guestToken)},
    refresh:()=>startRefresh(),
    restore:()=>startRefresh(true),
    async confirmSignedOut(){
      gate()
      if(memory)throw failure('REAUTHENTICATION_REQUIRED')
      const g=++generation;reauthenticationRequired=true
      await serialized(async()=>{
        current(g)
        const proof=await secureStore.take();current(g)
        // A UI marker cannot prove credential erasure. Unexpected proof is
        // consumed fail-closed, never restored or sent to Refresh.
        if(proof!==null && proof!==undefined)throw failure('REAUTHENTICATION_REQUIRED')
        await secureStore.clear();current(g)
      })
    },
    async invalidate(){generation++;memory=null;reauthenticationRequired=true;await serialized(()=>eraseProof())},
    async changePassword(body){
      gate()
      if(!memory || memory.expires<=now())throw failure('REAUTHENTICATION_REQUIRED')
      const access=memory.access,g=++generation
      memory=null;reauthenticationRequired=true
      const results=await Promise.allSettled([serialized(()=>eraseProof()),call('password',body,access)])
      current(g)
      const failed=results.find(result=>result.status==='rejected')
      if(failed)throw failed.reason
      const result=results[1].value
      if(result.status!=='password_changed' || result.reauthentication_required!==true)throw failure('INVALID_RESPONSE')
      return {reauthentication_required:true}
    },
    async logout({allDevices=false}={}){
      gate();if(typeof allDevices!=='boolean')throw failure('INVALID_REQUEST')
      const access=memory?.access;generation++;memory=null;reauthenticationRequired=true
      const results=await Promise.allSettled([serialized(()=>eraseProof()),access?call('logout',{all_devices:allDevices},access):Promise.reject(failure('REAUTHENTICATION_REQUIRED'))])
      const failed=results.find(result=>result.status==='rejected')
      if(failed)throw failed.reason
    },
    accessToken:()=>memory && memory.expires>now()?memory.access:'',
    owner:()=>memory?.owner||null,
  })
}
