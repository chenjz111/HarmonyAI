<script>
import { submitAssessment, submitDiagnosis } from '@/common/api.js'

export default {
  data() {
    return {
      emotion: '',
      tone: '',
      // 页面状态：idle（初始） / loading（分析中） / error（出错）
      status: 'idle',
      errorMsg: '',
      currentStep: 0,
      totalSteps: 4,
      narrativeText: '',
      steps: [
        {
          title: '最近发生了什么？',
          isNarrative: true
        },
        {
          title: '情绪状态',
          questions: [
            '我经常感到焦虑不安',
            '我容易因为小事发脾气',
            '我感到情绪低落',
            '我对事物失去兴趣',
            '我感到烦躁无法平静',
            '我容易紧张出汗',
            '我感到孤独无助',
            '我难以控制自己的情绪',
            '我经常感到恐惧',
            '我对未来感到悲观',
            '我容易冲动做事',
            '我感到精神疲惫'
          ]
        },
        {
          title: '睡眠质量',
          questions: [
            '我难以入睡',
            '我半夜容易醒来',
            '我早上醒得太早',
            '我觉得睡眠不够深',
            '我做很多梦',
            '我醒来后仍感到疲倦',
            '我白天容易犯困',
            '我需要很长时间才能入睡'
          ]
        },
        {
          title: '身体状况',
          questions: [
            '我经常头痛',
            '我食欲不振',
            '我消化不良',
            '我经常便秘或腹泻',
            '我感到胸闷气短',
            '我腰膝酸软',
            '我手脚冰凉',
            '我容易出汗',
            '我口干口苦',
            '我视力模糊或眼睛干涩'
          ]
        }
      ],
      // 答案存储：所有题目答案，1-5分
      answers: {},
      // Likert 量表选项
      options: [
        { value: 1, label: '完全不像我' },
        { value: 2, label: '不太像我' },
        { value: 3, label: '一般' },
        { value: 4, label: '有点像我' },
        { value: 5, label: '非常像我' }
      ]
    }
  },
  onLoad(options) {
    this.emotion = options.emotion || ''
    this.tone = options.tone || ''
  },
  computed: {
    isNarrativeStep() {
      return this.steps[this.currentStep] && this.steps[this.currentStep].isNarrative
    },
    currentQuestions() {
      const step = this.steps[this.currentStep]
      return step && step.questions ? step.questions : []
    },
    currentTitle() {
      return this.steps[this.currentStep] ? this.steps[this.currentStep].title : ''
    },
    progress() {
      return Math.round(((this.currentStep) / (this.totalSteps - 1)) * 100)
    },
    canSubmit() {
      if (this.isNarrativeStep) return true
      const currentQs = this.currentQuestions
      for (let i = 0; i < currentQs.length; i++) {
        const key = `step${this.currentStep}_q${i}`
        if (!this.answers[key]) return false
      }
      return true
    }
  },
  methods: {
    selectAnswer(questionIndex, value) {
      const key = `step${this.currentStep}_q${questionIndex}`
      this.answers[key] = value
    },
    getSelected(questionIndex) {
      const key = `step${this.currentStep}_q${questionIndex}`
      return this.answers[key] || 0
    },
    nextStep() {
      if (!this.canSubmit) {
        uni.showToast({
          title: '请完成所有题目',
          icon: 'none'
        })
        return
      }

      if (this.currentStep < this.totalSteps - 1) {
        this.currentStep++
      } else {
        this.submitSurvey()
      }
    },
    prevStep() {
      if (this.currentStep > 0) {
        this.currentStep--
      }
    },
    async submitSurvey() {
      this.status = 'loading'

      try {
        // === Agent 1: 评估 ===
        // 把问卷答案组装成 questionnaire 格式
        const questionnaire = {
          emotion: this.emotion,
          tone: this.tone,
          answer_count: Object.keys(this.answers).length,
          total_questions: 30,
          answers: this.answers
        }
        // Attach narrative_text if user entered anything
        if (this.narrativeText && this.narrativeText.trim()) {
          questionnaire.narrative_text = this.narrativeText.trim()
        }

        const assessmentEnvelope = await submitAssessment(questionnaire)
        const sessionId = assessmentEnvelope.session_id

        // === Agent 2: 辨证 ===
        const diagnosisEnvelope = await submitDiagnosis(sessionId, assessmentEnvelope)

        // 把两个 envelope 存到本地，供播放页读取
        uni.setStorageSync('harmony_assessment', JSON.stringify(assessmentEnvelope))
        uni.setStorageSync('harmony_diagnosis', JSON.stringify(diagnosisEnvelope))

        this.status = 'success'

        // 跳转到播放页（tabBar 页面用 switchTab）
        uni.switchTab({
          url: '/pages/player/player'
        })
      } catch (err) {
        console.error('提交失败：', err)
        this.status = 'error'
        this.errorMsg = err.message || '分析失败，请检查网络后重试'
        uni.showToast({
          title: '分析失败，请重试',
          icon: 'none'
        })
      }
    },
    retry() {
      this.status = 'idle'
      this.errorMsg = ''
      this.submitSurvey()
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- 顶部标题区 -->
    <view class="page-header">
      <text class="page-title">健康评估</text>
      <text class="page-subtitle">请根据近一周的真实感受作答</text>
    </view>

    <!-- 进度条 -->
    <view class="progress-bar" v-if="status !== 'loading'">
      <view class="progress-track">
        <view class="progress-fill" :style="{ width: progress + '%' }"></view>
      </view>
      <text class="progress-text">{{ currentStep + 1 }} / {{ totalSteps }} {{ currentTitle }}</text>
    </view>

    <!-- 叙事输入（第一步，可选） -->
    <view class="narrative-card" v-if="isNarrativeStep && (status === 'idle' || status === 'error')">
      <text class="narrative-title">最近发生了什么？</text>
      <text class="narrative-hint">描述最近几天经历的事情、身体状态和感受。越详细，AI 越能理解你。AI 不会根据这段文字直接诊断，只是辅助理解你的状态。</text>
      <text class="narrative-privacy">请勿填写姓名、电话、身份证等个人敏感信息</text>
      <textarea
        class="narrative-area"
        v-model="narrativeText"
        placeholder="比如：这两周工作压力很大，老板催项目催得紧，昨晚又失眠了，今天胸口闷闷的..."
        :maxlength="500"
        auto-height
      ></textarea>
      <text class="narrative-count">{{ narrativeText.length }}/500</text>
    </view>

    <!-- 正常问卷内容 -->
    <view class="question-list" v-if="!isNarrativeStep && (status === 'idle' || status === 'error')">
      <view
        v-for="(question, index) in currentQuestions"
        :key="index"
        class="question-item"
      >
        <text class="question-text">{{ index + 1 }}. {{ question }}</text>
        <view class="options-row">
          <view
            v-for="opt in options"
            :key="opt.value"
            class="option-item"
            :class="{ selected: getSelected(index) === opt.value }"
            @click="selectAnswer(index, opt.value)"
          >
            <view class="option-circle">
              <text class="option-num">{{ opt.value }}</text>
            </view>
            <text class="option-label">{{ opt.label }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Loading 状态：分析中 -->
    <view class="status-card loading-card" v-if="status === 'loading'">
      <view class="loading-spinner"></view>
      <text class="status-title">正在评估与辨证...</text>
      <text class="status-desc">AI 正在结合中医五行理论进行健康评估与辨证分析</text>
    </view>

    <!-- Error 状态：出错 -->
    <view class="status-card error-card" v-if="status === 'error'">
      <text class="status-icon-circle error"><text class="status-icon-text">!</text></text>
      <text class="status-title">分析失败</text>
      <text class="status-desc">{{ errorMsg }}</text>
      <view class="retry-btn" @click="retry">
        <text class="retry-btn-text">重新分析</text>
      </view>
    </view>

    <!-- 底部按钮 -->
    <view class="btn-group" v-if="status === 'idle' || status === 'error'">
      <view
        class="btn btn-secondary"
        :class="{ disabled: currentStep === 0 }"
        @click="prevStep"
      >
        <text class="btn-text">上一步</text>
      </view>
      <view class="btn btn-primary" @click="nextStep">
        <text class="btn-text">{{ isNarrativeStep ? '开始问卷' : (currentStep < totalSteps - 1 ? '下一步' : '提交评估') }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.container {
  padding: 30rpx;
  padding-bottom: 160rpx;
  min-height: 100vh;
  background: #F5F6FA;
}

/* 页面顶部标题 */
.page-header {
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 40rpx;
  font-weight: 700;
  color: #1A1A2E;
  display: block;
}
.page-subtitle {
  font-size: 24rpx;
  color: #9E9EB8;
  margin-top: 8rpx;
  display: block;
}

/* 进度条 */
.progress-bar {
  margin-bottom: 40rpx;
}
.progress-track {
  height: 8rpx;
  background: #E8E8F0;
  border-radius: 4rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6C63FF, #8B80FF);
  border-radius: 4rpx;
  transition: width 0.3s;
}
.progress-text {
  font-size: 24rpx;
  color: #9E9EB8;
  margin-top: 12rpx;
  display: block;
}

/* 叙事输入卡片 */
.narrative-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 36rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.06);
  border-left: 8rpx solid #6C63FF;
}
.narrative-title {
  font-size: 32rpx;
  color: #1A1A2E;
  font-weight: 700;
  display: block;
  margin-bottom: 12rpx;
}
.narrative-hint {
  font-size: 24rpx;
  color: #9E9EB8;
  display: block;
  margin-bottom: 10rpx;
  line-height: 1.6;
}
.narrative-privacy {
  font-size: 22rpx;
  color: #F26C5C;
  display: block;
  margin-bottom: 20rpx;
}
.narrative-area {
  width: 100%;
  min-height: 240rpx;
  background: #F5F6FA;
  border-radius: 16rpx;
  padding: 24rpx;
  font-size: 28rpx;
  color: #1A1A2E;
  box-sizing: border-box;
}
.narrative-count {
  text-align: right;
  font-size: 22rpx;
  color: #BFBFCF;
  margin-top: 12rpx;
  display: block;
}

/* 题目卡片 */
.question-item {
  background: #fff;
  border-radius: 24rpx;
  padding: 36rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.06);
}
.question-text {
  font-size: 30rpx;
  color: #1A1A2E;
  font-weight: 600;
  display: block;
  margin-bottom: 30rpx;
  line-height: 1.5;
}

/* 选项 */
.options-row {
  display: flex;
  justify-content: space-between;
  gap: 10rpx;
}
.option-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
}
.option-circle {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  border: 4rpx solid #E8E8F0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.option-item.selected .option-circle {
  border-color: #6C63FF;
  background: #6C63FF;
  box-shadow: 0 4rpx 16rpx rgba(108,99,255,0.3);
}
.option-item.selected .option-num {
  color: #fff;
}
.option-num {
  font-size: 28rpx;
  font-weight: 600;
  color: #9E9EB8;
}
.option-item.selected .option-label {
  color: #6C63FF;
  font-weight: 500;
}
.option-label {
  font-size: 20rpx;
  color: #9E9EB8;
  text-align: center;
}

/* 状态卡片：loading / error */
.status-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 60rpx 40rpx;
  margin-top: 60rpx;
  text-align: center;
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.06);
}
.loading-spinner {
  width: 80rpx;
  height: 80rpx;
  border: 6rpx solid #E8E8F0;
  border-top-color: #6C63FF;
  border-radius: 50%;
  margin: 0 auto 30rpx;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* CSS 图标替代 emoji */
.status-icon-circle {
  width: 100rpx;
  height: 100rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16rpx;
}
.status-icon-circle.error {
  background: #FFF0F0;
}
.status-icon-text {
  font-size: 56rpx;
  font-weight: 700;
}
.status-icon-circle.error .status-icon-text {
  color: #F26C5C;
}

.status-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #1A1A2E;
  display: block;
  margin-bottom: 12rpx;
}
.status-desc {
  font-size: 26rpx;
  color: #9E9EB8;
  display: block;
  margin-bottom: 30rpx;
}
.retry-btn {
  display: inline-block;
  background: #6C63FF;
  padding: 20rpx 60rpx;
  border-radius: 44rpx;
  box-shadow: 0 4rpx 16rpx rgba(108,99,255,0.3);
}
.retry-btn-text {
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
}

/* 底部按钮 */
.btn-group {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 20rpx;
  padding: 20rpx 30rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -4rpx 20rpx rgba(0,0,0,0.06);
}
.btn {
  flex: 1;
  height: 88rpx;
  border-radius: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-primary {
  background: #6C63FF;
  box-shadow: 0 4rpx 16rpx rgba(108,99,255,0.3);
}
.btn-primary .btn-text {
  color: #fff;
  font-size: 30rpx;
  font-weight: 600;
}
.btn-secondary {
  background: #F0F0FF;
}
.btn-secondary .btn-text {
  color: #6C63FF;
  font-size: 30rpx;
  font-weight: 500;
}
.btn-secondary.disabled {
  opacity: 0.4;
}
</style>
