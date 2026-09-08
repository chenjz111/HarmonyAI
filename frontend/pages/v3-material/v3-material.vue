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
 * ===== 后端对齐依赖（复审注明：等待蔡子鑫对齐，未确定前不擅自调用聚合端点） =====
 *  - 单文件仍走现有 V2 通道：POST /api/v2/documents + replace_document（真实接口已交付）
 *  - 多文档聚合（DocumentSet / 1~3 份有序聚合 + owner-aware upload）端点尚未交付
 *    —— 在此之前，本页面对真实多文档上传如实逐张失败并跳转 v3-material-error，不模拟成功；
 *    mock / hybrid 演示模式按"独立 document_id + 上传顺序保留"实现，便于本地预览
 *    1~3 份资料的有序聚合体验。后端对齐完成后由 apiV3.uploadDocument 内部替换为聚合通道。
 *
 * 注意：真实后端未交付多文档聚合与 owner-aware 上传端点，real 模式下逐张上传
 * 仍会如实失败并跳转异常页，不伪造成功；mock/hybrid 可完整演示多文件流程。
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

const MAX_FILES = 3

export default {
  components: { HanSideNav },
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
  <view class="page han-page side-nav-page">
    <han-side-nav current="material" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">声</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">有资料流程 · 第 1 步</text>
            <text class="page-title han-title-brush revealed">上传就诊资料</text>
          </view>
        </view>
        <text class="page-subtitle">可上传 1~3 张近期病历、检查报告或相关就诊记录。</text>
      </view>

      <!-- 空态：点击添加第一张 -->
      <view
        v-if="files.length === 0 && state === 'pick'"
        class="han-card upload-card ink-fade-up"
        @click="chooseFiles"
      >
        <view class="upload-icon"><text class="upload-plus">+</text></view>
        <text class="upload-title">点击上传文件</text>
        <view class="upload-divider han-divider han-divider--seal"></view>
        <text class="upload-hint">最多 3 张 · 仅用于本次评估</text>
      </view>

      <!-- 文件缩略图网格 -->
      <view v-if="files.length > 0 && state === 'pick'" class="file-grid ink-fade-up">
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
      <view v-if="state === 'uploading'" class="han-card status-card">
        <view class="status-ring"></view>
        <text class="status-label">正在识别资料</text>
        <text class="status-msg">通常需要几秒钟，请稍候。</text>
      </view>

      <!-- 全部识别成功：短暂提示后进入摘要确认 -->
      <view v-if="state === 'uploaded'" class="han-card status-card">
        <view class="status-done-seal">
          <text class="status-done-seal-text">成</text>
        </view>
        <text class="status-label">资料识别完成</text>
        <text class="status-msg">正在为你整理资料摘要…</text>
      </view>

      <!-- 开始识别按钮（仅选图阶段展示） -->
      <view v-if="state === 'pick'" class="action-area">
        <view
          class="han-btn han-btn-primary btn-start"
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
  </view>
</template>

<style scoped>
.container {
  min-height: 100vh;
  padding: 72rpx 48rpx 60rpx;
  box-sizing: border-box;
}

/* ===== 页头（印章 + 楷体标题） ===== */
.header {
  margin-bottom: 52rpx;
}
.header-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 20rpx;
}
.stage-seal {
  width: 88rpx;
  height: 88rpx;
  background: var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
  flex-shrink: 0;
}
.stage-seal-text {
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 44rpx;
  font-weight: 700;
}
.header-titles {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.step-tag {
  display: inline-block;
  align-self: flex-start;
  font-size: 22rpx;
  color: var(--ink-primary);
  background: rgba(107, 124, 94, 0.12);
  border: 1rpx solid rgba(107, 124, 94, 0.2);
  border-radius: 8rpx;
  padding: 4rpx 16rpx;
}
.page-title {
  font-size: 44rpx;
}
.page-subtitle {
  display: block;
  font-size: 28rpx;
  color: var(--text-secondary);
  line-height: 1.7;
}

/* ===== 上传空卡（宣纸虚线） ===== */
.upload-card {
  border: 2rpx dashed var(--border-soft);
  border-radius: var(--radius-lg);
  padding: 96rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.upload-icon {
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  background: rgba(107, 124, 94, 0.1);
  border: 1rpx solid rgba(107, 124, 94, 0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.upload-plus {
  font-size: 60rpx;
  color: var(--ink-primary);
  font-weight: 300;
}
.upload-title {
  font-size: 32rpx;
  color: var(--ink-700);
  font-weight: 500;
  margin-bottom: 8rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.upload-divider {
  width: 200rpx;
  margin: 8rpx 0 20rpx;
}
.upload-hint {
  font-size: 24rpx;
  color: var(--text-muted);
}

/* ===== 缩略图网格 ===== */
.file-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.file-tile {
  position: relative;
  width: 200rpx;
  height: 240rpx;
  border-radius: 16rpx;
  overflow: hidden;
  background: var(--paper-card-solid);
  border: 2rpx solid var(--border-light);
  box-shadow: var(--shadow-card);
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
  background: rgba(26, 25, 22, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
}
.file-remove-text {
  color: #fdfbf5;
  font-size: 32rpx;
  line-height: 1;
}
.file-name {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 8rpx 12rpx;
  background: rgba(251, 249, 244, 0.94);
  white-space: nowrap;
  overflow: hidden;
}
.file-name-text {
  font-size: 20rpx;
  color: var(--text-secondary);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-add {
  border: 2rpx dashed var(--border-soft);
  background: rgba(251, 249, 244, 0.6);
  box-shadow: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.file-add-plus {
  font-size: 56rpx;
  color: var(--text-muted);
  line-height: 1;
  margin-bottom: 8rpx;
  font-weight: 300;
}
.file-add-text {
  font-size: 24rpx;
  color: var(--text-muted);
}

/* ===== 识别状态卡 ===== */
.status-card {
  border-radius: var(--radius-lg);
  padding: 80rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.status-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid var(--paper-deep);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 28rpx;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.status-done-seal {
  width: 88rpx;
  height: 88rpx;
  background: var(--ink-primary);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24rpx;
  box-shadow: 0 6rpx 18rpx rgba(107, 124, 94, 0.3);
}
.status-done-seal-text {
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 40rpx;
  font-weight: 700;
}
.status-label {
  font-size: 32rpx;
  color: var(--ink-700);
  font-weight: 500;
  margin-bottom: 12rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.status-msg {
  font-size: 26rpx;
  color: var(--text-muted);
}

/* ===== 主按钮 ===== */
.action-area {
  margin-top: 48rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.btn-start {
  width: 100%;
}
.btn-start-disabled {
  opacity: 0.45;
  box-shadow: none;
  background: var(--text-disabled);
}
.btn-start-text {
  color: var(--text-inverse);
  font-size: 32rpx;
  font-weight: 600;
  letter-spacing: 2rpx;
}
.action-hint {
  margin-top: 20rpx;
  font-size: 24rpx;
  color: var(--text-muted);
}

.privacy-note {
  margin-top: 64rpx;
  text-align: center;
}
.privacy-note-text {
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 2rpx;
}
</style>
