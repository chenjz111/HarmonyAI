import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

import { MUSIC_CARD_V1_PREVIEW_FIXTURE as historyCards } from "../common/music-card-v1-preview-fixture.js"
import {
  createMusicLibraryPreview,
  musicPlayerUrl,
  presentMusicCard,
} from "../common/music-library-state.js"


const here = dirname(fileURLToPath(import.meta.url))
const profileSource = readFileSync(resolve(here, "../pages/v3-profile/v3-profile.vue"), "utf8")


test("MusicCardV1 preview keeps unplayed history and never invents unknown duration", () => {
  const preview = createMusicLibraryPreview("ready", historyCards)

  assert.equal(preview.history.length, 2)
  assert.equal(preview.history[0].music_id, "music_unplayed")
  assert.equal(preview.history[0].playback_label, "尚未播放")
  assert.equal(preview.history[0].duration_label, "时长未知")
  assert.equal(preview.history[0].can_open, true)
})


test("favorites are an independent view and unavailable audio remains visible but closed", () => {
  const preview = createMusicLibraryPreview("ready", historyCards)

  assert.deepEqual(preview.favorites.map((card) => card.music_id), ["music_expired"])
  assert.equal(preview.favorites[0].availability_label, "音频已不可用")
  assert.equal(preview.favorites[0].can_open, false)
  assert.equal(Object.hasOwn(preview.favorites[0], "learning_consent"), false)
  assert.equal(Object.hasOwn(preview.favorites[0], "preference"), false)
})


test("preview explicitly models loading, empty and error states", () => {
  assert.deepEqual(createMusicLibraryPreview("loading", historyCards), {
    status: "loading", history: [], favorites: [], error: null,
  })
  assert.deepEqual(createMusicLibraryPreview("empty", historyCards), {
    status: "empty", history: [], favorites: [], error: null,
  })
  assert.equal(createMusicLibraryPreview("error", historyCards).error, "暂时无法加载音乐记录")
})


test("card titles remain plain text and Player entry carries only encoded music_id", () => {
  const hostile = presentMusicCard({ ...historyCards[0], display_title: "<img src=x onerror=alert(1)>" })
  assert.equal(hostile.display_title, "<img src=x onerror=alert(1)>")
  assert.equal(musicPlayerUrl("music/a b"), "/pages/v3-player/v3-player?music_id=music%2Fa%20b")
  assert.match(profileSource, /<text class="music-title">\{\{ item\.display_title \}\}<\/text>/)
  assert.doesNotMatch(profileSource, /v-html/)
})


test("My page labels preview data and preserves one existing Player", () => {
  assert.match(profileSource, /我的音乐/)
  assert.match(profileSource, /界面预览 · 虚构数据/)
  assert.match(profileSource, /musicPlayerUrl\(item\.music_id\)/)
  assert.doesNotMatch(profileSource, /createInnerAudioContext|new Audio|audioCtx/)
})


test("My page consumes the one frozen preview fixture and keeps historical Player navigation disabled", () => {
  assert.match(profileSource, /import \{ MUSIC_CARD_V1_PREVIEW_FIXTURE \} from "\.\.\/\.\.\/common\/music-card-v1-preview-fixture\.js"/)
  assert.match(profileSource, /HISTORICAL_PLAYER_LINK_ENABLED = false/)
  assert.match(profileSource, /if \(!item\.can_open \|\| !HISTORICAL_PLAYER_LINK_ENABLED\) return/)
})
