<script>
/**
 * V3 最终评估确认页（唯一一次确认）
 * 合同依据：frontend-read-model-contract-v3.md §8 Final Assessment Confirmation
 *          harmonyai-v3-owner-flow-amendment-001.md §2（唯一最终确认）/ §4.3
 *
 * - Agent1 先产出评估，本页确认后最新已确认 revision 才进入后续流程
 * - 确认只有一次；可带修正（changes[]）提交，返回 revision+1
 * - 不展示 evidence_coverage、provider_metadata、内部 enum、置信度等禁止字段
 * - Safety policy/状态不显示（deferred_v3 / not_run 为内部字段）
 */
import { apiV3 } from "../../common/api-v3.js"

export default {
  data() {
    return {
      loading: true,
      error: "",
      model: null,
      confirming: false,
      // 修正状态
      correcting: false,
      draftSeverity: {}, // { target_id: severity }
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
      try {
        this.model = await apiV3.getAssessment()
      } catch (e) {
        this.error = e.message || "评估加载失败，请重试"
      } finally {
        this.loading = false
      }
    },
    // 操作1：基本符合，继续（唯一最终确认）
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
    // 操作2：有些地方不对，我要修改（修正入口）
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
    // 修正提交：带 changes[]，成功返回 revision+1 并继续
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
        // 确认 + 修正一次性提交；无改动时等同直接确认
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
  <view class="container">
    <view class="header">
      <text class="step-tag">最后一步 · 确认</text>
      <text class="page-title">{{ model ? model.title : "确认一下我们对你当前状态的理解" }}</text>
    </view>

    <view v-if="loading" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在准备你的评估结果…</text>
    </view>

    <view v-else-if="error" class="error-wrap">
      <text class="error-text">{{ error }}</text>
      <view class="btn-retry" @click="load"><text class="btn-retry-text">重试</text></view>
    </view>

    <view v-else-if="!correcting" class="confirm-card">
      <view class="summary-box">
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

      <view class="actions">
        <view class="btn-primary" :class="{ 'btn-disabled': confirming }" @click="confirmOk">
          <text class="btn-primary-text">基本符合，继续</text>
        </view>
        <view class="btn-secondary" @click="startCorrect">
          <text class="btn-secondary-text">有些地方不对，我要修改</text>
        </view>
      </view>
    </view>

    <!-- 修正态：调整各项程度 -->
    <view v-else class="correct-card">
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

      <view class="actions">
        <view class="btn-primary" :class="{ 'btn-disabled': confirming }" @click="saveCorrect">
          <text class="btn-primary-text">保存并继续</text>
        </view>
        <view class="btn-secondary" @click="cancelCorrect">
          <text class="btn-secondary-text">取消修改</text>
        </view>
      </view>
    </view>

    <view class="disclaimer">
      <text class="disclaimer-text">本结果仅用于音乐调养参考，不构成医学诊断。</text>
    </view>
  </view>
</template>

<style>
.container {
  min-height: 100vh;
  background: #f7f3eb;
  padding: 70rpx 48rpx 60rpx;
  box-sizing: border-box;
}
.header { margin-bottom: 40rpx; }
.step-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #4a6b5c;
  background: #e6ebe5;
  border-radius: 8rpx;
  padding: 6rpx 16rpx;
  margin-bottom: 18rpx;
}
.page-title { display: block; font-size: 40rpx; font-weight: 600; color: #2f3d35; line-height: 1.4; }
.confirm-card, .correct-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}
.summary-box {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 32rpx;
  margin-bottom: 36rpx;
}
.summary-text { font-size: 30rpx; color: #2f3d35; line-height: 1.8; }
.section { margin-bottom: 32rpx; }
.section-title {
  display: block;
  font-size: 26rpx;
  color: #9c9585;
  margin-bottom: 18rpx;
}
.section-item {
  display: flex;
  align-items: center;
  padding: 14rpx 0;
}
.item-dot {
  width: 12rpx;
  height: 12rpx;
  background: #4a6b5c;
  border-radius: 50%;
  margin-right: 20rpx;
  flex-shrink: 0;
}
.item-text { font-size: 28rpx; color: #2f3d35; }
.correct-title { display: block; font-size: 34rpx; font-weight: 600; color: #2f3d35; margin-bottom: 14rpx; }
.correct-hint { display: block; font-size: 26rpx; color: #7a8078; line-height: 1.6; margin-bottom: 32rpx; }
.correct-item { margin-bottom: 36rpx; }
.correct-label { display: block; font-size: 28rpx; color: #2f3d35; font-weight: 500; margin-bottom: 18rpx; }
.severity-row { display: flex; gap: 16rpx; }
.severity-btn {
  flex: 1;
  border: 2rpx solid #d9d3c2;
  border-radius: 36rpx;
  padding: 16rpx 0;
  display: flex;
  justify-content: center;
}
.severity-active { background: #4a6b5c; border-color: #4a6b5c; }
.severity-btn-text { font-size: 26rpx; color: #7a8078; }
.severity-active-text { color: #fff; }
.actions { display: flex; flex-direction: column; margin-top: 12rpx; }
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
}
.btn-secondary-text { color: #4a6b5c; font-size: 30rpx; }
.btn-disabled { opacity: 0.6; }
.disclaimer { margin-top: 48rpx; text-align: center; }
.disclaimer-text { font-size: 22rpx; color: #b3ac9c; }
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
</style>
