const NONE_EXCLUSIVE = new Set(["q16_physical_signals", "q20_emergency"])

// 题型 → 渲染模式（canonical questionnaire → generic renderer 的单一映射来源）。
// 永远返回一个具体模式，绝不返回 null（null 会导致题目无选项的空白死锁）。
export function rendererModeFor(question) {
  const type = question && question.type
  const layout = question && question.ui && question.ui.layout
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