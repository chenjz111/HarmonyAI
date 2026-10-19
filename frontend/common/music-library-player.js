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
 * @param {() => string} options.newEventId 生成 play_started 的稳定 event id
 */
export function createHistoricalMusicSession({ api, getOwnerId, newEventId }) {
  if (!api) throw new TypeError("createHistoricalMusicSession: api is required")
  const readOwner = typeof getOwnerId === "function" ? getOwnerId : () => null
  const makeEventId = typeof newEventId === "function" ? newEventId : () => "play-" + Date.now()

  let openOwner = null
  let eventId = null
  let playReported = false
  let contextId = null
  let generation = 0
  let reportPromise = null

  function ownerChanged() {
    return openOwner !== null && readOwner() !== openOwner
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
      const owner = readOwner()
      if (!owner) throw failure(HISTORICAL_PLAYER_ERROR.IDENTITY_REQUIRED, "请恢复当前身份后重试")
      const opening = ++generation
      openOwner = owner
      contextId = context
      eventId = makeEventId()
      playReported = false
      const detail = await api.getMusicAsset(musicId, { contextId: context })
      assertOwner()
      if (opening !== generation) throw failure(HISTORICAL_PLAYER_ERROR.OWNER_CHANGED, "历史播放会话已失效")
      contextId = detail && detail.selected_context_id || null
      return detail
    },

    /**
     * 真实播放成功后上报一次 play_started。
     * - 重复调用（同一会话）不再上报（幂等）
     * - 失败不标记已上报，重试复用同一 event id
     */
    async reportPlayStarted(musicId) {
      if (playReported) return { reported: false, reason: "already_reported" }
      if (reportPromise) return reportPromise
      if (!eventId) throw failure(HISTORICAL_PLAYER_ERROR.FEATURE_NOT_READY, "播放会话尚未开始")
      assertOwner()
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
      reportPromise = null
      openOwner = null
      eventId = null
      playReported = false
      contextId = null
    },

    getState() {
      return { eventId, playReported, contextId, owner: openOwner }
    },

    hasOwnerChanged: ownerChanged,
  })
}
