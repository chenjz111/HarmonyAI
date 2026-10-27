/** Ephemeral ownership of files returned by OUR authorized downloads only.
 * No original assets, uploads, static files or arbitrary paths may be erased.
 */
const owned=new Map()
export function trackAuthorizedAudio(path,remove){
 if(typeof path!=='string'||!path||typeof remove!=='function')throw new Error('AUDIO_RESOURCE_INVALID')
 const previous=owned.get(path)
 if(previous){
  if(previous.refs===0)throw new Error('AUDIO_RESOURCE_RELEASING')
  previous.refs++;return
 }
 owned.set(path,{refs:1,remove,pending:null})
}
export function releaseAuthorizedAudio(path){
 const entry=owned.get(path)
 if(!entry)return Promise.resolve(false)
 if(entry.refs>0)entry.refs--
 if(entry.refs>0)return Promise.resolve(false)
 if(entry.pending)return entry.pending
 const pending=Promise.resolve().then(()=>entry.remove(path)).then(()=>{
  if(owned.get(path)===entry)owned.delete(path)
  return true
 },()=>false).finally(()=>{if(entry.pending===pending)entry.pending=null})
 entry.pending=pending
 return pending
}
export function releaseAllAuthorizedAudio(){
 for(const entry of owned.values())entry.refs=0
 return Promise.all([...owned.keys()].map(path=>releaseAuthorizedAudio(path)))
}

export function audioRemover({network,uniApi,plusApi,URLApi}={}){
 if(typeof network?.releaseAudioFile==='function')return path=>network.releaseAudioFile(path)
 return path=>new Promise((resolve,reject)=>{
  if(path.startsWith('blob:') && typeof URLApi?.revokeObjectURL==='function'){URLApi.revokeObjectURL(path);resolve();return}
  if(typeof plusApi?.io?.resolveLocalFileSystemURL==='function'){
   plusApi.io.resolveLocalFileSystemURL(path,entry=>{
    if(entry?.isFile!==true||typeof entry.remove!=='function'){reject(new Error('AUDIO_CLEANUP_UNAVAILABLE'));return}
    entry.remove(resolve,reject)
   },error=>error?.code===1?resolve():reject(new Error('AUDIO_CLEANUP_UNAVAILABLE')))
   return
  }
  const fs=uniApi?.getFileSystemManager?.()
  if(typeof fs?.unlink==='function'){fs.unlink({filePath:path,success:resolve,fail:reject});return}
  reject(new Error('AUDIO_CLEANUP_UNAVAILABLE'))
 })
}
