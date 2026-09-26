import assert from "node:assert/strict"
import test from "node:test"

import {
  MATERIAL_PHASES,
  MATERIAL_THINKING_LABELS,
  createMaterialRecoveryFlow,
} from "../common/material-recovery-flow.js"

function createFakeScheduler() {
  let nextId = 1
  const jobs = new Map()
  return {
    schedule(callback) {
      const id = nextId++
      jobs.set(id, callback)
      return id
    },
    cancel(id) {
      jobs.delete(id)
    },
    runNext() {
      const entry = jobs.entries().next().value
      if (!entry) return false
      const [id, callback] = entry
      jobs.delete(id)
      callback()
      return true
    },
    runAll(limit = 500) {
      let count = 0
      while (jobs.size && count < limit) {
        this.runNext()
        count += 1
      }
      assert.ok(count < limit, "scheduled work must settle")
    },
    get pending() {
      return jobs.size
    },
  }
}

test("material flow exposes only the approved presentation phases and honest labels", () => {
  assert.deepEqual(Object.values(MATERIAL_PHASES), [
    "PICKING",
    "UPLOADING",
    "READING",
    "EXTRACTING",
    "SUMMARIZING",
    "SUMMARY_READY",
    "EDITING",
    "FAILED",
  ])
  assert.deepEqual(MATERIAL_THINKING_LABELS, [
    "正在分析资料内容…",
    "提取关键信息…",
    "生成资料摘要…",
  ])
  for (const label of MATERIAL_THINKING_LABELS) {
    assert.doesNotMatch(label, /\d+%|provider|Agent|RAG/i)
  }
})

test("legal transitions cycle indeterminate thinking stages and suppress duplicate begin", () => {
  const clock = createFakeScheduler()
  const flow = createMaterialRecoveryFlow({ schedule: clock.schedule, cancelSchedule: clock.cancel })

  assert.equal(flow.getState().phase, MATERIAL_PHASES.PICKING)
  assert.equal(flow.beginUpload(), true)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.UPLOADING)
  assert.equal(flow.beginUpload(), false, "rapid duplicate begin must be ignored")
  assert.equal(flow.documentsReady(), true)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.READING)

  clock.runNext()
  assert.equal(flow.getState().phase, MATERIAL_PHASES.EXTRACTING)
  clock.runNext()
  assert.equal(flow.getState().phase, MATERIAL_PHASES.SUMMARIZING)
  assert.equal(flow.beginEdit(), false, "editing is illegal before a summary is ready")
})

test("progressive reveal completes with the exact immutable backend summary", () => {
  const clock = createFakeScheduler()
  const flow = createMaterialRecoveryFlow({ schedule: clock.schedule, cancelSchedule: clock.cancel })
  const backendText = "近一个月乏力，偶有心悸。\n睡眠欠佳，夜间易醒。"

  flow.beginUpload()
  flow.documentsReady()
  assert.equal(flow.summaryReady(backendText), true)
  assert.equal(flow.getState().summaryText, backendText)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.SUMMARIZING)
  assert.notEqual(flow.getState().revealedText, backendText)

  clock.runAll()
  assert.equal(flow.getState().phase, MATERIAL_PHASES.SUMMARY_READY)
  assert.equal(flow.getState().revealedText, backendText)
  assert.equal(flow.getState().summaryText, backendText)
})

test("edit, cancel, reset and failure recovery preserve legal state", () => {
  const clock = createFakeScheduler()
  const flow = createMaterialRecoveryFlow({ schedule: clock.schedule, cancelSchedule: clock.cancel })

  assert.equal(flow.summaryReady("illegal"), false)
  flow.beginUpload()
  flow.documentsReady()
  flow.summaryReady("真实摘要")
  clock.runAll()
  assert.equal(flow.beginEdit(), true)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.EDITING)
  assert.equal(flow.cancelEdit(), true)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.SUMMARY_READY)

  assert.equal(flow.fail("网络异常"), true)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.FAILED)
  assert.equal(flow.getState().error, "网络异常")
  assert.equal(flow.retry(), true)
  assert.equal(flow.getState().phase, MATERIAL_PHASES.READING)
  assert.equal(flow.getState().error, "")
  assert.equal(clock.pending, 1)
  flow.fail("仍然失败")
  flow.reset()
  assert.deepEqual(flow.getState(), {
    phase: MATERIAL_PHASES.PICKING,
    thinkingLabel: "",
    summaryText: "",
    revealedText: "",
    error: "",
  })
  assert.equal(clock.pending, 0)
})

test("reset and dispose cancel reveal/thinking timers and disposed callbacks cannot mutate state", () => {
  const clock = createFakeScheduler()
  const changes = []
  const flow = createMaterialRecoveryFlow({
    schedule: clock.schedule,
    cancelSchedule: clock.cancel,
    onChange: state => changes.push(state),
  })

  flow.beginUpload()
  flow.documentsReady()
  assert.equal(clock.pending, 1)
  flow.reset()
  assert.equal(clock.pending, 0)

  flow.beginUpload()
  flow.documentsReady()
  flow.summaryReady("不会在卸载后继续揭示")
  assert.equal(clock.pending, 1)
  const beforeDispose = changes.length
  flow.dispose()
  assert.equal(clock.pending, 0)
  clock.runAll()
  assert.equal(changes.length, beforeDispose)
  assert.equal(flow.beginUpload(), false)
})
