<script>
import { submitPrescription, submitGeneration, submitFeedback } from '@/common/api.js'

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
        audioUrl: ''
      },
      // 音频播放
      audioContext: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      // 评分
      rating: 0,
      stars: [1, 2, 3, 4, 5],
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
        // 从本地存储读取辨证结果（Agent 2 的输出）
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
        this.status = 'error'
        this.errorMsg = e.message || '加载调理方案失败，请重试'
      }
    },

    setDefaultPrescription() {
      this.prescription = {
        sessionId: 'default',
        toneName: '角调',
        instrument: '古筝',
        bpm: 68,
        reasoning: '肝郁化火 → 角调疏肝理气，辅以宫调健脾安神',
        syndrome: '肝郁化火',
        confidence: 0.78,
        audioUrl: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'
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
        audioUrl: audio.url || 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'
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
        uni.showToast({ title: '音频加载失败', icon: 'none' })
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
        this.audioContext.stop()
        this.audioContext.destroy()
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
        this.feedbackStatus = 'idle'
        uni.showToast({ title: '提交失败，请重试', icon: 'none' })
      }
    },

    backToHome() {
      this.destroyAudio()
      uni.switchTab({ url: '/pages/index/index' })
    },

    reAssess() {
      this.destroyAudio()
      uni.navigateTo({ url: '/pages/emotion/emotion' })
    },

    retry() {
      this.loadAssessmentAndPrescription()
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- Loading 状态 -->
    <view class="status-card loading-card" v-if="status === 'loading'">
      <view class="loading-spinner"></view>
      <text class="status-title">正在生成音乐处方...</text>
      <text class="status-desc">AI 正根据辨证结果生成音乐处方并准备音频</text>
    </view>

    <!-- Error 状态 -->
    <view class="status-card error-card" v-if="status === 'error'">
      <text class="status-icon">⚠️</text>
      <text class="status-title">加载失败</text>
      <text class="status-desc">{{ errorMsg }}</text>
      <view class="retry-btn" @click="retry">
        <text class="retry-btn-text">重新加载</text>
      </view>
    </view>

    <!-- 成功状态：正常内容 -->
    <block v-if="status === 'success'">
      <!-- 处方信息卡片 -->
      <view class="prescription-card">
        <view class="prescription-header">
          <text class="prescription-title">AI 调理方案</text>
          <text class="prescription-confidence">可信度 {{ Math.round((prescription.confidence || 0) * 100) }}%</text>
        </view>
        <view class="prescription-main">
          <text class="prescription-tone">{{ prescription.toneName }}</text>
          <text class="prescription-weight">{{ prescription.instrument }}</text>
        </view>
        <view class="prescription-detail">
          <view class="detail-row">
            <text class="detail-label">辨证</text>
            <text class="detail-value">{{ prescription.syndrome }}</text>
          </view>
          <view class="detail-row">
            <text class="detail-label">主奏乐器</text>
            <text class="detail-value">{{ prescription.instrument }}</text>
          </view>
          <view class="detail-row">
            <text class="detail-label">节拍</text>
            <text class="detail-value">{{ prescription.bpm }} BPM</text>
          </view>
        </view>
        <view class="reasoning-box">
          <text class="reasoning-text">{{ prescription.reasoning }}</text>
        </view>
      </view>

      <!-- 播放器 -->
      <view class="player-section">
        <view class="album-cover" :class="{ rotating: isPlaying }">
          <text class="album-icon">🎵</text>
        </view>
        <view
          class="play-button"
          :class="{ playing: isPlaying }"
          @click="togglePlay"
        >
          <text class="play-icon">{{ isPlaying ? '❚❚' : '▶' }}</text>
        </view>
        <view class="progress-section">
          <view class="progress-track">
            <view class="progress-fill" :style="{ width: progress + '%' }"></view>
          </view>
          <view class="time-row">
            <text class="time-text">{{ currentTimeText }}</text>
            <text class="time-text">{{ totalTimeText }}</text>
          </view>
        </view>
      </view>

      <!-- 评分与反馈：idle 状态 -->
      <view class="rating-section" v-if="feedbackStatus === 'idle'">
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
          <text class="rating-label">{{ ['', '不太满意', '一般', '还行', '不错', '非常疗愈'][rating] }}</text>
        </view>
      </view>

      <!-- 提交中 -->
      <view class="status-card feedback-card" v-if="feedbackStatus === 'submitting'">
        <view class="loading-spinner"></view>
        <text class="status-title">正在提交反馈...</text>
        <text class="status-desc">您的评价将帮助我们优化调理方案</text>
      </view>

      <!-- 提交成功 -->
      <view class="status-card feedback-card feedback-success" v-if="feedbackStatus === 'success'">
        <text class="success-icon">✓</text>
        <text class="status-title">反馈提交成功</text>
        <text class="status-desc">感谢您的聆听，愿五音疗愈伴您身心平和</text>
        <view class="rating-summary" v-if="rating > 0">
          <text class="rating-summary-stars">{{ '★'.repeat(rating) + '☆'.repeat(5 - rating) }}</text>
          <text class="rating-summary-label">{{ ['', '不太满意', '一般', '还行', '不错', '非常疗愈'][rating] }}</text>
        </view>
        <view class="retry-btn" @click="backToHome">
          <text class="retry-btn-text">返回首页</text>
        </view>
      </view>

      <!-- 底部操作 -->
      <view class="action-group" v-if="feedbackStatus === 'idle'">
        <view class="action-btn action-btn-primary" @click="submitFeedback">
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
  padding: 30rpx;
  padding-bottom: 120rpx;
  min-height: 100vh;
  background: #F8F8F8;
}

/* 状态卡片 */
.status-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 60rpx 40rpx;
  margin-top: 60rpx;
  text-align: center;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.loading-spinner {
  width: 80rpx;
  height: 80rpx;
  border: 6rpx solid #E8E8E8;
  border-top-color: #534AB7;
  border-radius: 50%;
  margin: 0 auto 30rpx;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.status-icon {
  font-size: 64rpx;
  display: block;
  margin-bottom: 16rpx;
}
.status-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
  margin-bottom: 12rpx;
}
.status-desc {
  font-size: 26rpx;
  color: #888780;
  display: block;
  margin-bottom: 30rpx;
}
.retry-btn {
  display: inline-block;
  background: #534AB7;
  padding: 20rpx 60rpx;
  border-radius: 44rpx;
}
.retry-btn-text {
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
}

/* 处方卡片 */
.prescription-card {
  background: linear-gradient(135deg, #534AB7, #7F77DD);
  border-radius: 28rpx;
  padding: 40rpx;
  margin-bottom: 40rpx;
}
.prescription-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}
.prescription-title {
  font-size: 28rpx;
  color: rgba(255,255,255,0.8);
}
.prescription-confidence {
  font-size: 22rpx;
  color: rgba(255,255,255,0.7);
  background: rgba(255,255,255,0.15);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}
.prescription-main {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
  margin-bottom: 30rpx;
}
.prescription-tone {
  font-size: 56rpx;
  font-weight: 700;
  color: #fff;
}
.prescription-weight {
  font-size: 32rpx;
  color: rgba(255,255,255,0.7);
}

.prescription-detail {
  margin-bottom: 24rpx;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 14rpx 0;
  border-bottom: 1rpx solid rgba(255,255,255,0.1);
}
.detail-label {
  font-size: 26rpx;
  color: rgba(255,255,255,0.6);
}
.detail-value {
  font-size: 26rpx;
  color: #fff;
  font-weight: 500;
}

.reasoning-box {
  background: rgba(255,255,255,0.12);
  border-radius: 16rpx;
  padding: 24rpx;
  margin-top: 20rpx;
}
.reasoning-text {
  font-size: 24rpx;
  color: rgba(255,255,255,0.85);
  line-height: 1.6;
}

/* 播放器 */
.player-section {
  background: #fff;
  border-radius: 28rpx;
  padding: 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.album-cover {
  width: 200rpx;
  height: 200rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #EEEDFE, #E1F5EE);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 30rpx;
}
.album-cover.rotating {
  animation: rotate 8s linear infinite;
}
@keyframes rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.album-icon {
  font-size: 80rpx;
}
.play-button {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: #534AB7;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 30rpx;
  box-shadow: 0 8rpx 30rpx rgba(83,74,183,0.3);
  transition: all 0.2s;
}
.play-button.playing {
  transform: scale(0.95);
}
.play-icon {
  font-size: 48rpx;
  color: #fff;
  margin-left: 8rpx;
}
.play-button.playing .play-icon {
  margin-left: 0;
  font-size: 40rpx;
}

/* 进度条 */
.progress-section {
  width: 100%;
}
.progress-track {
  height: 8rpx;
  background: #E8E8E8;
  border-radius: 4rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #534AB7;
  border-radius: 4rpx;
  transition: width 0.3s;
}
.time-row {
  display: flex;
  justify-content: space-between;
  margin-top: 12rpx;
}
.time-text {
  font-size: 22rpx;
  color: #888780;
}

/* 评分 */
.rating-section {
  background: #fff;
  border-radius: 28rpx;
  padding: 40rpx;
  text-align: center;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.rating-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
  margin-bottom: 24rpx;
}
.stars-row {
  display: flex;
  justify-content: center;
  gap: 24rpx;
}
.star {
  font-size: 60rpx;
  color: #E8E8E8;
  transition: all 0.15s;
}
.star.active {
  color: #FAC775;
  transform: scale(1.1);
}
.rating-labels {
  margin-top: 16rpx;
}
.rating-label {
  font-size: 26rpx;
  color: #854F0B;
  font-weight: 500;
}

/* 底部操作 */
.action-group {
  display: flex;
  gap: 20rpx;
}
.action-btn {
  flex: 1;
  height: 88rpx;
  border-radius: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.action-btn-text {
  font-size: 28rpx;
  color: #5F5E5A;
  font-weight: 500;
}
.action-btn-primary {
  background: #534AB7;
}
.action-btn-primary .action-btn-text {
  color: #fff;
}

/* 反馈提交状态卡片 */
.feedback-card {
  background: #fff;
  border-radius: 28rpx;
  padding: 60rpx 40rpx;
  text-align: center;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.feedback-success .success-icon {
  width: 100rpx;
  height: 100rpx;
  line-height: 100rpx;
  border-radius: 50%;
  background: #E1F5EE;
  color: #4A9D6E;
  font-size: 52rpx;
  font-weight: 700;
  display: inline-block;
  margin-bottom: 24rpx;
}
.rating-summary {
  background: #FAF7F0;
  border-radius: 16rpx;
  padding: 24rpx;
  margin: 24rpx 0;
}
.rating-summary-stars {
  font-size: 40rpx;
  color: #FAC775;
  display: block;
  margin-bottom: 8rpx;
  letter-spacing: 8rpx;
}
.rating-summary-label {
  font-size: 26rpx;
  color: #854F0B;
  font-weight: 500;
}
</style>
