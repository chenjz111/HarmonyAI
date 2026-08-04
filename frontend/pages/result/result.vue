<template>
  <view class="container">
    <!-- 分析中 -->
    <view class="status-card" v-if="status === 'analyzing'">
      <view class="analyzing-orb">
        <view class="orb-ring orb-ring-1"></view>
        <view class="orb-ring orb-ring-2"></view>
        <view class="orb-ring orb-ring-3"></view>
        <view class="orb-core"></view>
      </view>
      <text class="status-title">AI 正在分析</text>
      <text class="status-desc">{{ statusMessage }}</text>
      <progress-bar :progress="analysisProgress" label="分析进度" />
    </view>

    <!-- 分析成功 -->
    <view v-else-if="status === 'success' && result">
      <!-- 顶部标题 -->
      <view class="result-header">
        <view>
          <text class="header-tag">分析结果</text>
          <text class="result-title">你的情绪画像</text>
        </view>
        <view class="match-tag" v-if="result.output.prescription.matched">
          <text class="match-tag-dot"></text>
          <text class="match-tag-text">已匹配</text>
        </view>
      </view>

      <!-- 多维画像 -->
      <view class="section-card">
        <view class="section-title-row">
          <view class="section-dot"></view>
          <text class="section-title">多维情绪画像</text>
        </view>
        <text class="section-desc">{{ result.output.profile.summary }}</text>
        <view class="dimension-list">
          <view class="dimension-item" v-for="(dim, idx) in result.output.profile.dimensions" :key="idx">
            <view class="dimension-info">
              <text class="dimension-name">{{ dim.name }}</text>
              <view class="dimension-pill" :style="{ background: dim.color + '18', color: dim.color }">
                <text class="dimension-level">{{ dim.level }}</text>
              </view>
            </view>
            <view class="dimension-bar">
              <view class="dimension-fill" :style="{ width: dim.score + '%', background: dim.color }"></view>
            </view>
          </view>
        </view>
      </view>

      <!-- 辨证 -->
      <view class="section-card">
        <view class="section-title-row">
          <view class="section-dot" style="background: #C8896D"></view>
          <text class="section-title">辅助辨证倾向</text>
        </view>

        <!-- 主证 印章式 -->
        <view class="diagnosis-main">
          <view class="diagnosis-stamp" :style="{ background: elementColor(result.output.diagnosis.primary.element) }">
            <text class="stamp-element">{{ result.output.diagnosis.primary.element }}</text>
          </view>
          <view class="diagnosis-info">
            <text class="diagnosis-name">{{ result.output.diagnosis.primary.name }}</text>
            <view class="diagnosis-meta-row">
              <text class="meta-pill">{{ result.output.diagnosis.primary.organ }} · 主脏</text>
              <text class="meta-pill">{{ result.output.diagnosis.primary.severity_name }}</text>
            </view>
          </view>
        </view>

        <view class="diagnosis-aux" v-if="result.output.diagnosis.auxiliary.length">
          <text class="aux-title">其他倾向</text>
          <view class="aux-list">
            <view class="aux-item" v-for="(aux, idx) in result.output.diagnosis.auxiliary" :key="idx">
              <text class="aux-name">{{ aux.name }}</text>
              <text class="aux-tendency">{{ aux.tendency }}</text>
            </view>
          </view>
        </view>

        <view class="evidence-box">
          <text class="evidence-title">分析依据</text>
          <view class="evidence-list">
            <view class="evidence-item" v-for="(ev, idx) in result.output.diagnosis.evidence" :key="idx">
              <text class="evidence-bullet">·</text>
              <text class="evidence-text">{{ ev }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 音乐推荐 -->
      <view class="section-card music-card">
        <view class="section-title-row">
          <view class="section-dot" style="background: #D4A574"></view>
          <text class="section-title">音乐处方</text>
        </view>
        <view class="music-main">
          <view class="music-tone-wrap">
            <text class="music-tone">{{ result.output.prescription.music_feature.tone_name }}</text>
            <text class="music-bpm">{{ result.output.prescription.music_feature.bpm }} BPM</text>
          </view>
          <view class="music-tags">
            <view class="music-tag" v-for="(inst, idx) in result.output.prescription.music_feature.instruments" :key="idx">
              <text class="music-tag-text">{{ inst }}</text>
            </view>
          </view>
        </view>
        <view class="reason-box">
          <text class="reason-title">推荐原因</text>
          <text class="reason-text">{{ result.output.prescription.music_reason }}</text>
        </view>
      </view>

      <!-- 行动按钮 -->
      <view class="action-wrap">
        <view class="action-btn" @click="goPlayer">
          <text class="action-btn-text">开始聆听</text>
          <text class="action-btn-arrow">→</text>
        </view>
        <text class="action-hint">戴上耳机 · 找个安静的角落</text>
      </view>
    </view>

    <!-- 降级 -->
    <error-state
      v-else-if="status === 'degraded'"
      title="AI 分析已降级"
      message="当前使用轻量模型生成结果，推荐原因可能不够精细，但仍可继续使用。"
      :showFallback="true"
      fallbackText="继续查看结果"
      @retry="loadResult"
      @fallback="forceShowResult"
    />

    <!-- 安全阻断 -->
    <error-state
      v-else-if="status === 'blocked'"
      title="安全提醒"
      message="检测到描述中可能包含高风险内容。建议你及时寻求专业心理医生或精神科医生的帮助。"
      :showRetry="false"
      :showFallback="false"
    />

    <!-- 错误 -->
    <error-state
      v-else-if="status === 'error'"
      title="分析失败"
      :message="errorMsg"
      @retry="loadResult"
    />
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { fetchAnalysisStatus, fetchAnalysisResult } from '@/common/api-v2.js'

export default {
  components: { ProgressBar, ErrorState },
  data() {
    return {
      status: 'analyzing',
      analysisProgress: 0,
      statusMessage: '正在整合问卷与描述信息...',
      result: null,
      errorMsg: ''
    }
  },
  onLoad() {
    this.loadResult()
  },
  methods: {
    async loadResult() {
      this.status = 'analyzing'
      this.analysisProgress = 0
      this.statusMessage = '正在整合问卷与描述信息...'

      const sessionId = uni.getStorageSync('harmony_session_id_v2')
      if (!sessionId) {
        this.status = 'error'
        this.errorMsg = '未找到会话信息，请重新评估'
        return
      }

      try {
        while (true) {
          const statusRes = await fetchAnalysisStatus(sessionId)
          this.status = statusRes.status
          this.analysisProgress = statusRes.progress
          this.statusMessage = statusRes.message

          if (statusRes.status === 'success') {
            const resultRes = await fetchAnalysisResult(sessionId)
            this.result = resultRes
            uni.setStorageSync('harmony_result_v2', JSON.stringify(resultRes))
            break
          }
          if (statusRes.status === 'degraded' || statusRes.status === 'blocked') break
          await new Promise(r => setTimeout(r, 800))
        }
      } catch (e) {
        this.status = 'error'
        this.errorMsg = e.message || '分析失败，请检查网络'
      }
    },
    forceShowResult() {
      const cached = uni.getStorageSync('harmony_assessment_v2')
      if (cached) {
        this.result = JSON.parse(cached)
        this.status = 'success'
      }
    },
    goPlayer() {
      uni.navigateTo({ url: '/pages/player-v2/player-v2' })
    },
    elementColor(element) {
      const map = {
        '木': '#6B8979',
        '火': '#C8896D',
        '土': '#D4A574',
        '金': '#A8B5A0',
        '水': '#4A6FA5'
      }
      return map[element] || '#4A6B5C'
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