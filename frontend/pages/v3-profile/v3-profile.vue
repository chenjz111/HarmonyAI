<template>
  <view class="profile-page v31-mobile-page v31-page-shell">
    <view class="page-heading">
      <view>
        <text class="eyebrow">MY HARMONY</text>
        <text class="profile-title">我的音乐</text>
      </view>
      <text class="mock-badge">{{ sourceBadge }}</text>
    </view>

    <view class="section-tabs" aria-label="音乐列表切换">
      <view :class="['section-tab', { active: activeSection === 'history' }]" @click="activeSection = 'history'"><text>历史音乐</text></view>
      <view :class="['section-tab', { active: activeSection === 'favorites' }]" @click="activeSection = 'favorites'"><text>我的收藏</text></view>
    </view>

    <view v-if="library.status === 'loading' && visibleItems.length === 0" class="state-card">
      <text class="state-title">正在加载音乐记录</text>
      <text class="state-copy">请稍候。</text>
    </view>
    <view v-else-if="library.status === 'error'" class="state-card error-card">
      <text class="state-title">加载失败</text>
      <text class="state-copy">{{ library.error }}</text>
      <view class="state-action" @click="reload"><text class="state-action-text">重试</text></view>
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
          <view class="favorite-toggle" :class="{ active: item.is_favorite }" @click.stop="toggleFavorite(item)">
            <text class="favorite-mark" aria-label="收藏">{{ item.is_favorite ? '♥' : '♡' }}</text>
          </view>
          <text :class="['availability', item.availability]">{{ item.availability_label }}</text>
        </view>
      </view>
    </view>

    <view v-if="library.hasMore && library.status !== 'loading'" class="load-more" @click="loadMore">
      <text class="load-more-text">加载更多</text>
    </view>

    <text class="preview-note">{{ sourceNote }}</text>
  </view>
</template>

<script>
import { MUSIC_CARD_V1_PREVIEW_FIXTURE } from "../../common/music-card-v1-preview-fixture.js"
import {
  createMusicLibraryPreview,
  createMusicLibraryStore,
  mergeMusicCards,
  musicPlayerUrl,
  normalizeUserTitle,
  presentMusicCard,
  splitFavorites,
} from "../../common/music-library-state.js"
import { createMusicLibraryApi } from "../../common/music-library-api.js"
import {
  MUSIC_LIBRARY_LIVE_ENABLED,
  createUniMusicLibraryTransport,
} from "../../common/music-library-transport.js"

// W1 reserves the canonical Player URL, but the existing Player is still
// session-scoped and does not consume music_id. Keep cards inert until the
// historical read integration and permission tests are approved.
const HISTORICAL_PLAYER_LINK_ENABLED = false

// 数据源门禁：默认关闭 → 使用冻结预览 fixture；显式开启后才走真实 Music Library API。
// 真实启用仍需 Backend API + owner 隔离 + stream 安全 Gate。
const LIVE_SOURCE_ENABLED = MUSIC_LIBRARY_LIVE_ENABLED === true

function readOwnerId() {
  try {
    const id = uni.getStorageSync("v3_public_user_id")
    return id || null
  } catch (e) {
    return null
  }
}

export default {
  data() {
    return {
      activeSection: "history",
      library: createMusicLibraryPreview("ready", MUSIC_CARD_V1_PREVIEW_FIXTURE),
      favoriteBusy: false,
      titleBusy: false,
    }
  },
  computed: {
    visibleItems() {
      return this.activeSection === "favorites" ? this.library.favorites : this.library.history
    },
    sourceBadge() {
      return LIVE_SOURCE_ENABLED ? "我的音乐" : "界面预览 · 虚构数据"
    },
    sourceNote() {
      return LIVE_SOURCE_ENABLED
        ? "音乐记录来自你的账号；音频可用性以服务端状态为准。"
        : "当前仅展示冻结 DTO 的本地 Mock，不代表后端已联调。"
    },
  },
  onLoad() {
    if (LIVE_SOURCE_ENABLED) this.setupLiveSource()
  },
  methods: {
    // ===== 数据源（门禁关闭时保持冻结预览 fixture） =====

    setupLiveSource() {
      this.api = createMusicLibraryApi({
        request: createUniMusicLibraryTransport({ getAccessToken: () => readOwnerId() }),
        getOwnerId: readOwnerId,
        enabled: true,
      })
      this.store = createMusicLibraryStore({
        fetchPage: (args) => this.api.listMusicAssets(args),
        getOwnerId: readOwnerId,
      })
      this.reload()
    },

    applyStoreState(state) {
      const history = (state.items || []).map(presentMusicCard)
      this.library = {
        status: state.status === "idle" ? "loading" : state.status,
        history,
        favorites: splitFavorites(history),
        error: state.error ? state.error.message || "暂时无法加载音乐记录" : null,
        hasMore: !!state.hasMore,
      }
    },

    async reload() {
      if (!this.store) return
      this.library = Object.assign({}, this.library, { status: "loading", error: null })
      this.applyStoreState(await this.store.loadFirstPage())
    },

    async loadMore() {
      if (!this.store) return
      this.applyStoreState(await this.store.loadMore())
    },

    // ===== 卡片交互 =====

    openMusic(item) {
      if (!item.can_open || !HISTORICAL_PLAYER_LINK_ENABLED) return
      uni.navigateTo({ url: musicPlayerUrl(item.music_id) })
    },

    // 收藏是独立 owner-scoped 变更：乐观更新 + 失败回滚，不作为偏好学习证据
    async toggleFavorite(item) {
      if (this.favoriteBusy || !this.api) return
      this.favoriteBusy = true
      const target = !item.is_favorite
      this.patchCard(item.music_id, { is_favorite: target })
      try {
        await this.api.setFavorite(
          { music_id: item.music_id, source_type: item.source_type },
          target
        )
      } catch (e) {
        this.patchCard(item.music_id, { is_favorite: !target })
        uni.showToast({ title: e.message || "收藏操作失败，请重试", icon: "none" })
      } finally {
        this.favoriteBusy = false
      }
    },

    // 标题编辑：CAS（expected_version）+ 显式 null 清除；冲突时提示并刷新
    async editTitle(item) {
      if (this.titleBusy || !this.api) return
      const result = await new Promise((resolve) => {
        uni.showModal({
          title: "修改标题",
          editable: true,
          placeholderText: "留空并确认可清除自定义标题",
          content: item.user_title || "",
          success: (res) => resolve(res),
          fail: () => resolve({ confirm: false }),
        })
      })
      if (!result || !result.confirm) return
      const nextTitle = normalizeUserTitle(result.content)
      this.titleBusy = true
      try {
        const updated = await this.api.setMusicTitle(item.music_id, nextTitle, item.metadata_version)
        this.patchCard(item.music_id, {
          user_title: nextTitle,
          display_title: nextTitle || item.default_title,
          metadata_version:
            updated && updated.metadata_version !== undefined
              ? updated.metadata_version
              : item.metadata_version,
        })
      } catch (e) {
        if (e && e.code === "METADATA_VERSION_CONFLICT") {
          uni.showToast({ title: "标题已在别处更新，正在刷新", icon: "none" })
          await this.reload()
        } else {
          uni.showToast({ title: e.message || "标题修改失败，请重试", icon: "none" })
        }
      } finally {
        this.titleBusy = false
      }
    },

    patchCard(musicId, patch) {
      const next = this.library.history.map((card) =>
        card.music_id === musicId ? Object.freeze(Object.assign({}, card, patch)) : card
      )
      this.library = Object.assign({}, this.library, {
        history: next,
        favorites: splitFavorites(next),
      })
    },

    musicPlayerUrl,
    mergeMusicCards,
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
.favorite-toggle { padding: 6rpx 10rpx; }
.favorite-mark { color: #a9b6b1; font-size: 31rpx; }
.favorite-toggle.active .favorite-mark { color: #c9785c; }
.availability { color: #26735f; font-size: 21rpx; white-space: nowrap; }
.availability.expired, .availability.deleted, .availability.missing, .availability.quarantined { color: #8a7670; }
.state-card { margin-top: 28rpx; padding: 64rpx 32rpx; border-radius: 26rpx; background: rgba(255,255,255,.82); text-align: center; }
.state-title { display: block; color: #244b43; font-size: 31rpx; font-weight: 650; }
.state-copy { display: block; margin-top: 16rpx; color: #7a8984; font-size: 24rpx; line-height: 1.7; }
.state-action { display: inline-block; margin-top: 28rpx; padding: 14rpx 44rpx; border-radius: 999rpx; background: #2f806b; }
.state-action-text { color: #fff; font-size: 26rpx; }
.error-card { border: 1rpx solid rgba(168,94,73,.18); }
.load-more { margin-top: 26rpx; padding: 22rpx; border-radius: 20rpx; background: rgba(255,255,255,.72); text-align: center; }
.load-more-text { color: #2f806b; font-size: 26rpx; }
.preview-note { display: block; margin: 34rpx 12rpx 0; color: #87948f; font-size: 21rpx; line-height: 1.6; text-align: center; }
</style>
