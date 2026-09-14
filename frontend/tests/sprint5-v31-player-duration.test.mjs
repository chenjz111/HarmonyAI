/**
 * Sprint 5 / V3.1 —— 音乐播放器真实时长显示（current / total）
 *
 * 纯静态/单元测试：不联网、不调用任何生成或识别服务、不播放真实音频。
 * 运行：cd frontend && node --test "tests/sprint5-v31-player-duration.test.mjs"
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

import { formatDuration } from "../common/v31-player-time.js"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

const playerPath = "pages/v3-player/v3-player.vue"
const player = read(playerPath)
const timeHelperSource = read("common/v31-player-time.js")

test("formatDuration renders zero-padded MM:SS and marks unknown totals", () => {
  assert.equal(typeof formatDuration, "function")
  // 常规音乐时长
  assert.equal(formatDuration(0), "00:00")
  assert.equal(formatDuration(35), "00:35")
  assert.equal(formatDuration(65), "01:05")
  assert.equal(formatDuration(180), "03:00")
  assert.equal(formatDuration(3599), "59:59")
  // 小数秒向下取整，不四舍五入
  assert.equal(formatDuration(180.9), "03:00")
  assert.equal(formatDuration("180"), "03:00")
  // 未知 / 非法 -> 占位符，绝不显示 00:00 冒充已知
  assert.equal(formatDuration(undefined), "--:--")
  assert.equal(formatDuration(null), "--:--")
  assert.equal(formatDuration(Number.NaN), "--:--")
  assert.equal(formatDuration(Number.POSITIVE_INFINITY), "--:--")
  assert.equal(formatDuration(-1), "--:--")
  assert.equal(formatDuration(""), "--:--")
  // 只有达到 1 小时才使用 HH:MM:SS
  assert.equal(formatDuration(3600), "01:00:00")
  assert.equal(formatDuration(3661), "01:01:01")
  // 未知占位符必须由 helper 本身提供（页面不重复硬编码）
  assert.match(timeHelperSource, /--:--/)
})

test("player page carries no hardcoded 180-second duration assumption", () => {
  // 页面 CSS 里存在 180deg 旋转（linear-gradient(180deg, ...)）；剔除合法的角度用法后，
  // 源码中不允许再出现任何 180 常量（即不得把 3 分钟写死为时长或超时）。
  const withoutRotationAngles = player.replace(/180deg/g, "<DEG>")
  assert.doesNotMatch(
    withoutRotationAngles,
    /\b180\b/,
    "player must not hardcode 180 (3 minutes) anywhere except CSS 180deg rotation",
  )
  assert.doesNotMatch(player, /duration\s*[:=]\s*180\b/, "duration must not be hardcoded to 180")
  assert.doesNotMatch(player, /\b180\s*\*\s*1000\b/, "no hardcoded 180s timeout")
  assert.doesNotMatch(player, /3\s*分钟/, "no static 3-minute label")
})

test("total duration comes from persisted duration_seconds, then the real audio context", () => {
  // 1) 数据源：后端 read model 持久化的 duration_seconds
  assert.match(player, /duration_seconds/, "player must read the persisted duration_seconds value")
  assert.match(
    player,
    /this\.music\s*&&\s*this\.music\.duration_seconds/,
    "duration_seconds must be read from the same music object the page already loads",
  )
  // 2) 兜底：InnerAudioContext 上报的真实音频时长
  assert.match(player, /uni\.createInnerAudioContext\(\)/, "player must use uni InnerAudioContext")
  assert.match(player, /onCanplay\(/, "player must read the real audio duration after load")
  assert.match(player, /this\.audioCtx\.duration/, "total must fall back to the real audio duration")

  // 优先级：duration_seconds 必须排在音频时长之前
  const totalBlock = (player.match(/totalSeconds\(\)\s*\{[\s\S]*?\n {4}\},/) || [""])[0]
  assert.ok(totalBlock.includes("totalSeconds()"), "player must define a totalSeconds computed")
  const persistedIndex = totalBlock.indexOf("duration_seconds")
  const audioIndex = totalBlock.indexOf("this.duration")
  assert.ok(persistedIndex >= 0, "totalSeconds must consider the persisted duration_seconds")
  assert.ok(audioIndex >= 0, "totalSeconds must fall back to the audio-reported duration")
  assert.ok(
    persistedIndex < audioIndex,
    "persisted duration_seconds must take priority over the audio-reported duration",
  )

  // 展示的总时长不得是常量字符串
  assert.doesNotMatch(
    player,
    /["'`]\s*\d{1,2}:\d{2}\s*["'`]/,
    "the displayed total must not be a constant time string",
  )
})

test("time readout shows current / total via the shared MM:SS helper on one real time base", () => {
  const template = (player.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
  // current / total 组合读数（例如 00:35 / 03:00）
  assert.match(
    template,
    /\{\{\s*formatDuration\(currentTime\)\s*\}\}\s*\/\s*\{\{\s*formatDuration\(totalSeconds\)\s*\}\}/,
    "progress readout must render current / total with the shared helper",
  )
  // 读数与进度条共用同一时间基：onTimeUpdate -> currentTime -> progressPercent -> 宽度
  assert.match(player, /onTimeUpdate\(/, "currentTime must be driven by the real onTimeUpdate event")
  assert.match(player, /this\.currentTime\s*=\s*this\.audioCtx\.currentTime/)
  assert.match(player, /progressPercent\(\)\s*\{[\s\S]*?this\.currentTime\s*\/\s*this\.totalSeconds/)
  assert.match(
    template,
    /width:\s*progressPercent\s*\+\s*'%'/,
    "progress bar width must be the percentage derived from the same time base",
  )
  // helper 直接复用页面导入的纯函数（模板与测试同源）
  assert.match(
    player,
    /import\s*\{\s*formatDuration\s*\}\s*from\s*"\.\.\/\.\.\/common\/v31-player-time\.js"/,
    "player must import formatDuration from common/v31-player-time.js",
  )
  // 暂停不清零当前时间/进度
  const pauseBlock = (player.match(/pause\(\)\s*\{[\s\S]*?\n {4}\},/) || [""])[0]
  assert.ok(pauseBlock.includes("pause()"), "pause() must be implemented")
  assert.doesNotMatch(pauseBlock, /this\.currentTime\s*=\s*0/, "pause must not reset currentTime")
  // 播放结束后仍保留完整总时长与进度
  const endedBlock = (player.match(/onEnded\(\(\)\s*=>\s*\{[\s\S]*?\n {10}\}/) || [""])[0]
  assert.ok(endedBlock.includes("onEnded"), "onEnded must be wired")
  assert.doesNotMatch(endedBlock, /this\.currentTime\s*=\s*0/, "playback end must not wipe the elapsed time")
  assert.match(endedBlock, /this\.totalSeconds/, "playback end must keep the real total visible")
})
