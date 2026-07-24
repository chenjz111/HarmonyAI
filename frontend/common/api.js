/**
 * HarmonyAI API 接口层 — Sprint 2
 * 5个 Agent 接口链式调用，格式对齐蔡子鑫后端 (agent_stubs.py)
 * 路由前缀: /api/v1
 * 链式流程: assessment -> diagnosis -> prescription -> generation -> feedback
 */

const BASE_URL = 'http://localhost:8000'

// 是否使用 mock 数据（true=前端模拟，false=请求真实后端）
const USE_MOCK = false

/**
 * Agent 1 — 评估
 * @param {Object} questionnaire - 问卷数据 { emotion, answers, ... }
 * @returns {Promise} assessment envelope
 */
export function submitAssessment(questionnaire) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'assessment_agent',
      agent_name: '评估Agent',
      agent_layer: 'medical_analysis',
      run_id: 'run_mock_eval',
      session_id: 'sess_mock_' + Date.now(),
      user_id: 'u_001',
      status: 'success',
      confidence: 0.85,
      reason: ['mock：使用提交的问卷数据'],
      warnings: [],
      input: { questionnaire },
      output: { emotion_profile: { dominant_emotion: 'anxiety', dominant_score: 70 } },
      processing_time_ms: 200,
      timestamp: new Date().toISOString(),
      retry_count: 0,
      degradation_triggered: false
    })
  }

  return request({
    url: `${BASE_URL}/api/v1/assessment`,
    method: 'POST',
    data: {
      user_id: 'u_001',
      questionnaire
    }
  })
}

/**
 * Agent 2 — 辨证
 * @param {String} sessionId - 会话ID
 * @param {Object} assessmentEnvelope - Agent 1 返回的完整 envelope
 * @returns {Promise} diagnosis envelope
 */
export function submitDiagnosis(sessionId, assessmentEnvelope) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'diagnosis_agent',
      agent_name: '辨证Agent',
      agent_layer: 'medical_analysis',
      run_id: 'run_mock_diag',
      session_id: sessionId,
      user_id: 'u_001',
      status: 'success',
      confidence: 0.85,
      reason: ['mock：怒情绪映射为肝郁化火'],
      warnings: [],
      input: { assessment: assessmentEnvelope.output },
      output: {
        syndrome_diagnosis: {
          primary: {
            name: '肝郁化火',
            element: '木',
            organ: '肝',
            emotion: '怒',
            severity_level: 3,
            severity_name: '中度'
          }
        },
        search_keywords: ['肝郁化火', '角调式', '疏肝解郁']
      },
      processing_time_ms: 150,
      timestamp: new Date().toISOString(),
      retry_count: 0
    })
  }

  return request({
    url: `${BASE_URL}/api/v1/diagnosis`,
    method: 'POST',
    data: {
      user_id: 'u_001',
      session_id: sessionId,
      assessment: assessmentEnvelope
    }
  })
}

/**
 * Agent 3 — 处方
 * @param {String} sessionId - 会话ID
 * @param {Object} diagnosisEnvelope - Agent 2 返回的完整 envelope
 * @returns {Promise} prescription envelope
 */
export function submitPrescription(sessionId, diagnosisEnvelope) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'prescription_agent',
      agent_name: '处方Agent',
      agent_layer: 'knowledge_mapping',
      run_id: 'run_mock_rx',
      session_id: sessionId,
      user_id: 'u_001',
      status: 'success',
      confidence: 0.82,
      reason: ['mock：肝郁化火对应角调式、68BPM与古筝'],
      warnings: [],
      input: { diagnosis: diagnosisEnvelope.output },
      output: {
        music_feature: {
          tone_id: 'jiao',
          tone_name: '角调式',
          bpm: 68,
          instruments: ['古筝', '古琴'],
          duration_minutes: 15
        },
        prompt_template: {
          template_id: 'CN_V1',
          template_version: '1.0.0',
          text: '请生成一段15分钟的传统五声音阶疗愈音乐，以角调为主要调式，速度为68 BPM。'
        },
        prompt_tags: { tone_id: 'jiao', style: 'healing', duration: '15_minutes' },
        evidence: []
      },
      processing_time_ms: 180,
      timestamp: new Date().toISOString(),
      retry_count: 0
    })
  }

  return request({
    url: `${BASE_URL}/api/v1/prescription`,
    method: 'POST',
    data: {
      user_id: 'u_001',
      session_id: sessionId,
      diagnosis: diagnosisEnvelope
    }
  })
}

/**
 * Agent 4 — 生成
 * @param {String} sessionId - 会话ID
 * @param {Object} prescriptionEnvelope - Agent 3 返回的完整 envelope
 * @returns {Promise} generation envelope
 */
export function submitGeneration(sessionId, prescriptionEnvelope) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'generation_agent',
      agent_name: '生成Agent',
      agent_layer: 'ai_generation',
      run_id: 'run_mock_gen',
      session_id: sessionId,
      user_id: 'u_001',
      status: 'degraded',
      confidence: 0.71,
      reason: ['mock：使用本地曲库示例音频'],
      warnings: ['当前为 Sprint 2 本地曲库 stub'],
      input: { prescription: prescriptionEnvelope.output },
      output: {
        audio: {
          url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
          format: 'mp3'
        }
      },
      processing_time_ms: 300,
      timestamp: new Date().toISOString(),
      retry_count: 0
    })
  }

  return request({
    url: `${BASE_URL}/api/v1/generation`,
    method: 'POST',
    data: {
      user_id: 'u_001',
      session_id: sessionId,
      prescription: prescriptionEnvelope
    }
  })
}

/**
 * Agent 5 — 反馈
 * @param {String} sessionId - 会话ID
 * @param {Object} generationEnvelope - Agent 4 返回的完整 envelope
 * @param {Number} satisfaction - 满意度评分 1-5
 * @returns {Promise} feedback envelope
 */
export function submitFeedback(sessionId, generationEnvelope, satisfaction) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'feedback_agent',
      agent_name: '反馈Agent',
      agent_layer: 'ai_generation',
      run_id: 'run_mock_fb',
      session_id: sessionId,
      user_id: 'u_001',
      status: 'success',
      confidence: 0.8,
      reason: [`mock：用户评分${satisfaction}分，继续当前方案`],
      warnings: [],
      input: { audio: generationEnvelope.output.audio },
      output: {
        decision: {
          action: satisfaction >= 4 ? 'continue' : 'adjust',
          next_step: satisfaction >= 4 ? 'push_next_day' : 'adjust_prescription'
        }
      },
      processing_time_ms: 100,
      timestamp: new Date().toISOString(),
      retry_count: 0
    })
  }

  return request({
    url: `${BASE_URL}/api/v1/feedback`,
    method: 'POST',
    data: {
      user_id: 'u_001',
      session_id: sessionId,
      generation: generationEnvelope,
      overall_satisfaction: satisfaction
    }
  })
}

/**
 * 通用请求封装：把 uni.request 包成 Promise，并统一处理错误
 */
function request(options) {
  return new Promise((resolve, reject) => {
    const isObject = typeof options.data === 'object' && options.data !== null && !(options.data instanceof FormData)
    const body = isObject ? JSON.stringify(options.data) : options.data

    uni.request({
      ...options,
      data: body,
      header: {
        'Content-Type': 'application/json',
        ...(options.header || {})
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${JSON.stringify(res.data)}`))
        }
      },
      fail: (err) => {
        reject(err)
      }
    })
  })
}

/**
 * mock 请求模拟器
 */
function mockRequest(data, delay = 1200) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      resolve(data)
    }, delay)
  })
}
