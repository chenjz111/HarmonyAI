<template>
  <view class="container">
    <!-- 顶部标题 -->
    <view class="header">
      <text class="step-tag">第 2 步 · 选填</text>
      <text class="page-title">最近，发生了什么？</text>
      <text class="page-subtitle">用一段话描述你近期的情绪、睡眠或身体状况，字数不限；没有也可直接跳过。</text>
    </view>

    <progress-bar :progress="50" label="评估进度" />

    <!-- 处理状态卡 -->
    <view v-if="phase === 'processing'" class="processing-card">
      <view class="processing-orb">
        <view class="orb-ring orb-ring-1"></view>
        <view class="orb-ring orb-ring-2"></view>
        <view class="orb-core"></view>
      </view>
      <text class="processing-title">AI 正在理解你的描述</text>
      <text class="processing-desc">{{ processingMessage }}</text>
      <view class="processing-steps">
        <view class="proc-step" :class="{ done: procStep >= 1 }">
          <text class="proc-step-icon">{{ procStep >= 1 ? '✓' : '○' }}</text>
          <text class="proc-step-text">文本预处理</text>
        </view>
        <view class="proc-step" :class="{ done: procStep >= 2 }">
          <text class="proc-step-icon">{{ procStep >= 2 ? '✓' : '○' }}</text>
          <text class="proc-step-text">情绪与事件提取</text>
        </view>
        <view class="proc-step" :class="{ done: procStep >= 3 }">
          <text class="proc-step-icon">{{ procStep >= 3 ? '✓' : '○' }}</text>
          <text class="proc-step-text">证据结构化</text>
        </view>
      </view>
    </view>

    <!-- 处理完成卡 -->
    <view v-else-if="phase === 'done'" class="done-card">
      <view class="done-icon-wrap">
        <text class="done-icon">✓</text>
      </view>
      <text class="done-title">描述已处理完成</text>
      <view class="done-stats">
        <view class="done-stat">
          <text class="stat-num">{{ narrativeResult.evidence_count || 0 }}</text>
          <text class="stat-label">条证据</text>
        </view>
        <view class="done-divider"></view>
        <view class="done-stat">
          <text class="stat-num">{{ narrativeResult.confidence ? Math.round(narrativeResult.confidence * 100) : 0 }}%</text>
          <text class="stat-label">提取置信度</text>
        </view>
      </view>
      <text class="done-hint">这些信息将和问卷一起用于综合评估</text>
      <view class="btn btn-primary done-btn" @click="goNext">
        <text class="btn-text">继续填写问卷</text>
        <text class="btn-arrow">→</text>
      </view>
    </view>

    <!-- 降级提示卡 -->
    <view v-else-if="phase === 'degraded'" class="done-card">
      <view class="done-icon-wrap warn">
        <text class="done-icon">!</text>
      </view>
      <text class="done-title">文本分析暂不可用</text>
      <text class="done-desc">已保存你的描述，但 AI 提取暂时不可用。问卷评估不受影响，后续可恢复处理。</text>
      <view class="btn btn-primary done-btn" @click="goNext">
        <text class="btn-text">继续填写问卷</text>
        <text class="btn-arrow">→</text>
      </view>
    </view>

    <!-- 输入区（idle / error） -->
    <template v-else>
      <!-- 输入卡 -->
      <view class="narrative-card">
        <textarea
          class="narrative-area"
          v-model="narrativeText"
          placeholder="例如：最近工作压力大，晚上经常睡不着，容易烦躁..."
          maxlength="300"
          :disable-default-padding="true"
        />
        <view class="narrative-meta">
          <view class="narrative-tags-inline">
            <text class="tag-dot">·</text>
            <text class="tag-hint">自由书写，不打分不评判</text>
          </view>
          <view class="count-ring" :class="{ active: narrativeText.length > 0 }">
            <text class="count-text">{{ narrativeText.length }}</text>
            <text class="count-divider">/</text>
            <text class="count-max">300</text>
          </view>
        </view>
      </view>

      <!-- 隐私提示 -->
      <view class="privacy-hint">
        <text class="privacy-icon">🔒</text>
        <text class="privacy-text">请不要填写姓名、电话、身份证等个人隐私信息</text>
      </view>

      <!-- 快捷标签 -->
      <view class="prompts">
        <view class="prompts-header">
          <text class="prompts-title">快捷输入</text>
          <text class="prompts-sub">点击填充</text>
        </view>
        <view class="prompt-tags">
          <view
            class="prompt-tag"
            v-for="(tag, index) in prompts"
            :key="index"
            @click="usePrompt(tag)"
          >
            <text class="prompt-tag-text">{{ tag }}</text>
          </view>
        </view>
      </view>

      <error-state
        v-if="phase === 'error'"
        title="提交失败"
        :message="errorMsg"
        :showFallback="true"
        fallbackText="跳过此步"
        @retry="submitNarrative"
        @fallback="skip"
      />

      <!-- 底部按钮 -->
      <view class="btn-group">
        <view class="btn btn-secondary" @click="skip">
          <text class="btn-text">跳过</text>
        </view>
        <view class="btn btn-primary" @click="submitNarrative">
          <text class="btn-text">{{ narrativeText.trim() ? '提交并分析' : '跳过' }}</text>
          <text class="btn-arrow" v-if="narrativeText.trim()">→</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { submitNarrative, getNarrativeStatus } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'

export default {
  components: { ProgressBar, ErrorState },
  data() {
    return {
      narrativeText: '',
      phase: 'idle', // idle | processing | done | degraded | error
      procStep: 0,
      processingMessage: '正在预处理文本...',
      narrativeResult: { evidence_count: 0, confidence: 0 },
      errorMsg: '',
      prompts: [
        '最近失眠多梦',
        '工作压力大、容易紧张',
        '情绪低落、提不起劲',
        '最近容易烦躁',
        '食欲不振、消化不适',
        '白天疲惫、没有精神'
      ]
    }
  },
  methods: {
    usePrompt(text) {
      this.narrativeText = text
      uni.showToast({ title: '已填充，可继续编辑', icon: 'none', duration: 1200 })
    },

    skip() {
      updateSprint3Session({ narrative_text: null, narrative_skipped: true })
      uni.navigateTo({ url: '/pages/questionnaire-v2/questionnaire-v2' })
    },

    async submitNarrative() {
      const text = this.narrativeText.trim()
      if (!text) return this.skip()

      this.phase = 'processing'
      this.procStep = 0
      this.processingMessage = '正在预处理文本...'

      try {
        const session = getSprint3Session()

        // 步骤动画
        const advanceStep = async (step, msg, delay = 700) => {
          this.procStep = step
          this.processingMessage = msg
          await new Promise(r => setTimeout(r, delay))
        }

        await advanceStep(1, '正在预处理文本...')
        const result = await submitNarrative({ sessionId: session?.session_id, text })
        await advanceStep(2, '正在提取情绪与事件...')
        await advanceStep(3, '正在结构化证据...')

        // 轮询状态（mock 直接返回 processed）
        let status
        try {
          status = await getNarrativeStatus(session?.session_id)
        } catch (e) {
          status = { status: 'processed', evidence_items_extracted: result?.evidence_items_extracted || 0 }
        }

        updateSprint3Session({ narrative_text: text, narrative_skipped: false })

        if (status?.status === 'processed' || result?.processing_status === 'processed') {
          this.narrativeResult = {
            evidence_count: status?.evidence_items_extracted ?? result?.evidence_items_extracted ?? 0,
            confidence: status?.extraction_confidence_avg ?? result?.extraction_confidence_avg ?? 0,
          }
          this.phase = 'done'
        } else if (status?.status === 'degraded' || result?.processing_status === 'degraded') {
          this.phase = 'degraded'
        } else {
          // 未知状态，当作完成处理
          this.narrativeResult = {
            evidence_count: result?.evidence_items_extracted ?? 0,
            confidence: result?.extraction_confidence_avg ?? 0,
          }
          this.phase = 'done'
        }
      } catch (err) {
        this.phase = 'error'
        this.errorMsg = err.message || '文本分析失败，可跳过此步继续'
      }
    },

    goNext() {
      uni.navigateTo({ url: '/pages/questionnaire-v2/questionnaire-v2' })
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #F7F3EB;
  padding: 40rpx 40rpx 200rpx;
  box-sizing: border-box;
}

/* 顶部 */
.header { margin-bottom: 32rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4A6B5C;
  background: #EEF1ED;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  letter-spacing: 0.1em;
  margin-bottom: 16rpx;
}
.page-title {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.03em;
  display: block;
  margin-bottom: 12rpx;
}
.page-subtitle {
  font-size: 26rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
}

/* 输入卡 */
.narrative-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
  margin-bottom: 24rpx;
}
.narrative-area {
  width: 100%;
  min-height: 280rpx;
  background: transparent;
  font-size: 28rpx;
  color: #2C2A28;
  line-height: 1.8;
  box-sizing: border-box;
  letter-spacing: 0.02em;
}
.narrative-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx dashed #E8E2D5;
}
.narrative-tags-inline {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.tag-dot { color: #C8896D; font-size: 24rpx; font-weight: 700; }
.tag-hint { font-size: 22rpx; color: #9C9585; }
.count-ring {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
  padding: 6rpx 16rpx;
  border-radius: 24rpx;
  background: #F7F3EB;
  transition: all 0.2s;
}
.count-ring.active { background: #EEF1ED; }
.count-text { font-size: 24rpx; color: #4A6B5C; font-weight: 700; }
.count-divider { font-size: 20rpx; color: #9C9585; }
.count-max { font-size: 20rpx; color: #9C9585; }

/* 隐私提示 */
.privacy-hint {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 20rpx 28rpx;
  background: #FDF8F0;
  border-radius: 20rpx;
  border: 1rpx solid #F0E5D0;
  margin-bottom: 32rpx;
}
.privacy-icon { font-size: 24rpx; }
.privacy-text { font-size: 22rpx; color: #9C8866; line-height: 1.6; }

/* 快捷标签 */
.prompts { margin-bottom: 32rpx; }
.prompts-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.prompts-title { font-size: 26rpx; color: #2C2A28; font-weight: 600; letter-spacing: 0.05em; }
.prompts-sub { font-size: 22rpx; color: #9C9585; }
.prompt-tags { display: flex; flex-wrap: wrap; gap: 16rpx; }
.prompt-tag {
  padding: 16rpx 28rpx;
  border-radius: 36rpx;
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
  transition: all 0.2s;
}
.prompt-tag:active { background: #EEF1ED; border-color: #4A6B5C; transform: scale(0.96); }
.prompt-tag-text { font-size: 26rpx; color: #4A6B5C; font-weight: 500; letter-spacing: 0.02em; }

/* 处理中 */
.processing-card {
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 72rpx 48rpx 56rpx;
  text-align: center;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 8rpx 28rpx rgba(74, 107, 92, 0.08);
}
.processing-orb {
  width: 180rpx;
  height: 180rpx;
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
  opacity: 0.25;
}
.orb-ring-1 { width: 180rpx; height: 180rpx; border-top-color: #4A6B5C; animation: spin 2s linear infinite; }
.orb-ring-2 { width: 130rpx; height: 130rpx; border-top-color: #6B8979; animation: spin 1.5s linear infinite reverse; }
.orb-core {
  width: 44rpx; height: 44rpx; border-radius: 50%;
  background: radial-gradient(circle, #6B8979 0%, #4A6B5C 100%);
  box-shadow: 0 0 28rpx rgba(74, 107, 92, 0.4);
}
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.processing-title { font-size: 34rpx; font-weight: 700; color: #2C2A28; display: block; margin-bottom: 12rpx; }
.processing-desc { font-size: 26rpx; color: #6B6862; display: block; margin-bottom: 40rpx; }
.processing-steps { display: flex; flex-direction: column; gap: 20rpx; align-items: flex-start; }
.proc-step { display: flex; align-items: center; gap: 16rpx; opacity: 0.4; transition: all 0.3s; }
.proc-step.done { opacity: 1; }
.proc-step-icon { font-size: 32rpx; color: #4A6B5C; font-weight: 700; }
.proc-step-text { font-size: 26rpx; color: #2C2A28; }

/* 完成卡 */
.done-card {
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 64rpx 48rpx 48rpx;
  text-align: center;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 8rpx 28rpx rgba(74, 107, 92, 0.08);
}
.done-icon-wrap {
  width: 120rpx; height: 120rpx; border-radius: 50%;
  background: #EEF1ED; display: flex; align-items: center; justify-content: center;
  margin: 0 auto 32rpx;
}
.done-icon-wrap.warn { background: #FDF0EA; }
.done-icon { font-size: 56rpx; color: #4A6B5C; font-weight: 700; }
.done-icon-wrap.warn .done-icon { color: #C8896D; }
.done-title { font-size: 36rpx; font-weight: 700; color: #2C2A28; display: block; margin-bottom: 24rpx; }
.done-desc { font-size: 26rpx; color: #6B6862; line-height: 1.7; display: block; margin-bottom: 32rpx; }
.done-stats {
  display: flex; align-items: center; justify-content: center; gap: 40rpx;
  padding: 32rpx; background: #F7F3EB; border-radius: 24rpx; margin-bottom: 24rpx;
}
.done-stat { display: flex; flex-direction: column; align-items: center; gap: 8rpx; }
.stat-num { font-size: 52rpx; font-weight: 700; color: #4A6B5C; font-family: Georgia, serif; }
.stat-label { font-size: 22rpx; color: #9C9585; }
.done-divider { width: 1rpx; height: 60rpx; background: #E8E2D5; }
.done-hint { font-size: 24rpx; color: #9C9585; display: block; margin-bottom: 40rpx; }
.done-btn {
  width: 100%; height: 100rpx; border-radius: 50rpx;
  display: flex; align-items: center; justify-content: center; gap: 12rpx;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  box-shadow: 0 12rpx 36rpx rgba(74, 107, 92, 0.30);
}
.done-btn:active { transform: scale(0.98); }

/* 底部按钮 */
.btn-group {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  display: flex; gap: 20rpx;
  padding: 24rpx 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: rgba(247, 243, 235, 0.95);
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border-top: 1rpx solid #E8E2D5;
  box-sizing: border-box;
}
.btn {
  flex: 1; height: 96rpx; border-radius: 48rpx;
  display: flex; align-items: center; justify-content: center; gap: 8rpx;
  transition: all 0.2s;
}
.btn:active { transform: scale(0.98); }
.btn-primary {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.20);
}
.btn-primary .btn-text { color: #F7F3EB; font-size: 30rpx; font-weight: 600; letter-spacing: 0.05em; }
.btn-arrow { font-size: 30rpx; color: #F7F3EB; font-weight: 500; }
.btn-secondary { background: #FCFAF6; border: 1rpx solid #E8E2D5; }
.btn-secondary .btn-text { color: #4A6B5C; font-size: 30rpx; font-weight: 600; }
</style>
