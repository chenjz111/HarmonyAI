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
/* 全局样式 */
page {
  background-color: #F8F8F8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #2C2C2A;
}

/* 五行五音配色变量 */
:root {
  --color-mu: #4A9D6E;   /* 木-青 */
  --color-huo: #E25C4E;  /* 火-赤 */
  --color-tu: #E8B547;   /* 土-黄 */
  --color-jin: #B8C5D6;  /* 金-白 */
  --color-shui: #3B5067; /* 水-黑 */
}
</style>
