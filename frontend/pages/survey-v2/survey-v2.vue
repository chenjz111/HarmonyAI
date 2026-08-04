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
import { submitSurveyV2 } from '@/common/api-v2.js'

export default {
  components: { ProgressBar, ImageChoice, ErrorState },
  data() {
    return {
      currentIndex: 0,
      answers: {},
      options: [
        { value: 1, label: '完全没有' },
        { value: 2, label: '偶尔' },
        { value: 3, label: '有时' },
        { value: 4, label: '经常' },
        { value: 5, label: '总是' }
      ],
      questions: [
        {
          id: 'q1',
          type: 'image',
          text: '最近一周，你的整体情绪状态更接近哪一种？',
          columns: 3,
          options: [
            { value: 5, label: '愉悦平和', icon: '☺', color: '#6B8979', bgColor: '#EEF1ED' },
            { value: 3, label: '一般波动', icon: '◐', color: '#C8896D', bgColor: '#F5EBE3' },
            { value: 1, label: '焦虑低落', icon: '☹', color: '#4A6B5C', bgColor: '#E5EAE7' }
          ]
        },
        {
          id: 'q2',
          type: 'image',
          text: '过去一周，你的睡眠质量如何？',
          columns: 5,
          options: [
            { value: 5, label: '很好', icon: '★', color: '#6B8979', bgColor: '#EEF1ED' },
            { value: 4, label: '较好', icon: '☆', color: '#8FA89C', bgColor: '#F0F4F1' },
            { value: 3, label: '一般', icon: '◐', color: '#C8896D', bgColor: '#F5EBE3' },
            { value: 2, label: '较差', icon: '☾', color: '#B8826A', bgColor: '#F0E5DC' },
            { value: 1, label: '很差', icon: '☁', color: '#9C9585', bgColor: '#F0EBE0' }
          ]
        },
        { id: 'q3', type: 'likert', text: '我感到焦虑不安，难以放松' },
        { id: 'q4', type: 'likert', text: '我感到疲惫无力，精力不足' },
        { id: 'q5', type: 'likert', text: '我对事物失去兴趣，提不起精神' },
        {
          id: 'q6',
          type: 'image',
          text: '你目前最明显的身体不适部位是哪里？',
          columns: 5,
          options: [
            { value: 1, label: '头部', icon: '头', color: '#C85A45', bgColor: '#F9EDE7' },
            { value: 2, label: '胸口', icon: '胸', color: '#C8896D', bgColor: '#F5EBE3' },
            { value: 3, label: '腹部', icon: '腹', color: '#D4A574', bgColor: '#F5EBD9' },
            { value: 4, label: '腰部', icon: '腰', color: '#6B8979', bgColor: '#EEF1ED' },
            { value: 5, label: '四肢', icon: '肢', color: '#4A6FA5', bgColor: '#E8EDF3' }
          ]
        },
        { id: 'q7', type: 'likert', text: '我难以入睡，或半夜容易醒来' },
        { id: 'q8', type: 'likert', text: '我容易因为小事发脾气' },
        { id: 'q9', type: 'likert', text: '我感到胸闷气短' },
        { id: 'q10', type: 'likert', text: '我食欲不振或消化不良' },
        { id: 'q11', type: 'likert', text: '我对未来感到悲观' },
        { id: 'q12', type: 'likert', text: '我感到口干口苦' }
      ],
      status: 'idle',
      errorMsg: ''
    }
  },
  computed: {
    currentQuestion() {
      return this.questions[this.currentIndex]
    },
    isLast() {
      return this.currentIndex === this.questions.length - 1
    },
    canNext() {
      return !!this.answers[this.currentQuestion.id]
    },
    answeredCount() {
      return Object.keys(this.answers).length
    }
  },
  methods: {
    select(value) {
      this.answers[this.currentQuestion.id] = value
      this.$forceUpdate()
      // 选中后短暂延迟进入下一题
      if (!this.isLast) {
        setTimeout(() => {
          this.currentIndex++
        }, 280)
      }
    },
    prev() {
      if (this.currentIndex > 0) this.currentIndex--
    },
    next() {
      if (!this.canNext) {
        uni.showToast({ title: '请选择一项', icon: 'none' })
        return
      }
      if (this.isLast) {
        this.submit()
      } else {
        this.currentIndex++
      }
    },
    async submit() {
      this.status = 'idle'
      try {
        const material = uni.getStorageSync('harmony_material') || '{}'
        const narrative = uni.getStorageSync('harmony_narrative') || '{}'
        const payload = {
          session_id: 'sess_' + Date.now(),
          answers: this.answers,
          material: JSON.parse(material),
          narrative: JSON.parse(narrative)
        }
        const res = await submitSurveyV2(payload)
        uni.setStorageSync('harmony_assessment_v2', JSON.stringify(res))
        uni.setStorageSync('harmony_session_id_v2', res.session_id)
        uni.navigateTo({ url: '/pages/result/result' })
      } catch (e) {
        this.status = 'error'
        this.errorMsg = e.message || '提交失败，请检查网络'
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