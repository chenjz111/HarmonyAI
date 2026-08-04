<template>
  <view class="container">
    <view class="status-card" v-if="status === 'analyzing'">
      <view class="analyzing-orb"><view class="orb-ring orb-ring-1"></view><view class="orb-core"></view></view>
      <text class="status-title">AI 正在分析</text>
      <text class="status-desc">{{ statusMessage }}</text>
      <progress-bar :progress="analysisProgress" label="分析进度" />
    </view>

    <view v-else-if="status === 'success' && result">
      <view class="result-header">
        <view><text class="header-tag">状态评估</text><text class="result-title">AI 对你当前状态的理解</text></view>
        <view class="match-tag"><text class="match-tag-text">证据充分度 {{ confidencePercent }}%</text></view>
      </view>

      <view class="section-card" v-if="result.degradation && result.degradation.triggered">
        <text class="section-title">已启用问卷降级模式</text>
        <text class="section-desc">Qwen 或材料识别暂不可用，当前结果主要依据结构化问卷，仍可继续体验。</text>
      </view>

      <view class="section-card">
        <view class="section-title-row"><view class="section-dot"></view><text class="section-title">状态摘要</text></view>
        <text class="section-desc">{{ result.assessment_summary }}</text>
        <view class="music-tags">
          <view class="music-tag" v-for="state in result.emotion_profile.primary_states" :key="state">
            <text class="music-tag-text">{{ state }}</text>
          </view>
        </view>
      </view>

      <view class="section-card">
        <view class="section-title-row"><view class="section-dot"></view><text class="section-title">量化维度</text></view>
        <view class="dimension-list">
          <view class="dimension-item" v-for="dim in dimensions" :key="dim.name">
            <view class="dimension-info"><text class="dimension-name">{{ dim.name }}</text><text>{{ dim.score }}</text></view>
            <view class="dimension-bar"><view class="dimension-fill" :style="{ width: dim.score + '%', background: '#6B8979' }"></view></view>
          </view>
        </view>
      </view>

      <view class="section-card">
        <view class="section-title-row"><view class="section-dot" style="background: #C8896D"></view><text class="section-title">可解释依据</text></view>
        <view class="evidence-box">
          <view class="evidence-item" v-for="(ev, idx) in result.extracted_evidence" :key="idx">
            <text class="evidence-bullet">·</text><text class="evidence-text">{{ ev.summary || ev.claim }}</text>
          </view>
        </view>
        <text class="section-desc">分析模式：{{ analysisModeText }}</text>
        <text class="section-desc">本结果只用于状态评估和音乐调养参考，不构成医学诊断。</text>
      </view>

      <view class="action-wrap">
        <view class="action-btn" @click="confirmAndContinue"><text class="action-btn-text">{{ confirming ? '正在生成方案...' : '基本准确，生成音乐方案' }}</text><text class="action-btn-arrow">→</text></view>
        <text class="action-hint">如果理解不准确，可返回修改描述或问卷</text>
      </view>
    </view>

    <error-state v-else-if="status === 'blocked'" title="请优先关注安全" :message="safetyMessage" :showRetry="false" :showFallback="false" />
    <error-state v-else-if="status === 'error'" title="分析失败" :message="errorMsg" @retry="loadResult" />
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { runWorkflow } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'

const dimensionLabels = {
  tension_worry: '紧张担忧', overthinking: '反复思虑', irritability_anger: '烦躁易怒',
  low_mood: '情绪低落', interest_loss: '兴趣下降', fear_unease: '恐惧不安',
  sleep_disturbance: '睡眠困扰', low_energy: '精力不足', appetite_change: '食欲变化',
  daily_impact: '日常影响'
}

export default {
  components: { ProgressBar, ErrorState },
  data() {
    return {
      status: 'analyzing', analysisProgress: 40, statusMessage: '正在整合材料、自由描述与问卷...',
      result: null, errorMsg: '', confirming: false
    }
  },
  computed: {
    confidencePercent() { return Math.round((this.result?.confidence || 0) * 100) },
    dimensions() {
      const scores = this.result?.emotion_profile?.dimension_scores || {}
      return Object.entries(scores).map(([name, score]) => ({ name: dimensionLabels[name] || name, score }))
    },
    analysisModeText() {
      const labels = {
        document_narrative_questionnaire: '材料 + 自由描述 + 问卷',
        document_questionnaire: '材料 + 问卷', narrative_questionnaire: '自由描述 + 问卷',
        questionnaire_only: '仅问卷'
      }
      return labels[this.result?.analysis_mode] || '综合评估'
    },
    safetyMessage() {
      return '当前输入出现需要进一步关注的风险信号。本系统不能代替医生或心理咨询师；如有严重胸痛、呼吸困难或自伤想法，请立即联系当地急救或专业人员。'
    }
  },
  onLoad() { this.loadResult() },
  methods: {
    loadResult() {
      try {
        const workflow = getSprint3Session().workflow
        const assessment = workflow?.assessment
        if (!assessment) throw new Error('未找到评估结果，请重新完成问卷')
        this.result = assessment
        this.analysisProgress = 100
        this.status = assessment.status === 'blocked_safety' ? 'blocked' : 'success'
      } catch (error) {
        this.status = 'error'
        this.errorMsg = error.message || '无法读取评估结果'
      }
    },
    async confirmAndContinue() {
      if (this.confirming) return
      this.confirming = true
      try {
        const session = getSprint3Session()
        const workflow = await runWorkflow({
          session_id: session.session_id,
          user_id: session.user_id || 'demo_user_001',
          document_id: session.document_id || null,
          document_text: session.document_text || null,
          narrative_text: session.narrative_text || null,
          questionnaire_answers: session.questionnaire_answers,
          assessment_confirmed: true
        })
        updateSprint3Session({ workflow })
        if (workflow.assessment?.status === 'blocked_safety') {
          this.status = 'blocked'
          return
        }
        uni.navigateTo({ url: '/pages/player-v2/player-v2' })
      } catch (error) {
        this.status = 'error'
        this.errorMsg = error.message || '音乐方案生成失败，请重试'
      } finally {
        this.confirming = false
      }
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #F7F3EB;
  padding: 40rpx 40rpx 80rpx;
  box-sizing: border-box;
}

/* ============ 分析中 ============ */
.status-card {
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 80rpx 48rpx;
  text-align: center;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 8rpx 28rpx rgba(74, 107, 92, 0.08);
}
.analyzing-orb {
  width: 200rpx;
  height: 200rpx;
  margin: 0 auto 40rpx;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.orb-ring {
  position: absolute;
  border-radius: 50%;
  border: 2rpx solid #4A6B5C;
  opacity: 0.3;
}
.orb-ring-1 {
  width: 200rpx; height: 200rpx;
  border-top-color: #4A6B5C;
  animation: spin 2s linear infinite;
}
.orb-ring-2 {
  width: 150rpx; height: 150rpx;
  border-top-color: #6B8979;
  animation: spin 1.5s linear infinite reverse;
}
.orb-ring-3 {
  width: 100rpx; height: 100rpx;
  border-top-color: #C8896D;
  animation: spin 1s linear infinite;
}
.orb-core {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: radial-gradient(circle, #6B8979 0%, #4A6B5C 100%);
  box-shadow: 0 0 32rpx rgba(74, 107, 92, 0.4);
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
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
  margin-bottom: 32rpx;
}

/* ============ 结果头部 ============ */
.result-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 32rpx;
  padding: 0 8rpx;
}
.header-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4A6B5C;
  background: #EEF1ED;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  letter-spacing: 0.1em;
  margin-bottom: 16rpx;
}
.result-title {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  letter-spacing: 0.03em;
}
.match-tag {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: #EEF1ED;
  padding: 10rpx 20rpx;
  border-radius: 24rpx;
  border: 1rpx solid #C8D2CB;
}
.match-tag-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: #6B8979;
  box-shadow: 0 0 8rpx rgba(107, 137, 121, 0.5);
}
.match-tag-text {
  font-size: 22rpx;
  color: #4A6B5C;
  font-weight: 600;
  letter-spacing: 0.05em;
}

/* ============ 通用 section 卡 ============ */
.section-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 36rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
}
.section-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.section-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #4A6B5C;
  position: relative;
}
.section-dot::before {
  content: '';
  position: absolute;
  width: 18rpx;
  height: 18rpx;
  border-radius: 50%;
  background: rgba(74, 107, 92, 0.15);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
.section-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.05em;
}
.section-desc {
  font-size: 26rpx;
  color: #6B6862;
  line-height: 1.7;
  margin-bottom: 28rpx;
  display: block;
}

/* ============ 多维画像 ============ */
.dimension-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
.dimension-item {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.dimension-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dimension-name {
  font-size: 26rpx;
  color: #2C2A28;
  font-weight: 600;
}
.dimension-pill {
  padding: 4rpx 14rpx;
  border-radius: 14rpx;
}
.dimension-level {
  font-size: 22rpx;
  font-weight: 600;
}
.dimension-bar {
  height: 10rpx;
  background: #F0EBE0;
  border-radius: 5rpx;
  overflow: hidden;
}
.dimension-fill {
  height: 100%;
  border-radius: 5rpx;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ============ 辨证 ============ */
.diagnosis-main {
  display: flex;
  align-items: center;
  gap: 28rpx;
  margin-bottom: 28rpx;
  padding: 24rpx;
  background: #F7F3EB;
  border-radius: 24rpx;
}
.diagnosis-stamp {
  width: 120rpx;
  height: 120rpx;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.15);
  border: 3rpx solid rgba(255, 255, 255, 0.4);
  position: relative;
  overflow: hidden;
}
.diagnosis-stamp::before {
  content: '';
  position: absolute;
  inset: 6rpx;
  border: 1rpx dashed rgba(255, 255, 255, 0.4);
  border-radius: 8rpx;
}
.stamp-element {
  font-size: 56rpx;
  color: #FCFAF6;
  font-weight: 700;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.diagnosis-info {
  flex: 1;
  min-width: 0;
}
.diagnosis-name {
  font-size: 32rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  margin-bottom: 12rpx;
  letter-spacing: 0.03em;
}
.diagnosis-meta-row {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
}
.meta-pill {
  font-size: 22rpx;
  color: #4A6B5C;
  background: #EEF1ED;
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
}

.diagnosis-aux {
  margin-bottom: 24rpx;
}
.aux-title {
  font-size: 24rpx;
  color: #9C9585;
  margin-bottom: 14rpx;
  display: block;
  letter-spacing: 0.05em;
}
.aux-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.aux-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #F7F3EB;
  padding: 16rpx 20rpx;
  border-radius: 16rpx;
  border: 1rpx solid #E8E2D5;
}
.aux-name {
  font-size: 26rpx;
  color: #2C2A28;
}
.aux-tendency {
  font-size: 24rpx;
  color: #C8896D;
  font-weight: 600;
  font-family: Georgia, serif;
}

.evidence-box {
  background: #F7F3EB;
  border-radius: 20rpx;
  padding: 24rpx;
  border-left: 4rpx solid #C8896D;
}
.evidence-title {
  font-size: 24rpx;
  font-weight: 700;
  color: #C8896D;
  margin-bottom: 14rpx;
  display: block;
  letter-spacing: 0.05em;
}
.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}
.evidence-item {
  display: flex;
  gap: 8rpx;
  align-items: flex-start;
}
.evidence-bullet {
  color: #C8896D;
  font-size: 26rpx;
  line-height: 1.7;
}
.evidence-text {
  flex: 1;
  font-size: 24rpx;
  color: #6B6862;
  line-height: 1.7;
}

/* ============ 音乐卡 ============ */
.music-card {
  background: linear-gradient(135deg, #FCFAF6 0%, #F5EBE3 100%);
}
.music-main {
  margin-bottom: 20rpx;
}
.music-tone-wrap {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.music-tone {
  font-size: 52rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.05em;
  font-family: 'Kaiti SC', serif;
}
.music-bpm {
  font-size: 26rpx;
  color: #C8896D;
  font-weight: 600;
  font-family: Georgia, serif;
}
.music-tags {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
}
.music-tag {
  background: rgba(200, 137, 109, 0.15);
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
}
.music-tag-text {
  font-size: 22rpx;
  color: #C8896D;
  font-weight: 500;
}
.reason-box {
  background: rgba(255, 255, 255, 0.5);
  border-radius: 16rpx;
  padding: 20rpx;
  border: 1rpx dashed #E8E2D5;
}
.reason-title {
  font-size: 24rpx;
  font-weight: 700;
  color: #C8896D;
  margin-bottom: 8rpx;
  display: block;
  letter-spacing: 0.05em;
}
.reason-text {
  font-size: 24rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
}

/* ============ 行动按钮 ============ */
.action-wrap {
  margin-top: 16rpx;
  text-align: center;
}
.action-btn {
  height: 108rpx;
  border-radius: 54rpx;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  box-shadow: 0 12rpx 36rpx rgba(74, 107, 92, 0.30);
  transition: all 0.2s;
}
.action-btn:active {
  transform: scale(0.98);
}
.action-btn-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #F7F3EB;
  letter-spacing: 0.1em;
}
.action-btn-arrow {
  font-size: 30rpx;
  color: #F7F3EB;
  font-weight: 500;
}
.action-hint {
  display: block;
  font-size: 22rpx;
  color: #9C9585;
  margin-top: 20rpx;
  letter-spacing: 0.05em;
}
</style>