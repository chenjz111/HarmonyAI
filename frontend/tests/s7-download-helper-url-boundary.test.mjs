import test from 'node:test'
import assert from 'node:assert/strict'
import { apiV3 } from '../common/api-v3.js'
import { createPlayerController } from '../common/player-controller.js'
import { resolvePlayableAudio } from '../common/music-library-player.js'

// Only the platform I/O is fake: the exported helper and controller are real.
function platform(response = { statusCode: 200, tempFilePath: '/synthetic/audio.wav' }) {
  const calls = []
  globalThis.uni = {
    getStorageSync: key => key === 'v3_access_token' ? 'synthetic-only' : '',
    downloadFile(options) { calls.push(options); options.success(response) },
  }
  return calls
}

for (const input of [
  '/api/v3/music/assets/one/stream',
  'http://localhost:8000/api/v3/music/assets/one/stream',
  'HTTP://LOCALHOST:8000/api/v3/music/assets/one/stream',
  'http://localhost:8000/api/%2F%2Fevil.invalid?next=https%3A%2F%2Fevil.invalid',
]) {
  test(`authorized exact origin: ${input}`, async () => {
    const calls = platform()
    assert.equal(await apiV3.fetchAuthorizedAudio(input), '/synthetic/audio.wav')
    assert.equal(calls.length, 1)
    assert.equal(new URL(calls[0].url).origin, 'http://localhost:8000')
    assert.equal(calls[0].header.Authorization, 'Bearer synthetic-only')
  })
}

for (const input of [
  'http://localhost:8000@audit-only.invalid/audio',
  'http://localhost:8000@localhost:8000/audio',
  'http://localhost:8000%40audit-only.invalid/audio',
  'http://localhost:8000\\@audit-only.invalid/audio',
  'http://local\thost:8000/audio',
  '//localhost:8000/audio',
  'https://',
  'javascript:alert(1)',
  'data:audio/wav;base64,not-real',
]) {
  test(`reject ambiguous or unsafe URL: ${JSON.stringify(input)}`, async () => {
    const calls = platform()
    await assert.rejects(() => apiV3.fetchAuthorizedAudio(input), error => error.code === 'AUDIO_FETCH_FAILED')
    assert.equal(calls.length, 0)
  })
}

for (const input of [
  'http://localhost:8001/audio',
  'http://localhost:800/audio',
  'http://localhost/audio',
  'https://localhost:8000/audio',
  'http://localhost.audit-only.invalid:8000/audio',
  'http://localhost.:8000/audio',
  'https://cdn.invalid/audio?next=http://localhost:8000',
  '/static/demo.mp3',
  '/static/demo audio.mp3',
  '_doc/uniapp_temp/audio.mp3',
  'blob:https://app.invalid/synthetic',
  'file:///synthetic/audio.wav',
  'wxfile://synthetic/audio.wav',
]) {
  test(`no credentialed download for external/local source: ${input}`, async () => {
    const calls = platform()
    assert.equal(await apiV3.fetchAuthorizedAudio(input), input)
    assert.equal(calls.length, 0)
  })
}

test('unavailable URL parser fails closed before credential lookup/download', async () => {
  const calls = platform()
  const original = globalThis.URL
  globalThis.URL = undefined
  try {
    await assert.rejects(() => apiV3.fetchAuthorizedAudio('/api/v3/music/assets/one/stream'),
      error => error.code === 'AUDIO_FETCH_FAILED')
    assert.equal(calls.length, 0)
    assert.equal(await apiV3.fetchAuthorizedAudio('/static/demo.mp3'), '/static/demo.mp3')
  } finally { globalThis.URL = original }
})

test('visible redirect/error response does not fall back to remote audio', async () => {
  for (const statusCode of [302, 307, 308, 401, 500]) {
    const calls = platform({ statusCode, tempFilePath: '/synthetic/audio.wav' })
    await assert.rejects(() => apiV3.fetchAuthorizedAudio('/api/v3/music/assets/one/stream'))
    assert.equal(calls.length, 1)
  }
})

test('actual historical DTO to controller to detached helper uses authorized local download', async () => {
  const calls = platform()
  const audio = resolvePlayableAudio({
    card: { music_id: 'one/encoded', availability: 'ready', source_type: 'generated' },
    audio: { availability: 'ready', duration_seconds: null },
  })
  const ctx = { play() {}, destroy() {} }
  const controller = createPlayerController({ downloadAudio: apiV3.fetchAuthorizedAudio, createAudioContext: () => ctx })
  await controller.play(audio.stream_url)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, 'http://localhost:8000/api/v3/music/assets/one%2Fencoded/stream')
  assert.equal(ctx.src, '/synthetic/audio.wav')
  controller.dispose()
})

test('controller refuses userinfo URL without downloading or creating audio context', async () => {
  const calls = platform()
  let contexts = 0
  const controller = createPlayerController({ downloadAudio: apiV3.fetchAuthorizedAudio,
    createAudioContext: () => { contexts++; return {} } })
  await controller.play('http://localhost:8000@audit-only.invalid/audio')
  assert.equal(calls.length, 0)
  assert.equal(contexts, 0)
  assert.equal(controller.getState().state, 'error')
  controller.dispose()
})
