import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { createHistoricalMusicSession, resolvePlayableAudio } from '../common/music-library-player.js'
import { createPlayerController } from '../common/player-controller.js'
import {putHistoricalFeedback,consumeHistoricalFeedback} from '../common/feedback-context.js'
import * as transport from '../common/music-library-transport.js'
import { createMusicLibraryApi } from '../common/music-library-api.js'
import * as presentation from '../common/music-presentation.js'
import * as seek from '../common/player-seek.js'
import { MUSIC_CARD_V1_PREVIEW_FIXTURE } from '../common/music-card-v1-preview-fixture.js'

const flush = () => new Promise(setImmediate)
function deferred() { let resolve, reject; const promise = new Promise((r, j) => { resolve = r; reject = j }); return { promise, resolve, reject } }
function detail(id = 'music_a') {
  return { card: { ...MUSIC_CARD_V1_PREVIEW_FIXTURE[0], music_id: id, display_title: id },
    audio: { availability: 'ready', duration_seconds: null, format: 'wav' },
    source_contexts: [], selected_context_id: null, history_explanation: null }
}
function sessionHarness({ fetch = async () => detail(), report = async () => ({}) } = {}) {
  const identity = { owner: 'A', token: 'synthetic-A', epoch: 0 }
  const calls = []
  const session = createHistoricalMusicSession({
    api: { getMusicAsset: fetch, recordPlayStarted: (...args) => { calls.push(args); return report(...args) } },
    getOwnerId: () => identity.owner, getAccessToken: () => identity.token, getAuthEpoch: () => identity.epoch,
    newEventId: () => 'synthetic-event',
  })
  return { session, identity, calls }
}
for (const mutation of ['owner', 'token', 'epoch', 'ABA']) {
  test(`History R1: pending detail rejects changed ${mutation} authentication instance`, async () => {
    const pending = deferred(), h = sessionHarness({ fetch: () => pending.promise })
    const opening = h.session.open('music_a')
    if (mutation === 'owner') h.identity.owner = 'B'
    if (mutation === 'token') h.identity.token = 'synthetic-new'
    if (mutation === 'epoch') h.identity.epoch++
    if (mutation === 'ABA') { h.identity.owner = 'B'; h.identity.epoch++; h.identity.owner = 'A'; h.identity.epoch++ }
    pending.resolve(detail())
    await assert.rejects(opening, { code: 'OWNER_CHANGED' })
    assert.equal(h.session.hasOwnerChanged(), true)
  })
}
test('History R1: old auth cannot submit an event or reopen by adopting new credentials', async () => {
  const h = sessionHarness(); await h.session.open('music_a')
  h.identity.epoch++
  await assert.rejects(h.session.reportPlayStarted('music_a'), { code: 'OWNER_CHANGED' })
  await assert.rejects(h.session.open('music_a'), { code: 'OWNER_CHANGED' })
  assert.equal(h.calls.length, 0)
})
test('History R1: changed epoch after event dispatch rejects the late success', async () => {
  const pending = deferred(), h = sessionHarness({ report: () => pending.promise })
  await h.session.open('music_a'); const posting = h.session.reportPlayStarted('music_a')
  h.identity.epoch++; pending.resolve({ replayed: false })
  await assert.rejects(posting, { code: 'OWNER_CHANGED' })
  assert.equal(h.session.getState().playReported, false)
  assert.equal(h.calls.length, 1)
})
test('History R1: reset invalidates a dispatched result without another event', async () => {
  const pending = deferred(), h = sessionHarness({ report: () => pending.promise })
  await h.session.open('music_a'); const posting = h.session.reportPlayStarted('music_a')
  h.session.reset(); pending.resolve({})
  await assert.rejects(posting, { code: 'OWNER_CHANGED' })
  assert.equal(h.session.getState().playReported, false)
  assert.equal(h.calls.length, 1)
})
test('History R1: concurrent onPlay and retry retain one stable event id', async () => {
  let attempt = 0; const pending = deferred()
  const h = sessionHarness({ report: () => ++attempt === 1 ? Promise.reject(new Error('synthetic failure')) : pending.promise })
  await h.session.open('music_a')
  await assert.rejects(h.session.reportPlayStarted('music_a'), /synthetic failure/)
  const first = h.session.reportPlayStarted('music_a'), second = h.session.reportPlayStarted('music_a')
  pending.resolve({ replayed: false }); await first; await second
  assert.equal(h.calls.length, 2)
  assert.deepEqual(h.calls.map(x => x[1]), ['synthetic-event', 'synthetic-event'])
  assert.equal((await h.session.reportPlayStarted('music_a')).reported, false)
  assert.equal(JSON.stringify(h.session.getState()).includes('synthetic-A'), false)
})
test('History R1: absent authentication proof fails closed before detail request', async () => {
  let reads = 0
  const session = createHistoricalMusicSession({ api: { getMusicAsset: async () => { reads++; return detail() } }, getOwnerId: () => 'A' })
  await assert.rejects(session.open('music_a'), { code: 'IDENTITY_REQUIRED' })
  assert.equal(reads, 0)
})

function pageHarness({ handler = null, missing = null, subscriptionFalse = false, live = true } = {}) {
  const storage = new Map([['v3_public_user_id', 'A'], ['v3_access_token', 'synthetic-A'], ['v3_auth_epoch', 0]])
  const listeners = new Set()
  const h = { storage, requests: [], callbacks: [], contexts: [], toasts: [], loads: [], navigations: [], normalReads: 0, controllerCreations: 0, downloads: 0 }
  const uni = {
    getStorageSync: key => storage.get(key) ?? '',
    $on: (event, fn) => { assert.equal(event, 'harmonyai:v3-auth-changed'); listeners.add(fn); if (subscriptionFalse) return false },
    $off: (event, fn) => { listeners.delete(fn) },
    $emit: () => { for (const fn of [...listeners]) fn() },
    showToast: args => h.toasts.push(args.title),
    navigateTo: args => h.navigations.push(args.url),
    createInnerAudioContext() {
      const events = {}, ctx = { events, src: '', duration: 120, currentTime: 0, plays: 0, destroyed: 0,
        play() { this.plays++ }, pause() {}, seek(value) { this.currentTime = value }, destroy() { this.destroyed++ } }
      for (const name of ['Play', 'Canplay', 'TimeUpdate', 'Ended', 'Error']) ctx['on' + name] = fn => { events[name] = fn }
      h.contexts.push(ctx); return ctx
    },
    request(args) {
      const request = { method: args.method, path: new URL(args.url).pathname, data: args.data }
      h.requests.push(request)
      Promise.resolve().then(() => handler ? handler(request) : request.method === 'GET' ? detail(request.path.split('/').at(-1)) : {})
        .then(data => args.success({ statusCode: 200, data: { ok: true, data } }),
          () => args.success({ statusCode: 409, data: { ok: false, error: { code: 'SYNTHETIC_FAILURE' } } }))
    },
  }
  if (missing) delete uni[missing]
  const src = readFileSync(new URL('../pages/v3-player/v3-player.vue', import.meta.url), 'utf8')
  const script = src.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g, (_, names) => `const {${names}}=deps;`)
    // VM-only branch injection, not a change to the production feature flag.
    .replace('const HISTORICAL_LIBRARY_ENABLED = false', `const HISTORICAL_LIBRARY_ENABLED = ${live}`)
    .replace('export default {', 'pageOptions = {')
  const apiV3 = {
    getMusic: async () => { h.normalReads++; return { music_ref: { music_id: 'normal' }, stream_url: '/synthetic', favorite: false } },
    getMusicBasis: async () => ({ synthetic: true }), getCurrentUserGoal: () => null,
    fetchAuthorizedAudio: async () => { h.downloads++; return '/synthetic/local.wav' },
  }
  const context = { uni, pageOptions: null, deps: { apiV3, ...presentation, ...seek, createMusicLibraryApi,
    createHistoricalMusicSession, resolvePlayableAudio, putHistoricalFeedback,
    readV3AccessToken: () => transport.readV3AccessToken(uni),
    createUniMusicLibraryTransport: options => transport.createUniMusicLibraryTransport({ ...options, uniApi: uni }),
    createPlayerController: options => { h.controllerCreations++; h.callbacks.push(options); return createPlayerController(options) },
  } }
  runInNewContext(script, context)
  h.options = context.pageOptions; h.page = { ...h.options.data() }
  for (const [name, fn] of Object.entries(h.options.methods)) h.page[name] = fn.bind(h.page)
  const load = h.page.load
  h.page.load = (...args) => { const promise = load(...args); h.loads.push(promise); return promise }
  h.start = async (query = { music_id: 'music_a' }) => { h.options.onLoad.call(h.page, query); await flush() }
  h.finish = async () => { await Promise.all(h.loads); await flush() }
  h.unload = () => h.options.onUnload.call(h.page)
  h.auth = ({ owner = 'A', token = 'synthetic-A', epoch = 1 } = {}, emit = true) => {
    storage.set('v3_public_user_id', owner); storage.set('v3_access_token', token); storage.set('v3_auth_epoch', epoch)
    if (emit && uni.$emit) uni.$emit('harmonyai:v3-auth-changed')
  }
  h.listeners = () => listeners.size
  return h
}
test('History R1: unload pending detail never restores private state or controller', async () => {
  const pending = deferred(), h = pageHarness({ handler: () => pending.promise })
  await h.start(); h.unload(); pending.resolve(detail()); await h.finish()
  assert.equal(h.page.music, null); assert.equal(h.page.basis, null); assert.equal(h.page.userGoal, null)
  assert.equal(h.page.favorite, false); assert.equal(h.controllerCreations, 0); assert.equal(h.requests.length, 1)
})
test('History R1: unloaded pending error and finally do not mutate page state', async () => {
  const pending = deferred(), h = pageHarness({ handler: () => pending.promise })
  await h.start(); h.unload()
  const before = { loading: h.page.loading, error: h.page.loadFailure, state: h.page.playerState }
  pending.reject(new Error('synthetic late error')); await h.finish()
  assert.equal(h.page.loading, before.loading); assert.equal(h.page.loadFailure, before.error)
  assert.equal(h.page.playerState, before.state); assert.equal(h.toasts.length, 0)
})
test('History R1: newer load wins and old detail cannot create another controller', async () => {
  const old = deferred(), current = deferred()
  const h = pageHarness({ handler: r => r.path.endsWith('music_a') ? old.promise : current.promise })
  await h.start(); h.page.historicalMusicId = 'music_b'; const second = h.page.load(); await flush()
  current.resolve(detail('music_b')); await second
  old.resolve(detail('music_a')); await h.finish()
  assert.equal(h.page.music.music_ref.music_id, 'music_b'); assert.equal(h.controllerCreations, 1)
  h.unload()
})
test('History R1: auth notification stops audio and stale callbacks cannot revive page', async () => {
  const h = pageHarness(); await h.start(); await h.finish(); await h.page.togglePlay()
  const ctx = h.contexts[0], callbacks = h.callbacks[0]
  h.auth({ owner: 'A', token: 'synthetic-A', epoch: 1 })
  assert.equal(ctx.destroyed, 1); assert.equal(h.page.music, null); assert.equal(h.page.playerController, null)
  const state = h.page.playerState
  callbacks.onStateChange({ playing: true }); callbacks.onPlaybackStarted(); callbacks.onError(new Error('late'))
  assert.equal(h.page.playerState, state); assert.equal(h.toasts.length, 0)
  assert.equal(h.requests.filter(x => x.method === 'POST').length, 0)
  h.unload(); assert.equal(h.listeners(), 0)
})
test('History R1: old auth blocks play and favorite even without onShow or notification', async () => {
  const h = pageHarness(); await h.start(); await h.finish()
  h.auth({ epoch: 1 }, false)
  await h.page.togglePlay(); await h.page.toggleFavorite()
  assert.equal(h.downloads, 0); assert.equal(h.requests.filter(x => x.method !== 'GET').length, 0)
  h.unload()
})
test('History R1: unload blocks late audio callbacks and historical writes', async () => {
  const h = pageHarness(); await h.start(); await h.finish(); const callbacks = h.callbacks[0]
  h.unload(); const state = h.page.playerState
  callbacks.onStateChange({ playing: true }); callbacks.onError(new Error('late')); callbacks.onPlaybackStarted()
  await h.page.togglePlay(); await h.page.toggleFavorite()
  assert.equal(h.page.playerState, state); assert.equal(h.toasts.length, 0)
  assert.equal(h.requests.filter(x => x.method !== 'GET').length, 0)
})
test('History R1: authentication release clears the old private playback snapshot', async () => {
  const h = pageHarness(); await h.start(); await h.finish(); await h.page.togglePlay()
  assert.equal(h.page.playerState.playing, true)
  assert.ok(h.page.playerState.src)
  h.auth({ owner: 'B', token: 'synthetic-B', epoch: 1 })
  assert.equal(h.page.playerState.playing, false)
  assert.equal(h.page.playerState.currentTime, 0); assert.equal(h.page.playerState.duration, 0)
  assert.equal(h.page.playerState.src || '', ''); assert.equal(h.page.playerState.streamUrl || '', '')
  h.unload()
})
for (const missing of ['$on', '$off', '$emit', 'subscription']) {
  test(`History R1: ${missing} unavailable denies all live historical requests`, async () => {
    const h = pageHarness(missing === 'subscription' ? { subscriptionFalse: true } : { missing })
    await h.start(); await h.finish()
    assert.equal(h.requests.length, 0); assert.equal(h.controllerCreations, 0)
    assert.equal(h.page.loadFailure?.code, 'FEATURE_NOT_READY'); assert.equal(h.listeners(), 0)
    h.unload()
  })
}
test('History R1: normal history plays use actual onPlay once and keep one controller', async () => {
  const h = pageHarness(); await h.start(); await h.finish(); await h.page.togglePlay()
  assert.equal(h.requests.filter(x => x.method === 'POST').length, 0)
  h.contexts[0].events.Play(); h.contexts[0].events.Play(); await flush(); await flush()
  assert.equal(h.requests.filter(x => x.method === 'POST').length, 1)
  assert.equal(h.controllerCreations, 1); h.unload()
})
test('History R1: legacy non-history load, pause and seek remain compatible', async () => {
  const h = pageHarness({ missing: '$on' }); await h.start({}); await h.finish()
  assert.equal(h.normalReads, 1); assert.equal(h.page.music.music_ref.music_id, 'normal')
  await h.page.togglePlay(); const ctx = h.contexts[0]; ctx.events.Canplay()
  assert.equal(h.page.seekToRatio(0.25), true); assert.equal(ctx.currentTime, 30)
  h.options.onHide.call(h.page); assert.equal(h.page.playerController.getState().playing, false)
  assert.equal(h.requests.length, 0); h.unload(); assert.equal(ctx.destroyed, 1)
})
test('History R1: production historical gate remains closed', async () => {
  const h = pageHarness({ live: false }); await h.start(); await h.finish()
  assert.equal(h.requests.length, 0); assert.equal(h.page.loadFailure?.code, 'FEATURE_NOT_READY')
  h.unload()
})

test('M1: historical feedback never falls back to the current flow session', async () => {
  const h = pageHarness(); await h.start(); await h.finish()
  h.page.goFeedback()
  assert.deepEqual(h.navigations, [])
  assert.equal(h.contexts[0]?.destroyed || 0, 0)
  assert.equal(h.toasts.length, 1)
  h.unload()
})


test('History R1: existing Player hands off only selected server context and acknowledged event', async () => {
  const h = pageHarness({handler:args => {
    if (args.method === 'POST') return {event_id:args.data.event_id,music_id:'music_a',event_type:'play_started'}
    const data=detail();data.source_contexts=[{context_id:'ctx-a',session_id:'old-session'}];data.selected_context_id='ctx-a';return data
  }})
  await h.start();await h.finish()
  await h.page.historicalSession.reportPlayStarted('music_a')
  h.page.goFeedback()
  assert.equal(h.navigations.length,1)
  const key=h.navigations[0].split('handoff=')[1]
  const context=consumeHistoricalFeedback(decodeURIComponent(key))
  assert.equal(context.session_id,'old-session');assert.equal(context.source_context_id,'ctx-a')
  assert.equal(context.music_ref.music_id,'music_a');h.unload()
})
