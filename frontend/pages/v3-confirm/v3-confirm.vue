<script>
/**
 * V3 最终评估确认页（唯一一次确认）
 * 合同依据：frontend-read-model-contract-v3.md §8 Final Assessment Confirmation
 *          harmonyai-v3-owner-flow-amendment-001.md §2（唯一最终确认）/ §4.3
 *
 * - 评估服务先产出评估，本页确认后最新已确认 revision 才进入后续流程
 * - 确认只有一次；可带修正提交（本页提供全文修正 edited_summary_text），返回 revision+1
 * - 不展示 evidence_coverage、provider_metadata、内部 enum、置信度等禁止字段
 * - Safety policy/状态不显示（deferred_v3 / not_run 为内部字段）
 * - real 模式读取并确认真实 Assessment；失败显式提示且不伪造评估结果
 *
 * v2 重写（水墨国风）：
 *   - 全页 .han-page 山水背景
 *   - 标题区改为毛笔字 + 朱砂印章
 *   - 内容卡改为宣纸卡片 + 角花
 *   - 主按钮改为朱砂印章按钮，次按钮改为水墨 ghost
 *
 * Sprint 6 Phase 2（Option B，Owner D1–D7）：
 *   - 结构化证据以稳定身份 fact_evidence_id 为准，逐条“保留 / 不采用”两态控制
 *   - 叙述文本只是展示：文本变化本身绝不改变任何条目的采纳状态
 *   - changes[] 只携带稳定 id；前端不做子串匹配、否定解析或任何语义推断
 */
import {
  apiV3,
  buildEvidenceChanges,
  evidenceDecisionFor,
  EVIDENCE_DECISION_KEEP,
  EVIDENCE_DECISION_DROP,
} from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      model: null,
      confirming: false,
      agentPending: false,
      simulated: false,
      editingMode: null, // null | "text"
      draftSummaryText: "",
      summaryEditorFocused: false,
      decisions: {},
    }
  },
  computed: {
    // 真实“近期状态总结”正文：一律取后端 read model 已返回的文本
    // （presentation.summary → state_summary/summary）。前端不生成、不改写任何医学结论，
    // 也不再用固定文案冒充个性化总结。
    summaryText() {
      const model = this.model
      if (!model) return ""
      const presentation = model.presentation || {}
      return presentation.summary || model.state_summary || model.summary || ""
    },
    // 本次评估真实形成的条目：后端 fact_evidence 的 canonical 中文 display_name
    // （mock/hybrid 下为 mock sections 的条目）。此处只做去重与截断展示，
    // 不在前端推导证型、脏腑或调式。
    // Phase 2：条目同时携带稳定身份 fact_evidence_id —— 那才是提交时的唯一依据。
    evidenceList() {
      const model = this.model
      if (!model || !Array.isArray(model.evidence_items)) return []
      return model.evidence_items
    },
    summaryItems() {
      if (this.evidenceList.length) {
        return this.evidenceList.map((item) => ({
          id: item.item_id,
          label: item.display_name,
          structured: true,
        }))
      }
      // 旧 read model 没有稳定身份：只读展示，永不提交结构化决定。
      const model = this.model
      if (!model) return []
      const fromFacts = Array.isArray(model.fact_evidence)
        ? model.fact_evidence.map((item) => (item && item.display_name) || "")
        : []
      const fromSections = Array.isArray(model.sections)
        ? model.sections.flatMap((section) =>
            section && Array.isArray(section.items) ? section.items : [],
          )
        : []
      const items = [...fromFacts, ...fromSections]
        .map((item) => String(item == null ? "" : item).trim())
        .filter(Boolean)
      return [...new Set(items)].slice(0, 8).map((label) => ({
        id: null,
        label,
        structured: false,
      }))
    },
    // 只提交与后端当前状态不同的结构化决定。
    structuredChanges() {
      return buildEvidenceChanges(this.evidenceList, this.decisions, "fact_evidence")
    },
  },
  onLoad() {
    this.load()
  },
  methods: {
    back() {
      uni.navigateBack()
    },
    async load() {
      this.loading = true
      this.error = ""
      this.agentPending = false
      try {
        this.model = await apiV3.getAssessment()
        this.simulated = !!apiV3.AGENT_SIMULATED
        this.decisions = this.evidenceList.reduce((acc, item) => {
          acc[item.item_id] = evidenceDecisionFor(item)
          return acc
        }, {})
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
    // 两态控制：只改这一条稳定 id 的采纳状态。
    setEvidence(itemId, decision) {
      if (!itemId) return
      this.decisions = { ...this.decisions, [itemId]: decision }
    },
    isKept(itemId) {
      return (this.decisions[itemId] || EVIDENCE_DECISION_KEEP) === EVIDENCE_DECISION_KEEP
    },
    isDropped(itemId) {
      return !!itemId && this.decisions[itemId] === EVIDENCE_DECISION_DROP
    },
    async confirmOk() {
      if (this.confirming) return
      const changes = this.structuredChanges
      this.confirming = true
      try {
        await apiV3.confirmAssessment({
          expected_revision: this.model.revision,
          decision: changes.length ? "confirm_with_changes" : "confirm",
          changes,
        })
        uni.redirectTo({ url: "/pages/v3-basis/v3-basis" })
      } catch (e) {
        uni.showToast({ title: e.message || "确认失败，请重试", icon: "none" })
      } finally {
        this.confirming = false
      }
    },
    startCorrect() {
      this.draftSummaryText = this.summaryText || ""
      this.summaryEditorFocused = false
      this.editingMode = "text"
      this.$nextTick(() => {
        this.summaryEditorFocused = true
      })
    },
    cancelCorrect() {
      this.editingMode = null
      this.draftSummaryText = ""
      this.summaryEditorFocused = false
    },
    async saveCorrect() {
      if (this.confirming) return
      // 最小前端保护：contract 要求 edited_summary_text 至少 1 个字符（min_length >= 1），
      // 空白内容不发请求，避免用户只看到泛化的"提交失败，请重试"。
      const editedSummaryText = (this.draftSummaryText || "").trim()
      if (!editedSummaryText) {
        uni.showToast({ title: "状态总结内容不能为空", icon: "none" })
        return
      }

      this.confirming = true
      try {
        // 最终状态总结属于 Assessment；不得回写资料 Understanding。
        // Phase 2：叙述文本与结构化决定同请求提交，但互不推断。
        await apiV3.confirmAssessment({
          expected_revision: this.model.revision,
          decision: "confirm_with_changes",
          changes: this.structuredChanges,
          edited_summary_text: editedSummaryText,
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
  <view class="confirm-page v31-scroll-page">
    <view class="confirm-container">
      <view class="brand-row">
        <button class="back-button" role="button" aria-label="返回" @click="back"><view class="back-chevron" /></button>
        <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
        <view class="brand-copy"><text class="brand-name">HarmonyAI</text><text class="brand-tagline">用音乐，陪伴更好的你</text></view>
      </view>
      <view class="header ink-fade-in">
        <view class="step-tag">
          <text class="step-tag-text">最后一步 · 确认</text>
        </view>
        <view class="title-row">
          <text class="page-title">确认近期状态总结</text>
          <text class="title-seal">审</text>
        </view>
        <text class="page-subtitle">请确认下面的内容是否基本符合你最近的状态。确认后，我们会以此作为本次五音调适分析的基础。</text>
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

      <view v-else class="confirm-card han-card ink-fade-up">
        <view v-if="simulated" class="demo-banner">
          <text class="demo-banner-text">演示模式：以下评估内容为模拟数据</text>
        </view>

        <view class="summary-heading">
          <image class="summary-icon-image" src="/static/v31-goal/intent-2.png" mode="aspectFit" />
          <text class="summary-heading-title">近期状态总结</text>
        </view>
        <view class="summary-box">
          <text class="summary-title">{{ model.title }}</text>
          <text v-if="editingMode === null" class="summary-text">{{ summaryText }}</text>
          <textarea
            v-else
            class="edit-textarea inline-summary-editor"
            v-model="draftSummaryText"
            :maxlength="2000"
            :focus="summaryEditorFocused"
            :cursor="(draftSummaryText || '').length"
          />
          <!-- 本次问卷真实形成的条目（后端 canonical 中文名称），不是固定文案。
               Phase 2：稳定身份 fact_evidence_id 是唯一权威；文本编辑期间条目保持可见。 -->
          <view v-if="summaryItems.length" class="summary-facts">
            <text class="summary-facts-label">本次问卷中你确认的近期状态</text>
            <view class="summary-facts-list">
              <view
                v-for="(item, index) in summaryItems"
                :key="item.id || item.label"
                class="summary-fact evidence-item"
                :class="{ 'evidence-item--dropped': isDropped(item.id) }"
              >
                <text class="evidence-name">{{ item.label }}</text>
                <view v-if="item.id" class="evidence-toggle">
                  <text role="button" class="evidence-choice" :class="{ 'evidence-choice--active': isKept(item.id) }" @click="setEvidence(item.id, 'confirmed')">保留</text>
                  <text role="button" class="evidence-choice" :class="{ 'evidence-choice--active': isDropped(item.id) }" @click="setEvidence(item.id, 'rejected')">不采用</text>
                </view>
              </view>
            </view>
            <text class="evidence-hint">只修改上面的文字不会改变条目的采纳状态。</text>
          </view>
        </view>

        <view v-if="editingMode === null" class="actions confirm-actions">
          <view class="han-btn han-btn-ghost btn-secondary" @click="startCorrect">
            <text class="btn-text-ghost">有些地方不对，我要修改</text>
          </view>
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': confirming }" @click="confirmOk">
            <text class="btn-text">基本符合，继续</text>
          </view>
        </view>
        <view v-else class="actions confirm-actions">
          <view class="han-btn han-btn-ghost btn-secondary" @click="cancelCorrect">
            <text class="btn-text-ghost">取消修改</text>
          </view>
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': confirming }" @click="saveCorrect">
            <text class="btn-text">保存修改并继续</text>
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

.edit-textarea {
  min-width: 0;
  width: 100%;
  min-height: 280rpx;
  padding: 0;
  box-sizing: border-box;
  background: rgba(251, 249, 244, 0.6);
  border: 1rpx solid var(--border-soft);
  border-radius: var(--radius-md);
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.8;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", sans-serif;
  margin-bottom: 12rpx;
}

.edit-count {
  text-align: right;
  margin-bottom: 32rpx;
}

.edit-count-text {
  font-size: 22rpx;
  color: var(--text-muted);
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

<style scoped>
/* Owner 2026-09-13：近期状态总结手机视觉 */
.confirm-page {
  width:100%;
  max-width:430px;
  min-height:100vh;
  margin:0 auto;
  color:#064c50;
  background:#f8f8f1 url('/static/v31-questionnaire/questionnaire-background-q34.png') center top / 100% 100% no-repeat;
  font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
}
.confirm-container { min-height:100vh; box-sizing:border-box; padding:calc(12px + env(safe-area-inset-top)) 16px calc(26px + env(safe-area-inset-bottom)); }
.confirm-page .brand-row { display:flex; align-items:center; min-height:46px; gap:8px; }
.confirm-page .back-button { display:flex; align-items:center; justify-content:center; width:28px; height:40px; margin:0; padding:0; border:0; background:transparent; }
.confirm-page .back-button::after { border:0; }
.confirm-page .back-chevron { width:11px; height:11px; border-left:2px solid #064c50; border-bottom:2px solid #064c50; transform:rotate(45deg); }
.confirm-page .brand-leaf { width:42px; height:42px; }
.confirm-page .brand-copy { display:flex; flex-direction:column; gap:1px; }
.confirm-page .brand-name { font-size:18px; font-weight:750; line-height:1.15; }
.confirm-page .brand-tagline { font-size:10px; letter-spacing:2px; }
.confirm-page .header { margin:28px 14px 26px; }
.confirm-page .step-tag { display:inline-flex; margin-bottom:14px; padding:5px 10px; border:0; border-radius:7px; background:rgba(205,224,215,.68); }
.confirm-page .step-tag-text { color:#28675f; font-size:12px; }
.confirm-page .title-row { display:flex; align-items:center; gap:10px; }
.confirm-page .page-title { color:#064c50; font-family:'KaiTi','STKaiti',serif; font-size:31px; font-weight:800; letter-spacing:2px; line-height:1.25; }
.confirm-page .title-seal { display:none; }
.confirm-page .page-subtitle { display:block; margin-top:12px; color:#18585c; font-size:14px; line-height:1.7; }
.confirm-page .confirm-card { box-sizing:border-box; padding:18px 16px 16px; border:1px solid rgba(57,104,93,.10); border-radius:14px; background:rgba(255,255,251,.86); box-shadow:0 4px 14px rgba(31,72,62,.10); }
.confirm-page .demo-banner { margin-bottom:10px; }
.confirm-page .summary-heading { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
.confirm-page .summary-icon-image { width:52px; height:52px; flex:0 0 52px; border-radius:50%; mix-blend-mode:multiply; }
.confirm-page .summary-heading-title { color:#064c50; font-family:'KaiTi','STKaiti',serif; font-size:23px; font-weight:800; }
.confirm-page .summary-box { box-sizing:border-box; margin:0; padding:15px 14px; border:1px solid rgba(63,112,96,.10); border-radius:10px; background:rgba(239,246,237,.54); }
.confirm-page .summary-title { display:none; }
.confirm-page .summary-text { color:#164e57; font-size:15px; line-height:1.9; }
.confirm-page .summary-facts { margin-top:16px; }
.confirm-page .summary-facts-label { display:block; margin-bottom:9px; color:#55746f; font-size:12px; letter-spacing:.5px; }
.confirm-page .summary-facts-list { display:flex; flex-direction:column; gap:6px; }
.confirm-page .summary-fact { max-width:100%; padding:4px 10px; border-radius:12px; background:rgba(36,105,94,.08); color:#15565a; font-size:12px; line-height:1.5; overflow-wrap:anywhere; }
.confirm-page .evidence-item { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:5px 10px; }
.confirm-page .evidence-item--dropped { background:rgba(120,120,110,.10); }
.confirm-page .evidence-item--dropped .evidence-name { color:#8d968f; text-decoration:line-through; }
.confirm-page .evidence-name { flex:1; min-width:0; overflow-wrap:anywhere; }
.confirm-page .evidence-toggle { display:flex; flex:0 0 auto; gap:6px; }
.confirm-page .evidence-choice { padding:2px 8px; border:1px solid #d5ded0; border-radius:9px; color:#6a8272; font-size:11px; }
.confirm-page .evidence-choice--active { border-color:#438a71; background:#e5eddf; color:#1d5a42; }
.confirm-page .evidence-hint { display:block; margin-top:8px; color:#6a8272; font-size:11px; }
.confirm-page .inline-summary-editor { width:100%; min-height:150px; box-sizing:border-box; padding:0; border:0; background:transparent; color:#164e57; font-family:inherit; font-size:15px; line-height:1.9; }
.confirm-page .inline-summary-editor :deep(textarea) { padding:0; color:#164e57; font-family:inherit; font-size:15px; line-height:1.9; }
.confirm-page .confirm-actions { display:grid; grid-template-columns:1fr 1fr; gap:9px; margin-top:20px; }
.confirm-page .confirm-actions .han-btn { display:flex; align-items:center; justify-content:center; min-width:0; min-height:48px; box-sizing:border-box; margin:0; padding:8px 9px; border-radius:26px; }
.confirm-page .confirm-actions .btn-secondary { border:1px solid #207064; color:#15565a; background:rgba(255,255,252,.70); }
.confirm-page .confirm-actions .btn-primary { border:0; color:#fff; background:linear-gradient(105deg,#24695e,#28776a); box-shadow:0 5px 12px rgba(27,105,89,.14); }
.confirm-page .confirm-actions .btn-text,
.confirm-page .confirm-actions .btn-text-ghost { color:inherit; font-family:inherit; font-size:13px; font-weight:650; text-align:center; white-space:normal; }
.confirm-page .disclaimer { margin-top:18px; text-align:center; }
.confirm-page .disclaimer-text { color:#607a76; font-size:10px; letter-spacing:.5px; }
@media (max-width:350px) {
  .confirm-container { padding-left:10px; padding-right:10px; }
  .confirm-page .header { margin-left:8px; margin-right:8px; }
  .confirm-page .page-title { font-size:27px; }
  .confirm-page .confirm-card { padding-left:10px; padding-right:10px; }
  .confirm-page .confirm-actions .btn-text,
  .confirm-page .confirm-actions .btn-text-ghost { font-size:12px; }
}
</style>
