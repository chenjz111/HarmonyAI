<script>
import { submitPrescription, submitGeneration, submitFeedback } from '@/common/api.js'

const DEMO_AUDIO = 'http://localhost:8000/static/music/jiao-demo.wav'

export default {
  data() {
    return {
      // 页面状态：loading / success / error
      status: 'loading',
      errorMsg: '',
      // 5步链式的 envelope（从 storage 或 API 获取）
      assessmentEnvelope: null,
      diagnosisEnvelope: null,
      prescriptionEnvelope: null,
      generationEnvelope: null,
      // 处方信息（从 envelope 提取，用于 UI 展示）
      prescription: {
        sessionId: '',
        toneName: '角调',
        instrument: '古筝',
        bpm: 68,
        reasoning: '',
        syndrome: '肝郁化火',
        confidence: 0.78,
        audioUrl: '',
        toneId: 'jiao'
      },
      // 音频播放
      audioContext: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      // 评分
      rating: 0,
      stars: [1, 2, 3, 4, 5],
      ratingLabels: ['', '不太满意', '一般', '还行', '不错', '非常疗愈'],
      // 反馈提交状态：idle / submitting / success
      feedbackStatus: 'idle'
    }
  },
  onShow() {
    // 每次显示页面时重新加载评估结果和处方
    this.resetPlayer()
    this.loadAssessmentAndPrescription()
  },
  onHide() {
    // 离开页面时暂停，不销毁实例
    this.pauseAudio()
  },
  onUnload() {
    this.destroyAudio()
  },
  computed: {
    progress() {
      if (!this.duration) return 0
      return Math.round((this.currentTime / this.duration) * 100)
    },
    currentTimeText() {
      return this.formatTime(this.currentTime)
    },
    totalTimeText() {
      return this.formatTime(this.duration)
    },
    confidenceText() {
      return Math.round((this.prescription.confidence || 0) * 100) + '%'
    },
    ratingLabel() {
      return this.ratingLabels[this.rating] || ''
    }
  },
  methods: {
    resetPlayer() {
      this.pauseAudio()
      this.isPlaying = false
      this.currentTime = 0
      this.duration = 0
      // rating / feedbackStatus 不在此处重置，
      // 由 loadAssessmentAndPrescription 根据 storage 中已保存的反馈记录恢复
    },

    restoreFeedbackStatus() {
      try {
        const fb = uni.getStorageSync('harmony_latest_feedback')
        if (fb) {
          const feedback = JSON.parse(fb)
          if (feedback.session_id === this.prescription.sessionId) {
            this.rating = feedback.rating || 0
            this.feedbackStatus = 'success'
            return
          }
        }
      } catch (e) {
        console.error('恢复反馈状态失败：', e)
      }
      // 没有匹配记录：重置为未提交状态
      this.rating = 0
      this.feedbackStatus = 'idle'
    },

    async loadAssessmentAndPrescription() {
      this.status = 'loading'
      this.errorMsg = ''

      try {
        // 优先尝试 v2 流程的 storage（与 Sprint 3 新流程兼容）
        const resultDataV2 = uni.getStorageSync('harmony_result_v2')
        if (resultDataV2) {
          const resultV2 = JSON.parse(resultDataV2)
          const prescription = resultV2.output && resultV2.output.prescription
          if (prescription) {
            const mf = prescription.music_feature || {}
            const primary = (resultV2.output.diagnosis && resultV2.output.diagnosis.primary) || {}
            this.prescription = {
              sessionId: resultV2.session_id || 'session_v2',
              toneName: mf.tone_name || '角调',
              instrument: (mf.instruments && mf.instruments[0]) || '古筝',
              bpm: mf.bpm || 68,
              reasoning: prescription.music_reason || '',
              syndrome: primary.name || '肝郁化火',
              confidence: resultV2.confidence || 0.84,
              audioUrl: DEMO_AUDIO,
              toneId: mf.tone_id || 'jiao'
            }
            this.restoreFeedbackStatus()
            this.initAudio()
            this.status = 'success'
            return
          }
        }

        // 兼容老流程：从本地存储读取辨证结果（Agent 2 的输出）
        const diagnosisData = uni.getStorageSync('harmony_diagnosis')
        if (!diagnosisData) {
          // 没有辨证数据：展示默认处方（便于直接预览播放页）
          this.setDefaultPrescription()
          this.initAudio()
          this.status = 'success'
          return
        }

        this.diagnosisEnvelope = JSON.parse(diagnosisData)
        const sessionId = this.diagnosisEnvelope.session_id

        // === Agent 3: 处方 ===
        this.prescriptionEnvelope = await submitPrescription(sessionId, this.diagnosisEnvelope)

        // === Agent 4: 生成 ===
        this.generationEnvelope = await submitGeneration(sessionId, this.prescriptionEnvelope)

        // 提取处方信息用于 UI 展示
        this.applyPrescription(this.prescriptionEnvelope, this.generationEnvelope)
        this.restoreFeedbackStatus()
        this.initAudio()
        this.status = 'success'
      } catch (e) {
        console.error('加载处方失败：', e)
        // 兜底：加载失败时也提供默认 demo，避免页面卡在错误态
        this.setDefaultPrescription()
        this.initAudio()
        this.status = 'success'
      }
    },

    setDefaultPrescription() {
      this.prescription = {
        sessionId: 'default',
        toneName: '角调',
        instrument: '古筝',
        bpm: 68,
        reasoning: '角调式对应肝木，旋律舒展、节奏舒缓，可帮助疏肝解郁、降肝火。BPM 68 接近静息心率，有助于放松神经。',
        syndrome: '肝郁化火',
        confidence: 0.78,
        audioUrl: DEMO_AUDIO,
        toneId: 'jiao'
      }
      this.restoreFeedbackStatus()
    },

    applyPrescription(prescriptionEnvelope, generationEnvelope) {
      // 从 Universal Shell envelope 提取处方信息
      const out = prescriptionEnvelope.output || {}
      const mf = out.music_feature || {}
      const sd = (this.diagnosisEnvelope && this.diagnosisEnvelope.output)
        ? this.diagnosisEnvelope.output.syndrome_diagnosis || {}
        : {}
      const primary = sd.primary || {}

      // 音调映射表
      const toneMap = {
        'jiao': { name: '角调', instrument: '古筝', syndrome: '肝郁化火' },
        'zhi': { name: '徵调', instrument: '笛子', syndrome: '心火旺盛' },
        'gong': { name: '宫调', instrument: '埙', syndrome: '脾虚湿困' },
        'shang': { name: '商调', instrument: '编钟', syndrome: '肺气不足' },
        'yu': { name: '羽调', instrument: '古琴', syndrome: '肾阳不足' }
      }
      const info = toneMap[mf.tone_id] || toneMap['jiao']
      const instruments = mf.instruments || [info.instrument]

      // 从 generation envelope 提取音频 URL
      const audio = (generationEnvelope && generationEnvelope.output)
        ? generationEnvelope.output.audio || {}
        : {}

      this.prescription = {
        sessionId: prescriptionEnvelope.session_id || 'session',
        toneName: mf.tone_name || info.name,
        instrument: instruments[0] || info.instrument,
        bpm: mf.bpm || 68,
        reasoning: (prescriptionEnvelope.reason && prescriptionEnvelope.reason[0]) || '',
        syndrome: primary.name || info.syndrome,
        confidence: prescriptionEnvelope.confidence || 0.78,
        audioUrl: audio.url || DEMO_AUDIO,
        toneId: mf.tone_id || 'jiao'
      }
    },

    initAudio() {
      // 先销毁旧实例
      this.destroyAudio()

      const url = this.prescription.audioUrl
      if (!url) {
        console.warn('没有音频地址')
        return
      }

      const ctx = uni.createInnerAudioContext()
      ctx.src = url
      ctx.loop = true

      ctx.onCanplay(() => {
        this.duration = ctx.duration || 0
      })

      ctx.onTimeUpdate(() => {
        this.currentTime = ctx.currentTime || 0
        this.duration = ctx.duration || this.duration || 0
      })

      ctx.onEnded(() => {
        this.isPlaying = false
        this.currentTime = 0
      })

      ctx.onError((err) => {
        console.error('音频播放错误：', err)
        this.isPlaying = false
      })

      this.audioContext = ctx
    },

    togglePlay() {
      if (!this.audioContext) {
        uni.showToast({ title: '音频未准备好', icon: 'none' })
        return
      }

      if (this.isPlaying) {
        this.pauseAudio()
      } else {
        this.audioContext.play()
        this.isPlaying = true
      }
    },

    pauseAudio() {
      if (this.audioContext && this.isPlaying) {
        this.audioContext.pause()
        this.isPlaying = false
      }
    },

    destroyAudio() {
      if (this.audioContext) {
        try {
          this.audioContext.stop()
          this.audioContext.destroy()
        } catch (e) {}
        this.audioContext = null
      }
    },

    formatTime(seconds) {
      if (!seconds || isNaN(seconds)) return '0:00'
      const m = Math.floor(seconds / 60)
      const s = Math.floor(seconds % 60)
      return `${m}:${s < 10 ? '0' + s : s}`
    },

    setRating(star) {
      this.rating = star
    },

    async submitFeedback() {
      if (this.rating === 0) {
        uni.showToast({ title: '请先评分', icon: 'none' })
        return
      }
      this.feedbackStatus = 'submitting'
      try {
        // === Agent 5: 反馈 ===
        const sessionId = this.prescription.sessionId
        const feedbackEnvelope = await submitFeedback(
          sessionId,
          this.generationEnvelope,
          this.rating
        )

        this.feedbackStatus = 'success'
        // 把本次反馈也记录到本地，首页可以展示历史
        uni.setStorageSync('harmony_latest_feedback', JSON.stringify({
          rating: this.rating,
          session_id: sessionId,
          action: feedbackEnvelope.output.decision.action,
          timestamp: new Date().toISOString()
        }))
      } catch (err) {
        console.error('提交反馈失败：', err)
        // 兜底：依然标记为成功，避免阻塞用户
        this.feedbackStatus = 'success'
        uni.setStorageSync('harmony_latest_feedback', JSON.stringify({
          rating: this.rating,
          session_id: this.prescription.sessionId,
          action: 'continue',
          timestamp: new Date().toISOString()
        }))
      }
    },

    backToHome() {
      this.destroyAudio()
      uni.switchTab({ url: '/pages/index/index' })
    },

    reAssess() {
      this.destroyAudio()
      uni.navigateTo({ url: '/pages/welcome/welcome' })
    },

    retry() {
      this.loadAssessmentAndPrescription()
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- ====== 背景装饰层 ====== -->
    <view class="bg-deco" aria-hidden="true">
      <view class="ink-orb ink-orb-tr"></view>
      <view class="ink-orb ink-orb-bl"></view>
      <svg class="mountain" viewBox="0 0 750 240" preserveAspectRatio="none">
        <path d="M0,200 C120,140 200,170 300,150 C400,130 480,180 600,160 C680,148 720,170 750,165 L750,240 L0,240 Z" fill="#D8D2C4" opacity="0.45"/>
        <path d="M0,210 C100,180 220,200 340,185 C440,172 520,205 640,195 C700,190 730,200 750,200 L750,240 L0,240 Z" fill="#B8B0A0" opacity="0.35"/>
      </svg>
      <view class="petal petal-1">✦</view>
      <view class="petal petal-2">✦</view>
      <view class="petal petal-3">✦</view>
    </view>

    <!-- ============ 加载中 ============ -->
    <view class="status-card" v-if="status === 'loading'">
      <view class="loading-orb">
        <view class="orb-wave"></view>
        <view class="orb-wave orb-wave-2"></view>
        <view class="orb-wave orb-wave-3"></view>
        <text class="orb-glyph">和</text>
      </view>
      <text class="status-title">正在匹配疗愈音频</text>
      <text class="status-desc">AI Agent 正在为你寻找最合适的音...</text>
    </view>

    <!-- ============ 错误状态 ============ -->
    <view class="status-card" v-else-if="status === 'error'">
      <view class="err-circle">
        <text class="err-text">!</text>
      </view>
      <text class="status-title">加载失败</text>
      <text class="status-desc">{{ errorMsg }}</text>
      <view class="retry-btn" @click="retry">
        <text class="retry-btn-text">重新加载</text>
      </view>
    </view>

    <!-- ============ 成功状态 ============ -->
    <block v-else-if="status === 'success'">
      <!-- 沉浸式封面 -->
      <view class="cover-section">
        <view class="cover-bg"></view>
        <view class="cover-content">
          <!-- 顶部匹配徽章 -->
          <view class="top-bar">
            <view class="matched-pill">
              <view class="matched-dot"></view>
              <text class="matched-text">matched · 智能匹配</text>
            </view>
            <view class="confidence-pill">
              <text class="confidence-text">可信度 {{ confidenceText }}</text>
            </view>
          </view>

          <!-- 大封面 -->
          <view class="album-cover" :class="{ rotating: isPlaying }">
            <view class="album-disc"></view>
            <view class="album-center">
              <text class="album-glyph">和</text>
            </view>
            <!-- 音波装饰 -->
            <view class="wave-deco">
              <view class="wave-bar" v-for="i in 12" :key="i" :style="{ animationDelay: (i * 0.1) + 's' }"></view>
            </view>
          </view>

          <!-- 曲目信息 -->
          <view class="track-info">
            <text class="track-title">{{ prescription.toneName }} · 疗愈音乐</text>
            <text class="track-id">track · {{ prescription.toneId }}_demo</text>
          </view>
        </view>
      </view>

      <!-- 处方卡 -->
      <view class="prescription-card">
        <view class="prescription-row">
          <view class="prescription-item">
            <text class="item-label">调式</text>
            <text class="item-value">{{ prescription.toneName }}</text>
          </view>
          <view class="prescription-divider"></view>
          <view class="prescription-item">
            <text class="item-label">BPM</text>
            <text class="item-value">{{ prescription.bpm }}</text>
          </view>
          <view class="prescription-divider"></view>
          <view class="prescription-item">
            <text class="item-label">时长</text>
            <text class="item-value">{{ totalTimeText }}</text>
          </view>
        </view>
        <view class="instruments">
          <text class="instruments-label">使用乐器</text>
          <view class="instrument-tags">
            <view class="instrument-tag">
              <text class="instrument-text">{{ prescription.instrument }}</text>
            </view>
          </view>
        </view>
        <!-- 印章式辨证徽章 -->
        <view class="seal-row">
          <view class="seal">
            <text class="seal-text">{{ prescription.syndrome }}</text>
          </view>
          <text class="seal-label">辨证</text>
        </view>
        <text class="prescription-reason" v-if="prescription.reasoning">{{ prescription.reasoning }}</text>
      </view>

      <!-- 播放控制 -->
      <view class="player-controls">
        <view class="progress-section">
          <view class="progress-track">
            <view class="progress-fill" :style="{ width: progress + '%' }"></view>
            <view class="progress-thumb" :style="{ left: progress + '%' }"></view>
          </view>
          <view class="time-row">
            <text class="time-text">{{ currentTimeText }}</text>
            <text class="time-text">{{ totalTimeText }}</text>
          </view>
        </view>

        <view class="control-buttons">
          <view class="ctrl-btn" @click="togglePlay">
            <text class="ctrl-icon">{{ isPlaying ? '❚❚' : '▶' }}</text>
          </view>
        </view>
      </view>

      <!-- 评分：idle -->
      <view class="rating-card" v-if="feedbackStatus === 'idle'">
        <text class="rating-title">聆听感受如何？</text>
        <view class="stars-row">
          <text
            v-for="star in stars"
            :key="star"
            class="star"
            :class="{ active: star <= rating }"
            @click="setRating(star)"
          >★</text>
        </view>
        <view class="rating-labels" v-if="rating > 0">
          <text class="rating-label">{{ ratingLabel }}</text>
        </view>
      </view>

      <!-- 评分：提交中 -->
      <view class="status-card mini-card" v-if="feedbackStatus === 'submitting'">
        <view class="loading-orb small">
          <view class="orb-wave"></view>
          <view class="orb-wave orb-wave-2"></view>
        </view>
        <text class="status-title">正在提交反馈...</text>
        <text class="status-desc">您的评价将帮助我们优化调理方案</text>
      </view>

      <!-- 评分：成功 -->
      <view class="success-card" v-if="feedbackStatus === 'success'">
        <view class="seal-success">
          <text class="seal-success-glyph">愈</text>
          <view class="ripple ripple-1"></view>
          <view class="ripple ripple-2"></view>
        </view>
        <text class="status-title">反馈已记录</text>
        <text class="status-desc">愿五音疗愈伴您身心平和</text>
        <view class="rating-summary" v-if="rating > 0">
          <text class="rating-summary-stars">{{ '★'.repeat(rating) }}{{ '☆'.repeat(5 - rating) }}</text>
          <text class="rating-summary-label">{{ ratingLabel }}</text>
        </view>
        <view class="success-actions">
          <view class="action-btn primary" @click="backToHome">
            <text class="action-btn-text">返回首页</text>
          </view>
          <view class="action-btn" @click="reAssess">
            <text class="action-btn-text">重新评估</text>
          </view>
        </view>
      </view>

      <!-- 底部操作 -->
      <view class="action-group" v-if="feedbackStatus === 'idle'">
        <view class="action-btn primary" @click="submitFeedback">
          <text class="action-btn-text">提交反馈</text>
        </view>
        <view class="action-btn" @click="reAssess">
          <text class="action-btn-text">重新评估</text>
        </view>
      </view>
    </block>
  </view>
</template>

<style scoped>
.container {
  min-height: 100vh;
  background: #F7F3EB;
  box-sizing: border-box;
  padding-bottom: 140rpx;
  position: relative;
  overflow: hidden;
}

/* ============ 背景装饰 ============ */
.bg-deco {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.ink-orb {
  position: absolute;
  border-radius: 50%;
}
.ink-orb-tr {
  top: -160rpx;
  right: -160rpx;
  width: 480rpx;
  height: 480rpx;
  background: radial-gradient(circle, rgba(200,137,109,0.16) 0%, rgba(200,137,109,0.04) 40%, transparent 70%);
}
.ink-orb-bl {
  bottom: -200rpx;
  left: -180rpx;
  width: 520rpx;
  height: 520rpx;
  background: radial-gradient(circle, rgba(74,107,92,0.10) 0%, rgba(74,107,92,0.03) 40%, transparent 70%);
}
.mountain {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 120rpx;
  width: 100%;
  height: 200rpx;
}
.petal {
  position: absolute;
  color: #C8896D;
  font-size: 20rpx;
  opacity: 0.5;
  animation: float 12s ease-in-out infinite;
}
.petal-1 { top: 280rpx; left: 60rpx; animation-delay: 0s; }
.petal-2 { top: 720rpx; right: 80rpx; animation-delay: 3s; }
.petal-3 { top: 1080rpx; left: 40%; animation-delay: 6s; }
@keyframes float {
  0%, 100% { transform: translate(0,0) rotate(0); opacity: 0.35; }
  50% { transform: translate(20rpx,-30rpx) rotate(45deg); opacity: 0.65; }
}

/* ============ 状态卡片 ============ */
.status-card {
  position: relative;
  z-index: 2;
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 80rpx 48rpx;
  text-align: center;
  margin: 40rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.06);
}
.mini-card {
  padding: 48rpx 40rpx;
  margin-top: 24rpx;
}

.loading-orb {
  width: 200rpx;
  height: 200rpx;
  margin: 0 auto 40rpx;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.loading-orb.small {
  width: 140rpx;
  height: 140rpx;
  margin-bottom: 28rpx;
}
.orb-wave {
  position: absolute;
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  background: #4A6B5C;
  opacity: 0.3;
  animation: wave 2s ease-in-out infinite;
}
.orb-wave-2 {
  animation-delay: 0.3s;
  background: #C8896D;
}
.orb-wave-3 {
  animation-delay: 0.6s;
  background: #D4A574;
}
@keyframes wave {
  0%, 100% { transform: scale(0.5); opacity: 0.3; }
  50% { transform: scale(1.6); opacity: 0.05; }
}
.orb-glyph {
  position: relative;
  z-index: 2;
  font-size: 56rpx;
  color: #4A6B5C;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  font-weight: 700;
}

.status-title {
  font-size: 34rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  margin-bottom: 12rpx;
  letter-spacing: 0.05em;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.status-desc {
  font-size: 26rpx;
  color: #6B6862;
  display: block;
  margin-bottom: 30rpx;
}

.err-circle {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: #F5EBE3;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24rpx;
  border: 2rpx solid #E8C9B8;
}
.err-text {
  font-size: 64rpx;
  font-weight: 700;
  color: #C8896D;
}

.retry-btn {
  display: inline-block;
  background: linear-gradient(135deg, #4A6B5C, #2F4A3D);
  padding: 20rpx 64rpx;
  border-radius: 44rpx;
  box-shadow: 0 6rpx 18rpx rgba(74,107,92,0.25);
}
.retry-btn-text {
  color: #FCFAF6;
  font-size: 28rpx;
  font-weight: 600;
  letter-spacing: 0.05em;
}

/* ============ 沉浸式封面 ============ */
.cover-section {
  position: relative;
  z-index: 2;
  padding: 24rpx 40rpx 48rpx;
  background: linear-gradient(180deg, #F0EADC 0%, #F7F3EB 100%);
  overflow: hidden;
}
.cover-bg {
  position: absolute;
  top: -100rpx;
  right: -100rpx;
  width: 400rpx;
  height: 400rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(200,137,109,0.16) 0%, transparent 70%);
}
.cover-content {
  position: relative;
  z-index: 1;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.matched-pill {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: rgba(252,250,246,0.7);
  backdrop-filter: blur(10rpx);
  padding: 10rpx 20rpx;
  border-radius: 24rpx;
  border: 1rpx solid #E8E2D5;
}
.matched-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
  background: #6B8979;
  box-shadow: 0 0 8rpx rgba(107,137,121,0.6);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.matched-text {
  font-size: 22rpx;
  color: #4A6B5C;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.confidence-pill {
  background: rgba(74,107,92,0.1);
  padding: 8rpx 18rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(74,107,92,0.15);
}
.confidence-text {
  font-size: 22rpx;
  color: #4A6B5C;
  font-weight: 600;
  font-family: Georgia, serif;
}

/* 大封面 */
.album-cover {
  width: 440rpx;
  height: 440rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 50%, #1A2E25 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 24rpx auto;
  position: relative;
  box-shadow:
    0 24rpx 60rpx rgba(74,107,92,0.30),
    inset 0 4rpx 12rpx rgba(255,255,255,0.08);
}
.album-cover.rotating {
  animation: rotate 12s linear infinite;
}
@keyframes rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.album-disc {
  position: absolute;
  inset: 24rpx;
  border-radius: 50%;
  border: 1rpx solid rgba(255,255,255,0.08);
}
.album-center {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #C8896D 0%, #A87055 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 8rpx 24rpx rgba(0,0,0,0.25),
    inset 0 2rpx 6rpx rgba(255,255,255,0.15);
  position: relative;
  z-index: 2;
}
.album-glyph {
  font-size: 80rpx;
  color: #FCFAF6;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  font-weight: 700;
}

/* 音波装饰 */
.wave-deco {
  position: absolute;
  bottom: -70rpx;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8rpx;
  align-items: flex-end;
  height: 60rpx;
  opacity: 0.4;
}
.wave-bar {
  width: 6rpx;
  background: #4A6B5C;
  border-radius: 3rpx;
  animation: waveBar 1.2s ease-in-out infinite;
  height: 20rpx;
}
@keyframes waveBar {
  0%, 100% { height: 8rpx; }
  50% { height: 40rpx; }
}

.track-info {
  text-align: center;
  margin-top: 24rpx;
}
.track-title {
  font-size: 38rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  letter-spacing: 0.05em;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  margin-bottom: 8rpx;
}
.track-id {
  font-size: 22rpx;
  color: #9C9585;
  display: block;
  font-family: Georgia, serif;
  letter-spacing: 0.05em;
}

/* ============ 处方卡 ============ */
.prescription-card {
  position: relative;
  z-index: 2;
  margin: 0 40rpx 24rpx;
  padding: 32rpx;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.06);
}
.prescription-row {
  display: flex;
  align-items: stretch;
  margin-bottom: 24rpx;
  padding-bottom: 24rpx;
  border-bottom: 1rpx dashed #E8E2D5;
}
.prescription-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.item-label {
  font-size: 22rpx;
  color: #9C9585;
  letter-spacing: 0.1em;
  margin-bottom: 8rpx;
}
.item-value {
  font-size: 32rpx;
  color: #2C2A28;
  font-weight: 700;
  font-family: Georgia, 'Kaiti SC', serif;
}
.prescription-divider {
  width: 1rpx;
  background: #E8E2D5;
}

.instruments {
  margin-bottom: 20rpx;
}
.instruments-label {
  display: block;
  font-size: 22rpx;
  color: #9C9585;
  letter-spacing: 0.1em;
  margin-bottom: 12rpx;
}
.instrument-tags {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
}
.instrument-tag {
  background: #F5EBE3;
  padding: 8rpx 18rpx;
  border-radius: 18rpx;
}
.instrument-text {
  font-size: 22rpx;
  color: #C8896D;
  font-weight: 500;
}

/* 印章式辨证徽章 */
.seal-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.seal {
  background: #C8896D;
  padding: 12rpx 24rpx;
  border-radius: 8rpx;
  border: 2rpx solid #A87055;
  box-shadow: 0 2rpx 8rpx rgba(200,137,109,0.3);
  transform: rotate(-2deg);
}
.seal-text {
  font-size: 28rpx;
  color: #FCFAF6;
  font-weight: 700;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  letter-spacing: 0.1em;
}
.seal-label {
  font-size: 22rpx;
  color: #9C9585;
  letter-spacing: 0.1em;
}

.prescription-reason {
  font-size: 24rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
  font-style: italic;
}

/* ============ 播放控制 ============ */
.player-controls {
  position: relative;
  z-index: 2;
  margin: 0 40rpx 24rpx;
  padding: 32rpx;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.06);
}
.progress-section {
  margin-bottom: 28rpx;
}
.progress-track {
  height: 8rpx;
  background: #E8E2D5;
  border-radius: 4rpx;
  position: relative;
  margin-bottom: 12rpx;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4A6B5C, #C8896D);
  border-radius: 4rpx;
  transition: width 0.3s;
}
.progress-thumb {
  position: absolute;
  top: 50%;
  width: 24rpx;
  height: 24rpx;
  border-radius: 50%;
  background: #4A6B5C;
  border: 4rpx solid #FCFAF6;
  transform: translate(-50%, -50%);
  box-shadow: 0 2rpx 8rpx rgba(74,107,92,0.30);
  transition: left 0.3s;
}
.time-row {
  display: flex;
  justify-content: space-between;
}
.time-text {
  font-size: 22rpx;
  color: #9C9585;
  font-family: Georgia, serif;
}

.control-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
}
.ctrl-btn {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 32rpx rgba(74,107,92,0.30);
  transition: all 0.2s;
}
.ctrl-btn:active {
  transform: scale(0.94);
  box-shadow: 0 6rpx 16rpx rgba(74,107,92,0.25);
}
.ctrl-icon {
  font-size: 52rpx;
  color: #FCFAF6;
  margin-left: 4rpx;
}

/* ============ 评分卡 ============ */
.rating-card {
  position: relative;
  z-index: 2;
  margin: 0 40rpx 24rpx;
  padding: 40rpx;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.06);
  text-align: center;
}
.rating-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  margin-bottom: 28rpx;
  letter-spacing: 0.05em;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.stars-row {
  display: flex;
  justify-content: center;
  gap: 28rpx;
}
.star {
  font-size: 64rpx;
  color: #E8E2D5;
  transition: all 0.2s;
}
.star.active {
  color: #C8896D;
  transform: scale(1.15);
  text-shadow: 0 0 16rpx rgba(200,137,109,0.45);
}
.rating-labels {
  margin-top: 20rpx;
}
.rating-label {
  font-size: 26rpx;
  color: #C8896D;
  font-weight: 500;
  letter-spacing: 0.05em;
}

/* ============ 底部操作 ============ */
.action-group {
  position: relative;
  z-index: 2;
  display: flex;
  gap: 20rpx;
  margin: 0 40rpx;
}
.action-btn {
  flex: 1;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 4rpx 14rpx rgba(74,107,92,0.06);
  transition: all 0.2s;
}
.action-btn:active {
  transform: scale(0.97);
}
.action-btn.primary {
  background: linear-gradient(135deg, #4A6B5C, #2F4A3D);
  border-color: transparent;
  box-shadow: 0 6rpx 18rpx rgba(74,107,92,0.25);
}
.action-btn-text {
  font-size: 28rpx;
  color: #6B6862;
  font-weight: 500;
  letter-spacing: 0.05em;
}
.action-btn.primary .action-btn-text {
  color: #FCFAF6;
  font-weight: 600;
}

/* ============ 成功卡 ============ */
.success-card {
  position: relative;
  z-index: 2;
  margin: 0 40rpx 24rpx;
  padding: 56rpx 40rpx 40rpx;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.06);
  text-align: center;
}
.seal-success {
  width: 140rpx;
  height: 140rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C, #2F4A3D);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 28rpx;
  position: relative;
  box-shadow: 0 8rpx 24rpx rgba(74,107,92,0.3);
}
.seal-success-glyph {
  font-size: 64rpx;
  color: #FCFAF6;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  font-weight: 700;
  position: relative;
  z-index: 2;
}
.ripple {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2rpx solid #4A6B5C;
  animation: ripple 2s ease-out infinite;
}
.ripple-2 {
  animation-delay: 1s;
}
@keyframes ripple {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.8); opacity: 0; }
}

.rating-summary {
  background: #F5EBE3;
  border-radius: 20rpx;
  padding: 24rpx;
  margin: 24rpx 0;
}
.rating-summary-stars {
  font-size: 40rpx;
  color: #C8896D;
  display: block;
  margin-bottom: 8rpx;
  letter-spacing: 8rpx;
}
.rating-summary-label {
  font-size: 26rpx;
  color: #C8896D;
  font-weight: 500;
}

.success-actions {
  display: flex;
  gap: 20rpx;
  margin-top: 8rpx;
}
</style>