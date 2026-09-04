<script>
/**
 * V3.1 资料异常页（Issue #100）
 * 承接资料上传/识别失败后的独立分流，替代原先内嵌在本页的失败卡片。
 *
 * 依据：
 *  - harmonyai-v3-owner-flow-amendment-001.md §3.1（OCR 失败标准文案）
 *  - Sprint 5 组长指令：按钮二固定为"暂不使用资料，通过描述和问卷继续"
 *  - Issue #100：资料异常独立成页
 *
 * 两种异常类型（?type=）：
 *  - ocr     ：资料已上传但未能识别成功（固定文案，不带技术细节）
 *  - network ：上传/网络/服务失败（不冒充 OCR 失败，可重试）
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      type: "ocr", // ocr | network
      discarding: false,
      retrying: false,
    }
  },
  onLoad(query) {
    this.type = query && query.type === "network" ? "network" : "ocr"
    uni.setNavigationBarTitle({
      title: this.type === "network" ? "资料上传未完成" : "资料异常",
    })
  },
  methods: {
    retry() {
      // 重新上传资料（按钮一）：回到资料上传页重新选择
      if (this.retrying) return
      this.retrying = true
      uni.redirectTo({ url: "/pages/v3-material/v3-material" })
    },
    async switchToQuestionnaire() {
      // 暂不使用资料，通过描述和问卷继续（按钮二）
      // 必须调用后端 Input Transition（discard_document）切换为无资料模式，不是前端隐藏
      if (this.discarding) return
      this.discarding = true
      try {
        const session = await apiV3.discardDocument()
        apiV3.rememberSession(session)
        uni.redirectTo({ url: "/pages/v3-narrative/v3-narrative" })
      } catch (e) {
        uni.showToast({ title: e.message || "切换失败，请重试", icon: "none" })
      } finally {
        this.discarding = false
      }
    },
  },
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="page-title">{{ type === "network" ? "资料暂时没有上传成功" : "资料暂未识别成功" }}</text>
      <text class="page-subtitle" v-if="type === 'ocr'">
        我们暂时无法从这份资料中提取有效内容，请重新上传清晰的图片或 PDF。
      </text>
      <text class="page-subtitle" v-else>
        网络或服务暂时不可用，请稍后重试。
      </text>
    </view>

    <view class="fail-card">
      <view class="fail-icon"><text class="fail-icon-text">!</text></view>
      <text class="fail-title">{{ type === "network" ? "上传没有完成" : "没有识别到有效内容" }}</text>
      <text class="fail-desc" v-if="type === 'ocr'">
        你可以重新上传清晰、完整的资料；也可以暂时不使用资料，通过描述和问卷继续评估。
      </text>
      <text class="fail-desc" v-else>
        请检查网络后重新上传；也可以暂时不使用资料，通过描述和问卷继续评估。
      </text>

      <view class="fail-actions">
        <view class="btn-primary" @click="retry">
          <text class="btn-primary-text">{{ retrying ? "正在返回…" : "重新上传资料" }}</text>
        </view>
        <view class="btn-secondary" @click="switchToQuestionnaire">
          <text class="btn-secondary-text">{{ discarding ? "正在切换…" : "暂不使用资料，通过描述和问卷继续" }}</text>
        </view>
        <text class="fail-note">描述可以跳过，状态问卷需要完成。</text>
      </view>
    </view>

    <view class="privacy-note">
      <text class="privacy-note-text">资料仅用于本次评估 · 请勿上传他人资料</text>
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
.header { margin-bottom: 48rpx; }
.page-title {
  display: block;
  font-size: 44rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 16rpx;
}
.page-subtitle {
  display: block;
  font-size: 28rpx;
  color: #7a8078;
  line-height: 1.6;
}
.fail-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 64rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.fail-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: #f6e9e7;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.fail-icon-text { font-size: 52rpx; color: #b0574f; font-weight: 600; }
.fail-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #2f3d35;
  margin-bottom: 20rpx;
}
.fail-desc {
  font-size: 26rpx;
  color: #7a8078;
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
.fail-actions { width: 100%; }
.btn-primary {
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 26rpx 0;
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.btn-primary-text { color: #fff; font-size: 30rpx; }
.btn-secondary {
  background: #fffefa;
  border: 2rpx solid #4a6b5c;
  border-radius: 48rpx;
  padding: 24rpx 0;
  display: flex;
  justify-content: center;
}
.btn-secondary-text { color: #4a6b5c; font-size: 30rpx; }
.fail-note {
  display: block;
  text-align: center;
  margin-top: 28rpx;
  font-size: 24rpx;
  color: #9c9585;
}
.privacy-note { margin-top: 64rpx; text-align: center; }
.privacy-note-text { font-size: 22rpx; color: #b3ac9c; }
</style>
