<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">{{ withDocument ? "有资料流程 · 第 5 步 · 选填" : "无资料流程 · 第 3 步 · 选填" }}</text>
      <text class="page-title">疗愈诉求</text>
      <text class="page-subtitle">如果对这次调适有特别的期待，可以告诉我们；没有的话直接跳过即可。这一步选填。</text>
    </view>

    <view v-if="submitting" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在整理你的选择…</text>
    </view>

    <template v-else>
      <view class="card">
        <view class="card-head">
          <text class="card-title">主要诉求</text>
          <text class="card-hint">选择一项最希望调适的方面</text>
        </view>
        <view class="chip-grid">
          <view
            v-for="it in intents"
            :key="it.code"
            class="chip"
            :class="{ 'chip-active': primary === it.code }"
            @click="pickPrimary(it.code)"
          >
            <text class="chip-text" :class="{ 'chip-text-active': primary === it.code }">{{ it.label }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">次要诉求</text>
          <text class="card-hint">还可以再选一项</text>
        </view>
        <view class="chip-grid">
          <view
            v-for="it in intents"
            :key="it.code"
            class="chip"
            :class="{ 'chip-active': secondary === it.code, 'chip-dim': primary === it.code }"
            @click="pickSecondary(it.code)"
          >
            <text class="chip-text" :class="{ 'chip-text-active': secondary === it.code }">{{ it.label }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">其他想法</text>
          <text class="card-hint">选填</text>
        </view>
        <textarea
          class="custom-input"
          v-model="custom"
          :maxlength="200"
          placeholder="例如：希望音乐更舒缓一些、节奏慢一些……"
        />
        <view class="custom-count"><text class="custom-count-text">{{ (custom || '').length }} / 200</text></view>
      </view>

      <!-- 如实标注：该信息本机暂存，不会丢失（此步无后端持久化依赖） -->
      <view class="save-note">
        <text class="save-note-text">这一步选填。你的选择会保存在本机，不会丢失；之后随时可以重新体验来更新它。</text>
      </view>

      <view class="actions">
        <view class="btn-primary" @click="next">
          <text class="btn-primary-text">继续</text>
        </view>
        <view class="btn-link" @click="skip">
          <text class="btn-link-text">暂不选择，直接继续</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
/**
 * V3.1 疗愈诉求页（Issue #100：Provisional Flow 选填加回）
 *
 * - 此页为可选的调适方向偏好，两条路径（有资料 / 无资料）均为选填，可整步跳过
 * - 不虚构、不默认补全任何偏好：用户未选择时不留占位、不提交空对象
 * - 选择内容本机暂存（后端暂无对应保存能力），页面如实标注；mock 状态机同步记录
 * - 后续：v3-confirm（完成近期状态总结）
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      withDocument: false,
      intents: [
        { code: "sleep", label: "睡得更安稳" },
        { code: "relax", label: "让身心放松" },
        { code: "soothe", label: "舒缓紧张不安" },
        { code: "lift_mood", label: "改善低落心情" },
        { code: "energy", label: "更有精神一些" },
      ],
      primary: null,
      secondary: null,
      custom: "",
      submitting: false,
    }
  },
  onLoad() {
    apiV3.getSession()
      .then((s) => {
        this.withDocument = s.input_mode === "with_document"
      })
      .catch(() => {})
  },
  methods: {
    pickPrimary(code) {
      if (this.primary === code) {
        this.primary = null
        return
      }
      this.primary = code
      if (this.secondary === code) this.secondary = null
    },
    pickSecondary(code) {
      if (this.primary === code) {
        uni.showToast({ title: "已在主要诉求中", icon: "none" })
        return
      }
      if (this.secondary === code) {
        this.secondary = null
        return
      }
      this.secondary = code
    },
    // 无任何选择时等同跳过
    async next() {
      if (this.submitting) return
      if (!this.primary && !this.secondary && !(this.custom || "").trim()) {
        this.skip()
        return
      }
      this.submitting = true
      try {
        await apiV3.submitHealingIntent({
          primary: this.primary,
          secondary: this.secondary,
          custom_text: (this.custom || "").trim() || null,
        })
        uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
      } catch (e) {
        uni.showToast({ title: (e && e.message) || "保存失败，请稍后重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    skip() {
      // 整步跳过：不保存任何偏好、不伪造默认值
      uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
    },
  },
}
</script>

<style>
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 80rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header { margin-bottom: 48rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4a6b5c;
  background: #e6ebe5;
  border-radius: 8rpx;
  padding: 6rpx 16rpx;
  margin-bottom: 20rpx;
}
.page-title { display: block; font-size: 44rpx; font-weight: 600; color: #2f3d35; margin-bottom: 16rpx; }
.page-subtitle { display: block; font-size: 28rpx; color: #7a8078; line-height: 1.6; }
.card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 32rpx;
}
.card-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 24rpx; }
.card-title { font-size: 30rpx; font-weight: 500; color: #2f3d35; }
.card-hint { font-size: 22rpx; color: #b3ac9c; }
.chip-grid { display: flex; flex-wrap: wrap; gap: 20rpx; }
.chip {
  background: #f6f3ea;
  border: 2rpx solid transparent;
  border-radius: 40rpx;
  padding: 18rpx 32rpx;
}
.chip-active { background: #edf1ec; border-color: #4a6b5c; }
.chip-dim { opacity: 0.45; }
.chip-text { font-size: 28rpx; color: #4a554c; }
.chip-text-active { color: #2f5d43; font-weight: 500; }
.custom-input {
  width: 100%;
  min-height: 140rpx;
  font-size: 28rpx;
  color: #2f3d35;
  line-height: 1.7;
}
.custom-count { display: flex; justify-content: flex-end; margin-top: 8rpx; }
.custom-count-text { font-size: 22rpx; color: #b3ac9c; }
.save-note {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 20rpx 28rpx;
  margin-bottom: 40rpx;
}
.save-note-text { font-size: 24rpx; color: #8a9188; line-height: 1.6; }
.actions { display: flex; flex-direction: column; }
.btn-primary {
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 26rpx 0;
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.btn-primary-text { color: #fff; font-size: 30rpx; }
.btn-link { display: flex; justify-content: center; padding: 12rpx 0; }
.btn-link-text { color: #8a9188; font-size: 26rpx; text-decoration: underline; }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; }
.loading-ring {
  width: 72rpx; height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { margin-top: 24rpx; font-size: 26rpx; color: #9c9585; }
</style>
