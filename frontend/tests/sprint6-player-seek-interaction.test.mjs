import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const playerSource = readFileSync(resolve(root, "pages/v3-player/v3-player.vue"), "utf8")
const playerScript = playerSource.match(/<script>([\s\S]*?)<\/script>/)?.[1] || ""

async function seekHelpers() {
  return import("../common/player-seek.js")
}

function loadPlayerComponent(seekRatioFromEvent) {
  const executable = playerScript
    .replace(/import[\s\S]*?from\s+["'][^"']+["']\s*/g, "")
    .replace("export default", "return")

  return new Function(
    "apiV3",
    "createPlayerController",
    "buildMusicPresentation",
    "presentProgress",
    "seekRatioFromEvent",
    executable,
  )(
    {},
    () => { throw new Error("seek interaction must not create a controller") },
    () => ({}),
    () => ({}),
    seekRatioFromEvent,
  )
}

function createPlayerVm(component, rect = { left: 20, width: 200 }) {
  const seeks = []
  const calls = { selectorQueries: 0, downloads: 0, generations: 0 }
  const previousUni = globalThis.uni
  globalThis.uni = {
    createSelectorQuery() {
      calls.selectorQueries += 1
      return {
        in() { return this },
        select(selector) {
          assert.equal(selector, "#player-progress-track")
          return this
        },
        boundingClientRect(callback) {
          callback(rect)
          return this
        },
        exec() {},
      }
    },
  }
  const vm = component.data()
  for (const [name, method] of Object.entries(component.methods)) vm[name] = method.bind(vm)
  vm.playerState = { playing: true, currentTime: 20, duration: 100, error: null }
  vm.playerController = { seek: ratio => { seeks.push(ratio); return true } }
  vm.analysisExpanded = true
  return {
    vm,
    seeks,
    calls,
    restore() { globalThis.uni = previousUni },
  }
}

test("coordinate helper maps start, middle, end and clamps out-of-bounds positions", async () => {
  const { coordinateToRatio } = await seekHelpers()
  const rect = { left: 20, width: 200 }
  assert.equal(coordinateToRatio(20, rect), 0)
  assert.equal(coordinateToRatio(120, rect), 0.5)
  assert.equal(coordinateToRatio(220, rect), 1)
  assert.equal(coordinateToRatio(-50, rect), 0)
  assert.equal(coordinateToRatio(999, rect), 1)
  assert.equal(coordinateToRatio(100, { left: 20, width: 0 }), null)
  assert.equal(coordinateToRatio(Number.NaN, rect), null)
})

test("event helper supports uni-app tap and Android touch coordinates", async () => {
  const { seekRatioFromEvent } = await seekHelpers()
  const rect = { left: 10, width: 100 }
  assert.equal(seekRatioFromEvent({ detail: { x: 60 } }, rect), 0.5)
  assert.equal(seekRatioFromEvent({ touches: [{ clientX: 85 }] }, rect), 0.75)
  assert.equal(seekRatioFromEvent({ changedTouches: [{ clientX: 110 }] }, rect), 1)
  assert.equal(seekRatioFromEvent({}, rect), null)
})

test("rendered progress tap and drag delegate ratios to the existing controller only", async () => {
  const { seekRatioFromEvent } = await seekHelpers()
  const component = loadPlayerComponent(seekRatioFromEvent)
  const harness = createPlayerVm(component)
  try {
    harness.vm.handleProgressTap({ detail: { x: 20 } })
    harness.vm.handleProgressTap({ detail: { x: 120 } })
    harness.vm.handleProgressTap({ detail: { x: 220 } })
    harness.vm.handleSeekStart()
    harness.vm.handleSeekMove({ touches: [{ clientX: 170 }] })
    harness.vm.handleSeekEnd({ changedTouches: [{ clientX: 240 }] })

    assert.deepEqual(harness.seeks, [0, 0.5, 1, 0.75, 1])
    assert.equal(harness.vm.analysisExpanded, true)
    assert.equal(harness.calls.downloads, 0)
    assert.equal(harness.calls.generations, 0)
    assert.match(playerSource, /@tap="handleProgressTap"/)
    assert.match(playerSource, /@touchstart="handleSeekStart"/)
    assert.match(playerSource, /@touchmove\.stop\.prevent="handleSeekMove"/)
    assert.match(playerSource, /@touchend="handleSeekEnd"/)
  } finally {
    harness.restore()
  }
})

test("a tap touch sequence seeks once instead of seeking again on touchend", async () => {
  const { seekRatioFromEvent } = await seekHelpers()
  const component = loadPlayerComponent(seekRatioFromEvent)
  const harness = createPlayerVm(component)
  try {
    harness.vm.handleSeekStart()
    harness.vm.handleSeekEnd({ changedTouches: [{ clientX: 120 }] })
    harness.vm.handleProgressTap({ detail: { x: 120 } })

    assert.deepEqual(harness.seeks, [0.5])
    assert.equal(harness.vm.seeking, false)
  } finally {
    harness.restore()
  }
})

test("invalid track width or missing measured duration remains non-seekable", async () => {
  const { seekRatioFromEvent } = await seekHelpers()
  const component = loadPlayerComponent(seekRatioFromEvent)

  const invalidWidth = createPlayerVm(component, { left: 20, width: 0 })
  try {
    invalidWidth.vm.handleProgressTap({ detail: { x: 120 } })
    assert.deepEqual(invalidWidth.seeks, [])
  } finally {
    invalidWidth.restore()
  }

  const missingDuration = createPlayerVm(component)
  try {
    missingDuration.vm.playerState.duration = 0
    missingDuration.vm.handleProgressTap({ detail: { x: 120 } })
    missingDuration.vm.handleSeekMove({ touches: [{ clientX: 170 }] })
    assert.deepEqual(missingDuration.seeks, [])
    assert.equal(missingDuration.calls.selectorQueries, 0)
  } finally {
    missingDuration.restore()
  }
})
