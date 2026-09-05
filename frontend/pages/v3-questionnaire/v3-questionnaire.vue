<script>
/**
 * V3.1 五脏状态问卷页（Issue #100：10 题分 5 页，每页 2 题）
 * 合同依据：frontend-read-model-contract-v3.md §6 QuestionnaireReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2 / §4.3
 *          knowledge/v3/questionnaire-v3.0.json（权威清单，前端不内置另一套题目）
 *
 * - 题目数据来自权威清单模块（与后端同源），频率题渲染 FREQUENCY_OPTIONS
 * - 展示分页：PAGE_SIZE = 2，共 5 步（进度以页为单位 1/5 ~ 5/5）；提交时仍一次性提交全部答案
 * - 无资料模式：必填，全部 10 题完成才能提交（不能跳过）
 * - 有资料模式：整份选填，可跳过；一旦进入作答，本页 2 题都完成后才能进入下一页
 * - real 模式下提交/评估依赖后端综合评估能力（尚未交付）：
 *   捕获 AGENT_PENDING 后进入明确等待状态，不伪造结果、不静默失败
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3, FREQUENCY_OPTIONS } from "../../common/api-v3.js"
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

const PAGE_SIZE = 2 // V3.1：每页展示 2 题

export default {
  components: { HanSideNav },
  data() {
    return {
      loading: true,
      error: "",
      schema: null,
      required: false, // 无资料模式=true
      current: 0, // 当前页索引（每页 PAGE_SIZE 题）
      answers: {}, // { question_id: number | [option_code, ...] }
      submitting: false,
      submittingAssessment: false,
      agentPending: false, // real 模式：等待后端综合评估能力接入
      simulated: false, // hybrid/mock：演示数据标识
      frequencyOptions: FREQUENCY_OPTIONS,
    }
  },
  computed: {
    questionList() {
      if (!this.schema || !this.schema.questions) return []
      // 权威清单按 position 排列（q01-q10）
      return this.schema.questions
    },
    totalSteps() {
      const n = this.questionList.length
      return n ? Math.ceil(n / PAGE_SIZE) : 0
    },
    total() {
      return this.schema ? this.schema.question_count : 0
    },
    // 当前页题目（最多 PAGE_SIZE 题）
    pageQuestions() {
      const start = this.current * PAGE_SIZE
      return this.questionList.slice(start, start + PAGE_SIZE)
    },
    pageStartIndex() {
      return this.current * PAGE_SIZE
    },
    answeredCount() {
      // 频率题答案是 0..4 整数（0 是有效答案，不能用 truthy 判断）
      return this.questionList.filter((q) => this.hasAnswer(q)).length
    },
    // 当前页 2 题是否都已作答
    pageAnswered() {
      return this.pageQuestions.every((q) => this.hasAnswer(q))
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
        // 必填性必须读取当前权威 Session —— schema.required_for_flow 是历史
        // 冗余字段，不能作为唯一来源；防止过期的本地缓存 / 上一个会话的选项
        // 误判当前 10 题的必填性（强制读取 session.input_mode）
        const [schema, session] = await Promise.all([
          apiV3.getQuestionnaireSchema(),
          apiV3.getSession(),
        ])
        this.schema = schema
        this.required = !!session && session.input_mode !== "with_document"
        this.simulated = !!apiV3.AGENT_SIMULATED
        this.current = 0
        this.answers = {}
      } catch (e) {
        this.error = e.message || "问卷加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    isFrequency(q) {
      return !!q && q.answer_type === "frequency_0_4"
    },
    hasAnswer(q) {
      if (!q) return false
      if (this.isFrequency(q)) {
        return typeof this.answers[q.question_id] === "number"
      }
      const a = this.answers[q.question_id]
      return !!(a && a.length)
    },
    currentAnswer(q) {
      return this.answers[q.question_id] || []
    },
    currentFrequencyValue(q) {
      const a = this.answers[q.question_id]
      return typeof a === "number" ? a : null
    },
    // 频率题：单选 0..4（再点一次同选项可取消）
    selectFrequency(q, option) {
      const qid = q.question_id
      const cur = this.answers[qid]
      this.answers[qid] = typeof cur === "number" && cur === option.value ? null : option.value
    },
    // 多选题：处理"都很少出现"互斥（is_none + exclusive_with）
    toggleOption(q, option) {
      const qid = q.question_id
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
        const noneOpt = (q.options || []).find((o) => o.is_none)
        const noneIdx = noneOpt ? list.indexOf(noneOpt.option_code) : -1
        if (noneIdx !== -1) list.splice(noneIdx, 1)
        if (q.max_selections && list.length >= q.max_selections) {
          uni.showToast({ title: "最多选择 " + q.max_selections + " 项", icon: "none" })
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
      if (!this.pageAnswered) {
        const undone = this.pageQuestions.filter((q) => !this.hasAnswer(q))
        uni.showToast({
          title: undone.length + " 道题还未作答，请完成后继续",
          icon: "none",
        })
        return
      }
      if (this.current < this.totalSteps - 1) this.current += 1
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
    // V3.1 复审修订：有资料用户**跳过**问卷时，直接进入状态总结确认
    // （v3-confirm）—— 不显示疗愈诉求页（v3-goal）。意图与行为一致：
    // "整份选填、不需引导再做选择"的用户无需额外的偏好页。
    async skip() {
      if (this.required || this.submitting) return
      try {
        // 直接尝试推进到"完成近期状态总结"；评估依赖后端能力时如实报错。
        await apiV3.createAssessment()
        uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
      } catch (e) {
        if (e && e.agentPending) {
          // 综合评估能力未接入：保留问卷的等待卡
          this.agentPending = true
          return
        }
        uni.showToast({ title: e.message || "操作失败，请重试", icon: "none" })
      }
    },
    // V3.1：完成 10 题走"提交→评估→选填疗愈诉求"路径
    async goAssessment() {
      this.submittingAssessment = true
      try {
        // 提交后先入疗愈诉求（选填），再到最终确认（完成近期状态总结）
        await apiV3.createAssessment()
        uni.redirectTo({ url: "/pages/v3-goal/v3-goal" })
      } catch (e) {
        if (e.agentPending) {
          // real 模式：综合评估能力未接入，进入明确等待状态，不伪造评估
          this.agentPending = true
          return
        }
        uni.showToast({ title: e.message || "评估失败，请重试", icon: "none" })
        throw e
      } finally {
        this.submittingAssessment = false
      }
    },
    // V3.1 复审修订：有资料用户**跳过**问卷，不再经过疗愈诉求（Goal）页，
    // 直接进入"完成近期状态总结"（v3-confirm）。无资料用户这条分支永远走不到
    // （required 守卫阻断 + skip-row 仅在 !required 时渲染）。
    skipToFinalConfirm() {
      if (this.required || this.submitting) return
      uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
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
  <view class="page han-page side-nav-page">
    <han-side-nav current="question" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">问</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">{{ required ? "无资料流程 · 第 2 步 · 必填" : "有资料流程 · 第 4 步 · 选填" }}</text>
            <text class="page-title han-title-brush revealed">{{ schema ? schema.title : "五脏状态问卷" }}</text>
          </view>
        </view>
        <text class="page-subtitle">请根据最近 7 天的实际感受作答，每页 2 题。</text>
      </view>

      <view v-if="loading" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在加载问卷…</text>
      </view>

      <view v-else-if="error" class="han-card error-card ink-fade-in">
        <view class="error-seal">
          <text class="error-seal-text">静</text>
        </view>
        <text class="error-title">暂时无法加载</text>
        <text class="error-text">{{ error }}</text>
        <view class="han-btn han-btn-primary btn-retry" @click="load">
          <text class="btn-retry-text">重试</text>
        </view>
      </view>

      <view v-else-if="submittingAssessment" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在生成你的状态评估…</text>
        <text class="loading-sub">请稍候，通常需要几秒钟</text>
      </view>

      <!-- real 模式：评估服务未接入，明确等待状态，不伪造评估（稳定用户文案） -->
      <view v-else-if="agentPending" class="han-card pending-card ink-fade-in">
        <view class="pending-seal">
          <text class="pending-seal-text">候</text>
        </view>
        <text class="pending-title">正在等待评估服务接入</text>
        <text class="pending-desc">评估服务正在升级维护中，暂时无法提交。你的作答已保留在本页，不会丢失，服务恢复后可直接提交。</text>
        <view class="han-btn han-btn-ghost btn-back" @click="agentPending = false">
          <text class="btn-back-text">返回问卷</text>
        </view>
      </view>

      <view v-else-if="totalSteps > 0">
        <!-- hybrid 演示标识 -->
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：评估与音乐部分为模拟数据</text>
        </view>

        <!-- 进度（V3.1：以页为单位 1/5 ~ 5/5） -->
        <view class="progress-row">
          <view class="progress-bar">
            <view
              class="progress-fill"
              :style="{ width: (((current + (pageAnswered ? 1 : 0)) / totalSteps) * 100) + '%' }"
            ></view>
          </view>
          <text class="progress-text">第 {{ current + 1 }} / {{ totalSteps }} 页</text>
        </view>

        <!-- 当前页 2 道题 -->
        <view class="page-card">
          <view
            v-for="(q, i) in pageQuestions"
            :key="q.question_id"
            class="han-card q-card ink-fade-up"
          >
            <view class="q-card-head">
              <text class="q-index">第 {{ pageStartIndex + i + 1 }} 题 · 共 {{ total }} 题</text>
              <text v-if="required" class="q-required">必答</text>
            </view>
            <text class="q-prompt">{{ q.prompt }}</text>

            <!-- 频率题（q01-q05）：单选 0..4 -->
            <view v-if="isFrequency(q)" class="q-options">
              <view
                v-for="opt in frequencyOptions"
                :key="'f' + q.question_id + opt.value"
                class="q-option"
                :class="{ 'q-option-active': currentFrequencyValue(q) === opt.value }"
                @click="selectFrequency(q, opt)"
              >
                <view class="q-radio" :class="{ 'q-radio-active': currentFrequencyValue(q) === opt.value }">
                  <view v-if="currentFrequencyValue(q) === opt.value" class="q-radio-dot"></view>
                </view>
                <text class="q-option-label">{{ opt.label }}</text>
              </view>
            </view>

            <!-- 多选题（q06-q10） -->
            <view v-else class="q-options">
              <view
                v-for="opt in q.options"
                :key="opt.option_code"
                class="q-option"
                :class="{ 'q-option-active': currentAnswer(q).indexOf(opt.option_code) !== -1 }"
                @click="toggleOption(q, opt)"
              >
                <view
                  class="q-radio"
                  :class="{ 'q-radio-active': currentAnswer(q).indexOf(opt.option_code) !== -1 }"
                >
                  <view v-if="currentAnswer(q).indexOf(opt.option_code) !== -1" class="q-radio-dot"></view>
                </view>
                <text class="q-option-label">{{ opt.label }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 导航 -->
        <view class="nav-row">
          <view class="han-btn han-btn-ghost nav-btn" :class="{ 'nav-hidden': current === 0 }" @click="prev">
            <text class="nav-btn-text">上一页</text>
          </view>
          <view
            v-if="current < totalSteps - 1"
            class="han-btn han-btn-primary nav-btn nav-primary"
            :class="{ 'nav-disabled': !pageAnswered }"
            @click="next"
          >
            <text class="nav-btn-text nav-primary-text">下一页</text>
          </view>
          <view
            v-else
            class="han-btn han-btn-primary nav-btn nav-primary"
            :class="{ 'nav-disabled': !canSubmit }"
            @click="submit"
          >
            <text class="nav-btn-text nav-primary-text">提交问卷</text>
          </view>
        </view>

        <!-- 有资料模式：跳过整份问卷；跳过 = 直接进入状态总结确认，不经过疗愈诉求页 -->
        <view v-if="!required" class="skip-row" @click="skip">
          <text class="skip-text">跳过问卷，直接进入状态总结</text>
        </view>
        <view v-else class="must-note">
          <text class="must-note-text">无资料流程需要完成全部 {{ total }} 题后才能继续 · 已答 {{ answeredCount }} / {{ total }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.container {
  min-height: 100vh;
  padding: 70rpx 48rpx 60rpx;
  box-sizing: border-box;
}

/* ===== 页头 ===== */
.header {
  margin-bottom: 40rpx;
}
.header-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 16rpx;
}
.stage-seal {
  width: 88rpx;
  height: 88rpx;
  background: var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
  flex-shrink: 0;
}
.stage-seal-text {
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 44rpx;
  font-weight: 700;
}
.header-titles {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.step-tag {
  display: inline-block;
  align-self: flex-start;
  font-size: 22rpx;
  color: var(--ink-primary);
  background: rgba(107, 124, 94, 0.12);
  border: 1rpx solid rgba(107, 124, 94, 0.2);
  border-radius: 8rpx;
  padding: 4rpx 16rpx;
}
.page-title {
  font-size: 40rpx;
}
.page-subtitle {
  display: block;
  font-size: 26rpx;
  color: var(--text-secondary);
}

/* ===== 进度（墨线） ===== */
.progress-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 32rpx;
}
.progress-bar {
  flex: 1;
  height: 10rpx;
  background: var(--paper-deep);
  border-radius: 5rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--ink-primary), var(--ink-primary-dark));
  border-radius: 5rpx;
  transition: width 0.3s ease;
}
.progress-text {
  font-size: 24rpx;
  color: var(--text-muted);
  white-space: nowrap;
}

/* ===== 题目卡 ===== */
.page-card {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}
.q-card {
  border-radius: var(--radius-lg);
  padding: 40rpx 32rpx;
}
.q-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.q-index {
  display: block;
  font-size: 22rpx;
  color: var(--text-muted);
}
.q-required {
  font-size: 20rpx;
  color: var(--ink-seal);
  background: rgba(192, 57, 43, 0.07);
  border: 1rpx solid rgba(192, 57, 43, 0.18);
  border-radius: 6rpx;
  padding: 4rpx 14rpx;
}
.q-prompt {
  display: block;
  font-size: 32rpx;
  font-weight: 500;
  color: var(--ink-700);
  line-height: 1.6;
  margin-bottom: 36rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.q-options {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.q-option {
  display: flex;
  align-items: center;
  background: rgba(244, 238, 219, 0.45);
  border: 2rpx solid transparent;
  border-radius: 14rpx;
  padding: 26rpx 24rpx;
  transition: all 0.2s ease;
}
.q-option-active {
  background: rgba(107, 124, 94, 0.1);
  border-color: var(--ink-primary);
}
.q-radio {
  width: 36rpx;
  height: 36rpx;
  border: 3rpx solid var(--border-soft);
  border-radius: 50%;
  margin-right: 22rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.q-radio-active {
  border-color: var(--ink-primary);
}
.q-radio-dot {
  width: 18rpx;
  height: 18rpx;
  background: var(--ink-primary);
  border-radius: 50%;
}
.q-option-label {
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.5;
}

/* ===== 导航 ===== */
.nav-row {
  display: flex;
  gap: 24rpx;
  margin-top: 40rpx;
}
.nav-btn {
  flex: 1;
}
.nav-hidden {
  visibility: hidden;
}
.nav-btn-text {
  color: var(--ink-700);
  font-size: 30rpx;
}
.nav-primary-text {
  color: var(--text-inverse);
}
.nav-disabled {
  opacity: 0.5;
  box-shadow: none;
  background: var(--text-disabled);
}
.skip-row {
  display: flex;
  justify-content: center;
  margin-top: 36rpx;
  padding: 12rpx 0;
}
.skip-text {
  color: var(--text-muted);
  font-size: 26rpx;
  text-decoration: underline;
}
.must-note {
  display: flex;
  justify-content: center;
  margin-top: 36rpx;
}
.must-note-text {
  color: var(--text-muted);
  font-size: 24rpx;
}

/* ===== 加载 / 错误 / 等待 ===== */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid var(--paper-deep);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: var(--text-muted);
}
.loading-sub {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: var(--text-muted);
}
.error-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80rpx 40rpx;
  border-radius: var(--radius-lg);
}
.error-seal {
  width: 108rpx;
  height: 108rpx;
  border: 3rpx solid var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
  background: rgba(192, 57, 43, 0.04);
}
.error-seal-text {
  color: var(--ink-seal);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 52rpx;
  font-weight: 700;
}
.error-title {
  font-size: 32rpx;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  margin-bottom: 12rpx;
}
.error-text {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 36rpx;
  text-align: center;
  line-height: 1.6;
}
.btn-retry {
  padding: 20rpx 72rpx;
}
.btn-retry-text {
  color: var(--text-inverse);
  font-size: 28rpx;
}
.demo-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.demo-banner-text {
  font-size: 22rpx;
  color: var(--warning);
  background: rgba(198, 138, 46, 0.09);
  border: 1rpx solid rgba(198, 138, 46, 0.22);
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
}
.pending-card {
  border-radius: var(--radius-lg);
  padding: 64rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pending-seal {
  width: 100rpx;
  height: 100rpx;
  background: var(--ink-700);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
  box-shadow: 0 6rpx 18rpx rgba(26, 25, 22, 0.2);
}
.pending-seal-text {
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 44rpx;
  font-weight: 700;
}
.pending-title {
  font-size: 34rpx;
  font-weight: 600;
  color: var(--ink-700);
  margin-bottom: 20rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.pending-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
.btn-back {
  padding: 20rpx 64rpx;
}
.btn-back-text {
  color: var(--ink-700);
  font-size: 28rpx;
}
</style>
