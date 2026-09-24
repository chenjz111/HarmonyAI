/**
 * Sprint 6 Phase 6 — Player Controller 测试（PC-T1 ~ PC-T15）
 *
 * 被测模块：frontend/common/player-controller.js
 * 运行：cd frontend && node --test tests/*player-controller*.test.mjs
 *
 * 所有平台依赖（授权下载 / InnerAudioContext）均为测试注入的 fake，
 * 因此不需要真实 uni 环境或网络。
 */
import assert from "node:assert/strict"
import test from "node:test"

import { createPlayerController, PLAYER_STATE } from "../common/player-controller.js"

// ===== 测试替身 =====

function makeFakeAudioContext() {
  const listeners = {}
  const ctx = {
    src: "",
    duration: 0,
    currentTime: 0,
    playCount: 0,
    pauseCount: 0,
    destroyCount: 0,
    seeks: [],
    onCanplay(cb) {
      listeners.canplay = cb
    },
    onTimeUpdate(cb) {
      listeners.timeupdate = cb
    },
    onEnded(cb) {
      listeners.ended = cb
    },
    onError(cb) {
      listeners.error = cb
    },
    play() {
      this.playCount += 1
    },
    pause() {
      this.pauseCount += 1
    },
    seek(target) {
      this.seeks.push(target)
      this.currentTime = target
    },
    destroy() {
      this.destroyCount += 1
    },
    // --- 测试驱动事件 ---
    emitCanplay(d) {
      this.duration = d
      if (listeners.canplay) listeners.canplay()
    },
    emitTimeUpdate(t, d) {
      this.currentTime = t
      if (d !== undefined) this.duration = d
      if (listeners.timeupdate) listeners.timeupdate()
    },
    emitEnded() {
      if (listeners.ended) listeners.ended()
    },
    emitError(err) {
      if (listeners.error) listeners.error(err)
    },
  }
  return ctx
}

function makeHarness(opts = {}) {
  const audioCtx = makeFakeAudioContext()
  let contextCount = 0
  let downloadCount = 0
  const errors = []
  const states = []
  let resolveDownload
  const downloadGate = new Promise((resolve) => {
    resolveDownload = resolve
  })

  const controller = createPlayerController({
    downloadAudio: (url) => {
      downloadCount += 1
      if (opts.gated) {
        return downloadGate.then(() => "local://" + url)
      }
      return Promise.resolve("local://" + url)
    },
    createAudioContext: () => {
      contextCount += 1
      return audioCtx
    },
    onError: (e) => errors.push(e),
    onStateChange: (s) => states.push(s),
  })

  return {
    controller,
    audioCtx,
    errors,
    states,
    get downloadCount() {
      return downloadCount
    },
    get contextCount() {
      return contextCount
    },
    releaseDownload: () => resolveDownload(),
  }
}

const URL_A = "/api/v3/music/assets/asset_a/stream"

// ===== PC-T1 ~ PC-T5：播放 / 暂停 / 恢复 / 并发 / 单实例 =====

test("PC-T1 play starts playback", async () => {
  const h = makeHarness()
  const state = await h.controller.play(URL_A)
  assert.equal(state.playing, true)
  assert.equal(h.audioCtx.playCount, 1)
  assert.equal(h.downloadCount, 1)
  assert.equal(h.audioCtx.src, "local://" + URL_A)
})

test("PC-T2 pause stops playback", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  const state = h.controller.pause()
  assert.equal(state.playing, false)
  assert.equal(h.audioCtx.pauseCount, 1)
})

test("PC-T3 play→pause→play preserves position and does not re-download", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.audioCtx.emitCanplay(180)
  h.audioCtx.emitTimeUpdate(42, 180) // 播放到 42s
  h.controller.pause()

  const state = await h.controller.play(URL_A)
  assert.equal(state.playing, true)
  assert.equal(state.currentTime, 42, "position preserved across pause/resume")
  assert.equal(h.downloadCount, 1, "resume must not re-download")
  assert.equal(h.audioCtx.playCount, 2)
})

test("PC-T4 fast double play triggers exactly one download", async () => {
  const h = makeHarness({ gated: true })
  const p1 = h.controller.play(URL_A)
  const p2 = h.controller.play(URL_A) // 下载未完成时的第二次快速点击
  h.releaseDownload()
  await Promise.all([p1, p2])
  assert.equal(h.downloadCount, 1, "duplicate fast play must share one download")
})

test("PC-T5 only one audio context is ever created", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.controller.pause()
  await h.controller.play(URL_A)
  h.controller.pause()
  await h.controller.play(URL_A)
  assert.equal(h.contextCount, 1, "controller must own a single InnerAudioContext")
})

// ===== PC-T6 ~ PC-T10：Seek =====

test("PC-T6 seek 0% jumps to start", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.audioCtx.emitCanplay(180)
  assert.equal(h.controller.seek(0), true)
  assert.deepEqual(h.audioCtx.seeks, [0])
})

test("PC-T7 seek 50% jumps to half duration", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.audioCtx.emitCanplay(180)
  assert.equal(h.controller.seek(0.5), true)
  assert.deepEqual(h.audioCtx.seeks, [90])
})

test("PC-T8 seek 100% jumps to full duration", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.audioCtx.emitCanplay(180)
  assert.equal(h.controller.seek(1), true)
  assert.deepEqual(h.audioCtx.seeks, [180])
})

test("PC-T9 seek clamps negative and out-of-range ratios", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.audioCtx.emitCanplay(180)
  assert.equal(h.controller.seek(-0.5), true)
  assert.equal(h.controller.seek(1.8), true)
  assert.deepEqual(h.audioCtx.seeks, [0, 180], "negative→0, >1→duration")
})

test("PC-T10 invalid or missing duration blocks seek", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  // duration 仍为 0（未收到 canplay）
  assert.equal(h.controller.seek(0.5), false, "missing duration must block seek")
  // 非法 duration
  h.audioCtx.duration = Number.NaN
  assert.equal(h.controller.seek(0.5), false, "NaN duration must block seek")
  h.audioCtx.duration = -10
  assert.equal(h.controller.seek(0.5), false, "negative duration must block seek")
  assert.deepEqual(h.audioCtx.seeks, [], "no seek should be issued")
})

// ===== PC-T11 ~ PC-T15：事件 / 生命周期 =====

test("PC-T11 onEnded sets non-playing", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  assert.equal(h.controller.isPlaying(), true)
  h.audioCtx.emitEnded()
  assert.equal(h.controller.isPlaying(), false)
  assert.equal(h.controller.getState().state, PLAYER_STATE.PAUSED)
})

test("PC-T12 onHide pauses audio", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  const state = h.controller.handleHide()
  assert.equal(state.playing, false)
  assert.equal(h.audioCtx.pauseCount, 1)
  assert.equal(h.audioCtx.destroyCount, 0, "hide must not destroy the context")
})

test("PC-T13 dispose destroys exactly once", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.controller.dispose()
  h.controller.dispose()
  h.controller.dispose()
  assert.equal(h.audioCtx.destroyCount, 1, "destroy must run exactly once")
  assert.equal(h.controller.getState().disposed, true)
})

test("PC-T14 audio error is surfaced", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.audioCtx.emitError({ code: "AUDIO_DECODE_FAILED" })
  assert.equal(h.controller.isPlaying(), false, "error must stop playing state")
  assert.equal(h.errors.length, 1, "error must be surfaced to the caller")
  assert.equal(h.controller.getState().state, PLAYER_STATE.ERROR)
})

test("PC-T15 no auto-resume after hide/show", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  h.controller.handleHide()
  const playCountAfterHide = h.audioCtx.playCount
  h.controller.handleShow()
  assert.equal(h.controller.isPlaying(), false, "show must not auto-resume playback")
  assert.equal(h.audioCtx.playCount, playCountAfterHide, "show must not call play")
  assert.equal(h.downloadCount, 1, "show must not trigger any download")
})

// ===== 补充：lane 禁止项（autoplay / 持久缓存）与运行时时长口径 =====

test("PC-extra: creating controller does not autoplay", () => {
  const h = makeHarness()
  assert.equal(h.controller.isPlaying(), false)
  assert.equal(h.audioCtx.playCount, 0)
  assert.equal(h.downloadCount, 0)
})

test("PC-extra: duration is reported from runtime audio only", async () => {
  const h = makeHarness()
  await h.controller.play(URL_A)
  assert.equal(h.controller.getState().duration, 0, "no invented duration before canplay")
  h.audioCtx.emitCanplay(123.5)
  assert.equal(h.controller.getState().duration, 123.5, "runtime duration reported as-is")
})
