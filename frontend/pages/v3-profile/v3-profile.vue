<template>
  <view class="profile-page v31-mobile-page">
    <view class="profile-orb"><text class="profile-glyph">和</text></view>
    <text class="profile-brand">HarmonyAI</text>
    <text class="profile-title">功能升级中</text>
    <text class="profile-copy">个人记录、收藏与偏好管理将在后续版本开放。</text>
    <view class="profile-action" @click="goHome"><text>先回首页</text></view>
  </view>
</template>

<script>
export default {
  methods: {
    goHome() {
      uni.switchTab({ url: "/pages/entry/entry" })
    },
  },
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  box-sizing: border-box;
  padding: calc(160rpx + env(safe-area-inset-top)) 48rpx 180rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  background:
    radial-gradient(circle at 75% 12%, rgba(241, 188, 159, 0.28), transparent 22%),
    linear-gradient(180deg, #fbfaf4 0%, #eff8f3 100%);
}
.profile-orb { width: 152rpx; height: 152rpx; border-radius: 44rpx; display: flex; align-items: center; justify-content: center; background: linear-gradient(145deg, #62d4af, #087c64); box-shadow: 0 24rpx 52rpx rgba(18, 111, 88, .22); }
.profile-glyph { color: white; font-size: 76rpx; font-family: "STKaiti", serif; }
.profile-brand { margin-top: 30rpx; color: #0b4f47; font-size: 36rpx; font-weight: 700; letter-spacing: .08em; }
.profile-title { margin-top: 96rpx; color: #083f3c; font-family: "STKaiti", serif; font-size: 54rpx; font-weight: 700; }
.profile-copy { max-width: 560rpx; margin-top: 24rpx; color: #657a76; font-size: 27rpx; line-height: 1.8; }
.profile-action { margin-top: 64rpx; width: 420rpx; min-height: 92rpx; border-radius: 999rpx; display: flex; align-items: center; justify-content: center; color: white; background: linear-gradient(135deg, #4d9d83, #176956); font-size: 30rpx; font-weight: 600; box-shadow: 0 16rpx 36rpx rgba(23, 105, 86, .2); }
</style>
