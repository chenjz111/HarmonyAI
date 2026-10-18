import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createMusicLibraryApi} from '../../frontend/common/music-library-api.js'

const fixture=JSON.parse(readFileSync(new URL('../api/v3/fixtures/int2_music_library_api_v1.json',import.meta.url),'utf8'))

test('unchanged Frontend adapter consumes exact fixture verified by migrated Backend',async()=>{
  const calls={
    history: api=>api.listMusicAssets(),
    favorites: api=>api.listMusicFavorites(),
    detail: api=>api.getMusicAsset('music_shared'),
    selected_detail: api=>api.getMusicAsset('music_shared',{contextId:'ctx_a'}),
    title: api=>api.setMusicTitle('music_shared','合成标题',0),
    play: api=>api.recordPlayStarted('music_shared','synthetic-play-1','ctx_a'),
    play_replay: api=>api.recordPlayStarted('music_shared','synthetic-play-1','ctx_a'),
  }
  for(const [name,invoke] of Object.entries(calls)){
    const example=fixture[name]
    const api=createMusicLibraryApi({enabled:true,getOwnerId:()=>7,request:async args=>{
      assert.equal(args.method,example.method)
      assert.equal(args.path,example.path)
      assert.deepEqual(args.data,example.body)
      return {ok:true,data:example.data,request_id:'synthetic-request',schema_version:'harmonyai_v3.0'}
    }})
    assert.deepEqual(await invoke(api),example.data)
  }
})

test('adapter propagates frozen title CAS error without changing the request',async()=>{
  const example=fixture.stale_title
  const api=createMusicLibraryApi({enabled:true,getOwnerId:()=>7,request:async args=>{
    assert.deepEqual(args,{method:example.method,path:example.path,data:example.body})
    return {ok:false,error:{code:example.error_code,message:'synthetic',retryable:true,next_actions:['refetch_detail']}}
  }})
  await assert.rejects(api.setMusicTitle('music_shared','过期写入',0),{code:'TITLE_VERSION_CONFLICT'})
})
