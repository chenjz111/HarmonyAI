<script>
/**
 * V3.1 资料上传页（Issue #100：1~3 张资料上传）
 * 合同依据：frontend-read-model-contract-v3.md §3.2 SourceStatusReadModel
 *          harmonyai-v3-owner-flow-amendment-001.md §3.1（OCR 失败标准文案，现收敛至独立异常页）
 *
 * 变更（V3.0 → V3.1）：
 *  - 单文件 → 1~3 张多文件：缩略图列表、单张删除、"+ 添加"入口（不超过 3 张）
 *  - OCR/网络失败不再内嵌本页，统一跳转独立资料异常页 v3-material-error
 *    （?type=ocr | ?type=network）
 *  - 识别成功 → 资料摘要确认页
 *
 * ===== 后端对齐依赖（复审注明：等待蔡子鑫对齐，未确定前不擅自调用聚合端点） =====
 *  - 单文件仍走现有 V2 通道：POST /api/v2/documents + replace_document（真实接口已交付）
 *  - 多文档聚合（DocumentSet / 1~3 份有序聚合 + owner-aware upload）端点尚未交付
 *    —— 在此之前，本页面对真实多文档上传如实逐张失败并跳转 v3-material-error，不模拟成功；
 *    mock / hybrid 演示模式按"独立 document_id + 上传顺序保留"实现，便于本地预览
 *    1~3 份资料的有序聚合体验。后端对齐完成后由 apiV3.uploadDocument 内部替换为聚合通道。
 *
 * 注意：真实后端未交付多文档聚合与 owner-aware 上传端点，real 模式下逐张上传
 * 仍会如实失败并跳转异常页，不伪造成功；mock/hybrid 可完整演示多文件流程。
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import DocumentHeader from "../../components/v31/document-header.vue"

const MAX_FILES = 3

export default {
  components: { DocumentHeader },
  data() {
    return {
      state: "pick", // pick（选图/列表） | uploading | uploaded
      files: [], // [{ path, name, isImage, document_id }]
      error: "",
    }
  },
  computed: {
    canAdd() {
      return this.files.length < MAX_FILES
    },
  },
  methods: {
    goHome() { uni.switchTab({ url: "/pages/entry/entry" }) },
    chooseFiles() {
      if (this.state === "uploading" || !this.canAdd) return
      const remain = MAX_FILES - this.files.length
      uni.chooseImage({
        count: remain,
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
          // 用户取消选择，静默返回
        },
      })
    },
    defaultName(path) {
      const seg = String(path || "").split(/[\\/]/)
      return seg[seg.length - 1] || "就诊资料图片.jpg"
    },
    removeFile(idx) {
      if (this.state === "uploading") return
      this.files.splice(idx, 1)
    },
    async startUpload() {
      if (this.state !== "pick" || this.files.length === 0) return
      this.state = "uploading"
      this.error = ""
      for (let i = 0; i < this.files.length; i++) {
        const f = this.files[i]
        try {
          const doc = await apiV3.uploadDocument(f.path, f.name)
          if (doc.state === "failed") {
            // OCR 失败：跳独立异常页（?type=ocr）
            uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=ocr" })
            return
          }
          f.document_id = doc.document_id
        } catch (e) {
          // 网络/服务错误（含真实环境归属缺口）：跳独立异常页（?type=network）
          uni.redirectTo({ url: "/pages/v3-material-error/v3-material-error?type=network" })
          return
        }
      }
      // 全部识别成功 → 资料摘要确认页
      this.state = "uploaded"
      setTimeout(() => {
        uni.redirectTo({ url: "/pages/v3-summary/v3-summary" })
      }, 600)
    },
  },
}
</script>

<template>
  <view class="doc-page material-page">
    <view class="doc-container">
      <document-header :step="1" title="上传就诊资料" :quote="'用音乐\n陪伴更好的你'" subtitle="可上传 1~3 张近期病历、检查报告或相关就诊记录。" @back="goHome" />
      <view class="upload-area">
        <button role="button" v-if="files.length === 0 && state === 'pick'" class="upload-card" @click="chooseFiles">
          <view class="upload-icon" aria-hidden="true"></view>
          <text class="upload-title">点击上传文件</text>
          <view class="upload-seal" aria-hidden="true">◇</view>
          <text class="upload-hint">最多 3 张 · 仅用于本次评估</text>
        </button>
        <view v-if="files.length > 0 && state === 'pick'" class="file-grid">
          <view v-for="(f, idx) in files" :key="idx" class="file-tile">
            <image class="file-thumb" :src="f.path" mode="aspectFill" />
            <button role="button" class="file-remove file-remove--top-right" :aria-label="`删除第${idx + 1}张资料`" @click.stop="removeFile(idx)">×</button>
            <text class="file-name">{{ f.name }}</text>
          </view>
          <button role="button" v-if="canAdd" class="file-tile file-add" aria-label="添加资料" @click="chooseFiles"><text class="file-add-plus">+</text><text>继续添加</text></button>
        </view>
        <view v-if="state === 'uploading'" class="status-card"><view class="status-ring"></view><text class="status-label">正在识别资料</text><text class="status-msg">通常需要几秒钟，请稍候。</text></view>
        <view v-if="state === 'uploaded'" class="status-card"><text class="status-check">✓</text><text class="status-label">资料识别完成</text><text class="status-msg">正在为你整理资料摘要…</text></view>
      </view>
      <view v-if="state === 'pick'" class="action-area">
        <!-- 识别并继续：仍由用户手动触发，不在选择图片时发送。 -->
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
.file-remove::after { border: none; }
.file-add { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin: 0; padding: 0; font-size: 12px; color: #54846f; border-style: dashed; background: rgba(255,255,250,.6); }
.file-add::after { border: none; }
.file-add-plus { font-size: 36px; line-height: 1.3; font-weight: 300; }
.status-card { min-height: 300px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px dashed #a4c7ba; border-radius: 18px; background: rgba(255,255,250,.55); }
.status-label { display: block; margin-top: 18px; font-size: 19px; }
.status-msg { margin-top: 10px; font-size: 13px; color: #708478; }
.status-check { font-size: 44px; color: #4c8e73; }
.action-area { width: 84%; margin: 24px auto 0; }
.btn-start { border-radius: 20px; }
.btn-start text { margin-left: 10px; }
.action-hint { display: block; text-align: center; font-size: 12px; margin-top: 9px; color: #657c70; }
.privacy-note { display: block; text-align: center; font-size: 11px; line-height: 1.5; color: #829087; margin-top: 14px; }
@media(max-width:350px) { .upload-area { margin-top: 28px; } .upload-card,.file-grid,.status-card { min-height: 280px; } .file-tile { height: 130px; } .file-thumb { height: 98px; } }
</style>
