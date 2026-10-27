/** Existing Android R1 credential driver; never a browser-cookie fallback. */
import {createAccountLifecycle} from './account-client-lifecycle.js'
const failure=code=>Object.assign(new Error(code),{code})
export function createRegisteredAuthClient({request,secureStore,enabled=false,platform='android',now=Date.now}) {
 function gate(){
  if(enabled!==true||platform!=='android'||secureStore?.verified!==true||secureStore?.keystoreBacked!==true||secureStore?.atomicConsume!==true||
   !['write','take','clear'].every(name=>typeof secureStore?.[name]==='function'))throw failure('ACCOUNT_FEATURE_UNAVAILABLE')
 }
 const driver={gate,
  validate(data){if(typeof data.refresh_token!=='string'||!data.refresh_token)throw failure('INVALID_RESPONSE')},
  adopt:data=>secureStore.write(data.refresh_token),
  async refreshBody(){const proof=await secureStore.take();if(!proof)throw failure('REAUTHENTICATION_REQUIRED');return {refresh_token:proof}},
  async invalidate(){await secureStore.take();await secureStore.clear()},
  async confirmSignedOut(){const proof=await secureStore.take();if(proof!==null&&proof!==undefined)throw failure('REAUTHENTICATION_REQUIRED');await secureStore.clear()},
 }
 return createAccountLifecycle({request,driver,now})
}
