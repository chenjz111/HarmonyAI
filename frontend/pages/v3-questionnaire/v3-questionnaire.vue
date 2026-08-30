<script>
/**
 * V3 五脏状态问卷页（10 题）
 * 合同依据：frontend-read-model-contract-v3.md §6 QuestionnaireReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2 / §4.3
 *
 * - 题目数据来自 GET /api/v3/questionnaire/schema，前端不内置另一套题目
 * - 无资料模式：必填，全部 10 题完成才能提交（不能跳过）
 * - 有资料模式：整份选填，可跳过；一旦提交必须完整 10 题
 * - V3 普通页面不显示 Q19/Q20（Safety 暂缓，Amendment §6）
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      schema: null,
      required: false, // 无资料模式=true
      current: 0, // 当前题索引
      answers: {}, // { question_id: [option_code, ...] }
      submitting: false,
      submittingAssessment: false,
    }
  },
  computed: {
    question() {
      if (!this.schema || !this.schema.questions) return null
      return this.schema.questions[this.current]
    },
    total() {
      return this.schema ? this.schema.question_count : 0
    },
    answeredCount() {
      return Object.keys(this.answers).filter((k) => this.answers[k] && this.answers[k].length).length
    },
    currentAnswer() {
      return this.question ? (this.answers[this.question.question_id] || []) : []
    },
    canSubmit() {
      return this.total > 0 && this.answeredCount >= this.total
    },
  },
  onLoad() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ""
      try {
        this.schema = await apiV3.getQuestionnaireSchema()
        this.required = !!this.schema.required_for_flow
      } catch (e) {
        this.error = e.message || "问卷加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    // 选项点击：处理"无以上情况"互斥（exclusive_with: ["*"]）
    toggleOption(option) {
      if (!this.question) return
      const qid = this.question.question_id
      const list = (this.answers[qid] || []).slice()
      const idx = list.indexOf(option.option_code)
      if (option.is_none) {
        // 选"无"：清空其他选项
        this.answers[qid] = idx === -1 ? [option.option_code] : []
        return
      }
      if (idx !== -1) {
        list.splice(idx, 1)
      } else {
        // 移除"无"选项；校验 max_selections
        const noneIdx = list.indexOf("none")
        if (noneIdx !== -1) list.splice(noneIdx, 1)
        if (this.question.max_selections && list.length >= this.question.max_selections) {
          uni.showToast({ title: "最多选择 " + this.question.max_selections + " 项", icon: "none" })
          return
        }
        list.push(option.option_code)
      }
      this.answers[qid] = list
    },
    prev() {
      if (this.current > 0) this.current -= 1
    },
    next() {
      if (!this.currentAnswer.length) {
        uni.showToast({ title: "请至少选择一项", icon: "none" })
        return
      }
      if (this.current < this.total - 1) this.current += 1
    },
    async submit() {
      if (!this.canSubmit || this.submitting) return
      this.submitting = true
      try {
        await apiV3.submitQuestionnaire(this.answers)
        await this.goAssessment()
      } catch (e) {
        uni.showToast({ title: e.message || "提交失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    // 有资料模式：跳过整份问卷（部分草稿不作为有效来源）
    async skip() {
      if (this.required || this.submitting) return
      try {
        await this.goAssessment()
      } catch (e) {
        uni.showToast({ title: e.message || "操作失败，请重试", icon: "none" })
      }
    },
    async goAssessment() {
      this.submittingAssessment = true
      try {
        // 触发 Agent1 评估，进入最终确认页
        await apiV3.createAssessment()
        uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
      } catch (e) {
        uni.showToast({ title: e.message || "评估失败，请重试", icon: "none" })
        throw e
      } finally {
        this.submittingAssessment = false
      }
    },
  },
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">{{ required ? "无资料流程 · 第 2 步 · 必填" : "有资料流程 · 第 4 步 · 选填" }}</text>
      <text class="page-title">{{ schema ? schema.title : "五脏状态问卷" }}</text>
      <text class="page-subtitle">请根据最近 7 天的实际感受作答。</text>
    </view>

    <view v-if="loading" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在加载问卷…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <text class="error-text">{{ error }}</text>
      <view class="btn-retry" @click="load"><text class="btn-retry-text">重试</text></view>
    </view>

    <view v-else-if="submittingAssessment" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在生成你的状态评估…</text>
      <text class="loading-sub">请稍候，通常需要几秒钟</text>
    </view>

    <view v-else>
      <!-- 进度 -->
      <view class="progress-row">
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: ((answeredCount / total) * 100) + '%' }"></view>
        </view>
        <text class="progress-text">{{ answeredCount }} / {{ total }}</text>
      </view>

      <!-- 题目卡片 -->
      <view class="q-card" :key="question.question_id">
        <text class="q-index">第 {{ current + 1 }} 题 · 共 {{ total }} 题</text>
        <text class="q-prompt">{{ question.prompt }}</text>
        <view class="q-options">
          <view
            v-for="opt in question.options"
            :key="opt.option_code"
            class="q-option"
            :class="{ 'q-option-active': currentAnswer.indexOf(opt.option_code) !== -1 }"
            @click="toggleOption(opt)"
          >
            <view class="q-radio" :class="{ 'q-radio-active': currentAnswer.indexOf(opt.option_code) !== -1 }">
              <view v-if="currentAnswer.indexOf(opt.option_code) !== -1" class="q-radio-dot"></view>
            </view>
            <text class="q-option-label">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 导航 -->
      <view class="nav-row">
        <view class="nav-btn" :class="{ 'nav-hidden': current === 0 }" @click="prev">
          <text class="nav-btn-text">上一题</text>
        </view>
        <view
          v-if="current < total - 1"
          class="nav-btn nav-primary"
          :class="{ 'nav-disabled': !currentAnswer.length }"
          @click="next"
        >
          <text class="nav-btn-text nav-primary-text">下一题</text>
        </view>
        <view
          v-else
          class="nav-btn nav-primary"
          :class="{ 'nav-disabled': !canSubmit }"
          @click="submit"
        >
          <text class="nav-btn-text nav-primary-text">提交问卷</text>
        </view>
      </view>

      <!-- 有资料模式：整份跳过 -->
      <view v-if="!required" class="skip-row" @click="skip">
        <text class="skip-text">跳过问卷，继续评估</text>
      </view>
      <view v-else class="must-note">
        <text class="must-note-text">无资料流程需要完成全部 10 题后才能继续</text>
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
.page-title { display: block; font-size: 40rpx; font-weight: 600; color: #2f3d35; margin-bottom: 12rpx; }
.page-subtitle { display: block; font-size: 26rpx; color: #7a8078; }
.progress-row { display: flex; align-items: center; gap: 20rpx; margin-bottom: 32rpx; }
.progress-bar {
  flex: 1;
  height: 12rpx;
  background: #e8e2d4;
  border-radius: 6rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #4a6b5c;
  border-radius: 6rpx;
  transition: width 0.3s ease;
}
.progress-text { font-size: 24rpx; color: #9c9585; }
.q-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}
.q-index { display: block; font-size: 22rpx; color: #9c9585; margin-bottom: 16rpx; }
.q-prompt { display: block; font-size: 32rpx; font-weight: 500; color: #2f3d35; line-height: 1.6; margin-bottom: 36rpx; }
.q-options { display: flex; flex-direction: column; gap: 20rpx; }
.q-option {
  display: flex;
  align-items: center;
  background: #f6f3ea;
  border: 2rpx solid transparent;
  border-radius: 16rpx;
  padding: 26rpx 24rpx;
}
.q-option-active { background: #edf1ec; border-color: #4a6b5c; }
.q-radio {
  width: 36rpx;
  height: 36rpx;
  border: 3rpx solid #c9c3b2;
  border-radius: 50%;
  margin-right: 22rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.q-radio-active { border-color: #4a6b5c; }
.q-radio-dot { width: 18rpx; height: 18rpx; background: #4a6b5c; border-radius: 50%; }
.q-option-label { font-size: 28rpx; color: #2f3d35; line-height: 1.5; }
.nav-row { display: flex; gap: 24rpx; margin-top: 40rpx; }
.nav-btn {
  flex: 1;
  border: 2rpx solid #4a6b5c;
  border-radius: 48rpx;
  padding: 24rpx 0;
  display: flex;
  justify-content: center;
}
.nav-hidden { visibility: hidden; }
.nav-primary { background: #4a6b5c; }
.nav-btn-text { color: #4a6b5c; font-size: 30rpx; }
.nav-primary-text { color: #fff; }
.nav-disabled { opacity: 0.5; }
.skip-row { display: flex; justify-content: center; margin-top: 36rpx; padding: 12rpx 0; }
.skip-text { color: #8a9188; font-size: 26rpx; text-decoration: underline; }
.must-note { display: flex; justify-content: center; margin-top: 36rpx; }
.must-note-text { color: #b3ac9c; font-size: 24rpx; }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; }
.loading-ring {
  width: 72rpx; height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { margin-top: 24rpx; font-size: 26rpx; color: #9c9585; }
.loading-sub { margin-top: 12rpx; font-size: 24rpx; color: #b3ac9c; }
.error-wrap { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; }
.error-text { font-size: 28rpx; color: #b0574f; margin-bottom: 32rpx; }
.btn-retry { padding: 20rpx 64rpx; background: #4a6b5c; border-radius: 44rpx; }
.btn-retry-text { color: #fff; font-size: 28rpx; }
</style>
