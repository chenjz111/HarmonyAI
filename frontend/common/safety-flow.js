export const SAFETY_DESTINATIONS = Object.freeze({
  VERIFICATION: '/pages/safety-verification/safety-verification',
  SUPPORT: '/pages/safety-support/safety-support',
})

export const COMFORT_FEEDBACK_OPTIONS = Object.freeze([
  { value: 'slightly_stable', label: '稍微稳定一些' },
  { value: 'no_change', label: '没有变化' },
  { value: 'feeling_worse', label: '感觉更糟' },
  { value: 'need_help_now', label: '我现在需要帮助' },
])

export function comfortFeedbackState(feedback) {
  return {
    destination: SAFETY_DESTINATIONS.SUPPORT,
    clearsSafety: false,
    prominentHelp: ['feeling_worse', 'need_help_now'].includes(feedback),
  }
}

export function safetyDestination(assessment = {}) {
  if (assessment.safety_status === 'needs_verification') {
    return ''
  }
  if (['confirmed_mental_health_risk', 'confirmed_acute_physical_risk'].includes(assessment.safety_status)) {
    return SAFETY_DESTINATIONS.SUPPORT
  }
  return ''
}

export function safetyVerificationPayload(assessment, resolution) {
  return { revision: assessment.revision, resolution }
}

export function safetySupportState(assessment = {}) {
  const acute = assessment.safety_status === 'confirmed_acute_physical_risk'
  const mental = assessment.safety_status === 'confirmed_mental_health_risk'
  return {
    mode: acute ? 'acute' : mental ? 'mental' : 'unavailable',
    title: acute ? '请优先获得紧急医疗帮助' : '请先获得现实中的支持',
    comfortAudioVisible: mental && assessment.comfort_audio_allowed === true,
    personalizedPrescriptionAllowed: false,
  }
}
