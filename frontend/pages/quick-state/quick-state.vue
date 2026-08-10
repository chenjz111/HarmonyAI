<template>
  <view class="qs-page">
    <!-- 水墨背景 -->
    <view class="ink-bg-circle ink-bg-tl"></view>
    <view class="ink-bg-circle ink-bg-br"></view>

    <!-- 顶部 -->
    <view class="qs-header">
      <text class="qs-title">{{ phaseLabel }}</text>
      <text class="qs-subtitle">快速状态评估 · 约60秒</text>
    </view>

    <scroll-view scroll-y class="qs-scroll">
      <!-- 5个滑块题 -->
      <view v-for="(q, i) in scaleQuestions" :key="q.question_id" class="qs-card ink-card">
        <view class="qs-card-header">
          <view class="qs-badge"><text class="qs-badge-text">{{ i + 1 }}</text></view>
          <text class="qs-text">{{ q.text }}</text>
        </view>

        <!-- 滑块 -->
        <view class="qs-slider-wrap">
          <view class="qs-slider-labels">
            <text class="qs-slider-min">{{ q.label_min }}</text>
            <text class="qs-slider-value" :class="{ 'qs-value-warn': (answers[q.question_id] || 0) >= 7 }">{{ answers[q.question_id] !== undefined ? answers[q.question_id] : 0 }}</text>
            <text class="qs-slider-max">{{ q.label_max }}</text>
          </view>
          <slider
            :min="q.min"
            :max="q.max"
            :step="q.step"
            :value="answers[q.question_id] || 0"
            activeColor="#4A6B5C"
            backgroundColor="#E8E0CC"
            block-color="#4A6B5C"
            block-size="32"
            @change="onSliderChange(q.question_id, $event)"
          />
          <!-- 刻度点 -->
          <view class="qs-ticks">
            <text v-for="n in 11" :key="n-1" class="qs-tick" :class="{ 'qs-tick-active': (answers[q.question_id] || 0) >= n-1 }">{{ n - 1 }}</text>
          </view>
        </view>
      </view>

      <!-- 目标选择 (qs06) -->
      <view class="qs-card ink-card">
        <view class="qs-card-header">
          <view class="qs-badge"><text class="qs-badge-text">6</text></view>
          <text class="qs-text">{{ goalQuestion.text }}</text>
        </view>
        <view class="qs-goal-grid">
          <view
            v-for="opt in goalQuestion.options"
            :key="opt.value"
            class="qs-goal-btn"
            :class="{ 'opt-selected': answers[goalQuestion.question_id] === opt.value }"
            @tap="onSelectGoal(opt.value)"
          >
            <text class="qs-goal-label">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 提交按钮 -->
      <view class="qs-submit-wrap">
        <view
          class="qs-submit-btn"
          :class="{ 'qs-submit-disabled': !canSubmit }"
          @tap="handleSubmit"
        >
          <text class="qs-submit-text">{{ submitting ? '提交中...' : '提交评估' }}</text>
        </view>
        <text class="qs-hint">听前评估将用于匹配音乐处方</text>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { quickStateV1 } from "@/common/questionnaire-data.js"
import { submitQuickState, loadSession, saveSession } from "@/common/api-v2.js"

export default {
  data() {
    return {
      questions: quickStateV1.questions,
      answers: {},
      phase: "pre_listening",
      submitting: false,
    }
  },

  computed: {
    scaleQuestions() {
      return this.questions.filter((q) => q.type === "scale_0_10")
    },
    goalQuestion() {
      return this.questions.find((q) => q.type === "single_choice") || {}
    },
    phaseLabel() {
      return this.phase === "pre_listening" ? "听前状态" : "听后状态"
    },
    canSubmit() {
      const allAnswered = this.questions.every((q) => {
        const ans = this.answers[q.question_id]
        return ans !== undefined && ans !== null
      })
      return allAnswered && !this.submitting
    },
  },

  onLoad(opts) {
    if (opts && opts.phase) {
      this.phase = opts.phase
    }
  },

  methods: {
    onSliderChange(questionId, e) {
      this.$set(this.answers, questionId, e.detail.value)
    },

    onSelectGoal(value) {
      this.$set(this.answers, this.goalQuestion.question_id, value)
    },

    async handleSubmit() {
      if (!this.canSubmit) {
        uni.showToast({ title: "请完成所有题目", icon: "none" })
        return
      }

      this.submitting = true
      uni.showLoading({ title: "提交中..." })

      try {
        let session = loadSession()
        if (!session) {
          const { createSession } = await import("@/common/api-v2.js")
          session = await createSession({ entry_mode: "quick" })
          saveSession(session)
        }

        const answersArray = this.questions.map((q) => ({
          question_id: q.question_id,
          value: this.answers[q.question_id],
        }))

        const result = await submitQuickState({
          sessionId: session.session_id,
          phase: this.phase,
          answers: answersArray,
        })

        uni.showToast({ title: "提交成功", icon: "success" })

        // 听前 → 跳到音乐播放页；听后 → 跳到反馈页
        setTimeout(() => {
          if (this.phase === "pre_listening") {
            uni.redirectTo({ url: "/pages/player-v2/player-v2?quick_state=true" })
          } else {
            uni.redirectTo({ url: "/pages/feedback-v2/feedback-v2?post_quick=true" })
          }
        }, 1000)
      } catch (err) {
        uni.showToast({ title: err.message || "提交失败", icon: "none", duration: 3000 })
      } finally {
        this.submitting = false
        uni.hideLoading()
      }
    },
  },
}
</script>

<style scoped>
.qs-page {
  min-height: 100vh;
  background: #F7F3EB;
  position: relative;
  overflow: hidden;
}

.ink-bg-circle {
  position: fixed;
  border-radius: 50%;
  filter: blur(60rpx);
  z-index: 0;
  pointer-events: none;
}
.ink-bg-tl {
  width: 400rpx; height: 400rpx;
  top: -100rpx; left: -100rpx;
  background: rgba(74, 107, 92, 0.06);
}
.ink-bg-br {
  width: 500rpx; height: 500rpx;
  bottom: -150rpx; right: -150rpx;
  background: rgba(200, 137, 109, 0.05);
}

.qs-header {
  position: relative;
  z-index: 1;
  padding: 60rpx 40rpx 20rpx;
  text-align: center;
}
.qs-title {
  font-size: 44rpx;
  font-weight: 700;
  color: #4A6B5C;
  letter-spacing: 4rpx;
  display: block;
  margin-bottom: 8rpx;
}
.qs-subtitle {
  font-size: 24rpx;
  color: #9C9585;
  letter-spacing: 2rpx;
}

.qs-scroll {
  position: relative;
  z-index: 1;
  height: calc(100vh - 180rpx);
  padding: 0 40rpx 120rpx;
}

.qs-card {
  background: #FFFEFA;
  border-radius: 24rpx;
  padding: 36rpx 32rpx;
  box-shadow: 0 4rpx 16rpx rgba(74, 107, 92, 0.12);
  border: 1rpx solid #D9D0BD;
  margin-bottom: 24rpx;
}

.qs-card-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 28rpx;
}
.qs-badge {
  width: 48rpx;
  height: 48rpx;
  border-radius: 10rpx;
  background: #4A6B5C;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.qs-badge-text {
  color: #FFFEFA;
  font-size: 26rpx;
  font-weight: 700;
}
.qs-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #2C2C2A;
  flex: 1;
}

/* 滑块区 */
.qs-slider-wrap {
  padding: 0 8rpx;
}
.qs-slider-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.qs-slider-min {
  font-size: 22rpx;
  color: #9C9585;
}
.qs-slider-max {
  font-size: 22rpx;
  color: #C44A3E;
}
.qs-slider-value {
  font-size: 48rpx;
  font-weight: 700;
  color: #4A6B5C;
  min-width: 80rpx;
  text-align: center;
}
.qs-value-warn {
  color: #C44A3E;
}

.qs-ticks {
  display: flex;
  justify-content: space-between;
  margin-top: 12rpx;
}
.qs-tick {
  font-size: 18rpx;
  color: #C5BBA5;
  width: 32rpx;
  text-align: center;
}
.qs-tick-active {
  color: #6B8B7C;
  font-weight: 600;
}

/* 目标选择 */
.qs-goal-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.qs-goal-btn {
  width: calc(33.33% - 11rpx);
  padding: 28rpx 12rpx;
  border-radius: 16rpx;
  border: 2rpx solid #D9D0BD;
  background: #FFFEFA;
  text-align: center;
  transition: all 0.2s;
}
.qs-goal-btn:active {
  transform: scale(0.96);
}
.qs-goal-btn.opt-selected {
  border-color: #4A6B5C;
  background: rgba(74, 107, 92, 0.08);
  box-shadow: 0 2rpx 8rpx rgba(74, 107, 92, 0.15);
}
.qs-goal-label {
  font-size: 28rpx;
  font-weight: 600;
  color: #2C2C2A;
}
.qs-goal-btn.opt-selected .qs-goal-label {
  color: #4A6B5C;
}

/* 提交 */
.qs-submit-wrap {
  margin-top: 16rpx;
  padding-bottom: 60rpx;
}
.qs-submit-btn {
  padding: 32rpx;
  border-radius: 32rpx;
  background: #4A6B5C;
  box-shadow: 0 4rpx 16rpx rgba(74, 107, 92, 0.3);
  text-align: center;
  transition: all 0.2s;
}
.qs-submit-btn:active {
  transform: scale(0.97);
}
.qs-submit-disabled {
  opacity: 0.4;
}
.qs-submit-text {
  color: #FFFEFA;
  font-size: 32rpx;
  font-weight: 600;
  letter-spacing: 4rpx;
}
.qs-hint {
  font-size: 22rpx;
  color: #9C9585;
  text-align: center;
  display: block;
  margin-top: 16rpx;
}
</style>
