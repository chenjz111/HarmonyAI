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
import { toneThemeFor } from "../../common/v31-tone-theme.js"
// 纯函数：MM:SS（≥1 小时才 HH:MM:SS），未知时长显示 "--:--"
import { formatDuration } from "../../common/v31-player-time.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      music: null,
      basis: null,
      playing: false,
      audioCtx: null,
      resolvedAudioSrc: "",
      resolvedAudioStreamUrl: "",
      currentTime: 0, // 当前播放时间（秒），唯一来源：InnerAudioContext.onTimeUpdate
      duration: 0, // 真实音频时长（秒），来源：InnerAudioContext（onCanplay/onTimeUpdate）
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
    // 总时长（秒）：优先后端 read model 持久化的 duration_seconds，
    // 其次 InnerAudioContext 加载后上报的真实音频时长；都没有则返回 null（显示 --:--）。
    // 不伪造时长，也不使用任何固定常量。
    totalSeconds() {
      const persisted = Number(this.music && this.music.duration_seconds)
      if (Number.isFinite(persisted) && persisted > 0) return persisted
      const fromAudio = Number(this.duration)
      if (Number.isFinite(fromAudio) && fromAudio > 0) return fromAudio
      return null
    },
    // 进度百分比：currentTime / totalSeconds 同一真实时间基，总时长未知时为 0
    progressPercent() {
      if (!this.totalSeconds) return 0
      const p = (this.currentTime / this.totalSeconds) * 100
      return Math.max(0, Math.min(100, p))
    },
    // 主音的权威来源优先级（均为服务端数据，前端不重算、不猜）：
    //   1. 本次 music asset 的 tone_profile.primary_tone（persistMusicTask 已固化为 tone_code）
    //   2. 本次 music asset 的展示文案（tone_label，由同一个 tone_profile 派生）
    //   3. 本次音乐方案 / 五音分析 read model 明确存在的 primary_tone.tone
    // 都缺失时返回空字符串 → toneThemeFor 给出空状态 "--"，绝不回退成"宫"。
    toneSource() {
      const music = this.music || {}
      if (music.tone_code) return music.tone_code
      if (music.tone_label) return music.tone_label
      if (this.basis && this.basis.primary_tone) return this.basis.primary_tone.tone
      return ""
    },
    toneTheme() {
      return toneThemeFor(this.toneSource)
    },
    playerStyle() {
      const style = {
        "--tone-accent": this.toneTheme.accent,
        "--tone-soft": this.toneTheme.soft,
      }
      if (this.toneTheme.imageCode) {
        style.backgroundImage = `linear-gradient(rgba(255,255,252,.08),rgba(255,255,252,.08)), url('/static/v31-player/${this.toneTheme.imageCode}-1.png')`
      }
      return style
    },
    toneHeroSrc() {
      if (!this.toneTheme.imageCode) return ""
      return `/static/v31-player/${this.toneTheme.imageCode}-2.png`
    },
    basisMatchesTone() {
      return !!(this.basis && this.basis.primary_tone && this.basis.primary_tone.tone === this.toneTheme.code)
    },
    displayTitle() {
      return (this.music && this.music.title) || this.toneTheme.title || "—"
    },
    // 主音未解析出来时显示占位符，而不是任何具体的五音
    tonePairText() {
      if (!this.toneTheme.code) return "—"
      return `${this.toneTheme.glyph}音`
    },
    toneSummaryValue() {
      if (!this.toneTheme.code) return "—"
      return `${this.toneTheme.glyph}音主调`
    },
    displayBpm() {
      return this.basis && this.basis.bpm ? `${this.basis.bpm.value} BPM` : "—"
    },
    displayInstruments() {
      if (this.basisMatchesTone && this.basis.instruments) return this.basis.instruments.values.join(" · ")
      if (this.music && this.music.instrument_labels && this.music.instrument_labels.length) return this.music.instrument_labels.join(" · ")
      return this.toneTheme.instruments || "—"
    },
    displayAmbience() {
      if (this.basis && this.basis.ambience) return this.basis.ambience.values.join(" · ")
      return this.toneTheme.ambience || "—"
    },
    summaryDuration() {
      if (!this.totalSeconds) return "—"
      return `${Math.max(1, Math.round(this.totalSeconds / 60))}分钟`
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
        try {
          this.basis = await apiV3.getMusicBasis()
        } catch (e) {
          this.basis = null
        }
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
        // 已解析过后端鉴权地址时直接恢复本地音频，不重复下载或重置进度。
        if (this.audioCtx && this.resolvedAudioSrc) {
          if (this.resolvedAudioStreamUrl === this.music.stream_url) {
            this.audioCtx.play()
            this.playing = true
            return
          }
        }

        // 只在首次或切曲时才下载音频文件
        const src = await apiV3.fetchAuthorizedAudio(this.music.stream_url)
        this.resolvedAudioSrc = src
        this.resolvedAudioStreamUrl = this.music.stream_url
        if (!this.audioCtx) {
          this.audioCtx = uni.createInnerAudioContext()
          
          // 元数据加载成功：获取真实音频时长（totalSeconds 的兜底来源）
          this.audioCtx.onCanplay(() => {
            if (!this.audioCtx) return
            const realDuration = Number(this.audioCtx.duration)
            if (Number.isFinite(realDuration) && realDuration > 0) {
              this.duration = realDuration
            }
          })
          
          // 真实播放进度更新（唯一驱动 currentTime 的事件）；
          // 部分平台 onCanplay 时 duration 仍为 0，这里用同一音频时间基补齐真实总时长。
          this.audioCtx.onTimeUpdate(() => {
            if (!this.audioCtx) return
            this.currentTime = this.audioCtx.currentTime || 0
            const realDuration = Number(this.audioCtx.duration)
            if (Number.isFinite(realDuration) && realDuration > 0) {
              this.duration = realDuration
            }
          })
          
          this.audioCtx.onError(() => {
            this.playing = false
            uni.showToast({ title: "播放失败，请稍后重试", icon: "none" })
          })
          
          this.audioCtx.onEnded(() => {
            this.playing = false
            // 播放结束后进度停在总时长上，不清零：总时长与完整进度保持可见
            if (this.totalSeconds) this.currentTime = this.totalSeconds
          })
        }
        // 仅在 src 不同时才设置（换曲或首次）
        if (this.audioCtx.src !== src) {
          this.audioCtx.src = src
        }
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
      this.resolvedAudioSrc = ""
      this.resolvedAudioStreamUrl = ""
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
    // 时间格式化：复用 common/v31-player-time.js 的纯函数，模板与测试同源
    formatDuration,
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
  <view class="tone-player-page" :style="playerStyle">
    <view class="player-shell">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回" @click="exitSession"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
        <view class="brand-motto"><text>五音和鸣</text><text>心自安宁</text><text class="motto-seal">和</text></view>
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

      <view v-else class="player-content ink-fade-up">
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：当前音乐为模拟数据</text>
        </view>

        <view class="hero-wrap">
          <view class="wave-ring" :class="{ 'wave-ring--playing': playing }">
            <view class="tone-hero-frame">
              <image v-if="toneHeroSrc" class="tone-hero-image" :src="toneHeroSrc" mode="aspectFill" />
              <view class="tone-copy">
                <view class="tone-glyph-row"><text class="tone-glyph">{{ toneTheme.glyph }}</text><text class="tone-seal">主音</text></view>
                <text class="tone-traits">{{ toneTheme.traits }}</text>
              </view>
            </view>
          </view>
        </view>

        <text class="music-title">{{ displayTitle }}</text>
        <text class="tone-pair">{{ tonePairText }}</text>
        <text class="music-instruments">—　{{ displayInstruments }} · {{ displayAmbience }}　—</text>
        <text class="music-caption">让音乐回归身心的自然节奏，在静谧中遇见更好的自己。</text>

        <!-- 控制区：current / total 与进度条共用同一条真实音频时间基（onTimeUpdate） -->
        <view class="progress-wrap">
          <view class="progress-track" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100">
            <view class="progress-value" :style="{ width: progressPercent + '%' }"><view class="progress-thumb" /></view>
          </view>
          <view class="progress-times">
            <text class="progress-time">{{ formatDuration(currentTime) }} / {{ formatDuration(totalSeconds) }}</text>
          </view>
        </view>
        <view class="controls">
          <view class="ctrl-play" @click="togglePlay" :aria-label="playing ? '暂停' : '播放'">
            <view v-if="playing" class="pause-shape" aria-hidden="true">
              <view class="pause-bar"></view>
              <view class="pause-bar"></view>
            </view>
            <view v-else class="play-shape" aria-hidden="true"></view>
          </view>
        </view>

        <view class="music-summary-card">
          <view class="summary-heading"><view class="summary-note">♫</view><text>本次音乐</text></view>
          <view class="music-summary-grid">
            <view class="music-summary-cell"><text class="summary-value">{{ toneSummaryValue }}</text><text class="summary-label">{{ toneTheme.traits }}</text></view>
            <view class="music-summary-cell"><text class="summary-value">{{ displayBpm }}</text><text class="summary-label">舒缓节奏</text></view>
            <view class="music-summary-cell"><text class="summary-value">{{ summaryDuration }}</text><text class="summary-label">聆听时长</text></view>
            <view class="music-summary-cell"><text class="summary-value">{{ displayInstruments }}</text><text class="summary-label">主要乐器</text></view>
            <view class="music-summary-cell"><text class="summary-value">{{ displayAmbience }}</text><text class="summary-label">音乐氛围</text></view>
          </view>
        </view>

        <view class="actions">
          <view class="player-action feedback-action" @click="goFeedback">
            <view class="action-icon leaf-action-icon"><image src="/static/v31-document/leaf.svg" mode="aspectFit" /></view>
            <view class="action-copy"><text class="action-title">反馈本次体验</text><text class="action-subtitle">让我们做得更好</text></view><text class="action-arrow">→</text>
          </view>
          <view class="player-action end-action" @click="exitSession">
            <view class="action-icon"><view class="stop-square" /></view>
            <view class="action-copy"><text class="action-title">结束本次聆听</text><text class="action-subtitle">愿你身心安宁</text></view>
          </view>
        </view>
        <text class="player-disclaimer">{{ music.disclaimer }}</text>
        <view class="page-motto"><text>—　五音和鸣 · 乐养身心　—</text></view>
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

/* ===== 进度条 ===== */
.progress-wrap {
  width: 100%;
  margin-bottom: 32rpx;
}

.progress-track {
  width: 100%;
  height: 8rpx;
  background: rgba(107, 124, 94, 0.1);
  border-radius: 4rpx;
  overflow: hidden;
  margin-bottom: 12rpx;
}

.progress-value {
  height: 100%;
  background: var(--ink-seal);
  border-radius: 4rpx;
  transition: width 0.1s linear;
  transform-origin: left;
}

.progress-times {
  text-align: center;
}

.progress-time {
  font-size: 22rpx;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
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
  width: 48rpx;
  height: 48rpx;
  position: relative;
  transition: all 0.2s ease-out;
}

/* 心形收藏图标（CSS SVG） */
.heart-shape {
  width: 100%;
  height: 100%;
  background: var(--ink-accent-light);
  transform: rotate(-45deg);
  position: relative;
}

.heart-shape::before,
.heart-shape::after {
  content: "";
  width: 100%;
  height: 100%;
  background: inherit;
  border-radius: 50%;
  position: absolute;
}

.heart-shape::before {
  top: -24rpx;
  left: 0;
}

.heart-shape::after {
  left: 24rpx;
  top: 0;
}

.fav-active .heart-shape,
.fav-active .heart-shape::before,
.fav-active .heart-shape::after {
  background: var(--ink-seal);
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

/* 播放/暂停图标（CSS SVG） */
.play-shape {
  width: 0;
  height: 0;
  border-top: 32rpx solid transparent;
  border-bottom: 32rpx solid transparent;
  border-left: 52rpx solid var(--text-inverse);
  margin-left: 8rpx;
  position: relative;
  z-index: 1;
}

.pause-shape {
  display: flex;
  gap: 16rpx;
  position: relative;
  z-index: 1;
}

.pause-bar {
  width: 16rpx;
  height: 40rpx;
  background: var(--text-inverse);
  border-radius: 2rpx;
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

<style scoped>
.tone-player { background:radial-gradient(circle at 65% 8%,var(--tone-soft),transparent 30%),linear-gradient(180deg,#fffdf8 0%,var(--tone-soft) 100%); }
.tone-player .player-card { border:0; background:rgba(255,255,255,.72); border-radius:38rpx; box-shadow:0 24rpx 70rpx rgba(23,76,63,.13); }
.tone-player .disc { background:radial-gradient(circle at 50% 45%,#fffdf4 0 16%,var(--tone-soft) 17% 54%,rgba(255,255,255,.75) 55% 100%); border:4rpx solid rgba(255,255,255,.9); box-shadow:0 0 0 16rpx color-mix(in srgb,var(--tone-accent) 14%,transparent),0 26rpx 60rpx rgba(34,67,57,.18); }
.tone-player .disc-tone { color:var(--tone-accent); font-size:112rpx; font-family:"STKaiti","KaiTi",serif; }
.tone-player .disc-seal,.tone-player .ctrl-play,.tone-player .progress-value { background:var(--tone-accent); }
.tone-player .music-title { color:#103f3c; font-family:"STKaiti","KaiTi",serif; font-size:50rpx; }
.tone-player .ctrl-play { box-shadow:0 0 0 18rpx color-mix(in srgb,var(--tone-accent) 12%,transparent),0 16rpx 40rpx rgba(38,72,60,.2); }
.tone-player .btn-primary { background:linear-gradient(135deg,#c8553f,#a93b2e); border-radius:999rpx; }
.tone-player .btn-ghost { border-radius:999rpx; }
</style>

<style scoped>
/* ===== Owner V3.1 五音动态播放器 ===== */
.tone-player-page {
  width:100%;
  max-width:430px;
  min-height:100vh;
  margin:0 auto;
  color:#164f50;
  background-color:#f8f6ed;
  background-repeat:no-repeat;
  background-position:center top;
  background-size:100% 100%;
}
.player-shell { min-height:100vh; padding:14px 16px 26px; box-sizing:border-box; }
.tone-player-page .brand-row { display:flex; align-items:center; min-height:46px; gap:8px; }
.tone-player-page .back-button { display:flex; align-items:center; justify-content:center; width:28px; height:40px; margin:0; padding:0; border:0; background:transparent; }
.tone-player-page .back-button::after { border:0; }
.tone-player-page .back-chevron { width:11px; height:11px; border-left:2px solid #173e3d; border-bottom:2px solid #173e3d; transform:rotate(45deg); }
.tone-player-page .brand-leaf { width:42px; height:42px; }
.tone-player-page .brand-copy { display:flex; flex-direction:column; gap:1px; }
.tone-player-page .brand-name { color:#194f4e; font-size:18px; font-weight:750; line-height:1.15; }
.tone-player-page .brand-tagline { color:#416663; font-size:10px; letter-spacing:2px; }
.brand-motto { position:relative; display:flex; flex-direction:column; align-items:flex-end; margin-left:auto; padding-right:18px; color:#285c59; font-family:'KaiTi','STKaiti',serif; font-size:11px; font-weight:700; line-height:1.25; transform:rotate(-5deg); }
.motto-seal { position:absolute; right:0; bottom:0; display:flex; align-items:center; justify-content:center; width:14px; height:25px; border-radius:3px; color:#fff; background:#9d2821; font-size:8px; }
.player-content { display:flex; flex-direction:column; align-items:center; }
.tone-player-page .demo-banner { margin:2px 0 4px; }
.tone-player-page .demo-banner-text { padding:3px 8px; font-size:8px; }
.hero-wrap { display:flex; align-items:center; justify-content:center; width:100%; margin:7px 0 8px; }
.wave-ring { position:relative; display:flex; align-items:center; justify-content:center; width:286px; max-width:82vw; height:286px; max-height:82vw; border-radius:50%; background:repeating-conic-gradient(from -3deg,var(--tone-accent) 0 1deg,transparent 1deg 3.6deg); opacity:.98; }
.wave-ring::before { content:''; position:absolute; inset:12px; border-radius:50%; background:rgba(255,255,250,.82); box-shadow:0 0 0 1px color-mix(in srgb,var(--tone-accent) 30%,transparent); }
.wave-ring--playing { animation:pulse-ring 2.6s ease-in-out infinite; }
@keyframes pulse-ring { 50% { transform:scale(1.018); filter:saturate(1.08); } }
.tone-hero-frame { position:relative; width:250px; max-width:72vw; height:250px; max-height:72vw; border:4px solid rgba(255,255,248,.88); border-radius:50%; overflow:hidden; z-index:1; box-shadow:0 5px 18px rgba(42,67,59,.16); background:var(--tone-soft); }
.tone-hero-image { width:100%; height:100%; border-radius:50%; }
.tone-copy { position:absolute; top:45px; left:29px; display:flex; flex-direction:column; align-items:center; z-index:2; text-shadow:0 1px 2px rgba(255,255,255,.85); }
.tone-glyph-row { display:flex; align-items:center; gap:6px; }
.tone-glyph { color:#382b1c; font-family:'KaiTi','STKaiti',serif; font-size:42px; font-weight:800; line-height:1; }
.tone-seal { display:flex; align-items:center; justify-content:center; width:18px; height:32px; border-radius:4px; color:#fff; background:#9e3028; font-family:'KaiTi','STKaiti',serif; font-size:9px; writing-mode:vertical-rl; }
.tone-traits { width:16px; margin-top:5px; color:#263d37; font-family:'KaiTi','STKaiti',serif; font-size:11px; line-height:1.35; writing-mode:vertical-rl; letter-spacing:2px; }
.tone-player-page .music-title { margin:0 0 5px; color:#1e302c; font-family:'KaiTi','STKaiti',serif; font-size:30px; font-weight:800; letter-spacing:2px; line-height:1.2; }
.tone-pair { color:#65462e; font-family:'KaiTi','STKaiti',serif; font-size:14px; letter-spacing:2px; }
.tone-player-page .music-instruments { margin:8px 0 5px; color:#6c5039; font-family:'KaiTi','STKaiti',serif; font-size:13px; letter-spacing:1px; }
.music-caption { color:#536a66; font-size:10px; line-height:1.5; text-align:center; }
.tone-player-page .progress-wrap { width:90%; margin:15px 0 0; }
.tone-player-page .progress-track { width:100%; height:4px; margin:0; overflow:visible; border-radius:3px; background:rgba(73,85,80,.28); }
.tone-player-page .progress-value { position:relative; height:100%; border-radius:3px; background:var(--tone-accent); }
.progress-thumb { position:absolute; top:50%; right:-5px; width:10px; height:10px; border-radius:50%; background:var(--tone-accent); transform:translateY(-50%); }
.tone-player-page .progress-times { display:flex; justify-content:center; margin-top:7px; }
.tone-player-page .progress-time { color:#3f5551; font-size:10px; letter-spacing:0; white-space:nowrap; font-variant-numeric:tabular-nums; }
.tone-player-page .controls { display:flex; justify-content:center; margin:3px 0 15px; }
.tone-player-page .ctrl-play { display:flex; align-items:center; justify-content:center; width:78px; height:78px; border-radius:50%; background:var(--tone-accent); box-shadow:0 0 0 12px color-mix(in srgb,var(--tone-accent) 10%,transparent),0 8px 22px rgba(47,64,57,.22); }
.tone-player-page .play-shape { border-top-width:13px; border-bottom-width:13px; border-left-width:21px; margin-left:5px; }
.tone-player-page .pause-shape { gap:8px; }
.tone-player-page .pause-bar { width:7px; height:25px; border-radius:3px; }
.music-summary-card { width:100%; padding:12px 10px 13px; box-sizing:border-box; border:1px solid rgba(84,92,80,.12); border-radius:13px; background:rgba(255,255,250,.84); box-shadow:0 3px 12px rgba(62,74,65,.10); }
.summary-heading { display:flex; align-items:center; gap:8px; margin-bottom:9px; color:#233e3a; font-family:'KaiTi','STKaiti',serif; font-size:17px; font-weight:800; }
.summary-note { display:flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:50%; background:rgba(221,229,215,.9); color:var(--tone-accent); font-size:18px; }
.music-summary-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); }
.music-summary-cell { display:flex; flex-direction:column; align-items:center; min-width:0; min-height:54px; padding:4px 3px; box-sizing:border-box; border-right:1px solid rgba(80,90,82,.12); text-align:center; }
.music-summary-cell:last-child { border-right:0; }
.summary-value { max-width:100%; color:#2d3f3b; font-family:'KaiTi','STKaiti',serif; font-size:10px; font-weight:750; line-height:1.35; overflow-wrap:anywhere; }
.summary-label { margin-top:4px; color:#667a75; font-size:8px; line-height:1.3; }
.tone-player-page .actions { display:flex; flex-direction:column; gap:9px; width:78%; margin-top:13px; }
.player-action { display:grid; grid-template-columns:36px minmax(0,1fr) 24px; align-items:center; min-height:58px; padding:7px 17px; box-sizing:border-box; border-radius:31px; }
.feedback-action { color:#fff; background:linear-gradient(105deg,#c7513d,#b53d31); box-shadow:0 5px 15px rgba(155,54,43,.2); }
.end-action { grid-template-columns:36px minmax(0,1fr); color:#243b37; border:1px solid rgba(255,255,255,.9); background:rgba(239,239,230,.84); }
.action-icon { display:flex; align-items:center; justify-content:center; width:30px; height:30px; border:1px solid currentColor; border-radius:50%; }
.leaf-action-icon image { width:21px; height:21px; filter:brightness(0) invert(1); }
.stop-square { width:9px; height:9px; border-radius:1px; background:currentColor; }
.action-copy { display:flex; flex-direction:column; align-items:center; }
.action-title { font-family:'KaiTi','STKaiti',serif; font-size:16px; font-weight:700; line-height:1.2; }
.action-subtitle { margin-top:2px; font-size:8px; opacity:.82; }
.action-arrow { font-size:22px; }
.player-disclaimer { margin-top:10px; color:#637773; font-size:8px; text-align:center; }
.tone-player-page .page-motto { margin-top:13px; color:#496c67; font-family:'KaiTi','STKaiti',serif; font-size:10px; letter-spacing:1px; }
.tone-player-page .loading-wrap,.tone-player-page .error-wrap { min-height:600px; padding:120px 20px; box-sizing:border-box; }
.tone-player-page .error-text { color:#4f6661; }
@media (max-width:350px) {
  .player-shell { padding-left:10px; padding-right:10px; }
  .brand-motto { font-size:10px; }
  .wave-ring { width:254px; height:254px; }
  .tone-hero-frame { width:220px; height:220px; }
  .tone-copy { top:38px; left:24px; }
  .tone-glyph { font-size:37px; }
  .tone-player-page .music-title { font-size:27px; }
  .music-summary-card { padding-left:6px; padding-right:6px; }
  .music-summary-cell { padding-left:1px; padding-right:1px; }
  .summary-value { font-size:9px; }
  .tone-player-page .actions { width:84%; }
}
</style>
