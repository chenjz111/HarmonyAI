const NONE_EXCLUSIVE = new Set(["q16_physical_signals", "q20_emergency"])

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