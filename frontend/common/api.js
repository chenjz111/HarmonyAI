/**
 * HarmonyAI API 接口层
 * Sprint 1 阶段可开启 mock 数据，后端 ready 后把 USE_MOCK 设为 false
 */

const BASE_URL = 'http://localhost:8000'  // 后端 FastAPI 地址，联调时替换

// 是否使用 mock 数据（后端未就绪或本地演示时为 true）
const USE_MOCK = true

// mock 失败概率，用于验证 error 三态。0 表示永远成功，0.3 表示 30% 失败
const MOCK_FAIL_RATE = 0

/**
 * 提交健康评估问卷
 * @param {Object} payload - { emotion, tone, answers }
 * @returns {Promise} 评估+辨证结果
 */
export function submitAssessment(payload) {
  if (USE_MOCK) {
    return mockRequest({
      session_id: 'mock-session-' + Date.now(),
      agent_id: 'agent-1-assessment',
      confidence: 0.78,
      timestamp: new Date().toISOString(),
      emotion: payload.emotion,
      tone: payload.tone,
      syndrome: '肝郁化火',
      recommended_tone: '角',
      tone_weights: { '角': 0.75, '宫': 0.15, '羽': 0.10 },
      reasoning: '情绪以怒为主，伴焦虑失眠，辨证属肝郁化火，推荐角调疏肝。'
    })
  }

  return request({
    url: `${BASE_URL}/api/assess`,
    method: 'POST',
    data: payload
  })
}

/**
 * 获取音乐处方
 * @param {String} sessionId - 评估会话 ID
 * @returns {Promise} 处方详情（含音频 URL）
 */
export function getPrescription(sessionId) {
  if (USE_MOCK) {
    return mockRequest({
      session_id: sessionId,
      agent_id: 'agent-3-prescription',
      confidence: 0.82,
      timestamp: new Date().toISOString(),
      tone: '角',
      tone_weight: 0.75,
      instrument: '古筝',
      bpm: 68,
      reasoning: '肝郁化火 → 角调疏肝理气，辅以宫调健脾安神',
      prompt: '古筝独奏，角调，BPM 68，舒缓宁静',
      // 公开可访问的古筝样例音频（无版权争议的演示用）
      audio_url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'
    })
  }

  return request({
    url: `${BASE_URL}/api/prescription/${sessionId}`,
    method: 'GET'
  })
}

/**
 * 提交用户反馈
 * @param {Object} payload - { rating, session_id, completed }
 * @returns {Promise}
 */
export function submitFeedback(payload) {
  if (USE_MOCK) {
    return mockRequest({
      success: true,
      agent_id: 'agent-5-feedback',
      timestamp: new Date().toISOString(),
      decision: 'accepted'
    })
  }

  return request({
    url: `${BASE_URL}/api/feedback`,
    method: 'POST',
    data: payload
  })
}

/**
 * 通用请求封装：把 uni.request 包成 Promise，并统一处理错误
 */
function request(options) {
  return new Promise((resolve, reject) => {
    uni.request({
      ...options,
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
 * @param {Object} data - 要返回的数据
 * @param {Number} delay - 延迟毫秒
 */
function mockRequest(data, delay = 1200) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (MOCK_FAIL_RATE > 0 && Math.random() < MOCK_FAIL_RATE) {
        reject(new Error('网络异常，请稍后重试'))
      } else {
        resolve(data)
      }
    }, delay)
  })
}
