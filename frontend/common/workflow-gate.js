export function workflowGate(workflow) {
  const confirmation = workflow?.confirmation?.status
  if (workflow?.assessment?.status === 'blocked_safety' || confirmation === 'blocked_safety') return { ok: false, code: 'SAFETY_BLOCKED', message: '当前状态需要优先寻求专业帮助，暂不提供音乐。' }
  if (confirmation === 'needs_follow_up') return { ok: false, code: 'NEEDS_FOLLOW_UP', message: '请先完成补充问题。' }
  if (confirmation !== 'confirmed') return { ok: false, code: 'NOT_CONFIRMED', message: '请先确认最新评估结果。' }
  if (workflow?.diagnosis?.abstained === true) return { ok: false, code: 'DIAGNOSIS_ABSTAINED', message: '当前信息不足，暂不提供音乐。' }
  if (!workflow?.prescription) return { ok: false, code: 'PRESCRIPTION_MISSING', message: '后端未返回有效音乐处方。' }
  return { ok: true }
}

export async function resolveAuthoritativeMusic(workflow, sessionId, requestMusic) {
  const gate = workflowGate(workflow)
  if (!gate.ok) throw Object.assign(new Error(gate.message), { code: gate.code })
  if (workflow.music?.stream_url) return workflow.music
  const music = await requestMusic(workflow.prescription, sessionId)
  if (!music?.stream_url) throw Object.assign(new Error('没有匹配到可播放音乐'), { code: 'NO_MUSIC' })
  return music
}
