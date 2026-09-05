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
/* ===== HarmonyAI 全局样式 — 中式水墨 · 茶空间 · 宣纸（v2） =====
 * 参考 han-design tea/ink 主题 + shuimo-ui 山水留白意境
 */

/* ===== CSS 变量（与 uni.scss 同步） ===== */
page {
  /* 主色 */
  --ink-primary: #6B7C5E;
  --ink-primary-light: #8A9B7D;
  --ink-primary-dark: #55634B;
  --ink-seal: #C0392B;
  --ink-seal-light: #D16E64;
  --ink-seal-dark: #8A251B;
  --ink-accent: #B57152;
  --ink-accent-light: #C68A6E;

  /* 墨色阶 */
  --ink-50: #F7F6F3;
  --ink-100: #ECEBE6;
  --ink-200: #D8D6CF;
  --ink-300: #B5B2A9;
  --ink-400: #8A867D;
  --ink-500: #5E5A53;
  --ink-600: #3E3B36;
  --ink-700: #2A2824;
  --ink-800: #1A1916;
  --ink-900: #0D0C0A;

  /* 宣纸阶 */
  --paper-50: #FDFBF5;
  --paper-100: #FAF6EA;
  --paper-200: #F4EEDB;
  --paper-300: #EBE2C4;
  --paper-400: #DDCFA4;

  /* 语义背景 */
  --paper: #F6F3EE;
  --paper-card: rgba(251, 249, 244, 0.88);
  --paper-card-solid: #FBF9F4;
  --paper-warm: #E8E3D8;
  --paper-deep: #D9D2C3;
  --paper-veil: rgba(246, 243, 238, 0.92);

  /* 文字 */
  --text-primary: #3A352C;
  --text-secondary: #6B6458;
  --text-muted: #A39D90;
  --text-disabled: #C9C3B6;
  --text-inverse: #FBF9F4;

  /* 边框 */
  --border-soft: #CCC5B6;
  --border-light: #E8E3D8;
  --divider: #D8D6CF;
  --divider-ink: #B5B2A9;

  /* 状态 */
  --success: #4A7C59;
  --warning: #C68A2E;
  --danger: #C0392B;
  --info: #3A5285;

  /* 阴影 */
  --shadow-sm: 0 2rpx 12rpx rgba(58, 53, 44, 0.06);
  --shadow-md: 0 6rpx 24rpx rgba(58, 53, 44, 0.10);
  --shadow-lg: 0 12rpx 40rpx rgba(58, 53, 44, 0.14);
  --shadow-seal: 0 4rpx 16rpx rgba(192, 57, 43, 0.22);
  --shadow-card: 0 8rpx 32rpx rgba(58, 53, 44, 0.08);

  /* 圆角 */
  --radius-xs: 2rpx;
  --radius-sm: 8rpx;
  --radius-md: 16rpx;
  --radius-lg: 24rpx;
  --radius-xl: 32rpx;
  --radius-pill: 999rpx;
  --radius-seal: 6rpx;

  background-color: var(--paper);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--text-primary);
  font-size: 28rpx;
  line-height: 1.7;
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

.flex-col {
  display: flex;
  flex-direction: column;
}

.text-primary { color: var(--text-primary); }
.text-secondary { color: var(--text-secondary); }
.text-muted { color: var(--text-muted); }
.text-disabled { color: var(--text-disabled); }
.text-inverse { color: var(--text-inverse); }
.text-ink { color: var(--ink-primary); }
.text-seal { color: var(--ink-seal); }
.text-accent { color: var(--ink-accent); }

.bg-paper { background-color: var(--paper); }
.bg-card { background-color: var(--paper-card-solid); }
.bg-warm { background-color: var(--paper-warm); }

/* ===== 容器 ===== */
.container {
  min-height: 100vh;
  padding: 0 40rpx 64rpx;
  box-sizing: border-box;
}

.container-tabbar {
  min-height: calc(100vh - 120rpx);
  padding: 0 40rpx 64rpx;
  box-sizing: border-box;
}

/* ===== 水墨页面背景（茶空间 + 底部远山） ===== */
.han-page {
  position: relative;
  min-height: 100vh;
  background-color: var(--paper);
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320' preserveAspectRatio='xMidYMax slice'%3E%3Cpath fill='%23E8E3D8' fill-opacity='0.35' d='M0,224L48,213.3C96,203,192,181,288,181.3C384,181,480,203,576,224C672,245,768,267,864,250.7C960,235,1056,181,1152,165.3C1248,149,1344,171,1392,181.3L1440,192L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'%3E%3C/path%3E%3Cpath fill='%23D8D6CF' fill-opacity='0.25' d='M0,288L48,272C96,256,192,224,288,213.3C384,203,480,213,576,229.3C672,245,768,267,864,261.3C960,256,1056,224,1152,213.3C1248,203,1344,213,1392,218.7L1440,224L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'%3E%3C/path%3E%3Cpath fill='%23B5B2A9' fill-opacity='0.12' d='M0,256L60,250.7C120,245,240,235,360,240C480,245,600,267,720,261.3C840,256,960,224,1080,213.3C1200,203,1320,213,1380,218.7L1440,224L1440,320L1380,320C1320,320,1200,320,1080,320C960,320,840,320,720,320C600,320,480,320,360,320C240,320,120,320,60,320L0,320Z'%3E%3C/path%3E%3C/svg%3E"),
    radial-gradient(ellipse at 20% 0%, rgba(232, 227, 216, 0.5) 0%, transparent 45%),
    radial-gradient(ellipse at 80% 10%, rgba(235, 226, 196, 0.35) 0%, transparent 40%);
  background-repeat: no-repeat, no-repeat, no-repeat;
  background-position: center bottom, top left, top right;
  background-size: 100% 45%, 100% 100%, 100% 100%;
  overflow-x: hidden;
}

.han-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='1' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
  opacity: 0.6;
  pointer-events: none;
  z-index: 0;
}

.han-page-content {
  position: relative;
  z-index: 1;
}

/* ===== 宣纸卡片 ===== */
.han-card {
  position: relative;
  background: var(--paper-card);
  border: 1rpx solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(8rpx);
}

.han-card::before,
.han-card::after {
  content: "";
  position: absolute;
  width: 24rpx;
  height: 24rpx;
  background-repeat: no-repeat;
  background-size: contain;
  opacity: 0.35;
}

.han-card::before {
  top: 16rpx;
  left: 16rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.han-card::after {
  bottom: 16rpx;
  right: 16rpx;
  transform: rotate(180deg);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.han-card--ink {
  border-left: 5rpx solid var(--ink-700);
}

.han-card--seal {
  border-left: 5rpx solid var(--ink-seal);
}

.han-card--primary {
  border-left: 5rpx solid var(--ink-primary);
}

/* ===== 毛笔标题（楷体，仅用于短标题） ===== */
.han-title-brush {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  font-weight: 700;
  color: var(--ink-700);
  letter-spacing: 0.1em;
  line-height: 1.2;
  position: relative;
  display: inline-block;
}

.han-title-brush::after {
  content: "";
  display: block;
  width: 0;
  height: 3rpx;
  margin-top: 12rpx;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--ink-700) 15%,
    var(--ink-500) 50%,
    var(--ink-700) 85%,
    transparent 100%
  );
  border-radius: 50%;
  filter: blur(0.5px);
  transition: width 0.6s var(--ease-out);
}

.han-title-brush.is-revealed::after,
.han-title-brush.revealed::after {
  width: 100%;
}

.han-title-with-seal {
  display: flex;
  align-items: flex-end;
  gap: 20rpx;
}

.han-subtitle {
  font-family: var(--font-serif);
  font-size: 28rpx;
  color: var(--text-secondary);
  line-height: 1.7;
}

/* ===== 印章标记 ===== */
.han-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40rpx;
  height: 40rpx;
  padding: 0 10rpx;
  background: var(--ink-seal);
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 0;
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  box-shadow: var(--shadow-seal);
  vertical-align: middle;
}

.han-seal--circle {
  border-radius: 50%;
  padding: 0;
}

.han-seal--ink {
  background: var(--ink-700);
  box-shadow: var(--shadow-sm);
}

.han-seal--primary {
  background: var(--ink-primary);
  box-shadow: 0 4rpx 14rpx rgba(107, 124, 94, 0.2);
}

/* ===== 按钮（印章风格主按钮 + 水墨 ghost） ===== */
.han-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.15em;
  border: none;
  padding: 24rpx 48rpx;
  transition: all 0.25s var(--ease-out);
}

.han-btn-primary {
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  box-shadow: var(--shadow-seal);
  position: relative;
  overflow: hidden;
}

.han-btn-primary::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%);
  pointer-events: none;
}

.han-btn-primary:active {
  background: var(--ink-seal-dark);
  transform: scale(0.98);
}

.han-btn-primary.disabled {
  background: var(--text-disabled);
  box-shadow: none;
}

.han-btn-ghost {
  background: rgba(251, 249, 244, 0.6);
  color: var(--ink-700);
  border: 1rpx solid var(--border-soft);
  border-radius: var(--radius-seal);
}

.han-btn-ghost:active {
  background: rgba(232, 227, 216, 0.8);
}

.han-btn-seal {
  width: 120rpx;
  height: 120rpx;
  padding: 0;
  border-radius: var(--radius-seal);
  background: var(--ink-seal);
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 32rpx;
  font-weight: 700;
  box-shadow: var(--shadow-seal);
  transform: rotate(-2deg);
}

.han-btn-seal:active {
  transform: rotate(-2deg) scale(0.96);
}

/* ===== 墨线分隔 ===== */
.han-divider {
  height: 1rpx;
  background: linear-gradient(90deg, transparent, var(--divider-ink), transparent);
  margin: 32rpx 0;
}

.han-divider--seal::after {
  content: "";
  display: block;
  width: 16rpx;
  height: 16rpx;
  margin: -8rpx auto 0;
  background: var(--ink-seal);
  border-radius: 2rpx;
  transform: rotate(45deg);
}

/* ===== 卡片 v1（兼容旧版） ===== */
.ink-card {
  background: var(--paper-card-solid);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1rpx solid var(--border-light);
}

.ink-card-v2 {
  background: var(--paper-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1rpx solid var(--border-light);
  padding: 32rpx 28rpx;
}

.ink-card-v2.card-seal { border-left: 6rpx solid var(--ink-seal); }
.ink-card-v2.card-ink  { border-left: 6rpx solid var(--ink-primary); }
.ink-card-v2.card-accent { border-left: 6rpx solid var(--ink-accent); }

/* ===== 按钮 v1（兼容旧版，映射到新版印章风格） ===== */
.ink-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.1em;
  border: none;
  padding: 24rpx 48rpx;
  transition: all 0.25s var(--ease-out);
  background: var(--ink-primary);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  box-shadow: var(--shadow-sm);
}

.ink-btn-primary {
  background: var(--ink-seal);
  color: var(--text-inverse);
  box-shadow: var(--shadow-seal);
}

.ink-btn-primary:active { background: var(--ink-seal-dark); transform: scale(0.98); }
.ink-btn-primary.disabled { background: var(--text-disabled); box-shadow: none; }

.ink-btn-seal {
  background: var(--ink-seal);
  color: var(--text-inverse);
  box-shadow: var(--shadow-seal);
  border-radius: var(--radius-seal);
}

.ink-btn-seal:active { background: var(--ink-seal-dark); transform: scale(0.98); }

.ink-btn-ghost {
  background: rgba(251, 249, 244, 0.6);
  color: var(--ink-700);
  border: 1rpx solid var(--border-soft);
  border-radius: var(--radius-seal);
}

.ink-btn-ghost:active { background: rgba(232, 227, 216, 0.8); }

.ink-btn-ghost.seal-ghost { color: var(--ink-seal); border-color: var(--ink-seal); }
.ink-btn-ghost.seal-ghost:active { background: rgba(192, 57, 43, 0.06); }

/* ===== 印章 v1（兼容旧版） ===== */
.ink-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  font-size: 22rpx;
  font-weight: 700;
  padding: 6rpx 16rpx;
  letter-spacing: 0.05em;
  transform: rotate(-3deg);
  box-shadow: var(--shadow-seal);
}

/* ===== 进度条 ===== */
.ink-progress {
  position: relative;
  height: 8rpx;
  background: var(--border-light);
  border-radius: var(--radius-pill);
  overflow: hidden;
}

.ink-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--ink-primary), var(--ink-seal));
  border-radius: var(--radius-pill);
  transition: width 0.3s ease-out;
}

/* ===== 空态 / 错误态 / 加载态 ===== */
.ink-empty {
  padding: 96rpx 40rpx;
  text-align: center;
  color: var(--text-muted);
}

.ink-empty .ink-empty-icon {
  font-size: 96rpx;
  color: var(--ink-accent-light);
  margin-bottom: 24rpx;
  display: block;
}

.ink-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64rpx 0;
  color: var(--text-muted);
  font-size: 26rpx;
}

.ink-loading-spinner {
  width: 48rpx;
  height: 48rpx;
  border: 4rpx solid var(--border-light);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  margin-bottom: 16rpx;
  animation: ink-spin 0.8s linear infinite;
}

@keyframes ink-spin {
  to { transform: rotate(360deg); }
}

/* ===== 标题区 ===== */
.page-title {
  font-size: 48rpx;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 16rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.1em;
}

.page-desc {
  font-size: 28rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 40rpx;
}

.section-title {
  font-size: 36rpx;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 16rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.05em;
}

.section-hint {
  font-size: 24rpx;
  color: var(--text-muted);
  margin-bottom: 24rpx;
}

/* ===== 动画 ===== */
@keyframes ink-fade-in {
  from { opacity: 0; transform: translateY(20rpx); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes ink-fade-up {
  from { opacity: 0; transform: translateY(40rpx); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes ink-pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
}

@keyframes ink-breathe {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 1; }
}

@keyframes ink-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8rpx); }
}

@keyframes ink-mist {
  0% { opacity: 0; transform: translateX(-20rpx); }
  50% { opacity: 0.4; }
  100% { opacity: 0; transform: translateX(20rpx); }
}

.ink-fade-in { animation: ink-fade-in 0.6s var(--ease-out); }
.ink-fade-up { animation: ink-fade-up 0.7s var(--ease-out); }
.ink-breathe { animation: ink-breathe 4s ease-in-out infinite; }
.ink-float { animation: ink-float 5s ease-in-out infinite; }
</style>
