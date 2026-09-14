/**
 * V3.1 有资料流程：前端 canonical DocumentSet 接线回归测试
 *
 * 修复目标（真机 422 DOCUMENT_SET_NOT_ACTIVE 的根因）：
 *   前端真实上传链只做 POST /api/v2/documents + replace_document（单文档），
 *   从未调用 POST /api/v3/sessions/{id}/document-sets，
 *   导致 session.active_document_set_id 一直为 NULL，understanding 被 gate 拒绝。
 *
 * 本测试锁定：
 *   1. 上传页在 1~3 份资料全部识别后，**只创建一次** DocumentSet（不逐份 replace）
 *   2. api-v3.js 真实链使用既有 canonical 端点与字段
 *      （document_ids / expected_input_revision / Idempotency-Key）
 *   3. understanding 请求携带 expected_input_revision（V3.1 契约必填）
 *      并按活动集合的完整有序列表提交 inputs
 *   4. mock/demo 模式下同一语义可用（active set + revision 增长）
 *   5. 1~3 份约束在 mock 侧同样生效
 */

import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

const apiSource = read("common/api-v3.js")
const materialPage = read("pages/v3-material/v3-material.vue")

let caseSequence = 0

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
  globalThis.localStorage = { getItem: () => null }

  caseSequence += 1
  const mod = await import(`../common/api-v3.js?document-set-seq=${caseSequence}`)
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

// ---------------------------------------------------------------- 上传页接线

test("上传页：1~3 份全部识别后只创建一次 DocumentSet", () => {
  const uploadCall = materialPage.indexOf("apiV3.uploadDocument(f.path, f.name)")
  const pushId = materialPage.indexOf("documentIds.push(doc.document_id)")
  const createSet = materialPage.indexOf("apiV3.createDocumentSet(documentIds)")

  assert.notEqual(uploadCall, -1, "仍逐份上传（保持 1~3 份与顺序）")
  assert.notEqual(pushId, -1, "必须收集本次上传的 document_id")
  assert.notEqual(createSet, -1, "必须调用 canonical createDocumentSet")
  assert.ok(uploadCall < pushId, "先上传再收集 id")
  assert.ok(pushId < createSet, "set 必须在全部上传完成后创建")
  assert.equal(
    materialPage.split("apiV3.createDocumentSet(").length - 1,
    1,
    "整页只允许创建一次 set（不得逐份 replace）",
  )
  // 失败分流保持：OCR 失败 → ?type=ocr；网络/服务失败 → ?type=network
  assert.match(materialPage, /v3-material-error\/v3-material-error\?type=ocr/)
  assert.match(materialPage, /v3-material-error\/v3-material-error\?type=network/)
  assert.ok(
    materialPage.indexOf("type=network", createSet) > createSet,
    "set 创建失败必须走 network 异常分流",
  )
})

// ---------------------------------------------------------------- 真实链接线

test("真实链：uploadDocument 不再逐份 replace_document", () => {
  assert.equal(
    apiSource.includes("await realInputApi.replaceDocument(up.document_id)"),
    false,
    "上传步骤不得再调用 replace_document 作为资料激活",
  )
  assert.ok(
    apiSource.includes("V3.1 有资料流程：1~3 份资料全部上传/识别完成后"),
    "上传方法需说明 canonical 激活方式",
  )
})

test("真实链：createDocumentSet 使用既有 canonical 端点与字段", () => {
  assert.ok(
    apiSource.includes('"/api/v3/sessions/" + encodeURIComponent(state.session_id) + "/document-sets"'),
    "必须调用既有 document-sets 端点",
  )
  assert.ok(apiSource.includes("document_ids: ids"), "必须提交 document_ids")
  assert.ok(
    apiSource.includes("expected_input_revision: state.input_revision || 1"),
    "必须带 expected_input_revision（revision CAS）",
  )
  assert.ok(apiSource.includes('"Idempotency-Key": idempotencyKey()'), "必须带幂等键")
  assert.ok(apiSource.includes("active_document_set_id: data.document_set_id"), "需记录 active set")
  assert.ok(apiSource.includes("active_document_ids: activeIds"), "需记录有序资料列表")
  // 不允许前端自己判定 relevance / 伪造资料可用性（只看代码行，注释允许说明职责归属）
  const codeOnly = apiSource
    .split("\n")
    .filter((line) => {
      const trimmed = line.trim()
      return !trimmed.startsWith("//") && !trimmed.startsWith("*") && !trimmed.startsWith("/*")
    })
    .join("\n")
  for (const forbidden of ["relevance", "Relevance", "DOCUMENT_RELEVANCE"]) {
    assert.equal(codeOnly.includes(forbidden), false, `前端代码不得参与 relevance 判定: ${forbidden}`)
  }
})

test("真实链：understanding 带 expected_input_revision 且提交全部活动资料", () => {
  assert.ok(apiSource.includes("active_document_ids"), "需读取活动集合的有序列表")
  assert.ok(
    apiSource.includes("expected_input_revision: state.input_revision || 1"),
    "V3.1 契约要求 understanding 创建携带 expected_input_revision",
  )
  assert.ok(apiSource.includes("inputs: activeIds.map((documentId) => ({"), "需按集合列表逐个提交 inputs")
  assert.ok(apiSource.includes("text_ref: documentId"), "text_ref 必须为 document_id（gate 按序校验）")
})

test("门面层：createDocumentSet 在 real/mock 两模式都可分发", () => {
  assert.ok(
    apiSource.includes("realInputApi.createDocumentSet(documentIds)"),
    "real 模式需分发到真实实现",
  )
  assert.ok(
    apiSource.includes("mockApi.createDocumentSet(documentIds)"),
    "mock/demo 模式需分发到 mock 实现",
  )
})

// ---------------------------------------------------------------- mock 语义

test("mock：三份资料创建同一个 set，active 为首份且 revision 增长一次", async () => {
  await withApi({ environmentMode: "mock" }, async (apiV3) => {
    await apiV3.guestAuth()
    await apiV3.createSession()
    const before = (await apiV3.getSession()).input_revision
    const d1 = await apiV3.uploadDocument(null, "a.jpg")
    const d2 = await apiV3.uploadDocument(null, "b.jpg")
    const d3 = await apiV3.uploadDocument(null, "c.jpg")

    const created = await apiV3.createDocumentSet([
      d1.document_id,
      d2.document_id,
      d3.document_id,
    ])

    assert.deepEqual(created.document_ids, [
      d1.document_id,
      d2.document_id,
      d3.document_id,
    ])
    const session = await apiV3.getSession()
    assert.equal(session.active_document_set_id, created.document_set_id)
    assert.equal(session.active_document_id, d1.document_id, "active document 为首份")
    assert.equal(session.input_revision, before + 4, "3 次上传 + 1 次 set 各增长一次")
    assert.equal(created.input_revision, session.input_revision)
  })
})

test("mock：set 创建后仍可生成聚合摘要（source_document_ids 保持三份顺序）", async () => {
  await withApi({ environmentMode: "mock" }, async (apiV3) => {
    await apiV3.guestAuth()
    await apiV3.createSession()
    const d1 = await apiV3.uploadDocument(null, "a.jpg")
    const d2 = await apiV3.uploadDocument(null, "b.jpg")
    const d3 = await apiV3.uploadDocument(null, "c.jpg")
    await apiV3.createDocumentSet([d1.document_id, d2.document_id, d3.document_id])

    const summary = await apiV3.getCaseSummary()

    assert.deepEqual(summary.source_document_ids, [
      d1.document_id,
      d2.document_id,
      d3.document_id,
    ])
  })
})

test("mock：set 数量约束 1~3 份", async () => {
  await withApi({ environmentMode: "mock" }, async (apiV3) => {
    await apiV3.guestAuth()
    await apiV3.createSession()
    const doc = await apiV3.uploadDocument(null, "a.jpg")

    await assert.rejects(
      () => apiV3.createDocumentSet([]),
      (error) => error.code === "DOCUMENT_SET_SIZE",
      "空集合必须拒绝",
    )
    await assert.rejects(
      () => apiV3.createDocumentSet([doc.document_id, "d2", "d3", "d4"]),
      (error) => error.code === "DOCUMENT_SET_SIZE",
      "超过 3 份必须拒绝",
    )
  })
})
