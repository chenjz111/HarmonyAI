<script>
export default {
  onLaunch: function() {
    console.log('HarmonyAI App Launch')
  },
  onShow: function() {
    console.log('App Show')
  },
  onHide: function() {
    console.log('App Hide')
  }
}
</script>

<style>
/* ===== HarmonyAI 全局样式 — 中医药材纸感 ===== */

page {
  background-color: #F7F3EB;
  font-family: 'Kaiti SC', 'STKaiti', 'KaiTi', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, serif;
  color: #2C2C2A;
  font-size: 28rpx;
  line-height: 1.7;
}

/* ===== 配色变量 ===== */
:root {
  /* 主色系 */
  --color-primary: #4A6B5C;        /* 深苔绿 */
  --color-primary-light: #6B8B7C;  /* 浅苔绿 */
  --color-primary-dark: #3A5547;   /* 暗苔绿 */
  --color-accent: #C8896D;         /* 土褐 */
  --color-accent-light: #D9A589;   /* 浅土褐 */
  --color-bg: #F7F3EB;             /* 暖米白 */
  --color-bg-card: #FFFEFA;        /* 卡片白 */
  --color-bg-warm: #F0E9D9;        /* 暖底 */
  --color-text: #2C2C2A;           /* 主文字 */
  --color-text-light: #6B6B5C;     /* 次文字 */
  --color-text-muted: #9C9585;     /* 弱文字 */
  --color-border: #D9D0BD;         /* 边框 */
  --color-divider: #E8E0CC;        /* 分割线 */
  --color-danger: #C44A3E;         /* 朱砂红 */
  --color-success: #5A8A6B;        /* 成功绿 */
  --color-warning: #D4A542;        /* 警示金 */

  /* 阴影 */
  --shadow-sm: 0 2rpx 8rpx rgba(74, 107, 92, 0.08);
  --shadow-md: 0 4rpx 16rpx rgba(74, 107, 92, 0.12);
  --shadow-lg: 0 8rpx 32rpx rgba(74, 107, 92, 0.16);

  /* 圆角 */
  --radius-sm: 8rpx;
  --radius-md: 16rpx;
  --radius-lg: 24rpx;
  --radius-xl: 32rpx;
}

/* ===== 通用工具类 ===== */
.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.text-primary { color: var(--color-primary); }
.text-accent { color: var(--color-accent); }
.text-muted { color: var(--color-text-muted); }
.text-danger { color: var(--color-danger); }

/* ===== 卡片 ===== */
.ink-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  border: 1rpx solid var(--color-border);
}

/* ===== 按钮 ===== */
.ink-btn {
  background: var(--color-primary);
  color: #FFFEFA;
  border-radius: var(--radius-xl);
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 2rpx;
  border: none;
  padding: 24rpx 48rpx;
  box-shadow: var(--shadow-md);
}

.ink-btn-outline {
  background: transparent;
  color: var(--color-primary);
  border: 2rpx solid var(--color-primary);
  border-radius: var(--radius-xl);
}

.ink-btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

/* ===== 印章式徽章 ===== */
.ink-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent);
  color: #FFFEFA;
  border-radius: var(--radius-sm);
  font-size: 22rpx;
  font-weight: 700;
  padding: 6rpx 16rpx;
  letter-spacing: 1rpx;
}

/* ===== 水墨分割线 ===== */
.ink-divider {
  height: 1rpx;
  background: linear-gradient(90deg, transparent, var(--color-divider), transparent);
  margin: 24rpx 0;
}

/* ===== 动画 ===== */
@keyframes ink-fade-in {
  from { opacity: 0; transform: translateY(20rpx); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes ink-pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
}

@keyframes ink-ripple {
  0% { transform: scale(0.8); opacity: 0.8; }
  100% { transform: scale(2); opacity: 0; }
}

.ink-fade-in {
  animation: ink-fade-in 0.4s ease-out;
}
</style>
