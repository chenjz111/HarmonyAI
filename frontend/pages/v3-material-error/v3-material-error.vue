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
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

export default {
  components: { HanSideNav },
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
  <view class="page han-page side-nav-page">
    <han-side-nav current="material" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">声</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">有资料流程 · 异常分流</text>
            <text class="page-title han-title-brush revealed">{{ type === "network" ? "资料暂时没有上传成功" : "这份资料暂时无法用于本次分析" }}</text>
          </view>
        </view>
        <text class="page-subtitle" v-if="type === 'ocr'">
          未识别到与本次状态评估相关的有效信息，请检查是否上传了合适的就诊资料。
        </text>
        <text class="page-subtitle" v-else>
          网络或服务暂时不可用，请稍后重试。
        </text>
      </view>

      <view class="han-card fail-card ink-fade-up">
        <view class="fail-seal">
          <text class="fail-seal-text">{{ type === "network" ? "静" : "失" }}</text>
        </view>
        <text class="fail-title">{{ type === "network" ? "上传没有完成" : "资料暂时无法使用" }}</text>
        <text class="fail-desc" v-if="type === 'ocr'">
          你可以重新选择合适的资料；也可以不使用资料，直接通过问卷完成本次评估。
        </text>
        <text class="fail-desc" v-else>
          请检查网络后重新选择资料；也可以不使用资料，直接通过问卷完成本次评估。
        </text>

        <view class="fail-actions">
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': retrying }" @click="retry">
            <text class="btn-primary-text">{{ retrying ? "正在返回…" : "重新选择资料" }}</text>
          </view>
          <view class="han-btn han-btn-ghost btn-secondary" :class="{ 'btn-disabled': discarding }" @click="switchToQuestionnaire">
            <text class="btn-secondary-text">{{ discarding ? "正在切换…" : "我没有合适的资料" }}</text>
          </view>
          <text class="fail-note">问卷共 10 题，大约需要 3 分钟。</text>
        </view>
      </view>

      <view class="privacy-note">
        <text class="privacy-note-text">资料仅用于本次评估 · 请勿上传他人资料</text>
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
</style>
