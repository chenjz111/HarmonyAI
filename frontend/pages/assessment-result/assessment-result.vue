<template>
  <view class="ar-page">
    <!-- 水墨背景 -->
    <view class="ink-bg-circle ink-bg-tl"></view>
    <view class="ink-bg-circle ink-bg-br"></view>
    <view class="ink-mountain"></view>

    <!-- 安全流程提示 -->
    <view v-if="isSafetyFlow" class="ar-safety-banner">
      <text class="ar-safety-icon">!</text>
      <text class="ar-safety-text">检测到安全风险。音乐调养仅作为辅助舒缓支持，不能替代专业帮助；如你感到无法自控或身体情况紧急，请立即联系信任的人或拨打心理援助热线。</text>
    </view>

    <!-- 加载态 -->
    <view v-if="loading" class="ar-loading">
      <view class="ar-loading-circle">
        <text class="ar-loading-text">和</text>
      </view>
      <text class="ar-loading-label">正在分析你的状态...</text>
      <view class="ar-loading-steps">
        <view class="ar-step" :class="{ 'step-done': step >= 1 }">
          <text class="ar-step-icon">{{ step >= 1 ? '✓' : '○' }}</text>
          <text class="ar-step-text">问卷评分</text>
        </view>
        <view class="ar-step" :class="{ 'step-done': step >= 2 }">
          <text class="ar-step-icon">{{ step >= 2 ? '✓' : '○' }}</text>
          <text class="ar-step-text">文本分析</text>
        </view>
        <view class="ar-step" :class="{ 'step-done': step >= 3 }">
          <text class="ar-step-icon">{{ step >= 3 ? '✓' : '○' }}</text>
          <text class="ar-step-text">材料分析</text>
        </view>
        <view class="ar-step" :class="{ 'step-done': step >= 4 }">
          <text class="ar-step-icon">{{ step >= 4 ? '✓' : '○' }}</text>
          <text class="ar-step-text">多源融合</text>
        </view>
      </view>
    </view>

    <!-- 错误态 -->
    <view v-else-if="loadError" class="ar-error">
      <view class="ar-error-circle">
        <text class="ar-error-icon">!</text>
      </view>
      <text class="ar-error-title">分析失败</text>
      <text class="ar-error-msg">{{ loadError }}</text>
      <view class="ar-error-btn" @tap="loadData">
        <text>重新尝试</text>
      </view>
    </view>

    <!-- 结果内容 -->
    <scroll-view v-if="!loading" scroll-y class="ar-scroll">
      <view v-if="operationError" class="ar-error">
        <text class="ar-error-title">操作未完成</text>
        <text class="ar-error-msg">{{ operationError }}</text>
      </view>
      <!-- 数据来源状态 -->
      <view class="ar-section">
        <text class="ar-section-title">数据来源</text>
        <view class="ar-source-list">
          <view class="ar-source-item" v-for="src in sourceList" :key="src.key">
            <view class="ar-source-dot" :class="'dot-' + src.status"></view>
            <view class="ar-source-info">
              <text class="ar-source-name">{{ src.name }}</text>
              <text class="ar-source-detail">{{ src.detail }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 状态摘要 -->
      <view v-if="assessment.assessment_summary" class="ar-card ink-card ar-summary-card">
        <view class="ar-seal">辨证</view>
        <text class="ar-summary-text">{{ assessment.assessment_summary }}</text>
        <view v-if="assessment.confidence != null" class="ar-confidence">
          <text class="ar-confidence-label">可信度</text>
          <view class="ar-confidence-bar">
            <view class="ar-confidence-fill" :style="{ width: (assessment.confidence * 100) + '%' }"></view>
          </view>
          <text class="ar-confidence-value">{{ Math.round(assessment.confidence * 100) }}%</text>
        </view>
      </view>

      <!-- 情绪维度 -->
      <view v-if="emotionEntries.length" class="ar-section">
        <text class="ar-section-title">情绪维度</text>
        <view class="ar-dim-list">
          <view v-for="dim in emotionEntries" :key="dim.key" class="ar-dim-item ink-card" @tap="onTapEvidence(dim)">
            <view class="ar-dim-header">
              <text class="ar-dim-name">{{ dim.display_name }}</text>
              <view class="ar-source-tag" :class="'tag-' + dim.source">
                <text class="ar-tag-text">{{ sourceLabel(dim.source) }}</text>
              </view>
            </view>
            <view class="ar-dim-bar-wrap">
              <view class="ar-dim-bar">
                <view class="ar-dim-fill" :style="{ width: (dim.score / 4 * 100) + '%', background: severityColor(dim.score) }"></view>
              </view>
              <text class="ar-dim-tier" :style="{ color: severityColor(dim.score) }">{{ dim.severity_display }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 身体信号 -->
      <view v-if="physicalEntries.length" class="ar-section">
        <text class="ar-section-title">身体信号</text>
        <view class="ar-physical-list">
          <view v-for="phys in physicalEntries" :key="phys.key" class="ar-physical-item ink-card">
            <text class="ar-physical-name">{{ phys.display_name }}</text>
            <text v-if="phys.severity_display" class="ar-physical-tier" :style="{ color: phys.color }">{{ phys.severity_display }}</text>
            <text v-else class="ar-physical-value">{{ phys.value }}</text>
          </view>
        </view>
      </view>

      <!-- 冲突信息 -->
      <view v-if="assessment.conflicts && assessment.conflicts.length" class="ar-section">
        <text class="ar-section-title">冲突信息</text>
        <view v-for="cf in assessment.conflicts" :key="cf.conflict_id" class="ar-conflict-card ink-card">
          <view class="ar-conflict-header">
            <text class="ar-conflict-topic">{{ cf.display_topic }}</text>
            <view class="ar-conflict-badge" :class="'cf-' + cf.severity">
              <text>{{ cf.severity }}</text>
            </view>
          </view>
          <text class="ar-conflict-summary">{{ cf.summary }}</text>
          <view class="ar-conflict-sources">
            <view v-for="(s, si) in cf.sources" :key="si" class="ar-conflict-source">
              <text class="ar-cs-type">{{ sourceLabel(s.source_type) }}</text>
              <text class="ar-cs-value">{{ s.label }} ({{ s.value }})</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 缺失信息 -->
      <view v-if="assessment.missing_information && assessment.missing_information.length" class="ar-section">
        <text class="ar-section-title">缺失信息</text>
        <view v-for="mi in assessment.missing_information" :key="mi.field" class="ar-missing-card ink-card">
          <view class="ar-missing-header">
            <text class="ar-missing-name">{{ mi.display_name }}</text>
            <view class="ar-missing-badge" :class="'mi-' + mi.severity">
              <text>{{ mi.severity }}</text>
            </view>
          </view>
          <text class="ar-missing-reason">{{ mi.reason }}</text>
        </view>
      </view>

      <!-- 追问交互 -->
      <view v-if="followUpQuestions.length && !followUpSubmitted" class="ar-section">
        <text class="ar-section-title">补充追问</text>
        <text class="ar-followup-hint">为了更好地理解你，请回答以下问题：</text>
        <view v-for="(fu, fi) in followUpQuestions" :key="fu.follow_up_id" class="ar-fu-card ink-card">
          <view class="ar-fu-header">
            <view class="ar-fu-badge"><text>{{ fi + 1 }}</text></view>
            <text class="ar-fu-text">{{ fu.text }}</text>
          </view>
          <!-- single_choice -->
          <view v-if="fu.type === 'single_choice'" class="ar-fu-options">
            <view
              v-for="opt in fu.options"
              :key="opt"
              class="ar-fu-opt"
              :class="{ 'opt-selected': followUpAnswers[fu.follow_up_id] === opt }"
              @tap="onAnswerFollowUp(fu.follow_up_id, opt)"
            >
              <text>{{ opt }}</text>
            </view>
          </view>
          <!-- scale_0_10 -->
          <view v-else-if="fu.type === 'scale_0_10'" class="ar-fu-slider">
            <slider :min="0" :max="10" :step="1" activeColor="#4A6B5C" backgroundColor="#E8E0CC" block-color="#4A6B5C" block-size="28" @change="onAnswerFollowUp(fu.follow_up_id, $event.detail.value)" />
            <text class="ar-fu-slider-val">{{ followUpAnswers[fu.follow_up_id] !== undefined ? followUpAnswers[fu.follow_up_id] : 0 }}</text>
          </view>
          <!-- text -->
          <textarea v-else class="ar-fu-textarea" placeholder="请输入..." v-model="followUpAnswers[fu.follow_up_id]" />
        </view>
        <view class="ar-fu-submit" @tap="onSubmitFollowUp">
          <text>提交追问</text>
        </view>
      </view>

      <!-- 确认交互 -->
      <view v-if="!followUpQuestions.length || followUpSubmitted" class="ar-section">
        <view class="ar-confirm-card ink-card">
          <text class="ar-confirm-title">以下评估结果是否准确？</text>
          <view v-if="confirmationStatus === 'error'" class="ar-error">
            <text class="ar-error-title">确认失败</text>
            <text class="ar-error-msg">{{ confirmationError }}</text>
          </view>
          <view v-if="!confirmationLevel" class="ar-confirm-btns">
            <view class="ar-confirm-btn ar-confirm-full" @tap="onConfirm('fully_accurate')">
              <text>完全准确</text>
            </view>
            <view class="ar-confirm-btn ar-confirm-partial" @tap="onConfirm('partially_accurate')">
              <text>部分准确</text>
            </view>
            <view class="ar-confirm-btn ar-confirm-inaccurate" @tap="onConfirm('inaccurate')">
              <text>不准确</text>
            </view>
          </view>
          <!-- 修正输入 -->
          <view v-else-if="confirmationLevel !== 'fully_accurate'" class="ar-correction">
            <text class="ar-correction-hint">请告诉我们哪里不准确，或直接修改：</text>
            <textarea
              class="ar-correction-input"
              v-model="correctionText"
              placeholder="例如：紧张描述偏高，实际主要是睡眠问题..."
              maxlength="300"
            />
            <view class="ar-correction-btns">
              <view class="ar-correction-cancel" @tap="resetConfirm">
                <text>返回</text>
              </view>
              <view class="ar-correction-submit" @tap="submitCorrection">
                <text>提交修正</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 证据列表 -->
      <view v-if="assessment.evidence_items && assessment.evidence_items.length" class="ar-section">
        <text class="ar-section-title">证据来源</text>
        <view v-for="ev in assessment.evidence_items" :key="ev.evidence_id" class="ar-ev-item ink-card">
          <view class="ar-ev-header">
            <text class="ar-ev-name">{{ ev.display_name }}</text>
            <view class="ar-source-tag" :class="'tag-' + ev.source_type">
              <text class="ar-tag-text">{{ sourceLabel(ev.source_type) }}</text>
            </view>
          </view>
          <text v-if="ev.quote" class="ar-ev-quote">"{{ ev.quote }}"</text>
          <text class="ar-ev-ref">{{ ev.source_ref }}</text>
          <view class="ar-ev-meta">
            <text class="ar-ev-severity" :style="{ color: severityColor(ev.value) }">{{ ev.severity_display }}</text>
            <text v-if="ev.confirmed" class="ar-ev-confirmed">✓ 已确认</text>
          </view>
        </view>
      </view>

      <!-- 免责声明 -->
      <text class="ar-disclaimer">{{ assessment.disclaimer || "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。" }}</text>

      <!-- 底部留白 -->
      <view class="ar-bottom-space"></view>
    </scroll-view>
  </view>
</template>

<script>
import { submitFollowUpAnswers, confirmAssessment, runWorkflow } from "@/common/api-v2.js"
import { getSprint3Session, updateSprint3Session } from "@/common/sprint3-session.js"
import { safeUiError } from "@/common/safe-ui-error.js"
import { createAssessmentFlow, applyFollowUpRevision, applyCorrectionRevision, workflowPayload, confirmationFailed } from "@/common/assessment-page-flow.js"

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
    }
  },

  computed: {
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
      } catch (err) {
        this.loadError = err.message || "加载失败"
      } finally {
        this.loading = false
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
