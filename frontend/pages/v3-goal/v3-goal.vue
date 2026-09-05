<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">{{ withDocument ? "有资料流程 · 第 5 步 · 选填" : "无资料流程 · 第 3 步 · 选填" }}</text>
      <text class="page-title">疗愈诉求</text>
      <text class="page-subtitle">如果对这次调适有特别的期待，可以告诉我们；没有的话直接跳过即可。这一步选填。</text>
    </view>

    <view v-if="submitting" class="loading-wrap">
      <view class="loading-ring"></view>
      <text class="loading-text">正在整理你的选择…</text>
    </view>

    <template v-else>
      <view class="card">
        <view class="card-head">
          <text class="card-title">主要诉求</text>
          <text class="card-hint">选择一项最希望调适的方面</text>
        </view>
        <view class="chip-grid">
          <view
            v-for="it in intents"
            :key="it.code"
            class="chip"
            :class="{ 'chip-active': primary_goal === it.code }"
            @click="pickPrimaryGoal(it.code)"
          >
            <text class="chip-text" :class="{ 'chip-text-active': primary_goal === it.code }">{{ it.label }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">次要诉求</text>
          <text class="card-hint">还可以再选一项</text>
        </view>
        <view class="chip-grid">
          <view
            v-for="it in intents"
            :key="it.code"
            class="chip"
            :class="{ 'chip-active': secondary_goal === it.code, 'chip-dim': primary_goal === it.code }"
            @click="pickSecondaryGoal(it.code)"
          >
            <text class="chip-text" :class="{ 'chip-text-active': secondary_goal === it.code }">{{ it.label }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">其他想法</text>
          <text class="card-hint">选填</text>
        </view>
        <textarea
          class="custom-input"
          v-model="custom_goal_text"
          :maxlength="200"
          placeholder="例如：希望音乐更舒缓一些、节奏慢一些……"
        />
        <view class="custom-count"><text class="custom-count-text">{{ (custom_goal_text || '').length }} / 200</text></view>
      </view>

      <!-- 如实标注：该信息本机暂存，不会丢失（此步无后端持久化依赖） -->
      <view class="save-note">
        <text class="save-note-text">这一步选填。你的选择会保存在本机，不会丢失；之后随时可以重新体验来更新它。</text>
      </view>

      <view class="actions">
        <view class="btn-primary" @click="next">
          <text class="btn-primary-text">继续</text>
        </view>
        <view class="btn-link" @click="skip">
          <text class="btn-link-text">暂不选择，直接继续</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
/**
 * V3.1 疗愈诉求页（Issue #100：Provisional Flow 选填加回）
 *
 * 意图代码使用合同权威枚举（frontend-read-model-contract-v3.md §10 + 复审指令）：
 *   sleep / relaxation / emotion_regulation / focus / energy / stress_relief / other
 * - 不使用自定义代码（如 relax/soothe/lift_mood 等），与后端契约字段一一对应，
 *   便于上游 Agent / 下游生成器直接消费。
 * - 整页选填、可整步跳过；最多 2 项：主诉求（primary_goal）+ 次诉求（secondary_goal）。
 * - "其他想法"补充输入 ≤ 200 字（前端 maxlength=200；后端写入时也按同样上限校验）。
 * - 不虚构、不默认补全任何偏好：用户未选择时不留占位、不提交空对象。
 * - 后端暂无对应保存能力 → 选择内容本机暂存（safeSet），页面如实标注，
 *   mock 状态机同步记录。后端交付后由 apiV3.submitHealingIntent 替换为本请求。
 *
 * 复审指令（合同校验）：
 *   1. 用户不能只填"其他想法"而不选择主要诉求
 *   2. primary_goal === "other" 时，必须填写 1~200 字补充内容
 *   3. 全空 → 视为整页跳过，可直接继续
 *   4. secondary_goal 不能脱离 primary_goal 单独存在
 *   5. 前端保存字段与正式合同对应：primary_goal / secondary_goal / custom_goal_text
 *   6. 不再使用 primary / secondary / custom_text 作为最终提交字段
 * - 校验逻辑集中在 common/v3-healing-intent.js（decideHealingIntent），
 *   本组件只负责 UI 绑定 + 调用 + toast 提示。
 *
 * 后续：v3-confirm（完成近期状态总结）。
 */
import { apiV3 } from "../../common/api-v3.js"
import {
  INTENT_CODES,
  decideHealingIntent,
  HEALING_INTENT_REASON_MESSAGE,
} from "../../common/v3-healing-intent.js"

export default {
  data() {
    return {
      withDocument: false,
      intents: INTENT_CODES,
      // 合同权威字段名（primary_goal / secondary_goal / custom_goal_text），
      // 与 Read Model §10 一一对应；后端未交付时本机暂存同样采用这套字段，
      // 接入真实接口时无需再做映射。
      primary_goal: null,
      secondary_goal: null,
      custom_goal_text: "",
      submitting: false,
    }
  },
  onLoad() {
    apiV3.getSession()
      .then((s) => {
        this.withDocument = s.input_mode === "with_document"
      })
      .catch(() => {})
  },
  methods: {
    pickPrimaryGoal(code) {
      if (this.primary_goal === code) {
        this.primary_goal = null
        // 清空主诉求时，连带清掉"其他想法"——避免出现"只填文字、不选主要诉求"的状态
        this.custom_goal_text = ""
        return
      }
      this.primary_goal = code
      if (this.secondary_goal === code) this.secondary_goal = null
    },
    pickSecondaryGoal(code) {
      if (this.primary_goal === code) {
        uni.showToast({ title: "已在主要诉求中", icon: "none" })
        return
      }
      if (!this.primary_goal) {
        // 没有主诉求时不允许先选次要诉求
        uni.showToast({ title: "请先选择主要诉求", icon: "none" })
        return
      }
      if (this.secondary_goal === code) {
        this.secondary_goal = null
        return
      }
      this.secondary_goal = code
    },
    /**
     * 继续按钮：先走合同校验 → 全空 skip / 不合规 toast / 合规 submit
     * 与原行为等价，仅：
     *   - 字段名改为 primary_goal / secondary_goal / custom_goal_text
     *   - 增加"只填文字不选主要诉求" / "other 必填文字" / "secondary 脱离 primary"
     *     / "文字超长" 四类校验
     */
    async next() {
      if (this.submitting) return
      const decision = decideHealingIntent({
        primary_goal: this.primary_goal,
        secondary_goal: this.secondary_goal,
        custom_goal_text: this.custom_goal_text,
      })
      // 规则 1：全空 → 整页跳过，与原行为一致
      if (decision.skip) {
        this.skip()
        return
      }
      // 校验失败 → toast 阻断，不提交、不跳转
      if (!decision.ok) {
        const msg = HEALING_INTENT_REASON_MESSAGE[decision.reason] || "请检查后重试"
        uni.showToast({ title: msg, icon: "none" })
        return
      }
      this.submitting = true
      try {
        // 提交 payload 使用合同权威字段名（primary_goal / secondary_goal / custom_goal_text）
        await apiV3.submitHealingIntent(decision.payload)
        uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
      } catch (e) {
        uni.showToast({ title: (e && e.message) || "保存失败，请稍后重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    skip() {
      // 整步跳过：不保存任何偏好、不伪造默认值
      uni.redirectTo({ url: "/pages/v3-confirm/v3-confirm" })
    },
  },
}
</script>

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
.page-title { display: block; font-size: 44rpx; font-weight: 600; color: #2f3d35; margin-bottom: 16rpx; }
.page-subtitle { display: block; font-size: 28rpx; color: #7a8078; line-height: 1.6; }
.card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 32rpx;
}
.card-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 24rpx; }
.card-title { font-size: 30rpx; font-weight: 500; color: #2f3d35; }
.card-hint { font-size: 22rpx; color: #b3ac9c; }
.chip-grid { display: flex; flex-wrap: wrap; gap: 20rpx; }
.chip {
  background: #f6f3ea;
  border: 2rpx solid transparent;
  border-radius: 40rpx;
  padding: 18rpx 32rpx;
}
.chip-active { background: #edf1ec; border-color: #4a6b5c; }
.chip-dim { opacity: 0.45; }
.chip-text { font-size: 28rpx; color: #4a554c; }
.chip-text-active { color: #2f5d43; font-weight: 500; }
.custom-input {
  width: 100%;
  min-height: 140rpx;
  font-size: 28rpx;
  color: #2f3d35;
  line-height: 1.7;
}
.custom-count { display: flex; justify-content: flex-end; margin-top: 8rpx; }
.custom-count-text { font-size: 22rpx; color: #b3ac9c; }
.save-note {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 20rpx 28rpx;
  margin-bottom: 40rpx;
}
.save-note-text { font-size: 24rpx; color: #8a9188; line-height: 1.6; }
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
.btn-link { display: flex; justify-content: center; padding: 12rpx 0; }
.btn-link-text { color: #8a9188; font-size: 26rpx; text-decoration: underline; }
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
</style>
