<template>
  <view class="container">
    <!-- 顶部标题 -->
    <view class="header">
      <text class="step-tag">第 4 步 · 选填</text>
      <text class="page-title">聆听感受</text>
      <text class="page-subtitle">你的反馈将帮助我们优化下一次的疗愈处方</text>
    </view>

    <!-- 主评分卡 -->
    <view class="rating-main-card">
      <text class="rating-main-label">整体满意度</text>
      <view class="big-stars">
        <text
          class="big-star"
          v-for="s in 5"
          :key="s"
          :class="{ active: s <= overallRating }"
          @click="setOverall(s)"
        >★</text>
      </view>
      <text class="rating-main-text">{{ overallText }}</text>
    </view>

    <!-- 多维评分 -->
    <view class="rating-section">
      <text class="section-title">多维评分</text>
      <view class="rating-list">
        <view class="rating-item" v-for="(item, index) in ratings" :key="index">
          <view class="rating-info">
            <text class="rating-label">{{ item.label }}</text>
            <text class="rating-value">{{ item.value || '—' }} / 5</text>
          </view>
          <view class="stars-row">
            <text
              class="star"
              v-for="s in 5"
              :key="s"
              :class="{ active: s <= item.value }"
              @click="setRating(index, s)"
            >★</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 评论卡 -->
    <view class="comment-card">
      <view class="comment-header">
        <text class="comment-title">其他建议</text>
        <text class="comment-optional">选填</text>
      </view>
      <textarea
        class="comment-area"
        v-model="comment"
        placeholder="例如：节奏太急 / 某段音色不舒服 / 希望多些乐器..."
        maxlength="200"
        :disable-default-padding="true"
      />
      <view class="comment-meta">
        <view class="comment-presets">
          <text class="preset-tag" @click="usePreset(t)" v-for="t in presets" :key="t">{{ t }}</text>
        </view>
        <text class="comment-count">{{ comment.length }} / 200</text>
      </view>
    </view>

    <error-state
      v-if="status === 'error'"
      title="提交失败"
      :message="errorMsg"
      @retry="submit"
    />

    <!-- 底部按钮 -->
    <view class="btn-group">
      <view class="btn btn-primary" :class="{ disabled: !canSubmit }" @click="submit">
        <text class="btn-text">提交反馈</text>
        <text class="btn-arrow">→</text>
      </view>
    </view>
  </view>
</template>

<script>
import ErrorState from '@/components/sprint3/error-state.vue'
import { submitFeedbackV2 } from '@/common/api-v2.js'

export default {
  components: { ErrorState },
  data() {
    return {
      overallRating: 0,
      ratings: [
        { label: '情绪改善', value: 0 },
        { label: '身体放松', value: 0 },
        { label: '睡眠友好', value: 0 },
        { label: '推荐意愿', value: 0 }
      ],
      comment: '',
      presets: ['很好', '节奏刚好', '再舒缓些', '希望重复'],
      status: 'idle',
      errorMsg: ''
    }
  },
  computed: {
    canSubmit() {
      return this.overallRating > 0 && this.ratings.every(r => r.value > 0)
    },
    overallText() {
      const map = ['请选择评分', '需要调整', '一般', '较好', '很好', '非常疗愈']
      return map[this.overallRating] || '请选择评分'
    }
  },
  methods: {
    setOverall(value) {
      this.overallRating = value
      // 整体满意度变动时，自动填充其他维度（取均值±1的近似）
      this.ratings.forEach((r, i) => {
        if (r.value === 0) {
          r.value = Math.max(1, Math.min(5, value - (i % 2 === 0 ? 0 : 1)))
        }
      })
    },
    setRating(index, value) {
      this.ratings[index].value = value
    },
    usePreset(text) {
      this.comment = this.comment ? this.comment + '，' + text : text
    },
    async submit() {
      if (!this.canSubmit) {
        uni.showToast({ title: '请完成所有评分', icon: 'none' })
        return
      }
      this.status = 'idle'
      try {
        const sessionId = uni.getStorageSync('harmony_session_id_v2')
        const payload = {
          session_id: sessionId,
          track_id: 'track_jiao_demo_001',
          ratings: [
            { label: '整体满意度', value: this.overallRating },
            ...this.ratings
          ],
          comment: this.comment
        }
        const res = await submitFeedbackV2(payload)
        uni.setStorageSync('harmony_feedback_v2', JSON.stringify({ ...res, ...payload }))
        uni.navigateTo({ url: '/pages/complete/complete' })
      } catch (e) {
        this.status = 'error'
        this.errorMsg = e.message || '提交失败，请检查网络'
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
.header { margin-bottom: 32rpx; }
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

/* 主评分卡 */
.rating-main-card {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  border-radius: 36rpx;
  padding: 48rpx 40rpx;
  text-align: center;
  margin-bottom: 32rpx;
  box-shadow: 0 12rpx 32rpx rgba(74, 107, 92, 0.25);
  position: relative;
  overflow: hidden;
}
.rating-main-card::before {
  content: '';
  position: absolute;
  top: -40rpx;
  right: -40rpx;
  width: 200rpx;
  height: 200rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
}
.rating-main-card::after {
  content: '';
  position: absolute;
  bottom: -60rpx;
  left: -60rpx;
  width: 240rpx;
  height: 240rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
}
.rating-main-label {
  display: block;
  font-size: 26rpx;
  color: rgba(252, 250, 246, 0.75);
  letter-spacing: 0.15em;
  margin-bottom: 24rpx;
  position: relative;
  z-index: 1;
}
.big-stars {
  display: flex;
  justify-content: center;
  gap: 16rpx;
  margin-bottom: 24rpx;
  position: relative;
  z-index: 1;
}
.big-star {
  font-size: 72rpx;
  color: rgba(252, 250, 246, 0.3);
  transition: all 0.2s;
  line-height: 1;
}
.big-star.active {
  color: #F0C75E;
  transform: scale(1.08);
  text-shadow: 0 4rpx 16rpx rgba(240, 199, 94, 0.4);
}
.rating-main-text {
  display: block;
  font-size: 28rpx;
  color: #FCFAF6;
  font-weight: 500;
  letter-spacing: 0.1em;
  position: relative;
  z-index: 1;
}

/* 多维评分 */
.rating-section {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
}
.section-title {
  font-size: 28rpx;
  font-weight: 700;
  color: #2C2A28;
  display: block;
  margin-bottom: 24rpx;
  padding-bottom: 16rpx;
  border-bottom: 1rpx dashed #E8E2D5;
  letter-spacing: 0.05em;
}
.rating-list {
  display: flex;
  flex-direction: column;
}
.rating-item {
  padding: 24rpx 0;
  border-bottom: 1rpx dashed #F0EBE0;
}
.rating-item:last-child { border-bottom: none; }
.rating-info {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16rpx;
}
.rating-label {
  font-size: 28rpx;
  color: #2C2A28;
  font-weight: 500;
}
.rating-value {
  font-size: 22rpx;
  color: #C8896D;
  font-family: Georgia, serif;
}
.stars-row {
  display: flex;
  gap: 16rpx;
}
.star {
  font-size: 44rpx;
  color: #E8E2D5;
  transition: all 0.2s;
  line-height: 1;
}
.star.active {
  color: #D4A574;
  transform: scale(1.1);
}

/* 评论卡 */
.comment-card {
  background: #FCFAF6;
  border-radius: 32rpx;
  padding: 32rpx;
  border: 1rpx solid #E8E2D5;
  box-shadow: 0 6rpx 20rpx rgba(74, 107, 92, 0.06);
}
.comment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.comment-title {
  font-size: 28rpx;
  font-weight: 700;
  color: #2C2A28;
  letter-spacing: 0.05em;
}
.comment-optional {
  font-size: 22rpx;
  color: #9C9585;
  background: #F7F3EB;
  padding: 4rpx 12rpx;
  border-radius: 14rpx;
}
.comment-area {
  width: 100%;
  min-height: 180rpx;
  background: #F7F3EB;
  border-radius: 20rpx;
  padding: 24rpx;
  font-size: 28rpx;
  color: #2C2A28;
  line-height: 1.6;
  box-sizing: border-box;
  letter-spacing: 0.02em;
}
.comment-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
}
.comment-presets {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
  flex: 1;
}
.preset-tag {
  font-size: 22rpx;
  color: #4A6B5C;
  background: #EEF1ED;
  padding: 6rpx 14rpx;
  border-radius: 16rpx;
  transition: all 0.2s;
}
.preset-tag:active {
  background: #DDE5DF;
  transform: scale(0.95);
}
.comment-count {
  font-size: 22rpx;
  color: #9C9585;
  font-family: Georgia, serif;
}

/* 底部按钮 */
.btn-group {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 24rpx 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: rgba(247, 243, 235, 0.95);
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border-top: 1rpx solid #E8E2D5;
  box-sizing: border-box;
}
.btn {
  height: 108rpx;
  border-radius: 54rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  transition: all 0.2s;
}
.btn:active { transform: scale(0.98); }
.btn-primary {
  background: linear-gradient(135deg, #4A6B5C 0%, #2F4A3D 100%);
  box-shadow: 0 12rpx 36rpx rgba(74, 107, 92, 0.30);
}
.btn-primary .btn-text {
  color: #F7F3EB;
  font-size: 32rpx;
  font-weight: 600;
  letter-spacing: 0.1em;
}
.btn-arrow {
  font-size: 30rpx;
  color: #F7F3EB;
  font-weight: 500;
}
.btn.disabled {
  opacity: 0.4;
}
</style>