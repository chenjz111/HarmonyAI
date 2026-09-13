<template>
  <view class="goal-page v31-scroll-page">
    <view class="goal-container">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回" @click="back"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
      </view>

      <view class="goal-hero ink-fade-in">
        <text class="step-tag">可选填写</text>
        <text class="page-title">疗愈诉求</text>
        <text class="page-subtitle">最后，如果想的话，告诉我们：现在最希望音乐帮你做点什么？（不填也没关系）</text>
      </view>

      <view v-if="submitting" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在整理你的选择…</text>
      </view>

      <template v-else>
        <view class="intent-picker ink-fade-up">
          <view class="card-head">
            <view class="card-head-seal"><text class="card-head-seal-text">♥</text></view>
            <view class="card-head-copy">
              <text class="card-title">选择你的诉求</text>
              <text class="card-hint">最多选择 2 项，按选择顺序记录</text>
            </view>
          </view>
          <view class="intent-grid">
            <view
              v-for="it in intents"
              :key="it.code"
              class="intent-card"
              :class="{ 'intent-card--active': isSelected(it.code) }"
              @click="toggleIntent(it.code)"
            >
              <image class="intent-icon-image" :src="intentImage(it.code)" mode="aspectFit" />
              <text class="intent-label">{{ it.label }}</text>
              <view class="intent-check"><text>{{ isSelected(it.code) ? (primary_goal === it.code ? '1' : '2') : '' }}</text></view>
            </view>
          </view>
        </view>

        <view class="goal-actions">
          <view class="goal-button goal-button-secondary" @click="skip"><text>暂时跳过</text></view>
          <view class="goal-button goal-button-primary" @click="next"><text>完成</text></view>
        </view>
        <view class="page-motto"><text>—　五音和鸣 · 乐养身心　—</text></view>
      </template>
    </view>
  </view>
</template>

<script>
/**
 * V3.1 疗愈诉求页（Issue #100：Provisional Flow 选填加回）
 *
 * 意图代码沿用合同权威枚举；Owner 2026-09-11 决定本版界面只展示
 * sleep / relaxation / emotion_regulation / focus / energy / stress_relief 六项。
 * `other` 与自由文字只保留在底层兼容模块，不向用户展示。
 * - 整页选填、可整步跳过；最多 2 项：主诉求（primary_goal）+ 次诉求（secondary_goal）。
 * - 不虚构、不默认补全任何偏好：用户未选择时不留占位、不提交空对象。
 * - 后端暂无对应保存能力 → 选择内容本机暂存（safeSet），页面如实标注，
 *   mock 状态机同步记录。后端交付后由 apiV3.submitHealingIntent 替换为本请求。
 *
 * 合同校验仍由公共模块负责；界面提交字段保持
 * primary_goal / secondary_goal / custom_goal_text，后者固定为空。
 * - 校验逻辑集中在 common/v3-healing-intent.js（decideHealingIntent），
 *   本组件只负责 UI 绑定 + 调用 + toast 提示。
 *
 * 后续：v3-confirm（完成近期状态总结）。
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import {
  INTENT_CODES,
  decideHealingIntent,
  HEALING_INTENT_REASON_MESSAGE,
} from "../../common/v3-healing-intent.js"

export default {
  data() {
    return {
      withDocument: false,
      // Owner 2026-09-11 override: hide `other` and the free-text UI.
      // Keep the backend-compatible payload shape with an empty custom_goal_text.
      intents: INTENT_CODES.filter((item) => item.code !== "other"),
      // 合同权威字段名（primary_goal / secondary_goal / custom_goal_text），
      // 与 Read Model §10 一一对应；后端未交付时本机暂存同样采用这套字段，
      // 接入真实接口时无需再做映射。
      primary_goal: null,
      secondary_goal: null,
      custom_goal_text: "",
      submitting: false,
    }
  },
  onLoad() {
    apiV3.getSession()
      .then((s) => {
        this.withDocument = s.input_mode === "with_document"
      })
      .catch(() => {})
  },
  methods: {
    back() {
      uni.navigateBack()
    },
    isSelected(code) {
      return this.primary_goal === code || this.secondary_goal === code
    },
    intentImage(code) {
      const index = ({ sleep: 1, relaxation: 2, emotion_regulation: 3, focus: 4, energy: 5, stress_relief: 6 })[code]
      return `/static/v31-goal/intent-${index}.png`
    },
    toggleIntent(code) {
      if (this.primary_goal === code) {
        this.primary_goal = this.secondary_goal
        this.secondary_goal = null
        return
      }
      if (this.secondary_goal === code) {
        this.secondary_goal = null
        return
      }
      if (!this.primary_goal) {
        this.primary_goal = code
        return
      }
      if (!this.secondary_goal) {
        this.secondary_goal = code
        return
      }
      uni.showToast({ title: "最多选择 2 项", icon: "none" })
    },
    /**
     * 继续按钮：先走合同校验 → 全空 skip / 不合规 toast / 合规 submit。
     * Owner 界面隐藏项不会由本组件生成，底层校验仅用于保持接口兼容。
     */
    async next() {
      if (this.submitting) return
      const decision = decideHealingIntent({
        primary_goal: this.primary_goal,
        secondary_goal: this.secondary_goal,
        custom_goal_text: this.custom_goal_text,
      })
      // 规则 1：全空 → 整页跳过，与原行为一致
      if (decision.skip) {
        this.skip()
        return
      }
      // 校验失败 → toast 阻断，不提交、不跳转
      if (!decision.ok) {
        const msg = HEALING_INTENT_REASON_MESSAGE[decision.reason] || "请检查后重试"
        uni.showToast({ title: msg, icon: "none" })
        return
      }
      this.submitting = true
      try {
        // 提交 payload 使用合同权威字段名（primary_goal / secondary_goal / custom_goal_text）
        await apiV3.submitHealingIntent(decision.payload)
        uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
      } catch (e) {
        uni.showToast({ title: (e && e.message) || "保存失败，请稍后重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    skip() {
      // 整步跳过：不保存任何偏好、不伪造默认值
      uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
    },
  },
}
</script>

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
  margin-bottom: 16rpx;
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

/* ===== 卡片 ===== */
.card {
  border-radius: var(--radius-lg);
  padding: 32rpx;
  margin-bottom: 32rpx;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 24rpx;
}
.card-head-seal {
  min-width: 44rpx;
  height: 44rpx;
  background: var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
  flex-shrink: 0;
}
.card-head-seal--ink {
  background: var(--ink-700);
  box-shadow: 0 4rpx 14rpx rgba(26, 25, 22, 0.18);
}
.card-head-seal--primary {
  background: var(--ink-primary);
  box-shadow: 0 4rpx 14rpx rgba(107, 124, 94, 0.2);
}
.card-head-seal-text {
  color: var(--text-inverse);
  font-size: 24rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.card-title {
  font-size: 30rpx;
  font-weight: 500;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  flex: 1;
}
.card-hint {
  font-size: 22rpx;
  color: var(--text-muted);
}

/* ===== 诉求印章芯片 ===== */
.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.chip {
  background: rgba(244, 238, 219, 0.45);
  border: 2rpx solid transparent;
  border-radius: var(--radius-seal);
  padding: 18rpx 32rpx;
  transition: all 0.2s ease;
}
.chip-active {
  background: rgba(192, 57, 43, 0.06);
  border-color: var(--ink-seal);
  transform: rotate(-1.5deg);
  box-shadow: 0 4rpx 14rpx rgba(192, 57, 43, 0.14);
}
.chip-dim {
  opacity: 0.45;
}
.chip-text {
  font-size: 28rpx;
  color: var(--text-secondary);
}
.chip-text-active {
  color: var(--ink-seal);
  font-weight: 500;
}
.custom-input {
  width: 100%;
  min-height: 140rpx;
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.7;
}
.custom-count {
  display: flex;
  justify-content: flex-end;
  margin-top: 8rpx;
}
.custom-count-text {
  font-size: 22rpx;
  color: var(--text-muted);
}

/* ===== 暂存提示 ===== */
.save-note {
  background: rgba(244, 238, 219, 0.55);
  border: 1rpx solid var(--border-light);
  border-radius: 12rpx;
  padding: 20rpx 28rpx;
  margin-bottom: 40rpx;
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
}
.save-note-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: var(--ink-primary);
  margin-top: 12rpx;
  flex-shrink: 0;
}
.save-note-text {
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ===== 底部动作 ===== */
.actions {
  display: flex;
  flex-direction: column;
}
.btn-primary {
  margin-bottom: 24rpx;
}
.btn-primary-text {
  color: var(--text-inverse);
  font-size: 30rpx;
}
.btn-link {
  display: flex;
  justify-content: center;
  padding: 12rpx 0;
}
.btn-link-text {
  color: var(--text-muted);
  font-size: 26rpx;
  text-decoration: underline;
}

/* ===== 加载 ===== */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid var(--paper-deep);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: var(--text-muted);
}
</style>

<style scoped>
/* Owner 2026-09-13：疗愈诉求手机视觉 */
.goal-page {
  width: 100%;
  max-width: 430px;
  min-height: 100vh;
  margin: 0 auto;
  color: #064c50;
  background: #f8f8f1 url('/static/v31-questionnaire/questionnaire-background-q34.png') center top / 100% 100% no-repeat;
  font-family: system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.goal-container { min-height:100vh; box-sizing:border-box; padding:calc(12px + env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom)); }
.goal-page .brand-row { display:flex; align-items:center; min-height:46px; gap:8px; }
.goal-page .back-button { display:flex; align-items:center; justify-content:center; width:28px; height:40px; margin:0; padding:0; border:0; background:transparent; }
.goal-page .back-button::after { border:0; }
.goal-page .back-chevron { width:11px; height:11px; border-left:2px solid #064c50; border-bottom:2px solid #064c50; transform:rotate(45deg); }
.goal-page .brand-leaf { width:42px; height:42px; }
.goal-page .brand-copy { display:flex; flex-direction:column; gap:1px; }
.goal-page .brand-name { font-size:18px; font-weight:750; line-height:1.15; }
.goal-page .brand-tagline { font-size:10px; letter-spacing:2px; }
.goal-hero { margin:18px 14px 18px; }
.goal-page .step-tag { display:inline-block; margin-bottom:8px; padding:4px 10px; border:0; border-radius:7px; color:#28675f; background:rgba(205,224,215,.66); font-size:12px; }
.goal-page .page-title { display:block; color:#064c50; font-family:'KaiTi','STKaiti',serif; font-size:34px; font-weight:800; letter-spacing:3px; line-height:1.2; }
.goal-page .page-subtitle { display:block; margin-top:10px; color:#18585c; font-size:14px; line-height:1.75; }
.goal-page .intent-picker { box-sizing:border-box; padding:16px 13px; border:1px solid rgba(57,104,93,.08); border-radius:14px; background:rgba(255,255,251,.82); box-shadow:0 3px 12px rgba(31,72,62,.10); }
.goal-page .card-head { display:flex; align-items:center; gap:10px; margin-bottom:13px; }
.goal-page .card-head-seal { display:flex; align-items:center; justify-content:center; width:42px; min-width:42px; height:42px; border:0; border-radius:50%; transform:none; background:#deede6; box-shadow:none; }
.goal-page .card-head-seal-text { color:#155f56; font-family:inherit; font-size:20px; }
.goal-page .card-head-copy { display:flex; flex-direction:column; min-width:0; }
.goal-page .card-title { color:#0b4f51; font-family:inherit; font-size:17px; font-weight:750; }
.goal-page .card-hint { margin-top:3px; color:#567472; font-size:11px; }
.goal-page .intent-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:0; }
.goal-page .intent-card { position:relative; min-height:132px; box-sizing:border-box; padding:9px 5px 10px; border:1px solid rgba(58,93,87,.13); border-radius:9px; display:flex; flex-direction:column; align-items:center; justify-content:flex-start; background:rgba(255,255,252,.72); transition:.2s ease; }
.goal-page .intent-card--active { border-color:#167461; background:linear-gradient(145deg,#f4fbf7,#e2f2e9); box-shadow:0 4px 10px rgba(24,112,91,.12); }
.goal-page .intent-icon-image { width:61px; max-width:100%; height:61px; flex-shrink:0; border-radius:50%; mix-blend-mode:multiply; }
.goal-page .intent-label { margin-top:6px; color:#0c4b51; font-size:12px; font-weight:700; line-height:1.35; text-align:center; }
.goal-page .intent-check { position:absolute; top:7px; right:7px; width:18px; height:18px; border:1px solid #b7c5c0; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; }
.goal-page .intent-card--active .intent-check { border-color:#176f5e; background:#176f5e; }
.goal-actions { display:grid; grid-template-columns:1fr 1fr; gap:9px; margin:18px 36px 0; }
.goal-button { display:flex; align-items:center; justify-content:center; min-height:48px; border-radius:26px; font-size:15px; font-weight:650; }
.goal-button-secondary { color:#15565a; background:rgba(221,232,228,.82); }
.goal-button-primary { color:#fff; background:linear-gradient(105deg,#24695e,#28776a); box-shadow:0 5px 12px rgba(27,105,89,.15); }
.goal-page .page-motto { margin-top:14px; color:#285e5b; text-align:center; font-family:'KaiTi','STKaiti',serif; font-size:11px; letter-spacing:1px; }
@media (max-width:350px) {
  .goal-container { padding-left:10px; padding-right:10px; }
  .goal-hero { margin-left:8px; margin-right:8px; }
  .goal-page .intent-picker { padding-left:8px; padding-right:8px; }
  .goal-page .intent-grid { gap:5px; }
  .goal-page .intent-card { min-height:122px; padding-left:2px; padding-right:2px; }
  .goal-page .intent-icon-image { width:54px; height:54px; }
  .goal-page .intent-label { font-size:11px; }
  .goal-actions { margin-left:22px; margin-right:22px; }
}
</style>

<style scoped>
.intent-picker { padding:30rpx; border-radius:34rpx; }
.intent-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18rpx; margin-top:24rpx; }
.intent-card { position:relative; min-height:180rpx; box-sizing:border-box; padding:28rpx 22rpx; border:2rpx solid #e0e6df; border-radius:24rpx; display:flex; flex-direction:column; justify-content:center; background:rgba(255,255,255,.72); transition:.2s ease; }
.intent-card--active { border-color:#167461; background:linear-gradient(145deg,#f4fbf7,#e2f2e9); box-shadow:0 12rpx 30rpx rgba(24,112,91,.14); }
.intent-icon { width:66rpx; height:66rpx; border-radius:50%; display:flex; align-items:center; justify-content:center; background:#e4f1ea; color:#0f6558; font-family:"STKaiti",serif; font-size:31rpx; }
.intent-label { margin-top:16rpx; color:#0c4b46; font-size:26rpx; font-weight:700; line-height:1.35; }
.intent-check { position:absolute; top:16rpx; right:16rpx; width:38rpx; height:38rpx; border:2rpx solid #b7c5c0; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:20rpx; }
.intent-card--active .intent-check { background:#176f5e; border-color:#176f5e; }
@media (max-width:350px) { .intent-card{min-height:158rpx;padding:22rpx 18rpx}.intent-label{font-size:23rpx} }
</style>
