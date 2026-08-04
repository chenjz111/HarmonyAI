<template>
  <view class="container">
    <!-- 顶部标题 -->
    <view class="header">
      <text class="step-tag">第 2 步 · 选填</text>
      <text class="page-title">最近，发生了什么？</text>
      <text class="page-subtitle">用一段话描述你近期的情绪、睡眠或身体状况，字数不限；没有也可直接跳过。</text>
    </view>

    <progress-bar :progress="50" label="评估进度" />

    <!-- 输入卡 -->
    <view class="narrative-card">
      <textarea
        class="narrative-area"
        v-model="narrativeText"
        placeholder="例如：最近工作压力大，晚上经常睡不着，容易烦躁..."
        maxlength="300"
        :disable-default-padding="true"
      />
      <view class="narrative-meta">
        <view class="narrative-tags-inline">
          <text class="tag-dot">·</text>
          <text class="tag-hint">自由书写，不打分不评判</text>
        </view>
        <view class="count-ring" :class="{ active: narrativeText.length > 0 }">
          <text class="count-text">{{ narrativeText.length }}</text>
          <text class="count-divider">/</text>
          <text class="count-max">300</text>
        </view>
      </view>
    </view>

    <!-- 快捷标签 -->
    <view class="prompts">
      <view class="prompts-header">
        <text class="prompts-title">快捷输入</text>
        <text class="prompts-sub">点击填充</text>
      </view>
      <view class="prompt-tags">
        <view
          class="prompt-tag"
          v-for="(tag, index) in prompts"
          :key="index"
          @click="usePrompt(tag)"
        >
          <text class="prompt-tag-text">{{ tag }}</text>
        </view>
      </view>
    </view>

    <error-state
      v-if="status === 'error'"
      title="提交失败"
      :message="errorMsg"
      :showFallback="true"
      fallbackText="跳过此步"
      @retry="next"
      @fallback="skip"
    />

    <!-- 底部按钮 -->
    <view class="btn-group">
      <view class="btn btn-secondary" @click="skip">
        <text class="btn-text">跳过</text>
      </view>
      <view class="btn btn-primary" @click="next">
        <text class="btn-text">继续</text>
        <text class="btn-arrow">→</text>
      </view>
    </view>
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { updateSprint3Session } from '@/common/sprint3-session.js'

export default {
  components: { ProgressBar, ErrorState },
  data() {
    return {
      narrativeText: '',
      prompts: [
        '最近失眠多梦',
        '工作压力大、容易紧张',
        '情绪低落、提不起劲',
        '最近容易烦躁',
        '食欲不振、消化不适',
        '白天疲惫、没有精神'
      ],
      status: 'idle',
      errorMsg: ''
    }
  },
  methods: {
    usePrompt(text) {
      this.narrativeText = text
      uni.showToast({ title: '已填充，可继续编辑', icon: 'none', duration: 1200 })
    },
    skip() {
      updateSprint3Session({ narrative_text: null, narrative_skipped: true })
      uni.navigateTo({ url: '/pages/survey-v2/survey-v2' })
    },
    next() {
      const text = this.narrativeText.trim()
      if (!text) return this.skip()
      updateSprint3Session({ narrative_text: text, narrative_skipped: false })
      uni.navigateTo({ url: '/pages/survey-v2/survey-v2' })
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #F7F3EB;
  padding: 40rpx 40rpx 200rpx;
  box-sizing: border-box;
}

/* 顶部 */
.header { margin-bottom: 32rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4A6B5C;
  background: #EEF1ED;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  letter-spacing: 0.1em;
  margin-bottom: 16rpx;
}
.page-title {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.03em;
  display: block;
  margin-bottom: 12rpx;
}
.page-subtitle {
  font-size: 26rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
}

/* 输入卡 */
.narrative-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
  margin-bottom: 32rpx;
}
.narrative-area {
  width: 100%;
  min-height: 280rpx;
  background: transparent;
  font-size: 28rpx;
  color: #2C2A28;
  line-height: 1.8;
  box-sizing: border-box;
  letter-spacing: 0.02em;
}
.narrative-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx dashed #E8E2D5;
}
.narrative-tags-inline {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.tag-dot {
  color: #C8896D;
  font-size: 24rpx;
  font-weight: 700;
}
.tag-hint {
  font-size: 22rpx;
  color: #9C9585;
}
.count-ring {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
  padding: 6rpx 16rpx;
  border-radius: 24rpx;
  background: #F7F3EB;
  transition: all 0.2s;
}
.count-ring.active {
  background: #EEF1ED;
}
.count-text {
  font-size: 24rpx;
  color: #4A6B5C;
  font-weight: 700;
}
.count-divider {
  font-size: 20rpx;
  color: #9C9585;
}
.count-max {
  font-size: 20rpx;
  color: #9C9585;
}

/* 快捷标签 */
.prompts { margin-bottom: 32rpx; }
.prompts-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.prompts-title {
  font-size: 26rpx;
  color: #2C2A28;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.prompts-sub {
  font-size: 22rpx;
  color: #9C9585;
}
.prompt-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.prompt-tag {
  padding: 16rpx 28rpx;
  border-radius: 36rpx;
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
  transition: all 0.2s;
}
.prompt-tag:active {
  background: #EEF1ED;
  border-color: #4A6B5C;
  transform: scale(0.96);
}
.prompt-tag-text {
  font-size: 26rpx;
  color: #4A6B5C;
  font-weight: 500;
  letter-spacing: 0.02em;
}

/* 底部按钮 */
.btn-group {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 20rpx;
  padding: 24rpx 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: rgba(247, 243, 235, 0.95);
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border-top: 1rpx solid #E8E2D5;
  box-sizing: border-box;
}
.btn {
  flex: 1;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  transition: all 0.2s;
}
.btn:active { transform: scale(0.98); }
.btn-primary {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.20);
}
.btn-primary .btn-text {
  color: #F7F3EB;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.btn-arrow {
  font-size: 30rpx;
  color: #F7F3EB;
  font-weight: 500;
}
.btn-secondary {
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
}
.btn-secondary .btn-text {
  color: #4A6B5C;
  font-size: 30rpx;
  font-weight: 600;
}
</style>