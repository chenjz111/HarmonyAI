export function createAssessmentFlow(assessment = {}) {
  return { assessment: { ...assessment }, correctionText: '', confirmationStatus: 'idle', confirmationError: '', canRetry: false }
}

export function applyFollowUpRevision(state, response) {
  return { ...state, assessment: { ...response.assessment }, confirmationStatus: 'idle', confirmationError: '', canRetry: false }
}

export function applyCorrectionRevision(state, response, correctionText = state.correctionText) {
  return { ...state, assessment: { ...response.assessment }, correctionText, confirmationStatus: 'idle', confirmationError: '', canRetry: false }
}

export function workflowPayload(state, session) {
  return { ...session, assessment_confirmed: true, assessment_id: state.assessment.assessment_id, assessment_revision: state.assessment.revision }
}

export function confirmationFailed(state, error = {}) {
  return { ...state, confirmationStatus: 'error', confirmationError: error.message || '确认失败，请重试', canRetry: true }
}
