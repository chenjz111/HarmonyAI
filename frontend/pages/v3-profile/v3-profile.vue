<template>
  <view class="profile-page v31-mobile-page v31-page-shell">
    <view class="page-heading">
      <view>
        <text class="eyebrow">MY HARMONY</text>
        <text class="profile-title">我的音乐</text>
      </view>
      <text class="mock-badge">界面预览 · 虚构数据</text>
    </view>

    <view class="section-tabs" aria-label="音乐列表切换">
      <view :class="['section-tab', { active: activeSection === 'history' }]" @click="activeSection = 'history'"><text>历史音乐</text></view>
      <view :class="['section-tab', { active: activeSection === 'favorites' }]" @click="activeSection = 'favorites'"><text>我的收藏</text></view>
    </view>

    <view v-if="library.status === 'loading'" class="state-card">
      <text class="state-title">正在加载音乐记录</text>
      <text class="state-copy">请稍候。</text>
    </view>
    <view v-else-if="library.status === 'error'" class="state-card error-card">
      <text class="state-title">加载失败</text>
      <text class="state-copy">{{ library.error }}</text>
    </view>
    <view v-else-if="visibleItems.length === 0" class="state-card">
      <text class="state-title">{{ activeSection === 'favorites' ? '还没有收藏' : '还没有历史音乐' }}</text>
      <text class="state-copy">完成音乐生成后，合法归属的音乐会显示在这里。</text>
    </view>

    <view v-else class="music-list">
      <view v-for="item in visibleItems" :key="item.music_id" :class="['music-card', { unavailable: !item.can_open }]" @click="openMusic(item)">
        <view class="card-main">
          <text class="music-title">{{ item.display_title }}</text>
          <view class="music-meta">
            <text>{{ item.duration_label }}</text><text>·</text><text>{{ item.playback_label }}</text>
          </view>
        </view>
        <view class="card-side">
          <text v-if="item.is_favorite" class="favorite-mark" aria-label="已收藏">♥</text>
          <text :class="['availability', item.availability]">{{ item.availability_label }}</text>
        </view>
      </view>
    </view>

    <text class="preview-note">当前仅展示冻结 DTO 的本地 Mock，不代表后端已联调。</text>
  </view>
</template>

<script>
import { MUSIC_CARD_V1_PREVIEW_FIXTURE } from "../../common/music-card-v1-preview-fixture.js"
import { createMusicLibraryPreview, musicPlayerUrl } from "../../common/music-library-state.js"

// W1 reserves the canonical Player URL, but the existing Player is still
// session-scoped and does not consume music_id. Keep cards inert until the
// historical read integration and permission tests are approved.
const HISTORICAL_PLAYER_LINK_ENABLED = false

export default {
  data() {
    return {
      activeSection: "history",
      library: createMusicLibraryPreview("ready", MUSIC_CARD_V1_PREVIEW_FIXTURE),
    }
  },
  computed: {
    visibleItems() {
      return this.activeSection === "favorites" ? this.library.favorites : this.library.history
    },
  },
  methods: {
    openMusic(item) {
      if (!item.can_open || !HISTORICAL_PLAYER_LINK_ENABLED) return
      uni.navigateTo({ url: musicPlayerUrl(item.music_id) })
    },
    musicPlayerUrl,
  },
}
</script>

<style scoped>
.profile-page { --v31-page-top-base: 96rpx; --v31-page-bottom-base: 180rpx; min-height: 100vh; box-sizing: border-box; padding-left: 36rpx; padding-right: 36rpx; background: linear-gradient(180deg, #f7fbf7 0%, #f0f6f2 100%); }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20rpx; }
.eyebrow { display: block; color: #6b837c; font-size: 20rpx; font-weight: 700; letter-spacing: .16em; }
.profile-title { display: block; margin-top: 8rpx; color: #133f38; font-family: "STKaiti", serif; font-size: 54rpx; font-weight: 700; }
.mock-badge { padding: 10rpx 16rpx; border-radius: 999rpx; color: #805c24; background: #fff2d6; font-size: 20rpx; white-space: nowrap; }
.section-tabs { display: flex; gap: 14rpx; margin-top: 42rpx; padding: 8rpx; border-radius: 22rpx; background: rgba(255,255,255,.72); }
.section-tab { flex: 1; padding: 20rpx; border-radius: 16rpx; color: #71847e; text-align: center; font-size: 27rpx; }
.section-tab.active { color: #fff; background: #2f806b; box-shadow: 0 10rpx 24rpx rgba(27,104,84,.18); }
.music-list { display: flex; flex-direction: column; gap: 20rpx; margin-top: 28rpx; }
.music-card { display: flex; justify-content: space-between; gap: 22rpx; padding: 30rpx; border: 1rpx solid rgba(59,112,97,.12); border-radius: 26rpx; background: rgba(255,255,255,.9); box-shadow: 0 14rpx 34rpx rgba(38,91,75,.08); }
.music-card.unavailable { background: rgba(245,246,243,.94); box-shadow: none; }
.card-main { min-width: 0; flex: 1; }
.music-title { display: block; overflow: hidden; color: #183f38; font-size: 31rpx; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.music-meta { display: flex; gap: 10rpx; margin-top: 16rpx; color: #758580; font-size: 23rpx; }
.card-side { display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between; gap: 18rpx; }
.favorite-mark { color: #c9785c; font-size: 31rpx; }
.availability { color: #26735f; font-size: 21rpx; white-space: nowrap; }
.availability.expired, .availability.deleted, .availability.missing, .availability.quarantined { color: #8a7670; }
.state-card { margin-top: 28rpx; padding: 64rpx 32rpx; border-radius: 26rpx; background: rgba(255,255,255,.82); text-align: center; }
.state-title { display: block; color: #244b43; font-size: 31rpx; font-weight: 650; }
.state-copy { display: block; margin-top: 16rpx; color: #7a8984; font-size: 24rpx; line-height: 1.7; }
.error-card { border: 1rpx solid rgba(168,94,73,.18); }
.preview-note { display: block; margin: 34rpx 12rpx 0; color: #87948f; font-size: 21rpx; line-height: 1.6; text-align: center; }
</style>
