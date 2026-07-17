<script>
import { submitAssessment } from '@/common/api.js'

export default {
  data() {
    return {
      emotion: '',
      tone: '',
      // 页面状态：idle（初始） / loading（分析中） / error（出错）
      status: 'idle',
      errorMsg: '',
      currentStep: 1,
      totalSteps: 3,
      steps: [
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
    currentQuestions() {
      return this.steps[this.currentStep - 1].questions
    },
    currentTitle() {
      return this.steps[this.currentStep - 1].title
    },
    progress() {
      return Math.round((this.currentStep / this.totalSteps) * 100)
    },
    canSubmit() {
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

      if (this.currentStep < this.totalSteps) {
        this.currentStep++
      } else {
        this.submitSurvey()
      }
    },
    prevStep() {
      if (this.currentStep > 1) {
        this.currentStep--
      }
    },
    async submitSurvey() {
      this.status = 'loading'

      try {
        // 调用 API 提交问卷
        const assessment = await submitAssessment({
          emotion: this.emotion,
          tone: this.tone,
          answers: this.answers
        })

        // 把评估结果存到本地，供播放页读取
        // 因为 player 是 tabBar 页面，不能通过 URL 传参
        uni.setStorageSync('harmony_latest_assessment', JSON.stringify(assessment))

        this.status = 'success'

        // 跳转到播放页（tabBar 页面用 switchTab）
        uni.switchTab({
          url: '/pages/player/player'
        })
      } catch (err) {
        console.error('提交失败：', err)
        this.status = 'error'
        this.errorMsg = '分析失败，请检查网络后重试'
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
      <text class="progress-text">{{ currentStep }} / {{ totalSteps }} {{ currentTitle }}</text>
    </view>

    <!-- 正常问卷内容 -->
    <view class="question-list" v-if="status === 'idle' || status === 'error'">
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
      <text class="status-title">正在分析您的健康状态...</text>
      <text class="status-desc">AI 正在结合中医五行理论生成调理方案</text>
    </view>

    <!-- Error 状态：出错 -->
    <view class="status-card error-card" v-if="status === 'error'">
      <text class="status-icon">⚠️</text>
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
        :class="{ disabled: currentStep === 1 }"
        @click="prevStep"
      >
        <text class="btn-text">上一步</text>
      </view>
      <view class="btn btn-primary" @click="nextStep">
        <text class="btn-text">{{ currentStep < totalSteps ? '下一步' : '提交评估' }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.container {
  padding: 30rpx;
  padding-bottom: 160rpx;
  min-height: 100vh;
  background: #F8F8F8;
}

/* 页面顶部标题 */
.page-header {
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 40rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
}
.page-subtitle {
  font-size: 24rpx;
  color: #888780;
  margin-top: 8rpx;
  display: block;
}

/* 进度条 */
.progress-bar {
  margin-bottom: 40rpx;
}
.progress-track {
  height: 8rpx;
  background: #E8E8E8;
  border-radius: 4rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #534AB7;
  border-radius: 4rpx;
  transition: width 0.3s;
}
.progress-text {
  font-size: 24rpx;
  color: #888780;
  margin-top: 12rpx;
  display: block;
}

/* 题目卡片 */
.question-item {
  background: #fff;
  border-radius: 24rpx;
  padding: 36rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.question-text {
  font-size: 30rpx;
  color: #2C2C2A;
  font-weight: 500;
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
  border: 4rpx solid #E8E8E8;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.option-item.selected .option-circle {
  border-color: #534AB7;
  background: #534AB7;
}
.option-item.selected .option-num {
  color: #fff;
}
.option-num {
  font-size: 28rpx;
  font-weight: 600;
  color: #888780;
}
.option-item.selected .option-label {
  color: #534AB7;
  font-weight: 500;
}
.option-label {
  font-size: 20rpx;
  color: #888780;
  text-align: center;
}

/* 状态卡片：loading / error */
.status-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 60rpx 40rpx;
  margin-top: 60rpx;
  text-align: center;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.loading-spinner {
  width: 80rpx;
  height: 80rpx;
  border: 6rpx solid #E8E8E8;
  border-top-color: #534AB7;
  border-radius: 50%;
  margin: 0 auto 30rpx;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.status-icon {
  font-size: 64rpx;
  display: block;
  margin-bottom: 16rpx;
}
.status-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
  margin-bottom: 12rpx;
}
.status-desc {
  font-size: 26rpx;
  color: #888780;
  display: block;
  margin-bottom: 30rpx;
}
.retry-btn {
  display: inline-block;
  background: #534AB7;
  padding: 20rpx 60rpx;
  border-radius: 44rpx;
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
  box-shadow: 0 -2rpx 12rpx rgba(0,0,0,0.04);
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
  background: #534AB7;
}
.btn-primary .btn-text {
  color: #fff;
  font-size: 30rpx;
  font-weight: 600;
}
.btn-secondary {
  background: #F1EFE8;
}
.btn-secondary .btn-text {
  color: #5F5E5A;
  font-size: 30rpx;
}
.btn-secondary.disabled {
  opacity: 0.4;
}
</style>
