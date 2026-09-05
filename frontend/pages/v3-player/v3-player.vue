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
 *
 * v2 重写（水墨国风）：
 *   - 全页 .han-page 山水背景
 *   - 播放器卡片改为宣纸卡片
 *   - 唱片改为水墨渐变 + 旋转动效
 *   - 播放按钮改为朱砂印章大按钮
 *   - 业务逻辑 togglePlay/toggleFavorite/goFeedback/exitSession 完全保留
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
      simulated: false,
    }
  },
  computed: {
    audioSrc() {
      if (!this.music || !this.music.stream_url) return ""
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
        const src = await apiV3.fetchAuthorizedAudio(this.music.stream_url)
        if (!this.audioCtx) {
          this.audioCtx = uni.createInnerAudioContext()
          this.audioCtx.onError(() => {
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
      uni.navigateTo({ url: "/pages/v3-feedback/v3-feedback" })
    },
    exitSession() {
      this.stopAudio()
      uni.reLaunch({ url: "/pages/entry/entry" })
    },
  },
}
</script>

<template>
  <view class="page han-page">
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="step-tag">
          <text class="step-tag-text">音乐调养</text>
        </view>
      </view>

      <view v-if="loading" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在准备音乐…</text>
      </view>

      <view v-else-if="error" class="error-wrap ink-fade-in">
        <view class="error-seal">
          <text class="error-seal-text">音</text>
        </view>
        <text class="error-title">暂时无法播放</text>
        <text class="error-text">{{ error }}</text>
        <view class="han-btn han-btn-primary btn-retry" @click="load">
          <text class="btn-text">重试</text>
        </view>
        <text class="error-hint">你不必着急 · 待服务就绪再来聆听</text>
      </view>

      <view v-else class="player-card han-card ink-fade-up">
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：当前音乐为模拟数据</text>
        </view>

        <!-- 唱片：水墨渐变 + 朱砂印章角标 -->
        <view class="disc-wrap">
          <view class="disc" :class="{ 'disc-spinning': playing }">
            <view class="disc-inner">
              <text class="disc-tone">{{ music.tone_label ? music.tone_label.substring(0, 1) : "宫" }}</text>
            </view>
            <view class="disc-groove"></view>
          </view>
          <view class="disc-seal">
            <text class="disc-seal-text">调</text>
          </view>
        </view>

        <text class="music-title">{{ music.title }}</text>
        <text class="music-source">{{ music.source_label }} · {{ music.tone_label }}</text>
        <text class="music-instruments">{{ music.instrument_labels.join(" · ") }}</text>

        <!-- 控制区 -->
        <view class="controls">
          <view class="ctrl-fav" @click="toggleFavorite">
            <text class="ctrl-fav-icon" :class="{ 'fav-active': favorite }">{{ favorite ? "♥" : "♡" }}</text>
          </view>
          <view class="ctrl-play" @click="togglePlay">
            <text class="ctrl-play-icon">{{ playing ? "⏸" : "▶" }}</text>
          </view>
          <view class="ctrl-duration">
            <text class="ctrl-duration-text">{{ formatDuration(music.duration_seconds) }}</text>
          </view>
        </view>

        <!-- 免责声明 -->
        <view class="disclaimer-box">
          <text class="disclaimer-text">{{ music.disclaimer }}</text>
        </view>

        <view class="actions">
          <view class="han-btn han-btn-primary btn-primary" @click="goFeedback">
            <text class="btn-text">反馈本次体验</text>
          </view>
          <view class="han-btn han-btn-ghost btn-ghost" @click="exitSession">
            <text class="btn-text-ghost">结束本次聆听</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
}

.container {
  min-height: 100vh;
  padding: 48rpx 40rpx 60rpx;
  box-sizing: border-box;
}

.header {
  margin-bottom: 24rpx;
}

.step-tag {
  display: inline-flex;
}

.step-tag-text {
  font-size: 22rpx;
  color: var(--ink-primary);
  background: rgba(107, 124, 94, 0.1);
  border: 1rpx solid rgba(107, 124, 94, 0.2);
  border-radius: var(--radius-seal);
  padding: 8rpx 18rpx;
  letter-spacing: 0.1em;
  font-weight: 500;
}

.player-card {
  padding: 48rpx 36rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* ===== 唱片 ===== */
.disc-wrap {
  position: relative;
  margin-bottom: 48rpx;
  width: 320rpx;
  height: 320rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.disc {
  width: 320rpx;
  height: 320rpx;
  border-radius: 50%;
  background:
    radial-gradient(circle at 35% 35%, rgba(255,255,255,0.08) 0%, transparent 40%),
    radial-gradient(circle, var(--ink-primary) 0%, var(--ink-primary-dark) 55%, var(--ink-700) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 20rpx 50rpx rgba(58, 53, 44, 0.22),
    inset 0 0 0 16rpx rgba(255, 254, 250, 0.04);
  position: relative;
}

.disc-spinning {
  animation: discspin 10s linear infinite;
}

@keyframes discspin {
  to { transform: rotate(360deg); }
}

.disc-inner {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: var(--paper-card-solid);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 2rpx 10rpx rgba(58, 53, 44, 0.1);
  z-index: 2;
}

.disc-tone {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 52rpx;
  color: var(--ink-primary);
  font-weight: 700;
  line-height: 1;
}

.disc-groove {
  position: absolute;
  inset: 40rpx;
  border-radius: 50%;
  border: 1rpx solid rgba(255, 254, 250, 0.08);
  pointer-events: none;
}

.disc-seal {
  position: absolute;
  right: 4rpx;
  bottom: 24rpx;
  width: 72rpx;
  height: 72rpx;
  border-radius: var(--radius-seal);
  background: var(--ink-seal);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
  z-index: 3;
  transform: rotate(8deg);
}

.disc-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 34rpx;
  color: var(--text-inverse);
  font-weight: 700;
  line-height: 1;
}

/* ===== 音乐信息 ===== */
.music-title {
  font-size: 42rpx;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 14rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.1em;
  text-align: center;
}

.music-source {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 8rpx;
  letter-spacing: 0.08em;
}

.music-instruments {
  font-size: 24rpx;
  color: var(--text-muted);
  margin-bottom: 48rpx;
  letter-spacing: 0.05em;
}

/* ===== 控制区 ===== */
.controls {
  display: flex;
  align-items: center;
  gap: 56rpx;
  margin-bottom: 44rpx;
}

.ctrl-fav {
  width: 80rpx;
  height: 80rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ctrl-fav-icon {
  font-size: 48rpx;
  color: var(--ink-accent-light);
  transition: all 0.2s ease-out;
}

.fav-active {
  color: var(--ink-seal);
}

.ctrl-play {
  width: 140rpx;
  height: 140rpx;
  border-radius: 50%;
  background: var(--ink-seal);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
  transition: all 0.25s ease-out;
  position: relative;
  overflow: hidden;
}

.ctrl-play::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%);
  pointer-events: none;
}

.ctrl-play:active {
  transform: scale(0.96);
  background: var(--ink-seal-dark);
}

.ctrl-play-icon {
  font-size: 54rpx;
  color: var(--text-inverse);
  line-height: 1;
  position: relative;
  z-index: 1;
}

.ctrl-duration {
  width: 80rpx;
  display: flex;
  justify-content: center;
}

.ctrl-duration-text {
  font-size: 24rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* ===== 免责声明 ===== */
.disclaimer-box {
  background: rgba(107, 124, 94, 0.08);
  border: 1rpx solid rgba(107, 124, 94, 0.12);
  border-radius: var(--radius-md);
  padding: 24rpx;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 40rpx;
}

.disclaimer-text {
  font-size: 22rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  text-align: center;
}

/* ===== 操作区 ===== */
.actions {
  width: 100%;
}

.han-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.15em;
  border: none;
  padding: 24rpx 48rpx;
  transition: all 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.han-btn-primary {
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  box-shadow: var(--shadow-seal);
  position: relative;
  overflow: hidden;
}

.han-btn-primary::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%);
  pointer-events: none;
}

.han-btn-primary:active {
  background: var(--ink-seal-dark);
  transform: scale(0.98);
}

.btn-primary {
  width: 100%;
  margin-bottom: 20rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.han-btn-ghost {
  width: 100%;
  background: rgba(251, 249, 244, 0.6);
  color: var(--ink-700);
  border: 1rpx solid var(--border-soft);
  border-radius: var(--radius-seal);
}

.han-btn-ghost:active {
  background: rgba(232, 227, 216, 0.8);
}

.btn-ghost {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.btn-text,
.btn-text-ghost {
  color: inherit;
  font-size: 30rpx;
}

/* ===== 加载态 ===== */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid var(--border-light);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* ===== 错误态 ===== */
.error-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 100rpx 0;
}

.error-seal {
  width: 120rpx;
  height: 120rpx;
  border-radius: var(--radius-seal);
  background: var(--paper-card-solid);
  border: 2rpx solid var(--ink-seal);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
  box-shadow: var(--shadow-seal);
  transform: rotate(-4deg);
}

.error-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 64rpx;
  color: var(--ink-seal);
  font-weight: 700;
}

.error-title {
  font-size: 36rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  margin-bottom: 12rpx;
  letter-spacing: 0.08em;
}

.error-text {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 480rpx;
  line-height: 1.6;
}

.btn-retry {
  min-width: 220rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.error-hint {
  margin-top: 24rpx;
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.demo-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
  width: 100%;
}

.demo-banner-text {
  font-size: 22rpx;
  color: var(--warning);
  background: rgba(198, 138, 46, 0.1);
  border: 1rpx solid rgba(198, 138, 46, 0.2);
  border-radius: var(--radius-seal);
  padding: 8rpx 20rpx;
  letter-spacing: 0.05em;
}
</style>
