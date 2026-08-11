<template>
  <view class="container">
    <!-- 顶部标题区 -->
    <view class="header">
      <text class="step-tag">第 1 步 · 选填</text>
      <text class="page-title">上传病历材料</text>
      <text class="page-subtitle">如有近期的医院病历或检查报告，可上传供 AI 辅助分析；没有也没关系，可直接跳过。</text>
    </view>

    <progress-bar :progress="25" label="评估进度" />

    <!-- 上传卡片 -->
    <view v-if="!filePath" class="upload-card" @click="chooseFile">
      <view class="upload-icon-wrap">
        <view class="upload-icon">
          <text class="upload-plus">+</text>
        </view>
        <view class="upload-corner upload-corner-tl"></view>
        <view class="upload-corner upload-corner-tr"></view>
        <view class="upload-corner upload-corner-bl"></view>
        <view class="upload-corner upload-corner-br"></view>
      </view>
      <text class="upload-title">点击上传文件</text>
      <text class="upload-hint">支持图片、PDF · 仅用于本次评估</text>
      <view class="upload-formats">
        <text class="format-tag">JPG</text>
        <text class="format-tag">PNG</text>
        <text class="format-tag">PDF</text>
      </view>
    </view>

    <!-- 已上传文件卡片 -->
    <view v-else class="file-card">
      <view class="file-preview" v-if="isImage">
        <image class="preview-img" :src="filePath" mode="aspectFill" />
      </view>
      <view class="file-info" v-else>
        <view class="file-icon">
          <text class="file-icon-text">文</text>
        </view>
        <view class="file-meta">
          <text class="file-name">{{ fileName }}</text>
          <text class="file-size">已就绪</text>
        </view>
      </view>
      <view class="file-actions">
        <view class="file-action" @click="chooseFile">
          <text class="file-action-text">重新选择</text>
        </view>
        <view class="file-action danger" @click="clearFile">
          <text class="file-action-text">删除</text>
        </view>
      </view>
    </view>

    <!-- OCR 处理中 -->
    <view v-if="uploading" class="ocr-loading-card">
      <view class="ocr-loading-orb">
        <view class="ocr-orb-ring"></view>
        <text class="ocr-orb-text">识</text>
      </view>
      <text class="ocr-loading-title">OCR 识别中</text>
      <text class="ocr-loading-desc">正在用 PaddleOCR 识别材料文字...</text>
    </view>

    <view v-if="documentId && (ocrMode === 'success' || ocrMode === 'degraded' || ocrMode === 'manual')" class="file-card ocr-confirm-card">
      <view class="ocr-confirm-header">
        <text class="upload-title">请确认识别文字</text>
        <view v-if="ocrInfo" class="ocr-confidence-tag">
          <text class="ocr-confidence-text">置信度 {{ Math.round((ocrInfo.confidence || 0) * 100) }}%</text>
        </view>
      </view>
      <text class="upload-hint">OCR 仅作辅助，识别有误时请直接修改</text>
      <textarea
        v-model="extractedText"
        maxlength="2000"
        placeholder="请确认或补充材料文字"
        style="width: 100%; min-height: 220rpx; margin-top: 20rpx;"
      />
    </view>
    <error-state
      v-if="ocrMode === 'failed'"
      title="OCR 识别失败"
      :message="ocrSafeMessage"
      :showFallback="true"
      fallbackText="手动输入"
      @retry="retryOcr"
      @fallback="useManualInput"
    />
    <view v-if="ocrMode === 'failed'" class="file-actions">
      <view class="file-action" @click="skip"><text class="file-action-text">跳过材料</text></view>
    </view>
    <error-state
      v-if="status === 'error'"
      :title="'上传失败'"
      :message="errorMsg"
      :showFallback="true"
      :fallbackText="'跳过此步'"
      @retry="chooseFile"
      @fallback="skip"
    />

    <!-- 底部按钮 -->
    <view class="btn-group">
      <view class="btn btn-secondary" @click="skip">
        <text class="btn-text">跳过</text>
      </view>
      <view class="btn btn-primary" :class="{ disabled: !filePath && status !== 'error' }" @click="next">
        <text class="btn-text">{{ filePath ? nextLabel : '请上传或跳过' }}</text>
        <text class="btn-arrow" v-if="filePath">→</text>
      </view>
    </view>
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { confirmDocument, uploadDocument } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'
import { applyOcrResponse, createDocumentPageState, enterManualMode } from '@/common/document-page-state.js'
import { safeUiError } from '@/common/safe-ui-error.js'

export default {
  components: { ProgressBar, ErrorState },
  data() {
    return {
      filePath: '',
      fileName: '',
      isImage: false,
      documentId: '',
      extractedText: '',
      status: 'idle',
      errorMsg: '',
      uploading: false,
      ocrInfo: null,
      ocrMode: 'idle',
      ocrErrorCode: '',
      ocrSafeMessage: ''
    }
  },
  computed: {
    nextLabel() {
      return this.documentId ? '确认文字并继续' : '上传并识别'
    }
  },
  methods: {
    chooseFile() {
      this.status = 'idle'
      this.errorMsg = ''
      const done = (path, name = '') => {
        this.filePath = path
        this.fileName = name || path.split('/').pop() || '已选择文件'
        this.isImage = /\.(jpe?g|png)$/i.test(this.fileName)
        this.documentId = ''
        this.extractedText = ''
      }
      if (typeof uni.chooseMessageFile === 'function') {
        uni.chooseMessageFile({
          count: 1,
          type: 'file',
          extension: ['jpg', 'jpeg', 'png', 'pdf'],
          success: (res) => done(res.tempFiles[0].path, res.tempFiles[0].name),
          fail: () => this.chooseImage(done)
        })
      } else {
        this.chooseImage(done)
      }
    },
    chooseImage(done) {
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera'],
        success: (res) => done(res.tempFilePaths[0]),
        fail: () => {
          this.status = 'error'
          this.errorMsg = '选择文件失败，请重试或跳过此步'
        }
      })
    },
    clearFile() {
      this.filePath = ''
      this.fileName = ''
      this.isImage = false
      this.documentId = ''
      this.extractedText = ''
      this.ocrInfo = null
      this.uploading = false
      this.ocrMode = 'idle'
      this.ocrErrorCode = ''
      this.ocrSafeMessage = ''
    },
    retryOcr() { this.documentId = ''; this.ocrMode = 'idle'; this.next() },
    useManualInput() {
      const state = enterManualMode({ ...createDocumentPageState(), text: this.extractedText })
      this.ocrMode = state.mode
      this.extractedText = state.text
      this.ocrSafeMessage = state.message
    },
    skip() {
      updateSprint3Session({
        document_id: null,
        document_text: null,
        document_skipped: true
      })
      uni.navigateTo({ url: '/pages/narrative/narrative' })
    },
    async next() {
      if (!this.filePath || this.uploading) return
      this.status = 'idle'
      try {
        const session = getSprint3Session()
        if (!this.documentId) {
          this.uploading = true
          const uploaded = await uploadDocument({
            filePath: this.filePath,
            sessionId: session.session_id,
            consentConfirmed: true
          })
          this.uploading = false
          this.documentId = uploaded.document_id
          const ocrState = applyOcrResponse(createDocumentPageState(), uploaded)
          this.ocrMode = ocrState.mode
          this.extractedText = ocrState.text
          this.ocrErrorCode = ocrState.errorCode
          this.ocrSafeMessage = ocrState.message
          if (ocrState.mode === 'failed') return

          // 降级处理
          if (ocrState.mode === 'degraded') {
            this.ocrInfo = { confidence: uploaded.average_confidence || 0, degraded: true }
            updateSprint3Session({ document_id: uploaded.document_id })
            return
          }

          this.extractedText = uploaded.extracted_text || ''
          this.ocrInfo = {
            confidence: uploaded.average_confidence || 0,
            engine: uploaded.ocr_provider || 'paddleocr',
            evidenceCount: uploaded.evidence_items_extracted || 0,
          }
          updateSprint3Session({ document_id: uploaded.document_id })
          uni.showToast({ title: '请确认识别文字', icon: 'none' })
          return
        }
        const confirmed = await confirmDocument(this.documentId, {
          sessionId: session.session_id,
          confirmed: true,
          documentText: this.extractedText
        })
        updateSprint3Session({
          document_id: confirmed.document_id,
          document_text: confirmed.document_text || this.extractedText,
          document_skipped: false
        })
        uni.navigateTo({ url: '/pages/narrative/narrative' })
      } catch (error) {
        this.uploading = false
        this.status = 'error'
        this.errorMsg = safeUiError(error, 'BACKEND_UNAVAILABLE').message
      }
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #F7F3EB;
  padding: 40rpx 40rpx 200rpx;
  box-sizing: border-box;
}

/* 顶部 */
.header {
  margin-bottom: 32rpx;
}
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4A6B5C;
  background: #EEF1ED;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  letter-spacing: 0.1em;
  margin-bottom: 16rpx;
}
.page-title {
  font-size: 44rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.03em;
  display: block;
  margin-bottom: 12rpx;
}
.page-subtitle {
  font-size: 26rpx;
  color: #6B6862;
  line-height: 1.7;
  display: block;
}

/* 上传卡片 */
.upload-card {
  background: #FCFAF6;
  border: 2rpx dashed #C8D2CB;
  border-radius: 36rpx;
  padding: 80rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  transition: all 0.2s;
}
.upload-card:active {
  background: #F7F3EB;
}
.upload-icon-wrap {
  position: relative;
  width: 160rpx;
  height: 160rpx;
  margin-bottom: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-icon {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #EEF1ED 0%, #DDE5DF 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2rpx solid #FCFAF6;
  box-shadow: 0 4rpx 16rpx rgba(74, 107, 92, 0.10);
  position: relative;
  z-index: 1;
}
.upload-plus {
  font-size: 64rpx;
  color: #4A6B5C;
  font-weight: 300;
  line-height: 1;
}
.upload-corner {
  position: absolute;
  width: 24rpx;
  height: 24rpx;
  border: 2rpx solid #4A6B5C;
}
.upload-corner-tl {
  top: 0; left: 0; border-right: none; border-bottom: none; border-top-left-radius: 8rpx;
}
.upload-corner-tr {
  top: 0; right: 0; border-left: none; border-bottom: none; border-top-right-radius: 8rpx;
}
.upload-corner-bl {
  bottom: 0; left: 0; border-right: none; border-top: none; border-bottom-left-radius: 8rpx;
}
.upload-corner-br {
  bottom: 0; right: 0; border-left: none; border-top: none; border-bottom-right-radius: 8rpx;
}
.upload-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #2C2A28;
  letter-spacing: 0.03em;
  margin-bottom: 8rpx;
}
.upload-hint {
  font-size: 24rpx;
  color: #9C9585;
  margin-bottom: 24rpx;
}
.upload-formats {
  display: flex;
  gap: 12rpx;
}
.format-tag {
  font-size: 20rpx;
  color: #6B6862;
  background: #F7F3EB;
  padding: 6rpx 14rpx;
  border-radius: 16rpx;
  letter-spacing: 0.08em;
}

/* 文件已上传卡片 */
.file-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.08);
}
.file-preview {
  width: 100%;
  height: 360rpx;
  border-radius: 24rpx;
  overflow: hidden;
  margin-bottom: 24rpx;
  background: #F7F3EB;
}
.preview-img {
  width: 100%;
  height: 100%;
}
.file-info {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 24rpx;
  padding: 24rpx;
  background: #F7F3EB;
  border-radius: 20rpx;
}
.file-icon {
  width: 88rpx;
  height: 88rpx;
  border-radius: 24rpx;
  background: linear-gradient(135deg, #EEF1ED 0%, #DDE5DF 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.file-icon-text {
  font-size: 36rpx;
  color: #4A6B5C;
  font-weight: 700;
  font-family: 'Kaiti SC', serif;
}
.file-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  min-width: 0;
}
.file-name {
  font-size: 28rpx;
  color: #2C2A28;
  font-weight: 500;
  word-break: break-all;
}
.file-size {
  font-size: 22rpx;
  color: #6B8979;
}
.file-actions {
  display: flex;
  gap: 24rpx;
  justify-content: center;
  padding-top: 16rpx;
  border-top: 1rpx solid #F0EBE0;
}
.file-action {
  padding: 12rpx 32rpx;
  border-radius: 32rpx;
  background: #EEF1ED;
  transition: all 0.2s;
}
.file-action:active {
  transform: scale(0.96);
}
.file-action.danger {
  background: #F9EDE7;
}
.file-action-text {
  font-size: 24rpx;
  color: #4A6B5C;
  font-weight: 500;
}
.file-action.danger .file-action-text {
  color: #C85A45;
}

/* OCR 处理中 */
.ocr-loading-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 72rpx 40rpx;
  text-align: center;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
  margin-bottom: 24rpx;
}
.ocr-loading-orb {
  width: 140rpx; height: 140rpx; margin: 0 auto 32rpx;
  position: relative; display: flex; align-items: center; justify-content: center;
}
.ocr-orb-ring {
  position: absolute; width: 140rpx; height: 140rpx;
  border-radius: 50%; border: 3rpx solid #EEF1ED; border-top-color: #4A6B5C;
  animation: ocr-spin 1.2s linear infinite;
}
@keyframes ocr-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.ocr-orb-text { font-size: 44rpx; color: #4A6B5C; font-weight: 700; font-family: 'Kaiti SC', serif; }
.ocr-loading-title { font-size: 32rpx; font-weight: 600; color: #2C2A28; display: block; margin-bottom: 8rpx; }
.ocr-loading-desc { font-size: 24rpx; color: #9C9585; }

/* OCR 确认头部 */
.ocr-confirm-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4rpx; }
.ocr-confidence-tag {
  padding: 6rpx 16rpx; border-radius: 20rpx;
  background: #EEF1ED; border: 1rpx solid #C8D2CB;
}
.ocr-confidence-text { font-size: 22rpx; color: #4A6B5C; font-weight: 600; }

/* 底部按钮 */
.btn-group {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 20rpx;
  padding: 24rpx 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: rgba(247, 243, 235, 0.95);
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border-top: 1rpx solid #E8E2D5;
  box-sizing: border-box;
}
.btn {
  flex: 1;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  transition: all 0.2s;
}
.btn:active {
  transform: scale(0.98);
}
.btn-primary {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  box-shadow: 0 8rpx 24rpx rgba(74, 107, 92, 0.20);
}
.btn-primary .btn-text {
  color: #F7F3EB;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.btn-arrow {
  font-size: 30rpx;
  color: #F7F3EB;
  font-weight: 500;
}
.btn-secondary {
  background: #FCFAF6;
  border: 1rpx solid #E8E2D5;
}
.btn-secondary .btn-text {
  color: #4A6B5C;
  font-size: 30rpx;
  font-weight: 600;
}
.btn.disabled {
  opacity: 0.4;
}
</style>