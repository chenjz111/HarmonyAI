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
    this.todayDate = `${month}月${day}日 · 星期${week}`
  },
  methods: {
    goWelcome() {
      uni.navigateTo({ url: '/pages/welcome/welcome' })
    },
    goPlayer() {
      uni.switchTab({ url: '/pages/player/player' })
    },
    goWuxing(e) {
      const idx = e.currentTarget.dataset.idx
      uni.showToast({ title: ['角调·疏肝','徵调·养心','宫调·健脾','商调·润肺','羽调·补肾'][idx], icon: 'none' })
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- ====== 背景装饰层（远山 / 飞鸟 / 祥云 / 水墨晕染） ====== -->
    <view class="bg-deco" aria-hidden="true">
      <!-- 水墨晕染圆（右上） -->
      <view class="ink-orb ink-orb-tr"></view>
      <!-- 水墨晕染圆（左下） -->
      <view class="ink-orb ink-orb-bl"></view>
      <!-- 远山轮廓 -->
      <svg class="mountain" viewBox="0 0 750 240" preserveAspectRatio="none">
        <path d="M0,200 C120,140 200,170 300,150 C400,130 480,180 600,160 C680,148 720,170 750,165 L750,240 L0,240 Z" fill="#D8D2C4" opacity="0.55"/>
        <path d="M0,210 C100,180 220,200 340,185 C440,172 520,205 640,195 C700,190 730,200 750,200 L750,240 L0,240 Z" fill="#B8B0A0" opacity="0.45"/>
      </svg>
      <!-- 飞鸟剪影（右上） -->
      <svg class="birds" viewBox="0 0 120 60">
        <path d="M5,40 Q15,30 25,40 M15,40 Q25,32 35,40 M35,42 Q45,34 55,42 M55,38 Q65,28 75,38"
              fill="none" stroke="#6B6862" stroke-width="1.6" stroke-linecap="round" opacity="0.55"/>
        <path d="M70,20 Q78,12 86,20 M80,20 Q88,14 96,20"
              fill="none" stroke="#6B6862" stroke-width="1.4" stroke-linecap="round" opacity="0.4"/>
      </svg>
      <!-- 祥云（左上） -->
      <svg class="cloud cloud-1" viewBox="0 0 100 50">
        <path d="M10,30 Q5,20 18,18 Q22,8 35,12 Q45,5 52,15 Q70,12 72,25 Q88,25 85,35 Q70,42 55,38 Q40,42 25,38 Q12,40 10,30 Z"
              fill="#FCFAF6" opacity="0.7"/>
      </svg>
      <!-- 祥云（右中） -->
      <svg class="cloud cloud-2" viewBox="0 0 80 40">
        <path d="M8,24 Q4,16 16,14 Q20,6 30,10 Q40,4 46,14 Q60,12 62,22 Q74,22 72,30 Q58,36 46,32 Q34,36 22,32 Q10,34 8,24 Z"
              fill="#FCFAF6" opacity="0.55"/>
      </svg>
      <!-- 飘落梅花点 -->
      <view class="petal petal-1">✦</view>
      <view class="petal petal-2">✦</view>
      <view class="petal petal-3">✦</view>
      <view class="petal petal-4">✦</view>
      <view class="petal petal-5">✦</view>
    </view>

    <!-- ====== 顶部欢迎区 ====== -->
    <view class="header">
      <view class="header-text">
        <text class="greeting">你好，{{ userName }}</text>
        <view class="date-row">
          <view class="date-dot"></view>
          <text class="date">{{ todayDate }}</text>
        </view>
      </view>
      <view class="header-avatar">
        <text class="avatar-icon">和</text>
      </view>
    </view>

    <!-- ====== 今日处方卡（如果有） ====== -->
    <view class="prescription-card" v-if="hasPrescription" @click="goPlayer">
      <view class="prescription-header">
        <text class="prescription-title">今日推荐处方</text>
        <view class="prescription-tag">
          <text class="tag-dot"></text>
          <text class="tag-text">AI 定制</text>
        </view>
      </view>
      <view class="prescription-info">
        <view class="info-item">
          <text class="info-label">主调</text>
          <text class="info-value">角调 75%</text>
        </view>
        <view class="info-divider"></view>
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

    <!-- ====== 开始评估入口 ====== -->
    <view class="assess-card" @click="goWelcome">
      <!-- 角落装饰线 -->
      <view class="corner-deco corner-tl"></view>
      <view class="corner-deco corner-br"></view>

      <view class="assess-content">
        <view class="assess-icon">
          <text class="assess-glyph">乐</text>
        </view>
        <view class="assess-text">
          <text class="assess-title">开始健康评估</text>
          <text class="assess-desc">3 分钟问卷 · 获取专属中医音乐调理方案</text>
        </view>
      </view>
      <view class="assess-arrow">
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- ====== 五行五音 ====== -->
    <view class="wuxing-section">
      <view class="section-header">
        <view class="section-title-row">
          <view class="title-bar"></view>
          <text class="section-title">五音疗愈</text>
        </view>
        <text class="section-subtitle">中医五行 · 五音对应五脏</text>
      </view>

      <view class="wuxing-grid">
        <view class="wuxing-item" data-idx="0" @click="goWuxing" hover-class="wuxing-hover">
          <view class="wuxing-bg"></view>
          <text class="wuxing-name">角</text>
          <text class="wuxing-element">木 · 肝</text>
          <text class="wuxing-emotion">疏肝解郁</text>
        </view>
        <view class="wuxing-item" data-idx="1" @click="goWuxing" hover-class="wuxing-hover">
          <view class="wuxing-bg"></view>
          <text class="wuxing-name">徵</text>
          <text class="wuxing-element">火 · 心</text>
          <text class="wuxing-emotion">养心安神</text>
        </view>
        <view class="wuxing-item" data-idx="2" @click="goWuxing" hover-class="wuxing-hover">
          <view class="wuxing-bg"></view>
          <text class="wuxing-name">宫</text>
          <text class="wuxing-element">土 · 脾</text>
          <text class="wuxing-emotion">健脾和胃</text>
        </view>
        <view class="wuxing-item" data-idx="3" @click="goWuxing" hover-class="wuxing-hover">
          <view class="wuxing-bg"></view>
          <text class="wuxing-name">商</text>
          <text class="wuxing-element">金 · 肺</text>
          <text class="wuxing-emotion">润肺清金</text>
        </view>
        <view class="wuxing-item" data-idx="4" @click="goWuxing" hover-class="wuxing-hover">
          <view class="wuxing-bg"></view>
          <text class="wuxing-name">羽</text>
          <text class="wuxing-element">水 · 肾</text>
          <text class="wuxing-emotion">补肾益精</text>
        </view>
      </view>
    </view>

    <!-- ====== 底部寄语 ====== -->
    <view class="footer-quote">
      <view class="quote-line"></view>
      <text class="quote-text">五音疗疾 · 以乐入心</text>
      <view class="quote-line"></view>
    </view>
  </view>
</template>

<style scoped>
.container {
  padding: 30rpx 36rpx 140rpx;
  min-height: 100vh;
  background: #F7F3EB;
  position: relative;
  overflow: hidden;
}

/* ============ 背景装饰层 ============ */
.bg-deco {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.ink-orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
.ink-orb-tr {
  top: -160rpx;
  right: -160rpx;
  width: 480rpx;
  height: 480rpx;
  background: radial-gradient(circle, rgba(200,137,109,0.18) 0%, rgba(200,137,109,0.05) 40%, transparent 70%);
}
.ink-orb-bl {
  bottom: -200rpx;
  left: -180rpx;
  width: 520rpx;
  height: 520rpx;
  background: radial-gradient(circle, rgba(74,107,92,0.12) 0%, rgba(74,107,92,0.04) 40%, transparent 70%);
}
.mountain {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 220rpx;
  width: 100%;
  height: 240rpx;
}
.birds {
  position: absolute;
  top: 60rpx;
  right: 30rpx;
  width: 140rpx;
  height: 70rpx;
  animation: drift 18s ease-in-out infinite;
}
.cloud {
  position: absolute;
  pointer-events: none;
}
.cloud-1 {
  top: 40rpx;
  left: -30rpx;
  width: 160rpx;
  height: 80rpx;
  animation: drift 30s ease-in-out infinite;
}
.cloud-2 {
  top: 380rpx;
  right: -20rpx;
  width: 120rpx;
  height: 60rpx;
  animation: drift 24s ease-in-out infinite reverse;
}
@keyframes drift {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(20rpx); }
}
.petal {
  position: absolute;
  color: #C8896D;
  font-size: 20rpx;
  opacity: 0.5;
  animation: float 12s ease-in-out infinite;
}
.petal-1 { top: 280rpx; left: 60rpx; animation-delay: 0s; }
.petal-2 { top: 520rpx; left: 80%; animation-delay: 2s; }
.petal-3 { top: 720rpx; left: 30%; animation-delay: 4s; }
.petal-4 { top: 880rpx; left: 75%; animation-delay: 6s; }
.petal-5 { top: 380rpx; left: 45%; animation-delay: 8s; }
@keyframes float {
  0%, 100% { transform: translate(0,0) rotate(0); opacity: 0.4; }
  50% { transform: translate(20rpx,-30rpx) rotate(45deg); opacity: 0.7; }
}

/* ============ 顶部欢迎区 ============ */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20rpx 0 36rpx;
  position: relative;
  z-index: 2;
}
.greeting {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  letter-spacing: 0.05em;
}
.date-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 10rpx;
}
.date-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #C8896D;
}
.date {
  font-size: 24rpx;
  color: #6B6862;
  letter-spacing: 0.05em;
}
.header-avatar {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6B5C, #2F4A3D);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.25);
  border: 2rpx solid #FCFAF6;
}
.avatar-icon {
  font-size: 40rpx;
  font-weight: 700;
  color: #FCFAF6;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}

/* ============ 今日处方卡 ============ */
.prescription-card {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  border-radius: 32rpx;
  padding: 36rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 28rpx rgba(74,107,92,0.22);
  position: relative;
  z-index: 2;
  overflow: hidden;
}
.prescription-card::before {
  content: '';
  position: absolute;
  top: -40rpx;
  right: -40rpx;
  width: 200rpx;
  height: 200rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(200,137,109,0.25) 0%, transparent 70%);
}
.prescription-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
  position: relative;
}
.prescription-title {
  font-size: 30rpx;
  color: #FCFAF6;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.prescription-tag {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: rgba(255,255,255,0.15);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}
.tag-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #D4A574;
}
.tag-text {
  font-size: 20rpx;
  color: #FCFAF6;
  letter-spacing: 0.05em;
}
.prescription-info {
  display: flex;
  align-items: center;
  gap: 32rpx;
  margin-bottom: 24rpx;
  position: relative;
}
.info-item {
  display: flex;
  flex-direction: column;
}
.info-divider {
  width: 1rpx;
  height: 48rpx;
  background: rgba(252,250,246,0.25);
}
.info-label {
  font-size: 22rpx;
  color: rgba(252,250,246,0.7);
  margin-bottom: 4rpx;
  letter-spacing: 0.05em;
}
.info-value {
  font-size: 32rpx;
  color: #FCFAF6;
  font-weight: 600;
  font-family: Georgia, serif;
}
.play-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  background: rgba(252,250,246,0.18);
  border-radius: 40rpx;
  padding: 18rpx 0;
  position: relative;
}
.play-btn-text {
  color: #FCFAF6;
  font-size: 28rpx;
  font-weight: 500;
  letter-spacing: 0.05em;
}
.play-btn-arrow {
  color: #FCFAF6;
  font-size: 32rpx;
}

/* ============ 开始评估入口 ============ */
.assess-card {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 36rpx 32rpx;
  margin-bottom: 36rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74,107,92,0.08);
  z-index: 2;
}
.corner-deco {
  position: absolute;
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid #C8896D;
}
.corner-tl {
  top: 16rpx;
  left: 16rpx;
  border-right: none;
  border-bottom: none;
}
.corner-br {
  bottom: 16rpx;
  right: 16rpx;
  border-left: none;
  border-top: none;
}
.assess-content {
  display: flex;
  align-items: center;
  gap: 24rpx;
  flex: 1;
}
.assess-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 28rpx;
  background: linear-gradient(135deg, #4A6B5C, #2F4A3D);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 14rpx rgba(74,107,92,0.25);
  position: relative;
}
.assess-icon::before {
  content: '';
  position: absolute;
  inset: 4rpx;
  border-radius: 24rpx;
  border: 1rpx solid rgba(252,250,246,0.2);
}
.assess-glyph {
  font-size: 44rpx;
  font-weight: 700;
  color: #FCFAF6;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.assess-text {
  flex: 1;
}
.assess-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  letter-spacing: 0.05em;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.assess-desc {
  font-size: 24rpx;
  color: #6B6862;
  margin-top: 8rpx;
  display: block;
  letter-spacing: 0.03em;
}
.assess-arrow {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: #EEF1ED;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1rpx solid #E8E2D5;
}
.arrow {
  font-size: 36rpx;
  color: #4A6B5C;
  font-weight: 400;
}

/* ============ 五行五音 ============ */
.wuxing-section {
  position: relative;
  z-index: 2;
}
.section-header {
  margin-bottom: 28rpx;
}
.section-title-row {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 8rpx;
}
.title-bar {
  width: 8rpx;
  height: 32rpx;
  border-radius: 4rpx;
  background: linear-gradient(180deg, #4A6B5C, #C8896D);
}
.section-title {
  font-size: 34rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.1em;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
.section-subtitle {
  font-size: 24rpx;
  color: #9C9585;
  letter-spacing: 0.1em;
  margin-left: 22rpx;
}
.wuxing-grid {
  display: flex;
  justify-content: space-between;
  gap: 10rpx;
}
.wuxing-item {
  flex: 1;
  border-radius: 28rpx;
  padding: 32rpx 0;
  text-align: center;
  position: relative;
  overflow: hidden;
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 18rpx rgba(74,107,92,0.08);
  transition: transform 0.2s;
}
.wuxing-bg {
  position: absolute;
  inset: 0;
  opacity: 0.85;
}
.wuxing-item[data-idx="0"] .wuxing-bg {
  background: linear-gradient(160deg, rgba(122,154,126,0.55) 0%, rgba(74,107,92,0.7) 100%);
}
.wuxing-item[data-idx="1"] .wuxing-bg {
  background: linear-gradient(160deg, rgba(212,165,116,0.5) 0%, rgba(200,137,109,0.7) 100%);
}
.wuxing-item[data-idx="2"] .wuxing-bg {
  background: linear-gradient(160deg, rgba(212,176,131,0.5) 0%, rgba(180,140,90,0.65) 100%);
}
.wuxing-item[data-idx="3"] .wuxing-bg {
  background: linear-gradient(160deg, rgba(200,193,178,0.6) 0%, rgba(160,150,130,0.7) 100%);
}
.wuxing-item[data-idx="4"] .wuxing-bg {
  background: linear-gradient(160deg, rgba(122,148,162,0.5) 0%, rgba(74,107,138,0.65) 100%);
}
.wuxing-name {
  font-size: 44rpx;
  font-weight: 700;
  display: block;
  color: #FCFAF6;
  font-family: 'Kaiti SC', 'STKaiti', serif;
  letter-spacing: 0.05em;
  position: relative;
  text-shadow: 0 2rpx 8rpx rgba(0,0,0,0.18);
}
.wuxing-element {
  font-size: 20rpx;
  display: block;
  margin-top: 6rpx;
  color: rgba(252,250,246,0.92);
  letter-spacing: 0.08em;
  position: relative;
}
.wuxing-emotion {
  font-size: 18rpx;
  display: block;
  margin-top: 10rpx;
  color: rgba(252,250,246,0.78);
  letter-spacing: 0.05em;
  position: relative;
  font-style: italic;
}
.wuxing-hover {
  transform: translateY(-4rpx) scale(1.02);
}

/* ============ 底部寄语 ============ */
.footer-quote {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  margin-top: 56rpx;
  position: relative;
  z-index: 2;
}
.quote-line {
  flex: 1;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, #C8896D, transparent);
  max-width: 160rpx;
}
.quote-text {
  font-size: 26rpx;
  color: #6B6862;
  letter-spacing: 0.3em;
  font-family: 'Kaiti SC', 'STKaiti', serif;
}
</style>