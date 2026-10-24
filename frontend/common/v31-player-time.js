/**
 * V3.1 播放器时间格式化（纯函数，可被 node:test 直接导入）
 *
 * 规则（Issue：播放器展示真实 "current / total"）：
 * - 常规音乐使用 MM:SS，例如 0 -> "00:00"、65 -> "01:05"、180 -> "03:00"
 * - 仅当总时长达到 1 小时及以上才使用 HH:MM:SS
 * - 时长未知（null / undefined / 空串 / 非有限数 / 负数）显示 "--:--"
 *
 * 注意：0 是合法时长（"00:00"），因此"未知"必须用 null/undefined 表示，
 * 播放页的 totalSeconds 在数据与音频都未给出时长时返回 null。
 */

const UNKNOWN_TIME = "--:--"

function toFiniteSeconds(value) {
  if (value === null || value === undefined) return null
  if (typeof value === "string" && value.trim() === "") return null
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds < 0) return null
  return seconds
}

/**
 * @param {number|string|null|undefined} seconds 秒数
 * @returns {string} "MM:SS" / "HH:MM:SS" / "--:--"
 */
export function formatDuration(seconds) {
  const value = toFiniteSeconds(seconds)
  if (value === null) return UNKNOWN_TIME

  const total = Math.floor(value)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const mm = String(minutes).padStart(2, "0")
  const ss = String(secs).padStart(2, "0")

  if (hours > 0) return `${String(hours).padStart(2, "0")}:${mm}:${ss}`
  return `${mm}:${ss}`
}

export { UNKNOWN_TIME as UNKNOWN_DURATION_LABEL }
