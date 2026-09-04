<template>
  <view class="container">
    <view class="ink-card card">
      <text class="title">想再补充一些近况吗？</text>
      <text class="desc">页面准备中，请稍后再试。</text>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {}
  },
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 120rpx 48rpx;
  box-sizing: border-box;
}
.card {
  padding: 48rpx 40rpx;
}
.title {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 16rpx;
}
.desc {
  display: block;
  font-size: 28rpx;
  color: #6b6862;
  line-height: 1.6;
}
</style>
