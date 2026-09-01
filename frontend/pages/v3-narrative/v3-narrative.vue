<script>
/**
 * V3 最近情况页（文字/语音，选填）
 * 合同依据：frontend-read-model-contract-v3.md §5 Narrative / Voice Page
 *          harmonyai-v3-owner-flow-amendment-001.md §2
 *
 * 两条路径此步均为选填、可整步跳过；跳过不创建空 Understanding。
 * 转写结果先展示给用户确认后才有效；ASR 不可用时文字输入始终可用。
 *
 * P0-1：语音转写仅在显式 mock 模式提供模拟数据（并明确标注演示）；
 * real/hybrid 模式没有真实 ASR 时，语音入口显示"暂不可用"，绝不注入虚构 transcript。
 * P1-1：real 模式下描述文本暂存本机（评估服务开通后随问卷一起提交），
 * 页面明确告知"已保存待提交"，不声称已实时提交。
 */
import { apiV3 } from "../../common/api-v3.js"

const MAX_VOICE_SECONDS = 180

export default {
  data() {
    return {
      withDocument: false, // 有资料模式（显示步骤标签差异）
      text: "",
      // 仅显式 mock 模式提供模拟语音转写；real/hybrid 语音入口显示暂不可用
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
    // 从 session 判断模式（mock：读 api 状态）
    apiV3.getSession().then((s) => {
      this.withDocument = s.input_mode === "with_document"
    }).catch(() => {})
  },
  onUnload() {
    this.stopRecordTimer()
  },
  methods: {
    // ---- 录音（仅 mock 演示模式可用；real/hybrid 无真实 ASR，不伪造转写） ----
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
      // 模拟 ASR（仅 mock 演示模式可达）：返回演示转写文本，需用户确认后才作为输入
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
        // 文字/语音均选填；直接进入问卷（有资料=选填 / 无资料=必填）
        if (this.text && this.text.trim()) {
          try { uni.setStorageSync("v3_narrative_text", this.text.trim()) } catch (e) { /* ignore */ }
        }
        uni.redirectTo({ url: "/pages/v3-questionnaire/v3-questionnaire" })
      } finally {
        this.submitting = false
      }
    },
    skip() {
      // 整步跳过：不创建空 Understanding（Read Model §5.1）
      uni.redirectTo({ url: "/pages/v3-questionnaire/v3-questionnaire" })
    },
  },
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="step-tag">{{ withDocument ? "有资料流程 · 第 3 步 · 选填" : "无资料流程 · 第 1 步 · 选填" }}</text>
      <text class="page-title">说说最近发生了什么</text>
      <text class="page-subtitle">可以写下最近的事情、感受、睡眠或身体状态，不需要先判断自己的情绪。</text>
    </view>

    <!-- 文字输入（始终可用） -->
    <view class="text-card">
      <textarea
        class="text-input"
        v-model="text"
        :maxlength="2000"
        placeholder="自由填写，也可以跳过这一步。"
      />
      <view class="text-count"><text class="text-count-text">{{ (text || '').length }} / 2000</text></view>
    </view>

    <!-- P1-1：real 模式下描述文本为"已保存待提交"，不声称已实时提交 -->
    <view v-if="!voiceSimulated" class="save-note">
      <text class="save-note-text">你填写的内容会先保存在本机，评估服务开通后与问卷作答一起提交，不会丢失。</text>
    </view>

    <!-- 语音输入（P0-1：仅显式 mock 演示模式提供模拟转写；real/hybrid 明确暂不可用） -->
    <view class="voice-card">
      <view class="voice-head">
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
            <view class="ts-btn ts-primary" @click="confirmTranscript"><text class="ts-btn-text ts-primary-text">使用这段文字</text></view>
            <view class="ts-btn" @click="cancelTranscript"><text class="ts-btn-text">重新录制</text></view>
          </view>
        </view>
        <view v-else-if="transcript && transcript.confirmed" class="transcript-done">
          <text class="transcript-done-text">✓ 已确认使用语音转写内容</text>
        </view>
      </template>

      <view v-else class="voice-unavailable">
        <view class="voice-mic"><text class="mic-icon">🎤</text></view>
        <text class="voice-unavailable-title">语音描述暂不可用</text>
        <text class="voice-unavailable-desc">当前版本暂不支持语音输入，你可以使用上方文字填写，内容会一并保留。</text>
      </view>
    </view>

    <view class="actions">
      <view class="btn-primary" :class="{ 'btn-disabled': submitting }" @click="next">
        <text class="btn-primary-text">继续</text>
      </view>
      <view class="btn-link" @click="skip">
        <text class="btn-link-text">暂不填写，继续</text>
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
.page-title { display: block; font-size: 44rpx; font-weight: 600; color: #2f3d35; margin-bottom: 16rpx; }
.page-subtitle { display: block; font-size: 28rpx; color: #7a8078; line-height: 1.6; }
.text-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 32rpx;
}
.text-input {
  width: 100%;
  min-height: 220rpx;
  font-size: 28rpx;
  color: #2f3d35;
  line-height: 1.7;
}
.text-count { display: flex; justify-content: flex-end; margin-top: 12rpx; }
.text-count-text { font-size: 22rpx; color: #b3ac9c; }
.save-note {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 20rpx 28rpx;
  margin-bottom: 32rpx;
}
.save-note-text { font-size: 24rpx; color: #8a9188; line-height: 1.6; }
.voice-card {
  background: #fffefa;
  border: 2rpx solid #e8e2d4;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 40rpx;
}
.voice-head { display: flex; justify-content: space-between; margin-bottom: 28rpx; }
.voice-title { font-size: 30rpx; font-weight: 500; color: #2f3d35; }
.voice-limit { font-size: 24rpx; color: #b3ac9c; }
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
  background: #eef0ea;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20rpx;
}
.mic-icon { font-size: 52rpx; }
.voice-idle-text { font-size: 26rpx; color: #7a8078; }
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
  background: #b0574f;
  border-radius: 50%;
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.rec-time { font-size: 40rpx; color: #2f3d35; font-variant-numeric: tabular-nums; }
.rec-stop {
  border: 2rpx solid #b0574f;
  border-radius: 36rpx;
  padding: 10rpx 36rpx;
}
.rec-stop-text { color: #b0574f; font-size: 26rpx; }
.transcript-card {
  background: #f6f3ea;
  border-radius: 16rpx;
  padding: 28rpx;
  margin-top: 24rpx;
}
.transcript-title { display: block; font-size: 24rpx; color: #9c9585; margin-bottom: 14rpx; }
.transcript-text { display: block; font-size: 28rpx; color: #2f3d35; line-height: 1.7; margin-bottom: 24rpx; }
.transcript-actions { display: flex; gap: 20rpx; }
.ts-btn {
  flex: 1;
  border: 2rpx solid #4a6b5c;
  border-radius: 40rpx;
  padding: 16rpx 0;
  display: flex;
  justify-content: center;
}
.ts-btn-text { color: #4a6b5c; font-size: 26rpx; }
.ts-primary { background: #4a6b5c; }
.ts-primary-text { color: #fff; }
.transcript-done {
  background: #edf1ec;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-top: 24rpx;
  display: flex;
  justify-content: center;
}
.transcript-done-text { font-size: 26rpx; color: #4a6b5c; }
.voice-unavailable {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0 28rpx;
}
.voice-unavailable-title { font-size: 28rpx; color: #2f3d35; font-weight: 500; margin-bottom: 12rpx; }
.voice-unavailable-desc { font-size: 24rpx; color: #9c9585; line-height: 1.6; text-align: center; }
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
.btn-disabled { opacity: 0.6; }
</style>
