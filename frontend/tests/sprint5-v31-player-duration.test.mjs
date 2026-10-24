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

test("duration authority belongs to player-controller and music-presentation", () => {
  assert.match(player, /createPlayerController/)
  assert.match(player, /measuredSeconds:\s*this\.playerState\.duration/)
  assert.match(player, /playerPresentation\.duration/)
  assert.doesNotMatch(player, /this\.audioCtx\.duration|totalSeconds\(\)/, "page must not calculate audio duration")
  assert.doesNotMatch(
    player,
    /["'`]\s*\d{1,2}:\d{2}\s*["'`]/,
    "the displayed total must not be a constant time string",
  )
})

test("time readout and progress bar consume one shared presentation model", () => {
  const template = (player.match(/<template>[\s\S]*?<\/template>/) || [""])[0]
  assert.match(player, /presentProgress/)
  assert.match(template, /progressPresentation\.currentText/)
  assert.match(template, /progressPresentation\.totalText/)
  assert.match(template, /progressPresentation\.percent/)
  assert.doesNotMatch(player, /onTimeUpdate\(|formatDuration\(|progressPercent\(\)/, "page must not own progress calculations")
})
