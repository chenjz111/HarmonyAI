<template>
  <view class="container">
    <!-- 顶部水墨首屏 -->
    <view class="hero">
      <!-- 装饰：水墨圆环 -->
      <view class="ink-ring"></view>
      <view class="ink-ring ink-ring-2"></view>

      <!-- 中央 logo -->
      <view class="logo-wrap">
        <view class="logo">
          <text class="logo-text">和</text>
        </view>
        <view class="logo-aura"></view>
      </view>

      <view class="brand-name">HarmonyAI</view>
      <view class="brand-tagline">中医五音 · 情绪疗愈</view>
      <view class="brand-divider">
        <view class="divider-line"></view>
        <view class="divider-dot"></view>
        <view class="divider-line"></view>
      </view>
      <view class="brand-quote">"五音疗疾，以乐入心"</view>
    </view>

    <!-- 流程时间轴 -->
    <view class="flow">
      <view class="flow-title">
        <text class="flow-title-text">评估流程</text>
        <text class="flow-title-sub">共 4 步，约 2 分钟</text>
      </view>

      <view class="timeline">
        <view class="timeline-item" v-for="(item, idx) in steps" :key="idx">
          <view class="timeline-node">
            <view class="timeline-circle">
              <text class="timeline-icon">{{ item.icon }}</text>
            </view>
            <view class="timeline-line" v-if="idx < steps.length - 1"></view>
          </view>
          <view class="timeline-content">
            <text class="timeline-step">步骤 {{ idx + 1 }}</text>
            <text class="timeline-name">{{ item.name }}</text>
            <text class="timeline-desc">{{ item.desc }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 底部说明 + 按钮 -->
    <view class="footer">
      <view class="meta-card">
        <view class="meta-item">
          <text class="meta-icon">⏱</text>
          <text class="meta-text">2-3 分钟</text>
        </view>
        <view class="meta-divider"></view>
        <view class="meta-item">
          <text class="meta-icon">✎</text>
          <text class="meta-text">全程匿名</text>
        </view>
        <view class="meta-divider"></view>
        <view class="meta-item">
          <text class="meta-icon">♪</text>
          <text class="meta-text">AI 处方</text>
        </view>
      </view>

      <view class="start-btn" @click="goNext">
        <text class="start-btn-text">开启疗愈之旅</text>
        <view class="start-btn-arrow">
          <text class="arrow-text">→</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      steps: [
        { icon: '册', name: '上传材料', desc: '可选 · 病历或检查报告' },
        { icon: '写', name: '自由描述', desc: '可选 · 写几句最近状态' },
        { icon: '问', name: '12 题问卷', desc: '约 1 分钟 · 五维度评估' },
        { icon: '音', name: 'AI 生成处方', desc: '即时 · 五音疗愈音乐' }
      ]
    }
  },
  methods: {
    goNext() {
      uni.navigateTo({ url: '/pages/material/material' })
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: linear-gradient(180deg, #F0EADC 0%, #F7F3EB 60%, #F7F3EB 100%);
  padding: 60rpx 48rpx 60rpx;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}

/* 顶部 hero 区 */
.hero {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 0 50rpx;
  position: relative;
}

/* 水墨圆环装饰 */
.ink-ring {
  position: absolute;
  top: 0;
  left: 50%;
  width: 480rpx;
  height: 480rpx;
  border-radius: 50%;
  border: 1rpx solid rgba(74, 107, 92, 0.12);
  transform: translate(-50%, -20%);
}
.ink-ring-2 {
  width: 700rpx;
  height: 700rpx;
  border-color: rgba(74, 107, 92, 0.06);
  transform: translate(-50%, -10%);
}

.logo-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 40rpx;
  z-index: 2;
}
.logo {
  width: 200rpx;
  height: 200rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 20rpx 60rpx rgba(74, 107, 92, 0.25),
    inset 0 4rpx 8rpx rgba(255, 255, 255, 0.15);
  position: relative;
  z-index: 2;
}
.logo-aura {
  position: absolute;
  width: 240rpx;
  height: 240rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(74, 107, 92, 0.18) 0%, transparent 70%);
}
.logo-text {
  font-size: 96rpx;
  font-weight: 700;
  color: #F7F3EB;
  font-family: 'Kaiti SC', 'STKaiti', 'Songti SC', serif;
  letter-spacing: 0;
}

.brand-name {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.16em;
  margin-bottom: 12rpx;
  z-index: 2;
}
.brand-tagline {
  font-size: 26rpx;
  color: #6B6862;
  letter-spacing: 0.4em;
  padding-left: 0.4em;
  margin-bottom: 24rpx;
  z-index: 2;
}
.brand-divider {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 20rpx;
  z-index: 2;
}
.divider-line {
  width: 80rpx;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, #C8896D, transparent);
}
.divider-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #C8896D;
}
.brand-quote {
  font-size: 26rpx;
  color: #6B6862;
  font-style: italic;
  letter-spacing: 0.1em;
  z-index: 2;
}

/* 流程时间轴 */
.flow {
  margin-top: 40rpx;
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 40rpx 36rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 8rpx 32rpx rgba(74, 107, 92, 0.08);
}
.flow-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 32rpx;
  padding-bottom: 20rpx;
  border-bottom: 1rpx dashed #E8E2D5;
}
.flow-title-text {
  font-size: 32rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.05em;
}
.flow-title-sub {
  font-size: 22rpx;
  color: #9C9585;
}

.timeline {
  display: flex;
  flex-direction: column;
}
.timeline-item {
  display: flex;
  gap: 28rpx;
}
.timeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  padding-top: 4rpx;
}
.timeline-circle {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: #EEF1ED;
  border: 2rpx solid #C8D2CB;
  display: flex;
  align-items: center;
  justify-content: center;
}
.timeline-icon {
  font-size: 32rpx;
  font-weight: 600;
  color: #4A6B5C;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.timeline-line {
  width: 2rpx;
  flex: 1;
  min-height: 80rpx;
  background: repeating-linear-gradient(180deg, #C8D2CB 0, #C8D2CB 8rpx, transparent 8rpx, transparent 16rpx);
  margin-top: 4rpx;
  margin-bottom: 4rpx;
}
.timeline-content {
  flex: 1;
  padding-bottom: 40rpx;
}
.timeline-item:last-child .timeline-content {
  padding-bottom: 0;
}
.timeline-step {
  font-size: 22rpx;
  color: #9C9585;
  letter-spacing: 0.1em;
  display: block;
  margin-bottom: 6rpx;
}
.timeline-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #2C2A28;
  letter-spacing: 0.03em;
  display: block;
  margin-bottom: 4rpx;
}
.timeline-desc {
  font-size: 24rpx;
  color: #6B6862;
  display: block;
}

/* 底部 */
.footer {
  margin-top: auto;
  padding-top: 40rpx;
}
.meta-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  margin-bottom: 32rpx;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.meta-icon {
  font-size: 24rpx;
  color: #C8896D;
}
.meta-text {
  font-size: 24rpx;
  color: #6B6862;
}
.meta-divider {
  width: 1rpx;
  height: 24rpx;
  background: #C8D2CB;
}

.start-btn {
  height: 108rpx;
  border-radius: 54rpx;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  box-shadow: 0 12rpx 36rpx rgba(74, 107, 92, 0.30);
  transition: all 0.2s;
}
.start-btn:active {
  transform: scale(0.98);
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.25);
}
.start-btn-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #F7F3EB;
  letter-spacing: 0.1em;
}
.start-btn-arrow {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}
.arrow-text {
  font-size: 28rpx;
  color: #F7F3EB;
}
</style>