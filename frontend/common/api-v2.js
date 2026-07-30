/**
 * HarmonyAI API 接口层 — Sprint 3 (v2)
 * 新入口：材料 -> 自由描述 -> 12题图文问卷 -> 分析结果 -> 播放器 -> Feedback 2.0
 * 路由前缀: /api/v2
 */

const BASE_URL = 'http://localhost:8000'
const USE_MOCK = true

/**
 * 上传病历材料
 * @param {String} filePath - 本地文件路径
 * @returns {Promise} { record_id, status, url }
 */
export function uploadRecord(filePath) {
  if (USE_MOCK) {
    return mockRequest({
      record_id: 'rec_' + Date.now(),
      status: 'uploaded',
      url: filePath,
      extracted_text: '患者近一周睡眠不佳，情绪烦躁，食欲减退。',
      confidence: 0.82,
      timestamp: new Date().toISOString()
    })
  }

  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE_URL}/api/v2/records`,
      filePath,
      name: 'record',
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(res.data))
        } else {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail: reject
    })
  })
}

/**
 * 提交自由描述
 * @param {Object} payload { narrative_text, record_id? }
 * @returns {Promise} envelope
 */
export function submitNarrative(payload) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'narrative_agent',
      agent_name: '自由描述Agent',
      run_id: 'run_mock_narrative',
      session_id: 'sess_mock_' + Date.now(),
      user_id: 'u_001',
      status: 'success',
      confidence: 0.78,
      reason: ['mock：从自由描述中提取焦虑、失眠关键词'],
      warnings: [],
      input: payload,
      output: {
        keywords: ['焦虑', '失眠', '烦躁'],
        emotions: [
          { label: '焦虑', score: 0.72 },
          { label: '烦躁', score: 0.58 }
        ]
      },
      timestamp: new Date().toISOString()
    })
  }

  return request({
    url: `${BASE_URL}/api/v2/narrative`,
    method: 'POST',
    data: payload
  })
}

/**
 * 提交 12 题图文问卷
 * @param {Object} payload { session_id, answers, record_id?, narrative_text? }
 * @returns {Promise} assessment envelope
 */
export function submitSurveyV2(payload) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'assessment_agent_v2',
      agent_name: '评估Agent V2',
      run_id: 'run_mock_assess_v2',
      session_id: payload.session_id || 'sess_mock_' + Date.now(),
      user_id: 'u_001',
      status: 'success',
      confidence: 0.86,
      reason: ['mock：综合问卷、自由描述与病历材料'],
      warnings: [],
      input: payload,
      output: {
        emotion_profile: {
          dimensions: [
            { name: '焦虑', score: 72, level: '偏高' },
            { name: '抑郁', score: 45, level: '轻度' },
            { name: '愤怒', score: 58, level: '轻度' },
            { name: '疲惫', score: 65, level: '偏高' },
            { name: '愉悦', score: 32, level: '偏低' }
          ],
          dominant: '焦虑',
          summary: '近期焦虑情绪偏高，伴随疲惫与轻度烦躁。'
        },
        evidence: [
          '睡眠质量题得分偏高',
          '自由描述中提到"睡不着""心烦"',
          '病历材料显示近一周睡眠不佳'
        ],
        degraded: false
      },
      timestamp: new Date().toISOString()
    })
  }

  return request({
    url: `${BASE_URL}/api/v2/assessment`,
    method: 'POST',
    data: payload
  })
}

/**
 * 获取 AI 分析状态
 * @param {String} sessionId
 * @returns {Promise} { status: analyzing|success|degraded|blocked, progress, message }
 */
export function fetchAnalysisStatus(sessionId) {
  if (USE_MOCK) {
    // 模拟一个渐进过程：第一次 analyzing，第二次 success
    const key = `harmony_analysis_status_${sessionId}`
    const current = uni.getStorageSync(key) || 0
    uni.setStorageSync(key, current + 1)

    if (current === 0) {
      return mockRequest({ status: 'analyzing', progress: 35, message: '正在整合问卷与描述信息...' })
    }
    if (current === 1) {
      return mockRequest({ status: 'analyzing', progress: 72, message: '正在匹配中医辨证与音乐处方...' })
    }

    // 重置，便于下次演示
    uni.removeStorageSync(key)
    return mockRequest({ status: 'success', progress: 100, message: '分析完成' })
  }

  return request({
    url: `${BASE_URL}/api/v2/analysis/${sessionId}/status`,
    method: 'GET'
  })
}

/**
 * 获取完整分析结果
 * @param {String} sessionId
 * @returns {Promise} result envelope
 */
export function fetchAnalysisResult(sessionId) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'result_agent_v2',
      agent_name: '结果Agent V2',
      run_id: 'run_mock_result_v2',
      session_id: sessionId,
      user_id: 'u_001',
      status: 'success',
      confidence: 0.84,
      reason: ['mock：多维画像 + 辅助辨证 + 音乐推荐'],
      warnings: [],
      output: {
        profile: {
          dimensions: [
            { name: '焦虑', score: 72, level: '偏高', color: '#F26C5C' },
            { name: '抑郁', score: 45, level: '轻度', color: '#4A6FA5' },
            { name: '愤怒', score: 58, level: '轻度', color: '#F0C75E' },
            { name: '疲惫', score: 65, level: '偏高', color: '#A8B8CC' },
            { name: '愉悦', score: 32, level: '偏低', color: '#52B788' }
          ],
          summary: '近期焦虑情绪偏高，伴随疲惫与轻度烦躁，整体情绪调节能力偏弱。'
        },
        diagnosis: {
          primary: {
            name: '肝郁化火',
            element: '木',
            organ: '肝',
            emotion: '怒',
            severity_level: 3,
            severity_name: '中度'
          },
          auxiliary: [
            { name: '心脾两虚', element: '火', organ: '心', tendency: '32%' },
            { name: '痰湿内阻', element: '土', organ: '脾', tendency: '18%' }
          ],
          evidence: [
            '情绪量表中焦虑维度得分最高（72）',
            '自由描述中提到"心烦""易怒"',
            '睡眠题显示入睡困难、多梦'
          ]
        },
        prescription: {
          music_feature: {
            tone_id: 'jiao',
            tone_name: '角调式',
            bpm: 68,
            instruments: ['古筝', '古琴'],
            duration_minutes: 15
          },
          music_reason: '角调式对应肝木，旋律舒展、节奏舒缓，可帮助疏肝解郁、降肝火。BPM 68 接近静息心率，有助于放松神经。',
          matched: true,
          music_agent: {
            agent_id: 'music_agent_v2',
            matched: true,
            reason: '根据肝郁化火证型匹配角调式，置信度 0.84'
          }
        }
      },
      timestamp: new Date().toISOString()
    })
  }

  return request({
    url: `${BASE_URL}/api/v2/analysis/${sessionId}/result`,
    method: 'GET'
  })
}

/**
 * 获取音频处方
 * @param {String} sessionId
 * @param {Object} prescription
 * @returns {Promise} generation envelope with track_id / audio_url
 */
export function fetchPrescriptionAudio(sessionId, prescription) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'generation_agent_v2',
      agent_name: '生成Agent V2',
      run_id: 'run_mock_gen_v2',
      session_id: sessionId,
      user_id: 'u_001',
      status: 'success',
      confidence: 0.88,
      reason: ['mock：匹配本地角调式疗愈音频'],
      warnings: [],
      output: {
        track_id: 'track_jiao_demo_001',
        audio_url: 'http://localhost:8000/static/music/jiao-demo.wav',
        stream_url: 'http://localhost:8000/static/music/jiao-demo.wav',
        format: 'wav',
        duration_seconds: 30
      },
      timestamp: new Date().toISOString()
    })
  }

  return request({
    url: `${BASE_URL}/api/v2/prescription/audio`,
    method: 'POST',
    data: { session_id: sessionId, prescription }
  })
}

/**
 * 提交 Feedback 2.0
 * @param {Object} payload { session_id, track_id, ratings, comment? }
 */
export function submitFeedbackV2(payload) {
  if (USE_MOCK) {
    return mockRequest({
      agent_id: 'feedback_agent_v2',
      agent_name: '反馈Agent V2',
      run_id: 'run_mock_fb_v2',
      session_id: payload.session_id,
      user_id: 'u_001',
      status: 'success',
      confidence: 0.85,
      reason: ['mock：反馈已保存'],
      warnings: [],
      output: {
        saved: true,
        decision: {
          action: 'continue',
          next_step: 'push_next_day'
        }
      },
      timestamp: new Date().toISOString()
    })
  }

  return request({
    url: `${BASE_URL}/api/v2/feedback`,
    method: 'POST',
    data: payload
  })
}

/**
 * 通用请求封装
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
        reject(new Error(`网络错误：${err.errMsg || '请检查网络连接'}`))
      }
    })
  })
}

function mockRequest(data, delay = 800) {
  return new Promise((resolve, reject) => {
    setTimeout(() => resolve(data), delay)
  })
}
