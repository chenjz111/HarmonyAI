/**
 * HarmonyAI Sprint 4 API Client v2.1
 * - session-store: 本地会话状态保存恢复
 * - 问卷 V2.1 / Quick State / Assessment / Follow-Up / Confirmation 接口
 * - mock 模式无需后端即可演示
 */

const env = import.meta.env || {}
const BASE_URL = env.VITE_API_BASE_URL || "http://localhost:8000"
const USE_MOCK = env.HARMONYAI_USE_MOCK === "true"

// ===== Session Store =====

const SESSION_KEY = "harmony_session_v2"
const QUESTIONNAIRE_PROGRESS_KEY = "harmony_q_progress_v2"

export function saveSession(session) {
  try {
    uni.setStorageSync(SESSION_KEY, JSON.stringify(session))
  } catch (e) {
    console.warn("[session-store] save failed", e)
  }
}

export function loadSession() {
  try {
    const raw = uni.getStorageSync(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

export function clearSession() {
  try {
    uni.removeStorageSync(SESSION_KEY)
    uni.removeStorageSync(QUESTIONNAIRE_PROGRESS_KEY)
  } catch (e) {
    console.warn("[session-store] clear failed", e)
  }
}

export function saveQuestionnaireProgress(answers, currentIndex) {
  try {
    uni.setStorageSync(QUESTIONNAIRE_PROGRESS_KEY, JSON.stringify({ answers, currentIndex, savedAt: Date.now() }))
  } catch (e) {
    console.warn("[session-store] save questionnaire progress failed", e)
  }
}

export function loadQuestionnaireProgress() {
  try {
    const raw = uni.getStorageSync(QUESTIONNAIRE_PROGRESS_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

export function clearQuestionnaireProgress() {
  try {
    uni.removeStorageSync(QUESTIONNAIRE_PROGRESS_KEY)
  } catch (e) {}
}

// ===== Utilities =====

export function isMockMode() {
  return USE_MOCK
}

export function resolveMediaUrl(url) {
  if (!url || /^https?:\/\//i.test(url)) return url
  // mock 模式下本地静态资源直接走前端 dev server，不拼到后端 BASE_URL
  if (USE_MOCK && url.startsWith("/static/")) return url
  return `${BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`
}

export function unwrapV2(payload) {
  if (payload?.success === true) return payload.data
  const error = new Error(payload?.error?.message || "请求失败，请稍后重试")
  error.code = payload?.error?.code || "UNKNOWN_ERROR"
  error.retryable = Boolean(payload?.error?.retryable)
  error.nextActions = payload?.error?.next_actions || []
  throw error
}

function request(path, { method = "GET", data } = {}) {
  if (USE_MOCK) return mockResponse(path, data, method)
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${path}`,
      method,
      data,
      header: { "content-type": "application/json" },
      success(response) {
        try {
          resolve(unwrapV2(response.data))
        } catch (error) {
          reject(error)
        }
      },
      fail(error) {
        const networkError = new Error("无法连接后端服务，请检查网络或稍后重试")
        networkError.code = "NETWORK_ERROR"
        networkError.cause = error
        reject(networkError)
      },
    })
  })
}

// ===== Session =====

export function createSession(payload = {}) {
  return request("/api/v2/sessions", {
    method: "POST",
    data: { user_id: "demo_user_001", entry_mode: "full", ...payload },
  })
}

export function getSession(sessionId) {
  return request(`/api/v2/sessions/${encodeURIComponent(sessionId)}`)
}

// ===== Document / OCR =====

export function uploadDocument({ filePath, sessionId, documentType = "other", consentConfirmed = true }) {
  if (USE_MOCK) {
    return mockResponse("/api/v2/documents", { sessionId, filePath })
  }
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE_URL}/api/v2/documents`,
      filePath,
      name: "file",
      formData: {
        session_id: sessionId,
        document_type: documentType,
        consent_confirmed: String(consentConfirmed),
      },
      success(response) {
        try {
          const payload = typeof response.data === "string" ? JSON.parse(response.data) : response.data
          resolve(unwrapV2(payload))
        } catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}

export function confirmDocument(documentId, { sessionId, confirmed, documentText = "", redactionsConfirmed = confirmed }) {
  return request(`/api/v2/documents/${encodeURIComponent(documentId)}/confirmation`, {
    method: "PATCH",
    data: {
      session_id: sessionId,
      confirmed,
      document_text: documentText,
      redactions_confirmed: Boolean(redactionsConfirmed),
    },
  })
}

// ===== Assessment =====

export function submitAssessment(payload) {
  return request("/api/v2/assessments", { method: "POST", data: payload })
}

// ===== Follow-Up =====

export function submitFollowUpAnswers(assessmentId, revision, answers) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}/follow-up`, {
    method: "POST",
    data: { revision, answers: answers.slice(0, 4) },
  })
}

// ===== Confirmation =====

export function confirmAssessment(assessmentId, { revision, confirmationLevel, corrections = [] }) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}/confirmation`, {
    method: "PATCH",
    data: { revision, confirmation_level: confirmationLevel, corrections },
  })
}

// ===== Workflow / Music / Feedback =====

export function runWorkflow(payload) {
  return request("/api/v2/workflows", { method: "POST", data: payload })
}

export function requestMusic(prescription, sessionId) {
  return request("/api/v2/music", {
    method: "POST",
    data: { session_id: sessionId, prescription },
  })
}

export function submitFeedback(payload) {
  return request("/api/v2/feedback", { method: "POST", data: payload })
}

// ===== Provider Health =====

export function getProviderHealth() {
  return request("/api/v2/providers/health")
}

// ===== Mock =====

function mockResponse(path, data = {}) {
  const sessionId = data?.session_id || data?.sessionId || ("sess_mock_" + Date.now())
  if (path === "/api/v2/sessions") {
    return Promise.resolve({ session_id: sessionId, status: "active", current_step: "document" })
  }
  if (path === "/api/v2/documents") {
    return Promise.resolve({
      document_id: "doc_mock_" + Date.now(),
      session_id: sessionId,
      ocr_status: "degraded",
      extracted_text: null,
      degradation: { triggered: true, reason_code: "MOCK_MODE", fallback: "manual_or_skip" },
      next_actions: ["manual_input", "skip_document"],
    })
  }
  return Promise.reject(Object.assign(
    new Error("显式 Mock 模式未实现该真实接口"),
    { code: "MOCK_UNAVAILABLE" },
  ))
}