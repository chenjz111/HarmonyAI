/**
 * Sprint 5 V3.1 P1 修复 + 多资料回归（Issue #100 复审修订）
 *
 * 1. 模式门控严格隔离（按 PR #94 思路参考）
 *    - 正式运行默认 real，陈旧 localStorage.Mock 配置绝不能污染正式域名
 *    - mock/hybrid 仅由以下三种显式入口触发：
 *      a) 构建环境变量 VITE_HARMONYAI_V3_MODE / HARMONYAI_V3_MODE（Vite 注入）
 *      b) Node 测试进程环境变量 process.env.HARMONYAI_V3_MODE
 *      c) H5 本机视觉演示：localhost/127.0.0.1 + ?harmonyai_demo=1
 *
 * 2. 多资料 mock 数组（与蔡子鑫对齐前的前端演示形态）
 *    - 真实后端未交付 DocumentSet / owner-aware multi-document upload，
 *      所以前端按"独立 document_id + 上传顺序保留"展示 1~3 份资料的有序聚合
 *    - mock uploadDocument 多次调用必须累积到 MOCK.documents[]，**不允许互相覆盖**
 *    - 真实模式失败时如实抛错，不模拟成功；mock getCaseSummary 在 ≥1 份 ready
 *      时返回聚合摘要（含 source_document_ids[]，保留上传顺序）
 *
 * 测试要点：每次模式切换都必须同步设置 process.env 之后立刻 import 新模块实例（带
 * ?seq=N query），并在使用过程中保持 process.env 处于期望值；用 try / finally 还原。
 */
import assert from "node:assert/strict"
import test from "node:test"

let caseSequence = 0

// 在指定环境下获取 api-v3；同步设置 process.env / location / localStorage，
// 然后导入一个全新模块实例，闭包内使用，最后还原。注意一定要保持 process.env 处于
// 期望值——再次 import 新模块实例时，该实例顶层 resolveMode() 会再次读 process.env。
async function withApi(env, runner) {
  const previousEnv = process.env.HARMONYAI_V3_MODE
  const previousLocation = globalThis.location
  const previousLocalStorage = globalThis.localStorage

  if (env.environmentMode) process.env.HARMONYAI_V3_MODE = env.environmentMode
  else delete process.env.HARMONYAI_V3_MODE

  if (env.hostname !== undefined) {
    globalThis.location = { hostname: env.hostname, search: env.search || "" }
  } else {
    delete globalThis.location
  }
  globalThis.localStorage = {
    getItem(key) {
      return key === "HARMONYAI_V3_MODE" ? env.storedMode || null : null
    },
  }

  caseSequence += 1
  const mod = await import(`../common/api-v3.js?gate-seq=${caseSequence}`)
  try {
    await runner(mod.apiV3)
  } finally {
    if (previousEnv === undefined) delete process.env.HARMONYAI_V3_MODE
    else process.env.HARMONYAI_V3_MODE = previousEnv

    if (previousLocation === undefined) delete globalThis.location
    else globalThis.location = previousLocation

    if (previousLocalStorage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = previousLocalStorage
  }
}

// ===== 模式门控 =====

test("formal runtime defaults to real, ignoring stale localStorage mock config", async () => {
  await withApi({ hostname: "app.harmonyai.example", storedMode: "mock" }, async (apiV3) => {
    assert.equal(apiV3.MODE, "real", "formal host with stale storage must still be real")
  })
  await withApi({ hostname: "www.harmonyai.example", storedMode: "hybrid" }, async (apiV3) => {
    assert.equal(apiV3.MODE, "real", "www host with stale storage must still be real")
  })
})

test("explicit ?harmonyai_demo=1 on localhost enters mock without env override", async () => {
  await withApi({ hostname: "127.0.0.1", search: "?harmonyai_demo=1" }, async (apiV3) => {
    assert.equal(apiV3.MODE, "mock")
  })
  await withApi({ hostname: "localhost", search: "?harmonyai_demo=1" }, async (apiV3) => {
    assert.equal(apiV3.MODE, "mock")
  })
})

test("?harmonyai_demo=1 only takes effect on explicit localhost/127.0.0.1", async () => {
  await withApi({ hostname: "app.harmonyai.example", search: "?harmonyai_demo=1" }, async (apiV3) => {
    assert.equal(apiV3.MODE, "real", "demo query on formal host must not escalate")
  })
})

test("explicit process.env.HARMONYAI_V3_MODE still drives mock/hybrid/real", async () => {
  for (const mode of ["real", "hybrid", "mock"]) {
    await withApi({ environmentMode: mode }, async (apiV3) => {
      assert.equal(apiV3.MODE, mode)
    })
  }
})

test("formal runtime exposes INPUT_SIMULATED=false and AGENT_SIMULATED=false", async () => {
  // 正式域名不会为语音转写 / Agent 段提供 mock 数据，确保不污染生产行为
  await withApi({ hostname: "app.harmonyai.example" }, async (apiV3) => {
    assert.equal(apiV3.INPUT_SIMULATED, false, "real runtime must not fabricate transcript-like data")
    assert.equal(apiV3.AGENT_SIMULATED, false, "real runtime must not fabricate agent data")
  })
})

// ===== 多资料 mock 数组不互相覆盖（蔡子鑫 DocumentSet/API 对齐前的演示形态） =====

test("mock uploadDocument keeps all 1-3 documents in order without overwriting", async () => {
  await withApi({ environmentMode: "mock" }, async (apiV3) => {
    await apiV3.guestAuth()
    await apiV3.createSession()
    const doc1 = await apiV3.uploadDocument(null, "report-2026-09-A.jpg")
    const doc2 = await apiV3.uploadDocument(null, "report-2026-09-B.jpg")
    const doc3 = await apiV3.uploadDocument(null, "report-2026-09-C.jpg")
    // 三份 document 必须是互不相同的 id
    assert.notEqual(doc1.document_id, doc2.document_id, "mock must keep doc1 distinct from doc2")
    assert.notEqual(doc2.document_id, doc3.document_id, "mock must keep doc2 distinct from doc3")
    assert.notEqual(doc1.document_id, doc3.document_id, "mock must keep doc1 distinct from doc3")
    // 当前会话的活跃资料 = 最后一份
    const session = await apiV3.getSession()
    assert.equal(session.active_document_id, doc3.document_id, "active document must be the latest uploaded")
    // mock 聚合摘要必须包含 3 份 source_document_ids 且按上传顺序保留
    const summary = await apiV3.getCaseSummary()
    assert.ok(Array.isArray(summary.source_document_ids), "summary must expose ordered source ids")
    assert.equal(summary.source_document_ids.length, 3)
    assert.equal(summary.source_document_ids[0], doc1.document_id, "first uploaded must remain first")
    assert.equal(summary.source_document_ids[2], doc3.document_id, "latest uploaded must remain last")
  })
})

test("mock uploadDocument does not silently merge into a single record", async () => {
  await withApi({ environmentMode: "mock" }, async (apiV3) => {
    await apiV3.guestAuth()
    await apiV3.createSession()
    const d1 = await apiV3.uploadDocument(null, "first.jpg")
    const d2 = await apiV3.uploadDocument(null, "second.jpg")
    // uploadDocument 每次必须返回新 document_id，而不是返回最后一次更新的旧值
    assert.notEqual(d1.document_id, d2.document_id)
  })
})

test("mock getCaseSummary still fails honestly when no document is ready", async () => {
  // 没有上传任何资料时，mock 也必须如实报错，绝不伪造成功
  await withApi({ environmentMode: "mock" }, async (apiV3) => {
    await apiV3.guestAuth()
    await apiV3.createSession()
    await assert.rejects(
      () => apiV3.getCaseSummary(),
      (e) => e.code === "SOURCE_NOT_READY",
      "must surface SOURCE_NOT_READY, never fabricate a summary",
    )
  })
})
