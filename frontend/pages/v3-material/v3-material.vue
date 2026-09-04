<script>
/**
 * V3 资料上传页（有资料流程第一步）
 * 合同依据：frontend-read-model-contract-v3.md §3.2 SourceStatusReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §3.1（OCR 失败标准文案）
 *          Sprint 5 组长指令：OCR 失败按钮二固定为"暂不使用资料，通过描述和问卷继续"
 *
 * 状态机：idle → uploading/processing → ready（去摘要确认）| failed（OCR 失败分流）| network_error（网络/服务错误，可重试）
 *  - 失败页文案严格按 Amendment §3.1：标题"资料暂未识别成功"
 *  - OCR 失败与网络错误是两种状态：网络错误展示具体错误信息与重试入口，不冒充 OCR 失败固定文案
 *  - 失败不得进入摘要确认或后续 Agent 页面
 *  - 不展示 OCR Provider、原始置信度或内部异常
 *
 * mock 提示：测试时选择文件名含 "fail" 的文件可模拟 OCR 失败路径
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      state: "idle", // idle | processing | ready | failed | network_error
      filePath: "",
      fileName: "",
      isImage: false,
      error: "",
      discarding: false,
    }
  },
  methods: {
    chooseFile() {
      if (this.state === "processing") return
      uni.chooseImage({
        count: 1,
        success: (res) => {
          const f = res.tempFiles && res.tempFiles[0]
          this.filePath = res.tempFilePaths && res.tempFilePaths[0]
          this.fileName = (f && f.name) || "就诊资料图片.jpg"
          this.isImage = true
          this.upload()
        },
        fail: () => {
          // 用户取消选择，静默返回
        },
      })
    },
    async upload() {
      this.state = "processing"
      this.error = ""
      try {
        const doc = await apiV3.uploadDocument(this.filePath, this.fileName)
        if (doc.state === "failed") {
          // OCR 失败：留在本页失败态，不进入摘要确认
          this.state = "failed"
        } else {
          this.state = "ready"
          // 识别成功 → 进入资料摘要确认页（Amendment §2）
          setTimeout(() => {
            uni.redirectTo({ url: "/pages/v3-summary/v3-summary" })
          }, 600)
        }
      } catch (e) {
        // 网络/服务错误与 OCR 失败分流：这里只是上传或服务调用失败，
        // 资料本身是否识别成功由后端 ocr_status 决定，不冒用 OCR 失败固定文案
        this.state = "network_error"
        this.error = e.message || "上传失败，请重试"
      }
    },
    retry() {
      // 重新上传资料（Amendment §3.1 按钮一）
      this.state = "idle"
      this.filePath = ""
      this.fileName = ""
    },
    retryFromNetworkError() {
      this.error = ""
      this.retry()
    },
    async switchToQuestionnaire() {
      // 暂不使用资料，通过描述和问卷继续（Sprint 5 组长指令按钮二）
      // 必须调用后端 Input Transition（discard_document）切换为无资料模式，不是前端隐藏卡片
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
      <text class="step-tag">有资料流程 · 第 1 步</text>
      <text class="page-title">上传就诊资料</text>
      <text class="page-subtitle">可以上传近期病历、检查报告或相关就诊记录。</text>
    </view>

    <!-- 待上传 -->
    <view v-if="state === 'idle'" class="upload-card" @click="chooseFile">
      <view class="upload-icon"><text class="upload-plus">+</text></view>
      <text class="upload-title">点击上传文件</text>
      <text class="upload-hint">支持图片、PDF · 仅用于本次评估</text>
    </view>

    <!-- OCR 处理中：不进入摘要确认（Amendment §3.1） -->
    <view v-if="state === 'processing'" class="status-card">
      <view class="status-ring"></view>
      <text class="status-label">正在识别资料</text>
      <text class="status-msg">通常需要几秒钟。</text>
    </view>

    <!-- 识别成功：短暂提示后进入摘要确认 -->
    <view v-if="state === 'ready'" class="status-card">
      <text class="status-done-icon">✓</text>
      <text class="status-label">资料识别完成</text>
      <text class="status-msg">正在为你整理资料摘要…</text>
    </view>

    <!-- OCR 失败页：文案严格按 Amendment §3.1 + Sprint 5 组长指令按钮二 -->
    <view v-if="state === 'failed'" class="fail-card">
      <view class="fail-icon"><text class="fail-icon-text">!</text></view>
      <text class="fail-title">资料暂未识别成功</text>
      <text class="fail-desc">我们暂时无法从这份资料中提取有效内容。你可以重新上传清晰的图片或PDF，也可以跳过本次资料，改用最近情况描述和10道状态问卷继续评估。</text>

      <view class="fail-actions">
        <view class="btn-primary" @click="retry">
          <text class="btn-primary-text">重新上传资料</text>
        </view>
        <view class="btn-secondary" @click="switchToQuestionnaire">
          <text class="btn-secondary-text">{{ discarding ? "正在切换…" : "暂不使用资料，通过描述和问卷继续" }}</text>
        </view>
        <text class="fail-note">自由描述可以跳过，10道状态问卷需要完成。</text>
      </view>
    </view>

    <!-- 网络/服务错误：展示具体错误与重试，不冒充 OCR 失败固定文案 -->
    <view v-if="state === 'network_error'" class="fail-card">
      <view class="fail-icon"><text class="fail-icon-text">!</text></view>
      <text class="fail-title">资料暂时没有上传成功</text>
      <text class="fail-desc">{{ error || "网络或服务暂时不可用，请稍后重试。" }}</text>

      <view class="fail-actions">
        <view class="btn-primary" @click="retryFromNetworkError">
          <text class="btn-primary-text">重新上传资料</text>
        </view>
        <!-- P0-2 前端桥接：资料无法关联会话等场景下，用户仍可走描述+问卷路径，
             不会被卡死在重试；归属问题的根治需后端 V3 owner-aware 上传接口 -->
        <view class="btn-secondary" @click="switchToQuestionnaire">
          <text class="btn-secondary-text">{{ discarding ? "正在切换…" : "暂不使用资料，通过描述和问卷继续" }}</text>
        </view>
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
.header { margin-bottom: 56rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4a6b5c;
  background: #e6ebe5;
  border-radius: 8rpx;
  padding: 6rpx 16rpx;
  margin-bottom: 20rpx;
}
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
.upload-card {
  background: #fffefa;
  border: 2rpx dashed #c9c3b2;
  border-radius: 24rpx;
  padding: 100rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.upload-icon {
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  background: #eef0ea;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.upload-plus { font-size: 60rpx; color: #4a6b5c; }
.upload-title { font-size: 32rpx; color: #2f3d35; font-weight: 500; margin-bottom: 12rpx; }
.upload-hint { font-size: 24rpx; color: #9c9585; }
.status-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 80rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.status-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 28rpx;
}
@keyframes spin { to { transform: rotate(360deg); } }
.status-done-icon {
  font-size: 64rpx;
  color: #4a6b5c;
  margin-bottom: 20rpx;
}
.status-label { font-size: 32rpx; color: #2f3d35; font-weight: 500; margin-bottom: 12rpx; }
.status-msg { font-size: 26rpx; color: #9c9585; }
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
  font-size: 36rpx;
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
