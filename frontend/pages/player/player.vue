<script>
import { submitFeedback } from '@/common/api.js'

export default {
  data() {
    return {
      // 页面状态：loading / success / error
      status: 'loading',
      errorMsg: '',
      // 评估结果（从本地存储读取）
      assessment: null,
      // 播放状态
      isPlaying: false,
      currentTime: '0:00',
      totalTime: '3:45',
      progress: 0,
      // 评分
      rating: 0,
      stars: [1, 2, 3, 4, 5],
      // 处方信息
      prescription: {
        toneName: '角调',
        toneWeight: '75%',
        instrument: '古筝',
        bpm: 68,
        reasoning: '肝郁化火 → 角调疏肝理气，辅以宫调健脾安神',
        syndrome: '肝郁化火'
      }
    }
  },
  onShow() {
    // 每次显示页面时从本地存储读取最新评估结果
    this.loadAssessment()
  },
  methods: {
    loadAssessment() {
      try {
        const data = uni.getStorageSync('harmony_latest_assessment')
        if (data) {
          this.assessment = JSON.parse(data)
          this.updatePrescriptionByAssessment(this.assessment)
          this.status = 'success'
        } else {
          // 没有评估数据，展示默认 mock
          this.status = 'success'
        }
      } catch (e) {
        console.error('读取评估结果失败：', e)
        this.status = 'error'
        this.errorMsg = '读取评估结果失败'
      }
    },
    updatePrescriptionByAssessment(assessment) {
      const tone = assessment.recommended_tone || '角'
      const toneMap = {
        '角': { name: '角调', instrument: '古筝', syndrome: '肝郁化火', reasoning: '角调疏肝理气，辅以宫调健脾安神' },
        '徵': { name: '徵调', instrument: '笛子', syndrome: '心火旺盛', reasoning: '徵调清心降火，辅以羽调滋水涵木' },
        '宫': { name: '宫调', instrument: '埙', syndrome: '脾虚湿困', reasoning: '宫调健脾化湿，辅以商调宣肺理气' },
        '商': { name: '商调', instrument: '编钟', syndrome: '肺气不足', reasoning: '商调补肺益气，辅以宫调培土生金' },
        '羽': { name: '羽调', instrument: '古琴', syndrome: '肾阳不足', reasoning: '羽调温补肾阳，辅以角调疏肝解郁' }
      }
      const info = toneMap[tone] || toneMap['角']
      const weights = assessment.tone_weights || { '角': 0.75 }
      const mainWeight = Math.round((weights[tone] || 0.75) * 100)
      this.prescription.toneName = info.name
      this.prescription.toneWeight = mainWeight + '%'
      this.prescription.instrument = info.instrument
      this.prescription.syndrome = info.syndrome
      this.prescription.reasoning = info.reasoning
    },
    togglePlay() {
      this.isPlaying = !this.isPlaying
      if (this.isPlaying) {
        uni.showToast({ title: '播放中（mock）', icon: 'none' })
      }
    },
    setRating(star) {
      this.rating = star
    },
    async submitFeedback() {
      if (this.rating === 0) {
        uni.showToast({ title: '请先评分', icon: 'none' })
        return
      }
      try {
        await submitFeedback({
          rating: this.rating,
          assessment_id: this.assessment ? 'mock-assessment-id' : '',
          completed: true
        })
        uni.showToast({ title: '感谢您的反馈！', icon: 'success' })
        setTimeout(() => {
          uni.switchTab({ url: '/pages/index/index' })
        }, 1500)
      } catch (err) {
        console.error('提交反馈失败：', err)
        uni.showToast({ title: '提交失败，请重试', icon: 'none' })
      }
    },
    reAssess() {
      uni.navigateTo({ url: '/pages/emotion/emotion' })
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- Loading 状态 -->
    <view class="status-card loading-card" v-if="status === 'loading'">
      <view class="loading-spinner"></view>
      <text class="status-title">正在加载调理方案...</text>
    </view>

    <!-- Error 状态 -->
    <view class="status-card error-card" v-if="status === 'error'">
      <text class="status-icon">⚠️</text>
      <text class="status-title">加载失败</text>
      <text class="status-desc">{{ errorMsg }}</text>
      <view class="retry-btn" @click="loadAssessment">
        <text class="retry-btn-text">重新加载</text>
      </view>
    </view>

    <!-- 成功状态：正常内容 -->
    <block v-if="status === 'success'">
      <!-- 处方信息卡片 -->
      <view class="prescription-card">
        <view class="prescription-header">
          <text class="prescription-title">AI 调理方案</text>
          <text class="prescription-confidence">可信度 78%</text>
        </view>
        <view class="prescription-main">
          <text class="prescription-tone">{{ prescription.toneName }}</text>
          <text class="prescription-weight">{{ prescription.toneWeight }}</text>
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
        <view class="album-cover">
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
            <text class="time-text">{{ currentTime }}</text>
            <text class="time-text">{{ totalTime }}</text>
          </view>
        </view>
      </view>

      <!-- 评分组件 -->
      <view class="rating-section">
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

      <!-- 底部操作 -->
      <view class="action-group">
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
</style>
