<script>
/**
 * Sprint 6 Product Recovery Phase B：资料上传、识别、摘要与确认保持在同一路由。
 * API 与医学事实仍由 apiV3/后端负责；material-recovery-flow 只管理展示阶段和逐字揭示。
 */
import {
  apiV3,
  buildEvidenceChanges,
  evidenceDecisionFor,
  EVIDENCE_DECISION_KEEP,
  EVIDENCE_DECISION_DROP,
} from "../../common/api-v3.js"
import { MATERIAL_PHASES, createMaterialRecoveryFlow } from "../../common/material-recovery-flow.js"
import DocumentHeader from "../../components/v31/document-header.vue"

const MAX_FILES = 3

const initialMaterialState = () => ({
  phase: MATERIAL_PHASES.PICKING,
  thinkingLabel: "",
  summaryText: "",
  revealedText: "",
  error: "",
})

export default {
  components: { DocumentHeader },
  data() {
    return {
      materialFlow: null,
      materialState: initialMaterialState(),
      files: [],
      error: "",
      summaryModel: null,
      editText: "",
      submitting: false,
      evidence: [],
      decisions: {},
      operationToken: 0,
    }
  },
  computed: {
    phase() { return this.materialState.phase },
    isPicking() { return this.phase === MATERIAL_PHASES.PICKING },
    isProcessing() {
      return [MATERIAL_PHASES.UPLOADING, MATERIAL_PHASES.READING, MATERIAL_PHASES.EXTRACTING, MATERIAL_PHASES.SUMMARIZING].includes(this.phase)
    },
    isSummaryVisible() { return !!this.materialState.summaryText },
    isSummaryReady() { return this.phase === MATERIAL_PHASES.SUMMARY_READY },
    editing() { return this.phase === MATERIAL_PHASES.EDITING },
    isFailed() { return this.phase === MATERIAL_PHASES.FAILED },
    canAdd() { return this.isPicking && this.files.length < MAX_FILES },
    headerTitle() {
      if (this.isPicking) return "上传就诊资料"
      if (this.isSummaryVisible || this.isSummaryReady || this.editing) return "请确认资料摘要"
      return "AI 正在阅读资料"
    },
    headerStep() { return this.isPicking ? 1 : 2 },
    statusLabel() {
      return this.phase === MATERIAL_PHASES.UPLOADING ? "正在识别资料" : "AI 正在阅读并生成资料摘要"
    },
    statusMessage() {
      if (this.phase === MATERIAL_PHASES.UPLOADING) return "正在理解你上传的资料内容，请稍候…"
      return this.materialState.thinkingLabel || "正在分析资料内容…"
    },
    resolvedSummaryText() {
      const model = this.summaryModel
      if (!model) return ""
      const presentation = model.presentation || {}
      return presentation.summary || model.state_summary || model.summary || ""
    },
    summaryDisplayText() { return this.materialState.revealedText },
    structuredChanges() {
      return buildEvidenceChanges(this.evidence, this.decisions, "normalized_fact")
    },
  },
  onLoad() {
    this.setupMaterialFlow()
  },
  onUnload() {
    this.operationToken += 1
    if (this.materialFlow) this.materialFlow.dispose()
    this.materialFlow = null
  },
  methods: {
    setupMaterialFlow() {
      if (this.materialFlow) this.materialFlow.dispose()
      this.materialFlow = createMaterialRecoveryFlow({
        onChange: state => { this.materialState = state },
      })
      this.materialState = this.materialFlow.getState()
    },
    goHome() { uni.switchTab({ url: "/pages/entry/entry" }) },
    chooseFiles() {
      if (!this.isPicking || !this.canAdd) return
      const remain = MAX_FILES - this.files.length
      uni.chooseImage({
        count: remain,
        sourceType: ["album"],
        success: (res) => {
          const paths = res.tempFilePaths || []
          const temp = res.tempFiles || []
          paths.forEach((p, i) => {
            const f = temp[i] || {}
            this.files.push({
              path: p,
              name: f.name || this.defaultName(p),
              isImage: true,
              document_id: null,
            })
          })
        },
        fail: () => {
          // 用户取消相册选择时保持当前页面和已选资料。
        },
      })
    },
    defaultName(path) {
      const segments = String(path || "").split(/[\\/]/)
      return segments[segments.length - 1] || "就诊资料图片.jpg"
    },
    removeFile(index) {
      if (!this.isPicking) return
      this.files.splice(index, 1)
    },
    isCurrentRun(runToken) {
      return !!this.materialFlow && this.operationToken === runToken
    },
    async startUpload() {
      if (!this.materialFlow || this.files.length === 0) return
      if (!this.materialFlow.beginUpload()) return
      const runToken = ++this.operationToken
      this.error = ""
      const documentIds = []

      for (let i = 0; i < this.files.length; i += 1) {
        const f = this.files[i]
        try {
          const doc = await apiV3.uploadDocument(f.path, f.name)
          if (!this.isCurrentRun(runToken)) return
          if (doc.state === "failed") {
            this.materialFlow.fail("资料识别失败")
            uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=ocr" })
            return
          }
          f.document_id = doc.document_id
          documentIds.push(doc.document_id)
        } catch (error) {
          if (!this.isCurrentRun(runToken)) return
          this.materialFlow.fail(error && error.message)
          uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=network" })
          return
        }
      }

      try {
        await apiV3.createDocumentSet(documentIds)
        if (!this.isCurrentRun(runToken)) return
      } catch (error) {
        if (!this.isCurrentRun(runToken)) return
        this.materialFlow.fail(error && error.message)
        uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=network" })
        return
      }

      this.materialFlow.documentsReady()
      await this.loadSummary(runToken)
    },
    async loadSummary(runToken) {
      if (!this.isCurrentRun(runToken)) return
      this.error = ""
      try {
        const summaryModel = await apiV3.getCaseSummary()
        if (!this.isCurrentRun(runToken)) return
        this.summaryModel = summaryModel
        this.evidence = this.summaryModel.evidence_items || []
        this.decisions = this.evidence.reduce((result, item) => {
          result[item.item_id] = evidenceDecisionFor(item)
          return result
        }, {})
        const summaryText = this.resolvedSummaryText
        if (!summaryText || !this.materialFlow.summaryReady(summaryText)) {
          throw new Error("资料摘要尚未就绪，请稍后重试。")
        }
      } catch (error) {
        if (!this.isCurrentRun(runToken)) return
        this.error = (error && error.message) || "加载失败，请重试"
        this.materialFlow.fail(this.error)
      }
    },
    async retrySummary() {
      if (!this.materialFlow || !this.materialFlow.retry()) return
      const runToken = ++this.operationToken
      await this.loadSummary(runToken)
    },
    setEvidence(item, decision) {
      if (!item || !item.item_id) return
      this.decisions = { ...this.decisions, [item.item_id]: decision }
    },
    isKept(item) {
      return (this.decisions[item.item_id] || EVIDENCE_DECISION_KEEP) === EVIDENCE_DECISION_KEEP
    },
    isDropped(item) { return this.decisions[item.item_id] === EVIDENCE_DECISION_DROP },
    async confirmOk() {
      if (this.submitting || !this.summaryModel) return
      const changes = this.structuredChanges
      this.submitting = true
      try {
        await apiV3.confirmUnderstanding({
          expected_revision: this.summaryModel.revision,
          decision: changes.length ? "confirm_with_changes" : "confirm",
          changes,
        })
        uni.redirectTo({ url: "/pages/v3-supplement/v3-supplement" })
      } catch (error) {
        uni.showToast({ title: (error && error.message) || "确认失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    startEdit() {
      if (!this.materialFlow || !this.materialFlow.beginEdit()) return
      this.editText = this.resolvedSummaryText
    },
    async saveEdit() {
      if (this.submitting || !this.summaryModel) return
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
          changes: this.structuredChanges,
          edited_summary_text: text,
          reprocess_requested: true,
        })
        uni.redirectTo({ url: "/pages/v3-supplement/v3-supplement" })
      } catch (error) {
        uni.showToast({ title: (error && error.message) || "保存失败，请重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    cancelEdit() {
      if (!this.materialFlow || !this.materialFlow.cancelEdit()) return
      this.editText = ""
    },
    resetMaterialFlow() {
      if (!this.materialFlow) return
      this.operationToken += 1
      this.materialFlow.reset()
      this.files = []
      this.error = ""
      this.summaryModel = null
      this.editText = ""
      this.submitting = false
      this.evidence = []
      this.decisions = {}
    },
    reupload() { this.resetMaterialFlow() },
  },
}
</script>

<template>
  <view class="doc-page material-page">
    <view class="doc-container">
      <document-header :step="headerStep" :title="headerTitle" :quote="isPicking ? '用音乐\n陪伴更好的你' : '每一份资料\n都是走向更好的开始'" :subtitle="isPicking ? '可上传 1~3 张近期病历、检查报告或相关就诊记录。' : ''" @back="isPicking ? goHome() : reupload()" />

      <view v-if="isPicking" class="upload-area">
        <button role="button" v-if="files.length === 0" class="upload-card" @click="chooseFiles">
          <view class="upload-icon" aria-hidden="true"></view>
          <text class="upload-title">点击上传文件</text>
          <view class="upload-seal" aria-hidden="true">◇</view>
          <text class="upload-hint">最多 3 张 · 仅用于本次评估</text>
        </button>
        <view v-else class="file-grid">
          <view v-for="(file, index) in files" :key="index" class="file-tile">
            <image class="file-thumb" :src="file.path" mode="aspectFill" />
            <button role="button" class="file-remove file-remove--top-right" :aria-label="`删除第${index + 1}张资料`" @click.stop="removeFile(index)">×</button>
            <text class="file-name">{{ file.name }}</text>
          </view>
          <button role="button" v-if="canAdd" class="file-tile file-add" aria-label="添加资料" @click="chooseFiles"><text class="file-add-plus">+</text><text>继续添加</text></button>
        </view>
      </view>

      <view v-else-if="isProcessing && !isSummaryVisible" class="status-card processing-card">
        <view class="status-ring"></view>
        <text class="status-label">{{ statusLabel }}</text>
        <text class="status-msg">{{ statusMessage }}</text>
      </view>

      <view v-else-if="isFailed" class="error-card material-error-card">
        <text class="error-title">暂时无法加载</text>
        <text class="error-text">{{ error || materialState.error }}</text>
        <button role="button" class="primary-button" @click="retrySummary">重试摘要</button>
        <button role="button" class="secondary-button" @click="reupload">重新上传资料</button>
      </view>

      <view v-else-if="isSummaryVisible" class="summary-card">
        <view class="source-notice-wrap">
          <view class="source-icon"><image src="/static/v31-document/document.svg" mode="aspectFit" /></view>
          <text class="source-notice">{{ summaryModel && summaryModel.source_notice }}</text>
        </view>
        <view class="summary-body" :class="{ 'summary-body--editing': editing }">
          <view class="summary-leaf"><image src="/static/v31-document/leaf.svg" mode="aspectFit" /></view>
          <textarea v-if="editing" class="edit-textarea inline-summary-editor" v-model="editText" :focus="editing" :auto-height="true" :maxlength="2000" aria-label="资料摘要" placeholder="请填写准确的近期情况" />
          <text v-else class="summary-text">{{ summaryDisplayText }}</text>
        </view>
        <text v-if="isProcessing" class="summary-reveal-hint">生成资料摘要…</text>

        <view v-if="(isSummaryReady || editing) && evidence.length" class="evidence-block">
          <text class="evidence-title">以下条目会作为后续分析的依据</text>
          <view class="evidence-list">
            <view v-for="item in evidence" :key="item.item_id" class="evidence-item" :class="{ 'evidence-item--dropped': isDropped(item) }">
              <text class="evidence-name">{{ item.display_name }}</text>
              <view class="evidence-toggle">
                <text role="button" class="evidence-choice" :class="{ 'evidence-choice--active': isKept(item) }" @click="setEvidence(item, 'confirmed')">保留</text>
                <text role="button" class="evidence-choice" :class="{ 'evidence-choice--active': isDropped(item) }" @click="setEvidence(item, 'rejected')">不采用</text>
              </view>
            </view>
          </view>
          <text class="evidence-hint">只修改上面的文字不会改变条目的采纳状态。</text>
        </view>

        <view v-if="editing" class="edit-notice"><text>请直接修改上方摘要，保存后继续。</text><text>{{ (editText || '').length }} / 2000</text></view>
        <view v-if="isSummaryReady" class="actions">
          <button role="button" class="primary-button" :disabled="submitting" :aria-disabled="submitting" @click="confirmOk">摘要基本准确，继续下一步</button>
          <button role="button" class="secondary-button" :disabled="submitting" :aria-disabled="submitting" @click="startEdit">修改资料摘要</button>
          <button role="button" class="secondary-button" :disabled="submitting" :aria-disabled="submitting" @click="reupload">重新上传资料</button>
        </view>
        <view v-else-if="editing" class="actions">
          <button role="button" class="primary-button" :disabled="submitting" :aria-disabled="submitting" @click="saveEdit">{{ submitting ? '正在保存…' : '保存修改并继续' }}</button>
          <button role="button" class="secondary-button" :disabled="submitting" :aria-disabled="submitting" @click="cancelEdit">取消修改</button>
        </view>
      </view>

      <view v-if="isPicking" class="action-area">
        <button role="button" class="primary-button btn-start" :disabled="files.length === 0" :aria-disabled="files.length === 0" @click="startUpload">开始识别 <text aria-hidden="true">→</text></button>
        <text v-if="files.length > 0" class="action-hint">已选择 {{ files.length }} 张<text v-if="canAdd"> · 还可再添加 {{ 3 - files.length }} 张</text></text>
      </view>

      <text class="privacy-note">资料仅用于本次评估 · 请勿上传他人资料</text>
      <view class="doc-footer"><text>MUSIC HEALS A BETTER YOU</text></view>
    </view>
  </view>
</template>

<style scoped lang="scss">
@import "../../common/v31-document.scss";
.upload-area { margin-top: 40px; }
.upload-card { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; min-height: 300px; margin: 0; padding: 38px 16px; border: 1px dashed #a4c7ba; border-radius: 18px; background: rgba(255,255,250,.22); line-height: 1.5; }
.upload-card::after { border: none; }
.upload-icon { width: 112px; height: 112px; border-radius: 50%; background: #e4ecdf url('/static/v31-document/camera.png') center center / 120% auto no-repeat; box-shadow: 0 0 0 5px rgba(255,255,249,.65),0 0 0 7px rgba(149,179,156,.21); }
.upload-title { margin-top: 18px; font: 700 21px/1.5 "KaiTi","STKaiti",serif; letter-spacing: .06em; color: #174b3e; }
.upload-seal { margin: 6px 0 12px; font-size: 17px; line-height: 1; color: #c95339; }
.upload-hint { font-size: 14px; color: #7d8880; letter-spacing: .04em; }
.file-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); align-content: start; gap: 10px; min-height: 300px; padding: 14px 10px; border: 1px dashed #a4c7ba; border-radius: 18px; box-sizing: border-box; background: rgba(255,255,250,.4); }
.file-tile { min-width: 0; height: 146px; position: relative; border-radius: 12px; background: #f9fbf5; overflow: hidden; border: 1px solid #d9e5db; box-sizing: border-box; }
.file-thumb { display: block; width: 100%; height: 114px; }
.file-name { display: block; padding: 7px 6px; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #536e60; }
.file-remove { position: absolute; top: 0; right: 0; width: 44px; height: 44px; padding: 0; margin: 0; border-radius: 0 0 0 16px; background: rgba(22,60,49,.72); color: white; font: 26px/44px Arial,sans-serif; }
.file-remove::after,.file-add::after { border: none; }
.file-add { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin: 0; padding: 0; font-size: 12px; color: #54846f; border-style: dashed; background: rgba(255,255,250,.6); }
.file-add-plus { font-size: 36px; line-height: 1.3; font-weight: 300; }
.status-card { margin-top: 40px; min-height: 300px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px dashed #a4c7ba; border-radius: 18px; background: rgba(255,255,250,.55); }
.status-label { display: block; margin-top: 18px; font-size: 19px; color: #284d3f; }
.status-msg { margin-top: 10px; font-size: 13px; color: #708478; }
.action-area { width: 84%; margin: 24px auto 0; }
.btn-start { border-radius: 20px; }
.btn-start text { margin-left: 10px; }
.action-hint { display: block; text-align: center; font-size: 12px; margin-top: 9px; color: #657c70; }
.privacy-note { display: block; text-align: center; font-size: 11px; line-height: 1.5; color: #829087; margin-top: 14px; }
.summary-card { margin-top: 40px; padding: 24px 18px 18px; border-radius: 15px; background: rgba(255,255,251,.9); box-shadow: 0 5px 22px rgba(43,92,72,.09); }
.source-notice-wrap { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 20px; }
.source-icon { display: flex; align-items: center; justify-content: center; flex: 0 0 44px; height: 47px; border-radius: 12px; background: #e5eddf; }
.source-icon image { width: 30px; height: 33px; }
.source-notice { font-size: 14px; line-height: 1.75; color: #3c4940; }
.summary-body { display: flex; align-items: flex-start; gap: 10px; min-height: 130px; padding: 13px 11px; border: 1px solid #e3e9db; border-radius: 11px; background: rgba(237,242,229,.6); }
.summary-leaf { display: flex; align-items: center; justify-content: center; flex: 0 0 42px; height: 42px; border-radius: 50%; background: #e1eadc; }
.summary-leaf image { width: 30px; height: 30px; filter: saturate(.55); }
.summary-text { min-width: 0; flex: 1; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; line-height: 1.85; color: #283b2f; }
.summary-reveal-hint { display: block; margin-top: 9px; font-size: 12px; color: #6a8272; }
.summary-body--editing { border-color: #438a71; box-shadow: 0 0 0 2px rgba(67,138,113,.08); }
.edit-textarea { flex: 1; min-width: 0; width: 100%; min-height: 130px; padding: 0; font-size: 15px; line-height: 1.85; color: #283b2f; background: transparent; caret-color: #186c4f; }
.edit-notice { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; margin-top: 9px; font-size: 11px; color: #6a8272; }
.evidence-block { margin-top: 18px; padding: 13px 11px; border: 1px solid #e3e9db; border-radius: 11px; background: rgba(247,249,243,.75); }
.evidence-title { display: block; font-size: 13px; color: #3c4940; margin-bottom: 9px; }
.evidence-list { display: flex; flex-direction: column; gap: 8px; }
.evidence-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.evidence-name { flex: 1; min-width: 0; font-size: 14px; color: #283b2f; }
.evidence-item--dropped .evidence-name { color: #9aa79c; text-decoration: line-through; }
.evidence-toggle { display: flex; flex: 0 0 auto; gap: 6px; }
.evidence-choice { min-width: 0; padding: 3px 9px; border: 1px solid #d5ded0; border-radius: 9px; font-size: 12px; color: #6a8272; }
.evidence-choice--active { border-color: #438a71; background: #e5eddf; color: #1d5a42; }
.evidence-hint { display: block; margin-top: 9px; font-size: 11px; color: #6a8272; }
.actions { display: flex; flex-direction: column; gap: 10px; margin-top: 20px; }
.material-error-card { margin-top: 40px; }
.material-error-card .secondary-button { margin-top: 10px; }
.material-page .doc-footer { padding-top: 48px; }
@media(max-width:350px) {
  .upload-area,.status-card,.summary-card,.material-error-card { margin-top: 28px; }
  .upload-card,.file-grid,.status-card { min-height: 280px; }
  .file-tile { height: 130px; }
  .file-thumb { height: 98px; }
  .summary-card { padding: 20px 13px 16px; }
  .source-notice { font-size: 13px; }
  .summary-text,.edit-textarea { font-size: 14px; }
  .source-icon { flex-basis: 36px; height: 40px; }
  .summary-leaf { flex-basis: 32px; height: 32px; }
}
</style>
