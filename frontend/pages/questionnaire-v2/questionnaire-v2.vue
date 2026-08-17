<template>
  <view class="q-page">
    <!-- 水墨背景装饰 -->
    <view class="ink-bg-circle ink-bg-tl"></view>
    <view class="ink-bg-circle ink-bg-br"></view>

    <!-- 顶部进度区 -->
    <view class="q-header">
      <view class="q-header-top">
        <text class="q-title">状态评估</text>
        <text class="q-counter">{{ currentIndex + 1 }} / {{ totalQuestions }}</text>
      </view>
      <!-- 分段进度条 -->
      <view class="q-progress-track">
        <view
          v-for="(q, i) in questions"
          :key="q.question_id"
          class="q-progress-seg"
          :class="{
            'seg-done': i < currentIndex,
            'seg-current': i === currentIndex,
            'seg-safety': q.safety_only,
          }"
        ></view>
      </view>
      <text class="q-module-label">{{ currentModule.name }}</text>
    </view>

    <!-- 安全提示弹窗 -->
    <view v-if="showSafetyAlert" class="safety-overlay">
      <view class="safety-card ink-fade-in">
        <view class="safety-icon-wrap">
          <text class="safety-icon">!</text>
        </view>
        <text class="safety-title">安全提示</text>
        <text class="safety-desc">{{ safetyMessage }}</text>
        <view class="safety-actions">
          <view class="safety-btn safety-btn-primary" @tap="onSafetyConfirm">
            <text>我已了解</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 题目卡片 -->
    <scroll-view scroll-y class="q-scroll" :key="currentQuestion.question_id">
      <view class="q-card ink-card ink-fade-in">
        <!-- 题号 + 模块 -->
        <view class="q-card-header">
          <view class="q-badge" :class="{ 'q-badge-safety': currentQuestion.safety_only }">
            <text class="q-badge-text">{{ currentQuestion.order }}</text>
          </view>
          <text v-if="currentQuestion.reverse_scored" class="q-positive-tag">正向题</text>
          <text v-if="currentQuestion.safety_only" class="q-safety-tag">安全筛查</text>
        </view>

        <!-- 题目文本 -->
        <text class="q-text">{{ currentQuestion.text }}</text>

        <view v-if="currentQuestion.order === 19" class="safety-section-intro">
          <text class="safety-section-title">最后两题用于安全确认</text>
          <text class="safety-section-copy">这些选择不参与普通状态或音乐评分，只用于安全确认，并在必要时优先提供安全支持。</text>
        </view>

        <!-- 题型渲染区 -->
        <view class="q-options">
          <!-- goal_selection: one primary goal plus one optional secondary goal -->
          <view v-if="isGoalSelection" class="goal-selection">
            <text class="goal-hint">请选择一个主要目标，也可以再选一个次要目标</text>
            <view class="opt-row">
              <view
                v-for="opt in currentQuestion.options"
                :key="String(opt.value)"
                class="opt-btn goal-option"
                :class="{ 'opt-selected': isGoalSelected(opt.value) }"
                @tap="onToggleGoal(opt.value)"
              >
                <text class="opt-label">{{ opt.label }}</text>
                <text v-if="goalRole(opt.value)" class="goal-role">{{ goalRole(opt.value) }}</text>
              </view>
            </view>
            <textarea
              v-if="usesOtherGoal"
              class="custom-answer"
              :value="goalCustomText"
              maxlength="120"
              placeholder="请简要写下你希望获得的帮助"
              @input="onGoalCustomInput"
            />
          </view>

          <!-- frequency_0_4 / single_choice (button-row) -->
          <view v-else-if="isButtonRow" class="opt-row" :class="'cols-' + currentQuestion.ui.columns">
            <view
              v-for="opt in currentQuestion.options"
              :key="String(opt.value)"
              class="opt-btn"
              :class="{ 'opt-selected': isSelected(opt.value) }"
              @tap="onSelect(opt.value)"
            >
              <text class="opt-label">{{ opt.label }}</text>
              <text v-if="opt.hint" class="opt-hint">{{ opt.hint }}</text>
            </view>
          </view>

          <!-- visual_single (visual-row) -->
          <view v-else-if="isVisualRow" class="opt-visual-row">
            <view
              v-for="opt in currentQuestion.options"
              :key="String(opt.value)"
              class="opt-visual"
              :class="{ 'opt-selected': isSelected(opt.value) }"
              @tap="onSelectVisual(opt)"
            >
              <text class="opt-icon">{{ opt.icon }}</text>
              <text class="opt-vlabel">{{ opt.label }}</text>
              <text class="opt-vhint">{{ opt.hint }}</text>
            </view>
          </view>

          <!-- directional (direction + conditional severity) -->
          <view v-else-if="isDirectional" class="opt-directional">
            <view class="opt-row">
              <view
                v-for="opt in currentQuestion.options"
                :key="String(opt.value)"
                class="opt-btn"
                :class="{ 'opt-selected': isDirectionSelected(opt.value) }"
                @tap="onSelectDirection(opt.value)"
              >
                <text class="opt-label">{{ opt.label }}</text>
              </view>
            </view>
            <template v-if="currentDirection === 'decrease' || currentDirection === 'increase'">
              <text class="opt-group-label">变化程度</text>
              <view class="opt-row" :class="'cols-' + directionalSteps.length">
                <view
                  v-for="step in directionalSteps"
                  :key="step.value"
                  class="opt-btn"
                  :class="{ 'opt-selected': isSeveritySelected(step.value) }"
                  @tap="onSelectSeverity(step.value)"
                >
                  <text class="opt-label">{{ step.label }}</text>
                </view>
              </view>
            </template>
          </view>

          <!-- button-grid -->
          <view v-else-if="isButtonGrid" class="opt-grid" :class="'cols-' + currentQuestion.ui.columns">
            <view
              v-for="opt in currentQuestion.options"
              :key="String(opt.value)"
              class="opt-btn opt-btn-grid"
              :class="{ 'opt-selected': isSelected(opt.value) }"
              @tap="onSelect(opt.value)"
            >
              <text class="opt-label">{{ opt.label }}</text>
            </view>
          </view>

          <!-- button-list (duration / safety single) -->
          <view v-else-if="isButtonList" class="opt-list">
            <view
              v-for="opt in currentQuestion.options"
              :key="String(opt.value)"
              class="opt-btn opt-btn-list"
              :class="{ 'opt-selected': isSelected(opt.value) }"
              @tap="onSelect(opt.value)"
            >
              <text class="opt-label">{{ opt.label }}</text>
            </view>
          </view>

          <!-- checkbox-grid (multi_choice) -->
          <view v-else-if="isCheckboxGrid" class="opt-grid" :class="'cols-' + (currentQuestion.ui.columns || 2)">
            <view
              v-for="opt in currentQuestion.options"
              :key="String(opt.value)"
              class="opt-check"
              :class="{ 'opt-selected': isMultiSelected(opt.value), 'opt-disabled': isMultiDisabled(opt.value) }"
              @tap="onToggleMulti(opt.value)"
            >
              <view class="opt-check-box">
                <text v-if="isMultiSelected(opt.value)" class="opt-check-mark">✓</text>
              </view>
              <text class="opt-label">{{ opt.label }}</text>
            </view>
          </view>
          <textarea
            v-if="currentQuestion.question_id === 'q16_physical_signals' && isMultiSelected('other')"
            class="custom-answer"
            :value="physicalCustomText"
            maxlength="160"
            placeholder="请简要描述其他身体感受"
            @input="onPhysicalCustomInput"
          />
        </view>

        <!-- 正向题提示 -->
        <text v-if="currentQuestion.ui && currentQuestion.ui.note" class="q-note">{{ currentQuestion.ui.note }}</text>
      </view>

      <!-- 导航按钮 -->
      <view class="q-nav">
        <view v-if="currentIndex > 0" class="q-nav-btn q-nav-prev" @tap="onPrev">
          <text class="q-nav-text">上一题</text>
        </view>
        <view class="q-nav-spacer" v-if="currentIndex === 0"></view>
        <view
          class="q-nav-btn q-nav-next"
          :class="{ 'q-nav-disabled': !canProceed }"
          @tap="onNext"
        >
          <text class="q-nav-text">{{ currentIndex === totalQuestions - 1 ? '提交问卷' : '下一题' }}</text>
        </view>
      </view>

      <!-- 保存提示 -->
      <text class="q-save-hint">进度自动保存</text>
    </scroll-view>
  </view>
</template>

<script>
import { questionnaireV22 } from "@/common/questionnaire-data.js"
import { submitAssessment, saveQuestionnaireProgress, loadQuestionnaireProgress, clearQuestionnaireProgress, createSession } from "@/common/api-v2.js"
import { getSprint3Session, updateSprint3Session } from "@/common/sprint3-session.js"
import {
  applyExclusiveChoice,
  applyGoalChoice,
  applyPhysicalChoice,
  safetyFlowForAnswer,
  rendererModeFor,
  severityScaleFor,
  serializeAnswer,
  isAnswerComplete,
} from "@/common/questionnaire-rules.js"

export default {
  data() {
    return {
      questions: questionnaireV22.questions,
      modules: questionnaireV22.modules,
      totalQuestions: questionnaireV22.total_questions,
      currentIndex: 0,
      answers: {},
      showSafetyAlert: false,
      safetyMessage: "",
      safetyFlow: null,
      submitting: false,
    }
  },

  computed: {
    currentQuestion() {
      return this.questions[this.currentIndex] || {}
    },
    currentModule() {
      const q = this.currentQuestion
      return this.modules.find((m) => m.code === q.module) || {}
    },
    rendererMode() {
      return rendererModeFor(this.currentQuestion)
    },
    isGoalSelection() { return this.rendererMode === "goal" },
    isButtonRow() { return this.rendererMode === "button-row" },
    isVisualRow() { return this.rendererMode === "visual" },
    isButtonGrid() { return this.rendererMode === "button-grid" },
    isButtonList() { return this.rendererMode === "button-list" },
    isCheckboxGrid() { return this.rendererMode === "multi" },
    isDirectional() { return this.rendererMode === "directional" },
    directionalSteps() { return severityScaleFor(this.currentQuestion) },
    usesOtherGoal() {
      const answer = this.answers.q01_user_goal
      return Boolean(answer && (answer.primary_goal === "other" || answer.secondary_goal === "other"))
    },
    goalCustomText() {
      const answer = this.answers.q01_user_goal
      return answer && typeof answer.custom_goal_text === "string" ? answer.custom_goal_text : ""
    },
    physicalCustomText() {
      const answer = this.answers.q16_physical_signals
      return answer && typeof answer.custom_text === "string" ? answer.custom_text : ""
    },    currentDirection() {
      const ans = this.answers[this.currentQuestion.question_id]
      return ans && typeof ans === "object" ? ans.direction : undefined
    },
    canProceed() {
      return isAnswerComplete(this.currentQuestion, this.answers[this.currentQuestion.question_id])
    },
  },

  onLoad() {
    this.restoreProgress()
  },

  onShow() {
    // 每次显示时自动保存
  },

  onHide() {
    this.autoSave()
  },

  methods: {
    restoreProgress() {
      const saved = loadQuestionnaireProgress()
      if (saved && saved.answers && Object.keys(saved.answers).length > 0) {
        this.answers = saved.answers
        this.currentIndex = Math.min(saved.currentIndex || 0, this.totalQuestions - 1)
        uni.showToast({ title: "已恢复上次进度", icon: "none", duration: 1500 })
      }
    },

    autoSave() {
      saveQuestionnaireProgress(this.answers, this.currentIndex)
    },

    isSelected(value) {
      const q = this.currentQuestion
      const ans = this.answers[q.question_id]
      if (q.type === "visual_single") {
        return ans && ans.value === value
      }
      return ans === value
    },

    isMultiSelected(value) {
      const q = this.currentQuestion
      const ans = this.answers[q.question_id]
      if (q.question_id === "q16_physical_signals" && ans && typeof ans === "object") {
        return Array.isArray(ans.selected) && ans.selected.includes(value)
      }
      if (!Array.isArray(ans)) return false
      return ans.includes(value)
    },

    isMultiDisabled(value) {
      const q = this.currentQuestion
      const raw = this.answers[q.question_id]
      const ans = q.question_id === "q16_physical_signals" && raw && typeof raw === "object" ? raw.selected : raw
      if (!Array.isArray(ans) || ans.length === 0) return false
      const mutex = ["q16_physical_signals", "q20_emergency"].includes(q.question_id) ? "none" : null
      if (!mutex) return false
      // 如果选了 mutex 项，其他禁用；如果选了其他项， mutex 禁用
      if (value === mutex) return ans.some((v) => v !== mutex)
      return ans.includes(mutex)
    },

    onSelect(value) {
      const q = this.currentQuestion
      this.answers[q.question_id] = value
      this.autoSave()
      // 安全题检查
      this.checkSafety(value)
    },

    isDirectionSelected(value) {
      const ans = this.answers[this.currentQuestion.question_id]
      return ans && typeof ans === "object" && ans.direction === value
    },

    isSeveritySelected(value) {
      const ans = this.answers[this.currentQuestion.question_id]
      return ans && typeof ans === "object" && ans.severity === value
    },

    onSelectDirection(value) {
      const q = this.currentQuestion
      const prev = this.answers[q.question_id]
      const prevSeverity =
        prev && typeof prev === "object" && Number.isInteger(prev.severity) && prev.severity >= 1 && prev.severity <= 4
          ? prev.severity
          : undefined
      this.answers[q.question_id] = { direction: value, severity: value === "none" ? 0 : prevSeverity }
      this.autoSave()
    },

    onSelectSeverity(value) {
      const q = this.currentQuestion
      const prev = this.answers[q.question_id]
      const direction = prev && typeof prev === "object" ? prev.direction : undefined
      this.answers[q.question_id] = { direction, severity: value }
      this.autoSave()
    },

    onSelectVisual(opt) {
      const q = this.currentQuestion
      this.answers[q.question_id] = { value: opt.value, score: opt.score }
      this.autoSave()
    },

    onToggleMulti(value) {
      const q = this.currentQuestion
      if (q.question_id === "q16_physical_signals") {
        this.answers[q.question_id] = applyPhysicalChoice(this.answers[q.question_id], value)
        this.autoSave()
        return
      }
      const current = Array.isArray(this.answers[q.question_id]) ? this.answers[q.question_id] : []
      const next = applyExclusiveChoice(q.question_id, current, value)
      this.answers[q.question_id] = next
      this.autoSave()
      const flow = safetyFlowForAnswer(q.question_id, next)
      if (flow) this.triggerSafety(flow)
    },

    isGoalSelected(value) {
      const answer = this.answers.q01_user_goal
      return Boolean(answer && (answer.primary_goal === value || answer.secondary_goal === value))
    },

    goalRole(value) {
      const answer = this.answers.q01_user_goal
      if (!answer) return ""
      if (answer.primary_goal === value) return "主要"
      if (answer.secondary_goal === value) return "次要"
      return ""
    },

    onToggleGoal(value) {
      this.answers.q01_user_goal = applyGoalChoice(this.answers.q01_user_goal, value)
      this.autoSave()
    },

    onGoalCustomInput(event) {
      const current = this.answers.q01_user_goal || applyGoalChoice(undefined, "other")
      this.answers.q01_user_goal = {
        ...current,
        custom_goal_text: event.detail.value,
      }
      this.autoSave()
    },

    onPhysicalCustomInput(event) {
      const current = this.answers.q16_physical_signals || { selected: ["other"], custom_text: null }
      this.answers.q16_physical_signals = {
        ...current,
        custom_text: event.detail.value,
      }
      this.autoSave()
    },

    checkSafety(value) {
      const flow = safetyFlowForAnswer(this.currentQuestion.question_id, value)
      if (flow) this.triggerSafety(flow)
    },

    triggerSafety(flow) {
      this.safetyFlow = flow
      if (flow === "SAFETY_SELF_HARM") {
        this.safetyMessage = "感谢你的坦诚。你提到的感受很重要，建议你尽快联系专业人士获取支持。\n\n全国24小时心理援助热线：400-161-9995\n北京心理危机研究与干预中心：010-82951332\n\n你仍可在确认后收听辅助舒缓音乐，但它不能替代专业帮助。"
      } else if (flow === "SAFETY_EMERGENCY_PHYSICAL") {
        this.safetyMessage = "你描述的身体情况需要优先处理，建议立即就医或拨打120。\n\nHarmonyAI 会在评估后提供辅助舒缓音乐作为支持，但请务必先确保身体安全，必要时寻求专业医疗救助。"
      }
      this.showSafetyAlert = true
    },

    onSafetyConfirm() {
      this.showSafetyAlert = false
      // 安全流程：仍允许继续问卷，但后续不会进入 Diagnosis
      if (this.currentIndex < this.totalQuestions - 1) {
        this.currentIndex++
      }
    },

    onPrev() {
      if (this.currentIndex > 0) {
        this.currentIndex--
      }
    },

    async onNext() {
      if (!this.canProceed) {
        uni.showToast({ title: "请先选择答案", icon: "none" })
        return
      }

      if (this.currentIndex < this.totalQuestions - 1) {
        this.currentIndex++
        this.autoSave()
      } else {
        await this.handleSubmit()
      }
    },

    async handleSubmit() {
      if (this.submitting) return
      this.submitting = true
      uni.showLoading({ title: "正在评估..." })
      try {
        const answersArray = this.questions.map((q) => {
          const { value, score } = serializeAnswer(q, this.answers[q.question_id])
          return {
            question_id: q.question_id,
            value,
            type: q.type,
            ...(score === undefined ? {} : { score }),
          }
        })
        let session = getSprint3Session()
        if (!session.session_id) {
          const created = await createSession({ entry_mode: "full" })
          session = updateSprint3Session({ session_id: created.session_id, user_id: "demo_user_001" })
        }
        const questionnaireAnswers = {
          schema_version: "questionnaire_v2.2",
          time_window_days: 14,
          answers: answersArray,
          safety_flags: this.safetyFlow ? [this.safetyFlow] : [],
        }
        const assessment = await submitAssessment({
          session_id: session.session_id,
          user_id: session.user_id || "demo_user_001",
          document_id: session.document_id || null,
          document_text: session.document_text || null,
          narrative_text: session.narrative_text || null,
          questionnaire_answers: questionnaireAnswers,
        })
        updateSprint3Session({
          questionnaire_answers: questionnaireAnswers,
          assessment,
          assessment_id: assessment.assessment_id,
          assessment_revision: assessment.revision || 1,
        })
        clearQuestionnaireProgress()
        const safety = (assessment.safety_flags || []).length ? "&safety=true" : ""
        uni.redirectTo({ url: "/pages/assessment-result/assessment-result?assessment_id=" +
          encodeURIComponent(assessment.assessment_id) + safety })
      } catch (err) {
        uni.showToast({ title: err.message || "评估失败", icon: "none", duration: 3000 })
      } finally {
        this.submitting = false
        uni.hideLoading()
      }
    },
  },
}
</script>

<style scoped>
.q-page {
  min-height: 100vh;
  background: #F7F3EB;
  position: relative;
  overflow: hidden;
}

/* 水墨背景 */
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

/* 顶部进度 */
.q-header {
  position: relative;
  z-index: 1;
  padding: 60rpx 40rpx 20rpx;
}
.q-header-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24rpx;
}
.q-title {
  font-size: 40rpx;
  font-weight: 700;
  color: #4A6B5C;
  letter-spacing: 4rpx;
}
.q-counter {
  font-size: 28rpx;
  color: #9C9585;
  font-weight: 600;
}

/* 分段进度条 */
.q-progress-track {
  display: flex;
  gap: 4rpx;
  margin-bottom: 16rpx;
}
.q-progress-seg {
  flex: 1;
  height: 6rpx;
  border-radius: 3rpx;
  background: #E8E0CC;
  transition: all 0.3s;
}
.seg-done {
  background: #6B8B7C;
}
.seg-current {
  background: #4A6B5C;
  height: 8rpx;
}
.seg-safety.seg-done,
.seg-safety.seg-current {
  background: #C44A3E;
}

.q-module-label {
  font-size: 24rpx;
  color: #9C9585;
  letter-spacing: 2rpx;
}

/* 滚动区 */
.q-scroll {
  position: relative;
  z-index: 1;
  height: calc(100vh - 200rpx);
  padding: 0 40rpx 120rpx;
}

/* 题目卡片 */
.q-card {
  background: #FFFEFA;
  border-radius: 24rpx;
  padding: 48rpx 36rpx;
  box-shadow: 0 4rpx 16rpx rgba(74, 107, 92, 0.12);
  border: 1rpx solid #D9D0BD;
  margin-bottom: 32rpx;
}

.q-card-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 32rpx;
}
.q-badge {
  width: 56rpx;
  height: 56rpx;
  border-radius: 12rpx;
  background: #4A6B5C;
  display: flex;
  align-items: center;
  justify-content: center;
}
.q-badge-text {
  color: #FFFEFA;
  font-size: 30rpx;
  font-weight: 700;
}
.q-badge-safety {
  background: #C44A3E;
}
.q-positive-tag {
  font-size: 22rpx;
  color: #5A8A6B;
  background: rgba(90, 138, 107, 0.12);
  padding: 6rpx 16rpx;
  border-radius: 8rpx;
}
.q-safety-tag {
  font-size: 22rpx;
  color: #C44A3E;
  background: rgba(196, 74, 62, 0.12);
  padding: 6rpx 16rpx;
  border-radius: 8rpx;
}

.q-text {
  font-size: 34rpx;
  font-weight: 600;
  color: #2C2C2A;
  line-height: 1.6;
  margin-bottom: 40rpx;
  display: block;
}

/* 选项区 */
.safety-section-intro {
  margin-top: 24rpx;
  padding: 24rpx;
  border-radius: 18rpx;
  background: #fff3ed;
  border: 1rpx solid #e7b2a2;
}
.safety-section-title,
.safety-section-copy,
.goal-hint,
.goal-role {
  display: block;
}
.safety-section-title {
  color: #a43f32;
  font-weight: 700;
  margin-bottom: 8rpx;
}
.safety-section-copy {
  color: #694b45;
  line-height: 1.6;
}
.goal-hint {
  margin-bottom: 18rpx;
  color: #6b746d;
}
.goal-option {
  position: relative;
}
.goal-role {
  margin-top: 8rpx;
  color: #4c705f;
  font-size: 22rpx;
}
.custom-answer {
  width: 100%;
  box-sizing: border-box;
  min-height: 140rpx;
  margin-top: 20rpx;
  padding: 20rpx;
  border: 1rpx solid #c8bfae;
  border-radius: 16rpx;
  background: #fffdf9;
  color: #28342e;
}
.q-options {
  margin-bottom: 20rpx;
}

/* button-row */
.opt-row {
  display: flex;
  gap: 12rpx;
}
.opt-row.cols-5 .opt-btn {
  flex: 1;
}
.opt-directional {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.opt-directional .opt-row .opt-btn {
  flex: 1;
}
.opt-group-label {
  font-size: 24rpx;
  color: #9C9585;
  font-weight: 600;
  letter-spacing: 1rpx;
  margin-top: 8rpx;
}
.opt-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24rpx 12rpx;
  border-radius: 16rpx;
  border: 2rpx solid #D9D0BD;
  background: #FFFEFA;
  transition: all 0.2s;
}
.opt-btn:active {
  transform: scale(0.96);
}
.opt-selected {
  border-color: #4A6B5C;
  background: rgba(74, 107, 92, 0.08);
  box-shadow: 0 2rpx 8rpx rgba(74, 107, 92, 0.15);
}
.opt-label {
  font-size: 28rpx;
  font-weight: 600;
  color: #2C2C2A;
}
.opt-selected .opt-label {
  color: #4A6B5C;
}
.opt-hint {
  font-size: 20rpx;
  color: #9C9585;
  margin-top: 6rpx;
}

/* visual-row */
.opt-visual-row {
  display: flex;
  gap: 8rpx;
}
.opt-visual {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28rpx 8rpx 20rpx;
  border-radius: 16rpx;
  border: 2rpx solid #D9D0BD;
  background: #FFFEFA;
  transition: all 0.2s;
}
.opt-visual:active {
  transform: scale(0.96);
}
.opt-selected {
  border-color: #4A6B5C;
  background: rgba(74, 107, 92, 0.08);
}
.opt-icon {
  font-size: 48rpx;
  margin-bottom: 12rpx;
}
.opt-vlabel {
  font-size: 24rpx;
  font-weight: 600;
  color: #2C2C2A;
}
.opt-selected .opt-vlabel {
  color: #4A6B5C;
}
.opt-vhint {
  font-size: 18rpx;
  color: #9C9585;
  margin-top: 4rpx;
}

/* button-grid */
.opt-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.opt-grid.cols-2 .opt-btn-grid,
.opt-grid.cols-2 .opt-check {
  width: calc(50% - 8rpx);
}
.opt-btn-grid {
  padding: 28rpx 20rpx;
  text-align: center;
}

/* button-list */
.opt-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.opt-btn-list {
  padding: 32rpx 28rpx;
  text-align: left;
  border-radius: 16rpx;
}
.opt-btn-list .opt-label {
  font-size: 30rpx;
}

/* checkbox-grid */
.opt-check {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 24rpx 20rpx;
  border-radius: 16rpx;
  border: 2rpx solid #D9D0BD;
  background: #FFFEFA;
  transition: all 0.2s;
}
.opt-check:active {
  transform: scale(0.97);
}
.opt-check.opt-selected {
  border-color: #4A6B5C;
  background: rgba(74, 107, 92, 0.08);
}
.opt-check.opt-disabled {
  opacity: 0.4;
}
.opt-check-box {
  width: 40rpx;
  height: 40rpx;
  border-radius: 8rpx;
  border: 2rpx solid #D9D0BD;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.opt-selected .opt-check-box {
  background: #4A6B5C;
  border-color: #4A6B5C;
}
.opt-check-mark {
  color: #FFFEFA;
  font-size: 24rpx;
  font-weight: 700;
}

/* 提示 */
.q-note {
  font-size: 22rpx;
  color: #9C9585;
  margin-top: 16rpx;
  display: block;
}

/* 导航 */
.q-nav {
  display: flex;
  gap: 24rpx;
  margin-top: 16rpx;
  margin-bottom: 24rpx;
}
.q-nav-spacer {
  flex: 1;
}
.q-nav-btn {
  padding: 28rpx 48rpx;
  border-radius: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.q-nav-prev {
  background: transparent;
  border: 2rpx solid #D9D0BD;
}
.q-nav-prev .q-nav-text {
  color: #6B6B5C;
  font-size: 28rpx;
}
.q-nav-next {
  flex: 1;
  background: #4A6B5C;
  box-shadow: 0 4rpx 16rpx rgba(74, 107, 92, 0.3);
}
.q-nav-next .q-nav-text {
  color: #FFFEFA;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 2rpx;
}
.q-nav-disabled {
  opacity: 0.4;
}
.q-nav-btn:active {
  transform: scale(0.97);
}

.q-save-hint {
  font-size: 20rpx;
  color: #C5BBA5;
  text-align: center;
  display: block;
  margin-bottom: 40rpx;
}

/* 安全弹窗 */
.safety-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60rpx;
}
.safety-card {
  background: #FFFEFA;
  border-radius: 32rpx;
  padding: 60rpx 48rpx;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.safety-icon-wrap {
  width: 100rpx;
  height: 100rpx;
  border-radius: 50%;
  background: #C44A3E;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
}
.safety-icon {
  color: #FFFEFA;
  font-size: 56rpx;
  font-weight: 700;
}
.safety-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #C44A3E;
  margin-bottom: 24rpx;
}
.safety-desc {
  font-size: 26rpx;
  color: #6B6B5C;
  line-height: 1.8;
  text-align: center;
  margin-bottom: 40rpx;
}
.safety-actions {
  width: 100%;
}
.safety-btn {
  padding: 28rpx;
  border-radius: 32rpx;
  text-align: center;
}
.safety-btn-primary {
  background: #C44A3E;
}
.safety-btn-primary text {
  color: #FFFEFA;
  font-size: 30rpx;
  font-weight: 600;
}
</style>
