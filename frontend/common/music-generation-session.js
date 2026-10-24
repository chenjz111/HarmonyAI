/**
 * Sprint 6 Phase 6 — music generation session (DSH core lane).
 *
 * Owner-frozen Phase 6 decisions encoded here:
 *   P6-D2  honest failure + resume the existing task; a terminal retry is a NEW paid attempt
 *   P6-D3  fallback request policy stays "none"; a fallback RETURNED by the backend is labelled
 *   P6-D7  measured generated duration is playback authority (the asset's own duration_seconds)
 *   P6-D8  onHide stops polling; onShow resumes task sync only (never starts generation)
 *
 * Design rules (see the Phase 6 discovery report):
 *   - Pure and IO-free: every side effect (start / sync / cancel / timer) is injected, so the whole
 *     state machine is testable with node:test and no network, no uni, no DOM.
 *   - The backend is the only authority for status, tone, duration, instruments and ambience.
 *     This module never invents a tone, a duration, an instrument, a fallback or a success.
 *   - A failure is never rendered as a cancellation, and a cancellation is never rendered as a
 *     failure. Unknown statuses and unreadable bodies fail closed into `sync_error` with the task
 *     identity retained (resumable), never into `failed`/`playable`.
 *   - No prompt, provider or audit field is read here; nothing from this module is persisted.
 */

export const GENERATION_STATES = Object.freeze({
  IDLE: "idle",
  READY_TO_GENERATE: "ready_to_generate",
  CREATING: "creating",
  QUEUED: "queued",
  RUNNING: "running",
  SYNC_ERROR: "sync_error",
  FAILED: "failed",
  CANCELLED: "cancelled",
  MATCHED_FALLBACK: "matched_fallback",
  PLAYABLE: "playable",
})

export const RESUMABLE_TASK_STATUSES = Object.freeze(["queued", "running"])
export const TERMINAL_TASK_STATUSES = Object.freeze([
  "succeeded",
  "matched_fallback",
  "failed",
  "cancelled",
])

const KNOWN_TASK_STATUSES = Object.freeze([
  ...RESUMABLE_TASK_STATUSES,
  ...TERMINAL_TASK_STATUSES,
])

/** Honest, code-derived failure copy. Never says "cancelled" for a failure. */
export const FAILURE_COPY_BY_CODE = Object.freeze({
  GENERATION_PROVIDER_UNAVAILABLE: "音乐生成服务暂时不可用，请稍后重试。",
  GENERATION_PROVIDER_TIMEOUT: "音乐生成服务响应超时，请稍后重试。",
  GENERATION_PROVIDER_RATE_LIMITED: "音乐生成服务繁忙，请稍后重试。",
  GENERATION_PROVIDER_AUTH_FAILED: "音乐生成服务认证失败，请联系管理员。",
  GENERATION_PROVIDER_REJECTED: "音乐生成服务拒绝了本次请求（参数、额度或内容受限）。",
})

export const UNKNOWN_FAILURE_COPY = "音乐生成未能完成，请稍后重试。"
export const CANCELLED_COPY = "已取消生成。"
export const MATCHED_FALLBACK_COPY = "生成服务暂时不可用，已为你匹配审核曲库中的音乐。"
export const SYNC_ERROR_COPY = "音乐生成状态暂时无法同步，正在重试…"
export const GENERATING_COPY = "正在生成音乐…"
export const READY_COPY = "可以开始生成本次音乐。"

/** source_type → user-visible source label (the backend decides the type; we only label it). */
export const MUSIC_SOURCE_LABELS = Object.freeze({
  generated: "AI生成音乐",
  matched: "审核曲库匹配音乐",
  comfort_audio: "安抚音频",
})

export const GENERATION_FALLBACK_POLICY = Object.freeze({
  mode: "prefer_real_generation",
  fallback: "none",
})

export function isKnownTaskStatus(status) {
  return KNOWN_TASK_STATUSES.includes(String(status || ""))
}

export function isTerminalTaskStatus(status) {
  return TERMINAL_TASK_STATUSES.includes(String(status || ""))
}

export function isResumableTaskStatus(status) {
  return RESUMABLE_TASK_STATUSES.includes(String(status || ""))
}

export function failureCopyFor(errorCode) {
  const key = String(errorCode || "")
  return FAILURE_COPY_BY_CODE[key] || UNKNOWN_FAILURE_COPY
}

/** An asset is playable only when the backend gave us a stable id + an authorized stream path. */
export function playableAssetOf(task) {
  const asset = task && task.audio_asset
  if (!asset || typeof asset !== "object") return null
  const musicId = asset.music_ref && asset.music_ref.music_id
  if (!musicId || typeof asset.stream_url !== "string" || !asset.stream_url) return null
  return asset
}

export function sourceLabelFor(task) {
  const asset = playableAssetOf(task)
  const sourceType = asset && asset.music_ref ? asset.music_ref.source_type : ""
  return MUSIC_SOURCE_LABELS[sourceType] || ""
}

/**
 * Normalize one backend task body into the facts the UI may render. `known:false` means the body is
 * not a status we can act on; callers must treat that as a sync problem, not as any outcome.
 */
export function classifyMusicTask(task) {
  const status = task && typeof task.status === "string" ? task.status : ""
  const known = isKnownTaskStatus(status)
  const asset = playableAssetOf(task)
  const fallbackApplied = !!(task && task.fallback && task.fallback.applied)
  return {
    known,
    status,
    terminal: isTerminalTaskStatus(status),
    resumable: isResumableTaskStatus(status),
    playable: (status === "succeeded" || status === "matched_fallback") && !!asset,
    asset,
    assetMissing: (status === "succeeded" || status === "matched_fallback") && !asset,
    fallbackApplied,
    fallbackReasonCode: (task && task.fallback && task.fallback.reason_code) || null,
    sourceLabel: sourceLabelFor(task),
    errorCode: (task && task.error_code) || null,
    serverMessage: (task && typeof task.message === "string" && task.message) || "",
    // Measured duration of the produced audio (never the requested/planned value).
    measuredDurationSeconds: asset && asset.duration_seconds ? asset.duration_seconds : null,
  }
}

/** Terminal state for a task, or null when the task is not terminal/known. */
export function stateAfterTask(task) {
  const view = classifyMusicTask(task)
  if (!view.known) return null
  if (view.status === "queued") return GENERATION_STATES.QUEUED
  if (view.status === "running") return GENERATION_STATES.RUNNING
  if (view.status === "succeeded") return view.playable ? GENERATION_STATES.PLAYABLE : null
  if (view.status === "matched_fallback") {
    return view.playable ? GENERATION_STATES.MATCHED_FALLBACK : null
  }
  if (view.status === "failed") return GENERATION_STATES.FAILED
  return GENERATION_STATES.CANCELLED
}

/** Honest copy for a terminal task. Failure copy comes from the code, never from cancellation. */
export function terminalCopyFor(task) {
  const view = classifyMusicTask(task)
  if (!view.known) return SYNC_ERROR_COPY
  if (view.status === "failed") {
    const derived = failureCopyFor(view.errorCode)
    // Prefer the specific code-derived copy; the server message is exposed separately because the
    // backend collapses every failure to one generic sentence.
    return view.errorCode ? derived : view.serverMessage || derived
  }
  if (view.status === "cancelled") return CANCELLED_COPY
  if (view.status === "matched_fallback") return MATCHED_FALLBACK_COPY
  if (view.status === "succeeded") return view.playable ? "" : SYNC_ERROR_COPY
  return SYNC_ERROR_COPY
}

/**
 * What a user-initiated retry may do from a given state.
 *   "new_paid_attempt" — a terminal failure/cancellation: an explicit new generation (P6-D2)
 *   "resume"           — a sync problem with a retained task: re-sync, never pay again
 *   "none"             — nothing to retry
 */
export function retryKindForState(state) {
  if (state === GENERATION_STATES.FAILED || state === GENERATION_STATES.CANCELLED) {
    return "new_paid_attempt"
  }
  if (state === GENERATION_STATES.SYNC_ERROR) return "resume"
  if (state === GENERATION_STATES.QUEUED || state === GENERATION_STATES.RUNNING) return "resume"
  return "none"
}

function positiveInt(value, fallback) {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback
}

function defaultRequestKey() {
  return "music_" + Date.now() + "_" + Math.random().toString(36).slice(2, 10)
}

/**
 * Create one generation session.
 *
 * @param {object} options
 * @param {{startGeneration:Function, syncTask:Function, cancelTask?:Function}} options.api
 *        Injected task operations. `startGeneration({ requestId })` must be a single POST whose
 *        idempotency key derives from `requestId`, so retrying the same request id cannot double-bill.
 * @param {Function} [options.newRequestKey]  Request-id factory (tests inject a deterministic one).
 * @param {Function} [options.setTimer]       (fn, ms) -> handle
 * @param {Function} [options.clearTimer]     (handle) -> void
 */
export function createMusicGenerationSession(options = {}) {
  const api = options.api || {}
  if (typeof api.startGeneration !== "function") {
    throw new TypeError("createMusicGenerationSession requires api.startGeneration")
  }
  if (typeof api.syncTask !== "function") {
    throw new TypeError("createMusicGenerationSession requires api.syncTask")
  }
  const cancelTask = typeof api.cancelTask === "function" ? api.cancelTask : null
  const newRequestKey = typeof options.newRequestKey === "function" ? options.newRequestKey : defaultRequestKey
  const setTimer = typeof options.setTimer === "function" ? options.setTimer : (fn, ms) => setTimeout(fn, ms)
  const clearTimer = typeof options.clearTimer === "function" ? options.clearTimer : (handle) => clearTimeout(handle)
  const basePollMs = positiveInt(options.pollIntervalMs, 2000)
  const maxSyncErrors = positiveInt(options.maxConsecutiveSyncErrors, 4)

  const internal = {
    state: GENERATION_STATES.IDLE,
    taskId: null,
    status: null,
    task: null,
    asset: null,
    view: null,
    fallbackApplied: false,
    sourceLabel: "",
    errorCode: null,
    copy: READY_COPY,
    serverMessage: "",
    playable: false,
    syncAttempts: 0,
    syncStalled: false,
    requestId: null,
  }

  const listeners = new Set()
  let pollTimer = null
  let startInFlight = null
  let syncInFlight = null
  let hidden = false
  let disposed = false

  function snapshot() {
    return {
      state: internal.state,
      taskId: internal.taskId,
      status: internal.status,
      task: internal.task,
      asset: internal.asset,
      fallbackApplied: internal.fallbackApplied,
      sourceLabel: internal.sourceLabel,
      errorCode: internal.errorCode,
      copy: internal.copy,
      serverMessage: internal.serverMessage,
      playable: internal.playable,
      syncAttempts: internal.syncAttempts,
      syncStalled: internal.syncStalled,
      retryKind: retryKindForState(internal.state),
    }
  }

  function emit() {
    const snap = snapshot()
    for (const listener of listeners) {
      try {
        listener(snap)
      } catch (e) {
        /* a listener must never break the session */
      }
    }
    return snap
  }

  function clearPoll() {
    if (pollTimer !== null) {
      clearTimer(pollTimer)
      pollTimer = null
    }
  }

  function scheduleNext(delayMs) {
    clearPoll()
    if (disposed || hidden) return
    const wait = positiveInt(delayMs, basePollMs)
    pollTimer = setTimer(() => {
      pollTimer = null
      void syncOnce()
    }, wait)
  }

  /** Apply one trusted task body. Returns the resulting state. */
  function applyTask(task) {
    const view = classifyMusicTask(task)
    internal.task = task || null
    internal.view = view
    internal.status = view.known ? view.status : null
    internal.serverMessage = view.serverMessage
    if (task && task.task_id) internal.taskId = task.task_id

    if (!view.known) {
      // Fail closed: an unrecognizable status is a sync problem, never an outcome. It keeps the
      // identity and keeps retrying; it must not stop the session or announce a terminal state.
      internal.errorCode = null
      internal.playable = false
      internal.asset = null
      return applySyncProblem(SYNC_ERROR_COPY)
    }

    internal.syncAttempts = 0
    internal.syncStalled = false

    if (view.assetMissing) {
      // "succeeded" without a usable asset is not playable: keep the identity and keep syncing.
      internal.errorCode = null
      internal.playable = false
      internal.asset = null
      return applySyncProblem(SYNC_ERROR_COPY)
    }

    internal.asset = view.asset
    internal.errorCode = view.errorCode
    internal.fallbackApplied = view.fallbackApplied
    internal.sourceLabel = view.sourceLabel
    internal.playable = view.playable
    internal.copy = terminalCopyFor(task)

    if (view.resumable) {
      internal.state = view.status === "queued" ? GENERATION_STATES.QUEUED : GENERATION_STATES.RUNNING
      // Re-read the interval from every response instead of freezing it at schedule time.
      scheduleNext(task && task.poll_after_ms)
      return emit()
    }

    internal.state = stateAfterTask(task)
    clearPoll()
    return emit()
  }

  /** Non-terminal transport problem: retain identity, never fabricate a terminal outcome. */
  function applySyncProblem(copy) {
    clearPoll()
    internal.syncAttempts += 1
    internal.syncStalled = internal.syncAttempts >= maxSyncErrors
    internal.state = GENERATION_STATES.SYNC_ERROR
    internal.copy = copy || SYNC_ERROR_COPY
    internal.playable = false
    const snap = emit()
    if (!hidden && !disposed) {
      const backoff = basePollMs * Math.min(4, Math.pow(2, Math.max(0, internal.syncAttempts - 1)))
      scheduleNext(backoff)
    }
    return snap
  }

  /** One status sync. Overlapping ticks are impossible: concurrent calls share one request. */
  function syncOnce() {
    if (disposed || hidden || !internal.taskId) return Promise.resolve(snapshot())
    if (syncInFlight) return syncInFlight
    const taskId = internal.taskId
    syncInFlight = Promise.resolve()
      .then(() => api.syncTask(taskId))
      .then((task) => {
        syncInFlight = null
        if (disposed) return snapshot()
        if (!task || (task.task_id && task.task_id !== taskId)) {
          // A response for a different task must never overwrite this session's identity.
          return applySyncProblem(SYNC_ERROR_COPY)
        }
        return applyTask(task)
      })
      .catch((error) => {
        syncInFlight = null
        if (disposed) return snapshot()
        return applySyncProblem(error && error.message ? error.message : SYNC_ERROR_COPY)
      })
    return syncInFlight
  }

  function hydrate(taskId, status) {
    if (taskId) internal.taskId = taskId
    if (status) internal.status = status
    return snapshot()
  }

  const session = {
    snapshot,
    subscribe(listener) {
      listeners.add(listener)
      listener(snapshot())
      return () => listeners.delete(listener)
    },

    /** The basis/spec is ready and the user may start a generation. */
    ready() {
      internal.state = GENERATION_STATES.READY_TO_GENERATE
      internal.copy = READY_COPY
      return emit()
    },

    /** Seed the identity of a task that already exists server-side (resume path). */
    hydrate,

    /** Resume a stored task id without starting a new paid generation (P6-D2). */
    resume() {
      if (disposed) return Promise.resolve(snapshot())
      if (!internal.taskId) return Promise.resolve(snapshot())
      if (isTerminalTaskStatus(internal.status) && internal.task) {
        internal.state = stateAfterTask(internal.task) || internal.state
        return Promise.resolve(emit())
      }
      return syncOnce()
    },

    /**
     * Start a generation. Repeated taps inside one render cycle share the same in-flight promise,
     * so exactly one POST is issued; a resumable task is resumed instead of re-created.
     */
    ensureGeneration() {
      if (disposed) return Promise.resolve(snapshot())
      if (startInFlight) return startInFlight
      if (
        internal.taskId &&
        (isResumableTaskStatus(internal.status) || internal.state === GENERATION_STATES.SYNC_ERROR)
      ) {
        return session.resume()
      }
      if (internal.state === GENERATION_STATES.PLAYABLE || internal.state === GENERATION_STATES.MATCHED_FALLBACK) {
        return Promise.resolve(snapshot())
      }
      if (!internal.requestId) internal.requestId = newRequestKey()
      const requestId = internal.requestId
      internal.state = GENERATION_STATES.CREATING
      internal.copy = GENERATING_COPY
      emit()
      startInFlight = Promise.resolve()
        .then(() => api.startGeneration({ requestId }))
        .then((task) => {
          startInFlight = null
          if (disposed) return snapshot()
          if (!task || !task.task_id) return applySyncProblem(SYNC_ERROR_COPY)
          // The request is now a durable task: reuse its id, never re-POST this request id.
          internal.requestId = null
          return applyTask(task)
        })
        .catch((error) => {
          startInFlight = null
          if (disposed) return snapshot()
          // The POST failed and the outcome is unknown: keep the request id so a retry replays the
          // same idempotency key instead of paying for a second generation.
          internal.errorCode = (error && error.code) || internal.errorCode
          return applySyncProblem(error && error.message ? error.message : SYNC_ERROR_COPY)
        })
      return startInFlight
    },

    /** Explicit user retry: new paid attempt only after a terminal failure/cancellation. */
    retry() {
      const kind = retryKindForState(internal.state)
      if (kind === "none") return Promise.resolve(snapshot())
      if (kind === "resume") {
        // A sync problem with a known task resumes it. If the POST itself failed we never learned a
        // task id, so re-issue the SAME request id: the backend replays one idempotency key instead
        // of paying for a second generation.
        if (internal.taskId) return session.resume()
        return session.ensureGeneration()
      }
      internal.requestId = null
      internal.taskId = null
      internal.task = null
      internal.status = null
      internal.asset = null
      internal.errorCode = null
      internal.syncAttempts = 0
      internal.syncStalled = false
      internal.state = GENERATION_STATES.READY_TO_GENERATE
      return session.ensureGeneration()
    },

    /** Ask the backend to cancel. A refused/failed cancel is a sync problem, not a cancellation. */
    cancel() {
      if (disposed || !internal.taskId || !cancelTask) return Promise.resolve(snapshot())
      if (isTerminalTaskStatus(internal.status)) return Promise.resolve(snapshot())
      return Promise.resolve()
        .then(() => cancelTask(internal.taskId))
        .then((task) => (disposed ? snapshot() : applyTask(task)))
        .catch((error) =>
          disposed ? snapshot() : applySyncProblem(error && error.message ? error.message : SYNC_ERROR_COPY),
        )
    },

    /** P6-D8: leaving the foreground stops polling and keeps the task identity. */
    onHide() {
      hidden = true
      clearPoll()
      return snapshot()
    },

    /** P6-D8: returning to the foreground resumes status sync only — never a new generation. */
    onShow() {
      if (disposed) return Promise.resolve(snapshot())
      hidden = false
      if (!internal.taskId) return Promise.resolve(snapshot())
      if (internal.task && isTerminalTaskStatus(internal.status)) {
        clearPoll()
        return Promise.resolve(snapshot())
      }
      return syncOnce()
    },

    dispose() {
      disposed = true
      clearPoll()
      listeners.clear()
      return snapshot()
    },
  }

  return session
}

export default createMusicGenerationSession
