import { createSSRApp } from 'vue'
import App from './App.vue'
import { initializeAndroidPlatform } from './common/android-platform.js'

export function createApp() {
  initializeAndroidPlatform({uniApi:typeof uni==='undefined'?null:uni})
  const app = createSSRApp(App)
  return {
    app
  }
}
