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
        <text class="btn-text">{{ filePath ? '继续' : '请上传或跳过' }}</text>
        <text class="btn-arrow" v-if="filePath">→</text>
      </view>
    </view>
  </view>
</template>

<script>
import ProgressBar from '@/components/sprint3/progress-bar.vue'
import ErrorState from '@/components/sprint3/error-state.vue'
import { uploadRecord } from '@/common/api-v2.js'

export default {
  components: { ProgressBar, ErrorState },
  data() {
    return {
      filePath: '',
      fileName: '',
      isImage: false,
      status: 'idle',
      errorMsg: ''
    }
  },
  methods: {
    chooseFile() {
      this.status = 'idle'
      this.errorMsg = ''
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera'],
        success: (res) => {
          const path = res.tempFilePaths[0]
          this.filePath = path
          this.fileName = path.split('/').pop() || '已上传文件'
          this.isImage = true
        },
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
    },
    skip() {
      uni.setStorageSync('harmony_material', JSON.stringify({ skipped: true }))
      uni.navigateTo({ url: '/pages/narrative/narrative' })
    },
    async next() {
      if (!this.filePath) return
      this.status = 'idle'
      try {
        const res = await uploadRecord(this.filePath)
        uni.setStorageSync('harmony_material', JSON.stringify(res))
        uni.navigateTo({ url: '/pages/narrative/narrative' })
      } catch (e) {
        this.status = 'error'
        this.errorMsg = e.message || '上传失败，请检查网络'
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