// Execute the existing My-page script with platform I/O supplied by the ASGI peer.
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import * as libraryState from '../common/music-library-state.js'
import * as libraryTransport from '../common/music-library-transport.js'
import {createMusicLibraryApi} from '../common/music-library-api.js'
import {MUSIC_CARD_V1_PREVIEW_FIXTURE} from '../common/music-card-v1-preview-fixture.js'
export function profile(h,{registeredAccountRuntime,startAccountStartup}){
 const source=readFileSync(new URL('../pages/v3-profile/v3-profile.vue',import.meta.url),'utf8')
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g,(_,names)=>`const {${names}}=deps;`).replace('export default {','options = {')
 const sandbox={options:null,uni:h.uni,deps:{...libraryState,...libraryTransport,MUSIC_LIBRARY_LIVE_ENABLED:false,
  MUSIC_CARD_V1_PREVIEW_FIXTURE,registeredAccountRuntime,startAccountStartup,createMusicLibraryApi}}
 runInNewContext(script,sandbox)
 const page=sandbox.options.data()
 for(const [name,fn] of Object.entries(sandbox.options.methods))page[name]=fn.bind(page)
 for(const [name,fn] of Object.entries(sandbox.options.computed))Object.defineProperty(page,name,{get:()=>fn.call(page)})
 return {page,options:sandbox.options}
}
