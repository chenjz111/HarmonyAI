/**
 * Sprint 7 M1 / FE-2B — 音乐库分页状态模型测试
 *
 * 覆盖 Issue #153：分页、cursor stale 刷新与去重、迟到响应丢弃、
 * 收藏独立视图、标题 null 清除。
 */
import assert from "node:assert/strict"
import test from "node:test"

import {
  createMusicLibraryStore,
  isCursorStale,
  mergeMusicCards,
  normalizeUserTitle,
  splitFavorites,
} from "../common/music-library-state.js"

const cardA = { music_id: "a", is_favorite: false, availability: "ready" }
const cardB = { music_id: "b", is_favorite: true, availability: "expired" }
const cardC = { music_id: "c", is_favorite: false, availability: "ready" }

test("FE2B: mergeMusicCards deduplicates by music_id keeping first occurrence", () => {
  const merged = mergeMusicCards([cardA], [cardA, cardB, { music_id: "a", is_favorite: true }])
  assert.deepEqual(merged.map((c) => c.music_id), ["a", "b"])
  assert.equal(merged[0].is_favorite, false, "existing card wins over late duplicate")
})

test("FE2B: store loads pages with cursor and has_more", async () => {
  const pages = [
    { items: [cardA], next_cursor: "cur-1", has_more: true },
    { items: [cardB], next_cursor: null, has_more: false },
  ]
  const calls = []
  const store = createMusicLibraryStore({
    pageSize: 1,
    fetchPage: async (args) => {
      calls.push(args)
      return pages[calls.length - 1]
    },
  })
  let state = await store.loadFirstPage()
  assert.equal(state.status, "ready")
  assert.deepEqual(state.items.map((c) => c.music_id), ["a"])
  assert.equal(state.hasMore, true)

  state = await store.loadMore()
  assert.deepEqual(state.items.map((c) => c.music_id), ["a", "b"])
  assert.equal(state.hasMore, false)
  assert.deepEqual(calls, [{ cursor: null, limit: 1 }, { cursor: "cur-1", limit: 1 }])
})

test("FE2B: store stops paging when has_more is false", async () => {
  let calls = 0
  const store = createMusicLibraryStore({
    fetchPage: async () => {
      calls += 1
      return { items: [cardA], next_cursor: null, has_more: false }
    },
  })
  await store.loadFirstPage()
  await store.loadMore()
  assert.equal(calls, 1, "loadMore must not call transport when has_more is false")
})

test("FE2B: cursor stale refreshes from scratch without duplicating items", async () => {
  let call = 0
  const store = createMusicLibraryStore({
    fetchPage: async ({ cursor }) => {
      call += 1
      if (call === 1) return { items: [cardA], next_cursor: "cur-1", has_more: true }
      if (cursor === "cur-1") {
        throw Object.assign(new Error("cursor expired"), { code: "LIBRARY_CURSOR_STALE" })
      }
      return { items: [cardA, cardB], next_cursor: null, has_more: false }
    },
  })
  await store.loadFirstPage()
  const state = await store.loadMore()
  assert.equal(state.status, "ready")
  assert.deepEqual(state.items.map((c) => c.music_id), ["a", "b"], "no duplicates after stale refresh")
  assert.equal(state.cursorStaleRefreshed, true)
})

test("FE2B: isCursorStale recognises frozen stale codes only", () => {
  assert.equal(isCursorStale({ code: "CURSOR_STALE" }), true)
  assert.equal(isCursorStale({ code: "LIBRARY_CURSOR_STALE" }), true)
  assert.equal(isCursorStale({ code: "CURSOR_EXPIRED" }), true)
  assert.equal(isCursorStale({ code: "NETWORK_ERROR" }), false)
  assert.equal(isCursorStale(null), false)
})

test("FE2B: store discards late responses after owner switch", async () => {
  let owner = "A"
  let finish
  const store = createMusicLibraryStore({
    getOwnerId: () => owner,
    fetchPage: () => new Promise((resolve) => { finish = resolve }),
  })
  const pending = store.loadFirstPage()
  owner = "B"
  finish({ items: [cardA], next_cursor: null, has_more: false })
  const state = await pending
  assert.deepEqual(state.items, [], "late response for old owner must not populate the list")
})

test("FE2B: error state surfaces the transport failure", async () => {
  const store = createMusicLibraryStore({
    fetchPage: async () => {
      throw Object.assign(new Error("boom"), { code: "REQUEST_FAILED" })
    },
  })
  const state = await store.loadFirstPage()
  assert.equal(state.status, "error")
  assert.equal(state.error.code, "REQUEST_FAILED")
})

test("FE2B: favorites are a separate view derived from the same cards", () => {
  assert.deepEqual(splitFavorites([cardA, cardB, cardC]).map((c) => c.music_id), ["b"])
})

test("FE2B: normalizeUserTitle maps blank input to explicit null (clear)", () => {
  assert.equal(normalizeUserTitle("  "), null)
  assert.equal(normalizeUserTitle(""), null)
  assert.equal(normalizeUserTitle(null), null)
  assert.equal(normalizeUserTitle(" 午后安静 "), "午后安静")
})
