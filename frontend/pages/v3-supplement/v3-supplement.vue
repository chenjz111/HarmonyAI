<script>
/**
 * V3.1 近况补充页（Issue #100："想再补充一些近况吗？" 选填）
 *
 * V3.1 流程变更：最近情况（Narrative）退出主流程，改为主流程中一个可选的
 * 补充页。两条路径（有资料 / 无资料）此步均为选填、可整步跳过。
 *
 * 输入语义与 v3-narrative 保持一致（该页保留为兼容）：
 *  - 有资料路径：后端暂不支持向已确认摘要追加描述源 → 文本本机暂存，如实标注
 *  - 无资料路径：填写则通过 narrative 源真实提交并确认绑定会话，失败如实报错
 *  - 语音转写仅在显式 mock 模式提供模拟数据并标注演示；real/hybrid 不伪造
 *
 * ===== 后端对齐依赖（复审注明：等待钟睿宸对齐，未确定前不擅自恢复旧流程） =====
 *  - 字段：narrative inline text（已提交）
 *  - 端点：POST /api/v3/understandings，inputs[].source_type = "narrative"
 *  - 保存位置：Understanding + Source；CAS 确认后写入 session understanding_ref
 *  - 调用方式：apiV3.submitNarrative(text) → create → confirmUnderstanding(decision="confirm")
 *  - 当前缺口：与钟睿宸对齐的"补充信息"新字段 / 保存方式仍在协议中
 *    —— 在此之前本页面**绝不**自行恢复旧版 narrative 必填规则，也**绝不**把本机暂存伪装成已提交；
 *    失败/缺口一律如实抛错（错误码 NARRATIVE_APPEND_UNSUPPORTED 等）。
 *
 * 后续：v3-questionnaire
 *
 * 视觉（重水墨国风）：han-page 山水底纹 + 左侧印章导航 + 宣纸卡片 + 朱砂主按钮
 */
import { apiV3 } from "../../common/api-v3.js"
import HanSideNav from "../../components/sprint3/han-side-nav.vue"

const MAX_VOICE_SECONDS = 180

export default {
  components: { HanSideNav },
  data() {
    return {
      withDocument: false, // 有资料模式（步骤标签差异）
      text: "",
      voiceSimulated: apiV3.INPUT_SIMULATED,
      recording: false,
      recordSeconds: 0,
      recordTimer: null,
      voiceAvailable: true,
      transcript: null, // { text, confirmed }
      submitting: false,
    }
  },
  onLoad() {
    apiV3.getSession().then((s) => {
      this.withDocument = s.input_mode === "with_document"
    }).catch(() => {})
  },
  onUnload() {
    this.stopRecordTimer()
  },
  methods: {
    // ---- 录音（仅 mock 演示模式；real/hybrid 无真实 ASR，不伪造转写） ----
    async toggleRecord() {
      if (!this.voiceSimulated || !this.voiceAvailable) return
      if (this.recording) {
        this.stopRecording()
      } else {
        this.startRecording()
      }
    },
    startRecording() {
      this.recording = true
      this.recordSeconds = 0
      this.recordTimer = setInterval(() => {
        this.recordSeconds += 1
        if (this.recordSeconds >= MAX_VOICE_SECONDS) {
          this.stopRecording()
        }
      }, 1000)
    },
    stopRecording() {
      this.stopRecordTimer()
      this.recording = false
      this.transcript = {
        text: "最近一段时间事情比较多，晚上躺下后脑子停不下来，入睡比较慢，白天容易累。",
        confirmed: false,
      }
    },
    cancelTranscript() {
      this.transcript = null
    },
    confirmTranscript() {
      if (!this.transcript) return
      this.transcript.confirmed = true
      this.text = this.transcript.text
      uni.showToast({ title: "已使用语音转写内容", icon: "none" })
    },
    stopRecordTimer() {
      if (this.recordTimer) {
        clearInterval(this.recordTimer)
        this.recordTimer = null
      }
    },
    formatSec(s) {
      const m = Math.floor(s / 60)
      const sec = s % 60
      return (m < 10 ? "0" + m : m) + ":" + (sec < 10 ? "0" + sec : sec)
    },

    // ---- 流转 ----
    async next() {
      if (this.submitting) return
      this.submitting = true
      try {
        const text = (this.text || "").trim()
        if (text && this.withDocument) {
          // 有资料路径：后端暂不支持向已确认摘要追加描述源 → 本机暂存（如实标注）
          try { uni.setStorageSync("v3_narrative_text", text) } catch (e) { /* ignore */ }
        } else if (text) {
          // 无资料路径：narrative 源真实提交 + 确认绑定会话
          await apiV3.submitNarrative(text)
        }
        uni.redirectTo({ url: "/pages/v3-questionnaire/v3-questionnaire" })
      } catch (e) {
        // 提交失败：如实报错并停留本页，可重试或跳过
        uni.showToast({ title: (e && e.message) || "提交失败，请稍后重试", icon: "none" })
      } finally {
        this.submitting = false
      }
    },
    skip() {
      // 整步跳过：不创建空 Understanding
      uni.redirectTo({ url: "/pages/v3-questionnaire/v3-questionnaire" })
    },
  },
}
</script>

<template>
  <view class="page han-page side-nav-page">
    <han-side-nav current="question" />
    <view class="han-page-content container">
      <view class="header ink-fade-in">
        <view class="header-row">
          <view class="stage-seal">
            <text class="stage-seal-text">问</text>
          </view>
          <view class="header-titles">
            <text class="step-tag">{{ withDocument ? "有资料流程 · 补充近况（选填）" : "无资料流程 · 补充近况（选填）" }}</text>
            <text class="page-title han-title-brush revealed">想再补充一些近况吗？</text>
          </view>
        </view>
        <text class="page-subtitle">可以写下最近的事情、感受、睡眠或身体状态，不需要先判断自己的情绪。这一步选填，也可以跳过。</text>
      </view>

      <!-- 文字输入（始终可用） -->
      <view class="han-card text-card ink-fade-up">
        <view class="card-head">
          <view class="card-head-seal"><text class="card-head-seal-text">述</text></view>
          <text class="card-head-title">文字描述</text>
        </view>
        <textarea
          class="text-input"
          v-model="text"
          :maxlength="2000"
          placeholder="自由填写，也可以直接跳过这一步。"
        />
        <view class="text-count"><text class="text-count-text">{{ (text || '').length }} / 2000</text></view>
      </view>

      <!-- 有资料路径：本机暂存（后端追加源能力缺失），如实标注；
           无资料路径：点击"继续"即真实提交 -->
      <view v-if="!voiceSimulated && withDocument" class="save-note">
        <view class="save-note-dot"></view>
        <text class="save-note-text">你填写的内容会先保存在本机，待服务支持后随评估一并提交，不会丢失。</text>
      </view>
      <view v-else-if="!voiceSimulated" class="save-note">
        <view class="save-note-dot"></view>
        <text class="save-note-text">你填写的内容将在点击"继续"时提交，作为生成评估的参考。</text>
      </view>

      <!-- 语音输入（仅显式 mock 演示模式提供模拟转写；real/hybrid 明确暂不可用） -->
      <view class="han-card voice-card ink-fade-up">
        <view class="voice-head">
          <view class="card-head-seal card-head-seal--ink"><text class="card-head-seal-text">声</text></view>
          <text class="voice-title">语音描述</text>
          <text v-if="voiceSimulated" class="voice-limit">最长 3 分钟 · 演示数据</text>
        </view>

        <template v-if="voiceSimulated">
          <view v-if="!recording" class="voice-idle" @click="toggleRecord">
            <view class="voice-mic"><text class="mic-icon">🎤</text></view>
            <text class="voice-idle-text">点击开始录音</text>
          </view>

          <view v-else class="voice-recording">
            <view class="rec-dot"></view>
            <text class="rec-time">{{ formatSec(recordSeconds) }}</text>
            <view class="rec-stop" @click="toggleRecord"><text class="rec-stop-text">停止</text></view>
          </view>

          <!-- 转写结果：先确认后生效 -->
          <view v-if="transcript && !transcript.confirmed" class="transcript-card">
            <text class="transcript-title">语音转写结果（演示数据）</text>
            <text class="transcript-text">{{ transcript.text }}</text>
            <view class="transcript-actions">
              <view class="han-btn han-btn-primary ts-btn ts-primary" @click="confirmTranscript"><text class="ts-btn-text ts-primary-text">使用这段文字</text></view>
              <view class="han-btn han-btn-ghost ts-btn" @click="cancelTranscript"><text class="ts-btn-text">重新录制</text></view>
            </view>
          </view>
          <view v-else-if="transcript && transcript.confirmed" class="transcript-done">
            <text class="transcript-done-text">✓ 已确认使用语音转写内容</text>
          </view>
        </template>

        <view v-else class="voice-unavailable">
          <view class="voice-mic"><text class="mic-icon">🎤</text></view>
          <text class="voice-unavailable-title">语音描述暂不可用</text>
          <text class="voice-unavailable-desc">当前版本暂不支持语音输入，你可以使用上方文字填写。</text>
        </view>
      </view>

      <view class="actions">
        <view class="han-btn han-btn-primary btn-primary" :class="{ 'btn-disabled': submitting }" @click="next">
          <text class="btn-primary-text">继续</text>
        </view>
        <view class="btn-link" @click="skip">
          <text class="btn-link-text">暂不补充，继续</text>
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
  margin-bottom: 16rpx;
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

/* ===== 卡片头 ===== */
.card-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 24rpx;
}
.card-head-seal {
  min-width: 44rpx;
  height: 44rpx;
  background: var(--ink-primary);
  border-radius: var(--radius-seal);
  transform: rotate(-3deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 14rpx rgba(107, 124, 94, 0.2);
}
.card-head-seal--ink {
  background: var(--ink-700);
  box-shadow: 0 4rpx 14rpx rgba(26, 25, 22, 0.18);
}
.card-head-seal-text {
  color: var(--text-inverse);
  font-size: 24rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.card-head-title {
  font-size: 30rpx;
  font-weight: 500;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}

/* ===== 文字卡 ===== */
.text-card {
  border-radius: var(--radius-lg);
  padding: 32rpx;
  margin-bottom: 32rpx;
}
.text-input {
  width: 100%;
  min-height: 220rpx;
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.7;
}
.text-count {
  display: flex;
  justify-content: flex-end;
  margin-top: 12rpx;
}
.text-count-text {
  font-size: 22rpx;
  color: var(--text-muted);
}

/* ===== 暂存提示 ===== */
.save-note {
  background: rgba(244, 238, 219, 0.55);
  border: 1rpx solid var(--border-light);
  border-radius: 12rpx;
  padding: 20rpx 28rpx;
  margin-bottom: 32rpx;
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
}
.save-note-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: var(--ink-primary);
  margin-top: 12rpx;
  flex-shrink: 0;
}
.save-note-text {
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ===== 语音卡 ===== */
.voice-card {
  border-radius: var(--radius-lg);
  padding: 32rpx;
  margin-bottom: 40rpx;
}
.voice-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 28rpx;
}
.voice-title {
  font-size: 30rpx;
  font-weight: 500;
  color: var(--ink-700);
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  flex: 1;
}
.voice-limit {
  font-size: 24rpx;
  color: var(--text-muted);
}
.voice-idle {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0;
}
.voice-mic {
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  background: rgba(107, 124, 94, 0.1);
  border: 1rpx solid rgba(107, 124, 94, 0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20rpx;
}
.mic-icon {
  font-size: 52rpx;
}
.voice-idle-text {
  font-size: 26rpx;
  color: var(--text-secondary);
}
.voice-recording {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32rpx 0;
  gap: 32rpx;
}
.rec-dot {
  width: 20rpx;
  height: 20rpx;
  background: var(--ink-seal);
  border-radius: 50%;
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
.rec-time {
  font-size: 40rpx;
  color: var(--ink-700);
  font-variant-numeric: tabular-nums;
}
.rec-stop {
  border: 2rpx solid var(--ink-seal);
  border-radius: 36rpx;
  padding: 10rpx 36rpx;
}
.rec-stop-text {
  color: var(--ink-seal);
  font-size: 26rpx;
}
.transcript-card {
  background: rgba(244, 238, 219, 0.55);
  border: 1rpx solid var(--border-light);
  border-radius: 14rpx;
  padding: 28rpx;
  margin-top: 24rpx;
}
.transcript-title {
  display: block;
  font-size: 24rpx;
  color: var(--text-muted);
  margin-bottom: 14rpx;
}
.transcript-text {
  display: block;
  font-size: 28rpx;
  color: var(--ink-700);
  line-height: 1.7;
  margin-bottom: 24rpx;
}
.transcript-actions {
  display: flex;
  gap: 20rpx;
}
.ts-btn {
  flex: 1;
}
.ts-btn-text {
  color: var(--ink-700);
  font-size: 26rpx;
}
.ts-primary-text {
  color: var(--text-inverse);
}
.transcript-done {
  background: rgba(107, 124, 94, 0.1);
  border: 1rpx solid rgba(107, 124, 94, 0.2);
  border-radius: 14rpx;
  padding: 24rpx;
  margin-top: 24rpx;
  display: flex;
  justify-content: center;
}
.transcript-done-text {
  font-size: 26rpx;
  color: var(--ink-primary);
}
.voice-unavailable {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0 28rpx;
}
.voice-unavailable-title {
  font-size: 28rpx;
  color: var(--ink-700);
  font-weight: 500;
  margin-bottom: 12rpx;
  font-family: "LXGW WenKai", "KaiTi", "STKaiti", serif;
}
.voice-unavailable-desc {
  font-size: 24rpx;
  color: var(--text-muted);
  line-height: 1.6;
  text-align: center;
}

/* ===== 底部动作 ===== */
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
</style>
