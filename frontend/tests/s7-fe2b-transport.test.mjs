/**
 * Sprint 7 M1 / FE-2B — Music Library 真实 transport 测试
 *
 * 覆盖：V3 envelope 解析、错误码透传（不发明）、uni 不可用降级、
 * 默认 fail-closed（liveEnabled=false 时 adapter 拒绝）。
 */
import assert from "node:assert/strict"
import test from "node:test"

import { createMusicLibraryApi } from "../common/music-library-api.js"
import {
  MUSIC_LIBRARY_LIVE_ENABLED,
  TRANSPORT_ERROR,
  createLiveMusicLibraryApi,
  createUniMusicLibraryTransport,
  readV3AccessToken,
} from "../common/music-library-transport.js"

function fakeUni(handler) {
  return {
    request(args) {
      handler(args)
    },
  }
}

test("FE2B: transport resolves the V3 envelope data payload", async () => {
  const seen = []
  const request = createUniMusicLibraryTransport({
    baseUrl: "https://api.example.test",
    getAccessToken: () => "token-1",
    uniApi: fakeUni((args) => {
      seen.push(args)
      args.success({ statusCode: 200, data: { ok: true, data: { items: [], next_cursor: null, has_more: false } } })
    }),
  })
  const res = await request({ method: "GET", path: "/api/v3/me/music-assets?limit=20" })
  assert.deepEqual(res, { data: { items: [], next_cursor: null, has_more: false } })
  assert.equal(seen[0].url, "https://api.example.test/api/v3/me/music-assets?limit=20")
  assert.equal(seen[0].header.Authorization, "Bearer token-1")
})

test("FE2B: transport forwards server error codes without inventing new ones", async () => {
  const request = createUniMusicLibraryTransport({
    getAccessToken: () => "test-token",
    uniApi: fakeUni((args) => {
      args.success({
        statusCode: 409,
        data: { ok: false, error: { code: "METADATA_VERSION_CONFLICT", message: "stale" } },
      })
    }),
  })
  const res = await request({ method: "PATCH", path: "/api/v3/music/assets/m/title" })
  assert.equal(res.error.code, "METADATA_VERSION_CONFLICT")
})

test("FE2B: transport degrades to a local error when uni is unavailable", async () => {
  const request = createUniMusicLibraryTransport({ getAccessToken: () => "test-token", uniApi: null })
  const res = await request({ method: "GET", path: "/api/v3/me/music-assets" })
  assert.equal(res.error.code, TRANSPORT_ERROR.UNAVAILABLE)
})

test("FE2B: transport maps network failure to NETWORK_ERROR", async () => {
  const request = createUniMusicLibraryTransport({
    getAccessToken: () => "test-token",
    uniApi: fakeUni((args) => args.fail({ errMsg: "request:fail" })),
  })
  const res = await request({ method: "GET", path: "/api/v3/me/music-assets" })
  assert.equal(res.error.code, TRANSPORT_ERROR.NETWORK)
})

test("FE2B: live api stays fail-closed until the gate is explicitly enabled", async () => {
  assert.equal(MUSIC_LIBRARY_LIVE_ENABLED, false, "live transport must default to closed")

  const closed = createLiveMusicLibraryApi({
    createApi: createMusicLibraryApi,
    getOwnerId: () => "A",
    liveEnabled: false,
    transportOptions: { uniApi: fakeUni(() => assert.fail("transport must not be called")) },
  })
  await assert.rejects(closed.listMusicAssets(), { code: "FEATURE_NOT_READY" })

  const calls = []
  const open = createLiveMusicLibraryApi({
    createApi: createMusicLibraryApi,
    getOwnerId: () => "A",
    liveEnabled: true,
    transportOptions: {
      getAccessToken: () => "test-token",
      uniApi: fakeUni((args) => {
        calls.push(args.url)
        args.success({ statusCode: 200, data: { ok: true, data: { items: [], next_cursor: null, has_more: false } } })
      }),
    },
  })
  const page = await open.listMusicAssets()
  assert.deepEqual(page.items, [])
  assert.equal(calls.length, 1)
})

test("FE2B: bearer token comes from credential storage, never public user id", () => {
  const fake = { getStorageSync: key => ({
    v3_access_token: "real-token", v3_public_user_id: "public-user-id"
  })[key] }
  assert.equal(readV3AccessToken(fake), "real-token")
  assert.equal(readV3AccessToken({ getStorageSync() { throw Error("unavailable") } }), "")
})
test("FE2B: HTTP 200 with ok=false cannot bypass V3 envelope error", async () => {
  const request = createUniMusicLibraryTransport({
    getAccessToken: () => "test-token",
    uniApi: fakeUni(args => args.success({ statusCode: 200, data: { ok: false, data: { private: true }, error: { code: "ACCESS_DENIED" } } }))
  })
  assert.equal((await request({ method: "GET", path: "/x" })).error.code, "ACCESS_DENIED")
})

test("FE2B: missing bearer fails locally with no uni.request invocation", async () => {
  let calls = 0
  const request = createUniMusicLibraryTransport({
    getAccessToken: () => "",
    uniApi: fakeUni(() => { calls++ }),
  })
  const result = await request({ method: "GET", path: "/api/v3/me/music-assets" })
  assert.equal(result.error.code, TRANSPORT_ERROR.AUTH_REQUIRED)
  assert.equal(calls, 0)
})
