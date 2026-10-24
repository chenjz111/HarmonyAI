/** Disabled integration adapter. No real Keystore plugin or H5 deployment is accepted here.
 * Access is runtime-only; refresh goes solely to an explicitly verified secure adapter.
 * Test fakes exercise behavior and never establish Android/device acceptance.
 */
const failure=code=>Object.assign(new Error(code),{code})
export function createRegisteredAuthClient({request,secureStore,enabled=false,platform='android',now=Date.now}) {
  let memory=null,generation=0,queue=Promise.resolve(),refreshing=null
  function gate(){
    if(enabled!==true || platform!=='android' || secureStore?.verified!==true || secureStore?.keystoreBacked!==true ||
      !['write','read','clear'].every(name=>typeof secureStore?.[name]==='function'))throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
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
  async function discard(g){
    if(g!==generation)return
    generation++;memory=null
    await serialized(()=>secureStore.clear())
  }
  async function adopt(data,g){
    validate(data);current(g)
    await serialized(async()=>{
      current(g);gate()
      await secureStore.write(data.refresh_token)
      if(g!==generation){await secureStore.clear();throw failure('OWNER_CHANGED')}
      memory=Object.freeze({owner:data.public_user_id,access:data.access_token,expires:Date.parse(data.expires_at)})
    })
    return {public_user_id:data.public_user_id}
  }
  async function authenticate(path,body,guestToken){
    gate();const g=++generation;memory=null
    try {
      await serialized(()=>secureStore.clear());current(g)
      return await adopt(await call(path,body,guestToken),g)
    } catch(error){await discard(g);throw error}
  }
  async function doRefresh(){
    gate();const g=generation
    if(!memory)throw failure('REAUTHENTICATION_REQUIRED')
    try {
      const proof=await serialized(()=>secureStore.read());current(g)
      if(!proof)throw failure('REAUTHENTICATION_REQUIRED')
      const result=await call('refresh',{refresh_token:proof})
      if(result.public_user_id!==memory?.owner)throw failure('OWNER_CHANGED')
      return await adopt(result,g)
    } catch(error){await discard(g);throw error}
  }
  return Object.freeze({
    login:body=>authenticate('login',body),
    bind:(body,guestToken)=>{if(!guestToken)return Promise.reject(failure('IDENTITY_REQUIRED'));return authenticate('register-bind',body,guestToken)},
    refresh(){
      if(refreshing?.generation===generation)return refreshing.promise
      const entry={generation,promise:null};entry.promise=doRefresh().finally(()=>{if(refreshing===entry)refreshing=null});refreshing=entry;return entry.promise
    },
    async invalidate(){generation++;memory=null;if(secureStore?.clear)await serialized(()=>secureStore.clear())},
    async logout({allDevices=false}={}){
      gate();if(typeof allDevices!=='boolean')throw failure('INVALID_REQUEST')
      const access=memory?.access;generation++;memory=null
      const results=await Promise.allSettled([serialized(()=>secureStore.clear()),access?call('logout',{all_devices:allDevices},access):Promise.reject(failure('REAUTHENTICATION_REQUIRED'))])
      const failed=results.find(result=>result.status==='rejected')
      if(failed)throw failed.reason
    },
    accessToken:()=>memory && memory.expires>now()?memory.access:'',
    owner:()=>memory?.owner||null,
  })
}
