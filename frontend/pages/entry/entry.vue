<script>
/**
 * V3 入口页（双入口选择）
 * 合同依据：frontend-read-model-contract-v3.md §3.1 EntryReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §2（最终用户流程）
 *
 * 文案严格使用 Owner Amendment 批准版本：
 *  - "我有近期就诊资料" / "我没有近期就诊资料"
 *  - 不使用旧的入口文案表述
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      entry: null,
      submitting: false,
      error: "",
    }
  },
  onLoad() {
    this.init()
  },
  methods: {
    async init() {
      this.loading = true
      this.error = ""
      try {
        await apiV3.guestAuth()
        const session = await apiV3.createSession()
        apiV3.rememberSession(session)
        this.entry = {
          page: "entry",
          session_id: session.session_id,
          title: "开始了解你最近的状态",
          description: "请选择是否有近期就诊资料。没有资料也可以通过状态问卷开始。",
          choices: [
            { id: "with_document", label: "我有近期就诊资料", desc: "可以上传近期病历、检查报告或相关就诊记录。", route: "/pages/v3-material/v3-material" },
            { id: "without_document", label: "我没有近期就诊资料", desc: "可以通过最近情况和10道状态问卷继续评估。", route: "/pages/v3-narrative/v3-narrative" },
          ],
        }
      } catch (e) {
        this.error = e.message || "加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    async choose(choice) {
      if (this.submitting) return
      this.submitting = true
      try {
        // select_mode：服务端权威保存入口选择（Amendment §4.1）
        await apiV3.selectMode(choice.id)
        uni.navigateTo({ url: choice.route })
      } catch (e) {
        uni.showToast({ title: e.message || "选择失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
  },
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="page-title">{{ entry ? entry.title : "开始了解你最近的状态" }}</text>
      <text class="page-subtitle">请选择是否有近期就诊资料。没有资料也可以通过状态问卷开始。</text>
    </view>

    <view v-if="loading" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在准备…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <text class="error-text">{{ error }}</text>
      <view class="btn-retry" @click="init"><text class="btn-retry-text">重试</text></view>
    </view>

    <view v-else class="choices">
      <view
        v-for="c in entry.choices"
        :key="c.id"
        class="choice-card"
        :class="{ 'choice-disabled': submitting }"
        @click="choose(c)"
      >
        <view class="choice-icon">
          <text class="choice-icon-text">{{ c.id === "with_document" ? "文" : "问" }}</text>
        </view>
        <view class="choice-body">
          <text class="choice-label">{{ c.label }}</text>
          <text class="choice-desc">{{ c.desc }}</text>
        </view>
        <view class="choice-arrow"><text class="arrow-text">›</text></view>
      </view>
    </view>

    <view class="foot-note">
      <text class="foot-note-text">两种方式都会生成音乐调养建议 · 全程数据仅用于本次评估</text>
    </view>
  </view>
</template>

<style>
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 80rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header {
  margin-bottom: 64rpx;
}
.page-title {
  display: block;
  font-size: 44rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 20rpx;
}
.page-subtitle {
  display: block;
  font-size: 28rpx;
  color: #7a8078;
  line-height: 1.6;
}
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: #9c9585;
}
.error-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 100rpx 0;
}
.error-text {
  font-size: 28rpx;
  color: #b0574f;
  margin-bottom: 32rpx;
}
.btn-retry {
  padding: 20rpx 64rpx;
  background: #4a6b5c;
  border-radius: 44rpx;
}
.btn-retry-text {
  color: #fff;
  font-size: 28rpx;
}
.choices {
  display: flex;
  flex-direction: column;
  gap: 32rpx;
}
.choice-card {
  display: flex;
  align-items: center;
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}
.choice-disabled {
  opacity: 0.6;
}
.choice-icon {
  width: 88rpx;
  height: 88rpx;
  background: #eef0ea;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.choice-icon-text {
  font-size: 36rpx;
  color: #4a6b5c;
  font-weight: 600;
}
.choice-body {
  flex: 1;
  margin: 0 24rpx;
}
.choice-label {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 10rpx;
}
.choice-desc {
  display: block;
  font-size: 24rpx;
  color: #9c9585;
  line-height: 1.5;
}
.choice-arrow {
  flex-shrink: 0;
}
.arrow-text {
  font-size: 44rpx;
  color: #c9c3b2;
}
.foot-note {
  margin-top: 72rpx;
  text-align: center;
}
.foot-note-text {
  font-size: 22rpx;
  color: #b3ac9c;
}
</style>
