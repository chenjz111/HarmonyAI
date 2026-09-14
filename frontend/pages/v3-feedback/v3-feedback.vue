<script>
/**
 * V3.1 反馈页（feedback_v3.0，Issue #100：由必填改为选填）
 * 合同依据：backend/app/schemas/v3/feedback.py（FeedbackV3 冻结契约）
 *          frontend-read-model-contract-v3.md §13 Feedback
 *
 * - 状态变化与继续使用为单选插图卡片
 * - 喜欢的方面与下次调整为多选插图卡片
 * - 视觉调整项通过 ADJUSTMENT_PAYLOAD_MAP 映射为后端冻结枚举
 * - continue_use 单选：yes / maybe / no
 * - liked_features 多选；comment 选填（1-200 字，页面限制更严格）
 * - 全部可选填，可一条不填直接提交，也可跳过反馈返回首页
 * - 选中态统一为青绿色边框、浅绿色底与 ✓
 *
 * 视觉：共享水墨山水背景 + 宣纸卡片 + 青绿色主按钮
 */
import { apiV3 } from "../../common/api-v3.js"

const ADJUSTMENT_PAYLOAD_MAP = {
  slower_tempo: "slower_tempo",
  quieter_ambience: "adjust_ambient",
  more_natural_sound: "adjust_ambient",
  clearer_melody: "change_instruments",
}

export default {
  data() {
    return {
      changeLabel: "", // 选填：much_better | slightly_better | no_change | worse
      changeOptions: [
        { value: "much_better", label: "明显好转", subtitle: "感觉轻松了很多", icon: "/static/v31-feedback/feedback-1-1.png" },
        { value: "slightly_better", label: "略有好转", subtitle: "有一些改善", icon: "/static/v31-feedback/feedback-1-2.png" },
        { value: "no_change", label: "没有变化", subtitle: "和之前差不多", icon: "/static/v31-feedback/feedback-1-3.png" },
        { value: "worse", label: "有些不适", subtitle: "感觉不太舒服", icon: "/static/v31-feedback/feedback-1-4.png" },
      ],
      continueUse: "", // yes | maybe | no（选填）
      continueOptions: [
        { value: "yes", label: "会继续使用", subtitle: "期待下一次", icon: "/static/v31-feedback/feedback-2-1.png" },
        { value: "maybe", label: "再看看", subtitle: "视情况而定", icon: "/static/v31-feedback/feedback-2-2.png" },
        { value: "no", label: "暂时不会", subtitle: "先休息一下", icon: "/static/v31-feedback/feedback-2-3.png" },
      ],
      likedFeatures: [], // 多选
      likedOptions: [
        { value: "melody", label: "旋律", subtitle: "旋律动听", icon: "/static/v31-feedback/feedback-3-1.png" },
        { value: "relax_body", label: "放松身体", subtitle: "缓解紧张", icon: "/static/v31-feedback/feedback-3-2.png" },
        { value: "calm_mind", label: "让我静下来", subtitle: "平静心情", icon: "/static/v31-feedback/feedback-3-3.png" },
        { value: "instrument", label: "乐器音色", subtitle: "喜欢这种音色", icon: "/static/v31-feedback/feedback-3-4.png" },
        { value: "natural_sound", label: "自然声音", subtitle: "自然、舒适", icon: "/static/v31-feedback/feedback-3-5.png" },
      ],
      adjustments: [], // 互斥多选
      adjustmentOptions: [
        { value: "slower_tempo", label: "节奏再慢一点", subtitle: "更舒缓放松", icon: "/static/v31-feedback/feedback-4-1.png" },
        { value: "quieter_ambience", label: "氛围再安静一点", subtitle: "减少刺激感", icon: "/static/v31-feedback/feedback-4-2.png" },
        { value: "more_natural_sound", label: "自然声音更多一点", subtitle: "更多自然元素", icon: "/static/v31-feedback/feedback-4-3.png" },
        { value: "clearer_melody", label: "旋律更明显一点", subtitle: "旋律更加突出", icon: "/static/v31-feedback/feedback-4-4.png" },
      ],
      comment: "",
      submitting: false,
      submitted: false,
      submitError: "",
    }
  },
  computed: {
    canSubmit() {
      return !this.submitting
    },
  },
  methods: {
    back() {
      uni.navigateBack()
    },
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
    toggleAdjust(value) {
      const idx = this.adjustments.indexOf(value)
      if (idx !== -1) {
        this.adjustments.splice(idx, 1)
        return
      }
      this.adjustments.push(value)
    },
    async submit() {
      if (!this.canSubmit) return
      this.submitting = true
      this.submitError = ""
      try {
        await apiV3.submitFeedback({
          post_state: this.changeLabel ? { change_label: this.changeLabel } : null,
          continue_use: this.continueUse || undefined,
          favorite: null,
          liked_features: this.likedFeatures.slice(),
          adjustment_preferences: [...new Set(this.adjustments.map(value => ADJUSTMENT_PAYLOAD_MAP[value]).filter(Boolean))],
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
      // P1-3：反馈完成后回到 V3 入口页，不再进入 Sprint 3 旧首页
      uni.reLaunch({ url: "/pages/entry/entry" })
    },
  },
}
</script>

<template>
  <view class="feedback-page v31-scroll-page" :class="{ 'feedback-page--success': submitted }">
    <view class="feedback-container" :class="{ 'feedback-container--success': submitted }">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回" @click="back"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
        <view class="hero-slogan"><text>五音和鸣</text><text>心自安宁</text><view class="hero-seal"><text>和</text><text>谐</text></view></view>
      </view>

      <view v-if="!submitted" class="feedback-hero ink-fade-in">
        <text class="page-title">聆听反馈</text>
        <text class="page-subtitle">花一点时间告诉我们的感受，</text>
        <text class="page-subtitle">你的反馈会帮助 HarmonyAI 更懂你。</text>
      </view>

      <!-- 提交成功 -->
      <view v-if="submitted" class="feedback-success ink-fade-up">
        <view class="feedback-success-ring" aria-hidden="true">
          <view class="feedback-success-ring-inner">
            <image class="feedback-success-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
            <view class="feedback-success-ripples">
              <view class="feedback-success-ripple feedback-success-ripple--one" />
              <view class="feedback-success-ripple feedback-success-ripple--two" />
              <view class="feedback-success-ripple feedback-success-ripple--three" />
            </view>
          </view>
        </view>
        <text class="done-title">反馈已提交</text>
        <view class="feedback-success-divider" aria-hidden="true">
          <view class="feedback-success-divider-line" />
          <view class="feedback-success-divider-dot" />
          <image class="feedback-success-divider-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
          <view class="feedback-success-divider-dot" />
          <view class="feedback-success-divider-line" />
        </view>
        <view class="done-sub">
          <text>感谢你的反馈，</text>
          <text>你会越来越好的。</text>
        </view>
        <view class="feedback-success-button" role="button" aria-label="返回首页" @click="goHome">
          <text class="btn-primary-text">返回首页</text>
          <text class="feedback-success-arrow">→</text>
        </view>
      </view>

      <view v-else>
        <!-- 1. 状态变化 -->
        <view class="feedback-section-card ink-fade-up">
          <view class="feedback-section-head">
            <text class="feedback-index">1</text>
            <text class="feedback-question">听完这段音乐，你现在感觉怎么样？</text>
          </view>
          <view class="feedback-options feedback-options--4">
            <view
              v-for="opt in changeOptions"
              :key="opt.value"
              class="feedback-option"
              :class="{ 'feedback-option--active': changeLabel === opt.value }"
              @click="pickChange(opt.value)"
            >
              <text v-if="changeLabel === opt.value" class="feedback-option-selected-marker">✓</text>
              <image class="feedback-option-image" :src="opt.icon" mode="aspectFit" />
              <text class="feedback-option-label">{{ opt.label }}</text>
              <text class="feedback-option-subtitle">{{ opt.subtitle }}</text>
            </view>
          </view>
        </view>

        <!-- 2. 是否继续使用（单选） -->
        <view class="feedback-section-card ink-fade-up">
          <view class="feedback-section-head">
            <text class="feedback-index">2</text>
            <text class="feedback-question">之后还会继续使用吗？</text>
          </view>
          <view class="feedback-options feedback-options--3">
            <view
              v-for="opt in continueOptions"
              :key="opt.value"
              class="feedback-option"
              :class="{ 'feedback-option--active': continueUse === opt.value }"
              @click="pickContinue(opt.value)"
            >
              <text v-if="continueUse === opt.value" class="feedback-option-selected-marker">✓</text>
              <image class="feedback-option-image" :src="opt.icon" mode="aspectFit" />
              <text class="feedback-option-label">{{ opt.label }}</text>
              <text class="feedback-option-subtitle">{{ opt.subtitle }}</text>
            </view>
          </view>
        </view>

        <!-- 3. 喜欢的方面（多选） -->
        <view class="feedback-section-card ink-fade-up">
          <view class="feedback-section-head">
            <text class="feedback-index">3</text>
            <text class="feedback-question">这次音乐中，你比较喜欢哪些方面？</text>
            <text class="feedback-choice-note">（可多选）</text>
          </view>
          <view class="feedback-options feedback-options--5">
            <view
              v-for="opt in likedOptions"
              :key="opt.value"
              class="feedback-option"
              :class="{ 'feedback-option--active': likedFeatures.indexOf(opt.value) !== -1 }"
              @click="toggleLiked(opt.value)"
            >
              <text v-if="likedFeatures.indexOf(opt.value) !== -1" class="feedback-option-selected-marker">✓</text>
              <image class="feedback-option-image" :src="opt.icon" mode="aspectFit" />
              <text class="feedback-option-label">{{ opt.label }}</text>
              <text class="feedback-option-subtitle">{{ opt.subtitle }}</text>
            </view>
          </view>
        </view>

        <!-- 4. 希望调整的地方（互斥多选） -->
        <view class="feedback-section-card ink-fade-up">
          <view class="feedback-section-head">
            <text class="feedback-index">4</text>
            <text class="feedback-question">下次希望怎么调整？</text>
            <text class="feedback-choice-note">（可多选）</text>
          </view>
          <view class="feedback-options feedback-options--4">
            <view
              v-for="opt in adjustmentOptions"
              :key="opt.value"
              class="feedback-option"
              :class="{ 'feedback-option--active': adjustments.indexOf(opt.value) !== -1 }"
              @click="toggleAdjust(opt.value)"
            >
              <text v-if="adjustments.indexOf(opt.value) !== -1" class="feedback-option-selected-marker">✓</text>
              <image class="feedback-option-image" :src="opt.icon" mode="aspectFit" />
              <text class="feedback-option-label">{{ opt.label }}</text>
              <text class="feedback-option-subtitle">{{ opt.subtitle }}</text>
            </view>
          </view>
        </view>

        <!-- 5. 补充说明（选填） -->
        <view class="feedback-section-card comment-section ink-fade-up">
          <view class="feedback-section-head">
            <text class="feedback-index">5</text>
            <text class="feedback-question">还有什么想说的？</text>
            <text class="feedback-choice-note">（选填）</text>
          </view>
          <textarea
            class="comment-textarea"
            v-model="comment"
            :maxlength="200"
            placeholder="例如：这段音乐让我很放松，希望下次可以多一些自然的声音……"
          />
          <view class="comment-count"><text class="comment-count-text">{{ (comment || '').length }}/200</text></view>
        </view>

        <view v-if="submitError" class="error-row">
          <text class="error-text">{{ submitError }}</text>
        </view>

        <view class="submit-button" :class="{ 'btn-disabled': !canSubmit }" @click="submit">
          <text class="btn-primary-text">{{ submitting ? "正在提交…" : "提交反馈" }}</text>
        </view>
        <view class="btn-link" @click="goHome">
          <text class="btn-link-text">暂时跳过</text>
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
  line-height: 1.6;
}

/* ===== 分节卡 ===== */
.section-card {
  border-radius: var(--radius-lg);
  padding: 36rpx 32rpx;
  margin-bottom: 28rpx;
}
.section-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 28rpx;
}
.section-seal {
  min-width: 44rpx;
  height: 44rpx;
  background: var(--ink-700);
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.section-seal-text {
  color: var(--text-inverse);
  font-size: 24rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.section-title {
  font-size: 30rpx;
  font-weight: 500;
  color: var(--ink-700);
  line-height: 1.5;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.section-hint {
  display: block;
  font-size: 22rpx;
  color: var(--text-muted);
  margin-bottom: 24rpx;
}

/* ===== 2×2 状态变化大卡片（朱砂选中） ===== */
.change-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.change-card {
  width: calc(50% - 10rpx);
  min-height: 160rpx;
  background: rgba(244, 238, 219, 0.45);
  border: 2rpx solid var(--border-light);
  border-radius: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 24rpx 16rpx;
  position: relative;
  transition: all 0.2s ease;
}
.change-card-active {
  background: #2f5d43;
  border-color: #2f5d43;
  transform: rotate(-1.5deg);
  box-shadow: 0 6rpx 18rpx rgba(47, 93, 67, 0.32);
}
.change-check {
  position: absolute;
  top: 14rpx;
  right: 18rpx;
  font-size: 28rpx;
  color: #fdfbf5;
  font-weight: 600;
}
.change-label {
  font-size: 30rpx;
  color: var(--ink-700);
  font-weight: 500;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.change-label-active {
  color: #fdfbf5;
}

/* ===== 单选 chips ===== */
.radio-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.radio-chip {
  background: rgba(244, 238, 219, 0.45);
  border: 2rpx solid transparent;
  border-radius: var(--radius-seal);
  padding: 18rpx 36rpx;
  transition: all 0.2s ease;
}
.radio-chip-active {
  background: rgba(192, 57, 43, 0.06);
  border-color: var(--ink-seal);
  transform: rotate(-1.5deg);
}
.radio-chip-text {
  font-size: 27rpx;
  color: var(--ink-700);
}
.radio-chip-text-active {
  color: var(--ink-seal);
  font-weight: 500;
}

/* ===== 多选 chips ===== */
.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 18rpx;
}
.tag-chip {
  background: rgba(244, 238, 219, 0.45);
  border: 2rpx solid transparent;
  border-radius: var(--radius-seal);
  padding: 16rpx 32rpx;
  transition: all 0.2s ease;
}
.tag-chip-active {
  background: rgba(107, 124, 94, 0.1);
  border-color: var(--ink-primary);
  transform: rotate(-1.5deg);
}
.tag-chip-text {
  font-size: 26rpx;
  color: var(--ink-700);
}
.tag-chip-text-active {
  color: var(--ink-primary-dark);
  font-weight: 500;
}

/* ===== 补充说明 ===== */
.comment-textarea {
  width: 100%;
  min-height: 200rpx;
  background: rgba(244, 238, 219, 0.5);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 26rpx;
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.7;
  box-sizing: border-box;
}
.comment-count {
  display: flex;
  justify-content: flex-end;
  margin-top: 12rpx;
}
.comment-count-text {
  font-size: 22rpx;
  color: var(--text-muted);
}

/* ===== 提交 ===== */
.btn-primary {
  margin-top: 12rpx;
}
.btn-primary-text {
  color: var(--text-inverse);
  font-size: 30rpx;
}
.btn-disabled {
  opacity: 0.5;
}
.btn-link {
  display: flex;
  justify-content: center;
  padding: 24rpx 0 8rpx;
}
.btn-link-text {
  color: var(--text-muted);
  font-size: 26rpx;
  text-decoration: underline;
}
.error-row {
  display: flex;
  justify-content: center;
  margin-bottom: 20rpx;
}
.error-text {
  font-size: 26rpx;
  color: var(--ink-seal);
}

/* ===== 提交成功 ===== */
.feedback-page.feedback-page--success {
  min-height: 100vh;
  min-height: 100svh;
  overflow-x: hidden;
  background: #f7f4ea;
}
.feedback-container.feedback-container--success {
  position: relative;
  display: flex;
  min-height: 100vh;
  min-height: 100svh;
  padding-bottom: max(24px, env(safe-area-inset-bottom));
  flex-direction: column;
  overflow: hidden;
  background-color: #f7f4ea;
  background-image:
    linear-gradient(rgba(255, 252, 243, .05), rgba(255, 252, 243, .05)),
    url('/static/v31-feedback/feedback-success-background.png');
  background-repeat: no-repeat;
  background-position: center center;
  background-size: cover;
}
.feedback-success {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  min-height: 650px;
  padding: clamp(72px, 10vh, 112px) 22px 32px;
  box-sizing: border-box;
  flex: 1;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.feedback-success-ring {
  position: absolute;
  z-index: -1;
  top: clamp(24px, 4.5vh, 48px);
  left: 50%;
  width: clamp(276px, 82vw, 350px);
  height: clamp(276px, 82vw, 350px);
  border: 1px solid rgba(43, 91, 83, .13);
  border-radius: 50%;
  transform: translateX(-50%);
  box-shadow:
    0 0 0 5px rgba(43, 91, 83, .025),
    0 0 0 11px rgba(43, 91, 83, .035),
    inset 0 0 45px rgba(255, 252, 242, .58);
}
.feedback-success-ring::before,
.feedback-success-ring::after {
  position: absolute;
  content: "";
  border-radius: 50%;
  border: 1px solid rgba(43, 91, 83, .075);
}
.feedback-success-ring::before { inset: 8px -4px -6px 5px; }
.feedback-success-ring::after { inset: -5px 9px 7px -7px; }
.feedback-success-ring-inner {
  position: absolute;
  inset: 0;
  display: flex;
  padding-top: 68px;
  box-sizing: border-box;
  flex-direction: column;
  align-items: center;
}
.feedback-success-leaf {
  width: 88px;
  height: 76px;
  opacity: .9;
  filter: saturate(.72) brightness(.83);
}
.feedback-success-ripples {
  position: relative;
  width: 132px;
  height: 34px;
  margin-top: -7px;
}
.feedback-success-ripple {
  position: absolute;
  left: 50%;
  border: 2px solid rgba(193, 144, 67, .58);
  border-top-color: transparent;
  border-left-color: transparent;
  border-radius: 50%;
  transform: translateX(-50%) scaleY(.34) rotate(45deg);
}
.feedback-success-ripple--one { top: 0; width: 64px; height: 34px; }
.feedback-success-ripple--two { top: 6px; width: 104px; height: 38px; opacity: .78; }
.feedback-success-ripple--three { top: 12px; width: 132px; height: 40px; opacity: .55; }
.feedback-page--success .done-title {
  display: block;
  margin: 157px 0 0;
  color: #154f4b;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: clamp(39px, 11.2vw, 48px);
  font-weight: 500;
  letter-spacing: .14em;
  line-height: 1.2;
  text-shadow: 0 1px 0 rgba(255,255,255,.65);
}
.feedback-success-divider {
  display: flex;
  width: min(254px, 72vw);
  height: 24px;
  margin-top: 17px;
  align-items: center;
  justify-content: center;
  gap: 7px;
}
.feedback-success-divider-line {
  width: 72px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(79, 100, 88, .55));
}
.feedback-success-divider-line:last-child {
  background: linear-gradient(90deg, rgba(79, 100, 88, .55), transparent);
}
.feedback-success-divider-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(86, 103, 90, .65);
}
.feedback-success-divider-leaf {
  width: 27px;
  height: 27px;
  opacity: .78;
  filter: saturate(.6) brightness(.85);
}
.feedback-page--success .done-sub {
  display: flex;
  margin-top: 26px;
  flex-direction: column;
  color: #68706a;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: clamp(20px, 5.5vw, 24px);
  letter-spacing: .06em;
  line-height: 1.65;
  text-shadow: 0 1px 0 rgba(255,255,255,.8);
}
.feedback-success-button {
  position: relative;
  display: flex;
  width: min(310px, 86vw);
  min-height: 58px;
  margin-top: 42px;
  padding: 0 58px;
  box-sizing: border-box;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(13, 71, 65, .62);
  border-radius: 999px;
  background:
    linear-gradient(104deg, rgba(17, 73, 67, .97), rgba(40, 100, 90, .96)),
    radial-gradient(circle at 15% 20%, rgba(255,255,255,.16), transparent 38%);
  box-shadow:
    0 11px 20px rgba(31, 72, 62, .18),
    inset 0 1px 0 rgba(255,255,255,.24),
    inset 0 -2px 0 rgba(0, 42, 37, .16);
}
.feedback-success-button::before {
  position: absolute;
  inset: 4px;
  content: "";
  pointer-events: none;
  border: 1px solid rgba(255,255,255,.13);
  border-radius: inherit;
}
.feedback-page--success .btn-primary-text {
  color: #fffdf6;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 23px;
  font-weight: 500;
  letter-spacing: .12em;
}
.feedback-success-arrow {
  position: absolute;
  right: 28px;
  color: #fffdf6;
  font-size: 28px;
  font-weight: 300;
  line-height: 1;
}

/* ===== Owner V3.1 聆听反馈视觉稿 ===== */
.feedback-page { min-height:100vh; color:#0b4f51; background:#e7f3ef; }
.feedback-container {
  width:100%; max-width:430px; min-height:100vh; margin:0 auto; padding:14px 12px 34px; box-sizing:border-box;
  background-color:#fbfcf7;
  background-image:linear-gradient(rgba(255,255,252,.10),rgba(255,255,252,.10)),url('/static/v31-questionnaire/questionnaire-background-q34.png');
  background-repeat:no-repeat; background-position:center top; background-size:100% 100%;
}
.feedback-page .brand-row { display:flex; align-items:center; min-height:48px; gap:8px; }
.feedback-page .back-button { display:flex; align-items:center; justify-content:center; width:28px; height:40px; margin:0; padding:0; border:0; background:transparent; }
.feedback-page .back-button::after { border:0; }
.feedback-page .back-chevron { width:11px; height:11px; border-left:2px solid #064c50; border-bottom:2px solid #064c50; transform:rotate(45deg); }
.feedback-page .brand-leaf { width:42px; height:42px; }
.feedback-page .brand-copy { display:flex; flex-direction:column; gap:1px; }
.feedback-page .brand-name { font-size:18px; font-weight:750; line-height:1.15; }
.feedback-page .brand-tagline { font-size:10px; letter-spacing:2px; white-space:nowrap; }
.feedback-page .hero-slogan { position:relative; display:flex; flex:0 0 auto; flex-direction:column; align-items:flex-end; margin-left:auto; padding:0 17px 3px 0; color:#15575a; font-family:'KaiTi','STKaiti',serif; font-size:10px; font-weight:700; line-height:1.35; transform:rotate(-4deg); }
.feedback-page .hero-seal { position:absolute; right:0; bottom:-2px; display:flex; width:15px; height:29px; padding:2px 0; box-sizing:border-box; flex-direction:column; align-items:center; justify-content:center; border-radius:3px; background:#a92e27; line-height:1.05; }
.feedback-page .hero-seal text { color:#fff; font-size:8px; }
.feedback-hero { margin:18px 18px 20px; }
.feedback-page .page-title { display:block; margin-bottom:8px; color:#064c50; font-family:'KaiTi','STKaiti',serif; font-size:34px; font-weight:800; letter-spacing:4px; line-height:1.2; }
.feedback-page .page-subtitle { display:block; color:#18585c; font-size:15px; line-height:1.65; }
.feedback-section-card,.feedback-page .surface-card { box-sizing:border-box; margin-bottom:12px; padding:13px 9px; border:1px solid rgba(55,102,92,.10); border-radius:14px; background:rgba(255,255,252,.88); box-shadow:0 3px 10px rgba(31,72,62,.09); }
.feedback-section-head { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
.feedback-index { display:flex; align-items:center; justify-content:center; width:32px; min-width:32px; height:32px; border-radius:50%; color:#fff; background:linear-gradient(145deg,#2d756a,#205e57); font-size:17px; font-weight:650; }
.feedback-question { min-width:0; color:#104f54; font-size:17px; font-weight:700; line-height:1.4; }
.feedback-choice-note { color:#315f60; font-size:13px; line-height:1.4; }
.feedback-options { display:grid; gap:7px; }
.feedback-options--3 { grid-template-columns:repeat(3,minmax(0,1fr)); }
.feedback-options--4 { grid-template-columns:repeat(4,minmax(0,1fr)); }
.feedback-options--5 { grid-template-columns:repeat(5,minmax(0,1fr)); gap:5px; }
.feedback-option { position:relative; display:flex; min-width:0; min-height:142px; padding:9px 4px 8px; box-sizing:border-box; flex-direction:column; align-items:center; border:1px solid rgba(61,100,93,.12); border-radius:9px; background:rgba(255,255,252,.65); text-align:center; transition:border-color .18s ease,background-color .18s ease,box-shadow .18s ease; }
.feedback-option--active { border-color:#268277; background:rgba(224,243,236,.72); box-shadow:inset 0 0 0 1px rgba(38,130,119,.12),0 3px 9px rgba(31,100,89,.08); }
.feedback-option-selected-marker { position:absolute; z-index:2; top:5px; right:5px; display:flex; align-items:center; justify-content:center; width:16px; height:16px; border-radius:50%; color:#fff; background:#24786e; font-size:10px; }
.feedback-option-image { width:62px; max-width:100%; height:62px; flex-shrink:0; mix-blend-mode:multiply; }
.feedback-options--5 .feedback-option-image { width:50px; height:50px; }
.feedback-option-label { display:block; margin-top:4px; color:#104f54; font-size:14px; font-weight:700; line-height:1.35; }
.feedback-options--5 .feedback-option-label { font-size:13px; }
.feedback-option-subtitle { display:block; margin-top:2px; color:#617873; font-size:11.5px; line-height:1.35; }
.feedback-options--5 .feedback-option-subtitle { font-size:11px; }
.feedback-page .comment-textarea { width:100%; min-height:92px; padding:13px; box-sizing:border-box; border:1px solid rgba(55,102,92,.12); border-radius:9px; color:#174f54; background:rgba(255,255,252,.58); font-size:14px; line-height:1.65; }
.feedback-page .comment-count { margin-top:5px; }
.feedback-page .comment-count-text { color:#6b807d; font-size:12px; }
.submit-button { display:flex; align-items:center; justify-content:center; min-height:54px; margin:16px 52px 0; border-radius:28px; color:#fff; background:linear-gradient(105deg,#24695e,#28776a); box-shadow:0 5px 12px rgba(27,105,89,.16); }
.feedback-page .btn-primary-text { color:#fff; font-size:17px; font-weight:650; }
.feedback-page .btn-link { padding:13px 0 5px; }
.feedback-page .btn-link-text { color:#315f60; font-size:14px; text-decoration:none; }
.feedback-page .page-motto { margin-top:12px; color:#285e5b; text-align:center; font-family:'KaiTi','STKaiti',serif; font-size:13px; letter-spacing:1px; }
.feedback-page .done-card { margin-top:18px; padding:52px 24px; }
.feedback-page--success .brand-row {
  position: relative;
  z-index: 2;
  padding-top: max(0px, env(safe-area-inset-top));
}
@media (max-width:350px) {
  .feedback-container { padding-left:8px; padding-right:8px; }
  .feedback-page .hero-slogan { display:none; }
  .feedback-page--success .hero-slogan { display:flex; font-size:9px; }
  .feedback-hero { margin-left:12px; margin-right:12px; }
  .feedback-section-card { padding-left:6px; padding-right:6px; }
  .feedback-options { gap:4px; }
  .feedback-option { min-height:148px; padding-left:2px; padding-right:2px; }
  .feedback-option-image { width:54px; height:54px; }
  .feedback-options--5 .feedback-option-image { width:42px; height:42px; }
  .feedback-option-label,.feedback-options--5 .feedback-option-label { font-size:13px; }
  .feedback-option-subtitle,.feedback-options--5 .feedback-option-subtitle { font-size:11px; }
  .submit-button { margin-left:36px; margin-right:36px; }
}
@media (max-height:650px) {
  .feedback-success {
    min-height: 470px;
    padding: 28px 12px 18px;
  }
  .feedback-success-ring {
    top: 5px;
    width: 236px;
    height: 236px;
  }
  .feedback-success-ring-inner { padding-top: 42px; }
  .feedback-success-leaf { width: 68px; height: 58px; }
  .feedback-success-ripples { transform: scale(.82); }
  .feedback-page--success .done-title {
    margin-top: 123px;
    font-size: 34px;
  }
  .feedback-success-divider { margin-top: 8px; }
  .feedback-page--success .done-sub {
    margin-top: 10px;
    font-size: 18px;
    line-height: 1.48;
  }
  .feedback-success-button {
    min-height: 52px;
    margin-top: 15px;
  }
  .feedback-page--success .btn-primary-text { font-size: 20px; }
}
</style>
