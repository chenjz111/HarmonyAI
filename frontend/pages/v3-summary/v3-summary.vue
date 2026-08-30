<script>
/**
 * V3 资料摘要确认页（有资料流程第二步）
 * 合同依据：frontend-read-model-contract-v3.md §4 Case Summary Page
 *          harmonyai-v3-owner-flow-amendment-001.md §3.2 / §3.3
 *
 * 四个操作（Amendment §3.2）：
 *  1. 主按钮：内容基本准确，继续
 *  2. 次按钮：修改资料摘要（进入同页编辑状态）
 *  3. 次按钮：重新上传资料
 *  4. 弱按钮：改用描述与问卷
 *
 * 编辑状态（Amendment §3.3）：
 *  - 只编辑通俗摘要文本，不展示 OCR 原文/置信度/Provider/revision
 *  - 保存=提交修正并确认，成功直接进最近情况，无二次确认
 *  - 取消不写入、不增加 revision
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
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
    // 操作1：内容基本准确，继续
    async confirmOk() {
      if (this.submitting) return
      this.submitting = true
      try {
        await apiV3.confirmUnderstanding({
          expected_revision: this.summaryModel.revision,
          decision: "confirm",
          changes: [],
        })
        uni.redirectTo({ url: "/pages/v3-narrative/v3-narrative" })
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
        // 保存成功直接进入最近情况，不再增加二次确认（Amendment §3.3）
        uni.redirectTo({ url: "/pages/v3-narrative/v3-narrative" })
      } catch (e) {
        // 失败保留编辑输入、停留本页，旧摘要不变
        uni.showToast({ title: e.message || "保存失败，请重试", icon: "none" })
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
    // 操作4：改用描述与问卷（服务端切换无资料模式）
    async switchToQuestionnaire() {
      if (this.submitting) return
      this.submitting = true
      try {
        const session = await apiV3.discardDocument()
        apiV3.rememberSession(session)
        uni.redirectTo({ url: "/pages/v3-narrative/v3-narrative" })
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
  <view class="container">
    <view class="header">
      <text class="step-tag">有资料流程 · 第 2 步</text>
      <text class="page-title">请确认资料摘要</text>
    </view>

    <view v-if="loading" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在整理资料摘要…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <text class="error-text">{{ error }}</text>
      <view class="btn-retry" @click="load"><text class="btn-retry-text">重试</text></view>
    </view>

    <!-- 确认态 -->
    <view v-else-if="!editing" class="summary-card">
      <text class="source-notice">{{ summaryModel.source_notice }}</text>
      <view class="summary-body">
        <text class="summary-text">{{ summaryModel.summary }}</text>
      </view>

      <view class="actions">
        <view class="btn-primary" :class="{ 'btn-disabled': submitting }" @click="confirmOk">
          <text class="btn-primary-text">内容基本准确，继续</text>
        </view>
        <view class="btn-secondary" @click="startEdit">
          <text class="btn-secondary-text">修改资料摘要</text>
        </view>
        <view class="btn-secondary" @click="reupload">
          <text class="btn-secondary-text">重新上传资料</text>
        </view>
        <view class="btn-link" @click="switchToQuestionnaire">
          <text class="btn-link-text">改用描述与问卷</text>
        </view>
      </view>
    </view>

    <!-- 编辑态（Amendment §3.3：只编辑通俗摘要文本） -->
    <view v-else class="edit-card">
      <text class="edit-title">修改资料摘要</text>
      <text class="edit-hint">你可以修正、补充或删减摘要内容。保存后我们会按修改后的内容继续。</text>
      <textarea
        class="edit-textarea"
        v-model="editText"
        :maxlength="2000"
        placeholder="例如：资料中提到近期存在入睡困难、白天精神不足等情况。"
      />
      <view class="edit-count"><text class="edit-count-text">{{ (editText || '').length }} / 2000</text></view>

      <view class="actions">
        <view class="btn-primary" :class="{ 'btn-disabled': submitting }" @click="saveEdit">
          <text class="btn-primary-text">保存修改并继续</text>
        </view>
        <view class="btn-secondary" @click="cancelEdit">
          <text class="btn-secondary-text">取消修改</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style>
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 80rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header { margin-bottom: 48rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4a6b5c;
  background: #e6ebe5;
  border-radius: 8rpx;
  padding: 6rpx 16rpx;
  margin-bottom: 20rpx;
}
.page-title { display: block; font-size: 44rpx; font-weight: 600; color: #2f3d35; }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 120rpx 0; }
.loading-ring {
  width: 72rpx; height: 72rpx;
  border: 6rpx solid #e3ddcf;
  border-top-color: #4a6b5c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { margin-top: 24rpx; font-size: 26rpx; color: #9c9585; }
.error-wrap { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; }
.error-text { font-size: 28rpx; color: #b0574f; margin-bottom: 32rpx; }
.btn-retry { padding: 20rpx 64rpx; background: #4a6b5c; border-radius: 44rpx; }
.btn-retry-text { color: #fff; font-size: 28rpx; }
.summary-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx;
}
.source-notice {
  display: block;
  font-size: 26rpx;
  color: #7a8078;
  line-height: 1.7;
  margin-bottom: 32rpx;
}
.summary-body {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 32rpx;
  margin-bottom: 48rpx;
}
.summary-text { font-size: 30rpx; color: #2f3d35; line-height: 1.8; }
.actions { display: flex; flex-direction: column; }
.btn-primary {
  background: #4a6b5c;
  border-radius: 48rpx;
  padding: 26rpx 0;
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.btn-primary-text { color: #fff; font-size: 30rpx; }
.btn-secondary {
  background: #fffefa;
  border: 2rpx solid #4a6b5c;
  border-radius: 48rpx;
  padding: 24rpx 0;
  display: flex;
  justify-content: center;
  margin-bottom: 24rpx;
}
.btn-secondary-text { color: #4a6b5c; font-size: 30rpx; }
.btn-link { display: flex; justify-content: center; padding: 12rpx 0; }
.btn-link-text { color: #8a9188; font-size: 26rpx; text-decoration: underline; }
.btn-disabled { opacity: 0.6; }
.edit-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx;
}
.edit-title { display: block; font-size: 34rpx; font-weight: 600; color: #2f3d35; margin-bottom: 16rpx; }
.edit-hint { display: block; font-size: 26rpx; color: #7a8078; line-height: 1.6; margin-bottom: 28rpx; }
.edit-textarea {
  width: 100%;
  min-height: 300rpx;
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 28rpx;
  font-size: 28rpx;
  color: #2f3d35;
  line-height: 1.7;
  box-sizing: border-box;
}
.edit-count { display: flex; justify-content: flex-end; margin: 12rpx 0 32rpx; }
.edit-count-text { font-size: 22rpx; color: #b3ac9c; }
</style>
