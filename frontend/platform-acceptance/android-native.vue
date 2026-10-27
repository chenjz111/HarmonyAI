<template>
 <view class="check-page">
  <text class="heading">HarmonyAI 非生产 Android 原生验收</text>
  <text>仅用于合成凭据与本机 HTTPS 检查，不启用注册账号，不读取原游客凭据。</text>
  <button :disabled="busy" @click="checkVault">检查真实 Keystore</button>
  <button :disabled="busy" @click="checkTls">检查本机 HTTPS</button>
  <text selectable>{{result}}</text>
  <text>构建成功不代表验收通过；强杀、重启、备份残留及账号流程仍需后续实测。</text>
 </view>
</template>
<script>
import {invokeAccountNative} from '@/uni_modules/harmonyai-account-native'
import {createAndroidNativeBridge} from '../common/android-native-bridge.js'
export default {
 data(){return {busy:false,result:'尚未执行设备检查'}},
 methods:{
  async execute(operation){
   if(this.busy)return
   this.busy=true
   try{const bridge=createAndroidNativeBridge({invoke:invokeAccountNative});this.result=JSON.stringify(await operation(bridge),null,2)}
   catch(error){this.result='检查未通过：'+(error.code||'NATIVE_CHECK_FAILED')}
   finally{this.busy=false}
  },
  checkVault(){return this.execute(bridge=>bridge.runSyntheticVaultChecks())},
  checkTls(){return this.execute(bridge=>bridge.probeTls('https://127.0.0.1:8443/health'))},
 }
}
</script>
<style>
.check-page{padding:32rpx;display:flex;flex-direction:column;gap:24rpx}.heading{font-size:36rpx;font-weight:bold}
</style>
