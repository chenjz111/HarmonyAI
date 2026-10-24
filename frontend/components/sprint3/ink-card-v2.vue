<template>
  <view
    class="ink-card-v2-wrapper"
    :class="[
      variant ? `card-${variant}` : '',
      noCorner ? 'no-corner' : ''
    ]"
    @click="$emit('click')"
  >
    <view v-if="title || hint || $slots.header" class="card-head">
      <view class="card-title-wrap">
        <text v-if="title" class="card-title">{{ title }}</text>
        <slot name="header" />
      </view>
      <text v-if="hint" class="card-hint">{{ hint }}</text>
    </view>
    <slot />
  </view>
</template>

<script>
/**
 * 宣纸卡片 v2（水墨国风）
 * 半透明纸面 + 角花 + 左侧色边
 *
 * variant:
 *   - default: 默认宣纸底
 *   - seal: 左侧朱砂色边
 *   - ink: 左侧墨色边
 *   - primary: 左侧茶绿色边
 * props:
 *   title: 卡片标题
 *   hint: 右侧辅助说明
 *   variant: 边色变体
 *   noCorner: 不显示角花
 * emit: click
 */
export default {
  name: 'InkCardV2',
  props: {
    title: { type: String, default: '' },
    hint: { type: String, default: '' },
    variant: { type: String, default: '' },
    noCorner: { type: Boolean, default: false },
  },
  emits: ['click'],
}
</script>

<style scoped>
.ink-card-v2-wrapper {
  position: relative;
  background: var(--paper-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  border: 1rpx solid var(--border-soft);
  padding: 36rpx 32rpx;
  margin-bottom: 24rpx;
  transition: box-shadow 0.25s ease-out, transform 0.25s ease-out;
  backdrop-filter: blur(8rpx);
}

.ink-card-v2-wrapper:not(.no-corner)::before,
.ink-card-v2-wrapper:not(.no-corner)::after {
  content: "";
  position: absolute;
  width: 24rpx;
  height: 24rpx;
  background-repeat: no-repeat;
  background-size: contain;
  opacity: 0.32;
}

.ink-card-v2-wrapper:not(.no-corner)::before {
  top: 16rpx;
  left: 16rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.ink-card-v2-wrapper:not(.no-corner)::after {
  bottom: 16rpx;
  right: 16rpx;
  transform: rotate(180deg);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.ink-card-v2-wrapper.card-seal { border-left: 5rpx solid var(--ink-seal); }
.ink-card-v2-wrapper.card-ink  { border-left: 5rpx solid var(--ink-700); }
.ink-card-v2-wrapper.card-primary { border-left: 5rpx solid var(--ink-primary); }

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.card-title-wrap {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.card-title {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.05em;
}

.card-hint {
  font-size: 24rpx;
  color: var(--text-muted);
  font-family: var(--font-sans);
}
</style>
