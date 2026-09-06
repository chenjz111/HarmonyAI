<template>
  <view class="page-header">
    <view v-if="back" class="back-btn" @click="onBack">
      <text class="back-text">‹</text>
    </view>
    <view class="title-area">
      <view class="title-row">
        <text class="page-title">{{ title }}</text>
        <text v-if="seal" class="title-seal">{{ seal }}</text>
      </view>
      <text v-if="subtitle" class="page-subtitle">{{ subtitle }}</text>
    </view>
    <view v-if="$slots.action" class="header-action">
      <slot name="action" />
    </view>
  </view>
  <view v-if="!noDivider" class="han-divider" :class="seal ? 'han-divider--seal' : ''" />
</template>

<script>
/**
 * 页面标题栏 v2（水墨国风）
 * 毛笔楷体标题 + 可选朱砂印章 + 墨线分隔
 *
 * props:
 *   title: 页面标题（必填）
 *   subtitle: 副标题
 *   back: 是否显示返回按钮
 *   noDivider: 不显示分割线
 *   seal: 标题旁印章文字（1 字）
 * emit: back
 */
export default {
  name: 'PageHeader',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    back: { type: Boolean, default: false },
    noDivider: { type: Boolean, default: false },
    seal: { type: String, default: '' },
  },
  emits: ['back'],
  methods: {
    onBack() {
      this.$emit('back')
    },
  },
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  padding: 32rpx 0 20rpx;
  gap: 16rpx;
}

.back-btn {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: rgba(107, 124, 94, 0.10);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 6rpx;
}

.back-text {
  font-size: 44rpx;
  color: var(--ink-primary);
  font-weight: 300;
  line-height: 1;
}

.title-area {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.title-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
}

.page-title {
  font-size: 48rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.1em;
  line-height: 1.25;
}

.title-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40rpx;
  height: 40rpx;
  padding: 0 8rpx;
  background: var(--ink-seal);
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 22rpx;
  font-weight: 700;
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  box-shadow: var(--shadow-seal);
  margin-top: 4rpx;
}

.page-subtitle {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-top: 10rpx;
  line-height: 1.6;
  font-family: var(--font-sans);
}

.header-action {
  flex-shrink: 0;
}

.han-divider {
  height: 1rpx;
  background: linear-gradient(90deg, transparent, var(--divider-ink), transparent);
  margin: 0 0 28rpx;
}

.han-divider--seal::after {
  content: "";
  display: block;
  width: 14rpx;
  height: 14rpx;
  margin: -7rpx auto 0;
  background: var(--ink-seal);
  border-radius: 2rpx;
  transform: rotate(45deg);
}
</style>
