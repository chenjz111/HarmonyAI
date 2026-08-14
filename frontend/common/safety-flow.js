export const SAFETY_DESTINATIONS = Object.freeze({
  VERIFICATION: '/pages/safety-verification/safety-verification',
  SUPPORT: '/pages/safety-support/safety-support',
})

export function safetyDestination(assessment = {}) {
  if (assessment.safety_status === 'needs_verification') {
    return SAFETY_DESTINATIONS.VERIFICATION
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

