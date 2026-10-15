const AVAILABILITY_LABELS = Object.freeze({
  ready: "可以播放",
  expired: "音频已不可用",
  quarantined: "音频暂不可用",
  deleted: "音频已不可用",
  missing: "音频暂不可用",
})

function durationLabel(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "时长未知"
  const whole = Math.floor(seconds)
  const minutes = Math.floor(whole / 60)
  const remainder = whole % 60
  return remainder ? `${minutes}分${remainder}秒` : `${minutes}分钟`
}

export function presentMusicCard(card) {
  const availability = Object.hasOwn(AVAILABILITY_LABELS, card.availability)
    ? card.availability
    : "missing"
  return Object.freeze({
    ...card,
    availability,
    duration_label: durationLabel(card.duration_seconds),
    playback_label: card.last_played_at ? "最近听过" : "尚未播放",
    availability_label: AVAILABILITY_LABELS[availability],
    can_open: availability === "ready",
  })
}

export function createMusicLibraryPreview(status, cards = []) {
  if (status === "loading" || status === "empty") {
    return { status, history: [], favorites: [], error: null }
  }
  if (status === "error") {
    return { status, history: [], favorites: [], error: "暂时无法加载音乐记录" }
  }
  const history = cards.map(presentMusicCard)
  return {
    status: history.length ? "ready" : "empty",
    history,
    favorites: history.filter((card) => card.is_favorite === true),
    error: null,
  }
}

export function musicPlayerUrl(musicId) {
  return `/pages/v3-player/v3-player?music_id=${encodeURIComponent(musicId)}`
}
