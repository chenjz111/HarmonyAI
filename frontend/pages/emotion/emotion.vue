<script>
export default {
  data() {
    return {
      emotions: [
        { id: 'nu', name: '怒', element: '木', tone: '角', color: '#4A9D6E', desc: '烦躁易怒、胸闷胁痛', bg: '#E1F5EE' },
        { id: 'xi', name: '喜', element: '火', tone: '徵', color: '#E25C4E', desc: '亢奋失眠、心悸不安', bg: '#FAECE7' },
        { id: 'si', name: '思', element: '土', tone: '宫', color: '#E8B547', desc: '思虑过度、食欲不振', bg: '#FAEEDA' },
        { id: 'bei', name: '悲', element: '金', tone: '商', color: '#9CA8B8', desc: '情绪低落、气短乏力', bg: '#F1EFE8' },
        { id: 'kong', name: '恐', element: '水', tone: '羽', color: '#3B5067', desc: '焦虑恐惧、腰膝酸软', bg: '#E6F1FB' }
      ],
      selectedId: ''
    }
  },
  methods: {
    selectEmotion(item) {
      this.selectedId = item.id
      // 短暂延迟后跳转到问卷页，让用户看到选中效果
      setTimeout(() => {
        uni.navigateTo({
          url: `/pages/survey/survey?emotion=${item.id}&tone=${item.tone}`
        })
      }, 300)
    }
  }
}
</script>

<template>
  <view class="container">
    <!-- 顶部标题 -->
    <view class="header">
      <text class="title">你现在的感受是？</text>
      <text class="subtitle">选择最符合你当前状态的情绪，AI 将为你定制调理方案</text>
    </view>

    <!-- 情绪列表 -->
    <view class="emotion-list">
      <view
        v-for="item in emotions"
        :key="item.id"
        class="emotion-card"
        :class="{ active: selectedId === item.id }"
        :style="{ background: item.bg, borderColor: selectedId === item.id ? item.color : 'transparent' }"
        @click="selectEmotion(item)"
      >
        <view class="emotion-left" :style="{ background: item.color }">
          <text class="emotion-name">{{ item.name }}</text>
          <text class="emotion-tone">{{ item.tone }}调</text>
        </view>
        <view class="emotion-right">
          <view class="emotion-meta">
            <text class="emotion-element">{{ item.element }}行</text>
            <text class="emotion-divider">·</text>
            <text class="emotion-tone-name">{{ item.tone }}调</text>
          </view>
          <text class="emotion-desc">{{ item.desc }}</text>
        </view>
        <view class="emotion-check" v-if="selectedId === item.id">
          <text class="check-icon">✓</text>
        </view>
      </view>
    </view>

    <!-- 底部提示 -->
    <view class="tip">
      <text class="tip-icon">ℹ️</text>
      <text class="tip-text">选择后将进入 30 题健康评估问卷（约 3 分钟）</text>
    </view>
  </view>
</template>

<style scoped>
.container {
  padding: 30rpx;
  padding-bottom: 120rpx;
  min-height: 100vh;
  background: #F8F8F8;
}

.header {
  margin-bottom: 40rpx;
}
.title {
  font-size: 40rpx;
  font-weight: 600;
  color: #2C2C2A;
  display: block;
}
.subtitle {
  font-size: 24rpx;
  color: #888780;
  margin-top: 12rpx;
  display: block;
  line-height: 1.5;
}

.emotion-list {
  margin-top: 10rpx;
}

.emotion-card {
  display: flex;
  align-items: center;
  border-radius: 24rpx;
  border: 4rpx solid transparent;
  margin-bottom: 24rpx;
  overflow: hidden;
  transition: all 0.2s;
  position: relative;
}
.emotion-card.active {
  transform: scale(0.98);
  box-shadow: 0 8rpx 30rpx rgba(0,0,0,0.08);
}

.emotion-left {
  width: 140rpx;
  padding: 40rpx 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.emotion-name {
  font-size: 48rpx;
  font-weight: 600;
  color: #fff;
}
.emotion-tone {
  font-size: 22rpx;
  color: rgba(255,255,255,0.8);
  margin-top: 8rpx;
}

.emotion-right {
  flex: 1;
  padding: 0 30rpx;
}
.emotion-meta {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 8rpx;
}
.emotion-element {
  font-size: 28rpx;
  font-weight: 600;
  color: #2C2C2A;
}
.emotion-divider {
  font-size: 24rpx;
  color: #B4B2A9;
}
.emotion-tone-name {
  font-size: 26rpx;
  color: #5F5E5A;
}
.emotion-desc {
  font-size: 24rpx;
  color: #888780;
  display: block;
  line-height: 1.4;
}

.emotion-check {
  position: absolute;
  right: 24rpx;
  top: 50%;
  transform: translateY(-50%);
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: #534AB7;
  display: flex;
  align-items: center;
  justify-content: center;
}
.check-icon {
  color: #fff;
  font-size: 24rpx;
  font-weight: 600;
}

.tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  margin-top: 30rpx;
  padding: 20rpx;
  background: #fff;
  border-radius: 16rpx;
}
.tip-icon {
  font-size: 24rpx;
}
.tip-text {
  font-size: 24rpx;
  color: #B4B2A9;
}
</style>
