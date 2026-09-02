<script>
/**
 * V3 入口页（双入口选择）
 * 合同依据：frontend-read-model-contract-v3.md §3.1 EntryReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2（最终用户流程）
 *
 * 文案严格使用 Owner Amendment 批准版本：
 *  - "我有近期就诊资料" / "我没有近期就诊资料"
 *  - 不使用旧的入口文案表述
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      entry: null,
      submitting: false,
      error: "",
    }
  },
  onLoad() {
    this.init()
  },
  methods: {
    async init() {
      this.loading = true
      this.error = ""
      try {
        await apiV3.guestAuth()
        const session = await apiV3.createSession()
        apiV3.rememberSession(session)
        this.entry = {
          page: "entry",
          session_id: session.session_id,
          title: "开始了解你最近的状态",
          description: "请选择是否有近期就诊资料。没有资料也可以通过状态问卷开始。",
          choices: [
            { id: "with_document", label: "我有近期就诊资料", desc: "可以上传近期病历、检查报告或相关就诊记录。", route: "/pages/v3-material/v3-material" },
            { id: "without_document", label: "我没有近期就诊资料", desc: "可以通过最近情况和10道状态问卷继续评估。", route: "/pages/v3-narrative/v3-narrative" },
          ],
        }
      } catch (e) {
        this.error = e.message || "加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    async choose(choice) {
      if (this.submitting) return
      this.submitting = true
      try {
        // select_mode：服务端权威保存入口选择（Amendment §4.1）
        await apiV3.selectMode(choice.id)
        uni.navigateTo({ url: choice.route })
      } catch (e) {
        uni.showToast({ title: e.message || "选择失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
  },
}
</script>

<template>
  <view class="container v3-visual-page entry-page">
    <view class="flow-shell">
    <view class="header entry-hero">
      <view class="hero-mark" aria-hidden="true">
        <view class="hero-orbit hero-orbit-one"></view>
        <view class="hero-orbit hero-orbit-two"></view>
        <view class="hero-core"></view>
      </view>
      <text class="hero-eyebrow">HarmonyAI · 个性化音乐</text>
      <text class="page-title">{{ entry ? entry.title : "开始了解你最近的状态" }}</text>
      <text class="page-subtitle">从你愿意提供的信息开始，我们会一步步整理，并生成本次音乐建议。</text>
    </view>

    <view v-if="loading" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在准备…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <text class="error-text">{{ error }}</text>
      <view class="btn-retry" @click="init"><text class="btn-retry-text">重试</text></view>
    </view>

    <view v-else class="choices">
      <text class="section-label">选择开始方式</text>
      <view
        v-for="c in entry.choices"
        :key="c.id"
        class="choice-card mode-card"
        :class="{ 'choice-disabled': submitting }"
        @click="choose(c)"
      >
        <view class="choice-icon mode-card-icon" aria-hidden="true">
          <view v-if="c.id === 'with_document'" class="document-symbol">
            <view class="document-line document-line-long"></view>
            <view class="document-line"></view>
            <view class="document-line document-line-short"></view>
          </view>
          <view v-else class="pulse-symbol">
            <view class="pulse-path"></view>
            <view class="pulse-dot pulse-dot-one"></view>
            <view class="pulse-dot pulse-dot-two"></view>
            <view class="pulse-dot pulse-dot-three"></view>
          </view>
        </view>
        <view class="choice-body">
          <text class="choice-label">{{ c.label }}</text>
          <text class="choice-desc">{{ c.desc }}</text>
          <text class="choice-meta supporting-text">{{ c.id === "with_document" ? "上传 · 识别 · 确认" : "描述可选 · 10题问卷" }}</text>
        </view>
        <view class="choice-arrow"><text class="arrow-text">›</text></view>
      </view>
    </view>

    <view class="foot-note privacy-panel privacy-hint">
      <view class="privacy-symbol" aria-hidden="true"><view class="privacy-keyhole"></view></view>
      <view class="privacy-copy">
        <text class="privacy-title">你的信息由你决定</text>
        <text class="foot-note-text">两种方式都会进入同一评估流程，资料仅用于完成本次体验。</text>
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
  padding: 80rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header {
  margin-bottom: 64rpx;
}
.page-title {
  display: block;
  font-size: 44rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 20rpx;
}
.page-subtitle {
  display: block;
  font-size: 28rpx;
  color: #7a8078;
  line-height: 1.6;
}
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: #9c9585;
}
.error-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 100rpx 0;
}
.error-text {
  font-size: 28rpx;
  color: #b0574f;
  margin-bottom: 32rpx;
}
.btn-retry {
  padding: 20rpx 64rpx;
  background: #4a6b5c;
  border-radius: 44rpx;
}
.btn-retry-text {
  color: #fff;
  font-size: 28rpx;
}
.choices {
  display: flex;
  flex-direction: column;
  gap: 32rpx;
}
.choice-card {
  display: flex;
  align-items: center;
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}
.choice-disabled {
  opacity: 0.6;
}
.choice-icon {
  width: 88rpx;
  height: 88rpx;
  background: #eef0ea;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.choice-icon-text {
  font-size: 36rpx;
  color: #4a6b5c;
  font-weight: 600;
}
.choice-body {
  flex: 1;
  margin: 0 24rpx;
}
.choice-label {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 10rpx;
}
.choice-desc {
  display: block;
  font-size: 24rpx;
  color: #9c9585;
  line-height: 1.5;
}
.choice-arrow {
  flex-shrink: 0;
}
.arrow-text {
  font-size: 44rpx;
  color: #c9c3b2;
}
.foot-note {
  margin-top: 72rpx;
  text-align: center;
}
.foot-note-text {
  font-size: 22rpx;
  color: #b3ac9c;
}

.container { @include v3.v3-page; }
.flow-shell { @include v3.v3-flow-shell; }
.entry-hero { margin: 0; padding: v3.$v3-space-6 0 v3.$v3-space-10; }
.hero-mark { position: relative; width: 56px; height: 56px; margin-bottom: v3.$v3-space-6; }
.hero-orbit { position: absolute; border: 1px solid rgba(78, 116, 104, .34); border-radius: 50%; }
.hero-orbit-one { inset: 3px 9px; transform: rotate(28deg); }
.hero-orbit-two { inset: 9px 3px; transform: rotate(-28deg); }
.hero-core { position: absolute; width: 9px; height: 9px; border-radius: 50%; background: v3.$v3-accent; left: 50%; top: 50%; transform: translate(-50%, -50%); box-shadow: 0 0 0 7px rgba(185, 155, 99, .12); }
.hero-eyebrow { display: block; margin-bottom: v3.$v3-space-3; color: v3.$v3-primary; font-size: 11px; font-weight: 700; letter-spacing: 1.6px; }
.page-title { max-width: 560px; margin-bottom: v3.$v3-space-4; color: v3.$v3-text-primary; font-size: clamp(30px, 5vw, 42px); font-weight: 680; letter-spacing: -.03em; line-height: 1.22; }
.page-subtitle { max-width: 560px; color: v3.$v3-text-secondary; font-size: 16px; line-height: 1.75; }
.choices { gap: v3.$v3-space-4; }
.section-label { display: block; margin-bottom: 0; color: v3.$v3-text-secondary; font-size: 13px; font-weight: 650; letter-spacing: .04em; }
.mode-card { min-height: 148px; padding: v3.$v3-space-6; border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-lg; background: v3.$v3-surface; box-shadow: v3.$v3-shadow-soft; box-sizing: border-box; @include v3.v3-focusable; }
.mode-card:active { border-color: rgba(78, 116, 104, .48); box-shadow: v3.$v3-shadow-raised; }
.choice-disabled { opacity: .56; pointer-events: none; }
.mode-card-icon { width: 64px; height: 64px; border-radius: 20px; background: rgba(78, 116, 104, .1); }
.document-symbol { width: 27px; height: 34px; padding: 8px 6px; border: 1.5px solid v3.$v3-primary; border-radius: 6px; box-sizing: border-box; }
.document-line { width: 80%; height: 2px; margin-bottom: 5px; border-radius: 2px; background: v3.$v3-primary; }
.document-line-long { width: 100%; }
.document-line-short { width: 58%; margin-bottom: 0; }
.pulse-symbol { position: relative; width: 34px; height: 28px; }
.pulse-path { position: absolute; left: 5px; right: 5px; top: 13px; height: 1px; background: rgba(185, 155, 99, .52); }
.pulse-dot { position: absolute; z-index: 1; width: 7px; height: 7px; border-radius: 50%; background: v3.$v3-accent; box-shadow: 0 0 0 4px rgba(185, 155, 99, .12); }
.pulse-dot-one { left: 2px; top: 11px; }
.pulse-dot-two { left: 14px; top: 4px; }
.pulse-dot-three { right: 1px; top: 16px; }
.choice-body { min-width: 0; margin: 0 v3.$v3-space-5; }
.choice-label { margin-bottom: v3.$v3-space-2; color: v3.$v3-text-primary; font-size: 18px; font-weight: 680; line-height: 1.4; }
.choice-desc { color: v3.$v3-text-secondary; font-size: 14px; line-height: 1.65; }
.choice-meta { display: block; margin-top: v3.$v3-space-3; color: v3.$v3-primary; font-size: 12px; font-weight: 600; }
.choice-arrow { width: 34px; height: 34px; border-radius: 50%; background: v3.$v3-background; display: flex; align-items: center; justify-content: center; }
.arrow-text { color: v3.$v3-primary-dark; font-size: 26px; line-height: 1; transform: translateY(-1px); }
.privacy-panel { display: flex; align-items: flex-start; gap: v3.$v3-space-4; margin-top: v3.$v3-space-8; padding: v3.$v3-space-5; border: 1px solid rgba(78, 116, 104, .14); border-radius: v3.$v3-radius-md; background: rgba(255, 255, 255, .62); text-align: left; }
.privacy-symbol { position: relative; width: 30px; height: 30px; flex-shrink: 0; border: 1px solid rgba(78, 116, 104, .42); border-radius: 50%; }
.privacy-keyhole { position: absolute; width: 5px; height: 8px; border-radius: 4px; background: v3.$v3-primary; left: 50%; top: 50%; transform: translate(-50%, -42%); }
.privacy-copy { flex: 1; }
.privacy-title { display: block; margin-bottom: v3.$v3-space-1; color: v3.$v3-text-primary; font-size: 13px; font-weight: 650; }
.foot-note-text { color: v3.$v3-text-secondary; font-size: 12px; line-height: 1.65; }
.loading-wrap, .error-wrap { border: 1px solid v3.$v3-border; border-radius: v3.$v3-radius-lg; background: v3.$v3-surface; box-shadow: v3.$v3-shadow-soft; }
.loading-ring { border-color: v3.$v3-border; border-top-color: v3.$v3-primary; }
.loading-text { color: v3.$v3-text-muted; }
.error-text { color: v3.$v3-danger; }
.btn-retry { background: v3.$v3-primary; }
@media (min-width: 768px) { .container { padding-top: 64px; padding-bottom: 64px; } .entry-hero { padding-top: 32px; padding-bottom: 48px; } .mode-card { padding: 28px 30px; } }
@media (max-width: 420px) { .entry-hero { padding-top: v3.$v3-space-4; padding-bottom: v3.$v3-space-8; } .mode-card { min-height: 132px; padding: v3.$v3-space-5; } .mode-card-icon { width: 54px; height: 54px; border-radius: 17px; } .choice-body { margin: 0 v3.$v3-space-4; } .choice-label { font-size: 17px; } }
/* V1.1 restrained tuning */
.hero-eyebrow { color: v3.$v3-text-secondary; font-size: 12px; font-weight: 600; letter-spacing: .04em; }
.page-title { font-size: clamp(28px, 4.5vw, 37px); font-weight: 620; line-height: 1.32; }
.supporting-text { margin-top: v3.$v3-space-2; color: v3.$v3-text-muted; font-size: 11px; font-weight: 500; letter-spacing: .01em; }
.choice-arrow { width: 28px; height: 28px; background: transparent; }
.arrow-text { color: v3.$v3-text-muted; font-size: 23px; }
.privacy-hint { align-items: center; gap: v3.$v3-space-3; margin-top: v3.$v3-space-6; padding: v3.$v3-space-3 0; border: 0; border-radius: 0; background: transparent; }
</style>
