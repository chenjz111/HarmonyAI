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
 * - real 模式调用真实辨证、处方与生成接口；失败显式提示且不回退示例音乐
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import {
  modeLabelFor,
  normalizeRegulationMode,
  personalizedToneTheme,
} from "../../common/v31-tone-theme.js"

export default {
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
    stateTags() {
      if (!this.basis || !this.basis.confirmed_state) return []
      return this.basis.confirmed_state
        .split(/[，、。；;]/)
        .map(item => item.trim().replace(/^近期/, ""))
        .filter(Boolean)
        .slice(0, 5)
    },
    rationaleRows() {
      if (!this.basis) return []
      return this.basis.analysis_rationales.map(item => {
        const parts = item.summary.split(/[，。]?提示/)
        return {
          source: (parts[0] || item.summary).replace(/[，。]$/, ""),
          target: (parts[1] || "作为本次调适依据").replace(/^[，。]/, "").replace(/。$/, ""),
        }
      })
    },
    toneOptions() {
      // Sprint 6：主音/辅音角色只在后端明确 personalized_five_tone 时标注；
      // integrated / basic / 未知 mode 绝不标记任何音为主音。
      const primary = this.hasPrimaryTone && this.basis.primary_tone ? this.basis.primary_tone.tone : ""
      const secondary = this.isPersonalized && this.basis && this.basis.secondary_tone ? this.basis.secondary_tone.tone : ""
      // code 必须是后端权威拼写（gong/shang/jiao/zhi/yu），否则主音无法被标记出来
      return [
        { code: "gong", label: "宫" },
        { code: "shang", label: "商" },
        { code: "jiao", label: "角" },
        { code: "zhi", label: "徵" },
        { code: "yu", label: "羽" },
      ].map(item => ({
        ...item,
        role: item.code === primary ? "primary" : (item.code === secondary ? "secondary" : ""),
      }))
    },
    // 后端权威 mode：缺失/未知一律为 ""（前端绝不从主音或权重推断 mode）
    regulationMode() {
      return normalizeRegulationMode(this.basis && this.basis.regulation_mode)
    },
    isPersonalized() {
      return this.regulationMode === "personalized_five_tone"
    },
    modeLabel() {
      return modeLabelFor(this.regulationMode)
    },
    hasPrimaryTone() {
      return this.isPersonalized && !!(this.basis && this.basis.primary_tone && this.basis.primary_tone.tone)
    },
    // 非个性化模式的中性说明：不主张五音主音，也不使用"主音未定"这类技术兜底措辞
    modeCopy() {
      if (this.regulationMode === "integrated_regulation") {
        return { title: "综合调适", body: "本次未形成单一五音主音，按综合调适方向配置音乐参数。" }
      }
      if (this.regulationMode === "basic_wellness") {
        return { title: "基础舒缓", body: "当前依据尚不充分，未主张五音主音，按基础舒缓方向配置音乐参数。" }
      }
      return { title: "本次五音解析暂不可用", body: "未能读取到可用的音乐设计模式，暂不展示五音主音结论。" }
    },
    // 主音/辅音的性格文案取自五音主题表，避免写死某个音（例如"宫"）的旧文案；
    // 且只在 personalized + 真实主音时生效，其余一律中性空状态。
    primaryToneTheme() {
      return personalizedToneTheme(this.regulationMode, this.basis && this.basis.primary_tone ? this.basis.primary_tone.tone : "")
    },
    secondaryToneTheme() {
      return personalizedToneTheme(this.regulationMode, this.basis && this.basis.secondary_tone ? this.basis.secondary_tone.tone : "")
    },
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
    back() {
      uni.navigateBack()
    },
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
        if (this.task.status === "succeeded" || this.task.status === "matched_fallback") {
          // 幂等重放/已即时完成时直接进播放器，不空转轮询
          this.goPlayer()
        } else {
          this.schedulePoll()
        }
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
      // Owner 2026-09-11: bottom tab is Home/Profile; Player is a normal flow page.
      uni.redirectTo({ url: "/pages/v3-player/v3-player" })
    },
    formatDuration(sec) {
      const m = Math.floor(sec / 60)
      const s = sec % 60
      return m + "分钟" + (s ? s + "秒" : "")
    },
  },
}
</script>

<template>
  <view class="basis-page v31-scroll-page">
    <view class="basis-container">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回" @click="back"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
      </view>

      <view class="basis-hero ink-fade-in">
        <view class="hero-title-row">
          <view class="hero-title-copy"><text class="step-tag">五音调适</text><text class="page-title">五音调适解析</text></view>
          <view class="hero-slogan"><text>以中医为本</text><text>用音乐疗愈身心</text><text class="hero-seal">和</text></view>
        </view>
        <text class="page-subtitle">根据你的近期状态总结，生成本次调适的解析与方案。</text>
      </view>

      <!-- 加载中 -->
      <view v-if="phase === 'loading'" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在准备生成依据…</text>
      </view>

      <view v-else-if="error" class="surface-card error-card ink-fade-in">
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
      <view v-else-if="phase === 'pending'" class="surface-card pending-card ink-fade-in">
        <view class="pending-seal">
          <text class="pending-seal-text">候</text>
        </view>
        <text class="pending-title">正在等待音乐服务接入</text>
        <text class="pending-desc">音乐生成服务正在升级维护中，暂时无法查看依据或发起生成。服务恢复后即可继续，你的评估结果已保存。</text>
        <view class="han-btn han-btn-ghost btn-back" @click="load">
          <text class="btn-back-text">重新加载</text>
        </view>
      </view>

      <!-- 解析页（冻结 FiveToneAnalysisReadModel，flow_v31.py） -->
      <view v-else-if="phase === 'basis' || phase === 'generating' || phase === 'cancelled'" class="basis-content ink-fade-up">
        <!-- hybrid 演示标识 -->
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：以下解析与生成过程为模拟数据</text>
        </view>

        <!-- 近期状态 -->
        <view class="basis-section-card state-section">
          <view class="section-head">
            <view class="section-icon-shell leaf-shell"><image class="section-leaf-image" src="/static/v31-goal/intent-2.png" mode="aspectFit" /></view>
            <text class="section-title">近期状态</text>
          </view>
          <view class="state-tags">
            <text v-for="tag in stateTags" :key="tag" class="state-tag">{{ tag }}</text>
          </view>
        </view>

        <!-- 状态解读 -->
        <view class="basis-section-card interpretation-section">
          <view class="section-head">
            <view class="section-icon-shell"><image class="basis-icon-image" src="/static/v31-basis/status.png" mode="aspectFit" /></view>
            <text class="section-title">状态解读</text>
          </view>
          <view class="interpretation-box">
            <text class="interpretation-text">{{ basis.state_tendency }} 当前调适更适合从安定情绪、帮助入静、降低刺激、辅助睡眠几个方向展开。</text>
          </view>
        </view>

        <!-- 调适依据 -->
        <view class="basis-section-card rationale-section">
          <view class="section-head">
            <view class="section-icon-shell"><image class="basis-icon-image" src="/static/v31-basis/basis.png" mode="aspectFit" /></view>
            <text class="section-title">调适依据</text>
          </view>
          <view class="rationale-list">
            <view v-for="(row, idx) in rationaleRows" :key="idx" class="rationale-row">
              <text class="rationale-index">{{ idx + 1 }}</text>
              <text class="rationale-source">{{ row.source }}</text>
              <text class="rationale-arrow">→</text>
              <text class="rationale-target">{{ row.target }}</text>
            </view>
          </view>
        </view>

        <!-- 五音配置 -->
        <view class="basis-section-card tone-section">
          <view class="section-head section-head-spread">
            <view class="section-heading-main">
              <view class="section-icon-shell"><image class="basis-icon-image" src="/static/v31-basis/tone.png" mode="aspectFit" /></view>
              <text class="section-title">本次五音配置</text>
            </view>
            <text class="section-kicker">五音和鸣 · 调养身心</text>
          </view>
          <view class="tone-row">
            <view v-for="tone in toneOptions" :key="tone.code" class="tone-option">
              <view :class="['tone-orb', tone.role ? `tone-orb--${tone.role}` : '']"><text>{{ tone.label }}</text></view>
              <text :class="['tone-role', tone.role ? `tone-role--${tone.role}` : '']">{{ tone.role === 'primary' ? '主音' : (tone.role === 'secondary' ? '辅音' : '') }}</text>
            </view>
          </view>
          <view class="tone-details">
            <view v-if="hasPrimaryTone" class="tone-detail tone-detail--primary">
              <text class="tone-detail-title">{{ basis.primary_tone.display_name }} · 主音</text>
              <text class="tone-detail-subtitle">{{ primaryToneTheme.traits }}</text>
              <text class="tone-detail-copy">{{ basis.primary_tone.explanation }}</text>
            </view>
            <view v-else class="tone-detail tone-detail--neutral">
              <text class="tone-detail-title">{{ modeCopy.title }}</text>
              <text class="tone-detail-copy">{{ modeCopy.body }}</text>
            </view>
            <view v-if="hasPrimaryTone && basis.secondary_tone" class="tone-detail tone-detail--secondary">
              <text class="tone-detail-title">{{ basis.secondary_tone.display_name }} · 辅音</text>
              <text class="tone-detail-subtitle">{{ secondaryToneTheme.traits }}</text>
              <text class="tone-detail-copy">{{ basis.secondary_tone.explanation }}</text>
            </view>
          </view>
        </view>

        <!-- 音乐设计 -->
        <view class="basis-section-card design-section">
          <view class="section-head section-head-spread">
            <view class="section-heading-main">
              <view class="section-icon-shell section-icon-note"><text>♫</text></view>
              <text class="section-title">音乐设计</text>
            </view>
            <text class="section-kicker">让音符回归身心的自然节奏</text>
          </view>
          <view class="design-grid">
            <view class="design-card">
              <image class="basis-icon-image design-icon" src="/static/v31-basis/bpm.png" mode="aspectFit" />
              <text class="param-value">{{ basis.bpm.value }} BPM</text>
              <text class="param-label">舒缓节奏</text>
            </view>
            <view class="design-card">
              <image class="basis-icon-image design-icon" src="/static/v31-basis/duration.png" mode="aspectFit" />
              <text class="param-value">{{ formatDuration(basis.duration.seconds) }}</text>
              <text class="param-label">时长</text>
            </view>
            <view class="design-card">
              <image class="basis-icon-image design-icon" src="/static/v31-basis/instrument.png" mode="aspectFit" />
              <text class="param-value">{{ basis.instruments.values.join('、') }}</text>
              <text class="param-label">主要乐器</text>
            </view>
            <view class="design-card">
              <image class="basis-icon-image design-icon" src="/static/v31-basis/ambience.png" mode="aspectFit" />
              <text class="param-value">{{ basis.ambience.values.join('、') }}</text>
              <text class="param-label">音乐氛围</text>
            </view>
          </view>
        </view>

        <!-- 生成中 / 发起前 / 取消后 -->
        <view v-if="phase === 'generating'" class="gen-box">
          <text class="gen-label">音乐生成中</text>
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
          <view class="generate-button" @click="generate">
            <text>{{ phase === 'cancelled' ? "重新生成" : "生成我的音乐" }}</text><text class="button-arrow">→</text>
          </view>
        </view>
        <text class="basis-disclaimer">{{ basis.disclaimer }}</text>
      </view>
      <view class="page-motto"><text>—　五音和鸣 · 乐养身心　—</text></view>
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
  padding: 28rpx 32rpx;
  text-align: center;
  margin-bottom: 24rpx;
}
.tendency-disclaimer {
  display: block;
  font-size: 22rpx;
  color: var(--text-muted);
}
.state-box {
  background: rgba(244, 238, 219, 0.5);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 28rpx;
  margin-bottom: 16rpx;
}
.state-text {
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.7;
}
.tendency-line {
  display: block;
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.7;
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
  margin-bottom: 16rpx;
}
.tone-box--secondary {
  background: rgba(107, 124, 94, 0.06);
}
.tone-main {
  display: block;
  font-size: 30rpx;
  font-weight: 500;
  color: var(--ink-700);
  margin-bottom: 8rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.tone-secondary {
  display: block;
  font-size: 26rpx;
  font-weight: 500;
  color: var(--ink-primary-dark);
  margin-bottom: 8rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.tone-sub {
  display: block;
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.6;
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
  justify-content: center;
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
  margin-bottom: 0;
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

/* ===== Owner V3.1 五音调适解析视觉稿 ===== */
.basis-page {
  min-height: 100vh;
  color: #0b4f51;
  background: #edf7f3;
}
.basis-container {
  width: 100%;
  max-width: 430px;
  min-height: 100vh;
  margin: 0 auto;
  padding: 14px 14px 34px;
  box-sizing: border-box;
  background-color: #fbfcf7;
  background-image: linear-gradient(rgba(255,255,252,.12),rgba(255,255,252,.12)), url('/static/v31-questionnaire/questionnaire-background-q34.png');
  background-repeat: no-repeat;
  background-position: center top;
  background-size: 100% 100%;
}
.basis-page .brand-row { display:flex; align-items:center; min-height:46px; gap:8px; }
.basis-page .back-button { display:flex; align-items:center; justify-content:center; width:28px; height:40px; margin:0; padding:0; border:0; background:transparent; }
.basis-page .back-button::after { border:0; }
.basis-page .back-chevron { width:11px; height:11px; border-left:2px solid #064c50; border-bottom:2px solid #064c50; transform:rotate(45deg); }
.basis-page .brand-leaf { width:42px; height:42px; }
.basis-page .brand-copy { display:flex; flex-direction:column; gap:1px; }
.basis-page .brand-name { font-size:18px; font-weight:750; line-height:1.15; }
.basis-page .brand-tagline { font-size:10px; letter-spacing:2px; }
.basis-hero { margin:16px 16px 20px; }
.hero-title-row { display:flex; align-items:flex-end; justify-content:space-between; gap:8px; }
.hero-title-copy { display:flex; flex-direction:column; align-items:flex-start; min-width:0; }
.hero-slogan { position:relative; display:flex; flex:0 0 auto; flex-direction:column; align-items:flex-end; padding:0 17px 3px 0; color:#15575a; font-family:'KaiTi','STKaiti',serif; font-size:9px; font-weight:700; line-height:1.35; transform:rotate(-4deg); }
.hero-seal { position:absolute; right:0; bottom:2px; display:flex; align-items:center; justify-content:center; width:13px; height:23px; border-radius:3px; color:#fff; background:#a92e27; font-size:8px; }
.basis-page .step-tag { display:inline-block; margin-bottom:7px; padding:4px 10px; border:0; border-radius:7px; color:#28675f; background:rgba(205,224,215,.72); font-size:12px; }
.basis-page .page-title { display:block; white-space:nowrap; color:#064c50; font-family:'KaiTi','STKaiti',serif; font-size:31px; font-weight:800; letter-spacing:2px; line-height:1.2; }
.basis-page .page-subtitle { display:block; margin-top:11px; color:#18585c; font-size:15px; line-height:1.65; }
.basis-content { display:flex; flex-direction:column; gap:12px; }
.basis-section-card,
.surface-card { box-sizing:border-box; padding:16px 14px; border:1px solid rgba(55,102,92,.10); border-radius:14px; background:rgba(255,255,252,.86); box-shadow:0 3px 10px rgba(31,72,62,.09); }
.basis-page .section-head { display:flex; align-items:center; gap:10px; margin:0 0 12px; }
.section-head-spread { justify-content:space-between; }
.section-heading-main { display:flex; align-items:center; gap:9px; min-width:0; }
.section-icon-shell { display:flex; align-items:center; justify-content:center; width:37px; min-width:37px; height:37px; border-radius:50%; background:rgba(216,234,226,.8); overflow:hidden; }
.basis-icon-image { width:23px; height:23px; mix-blend-mode:multiply; }
.leaf-shell { overflow:hidden; }
.section-leaf-image { width:43px; height:43px; border-radius:50%; mix-blend-mode:multiply; }
.basis-page .section-title { color:#0b4f51; font-family:'KaiTi','STKaiti',serif; font-size:20px; font-weight:800; letter-spacing:1px; }
.section-kicker { color:#448078; font-family:'KaiTi','STKaiti',serif; font-size:12px; letter-spacing:1px; text-align:right; }
.state-tags { display:flex; flex-wrap:wrap; gap:8px; }
.state-tag { padding:8px 12px; border-radius:18px; color:#225b5c; background:rgba(230,237,233,.78); font-size:13px; line-height:1.15; }
.interpretation-box { padding:13px 14px; border:1px solid rgba(60,101,93,.07); border-radius:8px; background:rgba(245,247,241,.72); }
.interpretation-text { color:#174f54; font-size:15px; line-height:1.75; }
.rationale-list { border-top:1px solid rgba(49,91,84,.08); }
.rationale-row { display:grid; grid-template-columns:30px minmax(0,.95fr) 18px minmax(0,1.2fr); align-items:center; min-height:58px; padding:5px 0; border-bottom:1px solid rgba(49,91,84,.08); }
.rationale-row:last-child { border-bottom:0; }
.rationale-index { display:flex; align-items:center; justify-content:center; width:26px; height:26px; border-radius:50%; color:#fff; background:#bcd3cb; font-size:13px; }
.rationale-source,.rationale-target { color:#285a5d; font-size:13px; line-height:1.55; }
.rationale-arrow { color:#8ca7a2; font-size:15px; text-align:center; }
.tone-row { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:4px; margin:2px 3px 9px; }
.tone-option { display:flex; flex-direction:column; align-items:center; min-width:0; }
.tone-orb { display:flex; align-items:center; justify-content:center; width:42px; max-width:100%; height:42px; border:1px solid rgba(76,111,102,.12); border-radius:50%; color:#527b72; background:rgba(235,241,235,.82); font-family:'KaiTi','STKaiti',serif; font-size:22px; box-shadow:0 2px 8px rgba(44,80,72,.05); }
.tone-orb--primary { color:#b52d25; border-color:rgba(209,76,57,.2); background:#fff1e9; box-shadow:0 3px 10px rgba(204,75,52,.15); }
.tone-orb--secondary { color:#2672a0; border-color:rgba(61,139,188,.18); background:#eaf7ff; box-shadow:0 3px 10px rgba(61,139,188,.12); }
.tone-role { min-height:16px; margin-top:4px; color:#597d77; font-size:11px; }
.tone-role--primary { color:#bd3028; }
.tone-role--secondary { color:#2672a0; }
.tone-details { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; }
.tone-detail { padding:12px; border:1px solid rgba(61,101,92,.10); border-radius:9px; background:rgba(250,250,245,.65); }
.tone-detail--primary { border-color:rgba(201,91,70,.16); background:rgba(255,246,240,.68); }
.tone-detail--secondary { border-color:rgba(72,141,181,.16); background:rgba(242,250,254,.7); }
/* Sprint 6：integrated / basic / 未知 mode 的中性态（不暗示任何五音） */
.tone-detail--neutral { grid-column:1 / -1; border-color:rgba(61,101,92,.14); background:rgba(244,247,244,.75); }
.tone-detail-title,.tone-detail-subtitle,.tone-detail-copy { display:block; }
.tone-detail-title { color:#19565a; font-size:15px; font-weight:750; }
.tone-detail--primary .tone-detail-title { color:#b43b31; }
.tone-detail--secondary .tone-detail-title { color:#27739a; }
.tone-detail-subtitle { margin-top:5px; color:#52716e; font-size:12px; }
.tone-detail-copy { margin-top:7px; color:#315b5d; font-size:13px; line-height:1.6; }
.section-icon-note { color:#145d58; font-size:22px; font-weight:700; }
.design-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.design-card { display:flex; flex-direction:column; align-items:center; justify-content:center; min-width:0; min-height:108px; padding:13px 9px; box-sizing:border-box; border:1px solid rgba(56,96,89,.10); border-radius:10px; background:rgba(255,255,252,.62); text-align:center; }
.design-icon { width:34px; height:34px; flex-shrink:0; }
.basis-page .param-value { max-width:100%; margin:9px 0 4px; color:#104f54; font-size:15px; font-weight:750; line-height:1.3; overflow-wrap:anywhere; }
.basis-page .param-label { margin:0; color:#55746f; font-size:12px; }
.basis-page .demo-banner { margin:0 0 2px; }
.basis-page .demo-banner-text { padding:4px 9px; font-size:9px; }
.basis-page .actions { margin-top:5px; }
.generate-button { display:flex; align-items:center; justify-content:center; gap:14px; min-height:52px; margin:0 64px; border-radius:28px; color:#fff; background:linear-gradient(105deg,#24695e,#28776a); box-shadow:0 5px 12px rgba(27,105,89,.16); font-size:17px; font-weight:650; }
.button-arrow { font-size:22px; font-weight:400; }
.basis-disclaimer { display:block; margin:10px 18px 0; color:#677d79; font-size:12px; line-height:1.55; text-align:center; }
.basis-page .page-motto { margin-top:17px; color:#285e5b; text-align:center; font-family:'KaiTi','STKaiti',serif; font-size:13px; letter-spacing:1px; }
.basis-page .gen-box { margin-top:6px; padding:20px 0 10px; }
.basis-page .gen-ring { width:76px; height:76px; border-width:5px; margin-bottom:12px; }
.basis-page .gen-label,.basis-page .gen-status { font-size:13px; }
.basis-page .gen-status { margin-bottom:12px; }
.basis-page .loading-wrap { padding:80px 0; }
.basis-page .error-card,.basis-page .pending-card { padding:42px 22px; }
@media (max-width:350px) {
  .basis-container { padding-left:9px; padding-right:9px; }
  .basis-hero { margin-left:10px; margin-right:10px; }
  .hero-slogan { display:none; }
  .basis-page .page-title { font-size:29px; }
  .basis-section-card { padding-left:11px; padding-right:11px; }
  .tone-orb { width:37px; font-size:20px; }
  .rationale-row { grid-template-columns:28px minmax(0,.95fr) 16px minmax(0,1.1fr); }
  .design-grid { gap:8px; }
  .design-card { min-height:104px; padding-left:6px; padding-right:6px; }
  .generate-button { margin-left:42px; margin-right:42px; }
}
</style>
