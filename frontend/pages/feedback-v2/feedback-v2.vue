<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">体验反馈</text>
      <text class="page-title">这次体验后，你感觉怎么样？</text>
      <text class="page-subtitle">只有变化感受需要选择；其他内容均为选填，只会更新你的个人偏好，不会改写全局医学规则。</text>
    </view>

    <view class="rating-section required-change-section">
      <view class="section-heading-row">
        <text class="section-title inline-title">变化感受</text>
        <text class="required-tag">必填</text>
      </view>
      <view class="change-card-grid">
        <view v-for="item in changeOptions" :key="item.value" class="change-card" :class="{ active: changeLabel === item.value }" @tap="changeLabel = item.value">
          <text>{{ item.label }}</text>
        </view>
      </view>
    </view>

    <view class="rating-section">
      <text class="section-title">听前与听后状态（选填）</text>
      <view class="rating-item" v-for="item in stateItems" :key="item.key">
        <view class="rating-info"><text class="rating-label">{{ item.label }}</text><text class="rating-value">{{ stateValueText(item.key) }}</text></view>
        <text class="comment-optional">听前</text>
        <slider :value="preState[item.key] ?? 5" min="0" max="10" show-value activeColor="#6B8979" @change="setState('pre', item.key, $event.detail.value)" />
        <text class="comment-optional">听后</text>
        <slider :value="postState[item.key] ?? 5" min="0" max="10" show-value activeColor="#C8896D" @change="setState('post', item.key, $event.detail.value)" />
      </view>
    </view>

    <view class="rating-main-card">
      <text class="rating-main-label">整体满意度（选填）</text>
      <view class="big-stars"><text class="big-star" v-for="s in 5" :key="s" :class="{ active: s <= overallRating }" @tap="overallRating = s">★</text></view>
    </view>

    <view class="rating-section">
      <text class="section-title">音乐体验（选填）</text>
      <view class="rating-list">
        <view class="rating-item" v-for="item in ratings" :key="item.key">
          <view class="rating-info"><text class="rating-label">{{ item.label }}</text><text class="rating-value">{{ item.value || '未填写' }}</text></view>
          <view class="stars-row"><text class="star" v-for="s in 5" :key="s" :class="{ active: s <= item.value }" @tap="item.value = s">★</text></view>
        </view>
      </view>
      <text class="rating-label optional-block-title">以后是否愿意继续使用？（选填）</text>
      <view class="comment-presets"><text class="preset-tag" v-for="item in continueOptions" :key="item.value" :class="{ active: continueUse === item.value }" @tap="continueUse = item.value">{{ item.label }}</text></view>
      <view class="comment-presets favorite-row"><text class="preset-tag" :class="{ active: favorite === true }" @tap="toggleFavorite">{{ favorite === true ? '★ 已收藏' : '☆ 收藏本曲（选填）' }}</text></view>
    </view>

    <view class="comment-card">
      <view class="comment-header"><text class="comment-title">喜欢的音乐特点（选填）</text></view>
      <view class="comment-presets"><text class="preset-tag" v-for="feature in likedFeatureOptions" :key="feature" :class="{ active: likedFeatures.includes(feature) }" @tap="toggleList('likedFeatures', feature)">{{ feature }}</text></view>

      <view class="comment-header preference-heading"><text class="comment-title">希望下次调整（选填）</text></view>
      <view class="comment-presets"><text class="preset-tag" v-for="item in adjustmentOptions" :key="item" :class="{ active: adjustmentPreferences.includes(item) }" @tap="toggleList('adjustmentPreferences', item)">{{ item }}</text></view>

      <view class="comment-header preference-heading"><text class="comment-title">还有什么想告诉我们？（选填）</text></view>
      <textarea class="comment-area" v-model="comment" placeholder="可以记录喜欢的地方、不适合的地方，或任何建议..." maxlength="500" :disable-default-padding="true" />
      <text class="comment-count">{{ comment.length }} / 500</text>
    </view>

    <error-state v-if="status === 'error'" title="提交失败" :message="errorMsg" @retry="submit" />
    <view class="btn-group"><view class="btn btn-primary" :class="{ disabled: !canSubmit }" @tap="submit"><text class="btn-text">提交反馈</text><text class="btn-arrow">→</text></view></view>
  </view>
</template>

<script>
import ErrorState from '@/components/sprint3/error-state.vue'
import { submitFeedback } from '@/common/api-v2.js'
import { getSprint3Session, updateSprint3Session } from '@/common/sprint3-session.js'

function compactObject(value) {
  if (Array.isArray(value)) return value.map(compactObject)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, item]) => item !== null && item !== undefined && item !== '')
      .map(([key, item]) => [key, compactObject(item)])
  )
}

export default {
  components: { ErrorState },
  data() {
    return {
      preState: { tension: null, body_tension: null, mental_fatigue: null },
      postState: { tension: null, body_tension: null, mental_fatigue: null },
      stateItems: [
        { key: 'tension', label: '情绪紧张程度' },
        { key: 'body_tension', label: '身体紧绷程度' },
        { key: 'mental_fatigue', label: '精神疲劳程度' }
      ],
      changeLabel: '',
      changeOptions: [
        { value: 'much_better', label: '明显好一些' },
        { value: 'slightly_better', label: '稍微好一些' },
        { value: 'no_change', label: '差不多' },
        { value: 'worse', label: '感觉更不舒服' }
      ],
      overallRating: 0,
      ratings: [
        { key: 'relaxation', label: '放松程度', value: 0 },
        { key: 'music_match', label: '音乐匹配度', value: 0 }
      ],
      continueUse: null,
      continueOptions: [
        { value: 'yes', label: '愿意' },
        { value: 'maybe', label: '可以考虑' },
        { value: 'no', label: '暂时不愿意' }
      ],
      favorite: null,
      likedFeatureOptions: ['古琴音色', '节奏舒缓', '环境音', '音乐时长', '整体氛围', '音量舒适'],
      likedFeatures: [],
      adjustmentOptions: ['节奏更慢', '节奏更快', '减少高频', '更换乐器', '调整音量', '调整环境音', '缩短时长', '延长时长', '其他建议'],
      adjustmentPreferences: [],
      comment: '',
      status: 'idle',
      errorMsg: ''
    }
  },
  computed: {
    canSubmit() {
      return Boolean(this.changeLabel)
    }
  },
  methods: {
    setState(stage, key, value) {
      ;(stage === 'pre' ? this.preState : this.postState)[key] = value
    },
    stateValueText(key) {
      const before = this.preState[key]
      const after = this.postState[key]
      if (before == null && after == null) return '未填写'
      return '听前 ' + (before ?? '—') + ' → 听后 ' + (after ?? '—')
    },
    toggleList(key, value) {
      this[key] = this[key].includes(value)
        ? this[key].filter(item => item !== value)
        : [...this[key], value]
    },
    toggleFavorite() {
      this.favorite = this.favorite === true ? false : true
    },
    async submit() {
      if (!this.canSubmit) {
        uni.showToast({ title: '请选择本次体验后的变化感受', icon: 'none' })
        return
      }
      this.status = 'idle'
      try {
        const session = getSprint3Session()
        const music = session.music || session.workflow?.music || {}
        const playback = session.playback || {
          listened_seconds: 0,
          duration_seconds: Math.max(1, music.duration_seconds || 30),
          completion_rate: 0,
          pause_count: 0,
          skip_count: 0
        }
        const payload = compactObject({
          schema_version: 'feedback_v2.0',
          session_id: session.session_id,
          prescription_id: session.prescription_id || session.workflow?.result_id || ('rx_' + Date.now()),
          music_id: music.music_id || 'music_jiao_001',
          pre_state: { ...this.preState },
          post_state: { ...this.postState, change_label: this.changeLabel },
          experience: {
            overall_rating: this.overallRating || null,
            relaxation_rating: this.ratings[0].value || null,
            music_match_rating: this.ratings[1].value || null,
            continue_use: this.continueUse,
            favorite: this.favorite,
            disliked_features: [],
            disliked_instruments: [],
            liked_features: this.likedFeatures,
            adjustment_preferences: this.adjustmentPreferences,
            comment: this.comment
          },
          playback,
          submitted_at: new Date().toISOString()
        })
        const response = await submitFeedback(payload)
        updateSprint3Session({ feedback: response, feedback_payload: payload })
        uni.navigateTo({ url: '/pages/complete/complete' })
      } catch (error) {
        this.status = 'error'
        this.errorMsg = error.message || '提交失败，请检查网络'
      }
    }
  }
}
</script>
<style scoped>
.change-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18rpx;
}
.change-card {
  min-height: 150rpx;
  padding: 24rpx;
  border: 2rpx solid #d8d1c3;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #3f4f47;
  background: #fffdf9;
  font-size: 30rpx;
  font-weight: 600;
}
.change-card.active {
  border-color: #4a6b5c;
  background: #eaf1ed;
  color: #2f5142;
  box-shadow: 0 8rpx 20rpx rgba(74, 107, 92, 0.14);
}
.section-heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}
.inline-title {
  margin: 0;
  padding: 0;
  border: 0;
}
.required-tag {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  background: #c44a3e;
  color: #fff;
  font-size: 22rpx;
}
.optional-block-title { display: block; margin-top: 28rpx; }
.favorite-row, .preference-heading { margin-top: 28rpx; }
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