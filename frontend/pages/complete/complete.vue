<template>
  <view class="container">
    <view class="ornament-top"><view class="ornament-line"></view><view class="ornament-dot"></view><view class="ornament-line"></view></view>
    <view class="success-card">
      <view class="success-mark"><view class="success-circle"><text class="success-check">✓</text></view><view class="success-aura"></view></view>
      <text class="success-title">本次体验已完成</text>
      <text class="success-quote">“五音疗疾，以乐入心”</text>
      <text class="success-desc">反馈已经保存，并用于更新你的个人音乐偏好；不会自动修改全局医学知识和辨证规则。</text>

      <view class="summary-box" v-if="payload">
        <view class="summary-header"><view class="summary-line"></view><text class="summary-title">本次主观反馈</text><view class="summary-line"></view></view>
        <view class="overall-row"><text class="overall-label">整体满意度</text><view class="overall-stars"><text class="overall-star" v-for="s in 5" :key="s" :class="{ active: s <= payload.experience.overall_rating }">★</text></view></view>
        <view class="summary-list">
          <view class="summary-row"><text class="summary-label">放松程度</text><text>{{ payload.experience.relaxation_rating }} / 5</text></view>
          <view class="summary-row"><text class="summary-label">音乐匹配度</text><text>{{ payload.experience.music_match_rating }} / 5</text></view>
          <view class="summary-row"><text class="summary-label">紧张变化</text><text>{{ payload.pre_state.tension }} → {{ payload.post_state.tension }}</text></view>
        </view>
        <view class="summary-comment" v-if="payload.experience.comment"><text class="comment-quote-label">你的补充</text><text class="comment-quote-text">“{{ payload.experience.comment }}”</text></view>
      </view>

      <view class="action-btn" @click="goHome"><text class="action-btn-text">返回首页</text><text class="action-btn-arrow">→</text></view>
    </view>
    <view class="ornament-bottom"><view class="ornament-line"></view><view class="ornament-dot"></view><view class="ornament-line"></view></view>
  </view>
</template>

<script>
import { getSprint3Session } from '@/common/sprint3-session.js'

export default {
  data() { return { payload: null } },
  onLoad() { this.payload = getSprint3Session().feedback_payload || null },
  methods: {
    goHome() { uni.reLaunch({ url: '/pages/welcome/welcome' }) }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: linear-gradient(180deg, #F0EADC 0%, #F7F3EB 50%, #F7F3EB 100%);
  padding: 60rpx 40rpx 60rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

/* 顶部装饰 */
.ornament-top {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 40rpx;
}
.ornament-line {
  width: 80rpx;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, #C8896D, transparent);
}
.ornament-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #C8896D;
}

/* 成功标识 */
.success-card {
  width: 100%;
  max-width: 640rpx;
  background: #FCFAF6;
  border-radius: 36rpx;
  padding: 60rpx 40rpx 48rpx;
  text-align: center;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 12rpx 40rpx rgba(74, 107, 92, 0.10);
  position: relative;
}

.success-mark {
  position: relative;
  width: 180rpx;
  height: 180rpx;
  margin: 0 auto 40rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.success-circle {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 12rpx 32rpx rgba(74, 107, 92, 0.30),
    inset 0 4rpx 8rpx rgba(255, 255, 255, 0.15);
  position: relative;
  z-index: 2;
}
.success-check {
  font-size: 72rpx;
  color: #FCFAF6;
  font-weight: 700;
}
.success-aura {
  position: absolute;
  width: 180rpx;
  height: 180rpx;
  border-radius: 50%;
  border: 2rpx solid rgba(74, 107, 92, 0.3);
  animation: rippleOut 2s ease-out infinite;
}
@keyframes rippleOut {
  0% { transform: scale(0.6); opacity: 1; }
  100% { transform: scale(1.4); opacity: 0; }
}

.success-title {
  font-size: 40rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  margin-bottom: 16rpx;
  letter-spacing: 0.05em;
}
.success-quote {
  display: block;
  font-size: 24rpx;
  color: #C8896D;
  font-style: italic;
  letter-spacing: 0.15em;
  margin-bottom: 16rpx;
}
.success-desc {
  font-size: 26rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
  margin-bottom: 40rpx;
}

/* 本次记录 */
.summary-box {
  background: #F7F3EB;
  border-radius: 24rpx;
  padding: 32rpx 24rpx;
  text-align: left;
  margin-bottom: 40rpx;
  border: 1rpx solid #E8E2D5;
}
.summary-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
}
.summary-line {
  flex: 1;
  height: 1rpx;
  background: #E8E2D5;
}
.summary-title {
  font-size: 24rpx;
  color: #9C9585;
  letter-spacing: 0.15em;
  font-weight: 500;
}

.overall-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0 20rpx;
  border-bottom: 1rpx dashed #E8E2D5;
  margin-bottom: 20rpx;
}
.overall-label {
  font-size: 28rpx;
  color: #2C2A28;
  font-weight: 600;
}
.overall-stars {
  display: flex;
  gap: 6rpx;
}
.overall-star {
  font-size: 32rpx;
  color: #E8E2D5;
}
.overall-star.active {
  color: #D4A574;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.summary-label {
  font-size: 26rpx;
  color: #2C2A28;
}
.summary-stars-text {
  font-size: 24rpx;
  color: #D4A574;
  letter-spacing: 2rpx;
  font-family: Georgia, serif;
}
.empty-stars {
  color: #E8E2D5;
}

.summary-comment {
  margin-top: 24rpx;
  padding-top: 20rpx;
  border-top: 1rpx dashed #E8E2D5;
}
.comment-quote-label {
  display: block;
  font-size: 22rpx;
  color: #9C9585;
  letter-spacing: 0.1em;
  margin-bottom: 8rpx;
}
.comment-quote-text {
  display: block;
  font-size: 26rpx;
  color: #6B6862;
  font-style: italic;
  line-height: 1.7;
}

/* 行动按钮 */
.action-btn {
  height: 108rpx;
  border-radius: 54rpx;
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  box-shadow: 0 12rpx 36rpx rgba(74, 107, 92, 0.30);
  transition: all 0.2s;
}
.action-btn:active {
  transform: scale(0.98);
}
.action-btn-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #F7F3EB;
  letter-spacing: 0.1em;
}
.action-btn-arrow {
  font-size: 30rpx;
  color: #F7F3EB;
  font-weight: 500;
}

/* 底部装饰 */
.ornament-bottom {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-top: 40rpx;
}
.ornament-bottom .ornament-line {
  background: linear-gradient(90deg, transparent, #C8896D, transparent);
}
</style>