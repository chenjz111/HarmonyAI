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

// ===== FE-2B：分页 / 去重 / cursor stale（纯逻辑，可被 node:test 直接驱动） =====

/** cursor 失效（后端要求从头刷新）时视为 stale。 */
export const CURSOR_STALE_CODES = Object.freeze([
  "LIBRARY_CURSOR_STALE",
  "CURSOR_STALE",
  "CURSOR_EXPIRED",
  "INVALID_CURSOR",
])

export function isCursorStale(error) {
  return !!error && CURSOR_STALE_CODES.includes(error.code)
}

/**
 * 按 music_id 去重合并分页结果。
 * 已存在的卡片优先（先到为准），避免旧 cursor 的迟到响应覆盖新数据。
 */
export function mergeMusicCards(existing = [], incoming = []) {
  const merged = [...existing]
  const seen = new Set(merged.map((card) => card && card.music_id).filter(Boolean))
  for (const card of incoming) {
    if (!card || !card.music_id || seen.has(card.music_id)) continue
    seen.add(card.music_id)
    merged.push(card)
  }
  return merged
}

/** 收藏是独立视图：仅按服务端 is_favorite 标记筛选，不推断偏好。 */
export function splitFavorites(cards = []) {
  return cards.filter((card) => card.is_favorite === true)
}

/**
 * 标题编辑输入归一化：空/空白 → null（显式清除自定义标题），否则去空白保留原文。
 * 不做任何富文本处理（页面纯文本渲染，无 v-html）。
 */
export function normalizeUserTitle(input) {
  const raw = typeof input === "string" ? input.trim() : ""
  return raw === "" ? null : raw
}

/**
 * 音乐库分页 store（真实 transport 与合成 transport 共用）。
 *
 * - 分页：cursor + has_more
 * - cursor stale：自动从头刷新（重置游标），不重复追加
 * - 去重：mergeMusicCards 按 music_id
 * - 迟到响应：requestToken 门禁，owner 切换/新请求会丢弃旧响应
 * - 不发明字段：只透传后端 PageV1 的 items / next_cursor / has_more
 *
 * @param {object} options
 * @param {(args: {cursor: string|null, limit: number}) => Promise<object>} options.fetchPage
 * @param {number} [options.pageSize]
 * @param {() => string|null} [options.getOwnerId] owner 切换保护（可选）
 */
export function createMusicLibraryStore({ fetchPage, pageSize = 20, getOwnerId = null } = {}) {
  if (typeof fetchPage !== "function") {
    throw new TypeError("createMusicLibraryStore: fetchPage is required")
  }
  let status = "idle" // idle | loading | ready | empty | error
  let items = []
  let nextCursor = null
  let hasMore = false
  let error = null
  let requestToken = 0
  let cursorStaleRefreshed = false

  function currentOwner() {
    return typeof getOwnerId === "function" ? getOwnerId() : null
  }

  // Owner identity is part of the store state, not only an async request check.
  // Every public read/operation observes the owner, invalidating cached cards
  // and outstanding cursors before a new account can see old private metadata.
  let observedOwner = currentOwner()

  function clearState() {
    requestToken += 1
    items = []
    nextCursor = null
    hasMore = false
    error = null
    cursorStaleRefreshed = false
    status = "idle"
  }

  function syncOwner() {
    if (typeof getOwnerId !== "function") return false
    const nextOwner = currentOwner()
    if (nextOwner === observedOwner) return false
    observedOwner = nextOwner
    clearState()
    return true
  }

  function snapshot() {
    syncOwner()
    return { status, items, nextCursor, hasMore, error, cursorStaleRefreshed }
  }

  async function load({ reset = false, staleRefresh = false } = {}) {
    syncOwner()
    const token = ++requestToken
    const owner = observedOwner
    if (reset) {
      items = []
      nextCursor = null
      hasMore = false
      error = null
      if (!staleRefresh) cursorStaleRefreshed = false
    }
    status = "loading"
    const cursor = reset ? null : nextCursor
    try {
      const page = await fetchPage({ cursor, limit: pageSize })
      if (syncOwner() || token !== requestToken || observedOwner !== owner) return snapshot() // owner/请求失效
      const incoming = Array.isArray(page && page.items) ? page.items : []
      items = mergeMusicCards(items, incoming)
      nextCursor = page && page.next_cursor !== undefined ? page.next_cursor : null
      hasMore = !!(page && page.has_more === true && nextCursor)
      status = items.length ? "ready" : "empty"
      error = null
    } catch (e) {
      if (syncOwner() || token !== requestToken || observedOwner !== owner) return snapshot()
      if (isCursorStale(e) && !reset) {
        // cursor 失效：从头刷新一次（不追加脏数据）
        cursorStaleRefreshed = true
        return load({ reset: true, staleRefresh: true })
      }
      error = e
      status = "error"
    }
    return snapshot()
  }

  return Object.freeze({
    loadFirstPage: () => load({ reset: true }),
    loadMore: () => {
      syncOwner()
      if (!hasMore) return Promise.resolve(snapshot())
      return load({ reset: false })
    },
    refresh: () => load({ reset: true }),
    // Page lifecycle may proactively discard the current view on logout/reentry.
    invalidate: () => { observedOwner = currentOwner(); clearState(); return snapshot() },
    getState: snapshot,
  })
}
