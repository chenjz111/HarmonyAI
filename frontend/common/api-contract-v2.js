const encoded = (value) => encodeURIComponent(String(value))

export function assessmentRequest({
  sessionId, userId, documentId = null, documentText = null,
  narrativeText = null, questionnaireAnswers,
}) {
  return {
    path: "/api/v2/assessments",
    method: "POST",
    data: {
      session_id: sessionId,
      user_id: userId,
      document_id: documentId,
      document_text: documentText,
      narrative_text: narrativeText,
      questionnaire_answers: questionnaireAnswers,
    },
  }
}

export function documentConfirmationRequest(documentId, {
  sessionId, confirmed, documentText = null, redactionsConfirmed = confirmed,
}) {
  return {
    path: `/api/v2/documents/${encoded(documentId)}/confirmation`,
    method: "PATCH",
    data: {
      session_id: sessionId,
      confirmed,
      document_text: documentText,
      redactions_confirmed: Boolean(redactionsConfirmed),
    },
  }
}

export function assessmentFollowUpRequest(assessmentId, revision, answers) {
  return {
    path: `/api/v2/assessments/${encoded(assessmentId)}/follow-up`,
    method: "POST",
    data: { revision, answers: answers.slice(0, 4) },
  }
}

export function assessmentConfirmationRequest(assessmentId, {
  revision, confirmationLevel, corrections = [],
}) {
  return {
    path: `/api/v2/assessments/${encoded(assessmentId)}/confirmation`,
    method: "PATCH",
    data: { revision, confirmation_level: confirmationLevel, corrections },
  }
}

export function workflowRequest(payload) {
  return { path: "/api/v2/workflows", method: "POST", data: payload }
}

export function musicRequest(sessionId, prescription) {
  return {
    path: "/api/v2/music",
    method: "POST",
    data: { session_id: sessionId, prescription },
  }
}
