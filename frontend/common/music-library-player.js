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

/** MusicDetailV1 是否可播放：audio_asset（LibraryAudioV1）存在且带 stream_url。 */
export function isDetailPlayable(detail) {
  const audio = detail && detail.audio_asset
  return !!(audio && audio.stream_url)
}

/** 从 MusicDetailV1 取播放所需的最小信息（不构造处方、不发明字段）。 */
export function resolvePlayableAudio(detail) {
  if (!isDetailPlayable(detail)) return null
  const audio = detail.audio_asset
  return {
    music_id: detail.music_id,
    stream_url: audio.stream_url,
    duration_seconds:
      Number.isFinite(detail.duration_seconds) && detail.duration_seconds > 0
        ? detail.duration_seconds
        : null,
    source_type: detail.source_type,
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
      openOwner = owner
      contextId = context
      eventId = makeEventId()
      playReported = false
      const detail = await api.getMusicAsset(musicId, { contextId: context })
      assertOwner()
      return detail
    },

    /**
     * 真实播放成功后上报一次 play_started。
     * - 重复调用（同一会话）不再上报（幂等）
     * - 失败不标记已上报，重试复用同一 event id
     */
    async reportPlayStarted(musicId) {
      if (playReported) return { reported: false, reason: "already_reported" }
      if (!eventId) throw failure(HISTORICAL_PLAYER_ERROR.FEATURE_NOT_READY, "播放会话尚未开始")
      assertOwner()
      const result = await api.recordPlayStarted(musicId, eventId, contextId)
      playReported = true
      return { reported: true, eventId, result }
    },

    /** owner 切换或页面卸载时重置会话（不触发任何网络调用）。 */
    reset() {
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
