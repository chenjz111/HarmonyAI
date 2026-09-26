export const MATERIAL_PHASES = Object.freeze({
  PICKING: "PICKING",
  UPLOADING: "UPLOADING",
  READING: "READING",
  EXTRACTING: "EXTRACTING",
  SUMMARIZING: "SUMMARIZING",
  SUMMARY_READY: "SUMMARY_READY",
  EDITING: "EDITING",
  FAILED: "FAILED",
})

export const MATERIAL_THINKING_LABELS = Object.freeze([
  "正在分析资料内容…",
  "提取关键信息…",
  "生成资料摘要…",
])

const THINKING_PHASES = Object.freeze([
  MATERIAL_PHASES.READING,
  MATERIAL_PHASES.EXTRACTING,
  MATERIAL_PHASES.SUMMARIZING,
])

const initialState = () => ({
  phase: MATERIAL_PHASES.PICKING,
  thinkingLabel: "",
  summaryText: "",
  revealedText: "",
  error: "",
})

export function createMaterialRecoveryFlow({
  schedule = (callback, delay) => setTimeout(callback, delay),
  cancelSchedule = timer => clearTimeout(timer),
  onChange = () => {},
  thinkingIntervalMs = 900,
  revealIntervalMs = 18,
} = {}) {
  let state = initialState()
  let timer = null
  let epoch = 0
  let disposed = false

  const snapshot = () => ({ ...state })

  const emit = () => {
    if (!disposed) onChange(snapshot())
  }

  const clearTimer = () => {
    epoch += 1
    if (timer !== null) cancelSchedule(timer)
    timer = null
  }

  const scheduleNext = (callback, delay) => {
    const token = epoch
    timer = schedule(() => {
      timer = null
      if (disposed || token !== epoch) return
      callback()
    }, delay)
  }

  const setState = patch => {
    state = { ...state, ...patch }
    emit()
  }

  const startThinkingCycle = index => {
    scheduleNext(() => {
      const nextIndex = (index + 1) % THINKING_PHASES.length
      setState({
        phase: THINKING_PHASES[nextIndex],
        thinkingLabel: MATERIAL_THINKING_LABELS[nextIndex],
      })
      startThinkingCycle(nextIndex)
    }, thinkingIntervalMs)
  }

  const reveal = characters => {
    const step = Math.max(1, Math.ceil(characters.length / 80))
    const advance = () => {
      const currentLength = Array.from(state.revealedText).length
      const nextLength = Math.min(characters.length, currentLength + step)
      const revealedText = characters.slice(0, nextLength).join("")
      if (nextLength >= characters.length) {
        setState({
          phase: MATERIAL_PHASES.SUMMARY_READY,
          thinkingLabel: "",
          revealedText: state.summaryText,
        })
        return
      }
      setState({ revealedText })
      scheduleNext(advance, revealIntervalMs)
    }
    scheduleNext(advance, revealIntervalMs)
  }

  return {
    getState: snapshot,

    beginUpload() {
      if (disposed || state.phase !== MATERIAL_PHASES.PICKING) return false
      clearTimer()
      setState({
        phase: MATERIAL_PHASES.UPLOADING,
        thinkingLabel: "",
        summaryText: "",
        revealedText: "",
        error: "",
      })
      return true
    },

    documentsReady() {
      if (disposed || state.phase !== MATERIAL_PHASES.UPLOADING) return false
      clearTimer()
      setState({
        phase: MATERIAL_PHASES.READING,
        thinkingLabel: MATERIAL_THINKING_LABELS[0],
      })
      startThinkingCycle(0)
      return true
    },

    summaryReady(text) {
      if (disposed || !THINKING_PHASES.includes(state.phase) || typeof text !== "string" || !text.length) {
        return false
      }
      clearTimer()
      setState({
        phase: MATERIAL_PHASES.SUMMARIZING,
        thinkingLabel: MATERIAL_THINKING_LABELS[2],
        summaryText: text,
        revealedText: "",
        error: "",
      })
      reveal(Array.from(text))
      return true
    },

    beginEdit() {
      if (disposed || state.phase !== MATERIAL_PHASES.SUMMARY_READY) return false
      setState({ phase: MATERIAL_PHASES.EDITING })
      return true
    },

    cancelEdit() {
      if (disposed || state.phase !== MATERIAL_PHASES.EDITING) return false
      setState({ phase: MATERIAL_PHASES.SUMMARY_READY })
      return true
    },

    fail(error) {
      if (disposed) return false
      clearTimer()
      setState({
        phase: MATERIAL_PHASES.FAILED,
        thinkingLabel: "",
        error: String(error || "处理失败，请重试"),
      })
      return true
    },

    retry() {
      if (disposed || state.phase !== MATERIAL_PHASES.FAILED) return false
      clearTimer()
      setState({
        phase: MATERIAL_PHASES.READING,
        thinkingLabel: MATERIAL_THINKING_LABELS[0],
        error: "",
      })
      startThinkingCycle(0)
      return true
    },

    reset() {
      if (disposed) return false
      clearTimer()
      state = initialState()
      emit()
      return true
    },

    dispose() {
      if (disposed) return false
      clearTimer()
      disposed = true
      return true
    },
  }
}
