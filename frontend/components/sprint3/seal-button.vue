<template>
  <view
    class="seal-btn"
    :class="[
      shape === 'circle' ? 'seal-circle' : 'seal-square',
      active ? 'seal-active' : '',
      disabled ? 'seal-disabled' : '',
      variant
    ]"
    @click="onClick"
  >
    <text class="seal-text" :class="{ 'seal-text-active': active }">{{ label }}</text>
  </view>
</template>

<script>
/**
 * 印章按钮 v2（水墨国风）
 * 参考 han-design 的 .han-stamp：当代印章徽章，用于选择/标记
 *
 * props:
 *   label: 显示文字（必填，建议 1-2 字）
 *   shape: 'square' (64×64) | 'circle' (80×80)，默认 square
 *   active: 选中态
 *   disabled: 禁用态
 *   variant: '' | 'vermilion' | 'ink' | 'primary'，默认 vermilion 选中色
 * emit: click
 */
export default {
  name: 'SealButton',
  props: {
    label: { type: String, required: true },
    shape: { type: String, default: 'square' },
    active: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    variant: { type: String, default: '' },
  },
  emits: ['click'],
  methods: {
    onClick() {
      if (this.disabled) return
      this.$emit('click')
    },
  },
}
</script>

<style scoped>
.seal-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: var(--paper-card-solid);
  color: var(--ink-700);
  border: 2rpx solid var(--border-soft);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  font-weight: 700;
  transition: all 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.seal-btn::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background:
    radial-gradient(circle at 20% 30%, rgba(255,255,255,0.3) 0%, transparent 25%),
    radial-gradient(circle at 70% 70%, rgba(0,0,0,0.05) 0%, transparent 18%);
  pointer-events: none;
}

.seal-square {
  width: 64rpx;
  height: 64rpx;
  padding: 0;
  border-radius: var(--radius-seal);
  font-size: 26rpx;
}

.seal-circle {
  width: 80rpx;
  height: 80rpx;
  padding: 0;
  border-radius: 50%;
  font-size: 28rpx;
}

.seal-text {
  color: var(--ink-700);
  position: relative;
  z-index: 1;
}

.seal-active {
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-color: var(--ink-seal);
  box-shadow: var(--shadow-seal);
  transform: rotate(-3deg) scale(1.05);
}

.seal-active .seal-text {
  color: var(--text-inverse);
}

.seal-active.seal-circle {
  transform: rotate(-3deg) scale(1.08);
}

.seal-disabled {
  opacity: 0.4;
  pointer-events: none;
}

.seal-btn:active:not(.seal-disabled) {
  transform: scale(0.95);
}

.seal-active:active:not(.seal-disabled) {
  transform: rotate(-3deg) scale(0.98);
}

/* variant: ink 选中态 */
.seal-btn.ink.seal-active {
  background: var(--ink-700);
  border-color: var(--ink-700);
  box-shadow: var(--shadow-sm);
}

/* variant: primary 选中态 */
.seal-btn.primary.seal-active {
  background: var(--ink-primary);
  border-color: var(--ink-primary);
  box-shadow: 0 4rpx 16rpx rgba(107, 124, 94, 0.22);
}
</style>
