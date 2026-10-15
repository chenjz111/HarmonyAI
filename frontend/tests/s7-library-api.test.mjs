import test from 'node:test'
import assert from 'node:assert/strict'
import { createMusicLibraryApi } from '../common/music-library-api.js'
import { MUSIC_CARD_V1_PREVIEW_FIXTURE as cards } from '../common/music-card-v1-preview-fixture.js'

test('library adapter is closed by default and never creates an identity', async () => {
  const api = createMusicLibraryApi({ getOwnerId: () => 'A', request: () => assert.fail('transport called') })
  await assert.rejects(api.listMusicAssets(), { code: 'FEATURE_NOT_READY' })
})

test('library adapter uses frozen page DTO and preserves null duration and unplayed music', async () => {
  const calls = []
  const page = { items: cards, next_cursor: 'opaque-cursor', has_more: true }
  const api = createMusicLibraryApi({ enabled: true, getOwnerId: () => 'A', request: async (call) => {
    calls.push(call); return { data: page }
  } })
  assert.deepEqual(await api.listMusicAssets({ limit: 20, cursor: 'a/b' }), page)
  assert.equal(calls[0].path, '/api/v3/me/music-assets?limit=20&cursor=a%2Fb')
  assert.equal(page.items[0].last_played_at, null)
  assert.equal(page.items[0].duration_seconds, null)
})

test('owner changes discard late responses and do not leak the old owner card', async () => {
  let owner = 'A', finish
  const api = createMusicLibraryApi({ enabled: true, getOwnerId: () => owner,
    request: () => new Promise((resolve) => { finish = resolve }) })
  const pending = api.listMusicAssets()
  owner = 'B'
  finish({ data: { items: cards, next_cursor: null, has_more: false } })
  await assert.rejects(pending, { code: 'OWNER_CHANGED' })
})

test('history details read only music_id/context and preserve unavailable audio', async () => {
  const calls = []
  const detail = { ...cards[1], schema_version: 'music_library_detail_v1', audio_asset: null,
    explanation: null, explanation_status: 'unavailable', playback_context: {
      selection_state: 'selection_required', contexts: [], selected_context_id: null,
    } }
  const api = createMusicLibraryApi({ enabled: true, getOwnerId: () => 'A', request: async (call) => {
    calls.push(call); return { data: detail }
  } })
  assert.deepEqual(await api.getMusicAsset('a/b', { contextId: 'task/a' }), detail)
  assert.deepEqual(calls, [{ method: 'GET', path: '/api/v3/music/assets/a%2Fb?context_id=task%2Fa' }])
})

test('title CAS and explicit play event preserve server errors without retrying generation', async () => {
  const calls = []
  const api = createMusicLibraryApi({ enabled: true, getOwnerId: () => 'A', request: async (call) => {
    calls.push(call)
    if (call.method === 'PATCH') return { error: { code: 'METADATA_VERSION_CONFLICT', message: 'stale' } }
    return { data: { music_id: 'm', last_played_at: '2026-10-14T10:00:00Z', activity_at: '2026-10-14T10:00:00Z' } }
  } })
  await assert.rejects(api.setMusicTitle('m', null, 2), { code: 'METADATA_VERSION_CONFLICT' })
  await api.recordPlayStarted('m', 'event-1', null)
  assert.deepEqual(calls[0].data, { user_title: null, expected_version: 2 })
  assert.deepEqual(calls[1].data, { event_id: 'event-1', event_type: 'play_started', source_context_id: null })
  assert.equal(calls.length, 2)
})

test('favorites remain an independent owner-scoped request and mutation', async () => {
  const calls = []
  const api = createMusicLibraryApi({ enabled: true, getOwnerId: () => 'A', request: async (call) => {
    calls.push(call); return { data: { items: [], next_cursor: null, has_more: false } }
  } })
  await api.listMusicFavorites()
  await api.setFavorite({ music_id: 'm', source_type: 'matched' }, true)
  await api.setFavorite({ music_id: 'm', source_type: 'matched' }, false)
  assert.deepEqual(calls.map((c) => [c.method, c.path]), [
    ['GET', '/api/v3/me/music-favorites?limit=20'], ['PUT', '/api/v3/favorites'], ['DELETE', '/api/v3/favorites/m'],
  ])
  assert.deepEqual(calls[1].data, { music_ref: { music_id: 'm', source_type: 'matched' } })
})
