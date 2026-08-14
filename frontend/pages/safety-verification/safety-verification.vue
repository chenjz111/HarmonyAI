<template>
  <view class="page">
    <view class="card">
      <text class="eyebrow">信息核验</text>
      <text class="title">这条材料信息描述的是现在的你吗？</text>
      <text class="body">材料识别到了需要关注的内容，但它可能来自历史记录、他人信息或识别误差。请你确认后，系统再决定后续服务。</text>
      <view class="options">
        <button v-for="item in options" :key="item.value" class="option" @tap="submit(item.value)">{{ item.label }}</button>
      </view>
      <text class="notice">如果你不确定，可以选择“暂时无法确认”。系统不会把不确定信息直接当作当前风险。</text>
      <text v-if="error" class="error">{{ error }}</text>
    </view>
  </view>
</template>

<script>
import { verifyAssessmentSafety } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'
import { safetyDestination, safetyVerificationPayload } from '@/common/safety-flow.js'
import { safeUiError } from '@/common/safe-ui-error.js'

export default {
  data() {
    return {
      assessment: {}, error: '', submitting: false,
      options: [
        { value: 'current', label: '是，描述的是我现在的情况' },
        { value: 'past_resolved', label: '是过去的情况，现在已经缓解' },
        { value: 'other_person', label: '这是他人的信息' },
        { value: 'ocr_error', label: '材料识别有误' },
        { value: 'uncertain', label: '暂时无法确认' },
      ],
    }
  },
  onLoad() {
    this.assessment = getSprint3Session().assessment || {}
  },
  methods: {
    async submit(resolution) {
      if (this.submitting) return
      this.submitting = true
      this.error = ''
      try {
        const result = await verifyAssessmentSafety(
          this.assessment.assessment_id,
          safetyVerificationPayload(this.assessment, resolution),
        )
        this.assessment = result.assessment
        updateSprint3Session({ assessment: this.assessment, assessment_revision: this.assessment.revision })
        const destination = safetyDestination(this.assessment)
        if (destination) {
          uni.redirectTo({ url: destination })
        } else {
          uni.redirectTo({ url: `/pages/assessment-result/assessment-result?assessment_id=${encodeURIComponent(this.assessment.assessment_id)}` })
        }
      } catch (error) {
        this.error = safeUiError(error, 'SAFETY_VERIFICATION_FAILED').message
      } finally {
        this.submitting = false
      }
    },
  },
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 48rpx 32rpx; box-sizing: border-box; background: #f7f3eb; }
.card { background: #fffdfa; border: 1rpx solid #e5ded1; border-radius: 32rpx; padding: 40rpx 32rpx; }
.eyebrow { color: #8b624e; font-size: 24rpx; display: block; margin-bottom: 16rpx; }
.title { color: #292724; font-size: 40rpx; font-weight: 700; line-height: 1.4; display: block; }
.body, .notice { color: #625e57; font-size: 27rpx; line-height: 1.75; display: block; margin-top: 22rpx; }
.options { margin-top: 32rpx; }
.option { margin: 18rpx 0; border: 1rpx solid #b9c8bf; border-radius: 22rpx; color: #355849; background: #f6faf7; font-size: 28rpx; }
.error { color: #b54838; display: block; margin-top: 24rpx; }
</style>

