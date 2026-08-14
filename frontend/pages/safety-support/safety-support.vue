<template>
  <view class="page">
    <view class="support-card" :class="support.mode">
      <text class="eyebrow">安全支持</text>
      <text class="title">{{ support.title }}</text>
      <text v-if="support.mode === 'acute'" class="body">你提供的信息包含可能需要立即处理的身体风险。请优先拨打 120 或尽快前往急诊，不要等待音乐缓解。</text>
      <text v-else class="body">现在最重要的是联系可信任的人、专业心理援助或当地紧急服务。HarmonyAI 不会在这个状态下生成个性化音乐处方。</text>
      <button v-if="support.mode === 'acute'" class="primary emergency" @tap="callEmergency">拨打 120</button>
      <button v-else class="primary" @tap="callSupport">联系心理援助热线</button>
    </view>

    <view v-if="support.comfortAudioVisible" class="comfort-card">
      <text class="comfort-title">可选：短时安抚音频</text>
      <text class="body">它来自人工审核的固定曲库，不是个性化处方，不能替代专业帮助，也不会改变当前安全状态。</text>
      <button v-if="!audio" class="secondary" @tap="requestAudio">我已了解，获取安抚音频</button>
      <button v-else class="secondary" @tap="toggleAudio">{{ playing ? '暂停' : '开始播放' }}</button>
      <view v-if="audio" class="feedback">
        <text>听后感受（仅记录体验，不会解除安全状态）</text>
        <view class="chips">
          <text v-for="item in feedbackOptions" :key="item" class="chip" :class="{ active: feedback === item }" @tap="feedback = item">{{ item }}</text>
        </view>
      </view>
      <text v-if="error" class="error">{{ error }}</text>
    </view>
  </view>
</template>

<script>
import { requestComfortAudio, resolveMediaUrl } from '@/common/api-v2.js'
import { getSprint3Session } from '@/common/sprint3-session.js'
import { safetySupportState } from '@/common/safety-flow.js'
import { safeUiError } from '@/common/safe-ui-error.js'

export default {
  data() {
    return { assessment: {}, audio: null, audioContext: null, playing: false, error: '', feedback: '', feedbackOptions: ['稍有缓解', '没有变化', '感觉更不舒服'] }
  },
  computed: { support() { return safetySupportState(this.assessment) } },
  onLoad() { this.assessment = getSprint3Session().assessment || {} },
  onUnload() { if (this.audioContext) this.audioContext.destroy() },
  methods: {
    callEmergency() { uni.makePhoneCall({ phoneNumber: '120' }) },
    callSupport() { uni.showModal({ title: '请联系当地心理援助服务', content: '如有立即危险，请拨打 110 或 120，并联系身边可信任的人。', showCancel: false }) },
    async requestAudio() {
      this.error = ''
      try {
        this.audio = await requestComfortAudio(this.assessment.assessment_id, { revision: this.assessment.revision, user_initiated: true })
        const context = uni.createInnerAudioContext()
        context.src = resolveMediaUrl(this.audio.stream_url)
        context.onPlay(() => { this.playing = true })
        context.onPause(() => { this.playing = false })
        context.onEnded(() => { this.playing = false })
        this.audioContext = context
      } catch (error) {
        this.error = safeUiError(error, 'COMFORT_AUDIO_FAILED').message
      }
    },
    toggleAudio() {
      if (!this.audioContext) return
      if (this.playing) this.audioContext.pause()
      else this.audioContext.play()
    },
  },
}
</script>

<style scoped>
.page { min-height: 100vh; background: #f7f3eb; padding: 44rpx 32rpx; box-sizing: border-box; }
.support-card, .comfort-card { background: #fffdfa; border: 1rpx solid #e5ded1; border-radius: 32rpx; padding: 38rpx 32rpx; margin-bottom: 28rpx; }
.support-card.acute { border-color: #ca6d5b; }
.eyebrow { display: block; color: #9a594c; font-size: 24rpx; margin-bottom: 14rpx; }
.title { display: block; color: #292724; font-size: 40rpx; font-weight: 700; line-height: 1.4; }
.body { display: block; color: #625e57; font-size: 27rpx; line-height: 1.75; margin-top: 20rpx; }
.primary, .secondary { margin-top: 30rpx; border-radius: 22rpx; color: #fff; background: #496b5c; }
.primary.emergency { background: #ae493a; }
.secondary { color: #355849; background: #eef4f0; border: 1rpx solid #b9c8bf; }
.comfort-title { color: #292724; font-size: 32rpx; font-weight: 700; }
.feedback { margin-top: 30rpx; color: #625e57; font-size: 25rpx; }
.chips { display: flex; flex-wrap: wrap; gap: 14rpx; margin-top: 18rpx; }
.chip { padding: 12rpx 18rpx; border: 1rpx solid #d6cec1; border-radius: 24rpx; }
.chip.active { color: #fff; background: #496b5c; }
.error { color: #b54838; display: block; margin-top: 20rpx; }
</style>

