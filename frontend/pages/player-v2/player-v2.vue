<template>
  <view class="container">
    <!-- 加载中 -->
    <view class="status-card" v-if="status === 'loading'">
      <view class="loading-orb">
        <view class="orb-wave"></view>
        <view class="orb-wave orb-wave-2"></view>
        <view class="orb-wave orb-wave-3"></view>
      </view>
      <text class="status-title">正在匹配疗愈音频</text>
      <text class="status-desc">请稍候，AI Agent 正在为你寻找最合适的音...</text>
    </view>

    <error-state
      v-else-if="status === 'error'"
      title="音频加载失败"
      :message="errorMsg"
      @retry="loadAudio"
    />

    <error-state
      v-else-if="status === 'degraded'"
      title="音频已降级"
      :message="errorMsg"
      :showFallback="true"
      fallbackText="播放示例音频"
      @retry="loadAudio"
      @fallback="playFallback"
    />

    <!-- 播放器主体 -->
    <view v-else-if="status === 'success'">
      <!-- 沉浸式封面 -->
      <view class="cover-section">
        <view class="cover-bg"></view>

        <view class="cover-content">
          <!-- 顶部匹配徽章 -->
          <view class="top-bar">
            <view class="matched-pill" v-if="prescription.matched">
              <view class="matched-dot"></view>
              <text class="matched-text">matched · 智能匹配</text>
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
            <text class="track-id">track · {{ prescription.trackId }}</text>
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
            <view class="instrument-tag" v-for="(inst, idx) in prescription.instruments" :key="idx">
              <text class="instrument-text">{{ inst }}</text>
            </view>
          </view>
        </view>
        <text class="prescription-reason">{{ prescription.reason }}</text>
      </view>

      <!-- 播放控制 -->
      <view class="player-controls">
        <view class="progress-section">
          <view class="progress-track" @click="seek">
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

      <!-- 反馈按钮 -->
      <view class="feedback-btn" @click="goFeedback">
        <text class="feedback-btn-text">听完反馈感受</text>
        <text class="feedback-btn-arrow">›</text>
      </view>
    </view>
  </view>
</template>

<script>
import ErrorState from '@/components/sprint3/error-state.vue'
import { requestMusic, resolveMediaUrl } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'

export default {
  components: { ErrorState },
  data() {
    return {
      status: 'loading', errorMsg: '', audioContext: null, isPlaying: false,
      currentTime: 0, duration: 0, pauseCount: 0,
      prescription: { toneName: '', bpm: 68, instruments: [], reason: '', trackId: '', audioUrl: '', matched: true }
    }
  },
  computed: {
    progress() { return this.duration ? (this.currentTime / this.duration) * 100 : 0 },
    currentTimeText() { return this.formatTime(this.currentTime) },
    totalTimeText() { return this.formatTime(this.duration || 30) }
  },
  onLoad() { this.loadAudio() },
  onHide() { this.pauseAudio() },
  onUnload() { this.destroyAudio() },
  methods: {
    async loadAudio() {
      this.status = 'loading'
      this.errorMsg = ''
      try {
        const session = getSprint3Session()
        const workflow = session.workflow || {}
        const prescription = workflow.prescription
        if (!prescription || prescription.status === 'blocked_safety') {
          throw new Error('当前状态不适合提供普通音乐调养建议')
        }
        let music = workflow.music
        if (!music?.stream_url) music = await requestMusic(prescription, session.session_id)
        if (!music?.stream_url) throw new Error('没有可播放的本地曲目')
        const feature = prescription.music_feature || {}
        this.prescription = {
          toneName: music.mode || feature.tone_name || '角调',
          bpm: music.bpm || feature.bpm || 68,
          instruments: music.instruments || feature.instruments || [],
          reason: prescription.explanation || prescription.music_reason || '根据辅助辨证倾向和音乐参数规则匹配',
          trackId: music.music_id,
          audioUrl: resolveMediaUrl(music.stream_url),
          matched: music.source_type === 'matched'
        }
        updateSprint3Session({
          music,
          prescription_id: workflow.prescription_id || workflow.result_id || `rx_${Date.now()}`
        })
        this.initAudio()
        this.status = 'success'
        if (music.status === 'degraded') {
          uni.showToast({ title: '生成服务不可用，已切换本地曲库', icon: 'none' })
        }
      } catch (error) {
        this.status = 'error'
        this.errorMsg = error.message || '音频加载失败，请检查网络'
      }
    },
    initAudio() {
      this.destroyAudio()
      const ctx = uni.createInnerAudioContext()
      ctx.src = this.prescription.audioUrl
      ctx.onPlay(() => { this.isPlaying = true })
      ctx.onPause(() => { this.isPlaying = false })
      ctx.onStop(() => { this.isPlaying = false; this.currentTime = 0 })
      ctx.onEnded(() => { this.isPlaying = false })
      ctx.onTimeUpdate(() => { this.currentTime = ctx.currentTime || 0; this.duration = ctx.duration || this.duration })
      ctx.onError((error) => { this.status = 'error'; this.errorMsg = '音频播放错误：' + (error.errMsg || '未知错误') })
      this.audioContext = ctx
    },
    togglePlay() {
      if (!this.audioContext) return
      if (this.isPlaying) { this.pauseCount++; this.audioContext.pause() }
      else this.audioContext.play()
    },
    pauseAudio() { if (this.audioContext && this.isPlaying) this.audioContext.pause() },
    destroyAudio() { if (this.audioContext) { this.audioContext.destroy(); this.audioContext = null } },
    seek() {},
    playFallback() {
      this.prescription.audioUrl = resolveMediaUrl('/static/music/jiao-demo.wav')
      this.prescription.trackId = 'music_jiao_001'
      this.initAudio()
      this.status = 'success'
    },
    goFeedback() {
      this.pauseAudio()
      updateSprint3Session({
        playback: {
          listened_seconds: Math.max(0, Math.round(this.currentTime)),
          duration_seconds: Math.max(1, Math.round(this.duration || 30)),
          completion_rate: Math.min((this.currentTime || 0) / (this.duration || 30), 1),
          pause_count: this.pauseCount,
          skip_count: 0
        }
      })
      uni.navigateTo({ url: '/pages/feedback-v2/feedback-v2' })
    },
    formatTime(seconds) {
      const value = Math.floor(seconds || 0)
      return `${Math.floor(value / 60)}:${(value % 60).toString().padStart(2, '0')}`
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #F7F3EB;
  box-sizing: border-box;
}

/* ============ 加载中 ============ */
.status-card {
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 80rpx 48rpx;
  text-align: center;
  margin: 40rpx;
  border: 1rpx solid #E8E2D5;
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
.orb-wave {
  position: absolute;
  width: 60rpx;
  height: 60rpx;
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
  50% { transform: scale(1.2); opacity: 0.1; }
}
.status-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  margin-bottom: 12rpx;
  letter-spacing: 0.05em;
}
.status-desc {
  font-size: 26rpx;
  color: #6B6862;
  display: block;
}

/* ============ 沉浸式封面 ============ */
.cover-section {
  position: relative;
  padding: 32rpx 40rpx 60rpx;
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
  background: radial-gradient(circle, rgba(200, 137, 109, 0.18) 0%, transparent 70%);
}
.cover-content {
  position: relative;
  z-index: 1;
}

.top-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 24rpx;
}
.matched-pill {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: rgba(255, 255, 255, 0.7);
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
  box-shadow: 0 0 8rpx rgba(107, 137, 121, 0.6);
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

/* 大封面 */
.album-cover {
  width: 440rpx;
  height: 440rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 50%, #1A2E25 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 32rpx auto;
  position: relative;
  box-shadow:
    0 24rpx 60rpx rgba(74, 107, 92, 0.30),
    inset 0 4rpx 12rpx rgba(255, 255, 255, 0.08);
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
  border: 1rpx solid rgba(255, 255, 255, 0.08);
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
    0 8rpx 24rpx rgba(0, 0, 0, 0.25),
    inset 0 2rpx 6rpx rgba(255, 255, 255, 0.15);
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
  bottom: -80rpx;
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
  margin: 0 40rpx 24rpx;
  padding: 32rpx;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
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

.prescription-reason {
  font-size: 24rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
  font-style: italic;
}

/* ============ 播放控制 ============ */
.player-controls {
  margin: 0 40rpx 24rpx;
  padding: 32rpx;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
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
  box-shadow: 0 2rpx 8rpx rgba(74, 107, 92, 0.30);
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
  gap: 48rpx;
}
.ctrl-btn {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 32rpx rgba(74, 107, 92, 0.30);
  transition: all 0.2s;
}
.ctrl-btn:active {
  transform: scale(0.94);
  box-shadow: 0 6rpx 16rpx rgba(74, 107, 92, 0.25);
}
.ctrl-icon {
  font-size: 52rpx;
  color: #FCFAF6;
  margin-left: 4rpx;
}

/* ============ 反馈按钮 ============ */
.feedback-btn {
  margin: 8rpx 40rpx 40rpx;
  height: 96rpx;
  border-radius: 48rpx;
  background: #FCFAF6;
  border: 1rpx solid #4A6B5C;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  transition: all 0.2s;
}
.feedback-btn:active {
  background: #EEF1ED;
  transform: scale(0.98);
}
.feedback-btn-text {
  font-size: 28rpx;
  color: #4A6B5C;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.feedback-btn-arrow {
  font-size: 32rpx;
  color: #4A6B5C;
  font-weight: 300;
}
</style>