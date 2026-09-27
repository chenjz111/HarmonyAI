/**
 * Sprint 6 Product Recovery Phase D — cross-stage generation orchestration.
 *
 * This module owns preparation only. Generation task identity, request identity,
 * polling, retry, cancellation, re-entry and playable-task truth remain owned by
 * music-generation-session and are surfaced here without reinterpretation.
 */
import {
  GENERATION_STATES,
  createMusicGenerationSession,
} from "./music-generation-session.js"

export const MUSIC_GENERATION_FLOW_PHASES = Object.freeze({
  IDLE: "idle",
  PREPARING: "preparing",
  GENERATING: "generating",
  PLAYABLE: "playable",
  FAILED: "failed",
  CANCELLED: "cancelled",
})

const PREPARING_COPY = "正在准备你的音乐"
const GENERATING_COPY = "正在生成你的音乐……"
const PREPARATION_FAILED_COPY = "暂时无法准备音乐，请稍后重试。"
const SYNC_FAILED_COPY = "暂时无法同步音乐状态，请稍后重试。"
const CANCELLED_COPY = "已取消生成。"

function isMissingTask(error) {
  return !!error && (error.code === "NOT_FOUND" || error.statusCode === 404 || error.status === 404)
}

function phaseForSession(snapshot) {
  if (!snapshot) return null
  if (
    snapshot.state === GENERATION_STATES.PLAYABLE ||
    snapshot.state === GENERATION_STATES.MATCHED_FALLBACK
  ) {
    return snapshot.playable && snapshot.asset
      ? MUSIC_GENERATION_FLOW_PHASES.PLAYABLE
      : MUSIC_GENERATION_FLOW_PHASES.FAILED
  }
  if (snapshot.state === GENERATION_STATES.CANCELLED) return MUSIC_GENERATION_FLOW_PHASES.CANCELLED
  if (
    snapshot.state === GENERATION_STATES.FAILED ||
    snapshot.state === GENERATION_STATES.SYNC_ERROR
  ) return MUSIC_GENERATION_FLOW_PHASES.FAILED
  if (
    snapshot.state === GENERATION_STATES.CREATING ||
    snapshot.state === GENERATION_STATES.QUEUED ||
    snapshot.state === GENERATION_STATES.RUNNING
  ) return MUSIC_GENERATION_FLOW_PHASES.GENERATING
  return null
}

export function createMusicGenerationFlow(options = {}) {
  const api = options.api || {}
  if (typeof api.ensureMusicBasis !== "function") {
    throw new TypeError("createMusicGenerationFlow requires api.ensureMusicBasis")
  }
  if (typeof api.startGeneration !== "function" || typeof api.syncTask !== "function") {
    throw new TypeError("createMusicGenerationFlow requires generation task operations")
  }

  const makeSession = typeof options.createSession === "function"
    ? options.createSession
    : createMusicGenerationSession
  const listeners = new Set()
  if (typeof options.onChange === "function") listeners.add(options.onChange)

  const internal = {
    phase: MUSIC_GENERATION_FLOW_PHASES.IDLE,
    basis: null,
    session: null,
    copy: "",
    preparationErrorCode: null,
    disposed: false,
  }

  let session = null
  let unsubscribe = null
  let startInFlight = null
  let operationToken = 0
  let sessionLifecycleStarted = false
  let foreground = true

  function snapshot() {
    const sessionSnapshot = internal.session
    return {
      phase: internal.phase,
      basis: internal.basis,
      session: sessionSnapshot,
      taskId: sessionSnapshot ? sessionSnapshot.taskId || null : null,
      task: sessionSnapshot ? sessionSnapshot.task || null : null,
      asset: sessionSnapshot ? sessionSnapshot.asset || null : null,
      copy: internal.copy,
      preparationErrorCode: internal.preparationErrorCode,
      canRetry: internal.phase === MUSIC_GENERATION_FLOW_PHASES.FAILED,
      canCancel: !!(sessionSnapshot && sessionSnapshot.taskId) &&
        internal.phase === MUSIC_GENERATION_FLOW_PHASES.GENERATING,
      disposed: internal.disposed,
    }
  }

  function emit() {
    const value = snapshot()
    if (!foreground) return value
    for (const listener of listeners) {
      try { listener(value) } catch (e) { /* listeners cannot break orchestration */ }
    }
    return value
  }

  function applySessionSnapshot(next) {
    if (internal.disposed) return snapshot()
    internal.session = next || null
    const phase = phaseForSession(next)
    if (!phase) return snapshot()
    internal.phase = phase
    if (phase === MUSIC_GENERATION_FLOW_PHASES.GENERATING) {
      internal.copy = GENERATING_COPY
    } else if (next && next.state === GENERATION_STATES.SYNC_ERROR) {
      internal.copy = SYNC_FAILED_COPY
    } else if (phase === MUSIC_GENERATION_FLOW_PHASES.CANCELLED) {
      internal.copy = CANCELLED_COPY
    } else {
      internal.copy = (next && next.copy) || internal.copy
    }
    return emit()
  }

  function connectSession() {
    if (session) return session
    session = makeSession({
      api: {
        startGeneration: api.startGeneration,
        syncTask: api.syncTask,
        cancelTask: api.cancelTask,
      },
    })
    unsubscribe = session.subscribe(applySessionSnapshot)
    return session
  }

  async function findPersistedTask() {
    if (typeof api.findPersistedTask !== "function") return null
    try {
      return await api.findPersistedTask()
    } catch (error) {
      if (isMissingTask(error)) return null
      throw error
    }
  }

  async function runStart(token) {
    internal.phase = MUSIC_GENERATION_FLOW_PHASES.PREPARING
    internal.copy = PREPARING_COPY
    internal.preparationErrorCode = null
    emit()

    try {
      const persistedTask = await findPersistedTask()
      if (internal.disposed || token !== operationToken || !foreground) return snapshot()

      const currentSession = connectSession()
      if (persistedTask && persistedTask.task_id) {
        sessionLifecycleStarted = true
        currentSession.hydrate(persistedTask.task_id, persistedTask.status)
        internal.phase = MUSIC_GENERATION_FLOW_PHASES.GENERATING
        internal.copy = GENERATING_COPY
        emit()
        await currentSession.resume()
        return snapshot()
      }

      if (!internal.basis) internal.basis = await api.ensureMusicBasis()
      if (internal.disposed || token !== operationToken || !foreground) return snapshot()

      currentSession.ready()
      sessionLifecycleStarted = true
      internal.phase = MUSIC_GENERATION_FLOW_PHASES.GENERATING
      internal.copy = GENERATING_COPY
      emit()
      await currentSession.ensureGeneration()
      return snapshot()
    } catch (error) {
      if (internal.disposed || token !== operationToken || !foreground) return snapshot()
      // Once task lifecycle has started, the session owns all task failures and retries.
      if (sessionLifecycleStarted && session) return snapshot()
      internal.phase = MUSIC_GENERATION_FLOW_PHASES.FAILED
      internal.copy = PREPARATION_FAILED_COPY
      internal.preparationErrorCode = (error && error.code) || "PREPARATION_FAILED"
      return emit()
    }
  }

  const flow = {
    snapshot,
    subscribe(listener) {
      listeners.add(listener)
      listener(snapshot())
      return () => listeners.delete(listener)
    },
    start() {
      if (internal.disposed || !foreground) return Promise.resolve(snapshot())
      if (startInFlight) return startInFlight
      if (sessionLifecycleStarted && session) return Promise.resolve(snapshot())
      const token = ++operationToken
      startInFlight = runStart(token).finally(() => {
        if (token === operationToken) startInFlight = null
      })
      return startInFlight
    },
    retry() {
      if (internal.disposed) return Promise.resolve(snapshot())
      if (sessionLifecycleStarted && session) return session.retry()
      return flow.start()
    },
    cancel() {
      if (internal.disposed || !sessionLifecycleStarted || !session) {
        return Promise.resolve(snapshot())
      }
      return session.cancel()
    },
    onHide() {
      foreground = false
      if (session) session.onHide()
      return snapshot()
    },
    async onShow() {
      if (internal.disposed) return snapshot()
      foreground = true
      if (!sessionLifecycleStarted || !session) return flow.start()
      await session.onShow()
      return emit()
    },
    dispose() {
      if (internal.disposed) return snapshot()
      internal.disposed = true
      operationToken += 1
      startInFlight = null
      if (unsubscribe) unsubscribe()
      unsubscribe = null
      if (session) session.dispose()
      listeners.clear()
      return snapshot()
    },
  }

  return flow
}

export default createMusicGenerationFlow
