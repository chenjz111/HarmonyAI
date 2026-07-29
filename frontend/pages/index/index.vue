<script>
export default {
  data() {
    return {
      userName: '用户',
      todayDate: '',
      hasPrescription: false,
      todayPrescription: null
    }
  },
  onLoad() {
    const now = new Date()
    const month = now.getMonth() + 1
    const day = now.getDate()
    const weekDays = ['日', '一', '二', '三', '四', '五', '六']
    const week = weekDays[now.getDay()]
    this.todayDate = `${month}月${day}日 星期${week}`
  },
  methods: {
    goEmotion() {
      uni.navigateTo({ url: '/pages/emotion/emotion' })
    },
    goPlayer() {
      uni.switchTab({ url: '/pages/player/player' })
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- 顶部欢迎区 -->
    <view class="header">
      <view class="header-text">
        <text class="greeting">你好，{{ userName }}</text>
        <text class="date">{{ todayDate }}</text>
      </view>
      <view class="header-avatar">
        <text class="avatar-icon">🌿</text>
      </view>
    </view>

    <!-- 今日推荐（如果有处方的话） -->
    <view class="prescription-card" v-if="hasPrescription" @click="goPlayer">
      <view class="prescription-header">
        <text class="prescription-title">今日推荐处方</text>
        <text class="prescription-tag">AI 定制</text>
      </view>
      <view class="prescription-info">
        <view class="info-item">
          <text class="info-label">主调</text>
          <text class="info-value">角调 75%</text>
        </view>
        <view class="info-item">
          <text class="info-label">乐器</text>
          <text class="info-value">古筝</text>
        </view>
      </view>
      <view class="play-btn">
        <text class="play-btn-text">立即聆听</text>
        <text class="play-btn-arrow">›</text>
      </view>
    </view>

    <!-- 开始评估入口 -->
    <view class="assess-card" @click="goEmotion">
      <view class="assess-content">
        <view class="assess-icon">
          <text class="assess-emoji">🎧</text>
        </view>
        <view class="assess-text">
          <text class="assess-title">开始健康评估</text>
          <text class="assess-desc">3 分钟问卷，获取专属中医音乐调理方案</text>
        </view>
      </view>
      <view class="assess-arrow">
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- 五行五音简介 -->
    <view class="wuxing-section">
      <view class="section-header">
        <text class="section-title">五音疗愈</text>
        <text class="section-subtitle">中医五行 · 五音对应五脏</text>
      </view>
      <view class="wuxing-grid">
        <view class="wuxing-item" style="background: #4A9D6E">
          <text class="wuxing-name">角</text>
          <text class="wuxing-element">木 · 肝</text>
        </view>
        <view class="wuxing-item" style="background: #E25C4E">
          <text class="wuxing-name">徵</text>
          <text class="wuxing-element">火 · 心</text>
        </view>
        <view class="wuxing-item" style="background: #E8B547">
          <text class="wuxing-name">宫</text>
          <text class="wuxing-element">土 · 脾</text>
        </view>
        <view class="wuxing-item" style="background: #B8C5D6">
          <text class="wuxing-name">商</text>
          <text class="wuxing-element">金 · 肺</text>
        </view>
        <view class="wuxing-item" style="background: #3B5067">
          <text class="wuxing-name">羽</text>
          <text class="wuxing-element">水 · 肾</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.container {
  padding: 20rpx 30rpx;
  padding-bottom: 120rpx;
  min-height: 100vh;
  background: #F8F8F8;
}

/* 顶部欢迎区 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 30rpx 0;
}
.greeting {
  font-size: 40rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
}
.date {
  font-size: 24rpx;
  color: #888780;
  margin-top: 8rpx;
  display: block;
}
.header-avatar {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  background: #EEEDFE;
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-icon {
  font-size: 40rpx;
}

/* 今日推荐处方卡片 */
.prescription-card {
  background: linear-gradient(135deg, #534AB7, #7F77DD);
  border-radius: 28rpx;
  padding: 36rpx;
  margin-bottom: 24rpx;
}
.prescription-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}
.prescription-title {
  font-size: 28rpx;
  color: #fff;
  opacity: 0.9;
}
.prescription-tag {
  font-size: 20rpx;
  color: #fff;
  background: rgba(255,255,255,0.2);
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
}
.prescription-info {
  display: flex;
  gap: 40rpx;
  margin-bottom: 24rpx;
}
.info-item {
  display: flex;
  flex-direction: column;
}
.info-label {
  font-size: 22rpx;
  color: rgba(255,255,255,0.6);
  margin-bottom: 4rpx;
}
.info-value {
  font-size: 32rpx;
  color: #fff;
  font-weight: 600;
}
.play-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.2);
  border-radius: 40rpx;
  padding: 18rpx 0;
}
.play-btn-text {
  color: #fff;
  font-size: 28rpx;
  font-weight: 500;
}
.play-btn-arrow {
  color: #fff;
  font-size: 32rpx;
  margin-left: 8rpx;
}

/* 开始评估入口卡片 */
.assess-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 24rpx;
  padding: 30rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
.assess-content {
  display: flex;
  align-items: center;
  gap: 24rpx;
  flex: 1;
}
.assess-icon {
  width: 88rpx;
  height: 88rpx;
  border-radius: 24rpx;
  background: #E1F5EE;
  display: flex;
  align-items: center;
  justify-content: center;
}
.assess-emoji {
  font-size: 44rpx;
}
.assess-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
}
.assess-desc {
  font-size: 24rpx;
  color: #888780;
  margin-top: 6rpx;
  display: block;
}
.assess-arrow {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: #F1EFE8;
  display: flex;
  align-items: center;
  justify-content: center;
}
.arrow {
  font-size: 36rpx;
  color: #534AB7;
  font-weight: 600;
}

/* 五行五音区域 */
.wuxing-section {
  margin-top: 10rpx;
}
.section-header {
  margin-bottom: 20rpx;
}
.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
}
.section-subtitle {
  font-size: 22rpx;
  color: #888780;
  margin-top: 4rpx;
  display: block;
}
.wuxing-grid {
  display: flex;
  justify-content: space-between;
  gap: 12rpx;
}
.wuxing-item {
  flex: 1;
  border-radius: 20rpx;
  padding: 28rpx 0;
  text-align: center;
}
.wuxing-name {
  color: #fff;
  font-size: 36rpx;
  font-weight: 600;
  display: block;
}
.wuxing-element {
  color: rgba(255,255,255,0.75);
  font-size: 20rpx;
  display: block;
  margin-top: 6rpx;
}
</style>
