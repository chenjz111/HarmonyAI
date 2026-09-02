<script>
/**
 * V3 音乐播放页
 * 合同依据：frontend-read-model-contract-v3.md §12 PlayerReadModel
 *
 * - 只播放后端返回的 asset（stream_url），前端不构造处方
 * - source_label 区分"AI生成音乐"与"审核曲库匹配音乐"（不伪装实时生成）
 * - 不展示任何目标类字段（该概念已在 V3 删除，Amendment §5）
 * - 保留非诊断/非治疗免责声明
 * - 收藏走真实 Favorites API（music_ref），mock/hybrid 由 facade 本地记录
 * - hybrid 模式显示"演示数据"标识
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      music: null,
      playing: false,
      audioCtx: null,
      favorite: false,
      favBusy: false,
      simulated: false, // hybrid：演示数据标识
    }
  },
  computed: {
    audioSrc() {
      if (!this.music || !this.music.stream_url) return ""
      // 相对路径（/api/...）补全后端地址；本地 /static 与绝对地址原样使用
      return apiV3.musicStreamUrl(this.music.stream_url)
    },
  },
  onLoad() {
    this.load()
  },
  onUnload() {
    this.stopAudio()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ""
      try {
        this.music = await apiV3.getMusic()
        this.favorite = !!this.music.favorite
        this.simulated = !!apiV3.AGENT_SIMULATED
      } catch (e) {
        if (e.agentPending) {
          // real 模式：音乐生成能力未接入，明确等待状态，不伪造音乐
          this.error = e.message
        } else {
          this.error = e.message || "音乐加载失败，请重试"
        }
      } finally {
        this.loading = false
      }
    },
    togglePlay() {
      if (this.playing) {
        this.pause()
      } else {
        this.play()
      }
    },
    async play() {
      if (!this.audioSrc || this.playing) return
      try {
        // P0-3：后端音频流要求 Bearer 头，audio 标签无法携带；
        // 先经带鉴权的 downloadFile 拉取为本地临时文件再播放，失败如实提示
        const src = await apiV3.fetchAuthorizedAudio(this.music.stream_url)
        if (!this.audioCtx) {
          this.audioCtx = uni.createInnerAudioContext()
          this.audioCtx.onError(() => {
            // 播放失败：安全降级文案，不暴露原始错误
            this.playing = false
            uni.showToast({ title: "播放失败，请稍后重试", icon: "none" })
          })
          this.audioCtx.onEnded(() => { this.playing = false })
        }
        this.audioCtx.src = src
        this.audioCtx.play()
        this.playing = true
      } catch (e) {
        this.playing = false
        uni.showToast({ title: e.message || "播放失败，请稍后重试", icon: "none" })
      }
    },
    pause() {
      if (this.audioCtx) this.audioCtx.pause()
      this.playing = false
    },
    stopAudio() {
      if (this.audioCtx) {
        this.audioCtx.destroy()
        this.audioCtx = null
      }
      this.playing = false
    },
    // 收藏：走真实 Favorites API（music_ref.music_id + source_type）
    async toggleFavorite() {
      if (this.favBusy) return
      const ref = this.music.music_ref || {}
      const musicId = ref.music_id
      if (!musicId) {
        uni.showToast({ title: "收藏失败：缺少音乐标识", icon: "none" })
        return
      }
      this.favBusy = true
      const target = !this.favorite
      try {
        if (target) {
          await apiV3.addFavorite(musicId, ref.source_type)
        } else {
          await apiV3.removeFavorite(musicId)
        }
        this.favorite = target
        uni.showToast({ title: target ? "已收藏" : "已取消收藏", icon: "none" })
      } catch (e) {
        uni.showToast({ title: e.message || "操作失败，请重试", icon: "none" })
      } finally {
        this.favBusy = false
      }
    },
    formatDuration(sec) {
      const m = Math.floor(sec / 60)
      const s = sec % 60
      return (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s)
    },
    goFeedback() {
      this.stopAudio()
      // V3 流程进入 V3 反馈页（feedback_v3.0），不再复用 V2 反馈页
      // 本页是 tabBar 页面，用 navigateTo 跳转非 tab 页
      uni.navigateTo({ url: "/pages/v3-feedback/v3-feedback" })
    },
  },
}
</script>

<template>
  <view class="container v3-visual-page v3-one-screen-page player-page">
    <view class="flow-shell">
    <view class="header">
      <text class="step-tag">音乐调养</text>
      <text class="player-heading">本次生成结果</text>
      <text class="player-subheading">为当前状态准备的一段安静音乐</text>
    </view>

    <view v-if="loading" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在准备音乐…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <view class="error-mark" aria-hidden="true"><view class="error-mark-dot"></view></view>
      <text class="error-title">音乐暂时还没有准备好</text>
      <text class="error-description">生成服务可能暂时繁忙，你可以重新尝试。</text>
      <text class="error-detail">{{ error }}</text>
      <view class="error-actions">
        <view class="btn-retry" @click="load"><text class="btn-retry-text">重新尝试</text></view>
      </view>
      <view class="error-secondary-space" aria-hidden="true"></view>
    </view>

    <view v-else class="player-card">
      <!-- hybrid 演示标识 -->
      <view v-if="simulated" class="demo-banner">
        <text class="demo-banner-text">演示模式：当前音乐为模拟数据</text>
      </view>

      <!-- 唱片 -->
      <view class="disc breathing-artwork" :class="{ 'disc-spinning': playing }">
        <view class="breathing-ring breathing-ring-one"></view>
        <view class="breathing-ring breathing-ring-two"></view>
        <view class="disc-inner">
          <text class="disc-tone">{{ music.tone_label ? music.tone_label.substring(0, 1) : "宫" }}</text>
        </view>
      </view>

      <view class="music-identity">
        <text class="music-title">{{ music.title }}</text>
        <text class="music-source">{{ music.source_label }} · {{ music.tone_label }}</text>
      </view>
      <view class="music-parameter-summary">
        <text class="music-instruments">{{ music.instrument_labels.join(" · ") }}</text>
        <text class="parameter-duration">时长 {{ formatDuration(music.duration_seconds) }}</text>
      </view>

      <!-- 控制区 -->
      <view class="controls">
        <view class="ctrl-fav" @click="toggleFavorite">
          <text class="ctrl-fav-icon" :class="{ 'fav-active': favorite }">{{ favorite ? "♥" : "♡" }}</text>
        </view>
        <view class="ctrl-play" @click="togglePlay">
          <view v-if="playing" class="control-icon control-icon--pause"><view></view><view></view></view>
          <view v-else class="control-icon control-icon--play"></view>
        </view>
        <view class="ctrl-duration">
          <text class="ctrl-duration-text">本次</text>
        </view>
      </view>

      <!-- 免责声明（必须保留） -->
      <view class="disclaimer-box">
        <text class="disclaimer-text">{{ music.disclaimer }}</text>
      </view>

      <view class="actions">
        <view class="btn-primary" @click="goFeedback">
          <text class="btn-primary-text">完成收听，填写反馈</text>
        </view>
      </view>
    </view>
    </view>
  </view>
</template>

<style lang="scss">
@use "../../styles/v3-visual-tokens.scss" as v3;
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 70rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header { margin-bottom: 24rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4a6b5c;
  background: #e6ebe5;
  border-radius: 8rpx;
  padding: 6rpx 16rpx;
}
.player-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 56rpx 40rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.disc {
  width: 300rpx;
  height: 300rpx;
  border-radius: 50%;
  background: radial-gradient(circle, #4a6b5c 0%, #3a5548 60%, #2f443a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 44rpx;
  box-shadow: 0 16rpx 40rpx rgba(74, 107, 92, 0.3);
}
.disc-spinning { animation: discspin 8s linear infinite; }
@keyframes discspin { to { transform: rotate(360deg); } }
.disc-inner {
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  background: #f7f3eb;
  display: flex;
  align-items: center;
  justify-content: center;
}
.disc-tone { font-size: 44rpx; color: #4a6b5c; font-weight: 600; }
.music-title { font-size: 38rpx; font-weight: 600; color: #2f3d35; margin-bottom: 12rpx; }
.music-source { font-size: 26rpx; color: #7a8078; margin-bottom: 8rpx; }
.music-instruments { font-size: 24rpx; color: #b3ac9c; margin-bottom: 48rpx; }
.controls {
  display: flex;
  align-items: center;
  gap: 56rpx;
  margin-bottom: 44rpx;
}
.ctrl-fav { width: 80rpx; height: 80rpx; display: flex; align-items: center; justify-content: center; }
.ctrl-fav-icon { font-size: 44rpx; color: #c9c3b2; }
.fav-active { color: #b0574f; }
.ctrl-play {
  width: 130rpx;
  height: 130rpx;
  border-radius: 50%;
  background: #4a6b5c;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10rpx 30rpx rgba(74, 107, 92, 0.35);
}
.ctrl-play-icon { font-size: 52rpx; color: #fff; }
.ctrl-duration { width: 80rpx; display: flex; justify-content: center; }
.ctrl-duration-text { font-size: 24rpx; color: #9c9585; }
.disclaimer-box {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 24rpx;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 36rpx;
}
.disclaimer-text { font-size: 22rpx; color: #9c9585; line-height: 1.6; text-align: center; }
.actions { width: 100%; }
.btn-primary {
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 26rpx 0;
  display: flex;
  justify-content: center;
}
.btn-primary-text { color: #fff; font-size: 30rpx; }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; }
.loading-ring {
  width: 72rpx; height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { margin-top: 24rpx; font-size: 26rpx; color: #9c9585; }
.error-wrap { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; }
.error-text { font-size: 28rpx; color: #b0574f; margin-bottom: 32rpx; }
.btn-retry { padding: 20rpx 64rpx; background: #4a6b5c; border-radius: 44rpx; }
.btn-retry-text { color: #fff; font-size: 28rpx; }
.demo-banner { display: flex; justify-content: center; margin-bottom: 24rpx; width: 100%; }
.demo-banner-text {
  font-size: 22rpx;
  color: #8a6d3b;
  background: #f5eddc;
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
}

.container { @include v3.v3-page; background: radial-gradient(circle at 50% 24%, rgba(78, 116, 104, .11), transparent 34%), v3.$v3-background; }
.flow-shell { @include v3.v3-flow-shell; }
.header { margin: 0 0 v3.$v3-space-6; }
.step-tag { margin-bottom: v3.$v3-space-3; padding: 7px 12px; border-radius: v3.$v3-radius-pill; color: v3.$v3-primary-dark; background: rgba(78, 116, 104, .1); font-size: 12px; font-weight: 650; }
.player-heading { display: block; margin-bottom: v3.$v3-space-2; color: v3.$v3-text-primary; font-size: clamp(28px, 4.5vw, 36px); font-weight: 680; letter-spacing: -.025em; line-height: 1.25; }
.player-subheading { display: block; color: v3.$v3-text-secondary; font-size: 14px; line-height: 1.6; }
.player-card { padding: v3.$v3-space-8; border: 1px solid rgba(227, 231, 226, .9); border-radius: 30px; background: rgba(255, 255, 255, .9); box-shadow: v3.$v3-shadow-raised; backdrop-filter: blur(16px); }
.breathing-artwork { position: relative; width: min(255px, 62vw); height: min(255px, 62vw); margin: v3.$v3-space-3 0 v3.$v3-space-6; overflow: visible; background: radial-gradient(circle at 38% 32%, #76998f 0%, v3.$v3-primary 40%, v3.$v3-primary-dark 100%); box-shadow: 0 26px 60px rgba(54, 88, 79, .26); }
.breathing-ring { position: absolute; inset: -12px; border: 1px solid rgba(78, 116, 104, .18); border-radius: 50%; animation: breathe 5.5s ease-in-out infinite; }
.breathing-ring-two { inset: -26px; opacity: .55; animation-delay: -2.75s; }
@keyframes breathe { 0%, 100% { transform: scale(.96); opacity: .35; } 50% { transform: scale(1.04); opacity: .82; } }
.disc-inner { position: relative; z-index: 2; width: 96px; height: 96px; background: rgba(246, 247, 243, .94); box-shadow: inset 0 0 0 1px rgba(78, 116, 104, .12); }
.disc-tone { color: v3.$v3-primary-dark; font-family: v3.$v3-font-family; font-size: 34px; font-weight: 500; }
.music-identity { width: 100%; margin-bottom: v3.$v3-space-5; text-align: center; }
.music-title { display: block; margin-bottom: v3.$v3-space-2; color: v3.$v3-text-primary; font-size: clamp(24px, 4vw, 30px); font-weight: 680; line-height: 1.35; }
.music-source { display: block; margin: 0; color: v3.$v3-text-secondary; font-size: 14px; }
.music-parameter-summary { width: 100%; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: v3.$v3-space-2; margin-bottom: v3.$v3-space-6; }
.music-instruments, .parameter-duration { margin: 0; padding: 8px 12px; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-pill; background: v3.$v3-background; color: v3.$v3-text-secondary; font-size: 12px; line-height: 1.3; }
.controls { width: 100%; justify-content: center; gap: clamp(24px, 8vw, 52px); margin-bottom: v3.$v3-space-8; }
.ctrl-fav, .ctrl-duration { width: 54px; height: 54px; border: 1px solid v3.$v3-border; border-radius: 50%; background: v3.$v3-surface; display: flex; align-items: center; justify-content: center; }
.ctrl-fav { @include v3.v3-focusable; }
.ctrl-fav-icon { color: v3.$v3-text-muted; font-size: 27px; }
.fav-active { color: v3.$v3-danger; }
.ctrl-play { width: 76px; height: 76px; background: v3.$v3-primary; box-shadow: 0 14px 30px rgba(78, 116, 104, .28); @include v3.v3-focusable; }
.ctrl-play-icon { color: v3.$v3-surface; font-size: 30px; }
.control-icon { position: relative; display: block; }
.control-icon--play { width: 0; height: 0; margin-left: 4px; border-top: 12px solid transparent; border-bottom: 12px solid transparent; border-left: 19px solid v3.$v3-surface; }
.control-icon--pause { width: 22px; height: 24px; display: flex; justify-content: space-between; }
.control-icon--pause view { width: 7px; height: 24px; border-radius: 3px; background: v3.$v3-surface; }
.ctrl-duration-text { color: v3.$v3-text-secondary; font-size: 12px; font-weight: 650; }
.disclaimer-box { margin-bottom: v3.$v3-space-5; padding: v3.$v3-space-4; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-md; background: v3.$v3-background; }
.disclaimer-text { color: v3.$v3-text-secondary; font-size: 12px; line-height: 1.65; }
.btn-primary { @include v3.v3-primary-action; padding: 0 v3.$v3-space-6; }
.btn-primary-text { color: v3.$v3-surface; font-size: 15px; font-weight: 650; }
.loading-wrap, .error-wrap { border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-lg; background: v3.$v3-surface; box-shadow: v3.$v3-shadow-soft; }
.loading-ring { border-color: v3.$v3-border; border-top-color: v3.$v3-primary; }
.error-text { color: v3.$v3-danger; }
.btn-retry { background: v3.$v3-primary; }
@media (min-width: 768px) { .container { padding-top: 56px; padding-bottom: 64px; } .player-card { padding: 44px 48px; } }
@media (max-width: 420px) { .player-card { padding: v3.$v3-space-6 v3.$v3-space-5; border-radius: v3.$v3-radius-lg; } .breathing-artwork { margin-top: v3.$v3-space-2; } .controls { gap: v3.$v3-space-6; } .ctrl-play { width: 72px; height: 72px; } }
/* V1.1 compact error state */
.error-wrap { min-height: 0; padding: v3.$v3-space-8 v3.$v3-space-6; text-align: center; }
.error-mark { position: relative; width: 48px; height: 48px; margin-bottom: v3.$v3-space-5; border-radius: 50%; background: rgba(78, 116, 104, .08); }
.error-mark-dot { position: absolute; width: 8px; height: 8px; left: 50%; top: 50%; border-radius: 50%; background: v3.$v3-primary; transform: translate(-50%, -50%); box-shadow: 0 0 0 7px rgba(78, 116, 104, .08); }
.error-title { display: block; margin-bottom: v3.$v3-space-2; color: v3.$v3-text-primary; font-size: 21px; font-weight: 620; line-height: 1.45; }
.error-description { display: block; max-width: 360px; color: v3.$v3-text-secondary; font-size: 14px; line-height: 1.7; }
.error-detail { display: block; max-width: 420px; margin-top: v3.$v3-space-2; color: v3.$v3-text-muted; font-size: 12px; line-height: 1.6; }
.error-actions { width: 100%; max-width: 320px; margin-top: v3.$v3-space-6; display: grid; grid-template-columns: minmax(0, 1fr); gap: v3.$v3-space-3; }
.btn-retry { @include v3.v3-primary-action; width: 100%; padding: 0 v3.$v3-space-6; box-sizing: border-box; }
.btn-retry-text { color: v3.$v3-surface; font-size: 15px; font-weight: 650; }
.error-secondary-space { min-height: v3.$v3-space-3; }
/* Phase 3A viewport and safe-area tuning */
.container { @include v3.v3-one-screen; padding-bottom:calc(84px + env(safe-area-inset-bottom)); }
.flow-shell { min-height:calc(100dvh - 84px - env(safe-area-inset-top) - env(safe-area-inset-bottom)); display:flex; flex-direction:column; }
.player-card { flex:1; justify-content:center; }
@media (max-height:760px){.container{padding-top:calc(16px + env(safe-area-inset-top));padding-bottom:calc(76px + env(safe-area-inset-bottom))}.header{margin-bottom:14px}.player-card{padding:20px}.breathing-artwork{width:min(210px,54vw);height:min(210px,54vw);margin-bottom:16px}.music-parameter-summary{margin-bottom:14px}.controls{margin-bottom:16px}.disclaimer-box{margin-bottom:14px}}
</style>
