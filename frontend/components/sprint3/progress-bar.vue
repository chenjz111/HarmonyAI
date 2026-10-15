<template>
  <view class="progress-bar">
    <view class="progress-track">
      <view class="progress-fill" :style="{ width: progress + '%' }"></view>
    </view>
    <view class="progress-meta" v-if="showText">
      <text class="progress-label">{{ label }}</text>
      <text class="progress-value">{{ progress }}%</text>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ProgressBar',
  props: {
    progress: { type: Number, default: 0 },
    label: { type: String, default: '进度' },
    showText: { type: Boolean, default: true }
  }
}
</script>

<style scoped>
.progress-bar {
  margin-bottom: 32rpx;
}
.progress-track {
  height: 8rpx;
  background: #E8E2D5;
  border-radius: 4rpx;
  overflow: hidden;
  position: relative;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4A6B5C 0%, #6B8979 100%);
  border-radius: 4rpx;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}
.progress-fill::after {
  content: '';
  position: absolute;
  right: 0;
  top: -3rpx;
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: #4A6B5C;
  box-shadow: 0 0 0 4rpx rgba(74, 107, 92, 0.15);
}
.progress-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
}
.progress-label {
  font-size: 24rpx;
  color: #9C9585;
}
.progress-value {
  font-size: 24rpx;
  color: #4A6B5C;
  font-weight: 600;
}
</style>