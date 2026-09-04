<script>
/**
 * V3.1 资料上传页（Issue #100：1~3 张资料上传）
 * 合同依据：frontend-read-model-contract-v3.md §3.2 SourceStatusReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §3.1（OCR 失败标准文案，现收敛至独立异常页）
 *
 * 变更（V3.0 → V3.1）：
 *  - 单文件 → 1~3 张多文件：缩略图列表、单张删除、"+ 添加"入口（不超过 3 张）
 *  - OCR/网络失败不再内嵌本页，统一跳转独立资料异常页 v3-material-error
 *    （?type=ocr | ?type=network）
 *  - 识别成功 → 资料摘要确认页
 *
 * ===== 后端对齐依赖（Issue #100 复审注明：等待蔡子鑫对齐，未确定前不擅自调用聚合端点） =====
 *  - 单文件仍走现有 V2 通道：POST /api/v2/documents + replace_document（真实接口已交付）
 *  - 多文档聚合（DocumentSet / 1~3 份有序聚合 + owner-aware upload）端点尚未交付
 *    —— 在此之前，本页面对真实多文档上传如实逐张失败并跳转 v3-material-error，不模拟成功；
 *    mock / hybrid 演示模式按"独立 document_id + 上传顺序保留"实现，便于本地预览
 *    1~3 份资料的有序聚合体验。后端对齐完成后由 apiV3.uploadDocument 内部替换为聚合通道。
 *
 * 注意：真实后端未交付多文档聚合与 owner-aware 上传端点，real 模式下逐张上传
 * 仍会如实失败并跳转异常页，不伪造成功；mock/hybrid 可完整演示多文件流程。
 */
import { apiV3 } from "../../common/api-v3.js"

const MAX_FILES = 3

export default {
  data() {
    return {
      state: "pick", // pick（选图/列表） | uploading | uploaded
      files: [], // [{ path, name, isImage, document_id }]
      error: "",
    }
  },
  computed: {
    canAdd() {
      return this.files.length < MAX_FILES
    },
  },
  methods: {
    chooseFiles() {
      if (this.state === "uploading" || !this.canAdd) return
      const remain = MAX_FILES - this.files.length
      uni.chooseImage({
        count: remain,
        success: (res) => {
          const paths = res.tempFilePaths || []
          const temp = res.tempFiles || []
          paths.forEach((p, i) => {
            const f = temp[i] || {}
            this.files.push({
              path: p,
              name: f.name || this.defaultName(p),
              isImage: true,
              document_id: null,
            })
          })
        },
        fail: () => {
          // 用户取消选择，静默返回
        },
      })
    },
    defaultName(path) {
      const seg = String(path || "").split(/[\\/]/)
      return seg[seg.length - 1] || "就诊资料图片.jpg"
    },
    removeFile(idx) {
      if (this.state === "uploading") return
      this.files.splice(idx, 1)
    },
    async startUpload() {
      if (this.state !== "pick" || this.files.length === 0) return
      this.state = "uploading"
      this.error = ""
      for (let i = 0; i < this.files.length; i++) {
        const f = this.files[i]
        try {
          const doc = await apiV3.uploadDocument(f.path, f.name)
          if (doc.state === "failed") {
            // OCR 失败：跳独立异常页（?type=ocr）
            uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=ocr" })
            return
          }
          f.document_id = doc.document_id
        } catch (e) {
          // 网络/服务错误（含真实环境归属缺口）：跳独立异常页（?type=network）
          uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=network" })
          return
        }
      }
      // 全部识别成功 → 资料摘要确认页
      this.state = "uploaded"
      setTimeout(() => {
        uni.redirectTo({ url: "/pages/v3-summary/v3-summary" })
      }, 600)
    },
  },
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">有资料流程 · 第 1 步</text>
      <text class="page-title">上传就诊资料</text>
      <text class="page-subtitle">可上传 1~3 张近期病历、检查报告或相关就诊记录。</text>
    </view>

    <!-- 空态：点击添加第一张 -->
    <view v-if="files.length === 0 && state === 'pick'" class="upload-card" @click="chooseFiles">
      <view class="upload-icon"><text class="upload-plus">+</text></view>
      <text class="upload-title">点击上传文件</text>
      <text class="upload-hint">最多 3 张 · 仅用于本次评估</text>
    </view>

    <!-- 文件缩略图网格 -->
    <view v-if="files.length > 0 && state === 'pick'" class="file-grid">
      <view v-for="(f, idx) in files" :key="idx" class="file-tile">
        <image class="file-thumb" :src="f.path" mode="aspectFill" />
        <view class="file-remove" @click="removeFile(idx)"><text class="file-remove-text">×</text></view>
        <view class="file-name">
          <text class="file-name-text">{{ f.name }}</text>
        </view>
      </view>
      <view v-if="canAdd" class="file-tile file-add" @click="chooseFiles">
        <text class="file-add-plus">+</text>
        <text class="file-add-text">添加</text>
      </view>
    </view>

    <!-- 上传中 -->
    <view v-if="state === 'uploading'" class="status-card">
      <view class="status-ring"></view>
      <text class="status-label">正在识别资料</text>
      <text class="status-msg">通常需要几秒钟，请稍候。</text>
    </view>

    <!-- 全部识别成功：短暂提示后进入摘要确认 -->
    <view v-if="state === 'uploaded'" class="status-card">
      <text class="status-done-icon">✓</text>
      <text class="status-label">资料识别完成</text>
      <text class="status-msg">正在为你整理资料摘要…</text>
    </view>

    <!-- 开始识别按钮（仅选图阶段展示） -->
    <view v-if="state === 'pick'" class="action-area">
      <view
        class="btn-start"
        :class="{ 'btn-start-disabled': files.length === 0 }"
        @click="startUpload"
      >
        <text class="btn-start-text">{{ files.length > 0 ? `识别并继续（${files.length} 张）` : "开始识别" }}</text>
      </view>
      <text v-if="files.length > 0 && canAdd" class="action-hint">还可再添加 {{ 3 - files.length }} 张</text>
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

/* 缩略图网格 */
.file-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.file-tile {
  position: relative;
  width: 200rpx;
  height: 240rpx;
  border-radius: 20rpx;
  overflow: hidden;
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
}
.file-thumb {
  width: 100%;
  height: 172rpx;
  display: block;
}
.file-remove {
  position: absolute;
  top: 8rpx;
  right: 8rpx;
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: rgba(44, 42, 40, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
}
.file-remove-text { color: #fff; font-size: 32rpx; line-height: 1; }
.file-name {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 8rpx 12rpx;
  background: rgba(255, 254, 250, 0.92);
  white-space: nowrap;
  overflow: hidden;
}
.file-name-text {
  font-size: 20rpx;
  color: #6b6862;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-add {
  border: 2rpx dashed #c9c3b2;
  background: #fcfaf6;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.file-add-plus { font-size: 56rpx; color: #9c9585; line-height: 1; margin-bottom: 8rpx; }
.file-add-text { font-size: 24rpx; color: #9c9585; }

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

.action-area {
  margin-top: 48rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.btn-start {
  width: 100%;
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 28rpx 0;
  display: flex;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.2);
}
.btn-start-disabled {
  opacity: 0.5;
  box-shadow: none;
}
.btn-start-text { color: #fff; font-size: 32rpx; font-weight: 600; letter-spacing: 2rpx; }
.action-hint {
  margin-top: 20rpx;
  font-size: 24rpx;
  color: #9c9585;
}
.privacy-note { margin-top: 64rpx; text-align: center; }
.privacy-note-text { font-size: 22rpx; color: #b3ac9c; }
</style>
