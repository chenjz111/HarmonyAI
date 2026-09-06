<script>
/**
 * V3.1 五音调适解析页（Issue #100：升级自"音乐生成依据"，删除生成完成中间步骤）
 * 合同依据：frontend-read-model-contract-v3.md §10 / §11
 *          harmonyai-v3-owner-flow-amendment-001.md §2
 *
 * - 展示五音倾向、解析依据与调适参数（PUBLIC 提示，不显示分数/规则ID）
 * - 生成状态：queued | running | succeeded | matched_fallback | failed | cancelled
 * - Provider 未报告真实进度时显示不定进度，不伪造百分比
 * - 生成成功后直接切到播放器（无独立完成卡），失败/取消可重试
 * - 不显示候选分数、规则 ID 或任何目标类字段（该概念已在 V3 删除）
 * - real 模式下解析/生成依赖后端辨证能力（尚未交付）：
 *   遇 AGENT_PENDING 进入明确等待状态，不伪造解析或生成结果
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

export default {
  components: { HanSideNav },
  data() {
    return {
      phase: "loading", // loading | basis | generating | cancelled | pending
      error: "",
      basis: null,
      task: null,
      pollTimer: null,
      simulated: false, // hybrid：演示数据标识
    }
  },
  computed: {
    statusText() {
      const map = {
        queued: "排队中，请稍候…",
        running: "正在根据本次音乐参数生成。",
        succeeded: "生成完成！",
        matched_fallback: "已为你匹配审核曲库中的音乐。",
        failed: "生成失败，你可以重试。",
        cancelled: "已取消生成。",
      }
      return this.task ? (map[this.task.status] || "正在生成音乐…") : ""
    },
    progressPercent() {
      if (!this.task || !this.task.progress) return 0
      if (this.task.progress.indeterminate) return null
      return this.task.progress.value
    },
  },
  onLoad() {
    this.load()
  },
  onUnload() {
    this.stopPoll()
  },
  methods: {
    async load() {
      this.phase = "loading"
      this.error = ""
      try {
        this.basis = await apiV3.getMusicBasis()
        this.simulated = !!apiV3.AGENT_SIMULATED
        this.phase = "basis"
      } catch (e) {
        if (e.agentPending) {
          // real 模式：辨证能力未接入，明确等待，不伪造依据
          this.phase = "pending"
        } else {
          this.error = e.message || "加载失败，请重试"
          this.phase = "basis"
          this.basis = null
        }
      }
    },
    // 发起生成
    async generate() {
      this.phase = "generating"
      try {
        this.task = await apiV3.startMusicGeneration()
        this.schedulePoll()
      } catch (e) {
        if (e.agentPending) {
          // real 模式：音乐生成依赖辨证处方能力（未接入），明确等待，不伪造进度
          this.phase = "pending"
          return
        }
        uni.showToast({ title: e.message || "生成发起失败，请重试", icon: "none" })
        this.phase = "basis"
      }
    },
    schedulePoll() {
      this.stopPoll()
      const interval = (this.task && this.task.poll_after_ms) || 2000
      this.pollTimer = setInterval(async () => {
        try {
          this.task = await apiV3.pollMusicGeneration()
          if (this.task.status === "succeeded" || this.task.status === "matched_fallback") {
            // V3.1：删除"生成完成"中间步骤，成功后直接进入播放器
            this.stopPoll()
            setTimeout(() => { this.goPlayer() }, 600)
          } else if (this.task.status === "failed" || this.task.status === "cancelled") {
            this.stopPoll()
            this.phase = "cancelled"
          }
        } catch (e) {
          this.stopPoll()
          this.phase = "cancelled"
        }
      }, interval)
    },
    stopPoll() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
    async cancel() {
      this.stopPoll()
      try {
        await apiV3.cancelMusicGeneration()
        this.phase = "cancelled"
      } catch (e) {
        uni.showToast({ title: e.message || "取消失败，请重试", icon: "none" })
      }
    },
    retry() {
      this.generate()
    },
    goPlayer() {
      // v3-player 已是 tabBar 页面（播放 tab），redirectTo 无法打开 tab 页
      uni.switchTab({ url: "/pages/v3-player/v3-player" })
    },
    formatDuration(sec) {
      const m = Math.floor(sec / 60)
      const s = sec % 60
      return m + " 分" + (s ? s + " 秒" : "")
    },
  },
}
</script>

<template>
  <view class="page han-page side-nav-page">
    <han-side-nav current="confirm" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">承</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">五音调适</text>
            <text class="page-title han-title-brush revealed">五音调适解析</text>
          </view>
        </view>
        <text class="page-subtitle">根据你的近期状态总结，生成本次调适的解析与方案。</text>
      </view>

      <!-- 加载中 -->
      <view v-if="phase === 'loading'" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在准备生成依据…</text>
      </view>

      <view v-else-if="error" class="han-card error-card ink-fade-in">
        <view class="error-seal">
          <text class="error-seal-text">静</text>
        </view>
        <text class="error-title">暂时无法加载</text>
        <text class="error-text">{{ error }}</text>
        <view class="han-btn han-btn-primary btn-retry" @click="load">
          <text class="btn-retry-text">重试</text>
        </view>
      </view>

      <!-- real 模式：音乐服务未接入，明确等待状态，不伪造依据与生成（P1-2：稳定用户文案） -->
      <view v-else-if="phase === 'pending'" class="han-card pending-card ink-fade-in">
        <view class="pending-seal">
          <text class="pending-seal-text">候</text>
        </view>
        <text class="pending-title">正在等待音乐服务接入</text>
        <text class="pending-desc">音乐生成服务正在升级维护中，暂时无法查看依据或发起生成。服务恢复后即可继续，你的评估结果已保存。</text>
        <view class="han-btn han-btn-ghost btn-back" @click="load">
          <text class="btn-back-text">重新加载</text>
        </view>
      </view>

      <!-- 解析页（Read Model §10） -->
      <view v-else-if="phase === 'basis' || phase === 'generating' || phase === 'cancelled'" class="han-card basis-card ink-fade-up">
        <!-- hybrid 演示标识 -->
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：以下解析与生成过程为模拟数据</text>
        </view>

        <view class="tendency-box">
          <text class="tendency-label">{{ basis.tendency.label }}</text>
          <view class="tendency-divider han-divider han-divider--seal"></view>
          <text class="tendency-disclaimer">{{ basis.tendency.disclaimer }}</text>
        </view>

        <view class="basis-section">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">据</text></view>
            <text class="section-title">主要依据</text>
          </view>
          <view class="basis-items">
            <view v-for="(b, idx) in basis.basis_summaries" :key="idx" class="basis-item">
              <view class="item-dot"></view>
              <text class="item-text">{{ b }}</text>
            </view>
          </view>
        </view>

        <view class="basis-section">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">音</text></view>
            <text class="section-title">音调方案</text>
          </view>
          <view class="tone-box">
            <text class="tone-main">{{ basis.tone_profile.dominant_label }}为主</text>
            <text class="tone-sub">{{ basis.tone_profile.summary }}</text>
          </view>
        </view>

        <view class="basis-section">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">参</text></view>
            <text class="section-title">音乐参数</text>
          </view>
          <view class="params-grid">
            <view class="param-cell"><text class="param-value">{{ basis.music_parameters.bpm }}</text><text class="param-label">节拍 (BPM)</text></view>
            <view class="param-cell"><text class="param-value">{{ formatDuration(basis.music_parameters.duration_seconds) }}</text><text class="param-label">时长</text></view>
            <view class="param-cell"><text class="param-value">{{ basis.music_parameters.instrument_labels.join('、') }}</text><text class="param-label">乐器</text></view>
            <view class="param-cell"><text class="param-value">{{ basis.music_parameters.ambient_labels.join('、') }}</text><text class="param-label">氛围</text></view>
          </view>
        </view>

        <text class="personal-note">{{ basis.personalization_summary }}</text>

        <!-- 生成中 / 发起前 / 取消后 -->
        <view v-if="phase === 'generating'" class="gen-box">
          <view class="gen-ring" :class="{ 'gen-indeterminate': progressPercent === null }">
            <text v-if="progressPercent !== null" class="gen-percent">{{ progressPercent }}%</text>
          </view>
          <text class="gen-status">{{ statusText }}</text>
          <view class="gen-cancel" @click="cancel"><text class="gen-cancel-text">取消生成</text></view>
        </view>

        <view v-else class="actions">
          <view v-if="phase === 'cancelled'" class="cancel-note">
            <text class="cancel-note-text">已取消，可重新发起生成。</text>
          </view>
          <view class="han-btn han-btn-primary btn-primary" @click="generate">
            <text class="btn-primary-text">{{ phase === 'cancelled' ? "重新生成" : "生成本次音乐" }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.container {
  min-height: 100vh;
  padding: 70rpx 48rpx 60rpx;
  box-sizing: border-box;
}

/* ===== 页头 ===== */
.header {
  margin-bottom: 40rpx;
}
.header-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 16rpx;
}
.stage-seal {
  width: 88rpx;
  height: 88rpx;
  background: var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
  flex-shrink: 0;
}
.stage-seal-text {
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 44rpx;
  font-weight: 700;
}
.header-titles {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.step-tag {
  display: inline-block;
  align-self: flex-start;
  font-size: 22rpx;
  color: var(--ink-primary);
  background: rgba(107, 124, 94, 0.12);
  border: 1rpx solid rgba(107, 124, 94, 0.2);
  border-radius: 8rpx;
  padding: 4rpx 16rpx;
}
.page-title {
  font-size: 40rpx;
}
.page-subtitle {
  display: block;
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ===== 解析卡 ===== */
.basis-card {
  border-radius: var(--radius-lg);
  padding: 40rpx 32rpx;
}
.tendency-box {
  background: rgba(107, 124, 94, 0.08);
  border: 1rpx solid rgba(107, 124, 94, 0.16);
  border-radius: 14rpx;
  padding: 36rpx 32rpx;
  text-align: center;
  margin-bottom: 36rpx;
}
.tendency-label {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  color: var(--ink-primary-dark);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  margin-bottom: 6rpx;
}
.tendency-divider {
  width: 180rpx;
  margin: 6rpx auto 20rpx;
}
.tendency-disclaimer {
  display: block;
  font-size: 22rpx;
  color: var(--text-muted);
}

.basis-section {
  margin-bottom: 32rpx;
}
.section-head {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 18rpx;
}
.section-seal {
  min-width: 40rpx;
  height: 40rpx;
  background: var(--ink-700);
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.section-seal-text {
  color: var(--text-inverse);
  font-size: 22rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.section-title {
  font-size: 26rpx;
  color: var(--text-muted);
  letter-spacing: 2rpx;
}
.basis-item {
  display: flex;
  align-items: center;
  padding: 12rpx 0;
}
.item-dot {
  width: 12rpx;
  height: 12rpx;
  background: var(--ink-primary);
  border-radius: 50%;
  margin-right: 20rpx;
  flex-shrink: 0;
}
.item-text {
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.6;
}
.tone-box {
  background: rgba(244, 238, 219, 0.5);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 28rpx;
}
.tone-main {
  display: block;
  font-size: 30rpx;
  font-weight: 500;
  color: var(--ink-700);
  margin-bottom: 8rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.tone-sub {
  display: block;
  font-size: 24rpx;
  color: var(--text-secondary);
}
.params-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.param-cell {
  width: calc(50% - 8rpx);
  background: rgba(244, 238, 219, 0.5);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 24rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.param-value {
  font-size: 28rpx;
  color: var(--ink-700);
  font-weight: 500;
  margin-bottom: 8rpx;
}
.param-label {
  font-size: 22rpx;
  color: var(--text-muted);
}
.personal-note {
  display: block;
  font-size: 24rpx;
  color: var(--text-muted);
  margin: 8rpx 0 32rpx;
  line-height: 1.6;
}

/* ===== 生成 ===== */
.gen-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0 20rpx;
  border-top: 1rpx solid var(--divider);
}
.gen-ring {
  width: 160rpx;
  height: 160rpx;
  border: 10rpx solid var(--paper-deep);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.gen-indeterminate {
  animation: spin 1s linear infinite;
}
.gen-percent {
  font-size: 36rpx;
  color: var(--ink-700);
  font-weight: 600;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.gen-status {
  font-size: 28rpx;
  color: var(--ink-700);
  margin-bottom: 28rpx;
}
.gen-cancel {
  padding: 12rpx 40rpx;
  border: 2rpx solid var(--border-soft);
  border-radius: 36rpx;
}
.gen-cancel-text {
  font-size: 26rpx;
  color: var(--text-secondary);
}
.cancel-note {
  text-align: center;
  margin-bottom: 20rpx;
}
.cancel-note-text {
  font-size: 24rpx;
  color: var(--ink-seal);
}
.actions {
  display: flex;
  flex-direction: column;
}
.btn-primary {
  margin-bottom: 24rpx;
}
.btn-primary-text {
  color: var(--text-inverse);
  font-size: 30rpx;
}

/* ===== 加载 / 错误 / 等待 ===== */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid var(--paper-deep);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: var(--text-muted);
}
.error-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80rpx 40rpx;
  border-radius: var(--radius-lg);
}
.error-seal {
  width: 108rpx;
  height: 108rpx;
  border: 3rpx solid var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
  background: rgba(192, 57, 43, 0.04);
}
.error-seal-text {
  color: var(--ink-seal);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 52rpx;
  font-weight: 700;
}
.error-title {
  font-size: 32rpx;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  margin-bottom: 12rpx;
}
.error-text {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 36rpx;
  text-align: center;
  line-height: 1.6;
}
.btn-retry {
  padding: 20rpx 72rpx;
}
.btn-retry-text {
  color: var(--text-inverse);
  font-size: 28rpx;
}
.demo-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.demo-banner-text {
  font-size: 22rpx;
  color: var(--warning);
  background: rgba(198, 138, 46, 0.09);
  border: 1rpx solid rgba(198, 138, 46, 0.22);
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
}
.pending-card {
  border-radius: var(--radius-lg);
  padding: 64rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pending-seal {
  width: 100rpx;
  height: 100rpx;
  background: var(--ink-700);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
  box-shadow: 0 6rpx 18rpx rgba(26, 25, 22, 0.2);
}
.pending-seal-text {
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 44rpx;
  font-weight: 700;
}
.pending-title {
  font-size: 34rpx;
  font-weight: 600;
  color: var(--ink-700);
  margin-bottom: 20rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.pending-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
.btn-back {
  padding: 20rpx 64rpx;
}
.btn-back-text {
  color: var(--ink-700);
  font-size: 28rpx;
}
</style>
