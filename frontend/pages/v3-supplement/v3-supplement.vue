<script>
/**
 * V3.1 轻量选择页（冻结 teacher-user-flow §4.4："想再补充一些近况吗？"）
 *
 * 合同依据（V3.1_FREEZE_BASELINE 83fe2f4）：
 *  - docs/product/app-v3.1-teacher-user-flow.md §4.4 / §7 / §1
 *  - Issue #111 §6 document_only 路径
 *
 * 冻结语义（原自由描述页删除，本页不再包含任何文字/语音输入）：
 *  - 填写问卷：进入 5 页近期状态问卷（Q1-Q10 + 疗愈诉求 + 近期状态总结）
 *  - 直接继续：使用最终确认的资料摘要直接进入五音调适解析，
 *    不再重复出现"近期状态总结"确认页（document_only 无二次确认）
 *
 * 本页仅存在于有资料流程（资料摘要确认后）；无资料流程不经过本页。
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import HanSideNav from "../../components/sprint3/han-side-nav.vue"
import { apiV3 } from "../../common/api-v3.js"

export default {
  components: { HanSideNav },
  data() {
    return {
      navigating: false,
      analyzing: false,
      agentPending: false, // real 模式：评估/分析能力未就绪时的明确等待状态
    }
  },
  methods: {
    // 填写问卷：进入 5 页近期状态问卷
    goQuestionnaire() {
      if (this.navigating) return
      this.navigating = true
      uni.redirectTo({ url: "/pages/v3-questionnaire/v3-questionnaire" })
    },
    // 直接继续：document_only —— 内部分析（创建评估）后直接进入五音调适解析，
    // 不再出现"近期状态总结"确认页（冻结 §4.4 / ConfirmedUserState document_only）
    async goAnalysis() {
      if (this.navigating || this.analyzing) return
      this.analyzing = true
      try {
        // document_only：understanding_ref 携带已确认摘要，questionnaire_ref=null
        await apiV3.createAssessment()
        uni.redirectTo({ url: "/pages/v3-basis/v3-basis" })
      } catch (e) {
        if (e && e.agentPending) {
          this.agentPending = true
          return
        }
        uni.showToast({ title: (e && e.message) || "分析失败，请重试", icon: "none" })
      } finally {
        this.analyzing = false
      }
    },
  },
}
</script>

<template>
  <view class="page han-page side-nav-page">
    <han-side-nav current="material" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">声</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">有资料流程 · 第 3 步</text>
            <text class="page-title han-title-brush revealed">想再补充一些近况吗？</text>
          </view>
        </view>
      </view>

      <view class="han-card choice-card ink-fade-up">
        <view class="choice-intro-seal">
          <text class="choice-intro-seal-text">择</text>
        </view>
        <text class="choice-desc">填写问卷可以帮助我们更完整地了解你最近的状态。</text>

        <!-- real 模式：评估能力未就绪，明确等待状态，不伪造分析 -->
        <view v-if="agentPending" class="pending-box">
          <text class="pending-title">正在等待评估服务接入</text>
          <text class="pending-desc">评估服务正在升级维护中，暂时无法继续。你可以选择填写问卷，或稍后再试。</text>
          <view class="han-btn han-btn-ghost pending-back" @click="agentPending = false">
            <text class="pending-back-text">返回</text>
          </view>
        </view>

        <template v-else>
          <view class="actions">
            <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': analyzing }" @click="goAnalysis">
              <text class="btn-primary-text">{{ analyzing ? "正在分析…" : "直接继续" }}</text>
            </view>
            <view class="han-btn han-btn-ghost btn-secondary" :class="{ 'btn-disabled': navigating }" @click="goQuestionnaire">
              <text class="btn-secondary-text">填写问卷</text>
            </view>
          </view>

          <text class="choice-note">直接继续将使用你已确认的资料摘要进行分析。</text>
        </template>
      </view>
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

/* ===== 选择卡 ===== */
.choice-card {
  padding: 88rpx 48rpx 64rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.choice-intro-seal {
  width: 112rpx;
  height: 112rpx;
  border: 2rpx solid var(--ink-primary);
  border-radius: var(--radius-seal);
  transform: rotate(3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 36rpx;
  background: rgba(107, 124, 94, 0.08);
}
.choice-intro-seal-text {
  color: var(--ink-primary);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 56rpx;
  font-weight: 700;
}
.choice-desc {
  font-size: 28rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  text-align: center;
  margin-bottom: 64rpx;
}
.actions {
  width: 100%;
}
.btn-primary {
  margin-bottom: 24rpx;
}
.choice-note {
  margin-top: 36rpx;
  font-size: 24rpx;
  color: var(--text-tertiary);
  text-align: center;
  line-height: 1.6;
}

/* ===== real 等待态 ===== */
.pending-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24rpx 0 8rpx;
}
.pending-title {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  margin-bottom: 16rpx;
}
.pending-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  text-align: center;
  margin-bottom: 40rpx;
}
.pending-back {
  min-width: 220rpx;
}
.pending-back-text {
  font-size: 28rpx;
}
</style>
