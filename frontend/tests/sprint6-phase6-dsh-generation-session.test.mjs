// Sprint 6 Phase 6 — DSH generation-session state machine (P6-D2/D3/D7/D8).
//
// Pure unit tests: no network, no uni, no DOM. Every side effect is injected, and time is a manual
// clock, so polling/backoff/hide-show behaviour is deterministic.

import assert from "node:assert/strict"
import test from "node:test"

import {
  GENERATION_FALLBACK_POLICY,
  GENERATION_STATES,
  MUSIC_SOURCE_LABELS,
  UNKNOWN_FAILURE_COPY,
  classifyMusicTask,
  createMusicGenerationSession,
  failureCopyFor,
  isKnownTaskStatus,
  playableAssetOf,
  retryKindForState,
  stateAfterTask,
  terminalCopyFor,
} from "../common/music-generation-session.js"

const TASK_ID = "mtask_p6"

function asset(overrides = {}) {
  return Object.assign(
    {
      music_ref: { music_id: "asset_p6", source_type: "generated" },
      title: "生成音频 60 BPM",
      stream_url: "/api/v3/music/assets/asset_p6/stream",
      duration_seconds: 187,
      format: "mp3",
      checksum: "sha256:p6",
      tone_profile: { regulation_mode: "personalized_five_tone", primary_tone: "jiao" },
      bpm: 60,
      instruments: ["guqin"],
    },
    overrides,
  )
}

function task(status, overrides = {}) {
  return Object.assign(
    {
      task_id: TASK_ID,
      status,
      message: "",
      progress: null,
      poll_after_ms: status === "queued" || status === "running" ? 2000 : null,
      fallback: { applied: false, reason_code: null },
      error_code: null,
      audio_asset: null,
    },
    overrides,
  )
}

function createClock() {
  let now = 0
  let seq = 0
  const timers = []
  return {
    setTimer(fn, ms) {
      const handle = { id: (seq += 1), at: now + Math.max(0, Number(ms) || 0), fn, cancelled: false }
      timers.push(handle)
      return handle
    },
    clearTimer(handle) {
      if (handle) handle.cancelled = true
    },
    pending() {
      return timers.filter((t) => !t.cancelled).length
    },
    async advance(ms) {
      now += Math.max(0, Number(ms) || 0)
      for (;;) {
        const due = timers
          .filter((t) => !t.cancelled && t.at <= now)
          .sort((a, b) => a.at - b.at || a.id - b.id)
        if (!due.length) break
        const next = due[0]
        next.cancelled = true
        await next.fn()
        await new Promise((resolve) => setImmediate(resolve))
      }
      return now
    },
  }
}

function createFakeApi(script = {}) {
  const calls = { start: [], sync: [], cancel: [] }
  const queue = Array.isArray(script.sync) ? script.sync.slice() : []
  const control = {
    start: script.start || (({ requestId }) => Promise.resolve(task("queued"))),
    sync:
      script.sync ||
      (() => {
        const next = queue.length ? queue.shift() : task("running")
        if (next instanceof Error) return Promise.reject(next)
        return Promise.resolve(next)
      }),
    cancel: script.cancel || (() => Promise.resolve(task("cancelled"))),
  }
  return {
    calls,
    pushSync(entry) {
      queue.push(entry)
    },
    api: {
      startGeneration(payload) {
        calls.start.push(payload)
        return control.start(payload, calls.start.length)
      },
      syncTask(taskId) {
        calls.sync.push(taskId)
        return control.sync(taskId, calls.sync.length)
      },
      cancelTask(taskId) {
        calls.cancel.push(taskId)
        return control.cancel(taskId, calls.cancel.length)
      },
    },
  }
}

function makeSession(fake, extra = {}) {
  const clock = createClock()
  let keySeq = 0
  const session = createMusicGenerationSession(
    Object.assign(
      {
        api: fake.api,
        setTimer: clock.setTimer,
        clearTimer: clock.clearTimer,
        newRequestKey: () => `music_req_${(keySeq += 1)}`,
        pollIntervalMs: 2000,
      },
      extra,
    ),
  )
  return { session, clock }
}

// ---------------------------------------------------------------------------- classification

test("classify: only backend statuses are known; unknown bodies are not outcomes", () => {
  assert.equal(isKnownTaskStatus("running"), true)
  assert.equal(isKnownTaskStatus("failed"), true)
  assert.equal(isKnownTaskStatus("weird"), false)
  assert.equal(isKnownTaskStatus(undefined), false)
  assert.equal(classifyMusicTask(task("weird")).known, false)
  assert.equal(stateAfterTask(task("weird")), null)
  assert.equal(stateAfterTask(task("failed", { error_code: "GENERATION_PROVIDER_REJECTED" })), GENERATION_STATES.FAILED)
})

test("classify: playable requires a real asset id and stream path", () => {
  assert.equal(playableAssetOf(task("succeeded")), null)
  assert.equal(classifyMusicTask(task("succeeded")).assetMissing, true)
  const ok = classifyMusicTask(task("succeeded", { audio_asset: asset() }))
  assert.equal(ok.playable, true)
  assert.equal(ok.measuredDurationSeconds, 187) // P6-D7: the asset's measured duration
  const noPath = classifyMusicTask(
    task("succeeded", { audio_asset: asset({ stream_url: "" }) }),
  )
  assert.equal(noPath.playable, false)
  assert.equal(noPath.assetMissing, true)
})

test("failure copy is honest and never says cancelled", () => {
  const codes = [
    "GENERATION_PROVIDER_UNAVAILABLE",
    "GENERATION_PROVIDER_TIMEOUT",
    "GENERATION_PROVIDER_RATE_LIMITED",
    "GENERATION_PROVIDER_AUTH_FAILED",
    "GENERATION_PROVIDER_REJECTED",
  ]
  const copies = new Set()
  for (const code of codes) {
    const copy = failureCopyFor(code)
    copies.add(copy)
    assert.ok(copy.length > 0)
    assert.doesNotMatch(copy, /取消/)
  }
  assert.equal(copies.size, codes.length, "each public failure code keeps its own copy")
  assert.equal(failureCopyFor("PROVIDER_NOT_CONFIGURED"), UNKNOWN_FAILURE_COPY)

  const failed = terminalCopyFor(task("failed", { error_code: "GENERATION_PROVIDER_RATE_LIMITED" }))
  assert.equal(failed, failureCopyFor("GENERATION_PROVIDER_RATE_LIMITED"))
  assert.doesNotMatch(failed, /取消/)
  assert.match(terminalCopyFor(task("cancelled")), /取消/)
  assert.doesNotMatch(
    terminalCopyFor(task("failed", { error_code: "GENERATION_PROVIDER_REJECTED" })),
    /取消/,
  )
})

test("fallback is labelled, never presented as a plain success (P6-D3)", () => {
  assert.equal(GENERATION_FALLBACK_POLICY.fallback, "none")
  const matched = task("matched_fallback", {
    audio_asset: asset({ music_ref: { music_id: "asset_matched", source_type: "matched" } }),
    fallback: { applied: true, reason_code: "GENERATION_PROVIDER_UNAVAILABLE" },
  })
  const view = classifyMusicTask(matched)
  assert.equal(view.fallbackApplied, true)
  assert.equal(view.sourceLabel, MUSIC_SOURCE_LABELS.matched)
  assert.match(terminalCopyFor(matched), /审核曲库/)
  assert.equal(stateAfterTask(matched), GENERATION_STATES.MATCHED_FALLBACK)
})

test("retry policy: terminal failure pays again, sync problems only resume", () => {
  assert.equal(retryKindForState(GENERATION_STATES.FAILED), "new_paid_attempt")
  assert.equal(retryKindForState(GENERATION_STATES.CANCELLED), "new_paid_attempt")
  assert.equal(retryKindForState(GENERATION_STATES.SYNC_ERROR), "resume")
  assert.equal(retryKindForState(GENERATION_STATES.PLAYABLE), "none")
  assert.equal(retryKindForState(GENERATION_STATES.CREATING), "none")
})

// ---------------------------------------------------------------------------- double tap

test("double tap issues exactly one POST and one task identity", async () => {
  let release
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const fake = createFakeApi({
    start: async ({ requestId }) => {
      await gate
      return task("queued", { request_id: requestId })
    },
  })
  const { session } = makeSession(fake)

  const first = session.ensureGeneration()
  const second = session.ensureGeneration()
  const third = session.ensureGeneration()
  assert.equal(first, second, "the in-flight POST promise is shared")
  assert.equal(second, third, "the in-flight POST promise is shared")
  await Promise.resolve()
  assert.equal(fake.calls.start.length, 1, "the in-flight POST is issued once, not repeated")
  release()
  await Promise.all([first, second, third])

  assert.equal(fake.calls.start.length, 1)
  assert.equal(session.snapshot().state, GENERATION_STATES.QUEUED)
  assert.equal(session.snapshot().taskId, TASK_ID)
})

test("a second tap after the task exists resumes instead of re-creating it (P6-D2)", async () => {
  const fake = createFakeApi({ sync: () => Promise.resolve(task("running")) })
  const { session, clock } = makeSession(fake)

  await session.ensureGeneration()
  assert.equal(fake.calls.start.length, 1)
  const state = session.snapshot().state
  assert.equal(state, GENERATION_STATES.QUEUED)

  await clock.advance(2000)
  assert.equal(fake.calls.sync.length, 1)
  assert.equal(session.snapshot().state, GENERATION_STATES.RUNNING)

  await session.ensureGeneration() // user taps again while it is still generating
  assert.equal(fake.calls.start.length, 1, "no second paid generation")
})

// ---------------------------------------------------------------------------- resume + polling

test("a stored running task resumes with zero POSTs", async () => {
  const fake = createFakeApi({ sync: () => Promise.resolve(task("running")) })
  const { session } = makeSession(fake)

  session.hydrate(TASK_ID, "running")
  await session.resume()

  assert.equal(fake.calls.start.length, 0)
  assert.equal(fake.calls.sync.length, 1)
  assert.equal(session.snapshot().state, GENERATION_STATES.RUNNING)
})

test("polling follows the interval from each response and stops at a terminal state", async () => {
  const fake = createFakeApi({
    sync: () => {
      const queued = task("queued", { poll_after_ms: 1500 })
      const done = task("succeeded", { audio_asset: asset() })
      return Promise.resolve(fake.calls.sync.length === 1 ? queued : done)
    },
  })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()

  await clock.advance(2000)
  assert.equal(fake.calls.sync.length, 1)
  assert.equal(session.snapshot().state, GENERATION_STATES.QUEUED)
  assert.equal(clock.pending(), 1)

  await clock.advance(1500) // the second response asked for 1500 ms, not the original 2000
  assert.equal(fake.calls.sync.length, 2)
  assert.equal(session.snapshot().state, GENERATION_STATES.PLAYABLE)
  assert.equal(clock.pending(), 0, "no further polling after a terminal state")
  assert.equal(session.snapshot().asset.duration_seconds, 187)
})

test("overlapping ticks cannot double-request the same task", async () => {
  let release
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const fake = createFakeApi({
    sync: async () => {
      await gate
      return task("running")
    },
  })
  const { session, clock } = makeSession(fake)
  session.hydrate(TASK_ID, "running")

  const a = session.resume()
  const b = session.onShow()
  const c = session.resume()
  assert.equal(a, b, "concurrent syncs share one request")
  assert.equal(b, c, "concurrent syncs share one request")
  await Promise.resolve()
  assert.equal(fake.calls.sync.length, 1, "concurrent syncs share one request")
  release()
  await Promise.all([a, b, c])
  assert.equal(fake.calls.sync.length, 1)
  await clock.advance(10000)
  assert.ok(fake.calls.sync.length >= 2)
})

// ---------------------------------------------------------------------------- failures

test("a transient poll failure keeps identity, is never terminal, and recovers", async () => {
  const networking = Object.assign(new Error("网络连接失败，请检查网络后重试。"), { code: "NETWORK_ERROR" })
  const fake = createFakeApi({
    sync: () => {
      if (fake.calls.sync.length === 1) return Promise.reject(networking)
      return Promise.resolve(task("succeeded", { audio_asset: asset() }))
    },
  })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()

  await clock.advance(2000)
  const broken = session.snapshot()
  assert.equal(broken.state, GENERATION_STATES.SYNC_ERROR)
  assert.equal(broken.taskId, TASK_ID, "identity retained")
  assert.notEqual(broken.state, GENERATION_STATES.FAILED, "a network blip is not a terminal failure")
  assert.equal(fake.calls.start.length, 1, "no new paid generation")
  assert.equal(broken.retryKind, "resume")

  await clock.advance(2000) // backoff retry succeeds
  assert.equal(session.snapshot().state, GENERATION_STATES.PLAYABLE)
})

test("repeated sync errors back off and stall without ever declaring failure", async () => {
  const fake = createFakeApi({ sync: () => Promise.reject(new Error("boom")) })
  const { session, clock } = makeSession(fake, { maxConsecutiveSyncErrors: 3 })
  await session.ensureGeneration()

  await clock.advance(2000)
  assert.equal(session.snapshot().syncAttempts, 1)
  await clock.advance(2000)
  assert.equal(session.snapshot().syncAttempts, 2)
  await clock.advance(4000)
  assert.equal(session.snapshot().syncAttempts, 3)
  assert.equal(session.snapshot().syncStalled, true)
  assert.equal(session.snapshot().state, GENERATION_STATES.SYNC_ERROR)
  assert.notEqual(session.snapshot().state, GENERATION_STATES.FAILED)
  assert.equal(fake.calls.start.length, 1)
})

test("a terminal failed task is shown as a failure with its code copy, never as cancelled", async () => {
  const fake = createFakeApi({
    sync: () => Promise.resolve(task("failed", { error_code: "GENERATION_PROVIDER_AUTH_FAILED" })),
  })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  await clock.advance(2000)

  const snap = session.snapshot()
  assert.equal(snap.state, GENERATION_STATES.FAILED)
  assert.equal(snap.errorCode, "GENERATION_PROVIDER_AUTH_FAILED")
  assert.equal(snap.copy, failureCopyFor("GENERATION_PROVIDER_AUTH_FAILED"))
  assert.doesNotMatch(snap.copy, /取消/)
  assert.equal(snap.playable, false)
  assert.equal(snap.retryKind, "new_paid_attempt")
  assert.equal(clock.pending(), 0)
})

test("retry after a terminal failure is an explicit new paid attempt with a fresh key", async () => {
  const fake = createFakeApi({
    sync: () => Promise.resolve(task("failed", { error_code: "GENERATION_PROVIDER_REJECTED" })),
  })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  await clock.advance(2000)
  assert.equal(session.snapshot().state, GENERATION_STATES.FAILED)
  const firstRequestId = fake.calls.start[0].requestId

  await session.retry()
  assert.equal(fake.calls.start.length, 2, "a terminal retry is a new paid generation")
  assert.notEqual(fake.calls.start[1].requestId, firstRequestId, "a new request id → a new idempotency key")
})

test("retry from a sync problem resumes the same task and never pays twice", async () => {
  const fake = createFakeApi({ sync: () => Promise.reject(new Error("offline")) })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  await clock.advance(2000)
  assert.equal(session.snapshot().state, GENERATION_STATES.SYNC_ERROR)

  await session.retry()
  assert.equal(fake.calls.start.length, 1, "resume only")
  assert.ok(fake.calls.sync.length >= 2)
})

test("a POST failure keeps the request id so the retry replays one idempotency key", async () => {
  const fake = createFakeApi({
    start: () => Promise.reject(Object.assign(new Error("服务暂时不可用"), { code: "GENERATION_NOT_ALLOWED" })),
  })
  const { session } = makeSession(fake)
  await session.ensureGeneration()
  assert.equal(session.snapshot().state, GENERATION_STATES.SYNC_ERROR)
  assert.equal(session.snapshot().errorCode, "GENERATION_NOT_ALLOWED")

  await session.retry()
  assert.equal(fake.calls.start.length, 2)
  assert.equal(
    fake.calls.start[1].requestId,
    fake.calls.start[0].requestId,
    "same request id → same idempotency key, so the backend can replay instead of double-billing",
  )
})

test("cancel is only reported when the backend accepts it", async () => {
  const fake = createFakeApi({
    sync: () => Promise.resolve(task("running")),
    cancel: () => Promise.reject(new Error("当前生成服务不支持取消任务。")),
  })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  await clock.advance(2000)
  assert.equal(session.snapshot().state, GENERATION_STATES.RUNNING)

  await session.cancel()
  assert.equal(session.snapshot().state, GENERATION_STATES.SYNC_ERROR)
  assert.notEqual(session.snapshot().state, GENERATION_STATES.CANCELLED)
  assert.equal(session.snapshot().taskId, TASK_ID)

  const ok = createFakeApi({
    sync: () => Promise.resolve(task("running")),
    cancel: () => Promise.resolve(task("cancelled")),
  })
  const second = makeSession(ok)
  await second.session.ensureGeneration()
  await second.clock.advance(2000)
  await second.session.cancel()
  assert.equal(second.session.snapshot().state, GENERATION_STATES.CANCELLED)
})

// ---------------------------------------------------------------------------- lifecycle

test("onHide stops polling and onShow resumes sync only (P6-D8)", async () => {
  const fake = createFakeApi({ sync: () => Promise.resolve(task("running")) })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  await clock.advance(2000)
  const syncsBeforeHide = fake.calls.sync.length

  session.onHide()
  assert.equal(clock.pending(), 0, "no timer survives a hide")
  await clock.advance(60000)
  assert.equal(fake.calls.sync.length, syncsBeforeHide, "hidden sessions do not poll")

  await session.onShow()
  assert.equal(fake.calls.sync.length, syncsBeforeHide + 1)
  assert.equal(fake.calls.start.length, 1, "returning to the foreground never starts generation")
})

test("onShow on a terminal session neither polls nor creates", async () => {
  const fake = createFakeApi({ sync: () => Promise.resolve(task("succeeded", { audio_asset: asset() })) })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  await clock.advance(2000)
  assert.equal(session.snapshot().state, GENERATION_STATES.PLAYABLE)

  session.onHide()
  await session.onShow()
  await clock.advance(60000)
  assert.equal(fake.calls.sync.length, 1)
  assert.equal(fake.calls.start.length, 1)
  assert.equal(session.snapshot().state, GENERATION_STATES.PLAYABLE)
})

test("dispose stops all timers and further work", async () => {
  const fake = createFakeApi({ sync: () => Promise.resolve(task("running")) })
  const { session, clock } = makeSession(fake)
  await session.ensureGeneration()
  session.dispose()
  assert.equal(clock.pending(), 0)
  await clock.advance(60000)
  assert.equal(fake.calls.sync.length, 0)
  assert.equal(fake.calls.start.length, 1)
})

test("a sync response for a different task cannot hijack the session identity", async () => {
  const fake = createFakeApi({
    sync: () => Promise.resolve(task("succeeded", { task_id: "mtask_other", audio_asset: asset() })),
  })
  const { session, clock } = makeSession(fake)
  session.hydrate(TASK_ID, "running")
  await session.resume()
  assert.equal(session.snapshot().taskId, TASK_ID)
  assert.equal(session.snapshot().state, GENERATION_STATES.SYNC_ERROR)
  assert.notEqual(session.snapshot().state, GENERATION_STATES.PLAYABLE)
  await clock.advance(60000)
})

test("subscribers see every transition and the snapshot is never a fabricated success", async () => {
  const seen = []
  const fake = createFakeApi({
    sync: () => {
      if (fake.calls.sync.length === 1) return Promise.resolve(task("weird"))
      return Promise.resolve(task("succeeded", { audio_asset: asset() }))
    },
  })
  const { session, clock } = makeSession(fake)
  const unsubscribe = session.subscribe((snap) => seen.push({ state: snap.state, playable: snap.playable }))
  session.ready()
  await session.ensureGeneration()
  await clock.advance(2000)
  assert.equal(seen[seen.length - 1].state, GENERATION_STATES.SYNC_ERROR)
  assert.equal(seen[seen.length - 1].playable, false)

  await clock.advance(2000)
  assert.equal(seen[seen.length - 1].state, GENERATION_STATES.PLAYABLE)
  assert.equal(seen[seen.length - 1].playable, true)
  assert.ok(seen.length >= 5)
  unsubscribe()
})
