/** HarmonyAI Sprint 3 API client. Real FastAPI is the default. */

const env = import.meta.env || {}
const BASE_URL = env.VITE_API_BASE_URL || "http://localhost:8000"
const USE_MOCK = env.HARMONYAI_USE_MOCK === "true"


export function isMockMode() {
  return USE_MOCK
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
  if (USE_MOCK) return mockResponse(path, data)
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


export function createSession(payload = {}) {
  return request("/api/v2/sessions", {
    method: "POST",
    data: { user_id: "demo_user_001", entry_mode: "full", ...payload },
  })
}


export function uploadDocument({
  filePath,
  sessionId,
  documentType = "other",
  consentConfirmed = true,
}) {
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
          const payload = typeof response.data === "string"
            ? JSON.parse(response.data)
            : response.data
          resolve(unwrapV2(payload))
        } catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}


export function confirmDocument(documentId, { confirmed, documentText = "" }) {
  return request(`/api/v2/documents/${encodeURIComponent(documentId)}/confirmation`, {
    method: "PATCH",
    data: { confirmed, document_text: documentText },
  })
}


export function submitAssessment(payload) {
  return request("/api/v2/assessments", { method: "POST", data: payload })
}


export function runWorkflow(payload) {
  return request("/api/v2/workflows", { method: "POST", data: payload })
}


export function requestMusic(prescription) {
  return request("/api/v2/music", {
    method: "POST",
    data: { prescription },
  })
}


export function submitFeedback(payload) {
  return request("/api/v2/feedback", { method: "POST", data: payload })
}


export function getSession(sessionId) {
  return request(`/api/v2/sessions/${encodeURIComponent(sessionId)}`)
}


function mockResponse(path, data = {}) {
  const sessionId = data?.session_id || data?.sessionId || `sess_mock_${Date.now()}`
  const table = {
    "/api/v2/sessions": { session_id: sessionId, status: "active", current_step: "document" },
    "/api/v2/documents": {
      document_id: `doc_mock_${Date.now()}`,
      session_id: sessionId,
      ocr_status: "needs_confirmation",
      extracted_text: "演示模式 OCR 文本，请用户确认。",
      warnings: ["当前为显式演示模式"],
    },
  }
  return Promise.resolve(table[path] || { status: "mock", session_id: sessionId })
}
