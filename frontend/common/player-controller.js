/**
 * Sprint 6 Phase 6 — Player Controller（彭翔 · Player Controller Lane）
 *
 * 可测试的音频控制器：所有平台依赖通过注入提供（uni / 授权下载 / InnerAudioContext），
 * 模块本身不引用全局 `uni`，因此可在 node:test 中直接驱动。
 *
 * 职责（P6 lane 契约）：
 *   - 最多一个 pending 授权下载（duplicate fast Play guard）
 *   - 最多一个 InnerAudioContext
 *   - play / pause / seek
 *   - canplay / duration / time update / ended / error 事件
 *   - onHide 暂停（handleHide）
 *   - unload/dispose 销毁（dispose，恰好一次）
 *
 * 明确不做（lane 禁止项）：
 *   - autoplay（创建/加载不自动播放）
 *   - background audio manager
 *   - Android 原生插件
 *   - 持久化音频缓存（只持有内存中的已解析本地路径）
 *
 * 时长口径：
 *   controller 只上报**运行时音频**的 duration / currentTime（来自 InnerAudioContext），
 *   不发明、不补默认值、不混入后端声明时长。展示与权威策略由 DSH + presentation 模块负责。
 */

export const PLAYER_STATE = Object.freeze({
  IDLE: "idle",
  LOADING: "loading",
  PLAYING: "playing",
  PAUSED: "paused",
  ENDED: "ended",
  ERROR: "error",
})

/**
 * 创建播放器控制器。
 *
 * @param {object} options
 * @param {(streamUrl: string) => Promise<string>} options.downloadAudio
 *        授权下载：返回可供 InnerAudioContext 播放的本地路径（等价 apiV3.fetchAuthorizedAudio）
 * @param {() => object} options.createAudioContext
 *        创建 InnerAudioContext（等价 uni.createInnerAudioContext）
 * @param {(error: object) => void} [options.onError]
 *        音频错误上报（等价页面 toast）
 * @param {(snapshot: object) => void} [options.onStateChange]
 *        状态变化通知（页面据此更新 UI）
 * @returns {object} controller 公共 API
 */
export function createPlayerController(options = {}) {
  const { downloadAudio, createAudioContext, onError, onStateChange } = options

  if (typeof downloadAudio !== "function") {
    throw new TypeError("createPlayerController: downloadAudio is required")
  }
  if (typeof createAudioContext !== "function") {
    throw new TypeError("createPlayerController: createAudioContext is required")
  }

  // ===== 内部状态 =====
  let audioCtx = null
  let resolvedSrc = "" // 内存中的已解析本地路径（不做持久化缓存）
  let resolvedStreamUrl = "" // 当前已解析的 stream url（用于同曲恢复判断）
  let pendingDownload = null // Promise | null —— 同一时刻最多一个
  let pendingStreamUrl = "" // pending 下载对应的 stream url
  let playing = false
  let currentTime = 0
  let duration = 0 // 仅来自运行时音频（onCanplay / onTimeUpdate）
  let disposed = false
  let errorInfo = null

  function snapshot() {
    return {
      state: disposed
        ? PLAYER_STATE.IDLE
        : errorInfo
          ? PLAYER_STATE.ERROR
          : playing
            ? PLAYER_STATE.PLAYING
            : resolvedSrc
              ? PLAYER_STATE.PAUSED
              : PLAYER_STATE.IDLE,
      playing,
      currentTime,
      duration,
      src: resolvedSrc,
      streamUrl: resolvedStreamUrl,
      disposed,
      error: errorInfo,
    }
  }

  function emit() {
    if (typeof onStateChange === "function") onStateChange(snapshot())
  }

  function fail(error) {
    playing = false
    errorInfo = error || { message: "audio error" }
    emit()
    if (typeof onError === "function") onError(errorInfo)
  }

  // 单个 InnerAudioContext；绑定运行时事件（不发明 duration）
  function ensureContext() {
    if (audioCtx || disposed) return audioCtx
    audioCtx = createAudioContext()
    if (!audioCtx) return null

    if (typeof audioCtx.onCanplay === "function") {
      audioCtx.onCanplay(() => {
        if (disposed || !audioCtx) return
        const real = Number(audioCtx.duration)
        if (Number.isFinite(real) && real > 0) {
          duration = real
          emit()
        }
      })
    }
    if (typeof audioCtx.onTimeUpdate === "function") {
      audioCtx.onTimeUpdate(() => {
        if (disposed || !audioCtx) return
        currentTime = Number(audioCtx.currentTime) || 0
        // 部分平台 onCanplay 时 duration 仍为 0，这里用同一音频时间基补齐
        const real = Number(audioCtx.duration)
        if (Number.isFinite(real) && real > 0) duration = real
        emit()
      })
    }
    if (typeof audioCtx.onEnded === "function") {
      audioCtx.onEnded(() => {
        if (disposed) return
        playing = false
        emit()
      })
    }
    if (typeof audioCtx.onError === "function") {
      audioCtx.onError((err) => {
        if (disposed) return
        fail(err)
      })
    }
    return audioCtx
  }

  // 最多一个 pending 授权下载：同一 stream url 的并发请求复用同一 Promise
  function ensureDownload(streamUrl) {
    if (pendingDownload && pendingStreamUrl === streamUrl) return pendingDownload
    pendingStreamUrl = streamUrl
    pendingDownload = Promise.resolve()
      .then(() => downloadAudio(streamUrl))
      .then((src) => {
        resolvedSrc = src
        resolvedStreamUrl = streamUrl
        return src
      })
      .finally(() => {
        if (pendingStreamUrl === streamUrl) {
          pendingDownload = null
          pendingStreamUrl = ""
        }
      })
    return pendingDownload
  }

  /**
   * 播放。重复快速调用只触发一次下载。
   * @param {string} [streamUrl] 目标音频地址；省略则复用当前已解析地址
   */
  async function play(streamUrl) {
    if (disposed) return snapshot()
    const url = streamUrl || resolvedStreamUrl
    if (!url) {
      fail({ message: "missing stream url" })
      return snapshot()
    }

    // 同一曲目且已解析：直接恢复播放，不重复下载、不重置进度
    if (audioCtx && resolvedSrc && resolvedStreamUrl === url) {
      errorInfo = null
      if (typeof audioCtx.play === "function") audioCtx.play()
      playing = true
      emit()
      return snapshot()
    }

    errorInfo = null
    let src
    try {
      src = await ensureDownload(url)
    } catch (e) {
      fail(e)
      return snapshot()
    }
    if (disposed) return snapshot()

    const ctx = ensureContext()
    if (!ctx) {
      fail({ message: "audio context unavailable" })
      return snapshot()
    }
    // 仅在 src 变化时赋值，避免重复设置导致重启
    if (ctx.src !== src) ctx.src = src
    if (typeof ctx.play === "function") ctx.play()
    playing = true
    emit()
    return snapshot()
  }

  /** 暂停（幂等）。 */
  function pause() {
    if (disposed) return snapshot()
    if (audioCtx && typeof audioCtx.pause === "function") audioCtx.pause()
    playing = false
    emit()
    return snapshot()
  }

  /** 播放/暂停切换。 */
  function toggle(streamUrl) {
    if (playing) return pause()
    return play(streamUrl)
  }

  /**
   * 按比例跳转。ratio ∈ [0, 1] 对应 0%~100%，越界自动 clamp。
   * 时长无效/缺失（非有限数或 <= 0）时不执行 seek。
   *
   * @param {number} ratio
   * @returns {boolean} 是否执行了 seek
   */
  function seek(ratio) {
    if (disposed) return false
    if (!audioCtx) return false
    const total = Number(duration)
    if (!Number.isFinite(total) || total <= 0) return false // invalid/missing duration => no seek
    const value = Number(ratio)
    if (!Number.isFinite(value)) return false
    const clamped = Math.max(0, Math.min(1, value))
    const target = clamped * total
    if (typeof audioCtx.seek === "function") audioCtx.seek(target)
    currentTime = target
    emit()
    return true
  }

  /** 页面 onHide：暂停音频；不停止、不销毁。 */
  function handleHide() {
    return pause()
  }

  /**
   * 页面 onShow：仅同步状态，**不自动恢复播放**（no auto-resume）。
   * 任务轮询恢复由 DSH 页面层负责，controller 不参与。
   */
  function handleShow() {
    emit()
    return snapshot()
  }

  /** 销毁：destroy 恰好一次（幂等）。 */
  function dispose() {
    if (disposed) return snapshot()
    disposed = true
    if (audioCtx) {
      if (typeof audioCtx.destroy === "function") audioCtx.destroy()
      audioCtx = null
    }
    resolvedSrc = ""
    playing = false
    emit()
    return snapshot()
  }

  return {
    play,
    pause,
    toggle,
    seek,
    handleHide,
    handleShow,
    dispose,
    getState: snapshot,
    isPlaying: () => playing,
  }
}

export default createPlayerController
