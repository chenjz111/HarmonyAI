<script>
/**
 * V3 资料摘要确认页（有资料流程第二步）
 * 合同依据：frontend-read-model-contract-v3.md §4 Case Summary Page
 *          harmonyai-v3-owner-flow-amendment-001.md §3.2 / §3.3
 *
 * 三个操作（冻结 §4.3；原"放弃资料"弱按钮已前移到异常页，摘要页不再提供该出口）：
 *  1. 主按钮：资料摘要基本无误
 *  2. 次按钮：修改资料摘要（进入同页编辑状态）
 *  3. 次按钮：重新上传资料
 *
 * 编辑状态（Amendment §3.3）：
 *  - 只编辑通俗摘要文本，不展示 OCR 原文/置信度/Provider/revision
 *  - 保存=提交修正并确认，成功直接进最近情况，无二次确认
 *  - 取消不写入、不增加 revision
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import DocumentHeader from "../../components/v31/document-header.vue"

export default {
  components: { DocumentHeader },
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
  },
}
</script>

<template>
  <view class="doc-page summary-page">
    <view class="doc-container">
      <document-header :step="2" title="请确认资料摘要" :quote="'每一份资料\n都是走向更好的开始'" @back="reupload" />
      <view v-if="loading" class="loading-wrap"><view class="loading-ring"></view><text class="loading-text">正在整理资料摘要…</text></view>
      <view v-else-if="error" class="error-card"><text class="error-title">暂时无法加载</text><text class="error-text">{{ error }}</text><button role="button" class="primary-button" @click="load">重试</button></view>
      <view v-else class="summary-card">
        <view class="source-notice-wrap">
          <view class="source-icon"><image src="/static/v31-document/document.svg" mode="aspectFit" /></view>
          <text class="source-notice">{{ summaryModel.source_notice }}</text>
        </view>
        <view class="summary-body" :class="{ 'summary-body--editing': editing }">
          <view class="summary-leaf"><image src="/static/v31-document/leaf.svg" mode="aspectFit" /></view>
          <textarea v-if="editing" class="edit-textarea inline-summary-editor" v-model="editText" :focus="editing" :auto-height="true" :maxlength="2000" aria-label="资料摘要" placeholder="请填写准确的近期情况" />
          <text v-else class="summary-text">{{ summaryModel.summary }}</text>
        </view>
        <view v-if="editing" class="edit-notice"><text>请直接修改上方摘要，保存后继续。</text><text>{{ (editText || '').length }} / 2000</text></view>
        <view v-if="!editing" class="actions">
          <button role="button" class="primary-button" :disabled="submitting" :aria-disabled="submitting" @click="confirmOk">资料摘要基本无误</button>
          <button role="button" class="secondary-button" :disabled="submitting" :aria-disabled="submitting" @click="startEdit">修改资料摘要</button>
          <button role="button" class="secondary-button" :disabled="submitting" :aria-disabled="submitting" @click="reupload">重新上传资料</button>
        </view>
        <view v-else class="actions">
          <button role="button" class="primary-button" :disabled="submitting" :aria-disabled="submitting" @click="saveEdit">{{ submitting ? '正在保存…' : '保存修改并继续' }}</button>
          <button role="button" class="secondary-button" :disabled="submitting" :aria-disabled="submitting" @click="cancelEdit">取消修改</button>
        </view>
      </view>
      <view class="doc-footer"><text>MUSIC HEALS A BETTER YOU</text></view>
    </view>
  </view>
</template>

<style scoped lang="scss">
@import "../../common/v31-document.scss";
.summary-card { margin-top: 56px; padding: 24px 18px 18px; border-radius: 15px; background: rgba(255,255,251,.9); box-shadow: 0 5px 22px rgba(43,92,72,.09); }
.source-notice-wrap { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 20px; }
.source-icon { display: flex; align-items: center; justify-content: center; flex: 0 0 44px; height: 47px; border-radius: 12px; background: #e5eddf; }
.source-icon image { width: 30px; height: 33px; }
.source-notice { font-size: 14px; line-height: 1.75; color: #3c4940; }
.summary-body { display: flex; align-items: flex-start; gap: 10px; padding: 13px 11px; border: 1px solid #e3e9db; border-radius: 11px; background: rgba(237,242,229,.6); }
.summary-leaf { display: flex; align-items: center; justify-content: center; flex: 0 0 42px; height: 42px; border-radius: 50%; background: #e1eadc; }
.summary-leaf image { width: 30px; height: 30px; filter: saturate(.55); }
.summary-text { min-width: 0; flex: 1; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; line-height: 1.85; color: #283b2f; }
.summary-body--editing { border-color: #438a71; box-shadow: 0 0 0 2px rgba(67,138,113,.08); }
.edit-textarea { flex: 1; min-width: 0; width: 100%; min-height: 130px; padding: 0; font-size: 15px; line-height: 1.85; color: #283b2f; background: transparent; caret-color: #186c4f; }
.edit-notice { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; margin-top: 9px; font-size: 11px; color: #6a8272; }
.actions { display: flex; flex-direction: column; gap: 10px; margin-top: 20px; }
.summary-page .doc-footer { padding-top: 64px; }
@media(max-width:350px) { .summary-card { padding: 20px 13px 16px; margin-top: 46px; } .source-notice { font-size: 13px; } .summary-text,.edit-textarea { font-size: 14px; } .source-icon { flex-basis: 36px; height: 40px; } .summary-leaf { flex-basis: 32px; height: 32px; } }
</style>
