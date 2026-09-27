<template>
  <view class="generation-page">
    <view class="generation-shell">
      <view class="brand-row">
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy">
          <text class="brand-name">HarmonyAI</text>
          <text class="brand-tagline">用音乐，陪伴更好的你</text>
        </view>
      </view>

      <view class="generation-card">
        <view class="ink-ring" :class="{ 'ink-ring--still': phase === phases.CANCELLED || phase === phases.FAILED }">
          <text class="ink-note">♫</text>
        </view>

        <template v-if="phase === phases.PREPARING || phase === phases.IDLE">
          <text class="generation-title">正在准备你的音乐</text>
          <text class="generation-copy">正在整理本次音乐方案，请稍候。</text>
        </template>

        <template v-else-if="phase === phases.GENERATING">
          <text class="generation-title">正在生成你的音乐……</text>
          <text class="generation-copy">{{ statusCopy || '请稍候，我们会在音乐准备好后自动进入播放。' }}</text>
          <button v-if="canCancel" class="quiet-action" @click="cancel">取消生成</button>
        </template>

        <template v-else-if="phase === phases.FAILED">
          <text class="generation-title">暂时未能完成</text>
          <text class="generation-copy">{{ statusCopy || '请稍后重试。' }}</text>
          <button class="primary-action" @click="retry">重试</button>
        </template>

        <template v-else-if="phase === phases.CANCELLED">
          <text class="generation-title">已取消生成</text>
          <text class="generation-copy">需要时可以重新开始。</text>
          <button class="primary-action" @click="retry">重新生成</button>
        </template>

        <template v-else-if="phase === phases.PLAYABLE">
          <text class="generation-title">音乐已准备好</text>
          <text class="generation-copy">正在进入播放页。</text>
        </template>
      </view>

      <text class="page-motto">—　五音和鸣 · 乐养身心　—</text>
    </view>
  </view>
</template>

<script>
import { apiV3 } from "../../common/api-v3.js"
import {
  MUSIC_GENERATION_FLOW_PHASES,
  createMusicGenerationFlow,
} from "../../common/music-generation-flow.js"

export default {
  data() {
    return {
      phases: MUSIC_GENERATION_FLOW_PHASES,
      phase: MUSIC_GENERATION_FLOW_PHASES.IDLE,
      statusCopy: "",
      canCancel: false,
      generationFlow: null,
      unsubscribeFlow: null,
      pageActive: false,
      playerNavigationStarted: false,
    }
  },
  onLoad() {
    this.pageActive = true
    this.setupFlow()
    void this.generationFlow.start()
  },
  onHide() {
    if (this.generationFlow) this.generationFlow.onHide()
  },
  onShow() {
    if (this.generationFlow) void this.generationFlow.onShow()
  },
  onUnload() {
    this.pageActive = false
    if (this.unsubscribeFlow) this.unsubscribeFlow()
    if (this.generationFlow) this.generationFlow.dispose()
    this.unsubscribeFlow = null
    this.generationFlow = null
  },
  methods: {
    setupFlow() {
      if (this.generationFlow) return
      this.generationFlow = createMusicGenerationFlow({
        api: {
          ensureMusicBasis: () => apiV3.getMusicBasis({ allowCreate: true }),
          findPersistedTask: apiV3.pollMusicGeneration,
          startGeneration: apiV3.startMusicGeneration,
          syncTask: apiV3.pollMusicGeneration,
          cancelTask: apiV3.cancelMusicGeneration,
        },
      })
      this.unsubscribeFlow = this.generationFlow.subscribe(snapshot => {
        this.applyFlowSnapshot(snapshot)
      })
    },
    applyFlowSnapshot(snapshot) {
      if (!this.pageActive) return
      this.phase = snapshot.phase
      this.statusCopy = snapshot.copy
      this.canCancel = snapshot.canCancel
      if (
        snapshot.phase === MUSIC_GENERATION_FLOW_PHASES.PLAYABLE &&
        snapshot.asset && snapshot.asset.music_ref && snapshot.asset.music_ref.music_id &&
        !this.playerNavigationStarted
      ) {
        this.playerNavigationStarted = true
        uni.redirectTo({ url: "/pages/v3-player/v3-player" })
      }
    },
    retry() {
      if (this.generationFlow) void this.generationFlow.retry()
    },
    cancel() {
      if (this.generationFlow) void this.generationFlow.cancel()
    },
  },
}
</script>

<style scoped>
.generation-page {
  min-height: 100vh;
  color: #0b4f51;
  background: #edf7f3;
}
.generation-shell {
  box-sizing: border-box;
  width: 100%;
  max-width: 430px;
  min-height: 100vh;
  margin: 0 auto;
  padding: 14px 18px 36px;
  background-color: #fbfcf7;
  background-image: linear-gradient(rgba(255,255,252,.18),rgba(255,255,252,.18)), url('/static/v31-questionnaire/questionnaire-background-q34.png');
  background-repeat: no-repeat;
  background-position: center top;
  background-size: cover;
}
.brand-row { display:flex; align-items:center; min-height:46px; gap:8px; }
.brand-leaf { width:42px; height:42px; }
.brand-copy { display:flex; flex-direction:column; gap:1px; }
.brand-name { font-size:18px; font-weight:750; line-height:1.15; }
.brand-tagline { font-size:10px; letter-spacing:2px; }
.generation-card {
  display:flex;
  flex-direction:column;
  align-items:center;
  margin:84px 4px 0;
  padding:46px 24px 40px;
  border:1px solid rgba(55,102,92,.10);
  border-radius:18px;
  background:rgba(255,255,252,.88);
  box-shadow:0 8px 24px rgba(31,72,62,.10);
  text-align:center;
}
.ink-ring {
  display:flex;
  align-items:center;
  justify-content:center;
  width:88px;
  height:88px;
  margin-bottom:28px;
  border:5px solid rgba(36,105,94,.18);
  border-top-color:#28776a;
  border-radius:50%;
  animation:spin 1.4s linear infinite;
}
.ink-ring--still { animation:none; }
.ink-note { color:#24695e; font-size:38px; }
.generation-title { color:#064c50; font-family:'KaiTi','STKaiti',serif; font-size:28px; font-weight:800; }
.generation-copy { max-width:290px; margin-top:14px; color:#426d69; font-size:14px; line-height:1.75; }
.primary-action,.quiet-action { min-width:154px; margin-top:28px; border-radius:24px; font-size:15px; }
.primary-action { color:#fff; background:#28776a; }
.quiet-action { color:#315f5c; background:rgba(220,234,228,.78); }
.primary-action::after,.quiet-action::after { border:0; }
.page-motto { display:block; margin-top:28px; color:#486f6b; font-family:'KaiTi','STKaiti',serif; font-size:13px; letter-spacing:1px; text-align:center; }
@keyframes spin { to { transform:rotate(360deg); } }
@media (max-width:350px) {
  .generation-shell { padding-left:10px; padding-right:10px; }
  .generation-card { margin-top:62px; padding-left:16px; padding-right:16px; }
}
</style>
