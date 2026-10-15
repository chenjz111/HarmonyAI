<template>
  <view class="page han-page v31-home">
    <view class="han-page-content page-inner">
      <view class="hero">
        <view class="brand-row">
          <view class="brand-logo home-art home-art--logo" aria-hidden="true"></view>
          <view class="brand-meta">
            <text class="brand-name">HarmonyAI</text>
            <text class="brand-tagline">中医灵感 · 音乐疗愈</text>
          </view>
        </view>
      </view>
      <view class="content-area">
        <view v-if="loading" class="loading-state">
          <view class="loading-ring"></view>
          <text class="loading-text">正在备茶</text>
        </view>
        <view v-else-if="error" class="error-state">
          <view class="error-seal"><text class="error-seal-text">静</text></view>
          <text class="error-title">暂时无法开始</text>
          <text class="error-desc">{{ error }}</text>
          <button class="retry-btn" @click="init">重试</button>
          <text class="error-hint">若持续出现，请检查网络后再次尝试 · 你不必着急</text>
        </view>
        <view v-else class="entry-content">
          <text class="home-slogan">让音乐，陪你回到更好的自己</text>
          <view class="home-slogan-line"></view>
          <text class="home-subtitle">以中医为本 · 用音乐疗愈身心</text>
          <view class="choice-stack">
            <button
              v-for="(choice, idx) in entry.choices"
              :key="choice.id"
              class="choice-card"
              :class="{ 'choice-card-loading': submittingId === choice.id }"
              :disabled="submitting"
              @click="choose(choice)"
            >
              <view class="choice-card-main">
                <view class="choice-icon home-art" :class="idx === 0 ? 'home-art--document' : 'home-art--survey'" aria-hidden="true"></view>
                <view class="choice-body">
                  <text class="choice-label">{{ choice.label }}</text>
                  <text class="choice-desc">{{ choice.desc }}</text>
                </view>
                <view class="choice-arrow" aria-hidden="true"><text class="choice-arrow-text">›</text></view>
              </view>
              <text class="choice-detail">{{ choice.detail }}</text>
            </button>
          </view>
          <view class="home-footer">
            <text class="home-footer-copy">MUSIC HEALS A BETTER YOU</text>
            <view class="footer-stroke"></view>
            <text class="footer-hint">全程数据仅用于本次聆听</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
/**
 * V3.1 首页（双入口选择）
 * 合同依据（V3.1_FREEZE_BASELINE 83fe2f4）：
 *   - docs/product/app-v3.1-teacher-user-flow.md §3（首页只保留核心入口）
 *   - Issue #111 §2：打开 APP 直接进入首页，不再经过旧 Welcome 页
 *
 * 首页两张入口卡片：
 *   - 我有就诊资料（上传资料）→ 资料上传页
 *   - 我没有就诊资料（填写问卷）→ 直接进入近期状态问卷
 * 品牌名称/Logo 为占位（冻结 §13 待设计，不阻塞功能收口）。
 *
 * v2 重写（水墨国风）：
 *   - 全页 .han-page 山水背景
 *   - 选项卡改为宣纸卡片 + 印章角标
 *   - 错误态用朱砂印章 + 减压文案
 *   - 业务逻辑 init() / choose() 完全保留
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      entry: null,
      submitting: false,
      submittingId: null,
      error: "",
    }
  },
  // 首页是 tabBar 页面，返回时实例不会重新创建；每次重新显示都开始一轮新评估。
  onShow() {
    this.init()
  },
  methods: {
    async init() {
      this.loading = true
      this.error = ""
      try {
        await apiV3.guestAuth()
        const session = await apiV3.createSession()
        apiV3.rememberSession(session)
        this.entry = {
          page: "entry",
          session_id: session.session_id,
          title: "了解你的近况",
          description: "为你生成专属音乐。",
          // 冻结 §3：首页只保留两个核心入口
          choices: [
            { id: "with_document", label: "我有就诊资料", desc: "上传资料", detail: "基于就诊资料，生成更个性化的音乐方案", route: "/pages/v3-material/v3-material" },
            { id: "without_document", label: "我没有就诊资料", desc: "填写问卷", detail: "通过问卷了解身心状态，定制专属音乐方案", route: "/pages/v3-questionnaire/v3-questionnaire" },
          ],
        }
      } catch (e) {
        this.error = e.message || "加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    async choose(choice) {
      if (this.submitting) return
      this.submitting = true
      this.submittingId = choice.id
      try {
        await apiV3.selectMode(choice.id)
        uni.navigateTo({ url: choice.route })
      } catch (e) {
        uni.showToast({ title: e.message || "选择失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
        this.submittingId = null
      }
    },
  },
}
</script>

<style scoped>
.page {
  position: relative;
  width: 100%;
  max-width: 430px;
  min-height: calc(100vh - 66px);
  margin: 0 auto;
  box-sizing: border-box;
  overflow: hidden;
  background: #eef8f2 url("/static/v31-home/home-watercolor-v1.png") center top / cover no-repeat;
}
.v31-home::before, .v31-home::after { display: none !important; content: none !important; }
.page-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 430px;
  min-height: calc(100vh - 66px);
  margin: 0 auto;
  padding: calc(32px + env(safe-area-inset-top)) clamp(14px, 4.6vw, 20px) 110px;
  box-sizing: border-box;
}
.hero { margin-bottom: 26px; }
.brand-row, .brand-meta, .entry-content, .loading-state, .error-state, .choice-body, .home-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.brand-row { gap: 6px; }
.home-art {
  background-image: url("/static/v31-home/home-icons-v2.png");
  background-repeat: no-repeat;
  background-size: 300% 100%;
}
.home-art--logo { width: 60px; height: 60px; border-radius: 17px; background-position: left; box-shadow: 0 8px 22px rgba(13,113,87,.19); }
.brand-name { margin-top: 1px; font: 700 26px/1.15 Georgia,"Times New Roman",serif; letter-spacing: .01em; color: #103f36; }
.brand-tagline { margin-top: 4px; font-size: 13px; line-height: 1.4; letter-spacing: .12em; color: #78847f; }
.content-area { width: 100%; }
.loading-state { justify-content: center; min-height: 360px; color: #68807a; }
.loading-ring { width: 28px; height: 28px; margin-bottom: 12px; border: 2px solid rgba(7,151,119,.18); border-top-color: #079777; border-radius: 50%; animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font: 15px/1.4 "KaiTi","STKaiti",serif; letter-spacing: .12em; }
.error-state { padding: 54px 12px; text-align: center; }
.error-seal { display: flex; align-items: center; justify-content: center; width: 64px; height: 64px; margin-bottom: 18px; border: 1px solid #a64c3d; border-radius: 12px; background: rgba(255,255,255,.72); }
.error-seal-text { font: 700 34px/1 "KaiTi","STKaiti",serif; color: #a64c3d; }
.error-title { margin-bottom: 8px; font: 700 21px/1.3 "KaiTi","STKaiti",serif; color: #174d44; }
.error-desc { max-width: 290px; margin-bottom: 20px; font-size: 14px; line-height: 1.65; color: #667873; }
.retry-btn { min-width: 150px; min-height: 44px; border-radius: 12px; background: #08795f; color: #fff; font-size: 15px; }
.error-hint { margin-top: 16px; font-size: 12px; line-height: 1.6; color: #7b8d88; }
.home-slogan { display: block; text-align: center; font: 400 clamp(17px,4.7vw,19px)/1.5 "STKaiti","KaiTi",serif; letter-spacing: .035em; color: #176251; }
.home-slogan-line { width: 112px; height: 4px; margin: 6px auto 13px; border-radius: 50%; background: linear-gradient(90deg,transparent,#0e765b 35%,rgba(19,117,91,.55) 78%,transparent); transform: rotate(-2deg); }
.home-subtitle { display: block; margin-bottom: 23px; text-align: center; font-size: 13px; line-height: 1.45; letter-spacing: .1em; color: #6e7d76; }
.choice-stack { display: flex; flex-direction: column; gap: 12px; width: 100%; margin-bottom: 16px; }
.choice-card {
  position: relative; display: flex; flex-direction: column; justify-content: center;
  width: 100%; min-height: 144px; margin: 0; padding: 12px 13px 13px;
  box-sizing: border-box; border: 3px solid rgba(255,255,255,.96); border-radius: 23px;
  text-align: left; white-space: normal; line-height: normal;
  background: rgba(240,252,247,.86);
  box-shadow: 0 8px 22px rgba(31,105,84,.12),inset 0 0 0 1px rgba(73,154,126,.09);
  backdrop-filter: blur(4px); transition: transform .2s ease;
}
.choice-card::after { border: none; }
.choice-card:nth-child(2) { background: rgba(255,248,235,.9); box-shadow: 0 8px 22px rgba(150,110,54,.1); }
.choice-card:active { transform: translateY(-2px); }
.choice-card:focus-visible { outline: 2px solid #079777; outline-offset: 3px; }
.choice-card-loading { opacity: .62; }
.choice-card-main { display: flex; align-items: center; width: 100%; gap: 12px; }
.choice-icon { width: clamp(72px,23vw,92px); height: clamp(72px,23vw,92px); flex: 0 0 auto; border-radius: 50%; }
.home-art--document { background-position: center; }
.home-art--survey { background-position: right; }
.choice-body { align-items: flex-start; min-width: 0; flex: 1; }
.choice-label { font-size: clamp(18px,5.3vw,21px); font-weight: 700; line-height: 1.3; color: #103d34; }
.choice-desc { margin-top: 6px; font-size: clamp(15px,4.35vw,17px); line-height: 1.3; color: #7b8580; }
.choice-arrow { display: flex; align-items: center; justify-content: center; width: 30px; height: 30px; flex: 0 0 auto; border-radius: 50%; background: rgba(7,151,119,.1); }
.choice-card:nth-child(2) .choice-arrow { background: rgba(190,139,43,.12); }
.choice-arrow-text { margin-top: -2px; font: 300 30px/1 Arial,sans-serif; color: #079777; }
.choice-card:nth-child(2) .choice-arrow-text { color: #a77419; }
.choice-detail { display: block; width: 100%; margin-top: 8px; box-sizing: border-box; font-size: 12px; line-height: 1.55; color: #6c8077; }
.home-footer { gap: 8px; margin-top: 2px; }
.home-footer-copy { font: 400 8px/1.4 Arial,sans-serif; letter-spacing: .32em; color: #598178; }
.footer-stroke { width: 43px; height: 2px; background: linear-gradient(90deg,transparent,#176251,transparent); }
.footer-hint { font-size: 10px; line-height: 1.35; color: #58776b; }
@media (max-width: 350px) {
  .page-inner { padding-left: 12px; padding-right: 12px; padding-top: 24px; }
  .hero { margin-bottom: 20px; }
  .home-art--logo { width: 54px; height: 54px; }
  .brand-name { font-size: 24px; }
  .choice-card { min-height: 132px; padding: 10px; }
  .choice-card-main { gap: 8px; }
  .choice-icon { width: 67px; height: 67px; }
  .choice-arrow { width: 24px; height: 24px; }
  .choice-label { font-size: 17px; }
  .choice-detail { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) { .loading-ring { animation: none; } .choice-card { transition: none; } }
</style>
