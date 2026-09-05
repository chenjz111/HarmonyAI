<template>
  <view class="page han-page">
    <view class="han-page-content page-inner">
      <!-- 品牌头部 -->
      <view class="hero ink-fade-in">
        <view class="brand-row">
          <view class="brand-seal">
            <text class="brand-seal-text">和</text>
          </view>
          <view class="brand-meta">
            <text class="brand-name">HarmonyAI</text>
            <text class="brand-tagline">中医五音 · 音乐调养</text>
          </view>
        </view>
      </view>

      <!-- 主内容 -->
      <view class="content-area">
        <!-- 加载态 -->
        <view v-if="loading" class="loading-state">
          <view class="loading-ring"></view>
          <text class="loading-text">正在备茶</text>
        </view>

        <!-- 错误态 -->
        <view v-else-if="error" class="error-state ink-fade-in">
          <view class="error-seal">
            <text class="error-seal-text">静</text>
          </view>
          <text class="error-title">暂时无法开始</text>
          <text class="error-desc">{{ error }}</text>
          <view class="han-btn han-btn-primary retry-btn" @click="init">
            <text class="btn-text">重试</text>
          </view>
          <text class="error-hint">若持续出现，请检查网络后再次尝试 · 你不必着急</text>
        </view>

        <!-- 正常态 -->
        <view v-else class="entry-content ink-fade-up">
          <text class="hero-title">今天感觉如何？</text>
          <text class="hero-desc">通过近期资料或状态问卷，生成专属于你的音乐调养建议。</text>

          <view class="choice-stack">
            <view
              v-for="(choice, idx) in entry.choices"
              :key="choice.id"
              class="choice-card"
              :class="{ 'choice-card-loading': submittingId === choice.id }"
              @click="choose(choice)"
            >
              <view class="choice-seal">
                <text class="choice-seal-text">{{ idx === 0 ? '资' : '心' }}</text>
              </view>
              <view class="choice-body">
                <text class="choice-label">{{ choice.label }}</text>
                <text class="choice-desc">{{ choice.desc }}</text>
              </view>
              <view class="choice-arrow">
                <text class="choice-arrow-text">›</text>
              </view>
            </view>
          </view>

          <view class="footer-seal-wrap">
            <text class="footer-hint">若文字方式无法满足 · 全程数据仅用于本次聆听</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
/**
 * V3 首页（双入口选择）
 * 合同依据：frontend-read-model-contract-v3.md §3.1 EntryReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2（最终用户流程）
 *          Issue #100：Welcome 退出主流程，entry 直接作为首页。
 *
 * v2 重写（水墨国风）：
 *   - 全页 .han-page 山水背景
 *   - 选项卡改为宣纸卡片 + 印章角标
 *   - 错误态用朱砂印章 + 减压文案
 *   - 业务逻辑 init() / choose() 完全保留
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      entry: null,
      submitting: false,
      submittingId: null,
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
      this.submittingId = choice.id
      try {
        await apiV3.selectMode(choice.id)
        uni.navigateTo({ url: choice.route })
      } catch (e) {
        uni.showToast({ title: e.message || "选择失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
        this.submittingId = null
      }
    },
  },
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
}

.page-inner {
  padding: 48rpx 40rpx 64rpx;
  min-height: 100vh;
  box-sizing: border-box;
}

/* ===== 品牌头部 ===== */
.hero {
  margin-bottom: 56rpx;
  padding-top: 24rpx;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.brand-seal {
  width: 84rpx;
  height: 84rpx;
  border-radius: var(--radius-seal);
  background: var(--ink-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 18rpx rgba(107, 124, 94, 0.22);
  transform: rotate(-3deg);
}

.brand-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 44rpx;
  font-weight: 700;
  color: var(--text-inverse);
}

.brand-meta {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--ink-700);
  letter-spacing: 0.1em;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
}

.brand-tagline {
  font-size: 22rpx;
  color: var(--text-muted);
  margin-top: 4rpx;
  letter-spacing: 0.1em;
}

/* ===== 加载态 ===== */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 220rpx 0;
  color: var(--text-muted);
}

.loading-ring {
  width: 56rpx;
  height: 56rpx;
  border: 4rpx solid var(--border-light);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  margin-bottom: 20rpx;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 26rpx;
  color: var(--text-muted);
  letter-spacing: 0.15em;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

/* ===== 错误态 ===== */
.error-state {
  padding: 120rpx 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.error-seal {
  width: 128rpx;
  height: 128rpx;
  border-radius: var(--radius-seal);
  background: var(--paper-card-solid);
  border: 2rpx solid var(--ink-seal);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 36rpx;
  box-shadow: var(--shadow-seal);
  transform: rotate(-4deg);
}

.error-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 72rpx;
  color: var(--ink-seal);
  font-weight: 700;
}

.error-title {
  font-size: 40rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.1em;
  margin-bottom: 16rpx;
}

.error-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 40rpx;
  max-width: 520rpx;
}

.retry-btn {
  min-width: 240rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.btn-text {
  color: inherit;
  font-size: 30rpx;
}

.error-hint {
  margin-top: 32rpx;
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* ===== 正常态 ===== */
.entry-content {
  display: flex;
  flex-direction: column;
}

.hero-title {
  font-size: 64rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.12em;
  line-height: 1.2;
  margin-bottom: 18rpx;
}

.hero-title::after {
  content: "";
  display: block;
  width: 120rpx;
  height: 4rpx;
  margin-top: 20rpx;
  background: linear-gradient(90deg, var(--ink-700), transparent);
  border-radius: 50%;
  filter: blur(0.5px);
}

.hero-desc {
  font-size: 28rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 56rpx;
}

.choice-stack {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
  margin-bottom: 56rpx;
}

.choice-card {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 32rpx 28rpx;
  background: var(--paper-card);
  border-radius: var(--radius-lg);
  border: 1rpx solid var(--border-soft);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(8rpx);
  transition: all 0.25s var(--ease-out);
  position: relative;
}

.choice-card::before {
  content: "";
  position: absolute;
  top: 18rpx;
  left: 18rpx;
  width: 22rpx;
  height: 22rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23CCC5B6' stroke-width='1'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
  background-size: contain;
  opacity: 0.45;
}

.choice-card::after {
  content: "";
  position: absolute;
  bottom: 18rpx;
  right: 18rpx;
  width: 22rpx;
  height: 22rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23CCC5B6' stroke-width='1'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
  background-size: contain;
  opacity: 0.45;
  transform: rotate(180deg);
}

.choice-card:active {
  transform: translateY(-4rpx);
  box-shadow: var(--shadow-lg);
}

.choice-card-loading {
  opacity: 0.6;
  pointer-events: none;
}

.choice-seal {
  width: 72rpx;
  height: 72rpx;
  border-radius: var(--radius-seal);
  background: var(--paper-card-solid);
  border: 2rpx solid var(--ink-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.choice-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 30rpx;
  color: var(--ink-primary);
  font-weight: 700;
}

.choice-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.choice-label {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  margin-bottom: 8rpx;
  letter-spacing: 0.05em;
}

.choice-desc {
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.5;
}

.choice-arrow {
  width: 52rpx;
  height: 52rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.choice-arrow-text {
  font-size: 44rpx;
  color: var(--text-muted);
  font-weight: 300;
  line-height: 1;
}

.footer-seal-wrap {
  display: flex;
  justify-content: center;
}

.footer-hint {
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-align: center;
  padding: 12rpx 28rpx;
  background: rgba(251, 249, 244, 0.6);
  border-radius: var(--radius-pill);
  border: 1rpx solid var(--border-light);
}
</style>
