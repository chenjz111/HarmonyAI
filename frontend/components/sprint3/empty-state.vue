<template>
  <view class="ink-empty">
    <view class="ink-empty-mark">
      <text v-if="icon" class="ink-empty-icon">{{ icon }}</text>
      <view v-else class="ink-empty-seal">
        <text class="ink-empty-seal-text">静</text>
      </view>
    </view>
    <text class="ink-empty-title">{{ title }}</text>
    <text v-if="desc" class="ink-empty-desc">{{ desc }}</text>
    <view v-if="actionLabel" class="ink-empty-action">
      <view class="han-btn han-btn-primary ink-btn-action" @click="$emit('action')">
        <text class="ink-btn-text">{{ actionLabel }}</text>
      </view>
    </view>
  </view>
</template>

<script>
/**
 * 空态 v2（水墨国风）
 * 用法：
 *   <empty-state
 *     icon="茶"
 *     title="尚未开始"
 *     desc="你可以从资料或问卷开始"
 *     action-label="开始"
 *     @action="..." />
 */
export default {
  name: 'EmptyState',
  props: {
    icon: { type: String, default: '' },
    title: { type: String, required: true },
    desc: { type: String, default: '' },
    actionLabel: { type: String, default: '' },
  },
  emits: ['action'],
}
</script>

<style scoped>
.ink-empty {
  padding: 96rpx 48rpx;
  text-align: center;
  color: var(--text-muted);
}

.ink-empty-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
}

.ink-empty-icon {
  font-size: 96rpx;
  color: var(--ink-accent-light);
  display: block;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.ink-empty-seal {
  width: 112rpx;
  height: 112rpx;
  border-radius: var(--radius-seal);
  background: var(--paper-card-solid);
  border: 2rpx solid var(--border-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
  transform: rotate(-4deg);
}

.ink-empty-seal-text {
  font-size: 48rpx;
  color: var(--ink-primary);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-weight: 700;
}

.ink-empty-title {
  font-size: 36rpx;
  color: var(--ink-700);
  margin-bottom: 14rpx;
  font-weight: 700;
  display: block;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.1em;
}

.ink-empty-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  display: block;
  margin-bottom: 40rpx;
}

.ink-empty-action {
  display: flex;
  justify-content: center;
}

.han-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.15em;
  border: none;
  padding: 24rpx 56rpx;
  transition: all 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.han-btn-primary {
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  box-shadow: var(--shadow-seal);
}

.han-btn-primary:active {
  background: var(--ink-seal-dark);
  transform: scale(0.98);
}

.ink-btn-action {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
}

.ink-btn-text {
  color: inherit;
}
</style>
