<script>
/**
 * V3 音乐生成依据 + 生成进度页
 * 合同依据：frontend-read-model-contract-v3.md §10 / §11
 *          harmonyai-v3-owner-flow-amendment-001.md §2
 *
 * - 展示辨证倾向、依据摘要、音参数（PUBLIC 提示，不显示分数/规则ID）
 * - 生成状态：queued | running | succeeded | matched_fallback | failed | cancelled
 * - Provider 未报告真实进度时显示不定进度，不伪造百分比
 * - 不显示候选分数、规则 ID 或任何目标类字段（该概念已在 V3 删除，Amendment §5）
 * - real 模式下依据/生成依赖后端辨证能力（尚未交付）：
 *   遇 AGENT_PENDING 进入明确等待状态，不伪造依据或生成结果
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      phase: "loading", // loading | basis | generating | done | cancelled | pending
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
            this.stopPoll()
            setTimeout(() => { this.phase = "done" }, 800)
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
  <view class="container">
    <view class="header">
      <text class="step-tag">音乐生成</text>
      <text class="page-title">本次音乐生成依据</text>
    </view>

    <!-- 加载中 -->
    <view v-if="phase === 'loading'" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在准备生成依据…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <text class="error-text">{{ error }}</text>
      <view class="btn-retry" @click="load"><text class="btn-retry-text">重试</text></view>
    </view>

    <!-- real 模式：音乐服务未接入，明确等待状态，不伪造依据与生成（P1-2：稳定用户文案） -->
    <view v-else-if="phase === 'pending'" class="pending-card">
      <view class="pending-icon"><text class="pending-icon-text">…</text></view>
      <text class="pending-title">正在等待音乐服务接入</text>
      <text class="pending-desc">音乐生成服务正在升级维护中，暂时无法查看依据或发起生成。服务恢复后即可继续，你的评估结果已保存。</text>
      <view class="btn-retry" @click="load"><text class="btn-retry-text">重新加载</text></view>
    </view>

    <!-- 依据页（Read Model §10） -->
    <view v-else-if="phase === 'basis' || phase === 'generating' || phase === 'cancelled'" class="basis-card">
      <!-- hybrid 演示标识 -->
      <view v-if="simulated" class="demo-banner">
        <text class="demo-banner-text">演示模式：以下依据与生成过程为模拟数据</text>
      </view>

      <view class="tendency-box">
        <text class="tendency-label">{{ basis.tendency.label }}</text>
        <text class="tendency-disclaimer">{{ basis.tendency.disclaimer }}</text>
      </view>

      <view class="basis-section">
        <text class="section-title">主要依据</text>
        <view class="basis-items">
          <view v-for="(b, idx) in basis.basis_summaries" :key="idx" class="basis-item">
            <view class="item-dot"></view>
            <text class="item-text">{{ b }}</text>
          </view>
        </view>
      </view>

      <view class="basis-section">
        <text class="section-title">音调方案</text>
        <view class="tone-box">
          <text class="tone-main">{{ basis.tone_profile.dominant_label }}为主</text>
          <text class="tone-sub">{{ basis.tone_profile.summary }}</text>
        </view>
      </view>

      <view class="basis-section">
        <text class="section-title">音乐参数</text>
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
        <view class="btn-primary" @click="generate">
          <text class="btn-primary-text">{{ phase === 'cancelled' ? "重新生成" : "生成本次音乐" }}</text>
        </view>
      </view>
    </view>

    <!-- 生成完成 -->
    <view v-else-if="phase === 'done'" class="done-card">
      <view class="done-icon"><text class="done-icon-text">♪</text></view>
      <text class="done-title">音乐已生成完成</text>
      <text class="done-sub">已根据本次评估结果为你定制</text>
      <view class="btn-primary" @click="goPlayer">
        <text class="btn-primary-text">开始收听</text>
      </view>
    </view>
  </view>
</template>

<style>
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 70rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header { margin-bottom: 40rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4a6b5c;
  background: #e6ebe5;
  border-radius: 8rpx;
  padding: 6rpx 16rpx;
  margin-bottom: 18rpx;
}
.page-title { display: block; font-size: 40rpx; font-weight: 600; color: #2f3d35; }
.basis-card, .done-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}
.tendency-box {
  background: #eef0ea;
  border-radius: 16rpx;
  padding: 32rpx;
  text-align: center;
  margin-bottom: 36rpx;
}
.tendency-label { display: block; font-size: 34rpx; font-weight: 600; color: #4a6b5c; margin-bottom: 10rpx; }
.tendency-disclaimer { display: block; font-size: 22rpx; color: #9c9585; }
.basis-section { margin-bottom: 32rpx; }
.section-title { display: block; font-size: 26rpx; color: #9c9585; margin-bottom: 18rpx; }
.basis-item { display: flex; align-items: center; padding: 12rpx 0; }
.item-dot { width: 12rpx; height: 12rpx; background: #4a6b5c; border-radius: 50%; margin-right: 20rpx; flex-shrink: 0; }
.item-text { font-size: 28rpx; color: #2f3d35; }
.tone-box {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 28rpx;
}
.tone-main { display: block; font-size: 30rpx; font-weight: 500; color: #2f3d35; margin-bottom: 8rpx; }
.tone-sub { display: block; font-size: 24rpx; color: #7a8078; }
.params-grid { display: flex; flex-wrap: wrap; gap: 16rpx; }
.param-cell {
  width: calc(50% - 8rpx);
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 24rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.param-value { font-size: 28rpx; color: #2f3d35; font-weight: 500; margin-bottom: 8rpx; }
.param-label { font-size: 22rpx; color: #9c9585; }
.personal-note { display: block; font-size: 24rpx; color: #9c9585; margin: 8rpx 0 32rpx; }
.gen-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0 20rpx;
  border-top: 2rpx solid #f0ebdf;
}
.gen-ring {
  width: 160rpx;
  height: 160rpx;
  border: 10rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.gen-indeterminate { animation: spin 1s linear infinite; }
.gen-percent { font-size: 36rpx; color: #2f3d35; font-weight: 600; }
@keyframes spin { to { transform: rotate(360deg); } }
.gen-status { font-size: 28rpx; color: #2f3d35; margin-bottom: 28rpx; }
.gen-cancel { padding: 12rpx 40rpx; border: 2rpx solid #c9c3b2; border-radius: 36rpx; }
.gen-cancel-text { font-size: 26rpx; color: #7a8078; }
.cancel-note { text-align: center; margin-bottom: 20rpx; }
.cancel-note-text { font-size: 24rpx; color: #b0574f; }
.actions { display: flex; flex-direction: column; }
.btn-primary {
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 26rpx 0;
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.btn-primary-text { color: #fff; font-size: 30rpx; }
.done-card { display: flex; flex-direction: column; align-items: center; padding: 80rpx 40rpx; }
.done-icon {
  width: 130rpx;
  height: 130rpx;
  border-radius: 50%;
  background: #eef0ea;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
}
.done-icon-text { font-size: 60rpx; color: #4a6b5c; }
.done-title { font-size: 36rpx; font-weight: 600; color: #2f3d35; margin-bottom: 14rpx; }
.done-sub { font-size: 26rpx; color: #9c9585; margin-bottom: 56rpx; }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; }
.loading-ring {
  width: 72rpx; height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
.loading-text { margin-top: 24rpx; font-size: 26rpx; color: #9c9585; }
.error-wrap { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; }
.error-text { font-size: 28rpx; color: #b0574f; margin-bottom: 32rpx; }
.btn-retry { padding: 20rpx 64rpx; background: #4a6b5c; border-radius: 44rpx; }
.btn-retry-text { color: #fff; font-size: 28rpx; }
.demo-banner { display: flex; justify-content: center; margin-bottom: 24rpx; }
.demo-banner-text {
  font-size: 22rpx;
  color: #8a6d3b;
  background: #f5eddc;
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
}
.pending-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 64rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pending-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: #eef0ea;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.pending-icon-text { font-size: 48rpx; color: #4a6b5c; font-weight: 600; }
.pending-title { font-size: 34rpx; font-weight: 600; color: #2f3d35; margin-bottom: 20rpx; }
.pending-desc {
  font-size: 26rpx;
  color: #7a8078;
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
</style>
