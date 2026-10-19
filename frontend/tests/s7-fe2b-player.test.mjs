/**
 * Sprint 7 M1 / FE-2B — 历史音乐播放会话测试
 *
 * 覆盖 Issue #153：music_id → MusicDetailV1 读取、不可播处理、
 * play_started 仅上报一次且重试复用 event id、owner 切换拒绝迟到结果、
 * 页面保持单一 Player 且不读当前 session 解析。
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import {
  createHistoricalMusicSession,
  isDetailPlayable,
  resolvePlayableAudio,
} from "../common/music-library-player.js"

const playerSource = readFileSync(new URL("../pages/v3-player/v3-player.vue", import.meta.url), "utf8")
const profileSource = readFileSync(new URL("../pages/v3-profile/v3-profile.vue", import.meta.url), "utf8")

const playableDetail = {
  music_id: "music_a",
  schema_version: "music_library_detail_v1",
  display_title: "午后安静",
  source_type: "generated",
  duration_seconds: 131,
  is_favorite: true,
  audio_asset: { stream_url: "/api/v3/music/assets/music_a/stream", duration_seconds: 131 },
  playback_context: { selection_state: "resolved", contexts: [], selected_context_id: null },
}

test("FE2B: playable detail resolves LibraryAudioV1 without inventing fields", () => {
  assert.equal(isDetailPlayable(playableDetail), true)
  const audio = resolvePlayableAudio(playableDetail)
  assert.deepEqual(audio, {
    music_id: "music_a",
    stream_url: "/api/v3/music/assets/music_a/stream",
    duration_seconds: 131,
    source_type: "generated",
  })
})

test("FE2B: unavailable audio is not playable and carries no stream", () => {
  const detail = { ...playableDetail, audio_asset: null, availability: "expired" }
  assert.equal(isDetailPlayable(detail), false)
  assert.equal(resolvePlayableAudio(detail), null)
})

test("FE2B: unknown duration stays null rather than a fabricated number", () => {
  const detail = { ...playableDetail, duration_seconds: null, audio_asset: { stream_url: "/x" } }
  assert.equal(resolvePlayableAudio(detail).duration_seconds, null)
})

test("FE2B: open requires an owner and reads detail through the library api", async () => {
  const calls = []
  const api = {
    getMusicAsset: async (id, opts) => {
      calls.push([id, opts])
      return playableDetail
    },
    recordPlayStarted: async () => ({ ok: true }),
  }

  const noOwner = createHistoricalMusicSession({ api, getOwnerId: () => null, newEventId: () => "e1" })
  await assert.rejects(noOwner.open("music_a"), { code: "IDENTITY_REQUIRED" })

  const session = createHistoricalMusicSession({ api, getOwnerId: () => "A", newEventId: () => "e1" })
  const detail = await session.open("music_a")
  assert.equal(detail.music_id, "music_a")
  assert.deepEqual(calls, [["music_a", { contextId: null }]])
})

test("FE2B: play_started is reported once even if play fires again", async () => {
  const events = []
  const api = {
    getMusicAsset: async () => playableDetail,
    recordPlayStarted: async (id, eventId, ctx) => {
      events.push([id, eventId, ctx])
      return { ok: true }
    },
  }
  const session = createHistoricalMusicSession({ api, getOwnerId: () => "A", newEventId: () => "evt-1" })
  await session.open("music_a")
  const first = await session.reportPlayStarted("music_a")
  const second = await session.reportPlayStarted("music_a")
  assert.equal(first.reported, true)
  assert.equal(second.reported, false)
  assert.equal(events.length, 1, "only the real onPlay success reports an event")
})

test("FE2B: failed report reuses the same event id on retry", async () => {
  let attempts = 0
  const seen = []
  const api = {
    getMusicAsset: async () => playableDetail,
    recordPlayStarted: async (id, eventId) => {
      attempts += 1
      seen.push(eventId)
      if (attempts === 1) throw Object.assign(new Error("boom"), { code: "REQUEST_FAILED" })
      return { ok: true }
    },
  }
  const session = createHistoricalMusicSession({ api, getOwnerId: () => "A", newEventId: () => "evt-fixed" })
  await session.open("music_a")
  await assert.rejects(session.reportPlayStarted("music_a"), { code: "REQUEST_FAILED" })
  const retry = await session.reportPlayStarted("music_a")
  assert.equal(retry.reported, true)
  assert.deepEqual(seen, ["evt-fixed", "evt-fixed"], "retry must reuse the same event id")
})

test("FE2B: owner switch rejects late detail and late play reports", async () => {
  let owner = "A"
  let finish
  const api = {
    getMusicAsset: () => new Promise((resolve) => { finish = resolve }),
    recordPlayStarted: async () => ({ ok: true }),
  }
  const session = createHistoricalMusicSession({ api, getOwnerId: () => owner, newEventId: () => "e1" })
  const pending = session.open("music_a")
  owner = "B"
  finish(playableDetail)
  await assert.rejects(pending, { code: "OWNER_CHANGED" })
  assert.equal(session.hasOwnerChanged(), true)
})

test("FE2B: historical player keeps a single controller and never reads session analysis", () => {
  // 历史通道只读 MusicDetailV1；不得用当前会话解析/UserGoal 替代旧资料
  assert.match(playerSource, /loadHistorical/)
  assert.match(playerSource, /resolvePlayableAudio/)
  assert.match(playerSource, /HISTORICAL_LIBRARY_ENABLED = false/)
  assert.match(playerSource, /onLoad\(query\)/)
  assert.match(playerSource, /query\.music_id/)
  assert.match(playerSource, /historicalSession\.reportPlayStarted/)
  assert.match(playerSource, /historicalSession\.hasOwnerChanged\(\)/)
  // 仍然只有一个 Player controller，页面不直接持有音频上下文
  assert.match(playerSource, /createPlayerController/)
  assert.doesNotMatch(playerSource, /uni\.createInnerAudioContext\s*\(/)
  assert.doesNotMatch(playerSource, /\baudioCtx\b/)
  // 历史分支不得复用当前会话解析
  assert.match(playerSource, /this\.basis = null \/\/ 历史播放不读取当前会话解析/)
})

test("FE2B: My page keeps frozen preview by default and never renders HTML", () => {
  assert.match(profileSource, /MUSIC_LIBRARY_LIVE_ENABLED/)
  assert.match(profileSource, /界面预览 · 虚构数据/)
  assert.match(profileSource, /HISTORICAL_PLAYER_LINK_ENABLED = false/)
  assert.doesNotMatch(profileSource, /v-html/)
  assert.doesNotMatch(profileSource, /createInnerAudioContext|new Audio|audioCtx/)
})
