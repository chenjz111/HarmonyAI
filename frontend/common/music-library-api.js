// W2 contract adapter. No default transport, credentials, identity creation,
// generation calls or persistent cache. Live enablement requires Backend Gates.
function failure(code, message) {
  return Object.assign(new Error(message), { code })
}

export function createMusicLibraryApi({ request, getOwnerId, enabled = false }) {
  async function call(method, path, data) {
    if (!enabled) throw failure('FEATURE_NOT_READY', '音乐库接口尚未开放')
    const owner = getOwnerId()
    if (!owner) throw failure('IDENTITY_REQUIRED', '请恢复当前身份后重试')
    const args = { method, path }
    if (data !== undefined) args.data = data
    const response = await request(args)
    if (getOwnerId() !== owner) throw failure('OWNER_CHANGED', '身份已切换，请重新加载')
    if (response?.error) throw failure(response.error.code, '请求未完成，请刷新后重试')
    if (!response || !Object.hasOwn(response, 'data')) throw failure('INVALID_RESPONSE', '音乐库响应不可用')
    return response.data
  }
  function page(path, { cursor = null, limit = 20 } = {}) {
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
      return Promise.reject(failure('INVALID_LIMIT', '分页数量无效'))
    }
    return call('GET', `${path}?limit=${limit}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`)
  }
  const asset = (id) => `/api/v3/music/assets/${encodeURIComponent(id)}`
  return Object.freeze({
    listMusicAssets: (options) => page('/api/v3/me/music-assets', options),
    listMusicFavorites: (options) => page('/api/v3/me/music-favorites', options),
    getMusicAsset: (id, { contextId = null } = {}) => call('GET', `${asset(id)}${contextId ? `?context_id=${encodeURIComponent(contextId)}` : ''}`),
    setMusicTitle: (id, userTitle, expectedVersion) => call('PATCH', `${asset(id)}/title`, {
      user_title: userTitle, expected_version: expectedVersion,
    }),
    recordPlayStarted: (id, eventId, sourceContextId = null) => call('POST', `${asset(id)}/playback-events`, {
      event_id: eventId, event_type: 'play_started', source_context_id: sourceContextId,
    }),
    setFavorite: (musicRef, selected) => selected
      ? call('PUT', '/api/v3/favorites', { music_ref: musicRef })
      : call('DELETE', `/api/v3/favorites/${encodeURIComponent(musicRef.music_id)}`),
  })
}
