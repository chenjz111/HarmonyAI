<template>
  <view class="page han-page">
    <view class="han-page-content page-inner">
      <!-- 顶部水墨首屏 -->
      <view class="hero ink-fade-in">
        <view class="mountain-decoration" aria-hidden="true"></view>

        <!-- 中央印章 logo -->
        <view class="logo-wrap">
          <view class="logo">
            <text class="logo-text">和</text>
          </view>
          <view class="logo-aura"></view>
          <view class="logo-mist"></view>
        </view>

        <view class="brand-name">HarmonyAI</view>
        <view class="brand-tagline">中医五音 · 音乐调养</view>

        <view class="brand-divider">
          <view class="divider-line"></view>
          <view class="divider-seal">
            <text class="divider-seal-text">音</text>
          </view>
          <view class="divider-line"></view>
        </view>

        <view class="brand-quote">"五音疗疾，以乐入心"</view>
      </view>

      <!-- 流程时间轴 -->
      <view class="flow ink-fade-up">
        <view class="flow-card">
          <view class="flow-title">
            <text class="flow-title-text">评估流程</text>
            <text class="flow-title-sub">约 2 分钟 · 你可以慢慢来</text>
          </view>

          <view class="timeline">
            <view class="timeline-item" v-for="(item, idx) in steps" :key="idx">
              <view class="timeline-node">
                <view class="timeline-seal">
                  <text class="timeline-seal-text">{{ item.icon }}</text>
                </view>
                <view class="timeline-line" v-if="idx < steps.length - 1"></view>
              </view>
              <view class="timeline-content">
                <text class="timeline-step">第 {{ idx + 1 }} 步</text>
                <text class="timeline-name">{{ item.name }}</text>
                <text class="timeline-desc">{{ item.desc }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 底部说明 + 按钮 -->
      <view class="footer ink-fade-up">
        <view class="meta-card">
          <view class="meta-item">
            <text class="meta-icon">⏱</text>
            <text class="meta-text">2-3 分钟</text>
          </view>
          <view class="meta-divider"></view>
          <view class="meta-item">
            <text class="meta-icon">匿</text>
            <text class="meta-text">全程匿名</text>
          </view>
          <view class="meta-divider"></view>
          <view class="meta-item">
            <text class="meta-icon">音</text>
            <text class="meta-text">音乐处方</text>
          </view>
        </view>

        <view class="start-btn" @click="goNext">
          <text class="start-btn-text">始调神</text>
          <view class="start-btn-arrow">
            <text class="arrow-text">→</text>
          </view>
        </view>

        <text class="footer-hint">一切从这一刻开始 · 你不必着急</text>
      </view>
    </view>
  </view>
</template>

<script>
/**
 * V3 欢迎页（Owner Amendment §2.2：作为「首次进入」轻量介绍，非主流程必经节点）
 *
 * v2 重写（水墨国风）：
 *   - 全页山水背景 + 云雾动效
 *   - 中央印章 logo
 *   - 流程卡改为宣纸卡片
 *   - 底部「始调神」朱砂印章按钮
 *
 * 跳转逻辑：entry 是 tabBar 页面，须用 reLaunch
 */
export default {
  data() {
    return {
      steps: [
        { icon: "择", name: "选择方式", desc: "有 / 无近期就诊资料均可" },
        { icon: "册", name: "资料与近况", desc: "可上传 · 也可直接补充近况" },
        { icon: "问", name: "状态问卷", desc: "5 页 · 每页 2 题 · 你不必着急" },
        { icon: "音", name: "聆听", desc: "依据状态生成音乐调养" },
      ],
    }
  },
  methods: {
    async goNext() {
      try {
        uni.reLaunch({ url: "/pages/entry/entry" })
      } catch (error) {
        uni.showToast({ title: error.message || "无法开始评估", icon: "none" })
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
  padding: 40rpx 40rpx 64rpx;
  min-height: 100vh;
  box-sizing: border-box;
}

/* ===== 顶部水墨首屏 ===== */
.hero {
  position: relative;
  padding: 64rpx 0 56rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
}

.mountain-decoration {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 180rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320' preserveAspectRatio='xMidYMax slice'%3E%3Cpath fill='%23E8E3D8' fill-opacity='0.45' d='M0,224L48,213.3C96,203,192,181,288,181.3C384,181,480,203,576,224C672,245,768,267,864,250.7C960,235,1056,181,1152,165.3C1248,149,1344,171,1392,181.3L1440,192L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'%3E%3C/path%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: bottom;
  background-size: cover;
  opacity: 0.7;
  pointer-events: none;
}

/* 中央印章 logo */
.logo-wrap {
  position: relative;
  width: 200rpx;
  height: 200rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 36rpx;
}

.logo {
  width: 160rpx;
  height: 160rpx;
  border-radius: var(--radius-seal);
  background: var(--ink-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-lg);
  position: relative;
  z-index: 2;
  transform: rotate(-3deg);
}

.logo-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 96rpx;
  font-weight: 700;
  color: var(--text-inverse);
  line-height: 1;
}

.logo-aura {
  position: absolute;
  width: 190rpx;
  height: 190rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(107, 124, 94, 0.16) 0%, transparent 70%);
  z-index: 1;
  animation: aura-breathe 3.5s ease-in-out infinite;
}

.logo-mist {
  position: absolute;
  width: 260rpx;
  height: 80rpx;
  bottom: 10rpx;
  border-radius: 50%;
  background: radial-gradient(ellipse, rgba(232, 227, 216, 0.7) 0%, transparent 70%);
  filter: blur(8rpx);
  z-index: 0;
  animation: mist-float 5s ease-in-out infinite;
}

@keyframes aura-breathe {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.12); opacity: 0.95; }
}

@keyframes mist-float {
  0%, 100% { transform: translateX(0); opacity: 0.6; }
  50% { transform: translateX(20rpx); opacity: 0.9; }
}

.brand-name {
  font-size: 48rpx;
  font-weight: 700;
  color: var(--ink-700);
  letter-spacing: 0.15em;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  margin-bottom: 10rpx;
}

.brand-tagline {
  font-size: 24rpx;
  color: var(--text-secondary);
  letter-spacing: 0.2em;
  margin-bottom: 28rpx;
}

.brand-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
  margin-bottom: 28rpx;
}

.divider-line {
  width: 80rpx;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, var(--ink-accent), transparent);
}

.divider-seal {
  width: 40rpx;
  height: 40rpx;
  border-radius: var(--radius-seal);
  background: var(--ink-seal);
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(-5deg);
  box-shadow: var(--shadow-seal);
}

.divider-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 20rpx;
  color: var(--text-inverse);
  font-weight: 700;
}

.brand-quote {
  font-size: 28rpx;
  color: var(--text-secondary);
  letter-spacing: 0.12em;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

/* ===== 流程时间轴 ===== */
.flow {
  margin-bottom: 40rpx;
}

.flow-card {
  padding: 36rpx 28rpx;
  background: var(--paper-card);
  border-radius: var(--radius-lg);
  border: 1rpx solid var(--border-soft);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(8rpx);
  position: relative;
}

.flow-card::before,
.flow-card::after {
  content: "";
  position: absolute;
  width: 24rpx;
  height: 24rpx;
  background-repeat: no-repeat;
  background-size: contain;
  opacity: 0.32;
}

.flow-card::before {
  top: 16rpx;
  left: 16rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.flow-card::after {
  bottom: 16rpx;
  right: 16rpx;
  transform: rotate(180deg);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.flow-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 28rpx;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid var(--border-light);
}

.flow-title-text {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.08em;
}

.flow-title-sub {
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.timeline {
  display: flex;
  flex-direction: column;
  padding: 8rpx 0;
}

.timeline-item {
  display: flex;
  align-items: stretch;
  gap: 24rpx;
}

.timeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  padding-top: 8rpx;
}

.timeline-seal {
  width: 64rpx;
  height: 64rpx;
  border-radius: var(--radius-seal);
  background: var(--paper-card-solid);
  border: 2rpx solid var(--ink-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
}

.timeline-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 28rpx;
  color: var(--ink-primary);
  font-weight: 700;
}

.timeline-line {
  flex: 1;
  width: 2rpx;
  background: linear-gradient(180deg, var(--ink-primary), var(--ink-accent));
  opacity: 0.35;
  margin: 10rpx 0;
  min-height: 36rpx;
}

.timeline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding-bottom: 36rpx;
}

.timeline-step {
  font-size: 22rpx;
  color: var(--ink-seal);
  letter-spacing: 0.1em;
  margin-bottom: 6rpx;
  font-weight: 500;
}

.timeline-name {
  font-size: 30rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  margin-bottom: 6rpx;
  letter-spacing: 0.05em;
}

.timeline-desc {
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ===== 底部 ===== */
.footer {
  display: flex;
  flex-direction: column;
}

.meta-card {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 22rpx 24rpx;
  background: rgba(107, 124, 94, 0.06);
  border-radius: var(--radius-md);
  margin-bottom: 36rpx;
  border: 1rpx solid var(--border-light);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.meta-icon {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 24rpx;
  color: var(--ink-primary);
}

.meta-text {
  font-size: 24rpx;
  color: var(--text-secondary);
  letter-spacing: 0.05em;
}

.meta-divider {
  width: 1rpx;
  height: 24rpx;
  background: var(--ink-accent);
  opacity: 0.4;
}

.start-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  padding: 28rpx 48rpx;
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  box-shadow: var(--shadow-seal);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  letter-spacing: 0.2em;
  transition: all 0.25s var(--ease-out);
  position: relative;
  overflow: hidden;
}

.start-btn::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%);
  pointer-events: none;
}

.start-btn:active {
  transform: scale(0.98);
  background: var(--ink-seal-dark);
}

.start-btn-text {
  font-size: 36rpx;
  font-weight: 700;
  position: relative;
  z-index: 1;
}

.start-btn-arrow {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: rgba(255, 254, 250, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.arrow-text {
  font-size: 28rpx;
  color: var(--text-inverse);
  font-weight: 300;
  line-height: 1;
}

.footer-hint {
  margin-top: 28rpx;
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-align: center;
}
</style>
