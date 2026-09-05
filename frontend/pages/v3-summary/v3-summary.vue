<script>
/**
 * V3 资料摘要确认页（有资料流程第二步）
 * 合同依据：frontend-read-model-contract-v3.md §4 Case Summary Page
 *          harmonyai-v3-owner-flow-amendment-001.md §3.2 / §3.3
 *
 * 四个操作（Sprint 5 组长指令，覆盖 Amendment §3.2 旧措辞）：
 *  1. 主按钮：资料摘要基本无误
 *  2. 次按钮：修改资料摘要（进入同页编辑状态）
 *  3. 次按钮：重新上传资料
 *  4. 弱按钮：暂不使用这份资料，继续评估
 *
 * 编辑状态（Amendment §3.3）：
 *  - 只编辑通俗摘要文本，不展示 OCR 原文/置信度/Provider/revision
 *  - 保存=提交修正并确认，成功直接进最近情况，无二次确认
 *  - 取消不写入、不增加 revision
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

export default {
  components: { HanSideNav },
  data() {
    return {
      loading: true,
      error: "",
      summaryModel: null,
      editing: false,
      editText: "",
      submitting: false,
    }
  },
  onLoad() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ""
      try {
        this.summaryModel = await apiV3.getCaseSummary()
      } catch (e) {
        this.error = e.message || "加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    // 操作1：资料摘要基本无误（decision=confirm，不触发重提取）
    async confirmOk() {
      if (this.submitting) return
      this.submitting = true
      try {
        await apiV3.confirmUnderstanding({
          expected_revision: this.summaryModel.revision,
          decision: "confirm",
          changes: [],
        })
        // V3.1：摘要确认后进入选填补充页（补充近况）
        uni.redirectTo({ url: "/pages/v3-supplement/v3-supplement" })
      } catch (e) {
        uni.showToast({ title: e.message || "确认失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    // 操作2：修改资料摘要（进入编辑状态）
    startEdit() {
      this.editing = true
      this.editText = this.summaryModel.summary
    },
    // 编辑态：保存修改并继续（= 提交修正并确认）
    async saveEdit() {
      if (this.submitting) return
      const text = (this.editText || "").trim()
      if (!text) {
        uni.showToast({ title: "请填写摘要内容", icon: "none" })
        return
      }
      if (text.length > 2000) {
        uni.showToast({ title: "摘要不能超过 2000 字", icon: "none" })
        return
      }
      this.submitting = true
      try {
        await apiV3.confirmUnderstanding({
          expected_revision: this.summaryModel.revision,
          decision: "confirm_with_changes",
          changes: [],
          edited_summary_text: text,
          reprocess_requested: true,
        })
        // 保存成功直接进入补充近况页，不再增加二次确认（Amendment §3.3）
        uni.redirectTo({ url: "/pages/v3-supplement/v3-supplement" })
      } catch (e) {
        // 失败保留编辑输入、停留本页，旧摘要不变
        if (e.code === "FACT_EXTRACTION_UNAVAILABLE") {
          // 后端不支持编辑后重提取：提示可返回按原摘要继续，不丢弃用户输入
          uni.showToast({
            title: e.message || "当前暂不支持修改摘要后重新解析，你可以按原摘要继续。",
            icon: "none",
            duration: 3000,
          })
        } else {
          uni.showToast({ title: e.message || "保存失败，请重试", icon: "none" })
        }
      } finally {
        this.submitting = false
      }
    },
    // 编辑态：取消修改（不写入、不增加 revision）
    cancelEdit() {
      this.editing = false
      this.editText = ""
    },
    // 操作3：重新上传资料
    reupload() {
      uni.redirectTo({ url: "/pages/v3-material/v3-material" })
    },
    // 操作4：暂不使用这份资料，继续评估（必须调用后端 Input Transition discard_document）
    async switchToQuestionnaire() {
      if (this.submitting) return
      this.submitting = true
      try {
        const session = await apiV3.discardDocument()
        apiV3.rememberSession(session)
        // 丢弃资料后走无资料路径：先到选填补充近况页
        uni.redirectTo({ url: "/pages/v3-supplement/v3-supplement" })
      } catch (e) {
        uni.showToast({ title: e.message || "切换失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
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
            <text class="step-tag">有资料流程 · 第 2 步</text>
            <text class="page-title han-title-brush revealed">请确认资料摘要</text>
          </view>
        </view>
      </view>

      <view v-if="loading" class="loading-wrap">
        <view class="loading-ring"></view>
        <text class="loading-text">正在整理资料摘要…</text>
      </view>

      <view v-else-if="error" class="han-card error-card ink-fade-in">
        <view class="error-seal">
          <text class="error-seal-text">静</text>
        </view>
        <text class="error-title">暂时无法加载</text>
        <text class="error-text">{{ error }}</text>
        <view class="han-btn han-btn-primary btn-retry" @click="load">
          <text class="btn-retry-text">重试</text>
        </view>
      </view>

      <!-- 确认态 -->
      <view v-else-if="!editing" class="han-card summary-card ink-fade-up">
        <view class="source-notice-wrap">
          <view class="source-seal"><text class="source-seal-text">要</text></view>
          <text class="source-notice">{{ summaryModel.source_notice }}</text>
        </view>
        <view class="summary-body">
          <text class="summary-text">{{ summaryModel.summary }}</text>
        </view>

        <view class="actions">
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': submitting }" @click="confirmOk">
            <text class="btn-primary-text">资料摘要基本无误</text>
          </view>
          <view class="han-btn han-btn-ghost btn-secondary" @click="startEdit">
            <text class="btn-secondary-text">修改资料摘要</text>
          </view>
          <view class="han-btn han-btn-ghost btn-secondary" @click="reupload">
            <text class="btn-secondary-text">重新上传资料</text>
          </view>
          <view class="btn-link" @click="switchToQuestionnaire">
            <text class="btn-link-text">暂不使用这份资料，继续评估</text>
          </view>
        </view>
      </view>

      <!-- 编辑态（Amendment §3.3：只编辑通俗摘要文本） -->
      <view v-else class="han-card edit-card ink-fade-up">
        <view class="edit-title-row">
          <view class="edit-seal"><text class="edit-seal-text">改</text></view>
          <text class="edit-title">修改资料摘要</text>
        </view>
        <text class="edit-hint">你可以修正、补充或删减摘要内容。保存后我们会按修改后的内容继续。</text>
        <textarea
          class="edit-textarea"
          v-model="editText"
          :maxlength="2000"
          placeholder="例如：资料中提到近期存在入睡困难、白天精神不足等情况。"
        />
        <view class="edit-count"><text class="edit-count-text">{{ (editText || '').length }} / 2000</text></view>

        <view class="actions">
          <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': submitting }" @click="saveEdit">
            <text class="btn-primary-text">保存修改并继续</text>
          </view>
          <view class="han-btn han-btn-ghost btn-secondary" @click="cancelEdit">
            <text class="btn-secondary-text">取消修改</text>
          </view>
        </view>
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

/* ===== 加载 / 错误 ===== */
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
.error-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80rpx 40rpx;
  border-radius: var(--radius-lg);
}
.error-seal {
  width: 108rpx;
  height: 108rpx;
  border: 3rpx solid var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-4deg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
  background: rgba(192, 57, 43, 0.04);
}
.error-seal-text {
  color: var(--ink-seal);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  font-size: 52rpx;
  font-weight: 700;
}
.error-title {
  font-size: 32rpx;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  margin-bottom: 12rpx;
}
.error-text {
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 36rpx;
  text-align: center;
  line-height: 1.6;
}
.btn-retry {
  padding: 20rpx 72rpx;
}
.btn-retry-text {
  color: var(--text-inverse);
  font-size: 28rpx;
}

/* ===== 摘要卡 ===== */
.summary-card {
  border-radius: var(--radius-lg);
  padding: 40rpx;
}
.source-notice-wrap {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 32rpx;
}
.source-seal {
  min-width: 40rpx;
  height: 40rpx;
  background: var(--ink-primary);
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 4rpx;
  box-shadow: 0 4rpx 14rpx rgba(107, 124, 94, 0.2);
}
.source-seal-text {
  color: var(--text-inverse);
  font-size: 22rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.source-notice {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.7;
}
.summary-body {
  background: rgba(244, 238, 219, 0.5);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 32rpx;
  margin-bottom: 48rpx;
}
.summary-text {
  font-size: 30rpx;
  color: var(--ink-700);
  line-height: 1.8;
}

/* ===== 按钮组 ===== */
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
.btn-secondary {
  margin-bottom: 24rpx;
}
.btn-secondary-text {
  color: var(--ink-700);
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
.btn-disabled {
  opacity: 0.6;
}

/* ===== 编辑卡 ===== */
.edit-card {
  border-radius: var(--radius-lg);
  padding: 40rpx;
}
.edit-title-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.edit-seal {
  min-width: 48rpx;
  height: 48rpx;
  background: var(--ink-seal);
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-seal);
}
.edit-seal-text {
  color: var(--text-inverse);
  font-size: 26rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.edit-title {
  font-size: 34rpx;
  font-weight: 600;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.edit-hint {
  display: block;
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 28rpx;
}
.edit-textarea {
  width: 100%;
  min-height: 300rpx;
  background: rgba(244, 238, 219, 0.5);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 28rpx;
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.7;
  box-sizing: border-box;
}
.edit-count {
  display: flex;
  justify-content: flex-end;
  margin: 12rpx 0 32rpx;
}
.edit-count-text {
  font-size: 22rpx;
  color: var(--text-muted);
}
</style>
