<script>
/**
 * V3 五脏状态问卷页（10 题：q01-q05 频率题 + q06-q10 多选题）
 * 合同依据：frontend-read-model-contract-v3.md §6 QuestionnaireReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2 / §4.3
 *          knowledge/v3/questionnaire-v3.0.json（权威清单，前端不内置另一套题目）
 *
 * - 题目数据来自权威清单模块（与后端同源），频率题渲染 FREQUENCY_OPTIONS
 * - 无资料模式：必填，全部 10 题完成才能提交（不能跳过）
 * - 有资料模式：整份选填，可跳过；一旦提交必须完整 10 题
 * - real 模式下提交/评估属于 Agent1 能力（PR #91 未合并）：
 *   捕获 AGENT_PENDING 后进入明确等待状态，不伪造结果、不静默失败
 */
import { apiV3, FREQUENCY_OPTIONS } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      schema: null,
      required: false, // 无资料模式=true
      current: 0, // 当前题索引
      answers: {}, // { question_id: number | [option_code, ...] }
      submitting: false,
      submittingAssessment: false,
      agentPending: false, // real 模式：等待后端 Agent1 接入（PR #91）
      simulated: false, // hybrid/mock：演示数据标识
      frequencyOptions: FREQUENCY_OPTIONS,
    }
  },
  computed: {
    question() {
      if (!this.schema || !this.schema.questions) return null
      return this.schema.questions[this.current]
    },
    isFrequency() {
      return !!this.question && this.question.answer_type === "frequency_0_4"
    },
    total() {
      return this.schema ? this.schema.question_count : 0
    },
    answeredCount() {
      // 频率题答案是 0..4 整数（0 是有效答案，不能用 truthy 判断）
      if (!this.schema || !this.schema.questions) return 0
      return this.schema.questions.filter((q) => {
        const a = this.answers[q.question_id]
        if (q.answer_type === "frequency_0_4") {
          return typeof a === "number"
        }
        return !!(a && a.length)
      }).length
    },
    currentAnswer() {
      if (!this.question) return []
      return this.answers[this.question.question_id] || []
    },
    currentFrequencyValue() {
      if (!this.question) return null
      const a = this.answers[this.question.question_id]
      return typeof a === "number" ? a : null
    },
    hasCurrentAnswer() {
      if (!this.question) return false
      if (this.question.answer_type === "frequency_0_4") {
        return typeof this.currentFrequencyValue === "number"
      }
      return this.currentAnswer.length > 0
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
        this.simulated = !!apiV3.AGENT_SIMULATED
      } catch (e) {
        this.error = e.message || "问卷加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    // 频率题：单选 0..4（再点一次同选项可取消）
    selectFrequency(option) {
      if (!this.question) return
      const qid = this.question.question_id
      const cur = this.answers[qid]
      this.answers[qid] = typeof cur === "number" && cur === option.value ? null : option.value
    },
    // 多选题：处理"都很少出现"互斥（is_none + exclusive_with）
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
        const noneOpt = (this.question.options || []).find((o) => o.is_none)
        const noneIdx = noneOpt ? list.indexOf(noneOpt.option_code) : -1
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
      if (!this.hasCurrentAnswer) {
        uni.showToast({ title: this.isFrequency ? "请选择一个频率" : "请至少选择一项", icon: "none" })
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
        this.handleAgentPending(e) || uni.showToast({ title: e.message || "提交失败，请重试", icon: "none" })
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
        if (e.agentPending) {
          // real 模式：Agent1 未接入（PR #91），进入明确等待状态，不伪造评估
          this.agentPending = true
          return
        }
        uni.showToast({ title: e.message || "评估失败，请重试", icon: "none" })
        throw e
      } finally {
        this.submittingAssessment = false
      }
    },
    // submit 阶段的 AGENT_PENDING：同样进入等待状态
    handleAgentPending(e) {
      if (e && e.agentPending) {
        this.agentPending = true
        return true
      }
      return false
    },
  },
}
</script>

<template>
  <view class="container v3-visual-page questionnaire-page">
    <view class="flow-shell">
    <view class="header">
      <text class="step-tag">{{ required ? "无资料流程 · 第 2 步 · 必填" : "有资料流程 · 第 4 步 · 选填" }}</text>
      <text class="page-title">近期状态问卷</text>
      <text class="page-subtitle question-support">没有标准答案，请按最近 7 天最接近的实际感受选择。</text>
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

    <!-- real 模式：评估服务未接入，明确等待状态，不伪造评估（P1-2：稳定用户文案） -->
    <view v-else-if="agentPending" class="pending-card">
      <view class="pending-icon"><text class="pending-icon-text">…</text></view>
      <text class="pending-title">正在等待评估服务接入</text>
      <text class="pending-desc">评估服务正在升级维护中，暂时无法提交。你的作答已保留在本页，不会丢失，服务恢复后可直接提交。</text>
      <view class="btn-retry" @click="agentPending = false"><text class="btn-retry-text">返回问卷</text></view>
    </view>

    <view v-else>
      <!-- hybrid 演示标识 -->
      <view v-if="simulated" class="demo-banner">
        <text class="demo-banner-text">演示模式：评估与音乐部分为模拟数据</text>
      </view>

      <!-- 进度 -->
      <view class="progress-row">
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: ((answeredCount / total) * 100) + '%' }"></view>
        </view>
        <text class="progress-text">{{ answeredCount }} / {{ total }}</text>
      </view>

      <!-- 题目卡片 -->
      <view class="q-card question-shell" :key="question.question_id">
        <text class="q-index">第 {{ current + 1 }} 题 · 共 {{ total }} 题</text>
        <text class="q-prompt">{{ question.prompt }}</text>

        <!-- 频率题（q01-q05）：单选 0..4 -->
        <view v-if="isFrequency" class="q-options">
          <view
            v-for="opt in frequencyOptions"
            :key="'f' + opt.value"
            class="q-option"
            :class="{ 'q-option-active': currentFrequencyValue === opt.value }"
            @click="selectFrequency(opt)"
          >
            <view class="q-radio" :class="{ 'q-radio-active': currentFrequencyValue === opt.value }">
              <view v-if="currentFrequencyValue === opt.value" class="q-radio-dot"></view>
            </view>
            <text class="q-option-label">{{ opt.label }}</text>
          </view>
        </view>

        <!-- 多选题（q06-q10） -->
        <view v-else class="q-options">
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
      <view class="nav-row bottom-navigation">
        <view class="nav-btn" :class="{ 'nav-hidden': current === 0 }" @click="prev">
          <text class="nav-btn-text">上一题</text>
        </view>
        <view
          v-if="current < total - 1"
          class="nav-btn nav-primary"
          :class="{ 'nav-disabled': !hasCurrentAnswer }"
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
  </view>
</template>

<style lang="scss">
@use "../../styles/v3-visual-tokens.scss" as v3;
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
.demo-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.demo-banner-text {
  font-size: 22rpx;
  color: #8a6d3b;
  background: #f5eddc;
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
}
.pending-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 64rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pending-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: #eef0ea;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.pending-icon-text { font-size: 48rpx; color: #4a6b5c; font-weight: 600; }
.pending-title { font-size: 34rpx; font-weight: 600; color: #2f3d35; margin-bottom: 20rpx; }
.pending-desc {
  font-size: 26rpx;
  color: #7a8078;
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
.container { @include v3.v3-page; }
.flow-shell { @include v3.v3-flow-shell; }
.header { margin: 0 0 v3.$v3-space-6; }
.step-tag { margin-bottom: v3.$v3-space-3; padding: 7px 12px; border-radius: v3.$v3-radius-pill; color: v3.$v3-primary-dark; background: rgba(78, 116, 104, .1); font-size: 12px; font-weight: 650; }
.page-title { margin-bottom: v3.$v3-space-3; color: v3.$v3-text-primary; font-size: clamp(28px, 4.5vw, 36px); font-weight: 680; letter-spacing: -.025em; line-height: 1.25; }
.question-support { color: v3.$v3-text-secondary; font-size: 15px; line-height: 1.7; }
.progress-row { gap: v3.$v3-space-4; margin-bottom: v3.$v3-space-5; padding: v3.$v3-space-4 v3.$v3-space-5; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-md; background: rgba(255, 255, 255, .72); }
.progress-bar { height: 6px; background: v3.$v3-border; }
.progress-fill { background: linear-gradient(90deg, v3.$v3-primary, #71958a); }
.progress-text { min-width: 46px; color: v3.$v3-text-secondary; font-size: 13px; font-variant-numeric: tabular-nums; }
.question-shell { min-height: 410px; padding: v3.$v3-space-8; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-lg; background: v3.$v3-surface; box-shadow: v3.$v3-shadow-soft; }
.q-index { margin-bottom: v3.$v3-space-4; color: v3.$v3-accent; font-size: 12px; font-weight: 700; letter-spacing: .06em; }
.q-prompt { margin-bottom: v3.$v3-space-6; color: v3.$v3-text-primary; font-size: clamp(20px, 3.4vw, 25px); font-weight: 650; line-height: 1.55; }
.q-options { gap: v3.$v3-space-3; }
.q-option { min-height: 56px; padding: v3.$v3-space-4 v3.$v3-space-5; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-md; background: v3.$v3-surface; @include v3.v3-focusable; }
.q-option-active { border-color: v3.$v3-primary; background: rgba(78, 116, 104, .09); box-shadow: 0 0 0 1px rgba(78, 116, 104, .12); }
.q-radio { width: 21px; height: 21px; border: 1.5px solid v3.$v3-border; background: v3.$v3-surface; }
.q-radio-active { border-color: v3.$v3-primary; background: v3.$v3-primary; }
.q-radio-dot { width: 7px; height: 7px; background: v3.$v3-surface; }
.q-option-label { color: v3.$v3-text-primary; font-size: 15px; line-height: 1.55; }
.bottom-navigation { position: sticky; bottom: max(v3.$v3-space-4, env(safe-area-inset-bottom)); z-index: 5; gap: v3.$v3-space-3; margin-top: v3.$v3-space-5; padding: v3.$v3-space-3; border: 1px solid rgba(227, 231, 226, .92); border-radius: v3.$v3-radius-lg; background: rgba(255, 255, 255, .94); box-shadow: v3.$v3-shadow-raised; backdrop-filter: blur(14px); }
.nav-btn { min-height: 50px; padding: 0 v3.$v3-space-5; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-pill; background: v3.$v3-surface; }
.nav-primary { border-color: v3.$v3-primary; background: v3.$v3-primary; box-shadow: 0 8px 20px rgba(78, 116, 104, .18); }
.nav-btn-text { color: v3.$v3-text-secondary; font-size: 15px; font-weight: 650; }
.nav-primary-text { color: v3.$v3-surface; }
.nav-disabled { opacity: .42; }
.skip-row, .must-note { margin-top: v3.$v3-space-4; padding: v3.$v3-space-3 v3.$v3-space-4; }
.skip-text { color: v3.$v3-text-secondary; font-size: 13px; }
.must-note-text { color: v3.$v3-text-muted; font-size: 12px; }
.loading-wrap, .error-wrap, .pending-card { border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-lg; background: v3.$v3-surface; box-shadow: v3.$v3-shadow-soft; }
.loading-ring { border-color: v3.$v3-border; border-top-color: v3.$v3-primary; }
.error-text { color: v3.$v3-danger; }
.btn-retry { background: v3.$v3-primary; }
@media (min-width: 768px) { .container { padding-top: 56px; padding-bottom: 64px; } .question-shell { padding: 36px 40px; } }
@media (max-width: 420px) { .question-shell { min-height: 380px; padding: v3.$v3-space-6 v3.$v3-space-5; } .bottom-navigation { bottom: max(v3.$v3-space-3, env(safe-area-inset-bottom)); } .nav-btn { min-height: 48px; padding: 0 v3.$v3-space-4; } }
/* V1.1 restrained tuning */
.questionnaire-page { padding-bottom: calc(132px + env(safe-area-inset-bottom)); }
.page-title { font-weight: 620; }
.q-prompt { font-weight: 600; }
.q-option { min-height: 50px; padding: 14px v3.$v3-space-5; }
.q-option-active { border-color: v3.$v3-primary; background: rgba(78, 116, 104, .04); box-shadow: 0 0 0 1px rgba(78, 116, 104, .08); }
</style>
