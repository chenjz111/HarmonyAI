<script>
export default {
  onLaunch() {
    // 启动时清除可能过期的会话数据
    // uni.removeStorageSync('harmony_result_v2')
  }
}
</script>

<style>
/* 全局样式 - 中医药材纸感调性 */
page {
  background-color: #F7F3EB;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  color: #2C2A28;
  font-size: 28rpx;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* CSS 变量：中医药材配色 */
page {
  --color-primary: #4A6B5C;          /* 主色 - 墨绿 */
  --color-primary-light: #6B8979;    /* 主色浅 */
  --color-primary-dark: #2F4A3D;     /* 主色深 */
  --color-primary-bg: #EEF1ED;       /* 主色背景 - 极浅绿 */
  --color-accent: #C8896D;           /* 强调 - 土褐 */
  --color-accent-warm: #D4A574;      /* 强调 - 土黄 */
  --color-bg: #F7F3EB;               /* 背景 - 暖米白 */
  --color-surface: #FCFAF6;          /* 卡片白 - 米色白 */
  --color-text: #2C2A28;             /* 主文字 */
  --color-text-secondary: #6B6862;   /* 次文字 */
  --color-text-muted: #9C9585;       /* 辅助文字 */
  --color-border: #E8E2D5;           /* 边框 - 米色 */
  --color-border-light: #F0EBE0;     /* 浅边框 */
  --color-danger: #C85A45;           /* 朱砂红 */
  --color-danger-bg: #F9EDE7;        /* 朱砂浅 */
  --color-success: #6B8979;          /* 复用主色浅 */
  --color-shadow: rgba(74,107,92,0.08);     /* 主色阴影 */
  --color-shadow-md: rgba(74,107,92,0.12);  /* 中阴影 */
  --color-shadow-lg: rgba(74,107,92,0.20);  /* 大阴影 */
}

/* 字体优化：标题字距 */
text {
  letter-spacing: 0.02em;
}
</style>