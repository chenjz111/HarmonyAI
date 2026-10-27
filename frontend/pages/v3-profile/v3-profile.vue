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
      <view :class="['section-tab', { active: activeSection === 'history' }]" @click="selectSection('history')"><text>历史音乐</text></view>
      <view :class="['section-tab', { active: activeSection === 'favorites' }]" @click="selectSection('favorites')"><text>我的收藏</text></view>
      <view :class="['section-tab', { active: activeSection === 'preferences' }]" @click="selectSection('preferences')"><text>个性化偏好</text></view>
      <view :class="['section-tab', { active: activeSection === 'account' }]" @click="selectSection('account')"><text>账号与数据</text></view>
      <view :class="['section-tab', { active: activeSection === 'about' }]" @click="selectSection('about')"><text>关于</text></view>
    </view>

    <view v-if="activeSection === 'preferences'" class="state-card">
      <text class="state-title">个性化偏好</text>
      <text class="state-copy">长期偏好学习尚未开启。收藏不会自动成为学习证据，也不会改变已生成的音乐。</text>
      <text class="state-copy">可从具体音乐查看或删除反馈。清除学习证据资格会保留未单独删除的历史反馈。</text>
    </view>
    <view v-else-if="activeSection === 'account'" class="state-card">
      <text class="state-title">账号与数据</text>
      <text class="state-copy">游客可直接体验。游客数据依赖当前有效身份，凭据丢失或过期后不能保证恢复。</text>
      <view class="account-modes">
        <button :disabled="!accountAvailable || accountBusy" @click="accountMode = 'bind'">绑定账号以保留数据</button>
        <button :disabled="!accountAvailable || accountBusy" @click="accountMode = 'login'">登录已有账号</button>
      </view>
      <text v-if="!accountAvailable" class="state-copy">注册与登录尚未开放：安全存储和平台连接尚未完成验收。目前不能在此切换账号。</text>
      <view v-if="accountAvailable" class="account-form">
        <text class="state-copy">{{ accountMode === 'bind' ? '主动绑定当前游客身份，保留合法归属的数据。' : '登录已有账号不会合并或转移当前游客数据。' }}</text>
        <text class="state-copy">没有已验证的邮箱或手机号时不支持自助找回密码，请妥善保存凭据。</text>
        <input v-model="accountUsername" :disabled="accountBusy" maxlength="32" placeholder="用户名：3–32 位字母、数字或下划线" />
        <input v-model="accountPassword" :disabled="accountBusy" :password="true" :maxlength="-1" placeholder="密码：15–1024 个字符，不截断" />
        <button :disabled="accountBusy" @click="submitAccount">{{ accountBusy ? '正在处理' : (accountMode === 'bind' ? '注册并绑定' : '登录') }}</button>
        <button v-if="accountOwner" :disabled="accountBusy" @click="logoutAccount(false)">退出当前设备</button>
        <button v-if="accountOwner" :disabled="accountBusy" @click="logoutAccount(true)">退出所有设备</button>
        <button v-if="accountOwner" :disabled="accountBusy" @click="togglePasswordChange">{{ passwordChangeOpen ? '取消修改密码' : '修改密码' }}</button>
        <view v-if="accountOwner && passwordChangeOpen">
          <text class="state-copy">修改成功后所有设备需要重新登录。结果未确认时，请重新认证，不要重复提交。</text>
          <input v-model="currentPassword" :disabled="accountBusy" :password="true" :maxlength="-1" placeholder="当前密码" />
          <input v-model="newPassword" :disabled="accountBusy" :password="true" :maxlength="-1" placeholder="新密码：15–1024 个字符" />
          <input v-model="confirmNewPassword" :disabled="accountBusy" :password="true" :maxlength="-1" placeholder="再次输入新密码" />
          <button :disabled="accountBusy" @click="changeAccountPassword">确认修改密码</button>
        </view>
      </view>
      <button v-if="accountGuestReady" :disabled="accountBusy" @click="returnToGuest">使用游客体验</button>
      <text v-if="accountError" class="state-copy">{{ accountError }}</text>
    </view>
    <view v-else-if="activeSection === 'about'" class="state-card">
      <text class="state-title">HarmonyAI</text>
      <text class="state-copy">音乐辅助调养不能替代专业医疗或心理帮助。</text>
    </view>
    <template v-else>
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
          <view v-if="liveSourceEnabled" class="title-action" @click.stop="editTitle(item)"><text>修改标题</text></view>
          <view v-if="liveSourceEnabled" class="title-action" @click.stop="openMusicFeedback(item)"><text>本曲反馈</text></view>
          <view v-if="liveSourceEnabled" class="title-action" @click.stop="openOriginalSource(item)"><text>生成来源</text></view>
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
    </template>

    <text class="preview-note">{{ sourceNote }}</text>
  </view>
</template>

<script>
import { MUSIC_CARD_V1_PREVIEW_FIXTURE } from "../../common/music-card-v1-preview-fixture.js"
import { registeredAccountRuntime, startAccountStartup } from "../../common/auth-runtime.js"
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
  readV3AccessToken,
} from "../../common/music-library-transport.js"

// 数据源门禁：默认关闭 → 使用冻结预览 fixture；显式开启后才走真实 Music Library API。
// 真实启用仍需 Backend API + owner 隔离 + stream 安全 Gate。
const LIVE_SOURCE_ENABLED = MUSIC_LIBRARY_LIVE_ENABLED === true
// One capability governs list, navigation and Player; production remains closed.
const HISTORICAL_PLAYER_LINK_ENABLED = LIVE_SOURCE_ENABLED

function readOwnerId() {
  try {
    const id = uni.getStorageSync("v3_public_user_id")
    return id || null
  } catch (e) {
    return null
  }
}

// A page operation belongs to one authentication instance, not just to a public
// owner name. The credential and the monotonic login epoch stay in this private
// closure, never in render data, to reject unobserved A -> B -> A transitions.
function authEpoch() {
  try {
    const value = Number(uni.getStorageSync("v3_auth_epoch"))
    return Number.isSafeInteger(value) && value >= 0 ? value : 0
  } catch (e) { return 0 }
}
function captureLiveIdentity() {
  const owner = readOwnerId()
  const token = readV3AccessToken()
  const epoch = authEpoch()
  return Object.freeze({
    owner,
    matches: () => readOwnerId() === owner &&
      readV3AccessToken() === token && authEpoch() === epoch,
  })
}

export default {
  data() {
    return {
      activeSection: "history",
      accountAvailable: !!(registeredAccountRuntime && registeredAccountRuntime.available),
      accountMode: "bind", accountUsername: "", accountPassword: "", accountBusy: false, accountError: "", accountOwner: null, accountSequence: 0, accountHidden: false, accountGuestReady: false,
      passwordChangeOpen: false, currentPassword: "", newPassword: "", confirmNewPassword: "",
      library: createMusicLibraryPreview("ready", MUSIC_CARD_V1_PREVIEW_FIXTURE),
      favoriteBusy: false,
      titleBusy: false,
      liveGeneration: 0,
      liveOwner: null,
      liveIdentity: null,
      liveDisposed: false,
      liveAuthReady: false,
    }
  },
  computed: {
    liveSourceEnabled() { return LIVE_SOURCE_ENABLED },
    visibleItems() {
      if (this.activeSection !== "history" && this.activeSection !== "favorites") return []
      // Computed render guard: never expose a stale page projection even when
      // identity changed while the page stayed visible (no onShow yet).
      if (LIVE_SOURCE_ENABLED && (this.liveDisposed || !this.liveAuthReady || !this.liveIdentity || !this.liveIdentity.matches())) return []
      return this.activeSection === "favorites" ? this.library.favorites : this.library.history
    },
    sourceBadge() {
      return LIVE_SOURCE_ENABLED ? "我的音乐" : "界面预览 · 虚构数据"
    },
    sourceNote() {
      if (LIVE_SOURCE_ENABLED && !this.liveAuthReady) return "当前环境无法安全同步身份，音乐库暂不可用。"
      return LIVE_SOURCE_ENABLED
        ? "音乐记录来自你的账号；音频可用性以服务端状态为准。"
        : "当前仅展示冻结 DTO 的本地 Mock，不代表后端已联调。"
    },
  },
  onLoad() {
    this.liveDisposed = false
    this.syncAccountView()
    if (LIVE_SOURCE_ENABLED || this.accountAvailable) {
      this.authChangeHandler = () => {
        this.syncAccountView()
        if (LIVE_SOURCE_ENABLED) this.ensureLiveOwner()
      }
      try {
        if (!["$on", "$off", "$emit"].every(name => typeof uni[name] === "function")) throw new Error("Authentication subscription unavailable")
        if (uni.$on("harmonyai:v3-auth-changed", this.authChangeHandler) === false) throw new Error("Authentication subscription rejected")
      } catch (e) {
        try { if (typeof uni.$off === "function") uni.$off("harmonyai:v3-auth-changed", this.authChangeHandler) } catch (ignored) { /* unavailable */ }
        this.accountAvailable = false
        this.accountOwner = null
        if (LIVE_SOURCE_ENABLED) this.library = createMusicLibraryPreview("empty")
        return
      }
    }
    if (LIVE_SOURCE_ENABLED) {
      this.library = createMusicLibraryPreview("empty")
      this.liveAuthReady = true
      this.setupLiveSource()
    }
  },
  async onShow() {
    this.accountHidden = false
    this.syncAccountView()
    if (this.accountAvailable) {
      const sequence = this.accountSequence
      try { await startAccountStartup(uni) }
      catch (error) {
        if (sequence === this.accountSequence && !this.accountHidden && !this.liveDisposed) this.accountError = "身份恢复未能确认，请重新登录；不会自动更换身份。"
      }
      if (sequence !== this.accountSequence || this.accountHidden || this.liveDisposed) return
      this.syncAccountView()
    }
    if (LIVE_SOURCE_ENABLED && !this.liveDisposed && this.api && this.ensureLiveOwner()) this.reload()
  },
  onHide() {
    this.accountHidden = true
    this.accountSequence++
    this.accountPassword = ""; this.accountUsername = ""; this.accountError = ""
    this.accountBusy = false
    this.accountOwner = null
    this.accountGuestReady = false
    this.clearPasswordChange(); this.passwordChangeOpen = false
  },
  onUnload() {
    this.accountSequence++; this.accountPassword = ""; this.accountUsername = ""
    this.clearPasswordChange()
    this.liveDisposed = true
    this.liveAuthReady = false
    try { if (this.authChangeHandler && typeof uni.$off === "function") uni.$off("harmonyai:v3-auth-changed", this.authChangeHandler) } catch (e) { /* unsupported */ }
    this.authChangeHandler = null
    if (this.historyStore) this.historyStore.invalidate()
    if (this.favoritesStore) this.favoritesStore.invalidate()
    this.liveGeneration += 1
    this.liveIdentity = null
    this.library = createMusicLibraryPreview("empty")
  },
  methods: {
    syncAccountView() {
      if (this.liveDisposed || this.accountHidden || !this.accountAvailable) { this.accountOwner = null; this.accountGuestReady = false; return }
      // Display only the runtime identity, never a cached public owner label.
      this.accountOwner = registeredAccountRuntime.owner?.() || null
      this.accountGuestReady = registeredAccountRuntime.canUseGuestAfterLogout?.() === true
      if (!this.accountOwner) { this.clearPasswordChange(); this.passwordChangeOpen = false }
    },
    clearPasswordChange() { this.currentPassword = ""; this.newPassword = ""; this.confirmNewPassword = "" },
    togglePasswordChange() {
      if (this.accountBusy) return
      this.clearPasswordChange(); this.passwordChangeOpen = !this.passwordChangeOpen
    },
    async changeAccountPassword() {
      if (!this.accountAvailable || !this.accountOwner || this.accountBusy || this.accountHidden || this.liveDisposed) { this.clearPasswordChange(); return }
      const current_password = this.currentPassword.normalize("NFC"), new_password = this.newPassword.normalize("NFC")
      if ([...current_password].length < 15 || [...current_password].length > 1024 || [...new_password].length < 15 || [...new_password].length > 1024 || new_password !== this.confirmNewPassword.normalize("NFC")) {
        this.accountError = "请检查密码长度，并确认两次新密码一致。"; this.clearPasswordChange(); return
      }
      const sequence = ++this.accountSequence, identity = captureLiveIdentity()
      this.accountBusy = true; this.accountError = ""
      try {
        const confirmed = await new Promise(resolve => uni.showModal({title:"修改密码",content:"修改成功会撤销所有设备的登录状态，需要使用新密码重新登录。确认继续？",success:result=>resolve(result.confirm===true),fail:()=>resolve(false)}))
        if (!confirmed || sequence !== this.accountSequence || this.accountHidden || this.liveDisposed || !identity.matches()) return
        await registeredAccountRuntime.changePassword({current_password,new_password})
        if (sequence !== this.accountSequence || this.accountHidden || this.liveDisposed) return
        this.accountMode = "login"
        uni.showToast({title:"密码已修改，请重新登录",icon:"none"})
      } catch (error) {
        if (sequence === this.accountSequence && !this.accountHidden && !this.liveDisposed) this.accountError = "修改结果未能确认，请重新认证；不要自动重复提交。"
      } finally {
        if (sequence === this.accountSequence) { this.clearPasswordChange(); this.accountPassword = ""; this.accountBusy = false; this.syncAccountView() }
      }
    },
    async returnToGuest() {
      if (!this.accountGuestReady || this.accountBusy || this.accountHidden || this.liveDisposed) return
      const sequence = ++this.accountSequence
      this.accountBusy = true; this.accountPassword = ""; this.accountError = ""
      try {
        const confirmed = await new Promise(resolve => uni.showModal({
          title:"使用游客体验", content:"将开始新的游客体验。原账号音乐仍归原账号，登录后可查看，不会转移给新游客。是否继续？",
          success:result=>resolve(result.confirm === true), fail:()=>resolve(false),
        }))
        if (!confirmed || sequence !== this.accountSequence || this.accountHidden || this.liveDisposed) return
        await registeredAccountRuntime.useGuestAfterLogout({confirmed:true})
        if (sequence !== this.accountSequence || this.accountHidden || this.liveDisposed) return
        this.syncAccountView()
        uni.switchTab({url:"/pages/entry/entry"})
      } catch (error) {
        if (sequence === this.accountSequence && !this.liveDisposed) this.accountError = "暂时无法进入游客体验，请重试或重新登录。"
      } finally { if (sequence === this.accountSequence) this.accountBusy = false }
    },
    openOriginalSource(item) {
      if (!LIVE_SOURCE_ENABLED || !item || !item.music_id || !this.ensureLiveOwner()) return
      uni.showModal({title:"生成来源",content:"原始资料查看尚未开放，不影响已获授权音乐的播放。",showCancel:false})
    },
    async submitAccount() {
      if (!this.accountAvailable || this.accountBusy) { this.accountPassword = ""; this.accountError = "账号功能尚未完成平台安全验收"; return }
      const username = this.accountUsername.toLowerCase(), password = this.accountPassword.normalize("NFC")
      if (!/^[a-z0-9_]{3,32}$/.test(username) || [...password].length < 15 || [...password].length > 1024) {
        this.accountError = "请检查用户名格式和密码长度"; this.accountPassword = ""; return
      }
      const sequence = ++this.accountSequence
      this.accountBusy = true; this.accountError = ""
      try {
        const result = await registeredAccountRuntime[this.accountMode === "bind" ? "bind" : "login"]({username,password})
        if (sequence !== this.accountSequence || this.liveDisposed) return
        this.accountOwner = result.public_user_id
        uni.showToast({title:"身份验证已完成",icon:"none"})
      } catch (error) {
        if (sequence === this.accountSequence && !this.liveDisposed) this.accountError = "身份验证未能确认，请检查凭据并重新认证。"
      } finally {
        if (sequence === this.accountSequence) { this.accountPassword = ""; this.accountBusy = false }
      }
    },
    async logoutAccount(allDevices) {
      if (!this.accountAvailable || this.accountBusy) return
      const sequence = ++this.accountSequence
      this.accountBusy = true; this.accountError = ""
      try { await registeredAccountRuntime.logout({allDevices}) }
      catch (error) { if (sequence === this.accountSequence && !this.liveDisposed) this.accountError = "本地身份已关闭，服务端撤销结果未能确认，请重新认证。" }
      finally { if (sequence === this.accountSequence) { this.accountPassword = ""; this.accountBusy = false; this.syncAccountView() } }
    },
    openMusicFeedback(item) {
      if (!LIVE_SOURCE_ENABLED || !this.liveAuthReady || !this.liveIdentity || !this.liveIdentity.matches()) return
      if (!item || !item.music_id) return
      uni.navigateTo({url:"/pages/v3-feedback/v3-feedback?mode=history&music_id="+encodeURIComponent(item.music_id)})
    },
    // ===== 数据源（门禁关闭时保持冻结预览 fixture） =====

    setupLiveSource() {
      if (this.liveDisposed || !this.liveAuthReady) return
      this.liveIdentity = captureLiveIdentity()
      this.liveOwner = this.liveIdentity.owner
      this.api = createMusicLibraryApi({
        request: createUniMusicLibraryTransport({ getAccessToken: () => readV3AccessToken() }),
        getOwnerId: readOwnerId,
        enabled: true,
      })
      this.historyStore = createMusicLibraryStore({ fetchPage: (args) => this.api.listMusicAssets(args), getOwnerId: readOwnerId })
      this.favoritesStore = createMusicLibraryStore({ fetchPage: (args) => this.api.listMusicFavorites(args), getOwnerId: readOwnerId })
      this.store = this.historyStore
      this.reload()
    },

    ensureLiveOwner() {
      if (this.liveDisposed) return false
      if (!LIVE_SOURCE_ENABLED) return true
      if (!this.liveAuthReady) return false
      if (this.liveIdentity && this.liveIdentity.matches()) return true
      this.liveIdentity = captureLiveIdentity()
      const owner = this.liveIdentity.owner
      this.liveOwner = owner
      this.liveGeneration += 1
      if (this.historyStore) this.historyStore.invalidate()
      if (this.favoritesStore) this.favoritesStore.invalidate()
      this.library = createMusicLibraryPreview("empty")
      if (this.store && owner) this.reload()
      return false
    },

    selectSection(section) {
      if (this.liveDisposed) return
      if (["preferences", "account", "about"].includes(section)) { this.activeSection = section; return }
      if (section !== "history" && section !== "favorites") return
      if (LIVE_SOURCE_ENABLED && !this.ensureLiveOwner()) return
      this.activeSection = section
      if (LIVE_SOURCE_ENABLED) {
        this.store = section === "favorites" ? this.favoritesStore : this.historyStore
        this.reload()
      }
    },

    applyStoreState(state) {
      if (this.liveDisposed || (LIVE_SOURCE_ENABLED && !this.liveAuthReady)) return
      const history = (state.items || []).map(presentMusicCard)
      this.library = {
        status: state.status === "idle" ? "loading" : state.status,
        history: this.activeSection === "history" ? history : [],
        favorites: this.activeSection === "favorites" ? history : [],
        error: state.error ? state.error.message || "暂时无法加载音乐记录" : null,
        hasMore: !!state.hasMore,
      }
    },

    async reload() {
      if (this.liveDisposed || !this.store) return
      if (LIVE_SOURCE_ENABLED && (!this.liveIdentity || !this.liveIdentity.matches())) { this.ensureLiveOwner(); return }
      this.library = Object.assign({}, this.library, { status: "loading", error: null })
      const generation = ++this.liveGeneration
      const store = this.store
      const identity = this.liveIdentity
      const state = await store.loadFirstPage()
      if (this.liveDisposed) return
      if (LIVE_SOURCE_ENABLED && (!identity || !identity.matches())) { this.ensureLiveOwner(); return }
      if (generation === this.liveGeneration && store === this.store) this.applyStoreState(state)
    },

    async loadMore() {
      if (this.liveDisposed || !this.store) return
      if (LIVE_SOURCE_ENABLED && (!this.liveIdentity || !this.liveIdentity.matches())) { this.ensureLiveOwner(); return }
      const generation = ++this.liveGeneration
      const store = this.store
      const identity = this.liveIdentity
      const state = await store.loadMore()
      if (this.liveDisposed) return
      if (LIVE_SOURCE_ENABLED && (!identity || !identity.matches())) { this.ensureLiveOwner(); return }
      if (generation === this.liveGeneration && store === this.store) this.applyStoreState(state)
    },

    // ===== 卡片交互 =====

    openMusic(item) {
      if (this.liveDisposed || (LIVE_SOURCE_ENABLED && (!this.ensureLiveOwner() || !this.liveOwner))) return
      if (!item.can_open || !HISTORICAL_PLAYER_LINK_ENABLED) return
      uni.navigateTo({ url: musicPlayerUrl(item.music_id) })
    },

    // 收藏是独立 owner-scoped 变更：乐观更新 + 失败回滚，不作为偏好学习证据
    async toggleFavorite(item) {
      if (this.liveDisposed || (LIVE_SOURCE_ENABLED && (!this.ensureLiveOwner() || !this.liveOwner))) return
      if (this.favoriteBusy || !this.api) return
      const identity = this.liveIdentity
      const generation = this.liveGeneration
      this.favoriteBusy = true
      const target = !item.is_favorite
      try {
        this.patchCard(item.music_id, { is_favorite: target })
        try {
          await this.api.setFavorite(
            { music_id: item.music_id, source_type: item.source_type },
            target
          )
          if (this.liveDisposed) return
          if (!identity || !identity.matches()) { this.ensureLiveOwner(); return }
        } catch (e) {
          if (this.liveDisposed) return
          if (!identity || !identity.matches()) { this.ensureLiveOwner(); return }
          if (generation === this.liveGeneration) {
            this.patchCard(item.music_id, { is_favorite: !target })
            uni.showToast({ title: e.message || "收藏操作失败，请重试", icon: "none" })
          }
        }
        if (!this.liveDisposed && identity && identity.matches() && this.liveIdentity === identity) {
          // A successful same-session mutation invalidates the selected list
          // even if the user switched tabs while the write was in flight.
          await this.reload()
        } else if (!this.liveDisposed) this.ensureLiveOwner()
      } finally {
        // Cleanup must not replace an exception from UI handling or refresh.
        this.favoriteBusy = false
      }
    },

    // 标题编辑：CAS（expected_version）+ 显式 null 清除；冲突时提示并刷新
    async editTitle(item) {
      if (this.liveDisposed || (LIVE_SOURCE_ENABLED && (!this.ensureLiveOwner() || !this.liveOwner))) return
      if (this.titleBusy || !this.api) return
      const identity = this.liveIdentity
      const generation = this.liveGeneration
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
      if (this.liveDisposed) return
      if (!identity || !identity.matches() || generation !== this.liveGeneration) { this.ensureLiveOwner(); return }
      if (!result || !result.confirm) return
      const nextTitle = normalizeUserTitle(result.content)
      this.titleBusy = true
      try {
        const updated = await this.api.setMusicTitle(item.music_id, nextTitle, item.metadata_version)
        if (!identity || !identity.matches() || generation !== this.liveGeneration) { this.ensureLiveOwner(); return }
        this.patchCard(item.music_id, {
          user_title: nextTitle,
          display_title: nextTitle || item.default_title,
          metadata_version:
            updated && updated.metadata_version !== undefined
              ? updated.metadata_version
              : item.metadata_version,
        })
      } catch (e) {
        if (!identity || !identity.matches() || generation !== this.liveGeneration) { this.ensureLiveOwner(); return }
        if (e && e.code === "TITLE_VERSION_CONFLICT") {
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
      const key = this.activeSection === "favorites" ? "favorites" : "history"
      const next = this.library[key].map((card) => card.music_id === musicId ? Object.freeze(Object.assign({}, card, patch)) : card)
      this.library = Object.assign({}, this.library, { [key]: next })
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
.section-tabs { display: flex; flex-wrap:wrap; gap: 14rpx; margin-top: 42rpx; padding: 8rpx; border-radius: 22rpx; background: rgba(255,255,255,.72); }
.section-tab { flex: 1 1 27%; padding: 20rpx; border-radius: 16rpx; color: #71847e; text-align: center; font-size: 27rpx; }
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
