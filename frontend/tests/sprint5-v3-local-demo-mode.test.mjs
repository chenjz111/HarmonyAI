import assert from "node:assert/strict"
import test from "node:test"

let importSequence = 0

async function resolveRuntimeMode({
  hostname = "app.harmonyai.example",
  search = "",
  storedMode = null,
  environmentMode = null,
} = {}) {
  const previousEnvironmentMode = process.env.HARMONYAI_V3_MODE
  const previousLocation = globalThis.location
  const previousLocalStorage = globalThis.localStorage

  if (environmentMode) process.env.HARMONYAI_V3_MODE = environmentMode
  else delete process.env.HARMONYAI_V3_MODE

  globalThis.location = { hostname, search }
  globalThis.localStorage = {
    getItem(key) {
      return key === "HARMONYAI_V3_MODE" ? storedMode : null
    },
  }

  try {
    importSequence += 1
    const { apiV3 } = await import(`../common/api-v3.js?local-demo-case=${importSequence}`)
    return apiV3.MODE
  } finally {
    if (previousEnvironmentMode === undefined) delete process.env.HARMONYAI_V3_MODE
    else process.env.HARMONYAI_V3_MODE = previousEnvironmentMode

    if (previousLocation === undefined) delete globalThis.location
    else globalThis.location = previousLocation

    if (previousLocalStorage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = previousLocalStorage
  }
}

test("formal runtime defaults to real", async () => {
  assert.equal(await resolveRuntimeMode(), "real")
})

test("stale mock localStorage cannot contaminate a formal runtime", async () => {
  assert.equal(await resolveRuntimeMode({ storedMode: "mock" }), "real")
})

test("explicit local demo query can enter mock", async () => {
  assert.equal(await resolveRuntimeMode({
    hostname: "127.0.0.1",
    search: "?harmonyai_demo=1",
  }), "mock")
})

test("explicit development modes preserve real hybrid and mock semantics", async () => {
  for (const mode of ["real", "hybrid", "mock"]) {
    assert.equal(await resolveRuntimeMode({ environmentMode: mode }), mode)
  }
})
