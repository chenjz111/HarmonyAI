<template>
  <view class="container">
    <!-- 顶部标题区 -->
    <view class="header">
      <text class="step-tag">第 3 步 · 必填</text>
      <view class="progress-row">
        <text class="page-title">健康评估</text>
        <view class="page-counter">
          <text class="counter-current">{{ currentIndex + 1 }}</text>
          <text class="counter-divider">/</text>
          <text class="counter-total">{{ questions.length }}</text>
        </view>
      </view>
      <text class="page-subtitle">请根据最近一周的真实感受作答 · 选完自动进入下一题</text>
    </view>

    <!-- 自定义进度条 -->
    <view class="custom-progress">
      <view
        v-for="(q, idx) in questions"
        :key="idx"
        class="progress-segment"
        :class="{
          done: idx < currentIndex,
          current: idx === currentIndex,
          pending: idx > currentIndex
        }"
      ></view>
    </view>

    <!-- Likert 题型 -->
    <view class="question-card" v-if="currentQuestion.type === 'likert'">
      <view class="question-num">Q{{ currentIndex + 1 }}</view>
      <text class="question-text">{{ currentQuestion.text }}</text>
      <view class="options-row">
        <view
          class="option-item"
          v-for="opt in options"
          :key="opt.value"
          :class="{ selected: answers[currentQuestion.id] === opt.value }"
          @click="select(opt.value)"
        >
          <view class="option-circle">
            <text class="option-num">{{ opt.value }}</text>
          </view>
          <text class="option-label">{{ opt.label }}</text>
        </view>
      </view>
    </view>

    <!-- Image 题型 -->
    <view class="question-card" v-else-if="currentQuestion.type === 'image'">
      <view class="question-num">Q{{ currentIndex + 1 }}</view>
      <image-choice
        :question="currentQuestion.text"
        :options="currentQuestion.options"
        :value="answers[currentQuestion.id]"
        :columns="currentQuestion.columns || 2"
        @change="select"
      />
    </view>

    <view class="question-card" v-else-if="currentQuestion.type === 'multi'">
      <view class="question-num">Q{{ currentIndex + 1 }}</view>
      <text class="question-text">{{ currentQuestion.text }}</text>
      <view class="options-row" style="flex-wrap: wrap;">
        <view
          class="option-item"
          v-for="opt in currentQuestion.options"
          :key="opt.value"
          :class="{ selected: (answers[currentQuestion.id] || []).includes(opt.value) }"
          @click="select(opt.value)"
        >
          <view class="option-circle"><text class="option-num">{{ opt.icon }}</text></view>
          <text class="option-label">{{ opt.label }}</text>
        </view>
      </view>
    </view>
    <error-state
      v-if="status === 'error'"
      title="提交失败"
      :message="errorMsg"
      @retry="submit"
    />

    <!-- 底部导航 -->
    <view class="btn-group">
      <view class="btn btn-secondary" :class="{ disabled: currentIndex === 0 }" @click="prev">
        <text class="btn-text">← 上一题</text>
      </view>
      <view class="btn btn-primary" :class="{ disabled: !canNext }" @click="next">
        <text class="btn-text">{{ isLast ? '提交评估' : '下一题' }}</text>
        <text class="btn-arrow" v-if="!isLast">→</text>
      </view>
    </view>
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ImageChoice from '@/components/sprint3/image-choice.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { runWorkflow } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'

const likert = [
  { value: 0, label: '完全没有' },
  { value: 1, label: '有几天' },
  { value: 2, label: '近一半天数' },
  { value: 3, label: '大多数天' },
  { value: 4, label: '几乎每天' }
]

export default {
  components: { ProgressBar, ImageChoice, ErrorState },
  data() {
    return {
      startedAt: new Date().toISOString(),
      currentIndex: 0,
      answers: {},
      options: likert,
      questions: [
        {
          id: 'q01_mood_weather', type: 'image', apiType: 'visual_single', columns: 3,
          text: '如果用天气形容最近一周的心情，最接近哪一种？',
          options: [
            { value: 'sunny', label: '晴空万里', icon: '晴', color: '#D4A574', bgColor: '#F7EFE3' },
            { value: 'lightly_cloudy', label: '阴晴不定', icon: '云', color: '#8FA89C', bgColor: '#EEF1ED' },
            { value: 'cloudy', label: '多云', icon: '阴', color: '#7C8C86', bgColor: '#E8ECEA' },
            { value: 'rainy', label: '连绵阴雨', icon: '雨', color: '#4A6FA5', bgColor: '#E8EDF3' },
            { value: 'stormy', label: '雷电交加', icon: '雷', color: '#8C5A55', bgColor: '#F2E8E5' }
          ]
        },
        { id: 'q02_tension_worry', type: 'likert', apiType: 'frequency_0_4', text: '我感到紧张、担忧，难以放松' },
        {
          id: 'q03_overthinking', type: 'image', apiType: 'visual_single', columns: 3,
          text: '最近一周，你的思绪更像哪一种海面？',
          options: [
            { value: 'calm', label: '平静', icon: '静', color: '#6B8979', bgColor: '#EEF1ED' },
            { value: 'ripple', label: '微澜', icon: '漪', color: '#8FA89C', bgColor: '#F0F4F1' },
            { value: 'waves', label: '起浪', icon: '浪', color: '#4A6FA5', bgColor: '#E8EDF3' },
            { value: 'swell', label: '涌动', icon: '涌', color: '#C8896D', bgColor: '#F5EBE3' },
            { value: 'storm', label: '风暴', icon: '暴', color: '#8C5A55', bgColor: '#F2E8E5' }
          ]
        },
        { id: 'q04_irritability_anger', type: 'likert', apiType: 'frequency_0_4', text: '我比平时更容易烦躁或发脾气' },
        { id: 'q05_low_mood', type: 'likert', apiType: 'frequency_0_4', text: '我感到情绪低落或难过' },
        { id: 'q06_interest_loss', type: 'likert', apiType: 'frequency_0_4', text: '我对原本感兴趣的事情提不起兴趣' },
        { id: 'q07_fear_unease', type: 'likert', apiType: 'frequency_0_4', text: '我感到害怕、不安，或总担心会发生不好的事' },
        { id: 'q08_sleep_disturbance', type: 'likert', apiType: 'frequency_0_4', text: '我入睡困难、容易醒，或睡后仍不解乏' },
        {
          id: 'q09_low_energy', type: 'image', apiType: 'visual_single', columns: 3,
          text: '如果身体像一块电池，最近一周的电量更接近？',
          options: [
            { value: 'full', label: '满格', icon: '满', color: '#6B8979', bgColor: '#EEF1ED' },
            { value: 'three_quarters', label: '四分之三', icon: '¾', color: '#8FA89C', bgColor: '#F0F4F1' },
            { value: 'half', label: '一半', icon: '½', color: '#D4A574', bgColor: '#F5EBD9' },
            { value: 'quarter', label: '较低', icon: '¼', color: '#C8896D', bgColor: '#F5EBE3' },
            { value: 'empty', label: '快耗尽', icon: '空', color: '#8C5A55', bgColor: '#F2E8E5' }
          ]
        },
        { id: 'q10_appetite_change', type: 'likert', apiType: 'frequency_0_4', text: '我的食欲或进食量与平时相比有明显变化' },
        { id: 'q11_daily_impact', type: 'likert', apiType: 'frequency_0_4', text: '这些状态影响了我的学习、工作或日常生活' },
        {
          id: 'q12_physical_safety', type: 'multi', apiType: 'visual_multi',
          text: '最近一周出现过哪些身体感受或需要关注的情况？（可多选）',
          options: [
            { value: 'neck_tension', label: '肩颈紧张', icon: '颈' },
            { value: 'head_heaviness', label: '头部沉重', icon: '头' },
            { value: 'palpitation', label: '心慌心悸', icon: '心' },
            { value: 'stomach_discomfort', label: '胃部不适', icon: '胃' },
            { value: 'fatigue', label: '明显疲惫', icon: '疲' },
            { value: 'other', label: '其他不适', icon: '其' },
            { value: 'severe_chest_pain', label: '严重或持续胸痛', icon: '警' },
            { value: 'severe_breathing_difficulty', label: '明显呼吸困难', icon: '警' },
            { value: 'self_harm_thoughts', label: '有伤害自己的想法', icon: '援' },
            { value: 'none', label: '以上均无', icon: '无' }
          ]
        }
      ],
      status: 'idle',
      errorMsg: ''
    }
  },
  computed: {
    currentQuestion() { return this.questions[this.currentIndex] },
    isLast() { return this.currentIndex === this.questions.length - 1 },
    canNext() {
      const value = this.answers[this.currentQuestion.id]
      return this.currentQuestion.type === 'multi'
        ? Array.isArray(value) && value.length > 0
        : Object.prototype.hasOwnProperty.call(this.answers, this.currentQuestion.id)
    }
  },
  methods: {
    select(value) {
      const question = this.currentQuestion
      if (question.type === 'multi') {
        const current = this.answers[question.id] || []
        if (value === 'none') {
          this.answers[question.id] = current.includes('none') ? [] : ['none']
        } else {
          const withoutNone = current.filter(item => item !== 'none')
          this.answers[question.id] = withoutNone.includes(value)
            ? withoutNone.filter(item => item !== value)
            : [...withoutNone, value]
        }
      } else {
        this.answers[question.id] = value
        if (!this.isLast) setTimeout(() => { this.currentIndex++ }, 220)
      }
      this.$forceUpdate()
    },
    prev() { if (this.currentIndex > 0) this.currentIndex-- },
    next() {
      if (!this.canNext) {
        uni.showToast({ title: '请选择一项', icon: 'none' })
        return
      }
      if (this.isLast) this.submit()
      else this.currentIndex++
    },
    async submit() {
      this.status = 'idle'
      try {
        const session = getSprint3Session()
        const questionnaire = {
          schema_version: 'questionnaire_v2.0',
          time_window_days: 7,
          started_at: this.startedAt,
          completed_at: new Date().toISOString(),
          answers: this.questions.map(question => ({
            question_id: question.id,
            type: question.apiType,
            value: this.answers[question.id]
          }))
        }
        const payload = {
          session_id: session.session_id,
          user_id: session.user_id || 'demo_user_001',
          document_id: session.document_id || null,
          document_text: session.document_text || null,
          narrative_text: session.narrative_text || null,
          questionnaire_answers: questionnaire,
          assessment_confirmed: false
        }
        const workflow = await runWorkflow(payload)
        updateSprint3Session({ questionnaire_answers: questionnaire, workflow })
        uni.navigateTo({ url: '/pages/assessment-result/assessment-result' })
      } catch (error) {
        this.status = 'error'
        this.errorMsg = error.message || '提交失败，请检查网络'
      }
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
.header { margin-bottom: 28rpx; }
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
.progress-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8rpx;
}
.page-title {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.03em;
}
.page-counter {
  display: flex;
  align-items: baseline;
  gap: 2rpx;
}
.counter-current {
  font-size: 40rpx;
  color: #4A6B5C;
  font-weight: 700;
  font-family: Georgia, serif;
}
.counter-divider {
  font-size: 28rpx;
  color: #C8D2CB;
  margin: 0 4rpx;
}
.counter-total {
  font-size: 24rpx;
  color: #9C9585;
}
.page-subtitle {
  font-size: 24rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
}

/* 自定义分段进度 */
.custom-progress {
  display: flex;
  gap: 8rpx;
  margin-bottom: 32rpx;
}
.progress-segment {
  flex: 1;
  height: 6rpx;
  border-radius: 3rpx;
  background: #E8E2D5;
  transition: all 0.4s;
}
.progress-segment.done {
  background: #4A6B5C;
}
.progress-segment.current {
  background: linear-gradient(90deg, #4A6B5C 50%, #E8E2D5 50%);
}
.progress-segment.pending {
  background: #E8E2D5;
}

/* 题目卡片 */
.question-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 40rpx 36rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 8rpx 28rpx rgba(74, 107, 92, 0.06);
  margin-bottom: 24rpx;
  animation: cardIn 0.3s ease;
}
@keyframes cardIn {
  from { opacity: 0; transform: translateY(20rpx); }
  to { opacity: 1; transform: translateY(0); }
}
.question-num {
  display: inline-block;
  font-size: 22rpx;
  color: #C8896D;
  background: #F5EBE3;
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  letter-spacing: 0.1em;
  margin-bottom: 20rpx;
  font-weight: 600;
}
.question-text {
  font-size: 32rpx;
  color: #2C2A28;
  font-weight: 600;
  display: block;
  margin-bottom: 36rpx;
  line-height: 1.6;
  letter-spacing: 0.02em;
}

/* Likert 选项 */
.options-row {
  display: flex;
  justify-content: space-between;
  gap: 12rpx;
}
.option-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 4rpx;
  border-radius: 20rpx;
  transition: all 0.2s;
}
.option-item:active {
  background: #EEF1ED;
}
.option-circle {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  border: 2rpx solid #E8E2D5;
  background: #FCFAF6;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.option-item.selected .option-circle {
  border-color: #4A6B5C;
  background: #4A6B5C;
  transform: scale(1.08);
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.25);
}
.option-item.selected .option-num {
  color: #FCFAF6;
}
.option-num {
  font-size: 30rpx;
  font-weight: 700;
  color: #6B6862;
  font-family: Georgia, serif;
}
.option-item.selected .option-label {
  color: #4A6B5C;
  font-weight: 600;
}
.option-label {
  font-size: 22rpx;
  color: #9C9585;
  text-align: center;
  line-height: 1.3;
}

/* 底部按钮 */
.btn-group {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 20rpx;
  padding: 24rpx 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: rgba(247, 243, 235, 0.95);
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border-top: 1rpx solid #E8E2D5;
  box-sizing: border-box;
}
.btn {
  flex: 1;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  transition: all 0.2s;
}
.btn:active { transform: scale(0.98); }
.btn-primary {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.20);
}
.btn-primary .btn-text {
  color: #F7F3EB;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.btn-arrow {
  font-size: 30rpx;
  color: #F7F3EB;
  font-weight: 500;
}
.btn-secondary {
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
}
.btn-secondary .btn-text {
  color: #4A6B5C;
  font-size: 28rpx;
  font-weight: 600;
}
.btn.disabled {
  opacity: 0.4;
}
</style>