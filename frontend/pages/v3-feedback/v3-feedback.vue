<script>
/**
 * V3.1 反馈页（feedback_v3.0，Issue #100：由必填改为选填）
 * 合同依据：backend/app/schemas/v3/feedback.py（FeedbackV3 冻结契约）
 *          frontend-read-model-contract-v3.md §13 Feedback
 *
 * - 状态变化为可选的大尺寸 2×2 卡片（much_better / slightly_better / no_change / worse）
 * - 互斥调整项由前端保证：节奏更慢/节奏更快互斥，缩短时长/延长时长互斥
 *   （后端同样校验，冲突时返回 422）
 * - continue_use 单选：yes / maybe / no
 * - liked_features 多选；comment 选填（1-500 字）
 * - 全部可选填，可一条不填直接提交，也可跳过反馈返回首页
 * - 选中态统一为朱砂印章底 + 白字 + ✓
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

// 互斥组定义（与 FeedbackV3.validate_selection_sets 一致）
const MUTEX_GROUPS = [
  ["slower_tempo", "faster_tempo"],
  ["shorter_duration", "longer_duration"],
]

export default {
  components: { HanSideNav },
  data() {
    return {
      changeLabel: "", // 选填：much_better | slightly_better | no_change | worse
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
      return !this.submitting
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
          post_state: this.changeLabel ? { change_label: this.changeLabel } : null,
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
      // P1-3：反馈完成后回到 V3 入口页，不再进入 Sprint 3 旧首页
      uni.reLaunch({ url: "/pages/entry/entry" })
    },
  },
}
</script>

<template>
  <view class="page han-page side-nav-page">
    <han-side-nav current="listen" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">谢</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">反馈 · 选填</text>
            <text class="page-title han-title-brush revealed">听完后，感觉怎么样？</text>
          </view>
        </view>
        <text class="page-subtitle">可以告诉我们你的感受，也可以直接结束。反馈为选填。</text>
      </view>

      <!-- 提交成功 -->
      <view v-if="submitted" class="han-card done-card ink-fade-up">
        <view class="done-seal">
          <text class="done-seal-text">谢</text>
        </view>
        <text class="done-title">反馈已提交</text>
        <text class="done-sub">感谢你的反馈，我们会让它越来越适合你。</text>
        <view class="han-btn han-btn-primary btn-primary" @click="goHome">
          <text class="btn-primary-text">返回首页</text>
        </view>
      </view>

      <view v-else>
        <!-- 1. 状态变化（选填，2×2 大卡片） -->
        <view class="han-card section-card ink-fade-up">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">感</text></view>
            <text class="section-title">听完这段音乐，你的状态变化是？</text>
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
        <view class="han-card section-card ink-fade-up">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">续</text></view>
            <text class="section-title">之后还会继续使用吗？</text>
          </view>
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
        <view class="han-card section-card ink-fade-up">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">好</text></view>
            <text class="section-title">这次音乐中，你比较喜欢哪些方面？（可多选）</text>
          </view>
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
        <view class="han-card section-card ink-fade-up">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">调</text></view>
            <text class="section-title">希望下次调整哪些地方？（可多选）</text>
          </view>
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
        <view class="han-card section-card ink-fade-up">
          <view class="section-head">
            <view class="section-seal"><text class="section-seal-text">言</text></view>
            <text class="section-title">还有什么想说的？（选填）</text>
          </view>
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

        <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': !canSubmit }" @click="submit">
          <text class="btn-primary-text">{{ submitting ? "正在提交…" : "提交反馈" }}</text>
        </view>
        <view class="btn-link" @click="goHome">
          <text class="btn-link-text">暂不反馈，返回首页</text>
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
.done-card {
  border-radius: var(--radius-lg);
  padding: 80rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.done-seal {
  width: 120rpx;
  height: 120rpx;
  background: var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
  box-shadow: var(--shadow-seal);
}
.done-seal-text {
  font-size: 56rpx;
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-weight: 700;
}
.done-title {
  font-size: 36rpx;
  font-weight: 600;
  color: var(--ink-700);
  margin-bottom: 14rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.done-sub {
  font-size: 26rpx;
  color: var(--text-muted);
  margin-bottom: 56rpx;
}
.done-card .btn-primary {
  width: 100%;
  margin-top: 0;
}
</style>
