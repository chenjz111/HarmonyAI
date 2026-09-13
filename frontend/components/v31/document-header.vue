<template>
  <view class="document-header">
    <view class="brand-row">
      <button role="button" class="back" aria-label="返回" @click="$emit('back')"><view class="back-chevron"></view></button>
      <image class="brand-leaf" src="/static/v31-document/leaf.svg" mode="aspectFit" />
      <text class="brand-name">HarmonyAI</text>
    </view>
    <view class="heading">
      <text class="step-tag">有资料流程 · 第 {{ step }} 步</text>
      <text class="page-title">{{ title }}</text>
      <view class="title-stroke"></view>
    </view>
    <view class="quote"><text>{{ quote }}</text><view class="quote-stroke"></view></view>
    <text v-if="subtitle" class="subtitle">{{ subtitle }}</text>
  </view>
</template>

<script>
export default {
  props: { step: { type: Number, required: true }, title: { type: String, required: true }, quote: { type: String, default: '' }, subtitle: { type: String, default: '' } },
  emits: ['back'],
}
</script>

<style scoped>
.document-header { position: relative; padding-top: 18px; color: #103f36; }
.brand-row { display: flex; align-items: center; height: 44px; gap: 8px; }
.back { display: flex; align-items: center; justify-content: center; width: 40px; height: 44px; margin: 0 0 0 -10px; padding: 0; background: transparent; border: 0; }
.back::after { border: 0; }
.back-chevron { width: 11px; height: 11px; border-left: 2px solid #123d34; border-bottom: 2px solid #123d34; transform: rotate(45deg); }
.brand-leaf { width: 30px; height: 28px; }
.brand-name { font-size: 16px; font-weight: 700; }
.heading { margin: 10px 0 0 34px; width: fit-content; max-width: calc(100% - 34px); }
.step-tag { display: block; width: fit-content; padding: 4px 11px; border-radius: 8px; background: rgba(98,143,125,.14); font-size: 12px; line-height: 1.6; letter-spacing: .08em; color: #4d776b; }
.page-title { display: block; margin-top: 7px; font: 700 27px/1.35 "KaiTi","STKaiti","Noto Serif SC",serif; letter-spacing: .035em; color: #103f36; }
.title-stroke { height: 3px; margin-top: 5px; background: linear-gradient(90deg,transparent,#194d3f 25%,#194d3f 60%,transparent); border-radius: 50%; }
.quote { position: absolute; right: 2px; top: 90px; font: 12px/1.65 "KaiTi","STKaiti",serif; white-space: pre-line; transform: rotate(-10deg); color: #285c4d; }
.quote-stroke { width: 75px; height: 2px; margin-top: 4px; background: linear-gradient(90deg,transparent,#61947f,transparent); }
.subtitle { display: block; margin: 16px 0 0 34px; font-size: 13px; line-height: 1.75; color: #66766e; }
@media(max-width:350px) { .page-title { font-size: 23px; } .quote { font-size: 11px; right: -3px; } .heading,.subtitle { margin-left: 24px; } }
</style>
