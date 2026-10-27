/** R1 endpoints; one authentication instance and no persistent response cache. */
const failure = (code) => Object.assign(new Error(code), { code })
// Process-local uncertainty barrier: never persist feedback, tokens or answers.
// A process restart still requires a separately reviewed durable recovery design.
const pendingSaves = new Map()
const MAX_PENDING_SAVES = 256

export function createFeedbackApi({ request, getOwnerId, getAccessToken, getAuthEpoch, enabled = false }) {
  let identity = null, invalid = false, generation = 0, latestEpoch = 0
  const snapshots = new WeakMap()
  const instance = Symbol('feedback instance')
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
    async save(body, key) {
      if (!enabled) throw failure('FEATURE_NOT_READY')
      assertIdentity()
      const event = body?.playback_event_id, music = body?.music_ref?.music_id, context = body?.source_context_id
      if (typeof event !== 'string' || !event || typeof music !== 'string' || !music || typeof context !== 'string' || !context || typeof key !== 'string' || !key) throw failure('FEEDBACK_SOURCE_NOT_FOUND')
      const scope = JSON.stringify([identity.owner,event])
      let entry = pendingSaves.get(scope)
      let serialized
      try { serialized = JSON.stringify(body); if (!serialized) throw new Error('invalid') } catch (error) { throw failure('FEEDBACK_COMMIT_UNVERIFIED') }
      if (entry && (entry.key !== key || entry.music !== music || entry.context !== context || entry.inFlight || entry.instance !== instance || snapshots.get(body) !== serialized)) throw failure('FEEDBACK_COMMIT_UNVERIFIED')
      if (!entry) {
        if (pendingSaves.size >= MAX_PENDING_SAVES) throw failure('FEEDBACK_COMMIT_UNVERIFIED')
        snapshots.set(body,serialized)
        entry = {key,music,context,instance,inFlight:false}; pendingSaves.set(scope,entry)
      }
      entry.inFlight = true
      try {
        const result = await call('POST', '/api/v3/feedback-records', JSON.parse(serialized), key)
        if (!result || typeof result.feedback_id !== 'string' || !result.feedback_id.trim() || result.feedback_id.length > 64 || result.status !== 'saved' || !Number.isSafeInteger(result.current_feedback_epoch) || result.current_feedback_epoch < 0 || typeof result.replayed !== 'boolean' || result.learning_applied !== false) throw failure('FEEDBACK_COMMIT_UNVERIFIED')
        if (pendingSaves.get(scope) === entry) pendingSaves.delete(scope)
        return result
      } catch (error) {
        if (error?.code === 'FEEDBACK_EPOCH_CONFLICT' && pendingSaves.get(scope) === entry) pendingSaves.delete(scope)
        throw error
      } finally { entry.inFlight = false }
    },
    clear: (body, key) => call('POST', '/api/v3/me/feedback-evidence/clear', body, key),
    remove: (id, epoch) => call('DELETE', `/api/v3/feedback-records/${encodeURIComponent(id)}`, { expected_evidence_epoch:epoch }),
    get: id => call('GET', `/api/v3/feedback-records/${encodeURIComponent(id)}`),
    list: ({limit=20,cursor=null,musicId=null}={}) => call('GET', `/api/v3/feedback-records?limit=${limit}${cursor ? '&cursor='+encodeURIComponent(cursor) : ''}${musicId ? '&music_id='+encodeURIComponent(musicId) : ''}`),
    invalidate() { invalid = true; generation++ },
    isCurrent() { try { assertIdentity(); return !invalid } catch (error) { return false } },
    currentEpoch: () => latestEpoch,
  })
}
