<script>
/**
 * V3.1 资料异常页（统一异常分流）
 *
 * 合同依据（V3.1_FREEZE_BASELINE 83fe2f4）：
 *  - docs/product/app-v3.1-teacher-user-flow.md §4.2（Relevance Error 统一页面）
 *  - Issue #111 §4 Path D（INVALID / IRRELEVANT / INSUFFICIENT → 统一异常页面）
 *
 * 两种异常类型（?type=）：
 *  - ocr     ：资料已上传但未能识别/不适用于本次分析（冻结标准文案，不带技术细节）
 *  - network ：上传/网络/服务失败（Path E 异常降级，可重试）
 *
 * 冻结按钮（§4.2）：
 *  - 重新选择资料 → 返回上传页
 *  - 我没有合适的资料 → 转入无资料流程，直接进入问卷（不经描述页）
 * 页面不得出现任何暗示资料本身有医学问题或诊断出错的措辞（冻结 §4.2 禁用词清单）。
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      type: "ocr", // ocr | network
      discarding: false,
      retrying: false,
    }
  },
  onLoad(query) {
    this.type = query && query.type === "network" ? "network" : "ocr"
    uni.setNavigationBarTitle({
      title: this.type === "network" ? "资料上传未完成" : "资料异常",
    })
  },
  methods: {
    retry() {
      // 重新选择资料（按钮一）：回到资料上传页重新选择
      if (this.retrying) return
      this.retrying = true
      uni.redirectTo({ url: "/pages/v3-material/v3-material" })
    },
    async switchToQuestionnaire() {
      // 我没有合适的资料（按钮二）：转入无资料流程，直接进入问卷
      // 必须调用后端 Input Transition（discard_document）切换为无资料模式，不是前端隐藏
      if (this.discarding) return
      this.discarding = true
      try {
        const session = await apiV3.discardDocument()
        apiV3.rememberSession(session)
        // V3.1 冻结：无资料流程直接进入 5 页问卷（不经描述/补充页）
        uni.redirectTo({ url: "/pages/v3-questionnaire/v3-questionnaire" })
      } catch (e) {
        uni.showToast({ title: e.message || "切换失败，请重试", icon: "none" })
      } finally {
        this.discarding = false
      }
    },
  },
}
</script>

<template>
  <view class="material-error-page">
    <view class="material-error-container">
      <view class="material-error-brand">
        <image class="material-error-logo" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="material-error-brand-copy">
          <text class="material-error-brand-name">HarmonyAI</text>
          <text class="material-error-brand-tagline">用音乐，陪伴更好的你</text>
        </view>
        <view class="material-error-slogan">
          <text>五音和鸣</text>
          <text>心自安宁</text>
          <view class="material-error-seal"><text>和</text><text>谐</text></view>
        </view>
      </view>

      <view class="material-error-heading ink-fade-in">
        <text class="material-error-tag">有资料流程 · 异常分级</text>
        <text class="material-error-title">{{ type === "network" ? "资料暂时没有上传成功" : "这份资料暂时无法用于本次分析" }}</text>
        <text v-if="type === 'ocr'" class="material-error-subtitle">
          未识别到与本次状态评估相关的有效信息，请检查是否上传了合适的就诊资料。
        </text>
        <text v-else class="material-error-subtitle">网络或服务暂时不可用，请稍后重试。</text>
      </view>

      <view class="material-error-card ink-fade-up">
        <image
          class="material-error-illustration"
          src="/static/v31-material/upload-failed-illustration.png"
          mode="aspectFit"
        />
        <text class="material-error-card-title">{{ type === "network" ? "上传没有完成" : "资料暂时无法使用" }}</text>
        <text v-if="type === 'ocr'" class="material-error-card-desc">
          你可以重新选择合适的资料；也可以不使用资料，直接通过问卷完成本次评估。
        </text>
        <text v-else class="material-error-card-desc">
          请检查网络后重新选择资料；也可以不使用资料，直接通过问卷完成本次评估。
        </text>

        <view class="material-error-actions">
          <view class="material-error-button material-error-primary" :class="{ 'btn-disabled': retrying }" @click="retry">
            <text class="material-error-retry-icon">↻</text>
            <text class="btn-primary-text">{{ retrying ? "正在返回…" : "重新选择资料" }}</text>
          </view>
          <view class="material-error-button material-error-secondary" :class="{ 'btn-disabled': discarding }" @click="switchToQuestionnaire">
            <image class="material-error-document-icon" src="/static/v31-document/document.svg" mode="aspectFit" />
            <text class="btn-secondary-text">{{ discarding ? "正在切换…" : "我没有合适的资料" }}</text>
          </view>
          <view class="material-error-note">
            <view class="material-error-note-line" />
            <text>问卷共 10 题，大约需要 3 分钟。</text>
            <view class="material-error-note-line" />
          </view>
        </view>
      </view>

      <text class="material-error-privacy">资料仅用于本次评估 · 请勿上传他人资料</text>
    </view>
  </view>
</template>

<style scoped>
.container {
  min-height: 100vh;
  padding: 72rpx 48rpx 60rpx;
  box-sizing: border-box;
}

/* ===== 页头 ===== */
.header {
  margin-bottom: 44rpx;
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
  line-height: 1.6;
}

/* ===== 异常卡 ===== */
.fail-card {
  padding: 72rpx 48rpx 56rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.fail-seal {
  width: 104rpx;
  height: 104rpx;
  background: rgba(192, 57, 43, 0.1);
  border: 2rpx solid rgba(192, 57, 43, 0.35);
  border-radius: var(--radius-seal);
  transform: rotate(3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
}
.fail-seal-text {
  color: var(--ink-seal);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 52rpx;
  font-weight: 700;
}
.fail-title {
  font-size: 34rpx;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.fail-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
.fail-actions {
  width: 100%;
}
.btn-primary {
  margin-bottom: 24rpx;
}
.fail-note {
  display: block;
  text-align: center;
  margin-top: 28rpx;
  font-size: 24rpx;
  color: var(--text-tertiary);
}

/* ===== 页脚 ===== */
.privacy-note {
  margin-top: 64rpx;
  text-align: center;
}
.privacy-note-text {
  font-size: 22rpx;
  color: var(--text-faint);
}

/* ===== Owner V3.1 资料上传失败视觉稿 ===== */
.material-error-page {
  min-height: 100vh;
  min-height: 100svh;
  overflow-x: hidden;
  color: #164f4e;
  background: #edf3ed;
}
.material-error-container {
  display: flex;
  width: 100%;
  max-width: 430px;
  min-height: 100vh;
  min-height: 100svh;
  margin: 0 auto;
  padding:
    max(18px, env(safe-area-inset-top))
    14px
    max(25px, env(safe-area-inset-bottom));
  box-sizing: border-box;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
  background-color: #f8f5ec;
  background-image:
    linear-gradient(rgba(255, 252, 244, .04), rgba(255, 252, 244, .04)),
    url('/static/v31-material/material-error-background.png');
  background-repeat: no-repeat;
  background-position: center -8px;
  background-size: auto calc(100% + 16px);
}
.material-error-brand {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  min-height: 54px;
  align-items: center;
  gap: 9px;
}
.material-error-logo {
  width: 53px;
  height: 53px;
  flex: 0 0 53px;
}
.material-error-brand-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  color: #15514f;
}
.material-error-brand-name {
  font-size: 20px;
  font-weight: 750;
  line-height: 1.15;
}
.material-error-brand-tagline {
  margin-top: 2px;
  font-size: 11px;
  letter-spacing: 1.8px;
  white-space: nowrap;
}
.material-error-slogan {
  position: relative;
  display: flex;
  margin-left: auto;
  padding-right: 21px;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: flex-end;
  color: #155553;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 2px;
  line-height: 1.35;
  transform: rotate(-5deg);
}
.material-error-seal {
  position: absolute;
  right: 0;
  bottom: -5px;
  display: flex;
  width: 17px;
  height: 35px;
  box-sizing: border-box;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: linear-gradient(160deg, #ba2921, #92251f);
  box-shadow: 0 2px 4px rgba(107, 24, 18, .18);
  line-height: 1.05;
}
.material-error-seal text {
  color: #fff8eb;
  font-size: 9px;
}
.material-error-heading {
  display: flex;
  width: 100%;
  margin-top: clamp(66px, 9.2vh, 92px);
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.material-error-tag {
  display: block;
  padding: 7px 16px;
  border: 1px solid rgba(43, 91, 82, .05);
  border-radius: 11px;
  color: #39706b;
  background: rgba(201, 216, 207, .48);
  font-size: clamp(13px, 3.7vw, 16px);
  letter-spacing: .04em;
  line-height: 1;
}
.material-error-title {
  display: block;
  max-width: 100%;
  margin-top: 18px;
  color: #114f4e;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: clamp(27px, 7.4vw, 34px);
  font-weight: 700;
  letter-spacing: .035em;
  line-height: 1.28;
  text-shadow: 0 1px 0 rgba(255,255,255,.7);
}
.material-error-subtitle {
  display: block;
  max-width: 360px;
  margin-top: 17px;
  color: #525957;
  font-size: clamp(14px, 3.9vw, 17px);
  line-height: 1.65;
}
.material-error-card {
  display: flex;
  width: 100%;
  margin-top: 18px;
  padding: 22px 24px 24px;
  box-sizing: border-box;
  flex-direction: column;
  align-items: center;
  border: 1px solid rgba(80, 101, 93, .09);
  border-radius: 24px;
  background: rgba(255, 253, 247, .88);
  box-shadow:
    0 13px 34px rgba(39, 68, 59, .12),
    inset 0 1px 0 rgba(255,255,255,.8);
  backdrop-filter: blur(2px);
}
.material-error-illustration {
  width: min(254px, 74vw);
  height: clamp(145px, 21vh, 190px);
  flex-shrink: 0;
}
.material-error-card-title {
  margin-top: 3px;
  color: #164f4e;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: clamp(24px, 6.6vw, 30px);
  font-weight: 700;
  letter-spacing: .05em;
  line-height: 1.25;
}
.material-error-card-desc {
  display: block;
  max-width: 330px;
  margin-top: 13px;
  color: #4e5b59;
  font-size: clamp(14px, 3.8vw, 16px);
  line-height: 1.75;
  text-align: center;
}
.material-error-actions {
  display: flex;
  width: 100%;
  margin-top: 21px;
  flex-direction: column;
  align-items: center;
}
.material-error-button {
  position: relative;
  display: flex;
  width: min(292px, 100%);
  min-height: 57px;
  padding: 0 40px;
  box-sizing: border-box;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
}
.material-error-primary {
  border: 1px solid rgba(18, 96, 85, .45);
  color: #fff;
  background:
    linear-gradient(104deg, rgba(25, 103, 90, .98), rgba(48, 130, 112, .96)),
    radial-gradient(circle at 15% 20%, rgba(255,255,255,.18), transparent 38%);
  box-shadow:
    0 8px 16px rgba(30, 101, 87, .18),
    inset 0 1px 0 rgba(255,255,255,.2);
}
.material-error-primary::before {
  position: absolute;
  inset: 4px;
  content: "";
  pointer-events: none;
  border: 1px solid rgba(255,255,255,.11);
  border-radius: inherit;
}
.material-error-secondary {
  margin-top: 12px;
  border: 1px solid rgba(34, 93, 84, .36);
  background: rgba(255, 253, 246, .74);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.7);
}
.material-error-retry-icon {
  margin-right: 13px;
  color: #fff;
  font-size: 30px;
  font-weight: 400;
  line-height: 1;
}
.material-error-document-icon {
  width: 25px;
  height: 25px;
  margin-right: 13px;
  filter: saturate(.62) brightness(.72);
}
.material-error-page .btn-primary-text,
.material-error-page .btn-secondary-text {
  font-size: clamp(17px, 4.8vw, 21px);
  font-weight: 650;
  letter-spacing: .05em;
}
.material-error-page .btn-primary-text { color: #fff; }
.material-error-page .btn-secondary-text { color: #175d57; }
.material-error-note {
  display: flex;
  width: 100%;
  margin-top: 20px;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #54635f;
  font-size: clamp(12px, 3.5vw, 14px);
  white-space: nowrap;
}
.material-error-note-line {
  width: clamp(28px, 9vw, 48px);
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(40, 97, 88, .45));
}
.material-error-note-line:last-child {
  background: linear-gradient(90deg, rgba(40, 97, 88, .45), transparent);
}
.material-error-privacy {
  display: block;
  margin-top: 24px;
  padding-bottom: 3px;
  color: #385c58;
  font-size: clamp(11px, 3.2vw, 13px);
  letter-spacing: .025em;
  text-align: center;
}
.btn-disabled { opacity: .52; }

@media (max-width:350px) {
  .material-error-container { padding-left: 10px; padding-right: 10px; }
  .material-error-logo { width: 46px; height: 46px; flex-basis: 46px; }
  .material-error-brand-name { font-size: 18px; }
  .material-error-brand-tagline { font-size: 9px; letter-spacing: 1.2px; }
  .material-error-slogan { padding-right: 17px; font-size: 12px; letter-spacing: 1px; }
  .material-error-heading { margin-top: 50px; }
  .material-error-card { padding-left: 15px; padding-right: 15px; }
  .material-error-button { min-height: 53px; }
  .material-error-note { gap: 7px; }
  .material-error-note-line { width: 24px; }
}

@media (max-height:700px) {
  .material-error-heading { margin-top: 34px; }
  .material-error-title { margin-top: 12px; }
  .material-error-subtitle { margin-top: 10px; }
  .material-error-card { margin-top: 13px; padding-top: 14px; }
  .material-error-illustration { height: 132px; }
  .material-error-actions { margin-top: 14px; }
  .material-error-privacy { margin-top: 18px; }
}
</style>
