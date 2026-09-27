import assert from "node:assert/strict"
import test from "node:test"

import {
  MUSIC_GENERATION_FLOW_PHASES,
  createMusicGenerationFlow,
} from "../common/music-generation-flow.js"
import {
  GENERATION_STATES,
  createMusicGenerationSession,
} from "../common/music-generation-session.js"

const playableTask = (overrides = {}) => ({
  task_id: "task_phase_d",
  status: "succeeded",
  message: "完成",
  poll_after_ms: null,
  fallback: { applied: false, reason_code: null },
  error_code: null,
  audio_asset: {
    music_ref: { music_id: "music_phase_d", source_type: "generated" },
    stream_url: "/api/v3/music/assets/music_phase_d/stream",
    title: "测试音乐",
    duration_seconds: 180,
  },
  ...overrides,
})

const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

function sessionFactory(options = {}) {
  return createMusicGenerationSession({
    ...options,
    setTimer: () => 1,
    clearTimer: () => {},
    newRequestKey: () => "request_phase_d",
  })
}

test("PR-024: start ensures preparation once and rapid double-start creates one task", async () => {
  const preparation = deferred()
  let ensureCalls = 0
  let startCalls = 0
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: () => {
        ensureCalls += 1
        return preparation.promise
      },
      startGeneration: async () => {
        startCalls += 1
        return playableTask()
      },
      syncTask: async () => playableTask(),
      cancelTask: async () => playableTask({ status: "cancelled", audio_asset: null }),
    },
    createSession: sessionFactory,
  })

  const first = flow.start()
  const second = flow.start()
  assert.equal(first, second, "double start must share one logical operation")
  assert.equal(flow.snapshot().phase, MUSIC_GENERATION_FLOW_PHASES.PREPARING)

  preparation.resolve({ generation: { status: "ready" } })
  await first

  assert.equal(ensureCalls, 1)
  assert.equal(startCalls, 1)
  assert.equal(flow.snapshot().phase, MUSIC_GENERATION_FLOW_PHASES.PLAYABLE)
  assert.equal(flow.snapshot().session.state, GENERATION_STATES.PLAYABLE)
  assert.equal(flow.snapshot().asset.music_ref.music_id, "music_phase_d")
})

test("preparation failure is retryable before a task exists", async () => {
  let attempts = 0
  let startCalls = 0
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: async () => {
        attempts += 1
        if (attempts === 1) throw Object.assign(new Error("暂时无法准备音乐"), { code: "PREPARE_FAILED" })
        return { generation: { status: "ready" } }
      },
      startGeneration: async () => {
        startCalls += 1
        return playableTask()
      },
      syncTask: async () => playableTask(),
      cancelTask: async () => null,
    },
    createSession: sessionFactory,
  })

  await flow.start()
  assert.equal(flow.snapshot().phase, MUSIC_GENERATION_FLOW_PHASES.FAILED)
  assert.equal(flow.snapshot().taskId, null)
  assert.equal(startCalls, 0)

  await flow.retry()
  assert.equal(attempts, 2)
  assert.equal(startCalls, 1)
  assert.equal(flow.snapshot().phase, MUSIC_GENERATION_FLOW_PHASES.PLAYABLE)
})

test("retry and cancel delegate to the session after task lifecycle starts", async () => {
  const calls = { retry: 0, cancel: 0 }
  let listener = () => {}
  const task = { task_id: "task_owned_by_session", status: "failed", error_code: "GENERATION_PROVIDER_TIMEOUT" }
  const fakeSession = {
    snapshot: () => ({ state: GENERATION_STATES.FAILED, taskId: task.task_id, task, asset: null, copy: "失败", playable: false }),
    subscribe(fn) { listener = fn; fn(this.snapshot()); return () => {} },
    ready() {},
    ensureGeneration: async () => { listener(this.snapshot()); return this.snapshot() },
    retry: async () => { calls.retry += 1; return fakeSession.snapshot() },
    cancel: async () => { calls.cancel += 1; return fakeSession.snapshot() },
    onHide() {},
    onShow: async () => fakeSession.snapshot(),
    dispose() {},
  }
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: async () => ({}),
      startGeneration: async () => task,
      syncTask: async () => task,
    },
    createSession: () => fakeSession,
  })

  await flow.start()
  await flow.retry()
  await flow.cancel()
  assert.deepEqual(calls, { retry: 1, cancel: 1 })
})

test("persisted task re-entry resumes exactly that task and does not prepare or create", async () => {
  let ensureCalls = 0
  let startCalls = 0
  let syncCalls = 0
  const persisted = { task_id: "task_persisted", status: "running" }
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => persisted,
      ensureMusicBasis: async () => { ensureCalls += 1 },
      startGeneration: async () => { startCalls += 1; return playableTask() },
      syncTask: async (taskId) => {
        syncCalls += 1
        assert.equal(taskId, persisted.task_id)
        return playableTask({ task_id: persisted.task_id })
      },
      cancelTask: async () => null,
    },
    createSession: sessionFactory,
  })

  await flow.start()
  assert.equal(ensureCalls, 0)
  assert.equal(startCalls, 0)
  assert.equal(syncCalls, 1)
  assert.equal(flow.snapshot().taskId, persisted.task_id)
  assert.equal(flow.snapshot().phase, MUSIC_GENERATION_FLOW_PHASES.PLAYABLE)
})

test("dispose during preparation ignores stale completion and never creates a task", async () => {
  const preparation = deferred()
  let startCalls = 0
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: () => preparation.promise,
      startGeneration: async () => { startCalls += 1; return playableTask() },
      syncTask: async () => playableTask(),
    },
    createSession: sessionFactory,
  })

  const pending = flow.start()
  flow.dispose()
  preparation.resolve({ generation: { status: "ready" } })
  await pending

  assert.equal(startCalls, 0)
  assert.equal(flow.snapshot().disposed, true)
})

test("D-R1: hidden pending preparation cannot start a task and show resumes exactly once", async () => {
  const preparation = deferred()
  let ensureCalls = 0
  let sessionCreations = 0
  let startCalls = 0
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: () => {
        ensureCalls += 1
        return preparation.promise
      },
      startGeneration: async () => {
        startCalls += 1
        return playableTask()
      },
      syncTask: async () => playableTask(),
      cancelTask: async () => null,
    },
    createSession(options) {
      sessionCreations += 1
      return sessionFactory(options)
    },
  })

  const pending = flow.start()
  while (ensureCalls === 0) await Promise.resolve()
  flow.onHide()
  preparation.resolve({ generation: { status: "ready" } })
  await pending

  assert.equal(ensureCalls, 1)
  assert.equal(startCalls, 0, "hidden preparation completion must not create a task")

  await flow.onShow()
  assert.equal(ensureCalls, 1, "show must reuse the completed preparation")
  assert.equal(sessionCreations, 1, "show must reuse the same session")
  assert.equal(startCalls, 1, "show resumes one logical task")
  assert.equal(flow.snapshot().taskId, "task_phase_d")
})

test("D-R1: hidden playable and failure snapshots are retained but not emitted until show", async () => {
  let sessionListener = () => {}
  let current = {
    state: GENERATION_STATES.RUNNING,
    taskId: "task_hidden",
    task: { task_id: "task_hidden", status: "running" },
    asset: null,
    copy: "生成",
    playable: false,
  }
  const fakeSession = {
    snapshot: () => current,
    subscribe(fn) { sessionListener = fn; fn(current); return () => {} },
    ready() {},
    ensureGeneration: async () => current,
    retry: async () => current,
    cancel: async () => current,
    onHide() {},
    onShow: async () => current,
    dispose() {},
  }
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: async () => ({}),
      startGeneration: async () => current.task,
      syncTask: async () => current.task,
    },
    createSession: () => fakeSession,
  })
  const observed = []
  flow.subscribe(value => observed.push(value.phase))
  await flow.start()

  flow.onHide()
  const beforeHiddenEvents = observed.length
  current = {
    state: GENERATION_STATES.PLAYABLE,
    taskId: "task_hidden",
    task: playableTask({ task_id: "task_hidden" }),
    asset: playableTask({ task_id: "task_hidden" }).audio_asset,
    copy: "完成",
    playable: true,
  }
  sessionListener(current)
  assert.equal(observed.length, beforeHiddenEvents, "hidden playable must not reach active-page listeners")

  await flow.onShow()
  assert.equal(observed.filter(phase => phase === MUSIC_GENERATION_FLOW_PHASES.PLAYABLE).length, 1)
  assert.equal(flow.snapshot().taskId, "task_hidden")

  flow.onHide()
  const beforeFailure = observed.length
  current = {
    state: GENERATION_STATES.FAILED,
    taskId: "task_hidden",
    task: { task_id: "task_hidden", status: "failed" },
    asset: null,
    copy: "失败",
    playable: false,
  }
  sessionListener(current)
  assert.equal(observed.length, beforeFailure, "hidden failure must not reach active-page listeners")

  await flow.onShow()
  assert.equal(observed.at(-1), MUSIC_GENERATION_FLOW_PHASES.FAILED)
})

test("D-R1: existing persisted task keeps its identity across hide and show", async () => {
  const calls = { starts: 0, syncs: 0 }
  const persisted = { task_id: "task_existing", status: "running" }
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => persisted,
      ensureMusicBasis: async () => ({}),
      startGeneration: async () => {
        calls.starts += 1
        return playableTask({ task_id: "task_replacement" })
      },
      syncTask: async taskId => {
        calls.syncs += 1
        assert.equal(taskId, persisted.task_id)
        return { task_id: persisted.task_id, status: "running" }
      },
      cancelTask: async () => null,
    },
    createSession: sessionFactory,
  })

  await flow.start()
  flow.onHide()
  await flow.onShow()

  assert.equal(flow.snapshot().taskId, persisted.task_id)
  assert.equal(calls.starts, 0)
  assert.equal(calls.syncs, 2, "show resumes the existing task instead of replacing it")
})

test("hide/show are delegated and session snapshots remain task-lifecycle authority", async () => {
  const calls = { hide: 0, show: 0 }
  let listener = () => {}
  const snapshots = {
    queued: { state: GENERATION_STATES.QUEUED, taskId: "task_q", task: { task_id: "task_q", status: "queued" }, asset: null, copy: "排队", playable: false },
    running: { state: GENERATION_STATES.RUNNING, taskId: "task_q", task: { task_id: "task_q", status: "running" }, asset: null, copy: "生成", playable: false },
  }
  const fakeSession = {
    snapshot: () => snapshots.queued,
    subscribe(fn) { listener = fn; fn(snapshots.queued); return () => {} },
    ready() {},
    ensureGeneration: async () => { listener(snapshots.running); return snapshots.running },
    retry: async () => snapshots.running,
    cancel: async () => snapshots.running,
    onHide() { calls.hide += 1 },
    onShow: async () => { calls.show += 1; return snapshots.running },
    dispose() {},
  }
  const flow = createMusicGenerationFlow({
    api: {
      findPersistedTask: async () => null,
      ensureMusicBasis: async () => ({}),
      startGeneration: async () => snapshots.queued.task,
      syncTask: async () => snapshots.running.task,
    },
    createSession: () => fakeSession,
  })

  await flow.start()
  assert.equal(flow.snapshot().phase, MUSIC_GENERATION_FLOW_PHASES.GENERATING)
  assert.equal(flow.snapshot().session.state, GENERATION_STATES.RUNNING)
  assert.equal(flow.snapshot().copy, "正在生成你的音乐……")
  flow.onHide()
  await flow.onShow()
  assert.deepEqual(calls, { hide: 1, show: 1 })
})

test("music-generation-session remains free of cross-stage preparation APIs", async () => {
  const { readFile } = await import("node:fs/promises")
  const source = await readFile(new URL("../common/music-generation-session.js", import.meta.url), "utf8")
  for (const forbidden of ["getMusicBasis", "ensureDiagnosis", "ensurePrescription", "ensureAssessment", "prepareGeneration"]) {
    assert.doesNotMatch(source, new RegExp(forbidden))
  }
})
