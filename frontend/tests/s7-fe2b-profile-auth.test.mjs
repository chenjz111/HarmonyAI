import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { reactive, computed, nextTick } from 'vue'
import * as state from '../common/music-library-state.js'
import * as adapter from '../common/music-library-api.js'
import * as transport from '../common/music-library-transport.js'
import * as fixture from '../common/music-card-v1-preview-fixture.js'

// Keep the actual page methods, Store, DTO adapter, transport and Vue computed.
// Only platform I/O is fake; no on-disk feature flag or credential is changed.
const source = readFileSync(new URL('../pages/v3-profile/v3-profile.vue', import.meta.url), 'utf8')
const flush = async () => { await new Promise(setImmediate); await nextTick() }
function deferred() {
  let resolve, reject
  const promise = new Promise((r, j) => { resolve = r; reject = j })
  return { promise, resolve, reject }
}
const card = (owner, id = `${owner}-music`) => ({ ...fixture.MUSIC_CARD_V1_PREVIEW_FIXTURE[0], music_id: id, availability: 'ready' })
let sequence = 0
async function harness({ missing = null, subscribeThrows = false, subscribeReturnsFalse = false, handler = null } = {}) {
  const storage = new Map([['v3_public_user_id', 'A'], ['v3_access_token', 'synthetic-reused'], ['v3_auth_epoch', 0]])
  const listeners = new Map()
  const h = { storage, requests: [], modals: [], toasts: [], navigations: [], nextAuth: null }
  const uni = {
    getStorageSync: key => storage.get(key) ?? '',
    setStorageSync: (key, value) => storage.set(key, value),
    showModal: args => h.modals.push(args),
    showToast: args => h.toasts.push(args.title),
    navigateTo: args => h.navigations.push(args.url),
    $on(name, fn) {
      if (subscribeThrows) throw new Error('synthetic subscription rejected')
      if (!listeners.has(name)) listeners.set(name, new Set())
      listeners.get(name).add(fn)
      if (subscribeReturnsFalse) return false
    },
    $off(name, fn) { listeners.get(name)?.delete(fn) },
    $emit(name) { for (const fn of [...(listeners.get(name) || [])]) fn() },
    request(args) {
      const request = { method: args.method, url: args.url, owner: storage.get('v3_public_user_id') }
      h.requests.push(request)
      if (args.url.endsWith('/auth/guest')) {
        args.success({ statusCode: 200, data: { ok: true, data: h.nextAuth } }); return
      }
      Promise.resolve().then(() => handler ? handler(request) : { items: [card(request.owner)], next_cursor: null, has_more: false })
        .then(data => args.success({ statusCode: 200, data: { ok: true, data } }),
          () => args.success({ statusCode: 409, data: { ok: false, error: { code: 'SYNTHETIC_FAILURE' } } }))
    },
  }
  if (missing) delete uni[missing]
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g, (_, names) => `const {${names}}=deps;`)
    .replace('export default {', 'pageOptions = {')
  const context = { uni, pageOptions: null, deps: { ...state, ...adapter, ...fixture, ...transport,
    MUSIC_LIBRARY_LIVE_ENABLED: true,
    readV3AccessToken: () => transport.readV3AccessToken(uni),
    createUniMusicLibraryTransport: options => transport.createUniMusicLibraryTransport({ ...options, uniApi: uni }),
  } }
  runInNewContext(script, context)
  h.options = context.pageOptions
  h.page = reactive({ ...h.options.data() })
  for (const [name, fn] of Object.entries(h.options.methods)) h.page[name] = fn.bind(h.page)
  for (const [name, fn] of Object.entries(h.options.computed)) {
    const value = computed(() => fn.call(h.page))
    Object.defineProperty(h.page, name, { get: () => value.value })
  }
  const previousUni = globalThis.uni
  globalThis.uni = uni
  const previousMode = process.env.HARMONYAI_V3_MODE
  process.env.HARMONYAI_V3_MODE = 'real'
  try { h.authApi = (await import(`../common/api-v3.js?r5-auth=${++sequence}`)).apiV3 }
  finally {
    if (previousMode === undefined) delete process.env.HARMONYAI_V3_MODE
    else process.env.HARMONYAI_V3_MODE = previousMode
  }
  h.auth = async (owner = 'A') => {
    h.nextAuth = { access_token: 'synthetic-reused', public_user_id: owner }
    await h.authApi.guestAuth(); await flush()
  }
  h.start = async () => { h.options.onLoad.call(h.page); await flush() }
  h.unload = () => h.options.onUnload.call(h.page)
  h.close = () => { globalThis.uni = previousUni }
  h.uni = uni
  h.listenerCount = () => [...listeners.values()].reduce((sum, entries) => sum + entries.size, 0)
  return h
}

test('W2: approved isolated live list opens its actual card in the single historical Player',async()=>{
 const h=await harness();try{await h.start();h.page.openMusic(h.page.visibleItems[0]);assert.deepEqual(h.navigations,['/pages/v3-player/v3-player?music_id=A-music']);assert.equal(h.requests.filter(x=>x.method==='POST').length,0)}finally{h.close()}
})
test('W2: returning from Player refreshes favorite and private title for the same owner',async()=>{
 let changed=false
 const h=await harness({handler:()=>({items:[{...card('A'),is_favorite:changed,display_title:changed?'Evening music':'Original title'}],has_more:false,next_cursor:null})})
 try{await h.start();assert.equal(h.page.visibleItems[0].is_favorite,false);changed=true;h.options.onShow.call(h.page);await flush();assert.equal(h.page.visibleItems[0].is_favorite,true);assert.equal(h.page.visibleItems[0].display_title,'Evening music');assert.equal(h.requests.length,2)}finally{h.close()}
})
test('W2: Player return supersedes an older pending list read',async()=>{
 let reads=0;const old=deferred()
 const h=await harness({handler:()=>++reads===2?old.promise:{items:[{...card('A'),display_title:reads>2?'Changed in Player':'Old title'}],has_more:false,next_cursor:null}})
 try{await h.start();const stale=h.page.reload();await flush();h.options.onShow.call(h.page);await flush();old.resolve({items:[{...card('A'),display_title:'Stale title'}],has_more:false,next_cursor:null});await stale;await flush();assert.equal(h.page.visibleItems[0].display_title,'Changed in Player');assert.equal(reads,3)}finally{h.close()}
})

test('R5: partial registration returning false is removed immediately without private requests', async () => {
  const h = await harness({ subscribeReturnsFalse: true })
  try {
    await h.start()
    assert.equal(h.listenerCount(), 0, 'the rejected subscription must be removed before unload')
    assert.equal(h.page.liveAuthReady, false)
    assert.equal(h.page.api, undefined)
    assert.equal(h.page.historyStore, undefined)
    assert.equal(h.page.visibleItems.length, 0)
    assert.equal(h.requests.length, 0)
    await h.auth('B')
    await h.page.reload(); await h.page.loadMore()
    await h.page.editTitle(card('A')); await h.page.toggleFavorite(card('A'))
    assert.equal(h.requests.filter(x => x.method === 'GET' || x.method === 'PATCH' || x.method === 'PUT' || x.method === 'DELETE').length, 0)
    assert.equal(h.modals.length, 0)
    assert.equal(h.page.visibleItems.length, 0)
    h.unload()
    assert.equal(h.listenerCount(), 0)
  } finally { h.close() }
})

for (const missing of ['$on', '$emit', '$off', 'subscription']) {
  test(`R5: ${missing} unavailable fails closed before any Library read or write`, async () => {
    const h = await harness(missing === 'subscription' ? { subscribeThrows: true } : { missing })
    try {
      await h.start()
      assert.equal(h.page.visibleItems.length, 0)
      assert.equal(h.page.library.history.length + h.page.library.favorites.length, 0)
      assert.equal(h.requests.length, 0)
      await h.auth('B')
      assert.equal(h.page.visibleItems.length, 0, 'real Vue computed must remain empty without onShow')
      await h.page.reload(); await h.page.loadMore()
      await h.page.toggleFavorite(card('A')); await h.page.editTitle(card('A'))
      assert.equal(h.requests.filter(x => !x.url.endsWith('/auth/guest')).length, 0)
      assert.equal(h.modals.length, 0)
      h.unload()
      assert.equal(h.listenerCount(), 0)
    } finally { h.close() }
  })
}
for (const tab of ['history', 'favorites']) {
  test(`R5: supported bus clears ${tab} computed without onShow and recovers`, async () => {
    const pending = deferred()
    const h = await harness({ handler: r => r.owner === 'B' ? pending.promise : { items: [card(r.owner)], has_more: false, next_cursor: null } })
    try {
      await h.start()
      if (tab === 'favorites') { h.page.selectSection(tab); await flush() }
      assert.equal(h.page.visibleItems[0].music_id, 'A-music')
      await h.auth('B')
      assert.equal(h.page.visibleItems.length, 0)
      pending.resolve({ items: [card('B')], has_more: false, next_cursor: null }); await flush()
      assert.equal(h.page.visibleItems[0].music_id, 'B-music')
      assert.equal(JSON.stringify(h.page).includes('synthetic-reused'), false, 'credential must stay in private identity closure')
    } finally { h.close() }
  })
}
test('R5: A-B-A same token invalidates the first A response and old modal', async () => {
  const pending = deferred(); let first = true
  const h = await harness({ handler: r => { if (first) { first = false; return pending.promise }; return { items: [card(r.owner)], has_more: false, next_cursor: null } } })
  try {
    await h.start(); await h.auth('A')
    const edit = h.page.editTitle(h.page.visibleItems[0])
    await h.auth('B'); await h.auth('A')
    pending.resolve({ items: [card('A', 'A-obsolete')], has_more: false, next_cursor: null })
    h.modals[0].success({ confirm: true, content: 'old-form' }); await edit; await flush()
    assert.equal(h.page.visibleItems[0].music_id, 'A-music')
    assert.equal(h.requests.filter(x => x.method === 'PATCH').length, 0)
    assert.equal(h.storage.get('v3_auth_epoch'), 3)
  } finally { h.close() }
})
test('R5: same owner same token reauthentication invalidates an open modal', async () => {
  const h = await harness()
  try {
    await h.start(); const edit = h.page.editTitle(h.page.visibleItems[0])
    await h.auth('A'); h.modals[0].success({ confirm: true, content: 'old-form' }); await edit
    assert.equal(h.requests.filter(x => x.method === 'PATCH').length, 0)
  } finally { h.close() }
})
test('R5: unloaded pending GET never recreates projection or another GET', async () => {
  const pending = deferred(), h = await harness({ handler: () => pending.promise })
  try {
    await h.start(); h.unload(); await h.auth('B')
    pending.resolve({ items: [card('A')], has_more: false, next_cursor: null }); await flush()
    assert.equal(h.requests.filter(x => x.method === 'GET').length, 1)
    assert.equal(h.page.visibleItems.length, 0)
    assert.equal(h.page.library.history.length, 0)
  } finally { h.close() }
})
test('R5: unloaded old modal cannot send PATCH or restart a GET', async () => {
  const h = await harness()
  try {
    await h.start(); const edit = h.page.editTitle(h.page.visibleItems[0]); h.unload()
    h.modals[0].success({ confirm: true, content: 'old-form' }); await edit
    assert.equal(h.requests.length, 1)
    assert.equal(h.page.visibleItems.length, 0)
  } finally { h.close() }
})
test('R5: favorite finally preserves UI errors after unload and clears busy', async () => {
  const h = await harness()
  try {
    await h.start()
    h.page.api = { setFavorite: async () => { throw new Error('synthetic request failure') } }
    h.uni.showToast = () => { h.unload(); throw new Error('synthetic UI failure') }
    await assert.rejects(h.page.toggleFavorite(h.page.visibleItems[0]), /synthetic UI failure/)
    assert.equal(h.page.favoriteBusy, false)
  } finally { h.close() }
})
test('R5: favorite refresh failure propagates and still clears busy', async () => {
  const h = await harness()
  try {
    await h.start()
    h.page.api = { setFavorite: async () => ({}) }
    h.page.reload = async () => { throw new Error('synthetic projection failure') }
    await assert.rejects(h.page.toggleFavorite(h.page.visibleItems[0]), /synthetic projection failure/)
    assert.equal(h.page.favoriteBusy, false)
  } finally { h.close() }
})
test('R5: optimistic projection failure propagates and clears busy before any write', async () => {
  const h = await harness()
  try {
    await h.start()
    h.page.patchCard = () => { throw new Error('synthetic optimistic projection failure') }
    await assert.rejects(h.page.toggleFavorite(h.page.visibleItems[0]), /synthetic optimistic projection failure/)
    assert.equal(h.page.favoriteBusy, false)
    assert.equal(h.requests.filter(x => x.method === 'PUT' || x.method === 'DELETE').length, 0)
  } finally { h.close() }
})
