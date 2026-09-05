<script>
/**
 * V3 最终评估确认页（唯一一次确认）
 * 合同依据：frontend-read-model-contract-v3.md §8 Final Assessment Confirmation
 *          harmonyai-v3-owner-flow-amendment-001.md §2（唯一最终确认）/ §4.3
 *
 * - 评估服务先产出评估，本页确认后最新已确认 revision 才进入后续流程
 * - 确认只有一次；可带修正（changes[]）提交，返回 revision+1
 * - 不展示 evidence_coverage、provider_metadata、内部 enum、置信度等禁止字段
 * - Safety policy/状态不显示（deferred_v3 / not_run 为内部字段）
 * - real 模式下评估依赖后端综合评估能力（尚未交付）：
 *   加载/确认遇 AGENT_PENDING 进入明确等待状态，不伪造评估结果
 *
 * v2 重写（水墨国风）：
 *   - 全页 .han-page 山水背景
 *   - 标题区改为毛笔字 + 朱砂印章
 *   - 内容卡改为宣纸卡片 + 角花
 *   - 主按钮改为朱砂印章按钮，次按钮改为水墨 ghost
 *   - 业务逻辑 load/confirmOk/startCorrect/saveCorrect 完全保留
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      model: null,
      confirming: false,
      agentPending: false,
      simulated: false,
      correcting: false,
      draftSeverity: {},
    }
  },
  computed: {
    severityLabel() {
      return {
        none: "无",
        mild: "轻微",
        moderate: "中等",
        severe: "明显",
      }
    },
  },
  onLoad() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ""
      this.agentPending = false
      try {
        this.model = await apiV3.getAssessment()
        this.simulated = !!apiV3.AGENT_SIMULATED
      } catch (e) {
        if (e.agentPending) {
          this.agentPending = true
        } else {
          this.error = e.message || "评估加载失败，请重试"
        }
      } finally {
        this.loading = false
      }
    },
    async confirmOk() {
      if (this.confirming) return
      this.confirming = true
      try {
        await apiV3.confirmAssessment({
          expected_revision: this.model.revision,
          decision: "confirm",
          changes: [],
        })
        uni.redirectTo({ url: "/pages/v3-basis/v3-basis" })
      } catch (e) {
        uni.showToast({ title: e.message || "确认失败，请重试", icon: "none" })
      } finally {
        this.confirming = false
      }
    },
    startCorrect() {
      this.correcting = true
      const draft = {}
      ;(this.model.editable_items || []).forEach((item, idx) => {
        draft[idx] = item.value.value
      })
      this.draftSeverity = draft
    },
    pickSeverity(idx, value) {
      this.draftSeverity[idx] = value
    },
    cancelCorrect() {
      this.correcting = false
    },
    async saveCorrect() {
      if (this.confirming) return
      const changes = (this.model.editable_items || [])
        .map((item, idx) => ({ item, idx }))
        .filter(({ item, idx }) => this.draftSeverity[idx] !== item.value.value)
        .map(({ item, idx }) => ({
          target_id: item.target_id,
          field: "severity",
          old_value: item.value.value,
          new_value: this.draftSeverity[idx],
        }))
      this.confirming = true
      try {
        await apiV3.confirmAssessment({
          expected_revision: this.model.revision,
          decision: changes.length ? "confirm_with_changes" : "confirm",
          changes,
        })
        uni.redirectTo({ url: "/pages/v3-basis/v3-basis" })
      } catch (e) {
        uni.showToast({ title: e.message || "提交失败，请重试", icon: "none" })
      } finally {
        this.confirming = false
      }
    },
  },
}
</script>

<template>
  <view class="page han-page">
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="step-tag">
          <text class="step-tag-text">最后一步 · 确认</text>
        </view>
        <view class="title-row">
          <text class="page-title">完成近期状态总结</text>
          <text class="title-seal">审</text>
        </view>
        <text class="page-subtitle">确认通过后，将以此为基础生成本次音乐调养方案。</text>
      </view>

      <view v-if="loading" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在准备你的评估结果…</text>
      </view>

      <view v-else-if="error" class="error-wrap ink-fade-in">
        <view class="error-seal">
          <text class="error-seal-text">静</text>
        </view>
        <text class="error-title">暂时无法加载评估</text>
        <text class="error-text">{{ error }}</text>
        <view class="han-btn han-btn-primary btn-retry" @click="load">
          <text class="btn-text">重试</text>
        </view>
        <text class="error-hint">你不必着急 · 稍后再试也可以</text>
      </view>

      <view v-else-if="agentPending" class="pending-card han-card ink-fade-up">
        <view class="pending-icon">
          <text class="pending-icon-text">…</text>
        </view>
        <text class="pending-title">正在等待评估服务接入</text>
        <text class="pending-desc">评估服务正在升级维护中，暂时无法生成结果。服务恢复后，本页将展示你的评估结果。</text>
        <view class="han-btn han-btn-primary btn-retry" @click="load">
          <text class="btn-text">重新加载</text>
        </view>
      </view>

      <view v-else-if="!correcting" class="confirm-card han-card ink-fade-up">
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：以下评估内容为模拟数据</text>
        </view>

        <view class="summary-box">
          <text class="summary-title">{{ model.title }}</text>
          <text class="summary-text">{{ model.summary }}</text>
        </view>

        <view v-for="sec in model.sections" :key="sec.id" class="section">
          <text class="section-title">{{ sec.title }}</text>
          <view class="section-items">
            <view v-for="(item, idx) in sec.items" :key="idx" class="section-item">
              <view class="item-dot"></view>
              <text class="item-text">{{ item }}</text>
            </view>
          </view>
        </view>

        <view class="han-divider"></view>

        <view class="actions">
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': confirming }" @click="confirmOk">
            <text class="btn-text">基本符合，继续</text>
          </view>
          <view class="han-btn han-btn-ghost btn-secondary" @click="startCorrect">
            <text class="btn-text-ghost">有些地方不对，我要修改</text>
          </view>
        </view>
      </view>

      <view v-else class="correct-card han-card ink-fade-up">
        <text class="correct-title">调整状态程度</text>
        <text class="correct-hint">请根据最近 7 天的实际情况，调整以下各项的准确程度。</text>

        <view v-for="(item, idx) in model.editable_items" :key="idx" class="correct-item">
          <text class="correct-label">{{ item.label }}</text>
          <view class="severity-row">
            <view
              v-for="sv in item.allowed_values"
              :key="sv"
              class="severity-btn"
              :class="{ 'severity-active': draftSeverity[idx] === sv }"
              @click="pickSeverity(idx, sv)"
            >
              <text class="severity-btn-text" :class="{ 'severity-active-text': draftSeverity[idx] === sv }">{{ severityLabel[sv] || sv }}</text>
            </view>
          </view>
        </view>

        <view class="han-divider"></view>

        <view class="actions">
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': confirming }" @click="saveCorrect">
            <text class="btn-text">保存并继续</text>
          </view>
          <view class="han-btn han-btn-ghost btn-secondary" @click="cancelCorrect">
            <text class="btn-text-ghost">取消修改</text>
          </view>
        </view>
      </view>

      <view class="disclaimer">
        <text class="disclaimer-text">本结果仅用于音乐调养参考，不构成医学诊断。</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
}

.container {
  min-height: 100vh;
  padding: 48rpx 40rpx 60rpx;
  box-sizing: border-box;
}

.header {
  margin-bottom: 44rpx;
}

.step-tag {
  display: inline-flex;
  margin-bottom: 20rpx;
}

.step-tag-text {
  font-size: 22rpx;
  color: var(--ink-primary);
  background: rgba(107, 124, 94, 0.1);
  border: 1rpx solid rgba(107, 124, 94, 0.2);
  border-radius: var(--radius-seal);
  padding: 8rpx 18rpx;
  letter-spacing: 0.1em;
  font-weight: 500;
}

.title-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 14rpx;
}

.page-title {
  display: block;
  font-size: 48rpx;
  font-weight: 700;
  color: var(--ink-700);
  line-height: 1.2;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.1em;
}

.title-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44rpx;
  height: 44rpx;
  padding: 0 8rpx;
  background: var(--ink-seal);
  color: var(--text-inverse);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 22rpx;
  font-weight: 700;
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  box-shadow: var(--shadow-seal);
  margin-top: 4rpx;
}

.page-subtitle {
  display: block;
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
}

.han-card {
  position: relative;
  background: var(--paper-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  border: 1rpx solid var(--border-soft);
  padding: 40rpx 32rpx;
  backdrop-filter: blur(8rpx);
}

.han-card::before,
.han-card::after {
  content: "";
  position: absolute;
  width: 24rpx;
  height: 24rpx;
  background-repeat: no-repeat;
  background-size: contain;
  opacity: 0.32;
}

.han-card::before {
  top: 16rpx;
  left: 16rpx;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

.han-card::after {
  bottom: 16rpx;
  right: 16rpx;
  transform: rotate(180deg);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23B5B2A9' stroke-width='1.2'%3E%3Cpath d='M2 2 Q8 2 8 8 M2 2 Q2 8 8 8'/%3E%3C/svg%3E");
}

/* ===== 加载态 ===== */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.loading-ring {
  width: 72rpx;
  height: 72rpx;
  border: 6rpx solid var(--border-light);
  border-top-color: var(--ink-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  margin-top: 24rpx;
  font-size: 26rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* ===== 错误态 ===== */
.error-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 100rpx 0;
}

.error-seal {
  width: 120rpx;
  height: 120rpx;
  border-radius: var(--radius-seal);
  background: var(--paper-card-solid);
  border: 2rpx solid var(--ink-seal);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 32rpx;
  box-shadow: var(--shadow-seal);
  transform: rotate(-4deg);
}

.error-seal-text {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 64rpx;
  color: var(--ink-seal);
  font-weight: 700;
}

.error-title {
  font-size: 36rpx;
  font-weight: 700;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  margin-bottom: 12rpx;
  letter-spacing: 0.08em;
}

.error-text {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 480rpx;
  line-height: 1.6;
}

.btn-retry {
  min-width: 220rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.btn-text {
  color: inherit;
  font-size: 30rpx;
}

.error-hint {
  margin-top: 24rpx;
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* ===== 确认卡 ===== */
.confirm-card,
.correct-card {
  margin-bottom: 24rpx;
}

.summary-box {
  background: rgba(107, 124, 94, 0.08);
  border-radius: var(--radius-md);
  padding: 32rpx;
  margin-bottom: 36rpx;
  border: 1rpx solid rgba(107, 124, 94, 0.12);
}

.summary-title {
  display: block;
  font-size: 30rpx;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 14rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.05em;
}

.summary-text {
  font-size: 28rpx;
  color: var(--text-primary);
  line-height: 1.8;
}

.section {
  margin-bottom: 32rpx;
}

.section-title {
  display: block;
  font-size: 26rpx;
  color: var(--text-muted);
  margin-bottom: 18rpx;
  letter-spacing: 0.08em;
  font-weight: 500;
}

.section-item {
  display: flex;
  align-items: center;
  padding: 14rpx 0;
}

.item-dot {
  width: 12rpx;
  height: 12rpx;
  background: var(--ink-primary);
  border-radius: 50%;
  margin-right: 20rpx;
  flex-shrink: 0;
}

.item-text {
  font-size: 28rpx;
  color: var(--text-primary);
  line-height: 1.5;
}

.correct-title {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 14rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.08em;
}

.correct-hint {
  display: block;
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 32rpx;
}

.correct-item {
  margin-bottom: 36rpx;
}

.correct-label {
  display: block;
  font-size: 28rpx;
  color: var(--ink-700);
  font-weight: 600;
  margin-bottom: 18rpx;
}

.severity-row {
  display: flex;
  gap: 16rpx;
}

.severity-btn {
  flex: 1;
  border: 2rpx solid var(--border-soft);
  border-radius: var(--radius-seal);
  padding: 16rpx 0;
  display: flex;
  justify-content: center;
  background: var(--paper-card-solid);
  transition: all 0.2s ease-out;
}

.severity-btn:active {
  transform: scale(0.96);
}

.severity-active {
  background: var(--ink-primary);
  border-color: var(--ink-primary);
}

.severity-btn-text {
  font-size: 26rpx;
  color: var(--text-secondary);
}

.severity-active-text {
  color: var(--text-inverse);
}

.han-divider {
  height: 1rpx;
  background: linear-gradient(90deg, transparent, var(--divider-ink), transparent);
  margin: 32rpx 0;
}

.actions {
  display: flex;
  flex-direction: column;
}

.han-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.15em;
  border: none;
  padding: 24rpx 48rpx;
  transition: all 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.han-btn-primary {
  background: var(--ink-seal);
  color: var(--text-inverse);
  border-radius: var(--radius-seal);
  box-shadow: var(--shadow-seal);
  position: relative;
  overflow: hidden;
}

.han-btn-primary::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%);
  pointer-events: none;
}

.han-btn-primary:active {
  background: var(--ink-seal-dark);
  transform: scale(0.98);
}

.btn-primary {
  margin-bottom: 24rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.han-btn-ghost {
  background: rgba(251, 249, 244, 0.6);
  color: var(--ink-700);
  border: 1rpx solid var(--border-soft);
  border-radius: var(--radius-seal);
}

.han-btn-ghost:active {
  background: rgba(232, 227, 216, 0.8);
}

.btn-secondary {
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

.btn-text-ghost {
  color: inherit;
  font-size: 30rpx;
}

.btn-disabled {
  opacity: 0.5;
  pointer-events: none;
}

.disclaimer {
  margin-top: 44rpx;
  text-align: center;
}

.disclaimer-text {
  font-size: 22rpx;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.demo-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 28rpx;
}

.demo-banner-text {
  font-size: 22rpx;
  color: var(--warning);
  background: rgba(198, 138, 46, 0.1);
  border: 1rpx solid rgba(198, 138, 46, 0.2);
  border-radius: var(--radius-seal);
  padding: 8rpx 20rpx;
  letter-spacing: 0.05em;
}

/* ===== 等待卡 ===== */
.pending-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64rpx 40rpx;
}

.pending-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: rgba(107, 124, 94, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}

.pending-icon-text {
  font-size: 48rpx;
  color: var(--ink-primary);
  font-weight: 600;
}

.pending-title {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 20rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", "Noto Serif SC", serif;
  letter-spacing: 0.08em;
}

.pending-desc {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 48rpx;
  text-align: center;
}
</style>
