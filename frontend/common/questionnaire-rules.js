const NONE_EXCLUSIVE = new Set(["q16_physical_signals", "q20_emergency"])

// 题型 → 渲染模式（canonical questionnaire → generic renderer 的单一映射来源）。
// 永远返回一个具体模式，绝不返回 null（null 会导致题目无选项的空白死锁）。
export function rendererModeFor(question) {
  const type = question && question.type
  const layout = question && question.ui && question.ui.layout
  if (question && question.severity_scale) return "directional"
  if (type === "visual_single") return "visual"
  if (type === "multi_choice") return "multi"
  if (layout === "button-grid") return "button-grid"
  if (layout === "button-list") return "button-list"
  // 其余单选类型（frequency_0_4 / single_choice / duration_choice / scale_0_10）统一渲染为按钮行。
  return "button-row"
}

export function applyExclusiveChoice(questionId, selected, value) {
  const current = Array.isArray(selected) ? [...selected] : []
  if (!NONE_EXCLUSIVE.has(questionId)) {
    return current.includes(value) ? current.filter((item) => item !== value) : [...current, value]
  }
  if (current.includes(value)) return current.filter((item) => item !== value)
  if (value === "none") return ["none"]
  return [...current.filter((item) => item !== "none"), value]
}

export function safetyFlowForAnswer(questionId, answer) {
  if (questionId === "q19_self_harm" && answer !== "never") return "SAFETY_SELF_HARM"
  if (questionId === "q20_emergency" && Array.isArray(answer) && answer.some((value) => value !== "none")) {
    return "SAFETY_EMERGENCY_PHYSICAL"
  }
  return null
}

export function severityScaleFor(question) {
  const scale = question && question.severity_scale
  if (!scale) return []
  const min = Number.isInteger(scale.min) ? scale.min : 1
  const max = Number.isInteger(scale.max) ? scale.max : 4
  const labels = Array.isArray(scale.labels) ? scale.labels : []
  const steps = []
  for (let value = min; value <= max; value++) {
    steps.push({ value, label: labels[value - min] ?? String(value) })
  }
  return steps
}

export function isDirectionalComplete(answer) {
  if (!answer || typeof answer !== "object") return false
  const { direction, severity } = answer
  if (direction === "none") return severity === 0
  if (direction === "decrease" || direction === "increase") {
    return Number.isInteger(severity) && severity >= 1 && severity <= 4
  }
  return false
}

export function serializeDirectional(direction, severity) {
  if (direction === "none") return { direction: "none", severity: 0 }
  return { direction, severity }
}

export function serializeAnswer(question, raw) {
  const type = question && question.type
  if (type === "visual_single" && raw && typeof raw === "object") {
    return { value: raw.value, score: raw.score }
  }
  if (question && question.severity_scale && raw && typeof raw === "object") {
    return { value: serializeDirectional(raw.direction, raw.severity) }
  }
  return { value: raw }
}

export function isAnswerComplete(question, answer) {
  if (answer === undefined || answer === null) return false
  if (Array.isArray(answer)) return answer.length > 0
  if (question && question.severity_scale) return isDirectionalComplete(answer)
  return true
}
