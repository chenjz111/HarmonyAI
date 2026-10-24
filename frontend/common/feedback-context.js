/** Single-use in-memory transfer; never writes private context to storage or URLs. */
let pending = null
let sequence = 0
export function putHistoricalFeedback(context, matchesIdentity) {
  if (!context || typeof matchesIdentity !== 'function' || !matchesIdentity()) throw new Error('OWNER_CHANGED')
  const key = `feedback-${Date.now()}-${++sequence}`
  pending = {key, context:JSON.parse(JSON.stringify(context)), matchesIdentity}
  return key
}
export function consumeHistoricalFeedback(key) {
  const transfer = pending
  pending = null
  if (!transfer || transfer.key !== key || !transfer.matchesIdentity()) throw new Error('OWNER_CHANGED')
  return transfer.context
}
