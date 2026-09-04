<script>
/**
 * V3 首页（双入口选择）
 * 合同依据：frontend-read-model-contract-v3.md §3.1 EntryReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2（最终用户流程）
 *          Issue #100：Welcome 退出主流程，entry 直接作为首页。
 *
 * 文案严格使用 Owner Amendment 批准版本：
 *  - "我有近期就诊资料" / "我没有近期就诊资料"
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
          title: "今天感觉如何？",
          description: "通过近期资料或状态问卷，生成专属于你的音乐调养建议。",
          choices: [
            { id: "with_document", label: "我有近期就诊资料", desc: "可上传近期病历、检查报告或相关就诊记录，让建议更贴合你的情况。", route: "/pages/v3-material/v3-material" },
            { id: "without_document", label: "我没有近期就诊资料", desc: "可以先补充一些近况，也可以直接完成近期状态问卷。", route: "/pages/v3-supplement/v3-supplement" },
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
  <view class="container">
    <!-- 品牌头部（首页定位：Welcome 已退出主流程） -->
    <view class="hero">
      <view class="brand-row">
        <view class="brand-logo"><text class="brand-logo-text">和</text></view>
        <view class="brand-meta">
          <text class="brand-name">HarmonyAI</text>
          <text class="brand-tagline">中医五音 · 音乐调养</text>
        </view>
      </view>
      <text class="hero-title">{{ entry ? entry.title : "今天感觉如何？" }}</text>
      <text class="hero-desc">{{ entry ? entry.description : "生成专属于你的音乐调养建议。" }}</text>
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
      <view class="section-label">
        <view class="label-line"></view>
        <text class="label-text">选择一种方式开始</text>
        <view class="label-line"></view>
      </view>
      <view
        v-for="c in entry.choices"
        :key="c.id"
        class="choice-card"
        :class="{ 'choice-disabled': submitting }"
        @click="choose(c)"
      >
        <view class="choice-icon">
          <text class="choice-icon-text">{{ c.id === "with_document" ? "文" : "问" }}</text>
        </view>
        <view class="choice-body">
          <text class="choice-label">{{ c.label }}</text>
          <text class="choice-desc">{{ c.desc }}</text>
        </view>
        <view class="choice-arrow"><text class="arrow-text">›</text></view>
      </view>
    </view>

    <view class="foot-note">
      <text class="foot-note-text">两种方式都会生成音乐调养建议 · 全程数据仅用于本次评估</text>
    </view>
  </view>
</template>

<style>
.container {
  min-height: 100vh;
  background: linear-gradient(180deg, #f0eadc 0%, #f7f3eb 320rpx, #f7f3eb 100%);
  padding: 60rpx 48rpx 60rpx;
  box-sizing: border-box;
}

/* ===== 品牌头部 ===== */
.hero {
  margin-bottom: 48rpx;
}
.brand-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 48rpx;
}
.brand-logo {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4a6b5c 0%, #2f4a3d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.22);
}
.brand-logo-text {
  font-size: 44rpx;
  font-weight: 700;
  color: #f7f3eb;
  font-family: 'Kaiti SC', 'STKaiti', 'Songti SC', serif;
}
.brand-meta {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 32rpx;
  font-weight: 700;
  color: #2c2a28;
  letter-spacing: 0.14em;
}
.brand-tagline {
  font-size: 22rpx;
  color: #6b6862;
  letter-spacing: 0.34em;
  padding-left: 0.34em;
  margin-top: 4rpx;
}
.hero-title {
  display: block;
  font-size: 46rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 16rpx;
  letter-spacing: 0.02em;
}
.hero-desc {
  display: block;
  font-size: 27rpx;
  color: #7a8078;
  line-height: 1.65;
  max-width: 560rpx;
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

/* ===== 双入口卡片 ===== */
.choices {
  display: flex;
  flex-direction: column;
}
.section-label {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 28rpx;
}
.label-line {
  flex: 1;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, #d9d0bd, transparent);
}
.label-text {
  font-size: 24rpx;
  color: #9c9585;
  letter-spacing: 0.08em;
}
.choice-card {
  display: flex;
  align-items: center;
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
  margin-bottom: 28rpx;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
  transition: all 0.2s;
}
.choice-card:active {
  transform: scale(0.99);
  border-color: #c8d2cb;
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
  margin-top: 48rpx;
  text-align: center;
}
.foot-note-text {
  font-size: 22rpx;
  color: #b3ac9c;
}
</style>
