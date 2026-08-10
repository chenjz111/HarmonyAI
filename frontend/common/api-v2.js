/**
 * HarmonyAI Sprint 4 API Client v2.1
 * - session-store: 本地会话状态保存恢复
 * - 问卷 V2.1 / Quick State / Assessment / Follow-Up / Confirmation 接口
 * - mock 模式无需后端即可演示
 */

const env = import.meta.env || {}
const BASE_URL = env.VITE_API_BASE_URL || "http://localhost:8000"
const USE_MOCK = env.HARMONYAI_USE_MOCK !== "false" // 默认 mock 模式，无需后端即可演示
const NARRATIVE_PREFIX = ["/api", "v2", "narrative"].join("/")

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

export function confirmDocument(documentId, { confirmed, documentText = "" }) {
  return request(`/api/v2/documents/${encodeURIComponent(documentId)}/confirmation`, {
    method: "PATCH",
    data: { confirmed, document_text: documentText },
  })
}

// ===== Narrative =====

export function submitNarrative({ sessionId, text }) {
  return request(NARRATIVE_PREFIX, {
    method: "POST",
    data: { session_id: sessionId, text },
  })
}

export function getNarrativeStatus(sessionId) {
  return request(`${NARRATIVE_PREFIX}/${encodeURIComponent(sessionId)}/status`)
}

// ===== Questionnaire V2.1 =====

export function submitQuestionnaire({ sessionId, schemaVersion = "questionnaire_v2.1", answers }) {
  return request("/api/v2/questionnaires", {
    method: "POST",
    data: { session_id: sessionId, schema_version: schemaVersion, answers },
  })
}

// ===== Quick State V1 =====

export function submitQuickState({ sessionId, phase, answers }) {
  return request("/api/v2/quick-state", {
    method: "POST",
    data: { session_id: sessionId, phase, schema_version: "quick_state_v1", answers },
  })
}

// ===== Assessment =====

export function submitAssessment(payload) {
  return request("/api/v2/assessments", { method: "POST", data: payload })
}

export function getAssessment(assessmentId) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}`)
}

export function getAssessmentRevisions(assessmentId) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}/revisions`)
}

// ===== Follow-Up =====

export function getFollowUpQuestions(assessmentId) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}/follow-up`)
}

export function submitFollowUpAnswers(assessmentId, answers) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}/follow-up`, {
    method: "POST",
    data: { answers },
  })
}

// ===== Confirmation =====

export function confirmAssessment(assessmentId, { confirmationLevel, corrections = {} }) {
  return request(`/api/v2/assessments/${encodeURIComponent(assessmentId)}/confirmation`, {
    method: "PATCH",
    data: { confirmation_level: confirmationLevel, corrections },
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

function mockResponse(path, data = {}, method = "GET") {
  const sessionId = data?.session_id || data?.sessionId || `sess_mock_${Date.now()}`
  const assessmentId = data?.assessment_id || `asmt_mock_${Date.now()}`

  const table = {
    "/api/v2/sessions": () => ({
      session_id: sessionId,
      status: "active",
      current_step: "document",
      created_at: new Date().toISOString(),
    }),
    "/api/v2/documents": () => ({
      document_id: `doc_mock_${Date.now()}`,
      session_id: sessionId,
      ocr_status: "needs_confirmation",
      ocr_engine: "paddleocr",
      ocr_confidence_avg: 0.91,
      extracted_text: "演示模式 OCR 文本。\n患者近期睡眠不佳，入睡困难约两周。\n情绪偏低，食欲略有下降。",
      evidence_items_extracted: 3,
      warnings: ["当前为显式演示模式"],
    }),
    [NARRATIVE_PREFIX]: () => ({
      narrative_id: `narr_mock_${Date.now()}`,
      session_id: sessionId,
      processing_status: "processed",
      text_length: data?.text?.length || 0,
      extraction_confidence_avg: 0.87,
      evidence_items_extracted: 5,
      warnings: [],
    }),
    "/api/v2/questionnaires": () => ({
      questionnaire_id: `q_mock_${Date.now()}`,
      assessment_id: `asmt_mock_${Date.now()}`,
      session_id: sessionId,
      schema_version: data?.schema_version || "questionnaire_v2.1",
      status: "processed",
      questions_answered: data?.answers?.length || 20,
      scored_dimensions: [
        "tension_worry", "overthinking", "irritability_anger", "fear_unease",
        "low_mood", "interest_loss", "calm_wellbeing", "emotional_recovery",
        "sleep_disturbance", "unrefreshing_sleep", "low_energy",
        "appetite_change", "daily_impact"
      ],
      scored_dimension_count: 13,
      safety_flags: [],
    }),
    "/api/v2/quick-state": () => ({
      quick_state_id: `qs_mock_${Date.now()}`,
      session_id: sessionId,
      phase: data?.phase || "pre_listening",
      schema_version: "quick_state_v1",
      status: "processed",
      scores: data?.answers || [],
    }),
    "/api/v2/music": () => {
      const req = data?.prescription || {}
      const feature = req.music_feature || {}
      const tone = feature.tone_name || req.recommended_tone || "角调"
      const bpm = feature.bpm || 68
      const instruments = feature.instruments || ["古琴", "箫"]
      const modeMap = { 角调: "jiao", 徵调: "zhi", 宫调: "gong", 商调: "shang", 羽调: "yu" }
      const modeKey = modeMap[tone] || "jiao"
      return {
        music_id: `music_${modeKey}_${Date.now()}`,
        session_id: sessionId,
        mode: tone,
        bpm,
        instruments,
        source_type: req.status === "blocked_safety" ? "fallback" : "matched",
        status: req.status === "blocked_safety" ? "degraded" : "success",
        stream_url: `/static/music/jiao-demo.wav`,
        duration_seconds: 30,
        explanation: req.status === "blocked_safety"
          ? "当前状态需要优先关注人身安全，我们为你准备了舒缓的角调式音乐作为辅助支持，请在安全环境下聆听。"
          : (req.explanation || req.music_reason || "根据辅助辨证倾向和音乐参数规则匹配"),
        safety_notice: req.status === "blocked_safety"
          ? "你当前勾选的状态提示存在较高风险。本音乐不能替代专业帮助，如感到无法自控，请立即联系信任的人或拨打心理援助热线。"
          : undefined,
      }
    },
    "/api/v2/assessments": () => ({
      assessment_id: assessmentId,
      session_id: sessionId,
      status: "awaiting_confirmation",
      revision: 1,
      analysis_mode: "document_narrative_questionnaire",
      confidence: 0.76,
      confidence_semantics: "evidence_coverage",
      assessment_summary: "当前状态显示中度紧张与睡眠困扰，情绪偏低但恢复力尚可。建议以角调式辅助放松。",
      user_goal: "relaxation",
      input_processing_status: {
        questionnaire: { version: "questionnaire_v2.1", status: "processed", questions_answered: 20, scored_dimension_count: 13, safety_flags: [] },
        narrative: { status: "processed", text_length: 156, extraction_confidence_avg: 0.87, evidence_items_extracted: 5, warnings: [] },
        document: { status: "confirmed", ocr_engine: "paddleocr", ocr_confidence_avg: 0.91, evidence_items_extracted: 3, warnings: [] },
      },
      emotion_profile: {
        tension_worry: { score: 3.0, severity: "moderate", severity_display: "有一定表现", source: "questionnaire" },
        overthinking: { score: 2.0, severity: "mild", severity_display: "轻微出现", source: "questionnaire" },
        irritability_anger: { score: 1.0, severity: "mild", severity_display: "轻微出现", source: "questionnaire" },
        fear_unease: { score: 2.0, severity: "mild", severity_display: "轻微出现", source: "questionnaire" },
        low_mood: { score: 3.0, severity: "moderate", severity_display: "有一定表现", source: "questionnaire" },
        interest_loss: { score: 1.0, severity: "mild", severity_display: "轻微出现", source: "questionnaire" },
        calm_wellbeing: { score: 1.0, severity: "mild", severity_display: "轻微出现", source: "questionnaire", note: "正向题反向计分" },
        emotional_recovery: { score: 2.0, severity: "mild", severity_display: "轻微出现", source: "questionnaire" },
      },
      physical_profile: {
        sleep_disturbance: { score: 3.0, severity: "moderate", severity_display: "有一定表现" },
        unrefreshing_sleep: { score: 2.0, severity: "mild", severity_display: "轻微出现" },
        low_energy: { score: 2.0, severity: "mild", severity_display: "轻微出现" },
        appetite_change: { direction: "decrease", severity: 2, severity_display: "明显下降" },
        physical_signals: ["neck_tension", "headache"],
      },
      life_events: { triggers: [], impact_level: "moderate" },
      evidence_items: [
        { evidence_id: "ev_001", category: "emotion", label: "tension_worry", display_name: "紧张与担忧", value: 3, polarity: "present", severity: "moderate", severity_display: "有一定表现", time_window: "过去两周", source_type: "questionnaire", source_ref: "q03_tension_worry", confirmed: false, dimension_score: 75 },
        { evidence_id: "ev_002", category: "sleep", label: "sleep_disturbance", display_name: "睡眠困扰", value: 3, polarity: "present", severity: "moderate", severity_display: "有一定表现", time_window: "过去两周", source_type: "questionnaire", source_ref: "q12_sleep_disturbance", confirmed: false, dimension_score: 75 },
        { evidence_id: "ev_003", category: "emotion", label: "low_mood", display_name: "情绪低落", value: 3, polarity: "present", severity: "moderate", severity_display: "有一定表现", time_window: "过去两周", source_type: "narrative", source_ref: "narrative:sentence_2", quote: "最近心情一直不太好", extraction_confidence: 0.89, confirmed: false, dimension_score: 75 },
      ],
      evidence_coverage_score: 0.76,
      source_diversity: { count: 3, sources: ["questionnaire", "narrative", "document"] },
      conflicts: [],
      missing_information: [
        { field: "duration", display_name: "状态持续时间", reason: "narrative 和 questionnaire 均未明确持续时间", severity: "important", candidate_follow_up: { question_id: "fu_duration_001", text: "这些状态大概持续了多久？", type: "single_choice", options: ["少于3天", "3-6天", "1-2周", "2周-1个月", "1-3个月", "超过3个月"] } }
      ],
      follow_up_questions: [
        { follow_up_id: "fu_001", assessment_id: assessmentId, trigger_reason: "duration_unclear", priority: 1, question_id: "fu_duration_001", text: "这些状态大概持续了多久？", type: "single_choice", options: ["少于3天", "3-6天", "1-2周", "2周-1个月", "1-3个月", "超过3个月"], required: true, max_questions_total: 4 }
      ],
      requires_user_confirmation: true,
      safety_flags: [],
      degradation: {},
      warnings: [],
      disclaimer: "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。",
    }),
  }

  // GET requests with path params
  if (path.startsWith("/api/v2/assessments/") && path.includes("/follow-up") && method === "GET") {
    return Promise.resolve(table["/api/v2/assessments"]().follow_up_questions || [])
  }
  if (path.startsWith("/api/v2/assessments/") && path.includes("/follow-up") && method === "POST") {
    const result = table["/api/v2/assessments"]()
    result.revision = 2
    result.follow_up_questions = []
    result.status = "awaiting_confirmation"
    return Promise.resolve(result)
  }
  if (path.startsWith("/api/v2/assessments/") && path.includes("/confirmation") && method === "PATCH") {
    const result = table["/api/v2/assessments"]()
    result.status = data?.confirmation_level === "fully_accurate" ? "confirmed" : "awaiting_confirmation"
    result.revision = (result.revision || 1) + 1
    return Promise.resolve(result)
  }
  if (path.startsWith("/api/v2/assessments/") && path.includes("/revisions") && method === "GET") {
    return Promise.resolve([
      { assessment_id: assessmentId, revision: 1, previous_revision: null, created_at: new Date(Date.now() - 60000).toISOString(), change_summary: "初始评估", changes: [] },
      { assessment_id: assessmentId, revision: 2, previous_revision: 1, created_at: new Date().toISOString(), change_summary: "用户回答了追问", changes: [{ field: "follow_up.fu_001.answer", from: null, to: "1-2周" }] },
    ])
  }
  if (path.startsWith("/api/v2/assessments/") && method === "GET") {
    return Promise.resolve(table["/api/v2/assessments"]())
  }
  if (path.startsWith(NARRATIVE_PREFIX + "/") && path.includes("/status")) {
    return Promise.resolve({ status: "processed", text_length: data?.text?.length || 156, extraction_confidence_avg: 0.87, evidence_items_extracted: 5, warnings: [] })
  }
  if (path.startsWith("/api/v2/documents/") && path.includes("/confirmation") && method === "PATCH") {
    return Promise.resolve({
      document_id: path.split("/")[4] || `doc_mock_${Date.now()}`,
      session_id: sessionId,
      document_text: data?.document_text || "已确认的材料文本",
      ocr_status: "confirmed",
      confirmed_at: new Date().toISOString(),
    })
  }
  if (path === "/api/v2/providers/health") {
    return Promise.resolve({
      qwen: { available: true, latency_ms: 1200 },
      paddleocr: { available: true, latency_ms: 800 },
    })
  }

  const handler = table[path]
  if (handler) return Promise.resolve(handler())
  return Promise.resolve({ status: "mock", session_id: sessionId })
}
