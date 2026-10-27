import { createSSRApp } from 'vue'
import App from './App.vue'
import { initializeAndroidPlatform } from './common/android-platform.js'
import { initializeH5Platform } from './common/h5-platform.js'

export function createApp() {
  initializeAndroidPlatform({uniApi:typeof uni==='undefined'?null:uni})
  initializeH5Platform({uniApi:typeof uni==='undefined'?null:uni})
  const app = createSSRApp(App)
  return {
    app
  }
}
