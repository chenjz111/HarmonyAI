<script>
export default {
  data() {
    return {
      emotions: [
        { id: 'nu', name: '怒', element: '木', tone: '角', color: '#52B788', desc: '烦躁易怒、胸闷胁痛', bg: '#E8F8F0' },
        { id: 'xi', name: '喜', element: '火', tone: '徵', color: '#F26C5C', desc: '亢奋失眠、心悸不安', bg: '#FFF0F0' },
        { id: 'si', name: '思', element: '土', tone: '宫', color: '#F0C75E', desc: '思虑过度、食欲不振', bg: '#FFF8E8' },
        { id: 'bei', name: '悲', element: '金', tone: '商', color: '#A8B8CC', desc: '情绪低落、气短乏力', bg: '#F0F2F5' },
        { id: 'kong', name: '恐', element: '水', tone: '羽', color: '#4A6FA5', desc: '焦虑恐惧、腰膝酸软', bg: '#E8F0FC' }
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
      <view class="tip-icon-circle"><text class="tip-icon-text">i</text></view>
      <text class="tip-text">选择后将进入 30 题健康评估问卷（约 3 分钟）</text>
    </view>
  </view>
</template>

<style scoped>
.container {
  padding: 30rpx;
  padding-bottom: 120rpx;
  min-height: 100vh;
  background: #F5F6FA;
}

.header {
  margin-bottom: 40rpx;
}
.title {
  font-size: 40rpx;
  font-weight: 700;
  color: #1A1A2E;
  display: block;
}
.subtitle {
  font-size: 24rpx;
  color: #9E9EB8;
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
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.06);
}
.emotion-card.active {
  transform: scale(0.98);
  box-shadow: 0 8rpx 30rpx rgba(0,0,0,0.1);
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
  font-weight: 700;
  color: #fff;
  text-shadow: 0 2rpx 8rpx rgba(0,0,0,0.15);
}
.emotion-tone {
  font-size: 22rpx;
  color: rgba(255,255,255,0.85);
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
  font-weight: 700;
  color: #1A1A2E;
}
.emotion-divider {
  font-size: 24rpx;
  color: #BFBFCF;
}
.emotion-tone-name {
  font-size: 26rpx;
  color: #9E9EB8;
}
.emotion-desc {
  font-size: 24rpx;
  color: #9E9EB8;
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
  background: #6C63FF;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 12rpx rgba(108,99,255,0.3);
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
  gap: 12rpx;
  margin-top: 30rpx;
  padding: 20rpx;
  background: #fff;
  border-radius: 16rpx;
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.06);
}
.tip-icon-circle {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: #F0F0FF;
  display: flex;
  align-items: center;
  justify-content: center;
}
.tip-icon-text {
  font-size: 24rpx;
  font-weight: 700;
  color: #6C63FF;
  font-style: italic;
}
.tip-text {
  font-size: 24rpx;
  color: #9E9EB8;
}
</style>
