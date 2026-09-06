<script>
/**
 * 左侧印章导航（重水墨国风 · 统一切换区）
 *
 * 5 枚印章对应 V3.1 五阶段：入静 / 呈声 / 问询 / 确认 / 聆听
 * 页面归属：
 *   入  welcome
 *   声  v3-material / v3-summary
 *   问  v3-narrative / v3-supplement / v3-questionnaire / v3-goal
 *   承  v3-confirm / v3-basis
 *   听  v3-player（tabBar 页）
 *
 * 跳转规则（tabBar 契约）：
 *   - 目标是 tabBar 页（v3-player）→ switchTab
 *   - 从 tabBar 页跳出 → navigateTo
 *   - 普通页之间 → redirectTo（避免层级堆叠）
 */
const NAV_ITEMS = [
  { key: "welcome", glyph: "入", step: "01", tip: "入静", path: "/pages/welcome/welcome", tab: false },
  { key: "material", glyph: "声", step: "02", tip: "呈声", path: "/pages/v3-material/v3-material", tab: false },
  { key: "question", glyph: "问", step: "03", tip: "问询", path: "/pages/v3-questionnaire/v3-questionnaire", tab: false },
  { key: "confirm", glyph: "承", step: "04", tip: "确认", path: "/pages/v3-confirm/v3-confirm", tab: false },
  { key: "listen", glyph: "听", step: "05", tip: "聆听", path: "/pages/v3-player/v3-player", tab: true },
]

export default {
  name: "HanSideNav",
  props: {
    // 当前页所属阶段 key；无（如入口页）则不高亮
    current: { type: String, default: "" },
  },
  data() {
    return { items: NAV_ITEMS }
  },
  methods: {
    go(item) {
      if (!item || item.key === this.current) return
      if (item.tab) {
        uni.switchTab({ url: item.path })
        return
      }
      // 从 tabBar 页（聆听）跳出普通页必须 navigateTo
      if (this.current === "listen") {
        uni.navigateTo({ url: item.path })
      } else {
        uni.redirectTo({ url: item.path })
      }
    },
  },
}
</script>

<template>
  <view class="han-side-nav" aria-label="页面导航">
    <view
      v-for="item in items"
      :key="item.key"
      class="nav-btn"
      :class="{ active: item.key === current }"
      @click="go(item)"
    >
      <text class="nav-glyph">{{ item.glyph }}</text>
      <text class="nav-step">{{ item.step }}</text>
      <view class="nav-tip">
        <text class="nav-tip-text">{{ item.tip }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.han-side-nav {
  position: fixed;
  left: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  z-index: 99;
}

.nav-btn {
  position: relative;
  width: 96rpx;
  height: 96rpx;
  background: var(--paper-card);
  border: 2rpx solid rgba(42, 40, 36, 0.14);
  border-radius: 18rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--ink-700);
  transition: all 220ms cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4rpx 14rpx rgba(29, 26, 22, 0.08);
}

.nav-btn:active {
  transform: scale(0.94);
}

.nav-btn.active {
  background: var(--ink-seal);
  border-color: var(--ink-seal);
  color: #fdfbf5;
  box-shadow: 0 0 0 6rpx rgba(192, 57, 43, 0.16), 0 0 0 12rpx rgba(192, 57, 43, 0.07),
    0 6rpx 18rpx rgba(192, 57, 43, 0.28);
  transform: rotate(-3deg);
}

.nav-glyph {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  font-weight: 700;
  font-size: 36rpx;
  line-height: 1;
}

.nav-step {
  font-size: 16rpx;
  letter-spacing: 2rpx;
  margin-top: 6rpx;
  opacity: 0.55;
}

.nav-tip {
  position: absolute;
  left: 108rpx;
  top: 50%;
  transform: translateY(-50%) translateX(-12rpx);
  background: rgba(29, 26, 22, 0.92);
  padding: 10rpx 24rpx;
  border-radius: 12rpx;
  opacity: 0;
  transition: all 220ms ease;
  pointer-events: none;
  white-space: nowrap;
}

.nav-tip::before {
  content: "";
  position: absolute;
  left: -6rpx;
  top: 50%;
  transform: translateY(-50%) rotate(45deg);
  width: 12rpx;
  height: 12rpx;
  background: rgba(29, 26, 22, 0.92);
}

.nav-tip-text {
  color: #fdfbf5;
  font-size: 22rpx;
  letter-spacing: 4rpx;
}

.nav-btn:hover .nav-tip,
.nav-btn.active .nav-tip {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
}
</style>
