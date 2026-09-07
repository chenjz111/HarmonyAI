/**
 * V3.1 疗愈诉求（可选）合同校验模块
 *
 * 依据：Issue #111 冻结 V3.1 规则 + 复审指令 2026-09-07
 *
 * 字段与 Read Model 合同权威字段一一对应：
 *   - primary_goal      （主要诉求，contract 7 code 之一：sleep / relaxation / ... / other；可空）
 *   - secondary_goal    （次要诉求，contract code；不可脱离 primary_goal 单独存在；可空；不能等于 primary_goal）
 *   - custom_goal_text  （其他想法补充，最多 200 字；可空；可独立存在）
 *
 * 不再使用：primary / secondary / custom_text 作为最终提交字段
 *
 * 冻结规则（V3.1 正式 §10）：
 *   1. 整页选填 → 全空时 skip = true，user_goal = null
 *   2. custom_goal_text 可独立存在 → 只填文字、不选诉求也合法（通过）
 *   3. primary_goal 必填当 secondary_goal 存在 → 反向：secondary 需要 primary，但 primary 不需要 secondary
 *   4. 选择 other 无需填文字 → other 与 custom_goal_text 独立
 *   5. custom_goal_text > 200 字 → 阻止（reason = custom_too_long）
 *   6. 主次诉求不能相同 → primary === secondary 时阻止（reason = primary_equals_secondary）
 *   7. 最多选择 2 项 → primary + secondary，不超出
 *   8. code 必须在合同内 → 防御性校验
 *
 * 后端尚未交付保存能力 → 调用方根据 ok 判断，本模块只负责判定 + 序列化。
 */

// 合同权威意图代码（V3.1 冻结 questionnaire-v3.0.1.json user_goal 配置，逐字一致；
// 后端尚未交付保存能力，本机暂存并如实标注）
export const INTENT_CODES = Object.freeze([
  { code: "sleep",               label: "帮我睡得安稳一点" },
  { code: "relaxation",          label: "让我放松、静下来" },
  { code: "emotion_regulation",  label: "帮我把情绪释放出来" },
  { code: "focus",               label: "让我更容易专注" },
  { code: "energy",              label: "帮我恢复点精力" },
  { code: "stress_relief",       label: "让我减轻点压力" },
  { code: "other",               label: "其他" },
])

export const MAX_CUSTOM_LEN = 200

const INTENT_SET = new Set(INTENT_CODES.map((it) => it.code))

/**
 * 净化 raw input：去首尾空白、null/undefined → 空串
 * 返回 { primary_goal, secondary_goal, custom_goal_text } 三个稳定字段
 */
export function normalizeIntentState(raw) {
  const p = raw && typeof raw.primary_goal === "string" ? raw.primary_goal.trim() : ""
  const s = raw && typeof raw.secondary_goal === "string" ? raw.secondary_goal.trim() : ""
  const c = raw && typeof raw.custom_goal_text === "string" ? raw.custom_goal_text.trim() : ""
  return {
    primary_goal: p || null,
    secondary_goal: s || null,
    custom_goal_text: c || null,
  }
}

/**
 * 校验 + 序列化合一函数：
 *   - skip = true  表示整页跳过（不进 submitHealingIntent）
 *   - submit       表示通过校验、可提交给后端的 payload
 *   - reason       表示阻止原因（reason code 字符串，供 UI 提示用）
 */
export function decideHealingIntent(rawState) {
  const norm = normalizeIntentState(rawState)
  const hasPrimary = !!norm.primary_goal
  const hasSecondary = !!norm.secondary_goal
  const customLen = (rawState && typeof rawState.custom_goal_text === "string")
    ? rawState.custom_goal_text.trim().length
    : 0

  // 规则 1：全空 → 跳过
  if (!hasPrimary && !hasSecondary && customLen === 0) {
    return { ok: true, skip: true, payload: null, reason: null }
  }

  // 自由文字长度优先校验；文字可独立存在，但不得超过冻结上限。
  if (customLen > MAX_CUSTOM_LEN) {
    return { ok: false, skip: false, payload: null, reason: "custom_too_long" }
  }

  // 次要诉求不能脱离主要诉求。仅填写 custom_goal_text 无需主要诉求。
  if (hasSecondary && !hasPrimary) {
    return { ok: false, skip: false, payload: null, reason: "secondary_requires_primary" }
  }

  // 防御性检查：存在的 code 均须是正式枚举；other 不要求自由文字。
  if (hasPrimary && !INTENT_SET.has(norm.primary_goal)) {
    return { ok: false, skip: false, payload: null, reason: "invalid_goal_code" }
  }
  if (hasSecondary && !INTENT_SET.has(norm.secondary_goal)) {
    return { ok: false, skip: false, payload: null, reason: "invalid_goal_code" }
  }

  // 主次诉求不能相同。
  if (hasPrimary && norm.secondary_goal === norm.primary_goal) {
    return { ok: false, skip: false, payload: null, reason: "primary_equals_secondary" }
  }

  return {
    ok: true,
    skip: false,
    payload: {
      primary_goal: norm.primary_goal,
      secondary_goal: norm.secondary_goal,
      custom_goal_text: norm.custom_goal_text,
    },
    reason: null,
  }
}

/**
 * 把 reason code 映射为人类可读的 toast 文案
 */
export const HEALING_INTENT_REASON_MESSAGE = Object.freeze({
  secondary_requires_primary: "需要先选择主要诉求",
  primary_equals_secondary: "主次诉求不能相同",
  invalid_goal_code: "选择的诉求不在正式列表中",
  custom_too_long: "补充内容不超过 200 字",
})

/**
 * 仅做序列化（不校验），用于已经校验过之后构造 payload 的场景
 */
export function serializeHealingIntent(rawState) {
  const norm = normalizeIntentState(rawState)
  return {
    primary_goal: norm.primary_goal,
    secondary_goal: norm.secondary_goal,
    custom_goal_text: norm.custom_goal_text,
  }
}