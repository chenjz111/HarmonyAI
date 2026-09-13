<script>
/**
 * V3.1 五脏状态问卷页（10 题分 5 页，每页 2 题）
 * 合同依据（V3.1_FREEZE_BASELINE 83fe2f4）：
 *   - docs/product/app-v3.1-teacher-user-flow.md §5/§6（唯一 USER-FACING FLOW）
 *   - knowledge/v3/questionnaire-v3.0.1.json（唯一可执行问卷，checksum 69a01d…）
 *   - backend/app/schemas/v3/flow_v31.py QuestionnaireResult（q01-q10 完整有序提交）
 *
 * - 题目与选项文案来自权威清单模块（与后端同源，逐字一致，前端不维护第二套）
 * - 频率题（q01-q05）选项文案内嵌于每题 options（V3.0.1：每题 5 个个性化文案）
 * - 展示分页：PAGE_SIZE = 2，共 5 步（进度以页为单位 1/5 ~ 5/5）；提交时一次性提交全部答案
 * - 冻结规则：Q1-Q10 全部必答，问卷内不提供跳过出口
 *   （"是否填写问卷"的选择在资料摘要后的轻量选择页完成）
 * - real 模式下提交问卷并创建真实 Assessment；失败显式提示且保留当前答案
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"

const PAGE_SIZE = 2 // V3.1：每页展示 2 题

export default {
  data() {
    return {
      loading: true,
      error: "",
      schema: null,
      withDocument: false, // 会话来源：有资料流程（仅用于步骤标签显示）
      current: 0, // 当前页索引（每页 PAGE_SIZE 题）
      answers: {}, // { question_id: number | [option_code, ...] }
      submitting: false,
      submittingAssessment: false,
      agentPending: false, // real 模式：等待后端综合评估能力接入
      simulated: false, // hybrid/mock：演示数据标识
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
    back() {
      uni.navigateBack()
    },
    optionImage(q, opt, optIndex) {
      const qid = q && q.question_id
      const frequencyMatch = /^q0([1-5])$/.exec(qid)
      if (frequencyMatch && this.isFrequency(q)) {
        return `/static/v31-questionnaire/q${frequencyMatch[1]}-${optIndex}.png`
      }
      if (qid === "q06") {
        return opt.is_none
          ? "/static/v31-questionnaire/q7-4.png"
          : `/static/v31-questionnaire/q6-${optIndex}.png`
      }
      const multiMatch = /^q(0[7-9]|10)$/.exec(qid)
      if (multiMatch) {
        return `/static/v31-questionnaire/q${Number(multiMatch[1])}-${optIndex}.png`
      }
      return ""
    },
    async load() {
      this.loading = true
      this.error = ""
      try {
        // 会话来源仅用于步骤标签显示；冻结规则下 Q1-Q10 一旦进入问卷全部必答
        const [schema, session] = await Promise.all([
          apiV3.getQuestionnaireSchema(),
          apiV3.getSession(),
        ])
        this.schema = schema
        this.withDocument = !!session && session.input_mode === "with_document"
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
    // 频率题：单选 0..4（按权威清单 score 取值；再点一次同选项可取消）
    selectFrequency(q, option) {
      const qid = q.question_id
      const cur = this.answers[qid]
      this.answers[qid] = typeof cur === "number" && cur === option.score ? null : option.score
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
    // V3.1 冻结流程：完成 10 题 → 提交 → 评估 → 选填疗愈诉求 → 近期状态总结。
    // 问卷内不再提供跳过出口（"是否填写问卷"的选择已前移到轻量选择页）。
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
    // 兼容旧演示构建的等待态；正式 real 模式不会再产生该状态
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
  <view class="questionnaire-page v31-scroll-page" :class="{ 'questionnaire-page-q34': current === 1, 'questionnaire-page-q56': current === 2, 'questionnaire-page-q78': current === 3, 'questionnaire-page-q910': current === 4 }">
    <view class="container">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回" @click="back"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
        <view class="page-progress"><text>{{ current + 1 }}/{{ totalSteps || 5 }}</text><view class="mini-track"><view class="mini-fill" :style="{ width: (((current + 1) / (totalSteps || 5)) * 100) + '%' }" /></view></view>
      </view>
      <view class="section-heading">
        <view class="section-mark">◖</view>
        <view><text class="section-title">{{ current >= 2 ? '身体状态' : '情绪感知' }}</text><text class="section-subtitle">{{ current >= 2 ? '再看看身体的感觉，有就有、没有就没有，选“都很少出现”就好。' : '先随便聊聊你最近一周的心情，选最接近的就行。' }}</text></view>
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

        <!-- 当前页 2 道题 -->
        <view class="page-card">
          <view
            v-for="(q, i) in pageQuestions"
            :key="q.question_id"
            class="q-card ink-fade-up"
          >
            <view class="q-card-head">
              <text class="q-index">Q{{ pageStartIndex + i + 1 }}</text>
              <view class="q-prompt-line"><text class="q-prompt">{{ q.prompt }}</text><text v-if="!isFrequency(q)" class="multi-hint">（可多选）</text></view>
            </view>

            <!-- 频率题（q01-q05）：单选 0..4，选项文案内嵌于每题（V3.0.1） -->
            <view v-if="isFrequency(q)" class="q-options frequency-options">
              <view
                v-for="(opt, optIndex) in q.options"
                :key="'f' + q.question_id + opt.score"
                class="q-option"
                :class="{ 'q-option-active': currentFrequencyValue(q) === opt.score }"
                role="button"
                :aria-pressed="currentFrequencyValue(q) === opt.score"
                @click="selectFrequency(q, opt)"
              >
                <image v-if="optionImage(q, opt, optIndex)" class="option-image" :src="optionImage(q, opt, optIndex)" mode="aspectFit" />
                <text class="q-option-label">{{ opt.label }}</text>
              </view>
            </view>

            <!-- 多选题（q06-q10） -->
            <view v-else class="q-options multi-options" :class="'multi-options-' + q.options.length">
              <view
                v-for="(opt, optIndex) in q.options"
                :key="opt.option_code"
                class="q-option"
                :class="{ 'q-option-active': currentAnswer(q).indexOf(opt.option_code) !== -1, 'q-option-none': opt.is_none }"
                @click="toggleOption(q, opt)"
              >
                <image v-if="optionImage(q, opt, optIndex)" class="option-image" :src="optionImage(q, opt, optIndex)" mode="aspectFit" />
                <view v-else-if="opt.is_none" class="q-none-mark">✓</view>
                <view
                  v-else
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
            <text class="nav-btn-text">上一题</text>
          </view>
          <view
            v-if="current < totalSteps - 1"
            class="han-btn han-btn-primary nav-btn nav-primary"
            :class="{ 'nav-disabled': !pageAnswered }"
            @click="next"
          >
            <text class="nav-btn-text nav-primary-text">下一题</text>
          </view>
          <view
            v-else
            class="han-btn han-btn-primary nav-btn nav-primary"
            :class="{ 'nav-disabled': !canSubmit }"
            @click="submit"
          >
            <text class="nav-btn-text nav-primary-text">完成问卷</text>
          </view>
        </view>

        <!-- 冻结规则：Q1-Q10 全部必答，问卷内无跳过出口 -->
        <view class="must-note">
          <text class="must-note-text">需要完成全部 {{ total }} 题后才能继续 · 已答 {{ answeredCount }} / {{ total }}</text>
        </view>
        <view class="page-motto"><text>—　五音和鸣 · 乐养身心　—</text></view>
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

/* ===== Owner 视觉稿：手机问卷 ===== */
.questionnaire-page {
  width: 100%;
  max-width: 430px;
  min-height: 100vh;
  margin: 0 auto;
  color: #064c50;
  background: #f8f8f1 url('/static/v31-questionnaire/questionnaire-background.png') center top / 100% 100% no-repeat;
  font-family: system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.questionnaire-page-q34 { background-image:url('/static/v31-questionnaire/questionnaire-background-q34.png'); }
.questionnaire-page-q56 { background-image:url('/static/v31-questionnaire/questionnaire-background-q34.png'); }
.questionnaire-page-q78 { background-image:url('/static/v31-questionnaire/questionnaire-background-q34.png'); }
.questionnaire-page-q910 { background-image:url('/static/v31-questionnaire/questionnaire-background-q34.png'); }
.questionnaire-page .container { min-height:100vh; padding:calc(12px + env(safe-area-inset-top)) 8px calc(24px + env(safe-area-inset-bottom)); }
.brand-row { display:flex; align-items:center; min-height:42px; gap:7px; padding:0 5px; }
.back-button { display:flex; align-items:center; justify-content:center; width:30px; height:40px; margin:0; padding:0; border:0; background:transparent; flex-shrink:0; }
.back-button::after { border:0; }
.back-chevron { width:10px; height:10px; border-left:2px solid #064c50; border-bottom:2px solid #064c50; transform:rotate(45deg); }
.brand-leaf { width:34px; height:34px; }
.brand-copy { display:flex; flex-direction:column; gap:1px; }
.brand-name { font-size:15px; font-weight:700; line-height:1.2; }
.brand-tagline { font-size:9px; letter-spacing:1px; white-space:nowrap; }
.page-progress { margin-left:auto; width:68px; text-align:right; font-size:12px; color:#236b69; }
.mini-track { height:4px; margin-top:6px; overflow:hidden; border-radius:4px; background:rgba(48,112,102,.18); }
.mini-fill { height:100%; border-radius:4px; background:#3d9484; transition:width .25s ease; }
.section-heading { display:flex; align-items:flex-start; gap:8px; margin:9px 3px 12px; }
.section-mark { display:flex; align-items:center; justify-content:center; width:29px; height:29px; border-radius:50%; color:#286f68; background:rgba(208,229,219,.7); font-size:24px; transform:rotate(-28deg); }
.section-title,.section-subtitle { display:block; }
.section-title { font-family:'KaiTi','STKaiti',serif; font-size:19px; font-weight:700; line-height:1.25; }
.section-subtitle { margin-top:3px; font-size:11px; line-height:1.45; }
.questionnaire-page .demo-banner { margin:0 0 6px; }
.questionnaire-page .page-card { gap:9px; }
.questionnaire-page .q-card { box-sizing:border-box; padding:11px 8px 8px; border:1px solid rgba(57,104,93,.08); border-radius:11px; background:rgba(255,255,251,.79); box-shadow:0 2px 8px rgba(31,72,62,.08); }
.questionnaire-page .q-card-head { display:grid; grid-template-columns:auto 1fr; align-items:start; gap:7px; margin-bottom:8px; }
.questionnaire-page .q-index { color:#064c50; font-size:18px; font-weight:750; line-height:1.4; }
.questionnaire-page .q-prompt-line { display:flex; align-items:baseline; flex-wrap:wrap; gap:2px; min-width:0; }
.questionnaire-page .q-prompt { margin:0; color:#154f59; font-family:inherit; font-size:13px; font-weight:600; line-height:1.6; }
.questionnaire-page .multi-hint { color:#39726f; font-size:11px; line-height:1.6; white-space:nowrap; }
.questionnaire-page .frequency-options { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:3px; }
.questionnaire-page .frequency-options .q-option { display:flex; flex-direction:column; align-items:center; min-width:0; padding:2px 1px 3px; border:1px solid transparent; border-radius:9px; background:transparent; }
.questionnaire-page .frequency-options .q-option-active { border-color:#2e897c; background:rgba(222,242,233,.65); box-shadow:0 2px 5px rgba(30,105,91,.12); }
.questionnaire-page-q34 .frequency-options { gap:5px; }
.questionnaire-page-q34 .frequency-options .q-option { padding:5px 2px 7px; border-color:rgba(37,92,83,.10); background:rgba(255,255,252,.67); }
.questionnaire-page-q34 .frequency-options .q-option-active { border-color:#2e897c; background:rgba(222,242,233,.72); }
.questionnaire-page-q34 .option-image { width:58px; height:55px; }
.questionnaire-page-q56 .frequency-options { gap:5px; }
.questionnaire-page-q56 .frequency-options .q-option { padding:5px 2px 7px; border-color:rgba(37,92,83,.10); background:rgba(255,255,252,.67); }
.questionnaire-page-q56 .frequency-options .q-option-active { border-color:#2e897c; background:rgba(222,242,233,.72); }
.questionnaire-page-q56 .option-image { width:58px; height:55px; }
.option-image { width:50px; max-width:100%; height:47px; border-radius:50%; mix-blend-mode:multiply; }
.questionnaire-page .frequency-options .q-option-label { min-height:34px; margin-top:2px; color:#174d55; font-size:10px; line-height:1.35; text-align:center; overflow-wrap:anywhere; }
.questionnaire-page .multi-options { gap:8px; }
.questionnaire-page .multi-options .q-option { padding:10px; }
.questionnaire-page .multi-options-5 { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:4px; }
.questionnaire-page .multi-options-4 { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:5px; }
.questionnaire-page-q56 .multi-options .q-option,
.questionnaire-page-q78 .multi-options .q-option,
.questionnaire-page-q910 .multi-options .q-option { flex-direction:column; justify-content:flex-start; min-width:0; padding:6px 2px 8px; border:1px solid rgba(37,92,83,.10); background:rgba(255,255,252,.67); }
.questionnaire-page-q56 .multi-options .q-option-active,
.questionnaire-page-q78 .multi-options .q-option-active,
.questionnaire-page-q910 .multi-options .q-option-active { border-color:#2e897c; background:rgba(222,242,233,.72); }
.questionnaire-page-q56 .multi-options .q-option-label,
.questionnaire-page-q78 .multi-options .q-option-label,
.questionnaire-page-q910 .multi-options .q-option-label { margin-top:4px; color:#174d55; font-size:10px; line-height:1.35; text-align:center; overflow-wrap:anywhere; }
.questionnaire-page-q56 .multi-options .option-image,
.questionnaire-page-q78 .multi-options .option-image,
.questionnaire-page-q910 .multi-options .option-image { width:50px; height:48px; }
.q-none-mark { display:flex; align-items:center; justify-content:center; width:24px; height:24px; margin-right:8px; border-radius:50%; color:#fff; background:#3d897b; font-size:14px; }
.questionnaire-page .nav-row { justify-content:center; gap:8px; margin:14px 52px 0; }
.questionnaire-page-q34 .nav-row { margin-left:20px; margin-right:20px; }
.questionnaire-page-q56 .nav-row { margin-left:20px; margin-right:20px; }
.questionnaire-page-q78 .nav-row { margin-left:20px; margin-right:20px; }
.questionnaire-page-q910 .nav-row { margin-left:20px; margin-right:20px; }
.questionnaire-page-q34 .nav-row .han-btn-ghost,
.questionnaire-page-q56 .nav-row .han-btn-ghost,
.questionnaire-page-q78 .nav-row .han-btn-ghost,
.questionnaire-page-q910 .nav-row .han-btn-ghost { display:flex; align-items:center; justify-content:center; min-height:46px; border:0; border-radius:28px; background:rgba(214,231,226,.76); }
.questionnaire-page .nav-hidden { display:none; }
.questionnaire-page .nav-btn { min-height:46px; border-radius:28px; }
.questionnaire-page .nav-primary { display:flex; align-items:center; justify-content:center; width:100%; flex:1; color:#fff; background:linear-gradient(105deg,#24695e,#28776a); }
.questionnaire-page .nav-btn-text { font-size:16px; white-space:nowrap; word-break:keep-all; }
.questionnaire-page .must-note { display:none; }
.page-motto { margin-top:9px; text-align:center; color:#285e5b; font-family:'KaiTi','STKaiti',serif; font-size:11px; letter-spacing:1px; }
@media(max-width:350px) {
  .questionnaire-page .container { padding-left:5px; padding-right:5px; }
  .brand-tagline { font-size:8px; letter-spacing:0; }
  .page-progress { width:55px; }
  .questionnaire-page .q-prompt { font-size:12px; }
  .option-image { width:43px; height:42px; }
  .questionnaire-page .frequency-options .q-option-label { font-size:9px; }
  .questionnaire-page .nav-row { margin-left:42px; margin-right:42px; }
}
</style>
