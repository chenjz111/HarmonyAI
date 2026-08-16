<template>
  <view class="ar-page">
    <view class="ink-bg-circle ink-bg-tl"></view>
    <view class="ink-bg-circle ink-bg-br"></view>

    <view v-if="loading" class="ar-loading">
      <view class="ar-loading-circle"><text class="ar-loading-text">和</text></view>
      <text class="ar-loading-label">正在综合问卷、文字和材料信息...</text>
    </view>

    <view v-else-if="loadError" class="ar-error">
      <text class="ar-error-title">暂时无法显示评估</text>
      <text class="ar-error-msg">{{ loadError }}</text>
      <view class="ar-error-btn" @tap="loadData"><text>重新尝试</text></view>
    </view>

    <scroll-view v-else scroll-y class="ar-scroll">
      <view v-if="operationError" class="ar-error">
        <text class="ar-error-title">操作未完成</text>
        <text class="ar-error-msg">{{ operationError }}</text>
      </view>

      <view v-if="needsSafetyVerification" class="ar-card ink-card safety-verification-card">
        <text class="ar-eyebrow">信息核验</text>
        <text class="ar-main-title">这条材料信息描述的是现在的你吗？</text>
        <text class="ar-body-copy">材料中出现了需要关注的内容，但它也可能来自历史记录、他人信息或识别误差。请先确认，系统再决定后续服务。</text>
        <view class="verification-options">
          <view
            v-for="item in safetyVerificationOptions"
            :key="item.value"
            class="verification-option"
            @tap="submitSafetyVerification(item.value)"
          >
            <text>{{ item.label }}</text>
          </view>
        </view>
        <text class="ar-help-copy">如果不确定，可以选择“暂时无法确认”。不确定信息不会被直接当作当前风险。</text>
      </view>

      <template v-else>
        <view class="ar-card ink-card ar-summary-card">
          <text class="ar-eyebrow">AI 状态理解</text>
          <text class="ar-main-title">确认一下我们对你当前状态的理解</text>
          <text class="ar-summary-text">{{ assessment.assessment_summary || "已根据你提供的信息形成初步状态理解。" }}</text>
          <text v-if="usesQuestionnaireRuleFallback" class="ar-body-copy">当前已使用问卷规则完成基础分析。</text>
        </view>

        <view v-if="sourceList.length" class="ar-section">
          <text class="ar-section-title">本次参考的信息</text>
          <view class="plain-source-list">
            <view v-for="src in sourceList" :key="src.key" class="plain-source-chip" :class="'source-' + src.status">
              <text>{{ src.name }} · {{ src.status === 'done' ? '已参考' : '未提供或暂不可用' }}</text>
            </view>
          </view>
        </view>

        <view v-if="emotionEntries.length" class="ar-section">
          <text class="ar-section-title">目前比较突出的感受</text>
          <view class="plain-state-grid">
            <view v-for="dim in emotionEntries" :key="dim.key" class="plain-state-card ink-card">
              <text class="plain-state-name">{{ dim.display_name }}</text>
              <text class="plain-state-level">{{ plainSeverity(dim.score) }}</text>
            </view>
          </view>
        </view>

        <view v-if="physicalEntries.length" class="ar-section">
          <text class="ar-section-title">你提到的身体感受</text>
          <view class="plain-body-card ink-card">
            <text v-for="phys in physicalEntries" :key="phys.key" class="plain-body-text">{{ phys.value || phys.display_name }}</text>
          </view>
        </view>

        <view class="ar-section">
          <view class="ar-confirm-card ink-card">
            <text class="ar-confirm-title">这和你现在的实际感受接近吗？</text>
            <text class="ar-confirm-copy">你的确认会作为下一步辅助辨证和音乐建议的依据。</text>
            <view v-if="confirmationStatus === 'error'" class="ar-error compact-error">
              <text class="ar-error-msg">{{ confirmationError }}</text>
            </view>
            <view v-if="!confirmationLevel" class="ar-confirm-btns">
              <view class="ar-confirm-btn ar-confirm-full" @tap="onConfirm('fully_accurate')">
                <text>基本符合，继续</text>
              </view>
              <view class="ar-confirm-btn ar-confirm-partial" @tap="onConfirm('partially_accurate')">
                <text>有些地方不对，我要修改</text>
              </view>
            </view>
            <view v-else-if="confirmationLevel !== 'fully_accurate'" class="ar-correction">
              <text class="ar-correction-hint">请写下需要补充或修改的地方：</text>
              <textarea
                class="ar-correction-input"
                v-model="correctionText"
                placeholder="例如：我不是害怕，主要是睡前脑子停不下来。"
                maxlength="300"
              />
              <view class="ar-correction-btns">
                <view class="ar-correction-cancel" @tap="resetConfirm"><text>返回</text></view>
                <view class="ar-correction-submit" @tap="submitCorrection"><text>提交修改</text></view>
              </view>
            </view>
          </view>
        </view>

        <text class="ar-disclaimer">{{ assessment.disclaimer || "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。" }}</text>
      </template>

      <view class="ar-bottom-space"></view>
    </scroll-view>
  </view>
</template>
<script>
import { submitFollowUpAnswers, confirmAssessment, runWorkflow, verifyAssessmentSafety } from "@/common/api-v2.js"
import { getSprint3Session, updateSprint3Session } from "@/common/sprint3-session.js"
import { safeUiError } from "@/common/safe-ui-error.js"
import { createAssessmentFlow, applyFollowUpRevision, applyCorrectionRevision, workflowPayload, confirmationFailed } from "@/common/assessment-page-flow.js"

import { safetyDestination, safetyVerificationPayload } from "@/common/safety-flow.js"
export default {
  data() {
    return {
      loading: true,
      step: 0,
      assessmentId: "",
      isSafetyFlow: false,
      assessment: {},
      loadError: "",
      followUpQuestions: [],
      followUpAnswers: {},
      followUpSubmitted: false,
      confirming: false,
      confirmationStatus: 'idle',
      confirmationError: '',
      confirmationLevel: "",
      correctionText: "",
      operationError: "",
      safetyVerificationOptions: [
        { value: "current", label: "是，描述的是我现在的情况" },
        { value: "past_resolved", label: "是过去的情况，现在已经缓解" },
        { value: "other_person", label: "这是他人的信息" },
        { value: "ocr_error", label: "材料识别有误" },
        { value: "uncertain", label: "暂时无法确认" },
      ],
      safetyVerificationSubmitting: false,    }
  },

  computed: {
    needsSafetyVerification() {
      return this.assessment.safety_status === "needs_verification"
    },
    usesQuestionnaireRuleFallback() {
      const narrative = this.assessment.input_processing_status?.narrative
      return narrative?.status === "unavailable"
    },
    sourceList() {
      const ips = this.assessment.input_processing_status || {}
      const list = []
      if (ips.questionnaire) {
        list.push({
          key: "questionnaire",
          name: "问卷",
          status: ips.questionnaire.status === "processed" ? "done" : "pending",
          detail: `${ips.questionnaire.questions_answered || 20}题完成 · ${ips.questionnaire.scored_dimension_count || 13}个维度`,
        })
      }
      if (ips.narrative) {
        const st = ips.narrative.status
        list.push({
          key: "narrative",
          name: "自由描述",
          status: st === "processed" ? "done" : st === "skipped" || st === "unavailable" ? "skip" : "pending",
          detail: st === "processed" ? `提取${ips.narrative.evidence_items_extracted || 0}条证据` : st === "skipped" ? "未填写" : st === "unavailable" ? "AI不可用" : "处理中",
        })
      }
      if (ips.document) {
        const st = ips.document.status
        list.push({
          key: "document",
          name: "上传材料",
          status: st === "confirmed" ? "done" : st === "skipped" ? "skip" : "pending",
          detail: st === "confirmed" ? `OCR置信度${Math.round((ips.document.ocr_confidence_avg || 0) * 100)}%` : st === "skipped" ? "未上传" : "识别中",
        })
      }
      return list
    },

    emotionEntries() {
      const scores = this.assessment.emotion_profile?.dimension_scores
      if (!scores || typeof scores !== "object" || Array.isArray(scores)) return []
      return Object.entries(scores).map(([key, score]) => ({
        key, display_name: this.dimDisplayName(key), score: Number(score),
        severity: Number(score) >= 3 ? "severe" : Number(score) >= 2 ? "moderate" : Number(score) > 0 ? "mild" : "none",
        severity_display: `${Number(score).toFixed(1)} / 4`, source: "multi_source",
      }))
    },

    physicalEntries() {
      const pp = this.assessment.physical_profile || {}
      const list = []
      for (const [key, val] of Object.entries(pp)) {
        if (key === "physical_signals" && Array.isArray(val)) {
          list.push({ key, display_name: "身体信号", value: val.join("、") })
        } else if (typeof val === "object" && val !== null) {
          list.push({
            key,
            display_name: this.dimDisplayName(key),
            score: val.score,
            severity_display: val.severity_display,
            color: this.severityColor(val.score),
            value: val.direction ? `${val.direction} ${val.severity}` : val.severity_display,
          })
        }
      }
      return list
    },
  },

  onLoad(opts) {
    this.assessmentId = opts?.assessment_id || ""
    this.isSafetyFlow = opts?.safety === "true"
    this.loadData()
  },

  methods: {
    async loadData() {
      this.loading = true
      this.loadError = ""
      try {
        const session = getSprint3Session()
        const assessment = session.assessment
        if (!assessment || assessment.assessment_id !== this.assessmentId) {
          throw new Error("未找到本次评估结果，请重新完成问卷")
        }
        this.assessment = createAssessmentFlow(assessment).assessment
        this.followUpQuestions = (assessment.follow_up_questions || []).slice(0, 4)
        if ((assessment.safety_flags || []).length > 0 || assessment.status === "blocked_safety") {
          this.isSafetyFlow = true
        }
        this.step = 4
        const destination = safetyDestination(this.assessment)
        if (destination) {
          uni.redirectTo({ url: destination })
          return
        }
      } catch (err) {
        this.loadError = err.message || "加载失败"
      } finally {
        this.loading = false
      }
    },

    plainSeverity(score) {
      const value = Number(score)
      if (!Number.isFinite(value) || value <= 0.75) return "目前不明显"
      if (value <= 1.75) return "轻度出现"
      if (value <= 2.75) return "需要关注"
      return "比较突出"
    },

    async submitSafetyVerification(resolution) {
      if (this.safetyVerificationSubmitting) return
      this.safetyVerificationSubmitting = true
      this.operationError = ""
      try {
        const result = await verifyAssessmentSafety(
          this.assessment.assessment_id,
          safetyVerificationPayload(this.assessment, resolution),
        )
        this.assessment = result.assessment
        updateSprint3Session({
          assessment: this.assessment,
          assessment_revision: this.assessment.revision,
        })
        const destination = safetyDestination(this.assessment)
        if (destination) {
          uni.redirectTo({ url: destination })
        }
      } catch (error) {
        this.operationError = safeUiError(error, "SAFETY_VERIFICATION_FAILED").message
      } finally {
        this.safetyVerificationSubmitting = false
      }
    },
    dimDisplayName(key) {
      const names = {
        tension_worry: "紧张与担忧", overthinking: "思虑反复", irritability_anger: "烦躁易怒",
        fear_unease: "不安恐惧", low_mood: "情绪低落", interest_loss: "兴趣减退",
        calm_wellbeing: "平静安稳", emotional_recovery: "情绪恢复力",
        sleep_disturbance: "睡眠困扰", unrefreshing_sleep: "睡眠不解乏",
        low_energy: "精力不足", appetite_change: "食欲变化", daily_impact: "日常影响",
      }
      return names[key] || key
    },

    severityColor(score) {
      if (score == null) return "#9C9585"
      if (score <= 0.75) return "#5A8A6B"
      if (score <= 1.75) return "#8AAF7C"
      if (score <= 2.75) return "#D4A542"
      if (score <= 3.5) return "#C8896D"
      return "#C44A3E"
    },

    sourceLabel(type) {
      const labels = { questionnaire: "问卷", narrative: "文本", document: "材料", user_follow_up: "追问", user_correction: "修正" }
      return labels[type] || type
    },

    onTapEvidence(dim) {
      uni.showToast({ title: `${dim.display_name}: ${dim.severity_display}`, icon: "none" })
    },

    onAnswerFollowUp(fuId, value) {
      this.followUpAnswers[fuId] = value
    },

    async onSubmitFollowUp() {
      const unanswered = this.followUpQuestions.filter((q) => this.followUpAnswers[q.follow_up_id] === undefined)
      if (unanswered.length) {
        uni.showToast({ title: "请回答所有追问", icon: "none" })
        return
      }

      this.operationError = ""
      uni.showLoading({ title: "更新评估..." })
      try {
        const answers = this.followUpQuestions.map((q) => ({
          follow_up_id: q.follow_up_id,
          answer: this.followUpAnswers[q.follow_up_id],
        }))
        const result = await submitFollowUpAnswers(this.assessmentId, this.assessment.revision || 1, answers)
        this.assessment = applyFollowUpRevision({ assessment: this.assessment }, result).assessment
        updateSprint3Session({ assessment: this.assessment, assessment_revision: this.assessment.revision })
        this.followUpSubmitted = true
        this.followUpQuestions = []
        uni.showToast({ title: "评估已更新", icon: "success" })
      } catch (err) {
        this.operationError = safeUiError(err, 'FOLLOW_UP_FAILED').message
      } finally {
        uni.hideLoading()
      }
    },

    async continueWorkflow() {
      const session = getSprint3Session()
      const workflow = await runWorkflow(workflowPayload({ assessment: this.assessment }, {
        session_id: session.session_id,
        user_id: session.user_id || "demo_user_001",
        document_id: session.document_id || null,
        document_text: session.document_text || null,
        narrative_text: session.narrative_text || null,
        questionnaire_answers: session.questionnaire_answers,
      }))
      updateSprint3Session({ workflow })
      return workflow
    },

    async onConfirm(level) {
      if (this.confirming) return
      this.confirmationLevel = level
      this.confirmationStatus = 'submitting'
      this.confirmationError = ''

      if (level === "fully_accurate") {
        this.confirming = true
        uni.showLoading({ title: "确认中..." })
        try {
          const result = await confirmAssessment(this.assessmentId, {
            revision: this.assessment.revision || 1,
            confirmationLevel: level,
          })
          this.assessment = result.assessment
          updateSprint3Session({ assessment: result.assessment, assessment_revision: result.revision.revision })
          await this.continueWorkflow()
          this.confirmationStatus = 'success'
          uni.showToast({ title: "已确认，进入下一步", icon: "success" })
          setTimeout(() => {
            uni.redirectTo({ url: "/pages/player-v2/player-v2" })
          }, 1500)
        } catch (err) {
          const failed = confirmationFailed({ assessment: this.assessment, correctionText: this.correctionText }, err)
          this.confirmationStatus = failed.confirmationStatus
          this.confirmationError = failed.confirmationError
          this.confirmationLevel = ""
          uni.showToast({ title: this.confirmationError, icon: "none" })
        } finally {
          this.confirming = false
          uni.hideLoading()
        }
      }
      // 部分准确 / 不准确 → 显示修正输入区，等用户提交修正
    },

    resetConfirm() {
      this.confirmationLevel = ""
      this.correctionText = ""
    },

    async submitCorrection() {
      if (!this.correctionText.trim()) {
        uni.showToast({ title: "请描述需要修正的内容", icon: "none" })
        return
      }
      this.operationError = ""
      this.confirming = true
      uni.showLoading({ title: "提交修正..." })
      try {
        const result = await confirmAssessment(this.assessmentId, {
          revision: this.assessment.revision || 1,
          confirmationLevel: this.confirmationLevel,
          corrections: [{
            field: "user_correction_note",
            from: null,
            to: this.correctionText.trim(),
          }],
        })
        this.assessment = applyCorrectionRevision({ assessment: this.assessment, correctionText: this.correctionText }, result, this.correctionText).assessment
        updateSprint3Session({
          assessment: this.assessment,
          assessment_revision: result.revision.revision,
        })
        this.confirmationLevel = ""
        this.correctionText = ""
        uni.showToast({ title: "评估已更新，请再次确认", icon: "none" })
      } catch (err) {
        this.operationError = safeUiError(err, 'CONFIRMATION_FAILED').message
      } finally {
        this.confirming = false
        uni.hideLoading()
      }
    },
  },
}
</script>

<style scoped>
.ar-eyebrow,
.ar-main-title,
.ar-body-copy,
.ar-help-copy,
.ar-confirm-copy,
.plain-state-name,
.plain-state-level,
.plain-body-text {
  display: block;
}
.ar-eyebrow { color: #8b624e; font-size: 24rpx; margin-bottom: 14rpx; }
.ar-main-title { color: #292724; font-size: 38rpx; font-weight: 700; line-height: 1.45; margin-bottom: 20rpx; }
.ar-body-copy, .ar-help-copy, .ar-confirm-copy { color: #625e57; font-size: 26rpx; line-height: 1.7; }
.verification-options { margin: 30rpx 0 18rpx; display: flex; flex-direction: column; gap: 14rpx; }
.verification-option { padding: 24rpx; border: 1rpx solid #b9c8bf; border-radius: 18rpx; background: #f6faf7; color: #355849; text-align: center; }
.plain-source-list { display: flex; flex-wrap: wrap; gap: 14rpx; }
.plain-source-chip { padding: 14rpx 20rpx; border-radius: 999rpx; background: #edf3ef; color: #456556; }
.plain-source-chip.source-skip, .plain-source-chip.source-pending { background: #f1ede4; color: #8a8377; }
.plain-state-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16rpx; }
.plain-state-card { padding: 24rpx; }
.plain-state-name { color: #2c2c2a; font-size: 27rpx; font-weight: 600; }
.plain-state-level { color: #6b776f; font-size: 23rpx; margin-top: 8rpx; }
.plain-body-card { padding: 24rpx; display: flex; flex-direction: column; gap: 10rpx; }
.plain-body-text { color: #5f625c; line-height: 1.6; }
.compact-error { margin: 18rpx 0; }
.ar-page {
  min-height: 100vh;
  background: #F7F3EB;
  position: relative;
  overflow: hidden;
}

/* 背景 */
.ink-bg-circle {
  position: fixed;
  border-radius: 50%;
  filter: blur(60rpx);
  z-index: 0;
  pointer-events: none;
}
.ink-bg-tl { width: 400rpx; height: 400rpx; top: -100rpx; left: -100rpx; background: rgba(74, 107, 92, 0.06); }
.ink-bg-br { width: 500rpx; height: 500rpx; bottom: -150rpx; right: -150rpx; background: rgba(200, 137, 109, 0.05); }
.ink-mountain { position: fixed; bottom: 0; left: 0; right: 0; height: 200rpx; background: linear-gradient(to top, rgba(74,107,92,0.03), transparent); z-index: 0; pointer-events: none; }

/* 安全横幅 */
.ar-safety-banner {
  position: relative;
  z-index: 1;
  margin: 40rpx;
  padding: 32rpx;
  background: rgba(196, 74, 62, 0.08);
  border: 1rpx solid rgba(196, 74, 62, 0.3);
  border-radius: 16rpx;
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
}
.ar-safety-icon {
  width: 48rpx; height: 48rpx;
  border-radius: 50%;
  background: #C44A3E;
  color: #FFFEFA;
  font-size: 28rpx;
  font-weight: 700;
  text-align: center;
  line-height: 48rpx;
  flex-shrink: 0;
}
.ar-safety-text {
  font-size: 26rpx;
  color: #C44A3E;
  line-height: 1.6;
  flex: 1;
}

/* 加载态 */
.ar-loading {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 200rpx;
}
.ar-loading-circle {
  width: 140rpx; height: 140rpx;
  border-radius: 50%;
  border: 4rpx solid #D9D0BD;
  border-top-color: #4A6B5C;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: ink-spin 1.5s linear infinite;
}
@keyframes ink-spin { to { transform: rotate(360deg); } }
.ar-loading-text {
  font-size: 48rpx;
  font-weight: 700;
  color: #4A6B5C;
  font-family: 'Kaiti SC', serif;
}
.ar-loading-label {
  font-size: 30rpx;
  color: #4A6B5C;
  margin-top: 32rpx;
  letter-spacing: 2rpx;
}
.ar-loading-steps {
  margin-top: 48rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.ar-step {
  display: flex;
  align-items: center;
  gap: 16rpx;
  opacity: 0.4;
  transition: all 0.3s;
}
.ar-step.step-done { opacity: 1; }
.ar-step-icon {
  width: 40rpx; height: 40rpx;
  border-radius: 50%;
  border: 2rpx solid #D9D0BD;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  color: #9C9585;
}
.ar-step.step-done .ar-step-icon {
  background: #4A6B5C;
  border-color: #4A6B5C;
  color: #FFFEFA;
}
.ar-step-text {
  font-size: 26rpx;
  color: #6B6B5C;
}

/* 错误态 */
.ar-error {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 200rpx;
}
.ar-error-circle {
  width: 120rpx; height: 120rpx;
  border-radius: 50%;
  background: #FFF8F6;
  border: 2rpx solid #E8C4B8;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ar-error-icon {
  font-size: 56rpx;
  color: #C44A3E;
  font-weight: bold;
}
.ar-error-title {
  margin-top: 32rpx;
  font-size: 34rpx;
  color: #4A6B5C;
  font-weight: 600;
  letter-spacing: 2rpx;
}
.ar-error-msg {
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #9C9585;
  text-align: center;
  padding: 0 80rpx;
}
.ar-error-btn {
  margin-top: 48rpx;
  width: 320rpx;
  height: 84rpx;
  border-radius: 42rpx;
  background: linear-gradient(135deg, #4A6B5C 0%, #5A8A6B 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.25);
}
.ar-error-btn text {
  color: #FFFEFA;
  font-size: 30rpx;
  letter-spacing: 2rpx;
}

/* 滚动区 */
.ar-scroll {
  position: relative;
  z-index: 1;
  height: 100vh;
  padding: 0 40rpx 120rpx;
}

/* 区块 */
.ar-section {
  margin-bottom: 40rpx;
}
.ar-section-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #4A6B5C;
  letter-spacing: 2rpx;
  display: block;
  margin-bottom: 20rpx;
}

/* 数据来源 */
.ar-source-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.ar-source-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: #FFFEFA;
  border-radius: 16rpx;
  padding: 20rpx 24rpx;
  border: 1rpx solid #D9D0BD;
}
.ar-source-dot {
  width: 16rpx; height: 16rpx;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-done { background: #5A8A6B; }
.dot-pending { background: #D4A542; }
.dot-skip { background: #C5BBA5; }
.ar-source-info { display: flex; flex-direction: column; }
.ar-source-name { font-size: 28rpx; font-weight: 600; color: #2C2C2A; }
.ar-source-detail { font-size: 22rpx; color: #9C9585; }

/* 摘要卡片 */
.ar-summary-card {
  padding: 40rpx 36rpx;
  position: relative;
  margin-bottom: 40rpx;
}
.ar-seal {
  position: absolute;
  top: 24rpx; right: 24rpx;
  background: #C8896D;
  color: #FFFEFA;
  font-size: 20rpx;
  font-weight: 700;
  padding: 6rpx 14rpx;
  border-radius: 6rpx;
  transform: rotate(-2deg);
}
.ar-summary-text {
  font-size: 30rpx;
  color: #2C2C2A;
  line-height: 1.8;
  display: block;
}
.ar-confidence {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-top: 24rpx;
}
.ar-confidence-label { font-size: 24rpx; color: #9C9585; }
.ar-confidence-bar {
  flex: 1;
  height: 12rpx;
  background: #E8E0CC;
  border-radius: 6rpx;
  overflow: hidden;
}
.ar-confidence-fill {
  height: 100%;
  background: linear-gradient(90deg, #6B8B7C, #4A6B5C);
  border-radius: 6rpx;
}
.ar-confidence-value { font-size: 26rpx; font-weight: 700; color: #4A6B5C; }

/* 维度列表 */
.ar-dim-list { display: flex; flex-direction: column; gap: 16rpx; }
.ar-dim-item {
  padding: 24rpx 28rpx;
}
.ar-dim-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.ar-dim-name { font-size: 28rpx; font-weight: 600; color: #2C2C2A; }
.ar-source-tag {
  font-size: 20rpx;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
}
.tag-questionnaire { background: rgba(74,107,92,0.12); color: #4A6B5C; }
.tag-narrative { background: rgba(200,137,109,0.12); color: #C8896D; }
.tag-document { background: rgba(212,165,66,0.12); color: #D4A542; }
.tag-user_follow_up { background: rgba(90,138,107,0.12); color: #5A8A6B; }
.tag-user_correction { background: rgba(196,74,62,0.12); color: #C44A3E; }
.ar-tag-text { font-size: 20rpx; }

.ar-dim-bar-wrap { display: flex; align-items: center; gap: 16rpx; }
.ar-dim-bar { flex: 1; height: 16rpx; background: #F0E9D9; border-radius: 8rpx; overflow: hidden; }
.ar-dim-fill { height: 100%; border-radius: 8rpx; transition: width 0.5s; }
.ar-dim-tier { font-size: 24rpx; font-weight: 600; min-width: 140rpx; text-align: right; }

/* 身体信号 */
.ar-physical-list { display: flex; flex-wrap: wrap; gap: 12rpx; }
.ar-physical-item {
  padding: 16rpx 24rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.ar-physical-name { font-size: 26rpx; font-weight: 600; color: #2C2C2A; }
.ar-physical-tier { font-size: 22rpx; font-weight: 600; }
.ar-physical-value { font-size: 22rpx; color: #6B6B5C; }

/* 冲突 */
.ar-conflict-card { padding: 28rpx; margin-bottom: 16rpx; }
.ar-conflict-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12rpx; }
.ar-conflict-topic { font-size: 28rpx; font-weight: 600; color: #2C2C2A; }
.ar-conflict-badge { padding: 4rpx 12rpx; border-radius: 6rpx; font-size: 20rpx; }
.cf-minor { background: rgba(212,165,66,0.15); color: #D4A542; }
.cf-moderate { background: rgba(200,137,109,0.15); color: #C8896D; }
.cf-major { background: rgba(196,74,62,0.15); color: #C44A3E; }
.ar-conflict-summary { font-size: 26rpx; color: #6B6B5C; line-height: 1.6; display: block; margin-bottom: 16rpx; }
.ar-conflict-sources { display: flex; gap: 24rpx; }
.ar-conflict-source { display: flex; flex-direction: column; }
.ar-cs-type { font-size: 20rpx; color: #9C9585; }
.ar-cs-value { font-size: 24rpx; color: #2C2C2A; font-weight: 600; }

/* 缺失信息 */
.ar-missing-card { padding: 24rpx 28rpx; margin-bottom: 12rpx; }
.ar-missing-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8rpx; }
.ar-missing-name { font-size: 28rpx; font-weight: 600; color: #2C2C2A; }
.ar-missing-badge { padding: 4rpx 12rpx; border-radius: 6rpx; font-size: 20rpx; }
.mi-critical { background: rgba(196,74,62,0.15); color: #C44A3E; }
.mi-important { background: rgba(212,165,66,0.15); color: #D4A542; }
.mi-supplementary { background: rgba(156,149,133,0.15); color: #9C9585; }
.ar-missing-reason { font-size: 24rpx; color: #9C9585; line-height: 1.5; display: block; }

/* 追问 */
.ar-followup-hint { font-size: 26rpx; color: #6B6B5C; margin-bottom: 20rpx; display: block; }
.ar-fu-card { padding: 28rpx; margin-bottom: 16rpx; }
.ar-fu-header { display: flex; align-items: center; gap: 16rpx; margin-bottom: 20rpx; }
.ar-fu-badge { width: 40rpx; height: 40rpx; border-radius: 8rpx; background: #4A6B5C; display: flex; align-items: center; justify-content: center; }
.ar-fu-badge text { color: #FFFEFA; font-size: 22rpx; font-weight: 700; }
.ar-fu-text { font-size: 28rpx; font-weight: 600; color: #2C2C2A; flex: 1; }
.ar-fu-options { display: flex; flex-wrap: wrap; gap: 12rpx; }
.ar-fu-opt {
  padding: 16rpx 24rpx;
  border-radius: 12rpx;
  border: 2rpx solid #D9D0BD;
  background: #FFFEFA;
  font-size: 26rpx;
  color: #2C2C2A;
}
.ar-fu-opt.opt-selected { border-color: #4A6B5C; background: rgba(74,107,92,0.08); color: #4A6B5C; }
.ar-fu-slider { display: flex; align-items: center; gap: 16rpx; }
.ar-fu-textarea {
  width: 100%;
  height: 120rpx;
  border: 2rpx solid #D9D0BD;
  border-radius: 12rpx;
  padding: 16rpx;
  font-size: 26rpx;
}
.ar-fu-submit {
  padding: 28rpx;
  border-radius: 32rpx;
  background: #4A6B5C;
  text-align: center;
  margin-top: 16rpx;
}
.ar-fu-submit text { color: #FFFEFA; font-size: 30rpx; font-weight: 600; }

/* 确认 */
.ar-confirm-card { padding: 40rpx 36rpx; text-align: center; }
.ar-confirm-title { font-size: 32rpx; font-weight: 600; color: #2C2C2A; display: block; margin-bottom: 32rpx; }
.ar-confirm-btns { display: flex; gap: 16rpx; }
.ar-confirm-btn {
  flex: 1;
  padding: 24rpx 12rpx;
  border-radius: 16rpx;
  border: 2rpx solid;
}
.ar-confirm-btn text { font-size: 26rpx; font-weight: 600; }
.ar-confirm-full { border-color: #4A6B5C; background: rgba(74,107,92,0.08); }
.ar-confirm-full text { color: #4A6B5C; }
.ar-confirm-partial { border-color: #D4A542; background: rgba(212,165,66,0.08); }
.ar-confirm-partial text { color: #D4A542; }
.ar-confirm-inaccurate { border-color: #C44A3E; background: rgba(196,74,62,0.08); }
.ar-confirm-inaccurate text { color: #C44A3E; }

/* 修正输入 */
.ar-correction { margin-top: 8rpx; text-align: left; }
.ar-correction-hint { font-size: 26rpx; color: #6B6862; display: block; margin-bottom: 20rpx; line-height: 1.6; }
.ar-correction-input {
  width: 100%; min-height: 180rpx; padding: 24rpx;
  background: #F7F3EB; border-radius: 20rpx; border: 1rpx solid #E8E2D5;
  font-size: 28rpx; color: #2C2A28; line-height: 1.7; box-sizing: border-box;
}
.ar-correction-btns { display: flex; gap: 16rpx; margin-top: 24rpx; }
.ar-correction-cancel {
  flex: 1; height: 80rpx; border-radius: 40rpx;
  background: #FCFAF6; border: 1rpx solid #E8E2D5;
  display: flex; align-items: center; justify-content: center;
}
.ar-correction-cancel text { font-size: 26rpx; color: #6B6862; font-weight: 500; }
.ar-correction-submit {
  flex: 2; height: 80rpx; border-radius: 40rpx;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(74,107,92,0.20);
}
.ar-correction-submit text { font-size: 26rpx; color: #F7F3EB; font-weight: 600; }

/* 证据 */
.ar-ev-item { padding: 24rpx 28rpx; margin-bottom: 12rpx; }
.ar-ev-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8rpx; }
.ar-ev-name { font-size: 28rpx; font-weight: 600; color: #2C2C2A; }
.ar-ev-quote { font-size: 24rpx; color: #6B6B5C; font-style: italic; display: block; margin-bottom: 8rpx; }
.ar-ev-ref { font-size: 20rpx; color: #9C9585; display: block; }
.ar-ev-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 8rpx; }
.ar-ev-severity { font-size: 24rpx; font-weight: 600; }
.ar-ev-confirmed { font-size: 22rpx; color: #5A8A6B; }

/* 免责声明 */
.ar-disclaimer {
  font-size: 22rpx;
  color: #C5BBA5;
  text-align: center;
  display: block;
  margin-top: 40rpx;
  line-height: 1.6;
  padding: 0 20rpx;
}

.ar-bottom-space { height: 80rpx; }
</style>
