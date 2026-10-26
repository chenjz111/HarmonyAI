/** R1 endpoints; one authentication instance and no persistent response cache. */
const failure = (code) => Object.assign(new Error(code), { code })

export function createFeedbackApi({ request, getOwnerId, getAccessToken, getAuthEpoch, enabled = false }) {
  let identity = null, invalid = false, generation = 0, latestEpoch = 0
  function assertIdentity() {
    let owner, token, epoch
    try { owner = getOwnerId(); token = getAccessToken(); epoch = getAuthEpoch() } catch (e) { /* fail closed */ }
    if (invalid || (identity && (owner !== identity.owner || token !== identity.token || epoch !== identity.epoch))) {
      invalid = true; throw failure('OWNER_CHANGED')
    }
    if (!owner || typeof token !== 'string' || !token.trim() || !Number.isSafeInteger(epoch) || epoch < 0) throw failure('IDENTITY_REQUIRED')
    if (!identity) identity = { owner, token, epoch }
  }
  async function call(method, path, data, idempotencyKey) {
    if (!enabled) throw failure('FEATURE_NOT_READY')
    assertIdentity()
    const starting = generation
    const args = { method, path }
    if (data !== undefined) args.data = data
    if (idempotencyKey !== undefined) args.idempotencyKey = idempotencyKey
    let response
    try { response = await request(args) } catch (error) { assertIdentity(); if (method === 'GET' && starting !== generation) throw failure('STALE_RESPONSE'); throw error }
    assertIdentity()
    if (method === 'GET' && starting !== generation) throw failure('STALE_RESPONSE')
    if (response?.error) throw Object.assign(new Error(response.error.message || response.error.code), response.error)
    if (!response || !Object.prototype.hasOwnProperty.call(response, 'data')) throw failure('INVALID_RESPONSE')
    const epoch = response.data.current_feedback_epoch ?? response.data.resulting_feedback_epoch
    if (method === 'GET' && Number.isSafeInteger(epoch) && epoch < latestEpoch) throw failure('STALE_RESPONSE')
    if (Number.isSafeInteger(epoch)) latestEpoch = Math.max(latestEpoch, epoch)
    if (method !== 'GET') generation++
    return response.data
  }
  return Object.freeze({
    save: (body, key) => call('POST', '/api/v3/feedback-records', body, key),
    clear: (body, key) => call('POST', '/api/v3/me/feedback-evidence/clear', body, key),
    remove: (id, epoch) => call('DELETE', `/api/v3/feedback-records/${encodeURIComponent(id)}`, { expected_evidence_epoch:epoch }),
    get: id => call('GET', `/api/v3/feedback-records/${encodeURIComponent(id)}`),
    list: ({limit=20,cursor=null,musicId=null}={}) => call('GET', `/api/v3/feedback-records?limit=${limit}${cursor ? '&cursor='+encodeURIComponent(cursor) : ''}${musicId ? '&music_id='+encodeURIComponent(musicId) : ''}`),
    invalidate() { invalid = true; generation++ },
    isCurrent() { try { assertIdentity(); return !invalid } catch (error) { return false } },
    currentEpoch: () => latestEpoch,
  })
}
