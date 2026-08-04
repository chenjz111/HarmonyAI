<template>
  <view class="image-choice">
    <text class="question-text">{{ question }}</text>
    <view class="choice-grid" :class="'cols-' + columns">
      <view
        class="choice-item"
        v-for="(item, index) in options"
        :key="index"
        :class="{ selected: value === item.value }"
        @click="select(item.value)"
      >
        <view class="choice-icon" :style="{ background: item.bgColor }">
          <text class="choice-icon-text" :style="{ color: item.color }">{{ item.icon }}</text>
        </view>
        <text class="choice-label">{{ item.label }}</text>
        <view class="choice-check" v-if="value === item.value">
          <text class="check-icon">✓</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ImageChoice',
  props: {
    question: { type: String, required: true },
    options: { type: Array, default: () => [] },
    value: { type: [String, Number], default: null },
    columns: { type: Number, default: 2 }  // 2 或 3 列
  },
  methods: {
    select(val) {
      this.$emit('change', val)
    }
  }
}
</script>

<style scoped>
.image-choice {
  background: transparent;
}
.question-text {
  font-size: 32rpx;
  color: #2C2A28;
  font-weight: 600;
  display: block;
  margin-bottom: 36rpx;
  line-height: 1.6;
  letter-spacing: 0.02em;
}
.choice-grid {
  display: grid;
  gap: 24rpx;
}
.cols-2 { grid-template-columns: repeat(2, 1fr); }
.cols-3 { grid-template-columns: repeat(3, 1fr); }
.cols-5 {
  grid-template-columns: repeat(5, 1fr);
  gap: 16rpx;
}
.choice-item {
  background: #FCFAF6;
  border-radius: 28rpx;
  padding: 36rpx 20rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 2rpx solid #E8E2D5;
  position: relative;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.choice-item:active {
  transform: scale(0.96);
}
.choice-item.selected {
  border-color: #4A6B5C;
  background: #EEF1ED;
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.15);
}
.cols-5 .choice-item {
  padding: 24rpx 8rpx;
}
.choice-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16rpx;
}
.cols-5 .choice-icon {
  width: 80rpx;
  height: 80rpx;
}
.choice-icon-text {
  font-size: 48rpx;
  font-weight: 600;
  font-family: Georgia, 'PingFang SC', sans-serif;
}
.cols-5 .choice-icon-text {
  font-size: 36rpx;
}
.choice-label {
  font-size: 26rpx;
  color: #2C2A28;
  font-weight: 500;
  text-align: center;
  letter-spacing: 0.02em;
}
.cols-5 .choice-label {
  font-size: 22rpx;
}
.choice-item.selected .choice-label {
  color: #4A6B5C;
  font-weight: 600;
}
.choice-check {
  position: absolute;
  top: 16rpx;
  right: 16rpx;
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: #4A6B5C;
  display: flex;
  align-items: center;
  justify-content: center;
}
.check-icon {
  color: #FCFAF6;
  font-size: 22rpx;
  font-weight: 700;
}
</style>