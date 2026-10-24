/**
 * Sprint 7 M1 / FE-2B — 历史音乐播放会话（Music Library 通道）
 *
 * 职责：
 *   - 用 music_id 读取受控 MusicDetailV1（音频与解锁来自历史持久化上下文）
 *   - 仅在真实 onPlay 成功时上报一次 play_started；重试复用同一 event id
 *   - owner 切换时拒绝迟到结果，调用方据此停止音频并清理页面状态
 *
 * 边界（Issue #153）：
 *   - 不 ensureMusicBasis、不读取当前 session / UserGoal 替代旧资料
 *   - 不发起生成、不做持久缓存、不新增第二个 Player
 *   - 只消费统一 DTO（MusicDetailV1 / LibraryAudioV1），字段原样透传
 */

function failure(code, message) {
  return Object.assign(new Error(message), { code })
}

export const HISTORICAL_PLAYER_ERROR = Object.freeze({
  FEATURE_NOT_READY: "FEATURE_NOT_READY",
  IDENTITY_REQUIRED: "IDENTITY_REQUIRED",
  OWNER_CHANGED: "OWNER_CHANGED",
  NOT_PLAYABLE: "MUSIC_NOT_PLAYABLE",
})

/** MusicDetailV1 是否可播放：已授权卡片及 LibraryAudioV1 都为 ready。 */
export function isDetailPlayable(detail) {
  const card = detail && detail.card
  const audio = detail && detail.audio
  return !!(card && card.music_id && card.availability === "ready" &&
    audio && audio.availability === "ready")
}

/** LibraryAudioV1 deliberately contains no URL. Use the existing owner-authorized V3 stream route. */
export function resolvePlayableAudio(detail) {
  if (!isDetailPlayable(detail)) return null
  const { card, audio } = detail
  return {
    music_id: card.music_id,
    stream_url: `/api/v3/music/assets/${encodeURIComponent(card.music_id)}/stream`,
    duration_seconds:
      Number.isFinite(audio.duration_seconds) && audio.duration_seconds > 0
        ? audio.duration_seconds : null,
    source_type: card.source_type,
  }
}

/**
 * 创建历史播放会话。
 *
 * @param {object} options
 * @param {object} options.api Music Library API（createMusicLibraryApi 产物）
 * @param {() => string|null} options.getOwnerId
 * @param {() => string|null} options.getAccessToken Credential reader; never exposed by getState.
 * @param {() => number|null} options.getAuthEpoch Nonnegative safe integer for this authentication instance.
 * @param {() => string} options.newEventId 生成 play_started 的稳定 event id
 */
export function createHistoricalMusicSession({ api, getOwnerId, getAccessToken, getAuthEpoch, newEventId }) {
  if (!api) throw new TypeError("createHistoricalMusicSession: api is required")
  const readOwner = typeof getOwnerId === "function" ? getOwnerId : () => null
  const readToken = typeof getAccessToken === "function" ? getAccessToken : () => null
  const readEpoch = typeof getAuthEpoch === "function" ? getAuthEpoch : () => null
  const makeEventId = typeof newEventId === "function" ? newEventId : () => "play-" + Date.now()

  let openOwner = null
  let eventId = null
  let playReported = false
  let contextId = null
  let generation = 0
  let reportPromise = null
  let identity = null
  let invalidated = false
  let openedMusicId = null
  let detailReady = false
  let feedbackContext = null
  let feedbackReady = false

  function captureIdentity() {
    let owner, token, epoch
    try { owner = readOwner(); token = readToken(); epoch = readEpoch() } catch (e) { /* fail closed */ }
    if (!owner || typeof token !== "string" || !token.trim() || !Number.isSafeInteger(epoch) || epoch < 0) {
      throw failure(HISTORICAL_PLAYER_ERROR.IDENTITY_REQUIRED, "请恢复当前身份后重试")
    }
    // Credential is held only by this private immutable closure, never getState().
    return Object.freeze({ owner, matches: () => {
      try { return readOwner() === owner && readToken() === token && readEpoch() === epoch } catch (e) { return false }
    } })
  }

  function ownerChanged() {
    if (identity && !identity.matches()) invalidated = true
    return invalidated
  }

  function assertOwner() {
    if (ownerChanged()) throw failure(HISTORICAL_PLAYER_ERROR.OWNER_CHANGED, "身份已切换，请重新加载")
  }

  return Object.freeze({
    /**
     * 打开历史音乐详情。返回 MusicDetailV1（原样）。
     * 迟到结果（owner 已切换）抛 OWNER_CHANGED，调用方必须丢弃。
     */
    async open(musicId, { context = null } = {}) {
      assertOwner()
      if (!identity) identity = captureIdentity()
      const opening = ++generation
      openOwner = identity.owner
      openedMusicId = musicId
      detailReady = false
      feedbackContext = null
      feedbackReady = false
      contextId = context
      eventId = makeEventId()
      playReported = false
      reportPromise = null
      let detail
      try { detail = await api.getMusicAsset(musicId, { contextId: context }) } catch (error) {
        assertOwner()
        if (opening !== generation) throw failure(HISTORICAL_PLAYER_ERROR.OWNER_CHANGED, "历史播放会话已失效")
        throw error
      }
      assertOwner()
      if (opening !== generation) throw failure(HISTORICAL_PLAYER_ERROR.OWNER_CHANGED, "历史播放会话已失效")
      contextId = detail && detail.selected_context_id || null
      const selected = detail && Array.isArray(detail.source_contexts)
        ? detail.source_contexts.find(choice => choice.context_id === contextId) : null
      if (contextId && selected && selected.session_id && detail.card?.music_id === musicId) {
        feedbackContext = Object.freeze({ session_id:selected.session_id,
          music_ref:Object.freeze({music_id:musicId,source_type:detail.card.source_type}),
          source_context_id:contextId,playback_event_id:eventId,
          pre_state_snapshot:Object.freeze({snapshot_id:'snap_'+eventId,source:'player_session',captured_at:new Date().toISOString()}) })
      }
      detailReady = true
      return detail
    },

    /**
     * 真实播放成功后上报一次 play_started。
     * - 重复调用（同一会话）不再上报（幂等）
     * - 失败不标记已上报，重试复用同一 event id
     */
    async reportPlayStarted(musicId) {
      assertOwner()
      if (playReported) return { reported: false, reason: "already_reported" }
      if (reportPromise) return reportPromise
      if (!eventId || !detailReady || musicId !== openedMusicId) throw failure(HISTORICAL_PLAYER_ERROR.FEATURE_NOT_READY, "播放会话尚未开始")
      const reportingGeneration = generation
      const reportingEventId = eventId
      const reportingContext = contextId
      const pending = (async () => {
        const result = await api.recordPlayStarted(musicId, reportingEventId, reportingContext)
        assertOwner()
        if (reportingGeneration !== generation || eventId !== reportingEventId) {
          throw failure(HISTORICAL_PLAYER_ERROR.OWNER_CHANGED, "历史播放会话已失效")
        }
        playReported = true
        feedbackReady = result?.event_id === reportingEventId && result?.music_id === musicId && result?.event_type === 'play_started'
        return { reported: true, eventId: reportingEventId, result }
      })()
      reportPromise = pending
      try { return await pending } finally {
        if (reportPromise === pending) reportPromise = null
      }
    },

    /** owner 切换或页面卸载时重置会话（不触发任何网络调用）。 */
    reset() {
      generation += 1
      invalidated = true
      detailReady = false
      openedMusicId = null
      reportPromise = null
      openOwner = null
      eventId = null
      playReported = false
      contextId = null
      feedbackContext = null
      feedbackReady = false
    },

    getState() {
      return { eventId, playReported, contextId, owner: openOwner }
    },

    getFeedbackContext() {
      assertOwner()
      if (!feedbackContext || !feedbackReady || !playReported) throw failure(HISTORICAL_PLAYER_ERROR.FEATURE_NOT_READY, '请先选择来源记录并实际播放')
      return feedbackContext
    },

    hasOwnerChanged: ownerChanged,
  })
}
