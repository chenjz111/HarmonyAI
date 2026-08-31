<script>
/**
 * V3 反馈页（feedback_v3.0）
 * 合同依据：backend/app/schemas/v3/feedback.py（FeedbackV3 冻结契约）
 *          frontend-read-model-contract-v3.md §13 Feedback
 *
 * - 状态变化为必填的大尺寸 2×2 卡片（much_better / slightly_better / no_change / worse）
 * - 互斥调整项由前端保证：节奏更慢/节奏更快互斥，缩短时长/延长时长互斥
 *   （后端同样校验，冲突时返回 422）
 * - continue_use 单选：yes / maybe / no
 * - liked_features 多选；comment 选填（1-500 字）
 * - 选中态统一为深绿色底 + 白字 + ✓
 */
import { apiV3 } from "../../common/api-v3.js"

// 互斥组定义（与 FeedbackV3.validate_selection_sets 一致）
const MUTEX_GROUPS = [
  ["slower_tempo", "faster_tempo"],
  ["shorter_duration", "longer_duration"],
]

export default {
  data() {
    return {
      changeLabel: "", // 必填：much_better | slightly_better | no_change | worse
      changeOptions: [
        { value: "much_better", label: "明显好转" },
        { value: "slightly_better", label: "略有好转" },
        { value: "no_change", label: "没有变化" },
        { value: "worse", label: "有些加重" },
      ],
      continueUse: "", // yes | maybe | no（选填）
      continueOptions: [
        { value: "yes", label: "会继续使用" },
        { value: "maybe", label: "再看一看" },
        { value: "no", label: "暂时不会" },
      ],
      likedFeatures: [], // 多选
      likedOptions: [
        { value: "help_sleep", label: "帮助入睡" },
        { value: "relax_body", label: "放松身体" },
        { value: "calm_mind", label: "让心静下来" },
        { value: "melody", label: "旋律好听" },
        { value: "instrument", label: "喜欢乐器音色" },
      ],
      adjustments: [], // 互斥多选
      adjustmentOptions: [
        { value: "slower_tempo", label: "节奏更慢" },
        { value: "faster_tempo", label: "节奏更快" },
        { value: "change_instruments", label: "换一种乐器" },
        { value: "adjust_volume", label: "调整音量" },
        { value: "adjust_ambient", label: "调整环境氛围" },
        { value: "shorter_duration", label: "缩短时长" },
        { value: "longer_duration", label: "延长时长" },
      ],
      comment: "",
      submitting: false,
      submitted: false,
      submitError: "",
    }
  },
  computed: {
    canSubmit() {
      return !!this.changeLabel && !this.submitting
    },
  },
  methods: {
    pickChange(value) {
      this.changeLabel = this.changeLabel === value ? "" : value
    },
    pickContinue(value) {
      this.continueUse = this.continueUse === value ? "" : value
    },
    toggleLiked(value) {
      const idx = this.likedFeatures.indexOf(value)
      if (idx === -1) {
        this.likedFeatures.push(value)
      } else {
        this.likedFeatures.splice(idx, 1)
      }
    },
    // 调整项多选：同组互斥（选一个自动取消同组另一个）
    toggleAdjust(value) {
      const idx = this.adjustments.indexOf(value)
      if (idx !== -1) {
        this.adjustments.splice(idx, 1)
        return
      }
      const group = MUTEX_GROUPS.find((g) => g.indexOf(value) !== -1)
      if (group) {
        const conflict = group.find((v) => v !== value && this.adjustments.indexOf(v) !== -1)
        if (conflict !== undefined) {
          this.adjustments.splice(this.adjustments.indexOf(conflict), 1)
        }
      }
      this.adjustments.push(value)
    },
    async submit() {
      if (!this.canSubmit) return
      this.submitting = true
      this.submitError = ""
      try {
        await apiV3.submitFeedback({
          post_state: { change_label: this.changeLabel },
          continue_use: this.continueUse || undefined,
          favorite: null,
          liked_features: this.likedFeatures.slice(),
          adjustment_preferences: this.adjustments.slice(),
          comment: (this.comment || "").trim() || undefined,
        })
        this.submitted = true
      } catch (e) {
        this.submitError = e.message || "提交失败，请重试"
      } finally {
        this.submitting = false
      }
    },
    goHome() {
      uni.reLaunch({ url: "/pages/index/index" })
    },
  },
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">最后一步 · 反馈</text>
      <text class="page-title">听完后，感觉怎么样？</text>
      <text class="page-subtitle">你的反馈会帮助我们调整后续的音乐，让它更适合你。</text>
    </view>

    <!-- 提交成功 -->
    <view v-if="submitted" class="done-card">
      <view class="done-icon"><text class="done-icon-text">✓</text></view>
      <text class="done-title">反馈已提交</text>
      <text class="done-sub">感谢你的反馈，我们会让它越来越适合你。</text>
      <view class="btn-primary" @click="goHome">
        <text class="btn-primary-text">返回首页</text>
      </view>
    </view>

    <view v-else>
      <!-- 1. 状态变化（必填，2×2 大卡片） -->
      <view class="section-card">
        <view class="section-head">
          <text class="section-title">听完这段音乐，你的状态变化是？</text>
          <text class="section-required">必填</text>
        </view>
        <view class="change-grid">
          <view
            v-for="opt in changeOptions"
            :key="opt.value"
            class="change-card"
            :class="{ 'change-card-active': changeLabel === opt.value }"
            @click="pickChange(opt.value)"
          >
            <text v-if="changeLabel === opt.value" class="change-check">✓</text>
            <text class="change-label" :class="{ 'change-label-active': changeLabel === opt.value }">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 2. 是否继续使用（单选） -->
      <view class="section-card">
        <text class="section-title">之后还会继续使用吗？</text>
        <view class="radio-row">
          <view
            v-for="opt in continueOptions"
            :key="opt.value"
            class="radio-chip"
            :class="{ 'radio-chip-active': continueUse === opt.value }"
            @click="pickContinue(opt.value)"
          >
            <text class="radio-chip-text" :class="{ 'radio-chip-text-active': continueUse === opt.value }">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 3. 喜欢的方面（多选） -->
      <view class="section-card">
        <text class="section-title">这次音乐中，你比较喜欢哪些方面？（可多选）</text>
        <view class="tag-cloud">
          <view
            v-for="opt in likedOptions"
            :key="opt.value"
            class="tag-chip"
            :class="{ 'tag-chip-active': likedFeatures.indexOf(opt.value) !== -1 }"
            @click="toggleLiked(opt.value)"
          >
            <text class="tag-chip-text" :class="{ 'tag-chip-text-active': likedFeatures.indexOf(opt.value) !== -1 }">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 4. 希望调整的地方（互斥多选） -->
      <view class="section-card">
        <text class="section-title">希望下次调整哪些地方？（可多选）</text>
        <text class="section-hint">节奏与时长各只能选一个方向</text>
        <view class="tag-cloud">
          <view
            v-for="opt in adjustmentOptions"
            :key="opt.value"
            class="tag-chip"
            :class="{ 'tag-chip-active': adjustments.indexOf(opt.value) !== -1 }"
            @click="toggleAdjust(opt.value)"
          >
            <text class="tag-chip-text" :class="{ 'tag-chip-text-active': adjustments.indexOf(opt.value) !== -1 }">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 5. 补充说明（选填） -->
      <view class="section-card">
        <text class="section-title">还有什么想说的？（选填）</text>
        <textarea
          class="comment-textarea"
          v-model="comment"
          :maxlength="500"
          placeholder="例如：希望晚上睡前听，节奏再舒缓一点。"
        />
        <view class="comment-count"><text class="comment-count-text">{{ (comment || '').length }} / 500</text></view>
      </view>

      <view v-if="submitError" class="error-row">
        <text class="error-text">{{ submitError }}</text>
      </view>

      <view class="btn-primary" :class="{ 'btn-disabled': !canSubmit }" @click="submit">
        <text class="btn-primary-text">{{ submitting ? "正在提交…" : "提交反馈" }}</text>
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
.page-subtitle { display: block; font-size: 26rpx; color: #7a8078; line-height: 1.6; }
.section-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 36rpx 32rpx;
  margin-bottom: 28rpx;
}
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 28rpx; }
.section-title { font-size: 30rpx; font-weight: 500; color: #2f3d35; line-height: 1.5; }
.section-required {
  font-size: 20rpx;
  color: #b0574f;
  border: 2rpx solid #e3c4c0;
  border-radius: 8rpx;
  padding: 4rpx 12rpx;
  flex-shrink: 0;
  margin-left: 16rpx;
}
.section-hint { display: block; font-size: 22rpx; color: #b3ac9c; margin-bottom: 24rpx; }
.section-card .section-title:not(:last-child) { margin-bottom: 28rpx; }
/* 2×2 状态变化大卡片 */
.change-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.change-card {
  width: calc(50% - 10rpx);
  min-height: 160rpx;
  background: #f6f3ea;
  border: 2rpx solid #e8e2d4;
  border-radius: 20rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 24rpx 16rpx;
  position: relative;
}
.change-card-active {
  background: #2f5d43;
  border-color: #2f5d43;
}
.change-check {
  position: absolute;
  top: 14rpx;
  right: 18rpx;
  font-size: 28rpx;
  color: #fff;
  font-weight: 600;
}
.change-label { font-size: 30rpx; color: #2f3d35; font-weight: 500; }
.change-label-active { color: #fff; }
/* 单选 chips */
.radio-row { display: flex; flex-wrap: wrap; gap: 20rpx; }
.radio-chip {
  background: #f6f3ea;
  border: 2rpx solid #e8e2d4;
  border-radius: 44rpx;
  padding: 18rpx 36rpx;
}
.radio-chip-active {
  background: #2f5d43;
  border-color: #2f5d43;
}
.radio-chip-text { font-size: 27rpx; color: #2f3d35; }
.radio-chip-text-active { color: #fff; }
/* 多选 chips */
.tag-cloud { display: flex; flex-wrap: wrap; gap: 18rpx; }
.tag-chip {
  background: #f6f3ea;
  border: 2rpx solid #e8e2d4;
  border-radius: 44rpx;
  padding: 16rpx 32rpx;
}
.tag-chip-active {
  background: #2f5d43;
  border-color: #2f5d43;
}
.tag-chip-text { font-size: 26rpx; color: #2f3d35; }
.tag-chip-text-active { color: #fff; }
/* 补充说明 */
.comment-textarea {
  width: 100%;
  min-height: 200rpx;
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 26rpx;
  font-size: 28rpx;
  color: #2f3d35;
  line-height: 1.7;
  box-sizing: border-box;
}
.comment-count { display: flex; justify-content: flex-end; margin-top: 12rpx; }
.comment-count-text { font-size: 22rpx; color: #b3ac9c; }
/* 提交 */
.btn-primary {
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 26rpx 0;
  display: flex;
  justify-content: center;
  margin-top: 12rpx;
}
.btn-primary-text { color: #fff; font-size: 30rpx; }
.btn-disabled { opacity: 0.5; }
.error-row { display: flex; justify-content: center; margin-bottom: 20rpx; }
.error-text { font-size: 26rpx; color: #b0574f; }
/* 提交成功 */
.done-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 80rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.done-icon {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: #2f5d43;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
}
.done-icon-text { font-size: 56rpx; color: #fff; font-weight: 600; }
.done-title { font-size: 36rpx; font-weight: 600; color: #2f3d35; margin-bottom: 14rpx; }
.done-sub { font-size: 26rpx; color: #9c9585; margin-bottom: 56rpx; }
.done-card .btn-primary { width: 100%; margin-top: 0; }
</style>
