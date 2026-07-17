/**
 * HarmonyAI API 接口层
 * Sprint 1 阶段使用 mock 数据，后端接口 ready 后替换为真实请求
 */

const BASE_URL = 'http://localhost:8000'  // 后端 FastAPI 地址，后续修改

// 是否使用 mock 数据（后端未就绪时为 true）
const USE_MOCK = true

/**
 * 提交健康评估问卷
 * @param {Object} answers - 问卷答案
 * @returns {Promise} 健康画像结果
 */
export function submitAssessment(answers) {
  if (USE_MOCK) {
    return mockRequest({
      anxiety_score: 82,
      sleep_score: 40,
      body_score: 65,
      syndrome: '肝郁化火',
      confidence: 0.78,
      recommended_tone: '角',
      tone_weights: { '角': 0.75, '宫': 0.15, '羽': 0.10 }
    })
  }
  return uni.request({
    url: BASE_URL + '/assessment',
    method: 'POST',
    data: answers
  })
}

/**
 * 获取音乐处方
 * @param {String} assessmentId - 评估结果ID
 * @returns {Promise} 处方详情
 */
export function getPrescription(assessmentId) {
  if (USE_MOCK) {
    return mockRequest({
      tone: '角',
      tone_weight: 0.75,
      instrument: '古筝',
      bpm: 68,
      reasoning: '肝郁化火 → 角调疏肝理气，辅以宫调健脾安神',
      prompt: '古筝独奏，角调，BPM 68，舒缓宁静',
      confidence: 0.82
    })
  }
  return uni.request({
    url: BASE_URL + '/prescription',
    method: 'GET',
    data: { assessment_id: assessmentId }
  })
}

/**
 * 提交用户反馈
 * @param {Object} feedback - { rating, assessment_id, completed }
 * @returns {Promise}
 */
export function submitFeedback(feedback) {
  if (USE_MOCK) {
    return mockRequest({ success: true })
  }
  return uni.request({
    url: BASE_URL + '/feedback',
    method: 'POST',
    data: feedback
  })
}

// mock 请求模拟器
function mockRequest(data) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(data)
    }, 800)
  })
}
