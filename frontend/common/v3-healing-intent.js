/**
 * V3.1 疗愈诉求（可选）合同校验模块
 *
 * 依据：frontend-read-model-contract-v3.md §10 + Issue #100 复审指令
 *
 * 字段与 Read Model 合同权威字段一一对应：
 *   - primary_goal      （主要诉求，contract 7 code 之一：sleep / relaxation / ... / other）
 *   - secondary_goal    （次要诉求，contract code，可空；不可脱离 primary_goal 单独存在）
 *   - custom_goal_text  （其他想法补充，1~200 字；primary_goal === "other" 时强制要求）
 *
 * 不再使用：primary / secondary / custom_text 作为最终提交字段
 *
 * 校验规则（复审指令）：
 *   1. 全空 → 视为整页跳过，直接返回 skip = true
 *   2. 只填文字、不选主要诉求 → 阻止（reason = primary_required）
 *   3. 只有次要诉求、没有主要诉求 → 阻止（reason = primary_required）
 *   4. primary_goal === "other" 但 custom_goal_text 为空 → 阻止（reason = other_needs_text）
 *   5. 自由文字 > 200 字 → 阻止（reason = custom_too_long）
 *
 * 后端尚未交付保存能力 → 调用方根据 ok 判断，本模块只负责判定 + 序列化。
 */

// 合同权威意图代码（与 Read Model 一致；后端尚未交付保存能力，本机暂存）
export const INTENT_CODES = Object.freeze([
  { code: "sleep",               label: "睡得更安稳" },
  { code: "relaxation",          label: "让身心放松" },
  { code: "emotion_regulation",  label: "调节情绪起伏" },
  { code: "focus",               label: "更专注一些" },
  { code: "energy",              label: "更有精神一些" },
  { code: "stress_relief",       label: "缓解压力" },
  { code: "other",               label: "其他诉求" },
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

  // 规则 2/3：没有主要诉求（不论是否有文字 / 次要诉求） → 阻止
  if (!hasPrimary) {
    return { ok: false, skip: false, payload: null, reason: "primary_required" }
  }

  // 规则 4：other 必填文字
  if (norm.primary_goal === "other" && customLen === 0) {
    return { ok: false, skip: false, payload: null, reason: "other_needs_text" }
  }

  // 规则 5：自由文字超长
  if (customLen > MAX_CUSTOM_LEN) {
    return { ok: false, skip: false, payload: null, reason: "custom_too_long" }
  }

  // 兜底：防御性检查意图代码在合同内（避免 UI 注入或脏数据）
  if (!INTENT_SET.has(norm.primary_goal)) {
    return { ok: false, skip: false, payload: null, reason: "primary_required" }
  }
  if (norm.secondary_goal && !INTENT_SET.has(norm.secondary_goal)) {
    return { ok: false, skip: false, payload: null, reason: "primary_required" }
  }
  // 兜底：secondary 不得等于 primary（pickSecondary 已拦截，这里仅防御）
  if (norm.secondary_goal === norm.primary_goal) {
    return { ok: false, skip: false, payload: null, reason: "primary_required" }
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
 * 复审指令 8：把 reason code 映射为人类可读的 toast 文案
 */
export const HEALING_INTENT_REASON_MESSAGE = Object.freeze({
  primary_required: "请先选择主要诉求",
  other_needs_text: "其他诉求需补充说明（1~200 字）",
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