import QUESTIONNAIRE_MANIFEST from "./questionnaire-v3-generated.js"

/**
 * V3.1 疗愈诉求（可选）合同校验模块
 *
 * 权威来源：knowledge/v3/questionnaire-v3.0.1.json 的 user_goal 定义。
 *
 * 字段与 Read Model 合同权威字段一一对应：
 *   - primary_goal      （主要诉求，contract 7 code 之一：sleep / relaxation / ... / other）
 *   - secondary_goal    （次要诉求，contract code，可空；不可脱离 primary_goal 单独存在）
 *   - custom_goal_text  （可独立填写的选填补充，最多 200 字）
 *
 * 不再使用：primary / secondary / custom_text 作为最终提交字段
 *
 * 校验规则：
 *   1. 全空 → 视为整页跳过，直接返回 skip = true
 *   2. 自由文字可独立存在；选择 other 时也不强制填写文字
 *   3. 只有次要诉求、没有主要诉求 → 阻止（reason = primary_required）
 *   4. 主要/次要诉求不得重复，且都必须来自权威 code set
 *   5. 自由文字 > 200 字 → 阻止（reason = custom_too_long）
 *
 * 后端尚未交付保存能力 → 调用方根据 ok 判断，本模块只负责判定 + 序列化。
 */

// 合同权威意图代码（与 Read Model 一致；后端尚未交付保存能力，本机暂存）
export const INTENT_CODES = Object.freeze(
  QUESTIONNAIRE_MANIFEST.user_goal.options.map((item) => Object.freeze({ ...item })),
)

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
  const hasCustom = !!norm.custom_goal_text

  if (!hasPrimary && !hasSecondary && !hasCustom) {
    return { ok: true, skip: true, payload: null, reason: null }
  }
  if (hasSecondary && !hasPrimary) {
    return { ok: false, skip: false, payload: null, reason: "primary_required" }
  }
  if (hasPrimary && !INTENT_SET.has(norm.primary_goal)) {
    return { ok: false, skip: false, payload: null, reason: "invalid_goal" }
  }
  if (hasSecondary && !INTENT_SET.has(norm.secondary_goal)) {
    return { ok: false, skip: false, payload: null, reason: "invalid_goal" }
  }
  if (hasSecondary && norm.secondary_goal === norm.primary_goal) {
    return { ok: false, skip: false, payload: null, reason: "duplicate_goal" }
  }
  const customLength = norm.custom_goal_text ? norm.custom_goal_text.length : 0
  if (customLength > MAX_CUSTOM_LEN) {
    return { ok: false, skip: false, payload: null, reason: "custom_too_long" }
  }

  return { ok: true, skip: false, payload: norm, reason: null }
}

/** Reason codes are UI messages only; they do not redefine contract semantics. */
export const HEALING_INTENT_REASON_MESSAGE = Object.freeze({
  primary_required: "次要诉求需要先选择主要诉求",
  invalid_goal: "诉求选项无效",
  duplicate_goal: "主要诉求和次要诉求不能相同",
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
