import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import * as Vue from 'vue'
import * as presentation from '../common/music-presentation.js'
import {createPlayerController} from '../common/player-controller.js'

const source=readFileSync(new URL('../pages/v3-player/v3-player.vue',import.meta.url),'utf8')
const music={music_ref:{music_id:'owned-asset',source_type:'generated'},title:'笛 · 2026年10月12日 · 123456',
 regulation_mode:'personalized_five_tone',tone_code:'gong',primary_instrument_code:'dizi',primary_instrument_origin:'legacy_single'}
function harness(){
 const calls=[],listeners=new Map()
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g,(_,names)=>`const {${names}}=deps;`).replace('export default {','options = {')
 const sandbox={options:null,uni:{showToast(){},reLaunch(){},navigateBack(){},createInnerAudioContext(){throw new Error('audio must remain lazy')},$on:(name,fn)=>listeners.set(name,fn),$off:name=>listeners.delete(name),$emit:name=>listeners.get(name)?.()},deps:{...presentation,createPlayerController,MUSIC_LIBRARY_LIVE_ENABLED:false,
  apiV3:{getMusic:async()=>({...music}),getMusicBasis:async()=>null,getCurrentUserGoal:()=>null,
   getMusicPresentation:async id=>{calls.push(['metadata',id]);return {music_id:id,display_title:'Private title',is_favorite:true,primary_instrument_code:'guqin',primary_instrument_origin:'legacy_single'}},
   fetchAuthorizedAudio:async()=>'/synthetic.wav',captureIdentity:()=>()=>{},
   addFavorite:async(...args)=>calls.push(['add',...args]),removeFavorite:async(...args)=>calls.push(['remove',...args])}}}
 runInNewContext(script,sandbox)
 const page=sandbox.options.data();for(const [name,fn] of Object.entries(sandbox.options.methods))page[name]=fn.bind(page)
 for(const [name,fn] of Object.entries(sandbox.options.computed))Object.defineProperty(page,name,{get:()=>fn.call(page)})
 page.music={...music};page.loading=false
 const result=compileTemplate({source:parse(source).descriptor.template.content,filename:'v3-player.vue',id:'s7-player',compilerOptions:{isCustomElement:()=>true}})
 assert.deepEqual(result.errors,[])
 const executable=result.code.replace(/import\s*\{([^}]+)\}\s*from\s*["']vue["']/g,(_,names)=>`const {${names.replace(/\s+as\s+/g,':')}}=Vue;`).replace('export function render','function render')
 const render=new Function('Vue',executable+';return render')(Vue)
 function nodes(){const all=[];function visit(node){if(Array.isArray(node)){node.forEach(visit);return}if(!node||typeof node!=='object')return;all.push(node);visit(node.children)}visit(render(page,[]));return all}
 return {page,calls,api:sandbox.deps.apiV3,authChanged:()=>sandbox.uni.$emit('harmonyai:v3-auth-changed'),nodes,find:className=>nodes().find(n=>String(n.props?.class||'').split(' ').includes(className))}
}

test('actual Player template renders the safe persisted display title',()=>{
 const h=harness();const title=h.find('music-title');assert.ok(title);assert.equal(title.children,'笛 · 2026年10月12日 · 123456')
})
test('actual Player favorite control invokes the existing favorite operation without naming',async()=>{
 const h=harness();const control=h.find('favorite-control');assert.ok(control);await control.props.onClick();assert.equal(h.page.favorite,true);assert.deepEqual(h.calls,[['add','owned-asset','generated']]);assert.ok(h.find('favorite-control'))
})
test('actual Player share control stays explicitly disabled without a public grant',()=>{
 const h=harness();const share=h.find('share-control');assert.ok(share);assert.equal(share.props.disabled,true);assert.equal(share.props.href,undefined);assert.equal(h.calls.length,0)
})
test('normal generation Player reads current owned title/favorite/instrument without creating music',async()=>{
 const h=harness();await h.page.load();assert.equal(h.page.music.title,'Private title');assert.equal(h.page.favorite,true);assert.equal(h.page.music.primary_instrument_code,'guqin');assert.deepEqual(h.calls,[['metadata','owned-asset']]);h.page.releasePlayerLoad()
})
for(const tone of ['gong','shang'])test(`persisted dizi metadata remains dizi for ${tone}; absent approved art is neutral`,()=>{
 const value=presentation.buildMusicPresentation({music:{...music,tone_code:tone}})
 assert.equal(value.instrumentIllustration?.code,'dizi');assert.equal(value.instrumentIllustration?.imageSrc,'');assert.equal(value.instrumentIllustration?.neutral,true)
})
test('instrument labels or tone cannot manufacture missing primary-instrument authority',()=>{
 const value=presentation.buildMusicPresentation({music:{...music,primary_instrument_code:undefined,instrument_labels:['古琴']}})
 assert.equal(value.instrumentIllustration?.code,'unknown');assert.equal(value.instrumentIllustration?.imageSrc,'')
})

test('real facade extracts the owned card from the existing detail envelope',async()=>{
 const previous=globalThis.uni;const store=new Map([['v3_access_token','guest'],['v3_public_user_id','A']]);const calls=[]
 globalThis.uni={getStorageSync:k=>store.get(k)||'',request(args){calls.push(args);args.success({statusCode:200,data:{ok:true,data:{card:{music_id:'owned',display_title:'Saved title'}}}})}}
 try{const {apiV3}=await import('../common/api-v3.js?player-card-envelope');const card=await apiV3.getMusicPresentation('owned');assert.equal(card.display_title,'Saved title');assert.equal(calls.length,1);assert.equal(calls[0].method,'GET');assert.ok(calls[0].url.endsWith('/api/v3/music/assets/owned'))}finally{globalThis.uni=previous}
})

test('presentation outage does not block existing audio and disables unverified favorite state',async()=>{
 const h=harness();h.api.getMusicPresentation=async()=>{throw Object.assign(new Error('offline'),{code:'NETWORK_ERROR'})}
 await h.page.load();assert.equal(h.page.loadFailure,null);assert.ok(h.page.playerController);assert.equal(h.find('favorite-control').props.disabled,true);h.page.releasePlayerLoad()
})

test('identity changed while metadata was pending cannot restore the normal Player',async()=>{
 const h=harness();let valid=true;h.api.captureIdentity=()=>()=>{if(!valid)throw Object.assign(new Error('identity'),{code:'OWNER_CHANGED'})}
 h.api.getMusicPresentation=async()=>{valid=false;return {music_id:'owned-asset',display_title:'Late owner A'}}
 await h.page.load();assert.equal(h.page.music,null);assert.equal(h.page.playerController,null);assert.equal(h.page.loadFailure?.code,'OWNER_CHANGED')
})

test('identity changed during the optional basis read cannot publish private metadata',async()=>{
 const h=harness();let valid=true;h.api.captureIdentity=()=>()=>{if(!valid)throw Object.assign(new Error('identity'),{code:'OWNER_CHANGED'})}
 h.api.getMusicBasis=async()=>{valid=false;return null}
 await h.page.load();assert.equal(h.page.music,null);assert.equal(h.page.playerController,null);assert.equal(h.page.loadFailure?.code,'OWNER_CHANGED')
})

test('identity event clears the loaded normal Player and controller',async()=>{
 const h=harness();await h.page.load();assert.ok(h.page.playerController);h.authChanged();assert.equal(h.page.music,null);assert.equal(h.page.playerController,null);assert.equal(h.page.loadFailure?.code,'OWNER_CHANGED')
})
