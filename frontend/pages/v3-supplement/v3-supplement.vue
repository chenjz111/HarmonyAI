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
 * 视觉：Owner 提供的山水背景与插画，双卡片选择，保留冻结分支语义
 */

import { apiV3 } from "../../common/api-v3.js"

export default {

  data() {
    return {
      navigating: false,
      analyzing: false,
      agentPending: false, // real 模式：评估/分析能力未就绪时的明确等待状态
    }
  },
  methods: {
    backToSummary() {
      if (this.navigating || this.analyzing) return
      uni.redirectTo({ url: "/pages/v3-summary/v3-summary" })
    },
    // 填写问卷：进入 5 页近期状态问卷
    goQuestionnaire() {
      if (this.navigating || this.analyzing) return
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
        const assessment = await apiV3.createAssessment()
        // 用户已确认资料摘要；document_only 不再展示第二个总结页，但下游仍只消费
        // confirmed Assessment，因此在“直接继续”这一明确操作中完成普通确认。
        await apiV3.confirmAssessment({
          expected_revision: assessment.revision,
          decision: "confirm",
          changes: [],
        })
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
  <view class="supplement-page">
    <view class="supplement-content">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回资料摘要" :disabled="navigating || analyzing" @click="backToSummary"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
      </view>
      <view class="intro">
        <text class="page-heading">资料已整理完成</text>
        <text class="intro-copy">我们已根据你上传的资料，整理出你的近期状况。</text>
      </view>
      <image class="complete-art" src="/static/v31-supplement/complete.png" mode="aspectFit" />
      <view class="explanation">
        <text>问卷可以帮助我们更全面地了解你的</text>
        <text>情绪、睡眠、压力等日常状态，</text>
        <text>从而为你生成更个性化的音乐调适方案。</text>
      </view>
      <view v-if="agentPending" class="pending-box" role="status">
        <text class="pending-title">正在等待评估服务接入</text>
        <text class="pending-desc">评估服务正在升级维护中，暂时无法继续。你可以选择填写问卷，或稍后再试。</text>
        <button class="choice-button primary" role="button" @click="agentPending = false">返回选择</button>
      </view>
      <view v-else class="choice-grid">
        <view class="option-card questionnaire-card">
          <image class="option-icon" src="/static/v31-supplement/questionnaire.png" mode="aspectFill" />
          <text class="option-title">填写问卷</text>
          <text class="option-description">结合资料与问卷，<br />获得更全面、精准的分析。</text>
          <button class="choice-button primary" role="button" :disabled="navigating || analyzing" :aria-disabled="navigating || analyzing" @click="goQuestionnaire"><text>去填写问卷</text><text aria-hidden="true"> →</text></button>
        </view>
        <view class="option-card analysis-card">
          <image class="option-icon" src="/static/v31-supplement/analysis.png" mode="aspectFill" />
          <text class="option-title">不填写问卷</text>
          <text class="option-description">仅基于你上传的资料<br />进行分析，快速生成方案。</text>
          <button class="choice-button secondary" role="button" :disabled="navigating || analyzing" :aria-disabled="navigating || analyzing" @click="goAnalysis"><text>{{ analyzing ? "正在分析…" : "直接进入分析" }}</text><text v-if="!analyzing" aria-hidden="true"> →</text></button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.supplement-page { width:100%; max-width:430px; min-height:100vh; margin:0 auto; color:#064c50; background:#f7f8f1 url('/static/v31-supplement/background.png') center top / 100% 100% no-repeat; font-family: system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.supplement-content { box-sizing:border-box; padding:calc(16px + env(safe-area-inset-top)) 22px calc(150px + env(safe-area-inset-bottom)); }
.brand-row { display:flex; align-items:center; gap:9px; }
.back-button { display:flex; align-items:center; justify-content:center; width:36px; height:44px; flex-shrink:0; margin:0 0 0 -10px; padding:0; background:transparent; border:0; }
.back-button::after,.choice-button::after { border:0; }
.back-chevron { width:12px; height:12px; border-left:2px solid #064c50; border-bottom:2px solid #064c50; transform:rotate(45deg); }
.brand-leaf { width:38px; height:38px; flex-shrink:0; }
.brand-copy { display:flex; flex-direction:column; gap:3px; }
.brand-name { font-size:20px; font-weight:700; letter-spacing:-.5px; line-height:1.2; }
.brand-tagline { font-size:11px; letter-spacing:2px; }
.intro { margin-top:43px; text-align:center; }
.page-heading { display:block; font-family:'KaiTi','STKaiti','LXGW WenKai',serif; font-size:30px; font-weight:700; letter-spacing:2px; line-height:1.4; }
.intro-copy { display:block; margin-top:10px; font-size:14px; line-height:1.8; }
.complete-art { display:block; width:100%; height:165px; margin:10px auto 4px; mix-blend-mode:multiply; -webkit-mask-image:radial-gradient(ellipse at center, #000 48%, transparent 73%); mask-image:radial-gradient(ellipse at center, #000 48%, transparent 73%); }
.explanation { padding:12px 7px; border-radius:10px; background:rgba(218,234,224,.4); text-align:center; font-family:'KaiTi','STKaiti',serif; font-size:15px; line-height:1.85; }
.explanation text { display:block; }
.choice-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:7px; margin-top:10px; }
.option-card { display:flex; flex-direction:column; align-items:center; min-width:0; padding:12px 9px 10px; border:1px solid rgba(216,224,215,.45); border-radius:10px; background:rgba(255,255,252,.7); box-shadow:0 3px 8px rgba(33,71,61,.07); text-align:center; }
.questionnaire-card { border-color:#479e8b; background:rgba(239,250,242,.72); }
.option-icon { width:68px; height:68px; border-radius:50%; mix-blend-mode:multiply; }
.option-title { font-family:'KaiTi','STKaiti',serif; font-size:21px; font-weight:700; margin-top:8px; line-height:1.5; }
.option-description { font-family:'KaiTi','STKaiti',serif; font-size:14px; line-height:1.75; margin:6px -3px 12px; flex:1; }
.choice-button { box-sizing:border-box; width:100%; min-height:44px; margin:0; padding:10px 3px; border-radius:28px; font-size:15px; line-height:1.5; font-family:inherit; font-weight:600; white-space:normal; }
.primary { color:#fff; background:linear-gradient(110deg,#2a7a69,#338572); }
.secondary { color:#064c50; background:rgba(221,230,219,.55); }
.choice-button[disabled] { opacity:.6; }
.choice-button:focus-visible,.back-button:focus-visible { outline:2px solid #1a7468; outline-offset:3px; }
.pending-box { margin-top:12px; padding:20px; background:rgba(255,255,252,.85); border-radius:12px; }
.pending-title,.pending-desc { display:block; margin-bottom:14px; line-height:1.7; }
.pending-title { font-size:18px; font-weight:600; }
.pending-desc { font-size:14px; }
@media(max-width:350px) { .supplement-content { padding-left:14px; padding-right:14px; } .page-heading { font-size:27px; } .explanation { font-size:13px; } .option-title { font-size:19px; } .option-description { font-size:13px; } .choice-button { font-size:13px; } }
</style>
