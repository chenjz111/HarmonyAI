<template>
  <view class="error-state">
    <view class="error-icon">
      <text class="error-icon-text">!</text>
    </view>
    <text class="error-title">{{ title }}</text>
    <text class="error-desc">{{ message }}</text>
    <view class="error-actions">
      <view class="error-btn primary" @click="onRetry" v-if="showRetry">
        <text class="error-btn-text">{{ retryText }}</text>
      </view>
      <view class="error-btn secondary" @click="onFallback" v-if="showFallback">
        <text class="error-btn-text">{{ fallbackText }}</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ErrorState',
  props: {
    title: { type: String, default: '出错了' },
    message: { type: String, default: '网络连接异常，请检查网络后重试' },
    showRetry: { type: Boolean, default: true },
    retryText: { type: String, default: '重新尝试' },
    showFallback: { type: Boolean, default: false },
    fallbackText: { type: String, default: '跳过' }
  },
  methods: {
    onRetry() { this.$emit('retry') },
    onFallback() { this.$emit('fallback') }
  }
}
</script>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80rpx 48rpx;
  text-align: center;
  background: #FCFAF6;
  border-radius: 32rpx;
  border: 1rpx solid #E8E2D5;
}
.error-icon {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: #F9EDE7;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
  border: 4rpx solid #FCFAF6;
  box-shadow: 0 4rpx 16rpx rgba(200, 90, 69, 0.12);
}
.error-icon-text {
  font-size: 64rpx;
  font-weight: 700;
  color: #C85A45;
  font-family: Georgia, serif;
}
.error-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #2C2A28;
  margin-bottom: 12rpx;
  letter-spacing: 0.02em;
}
.error-desc {
  font-size: 26rpx;
  color: #6B6862;
  line-height: 1.7;
  margin-bottom: 40rpx;
  max-width: 480rpx;
}
.error-actions {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  width: 100%;
  max-width: 440rpx;
}
.error-btn {
  height: 88rpx;
  border-radius: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.error-btn:active {
  transform: scale(0.97);
}
.error-btn.primary {
  background: #4A6B5C;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.20);
}
.error-btn.secondary {
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
}
.error-btn-text {
  font-size: 28rpx;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.error-btn.primary .error-btn-text {
  color: #FCFAF6;
}
.error-btn.secondary .error-btn-text {
  color: #4A6B5C;
}
</style>