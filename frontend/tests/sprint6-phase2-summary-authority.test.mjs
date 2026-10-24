/**
 * Sprint 6 Phase C — Summary Authority 前端 contract migration
 *
 * PR-006/PR-007/PR-022 replace the former user-facing retention controls:
 * users confirm or edit one summary; backend evidence remains provenance.
 *
 * 断言分两层：
 *   1. 运行时：api-v3.js 导出的纯函数按稳定身份构造 changes[]
 *   2. 静态：两个摘要页都只用稳定 id、不使用显示名或数组下标作为身份，
 *      且不含任何子串匹配 / 语义推断
 *
 * 运行方式与仓库其它前端测试一致：cd frontend && node --test tests/*.test.mjs
 */

import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

process.env.HARMONYAI_V3_MODE = "real"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")
const stripStyles = (source) => source.replace(/<style[\s\S]*?<\/style>/g, "")

const storage = new Map()
globalThis.uni = {
  getStorageSync(key) { return storage.get(key) ?? "" },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
}

const {
  EVIDENCE_DECISION_KEEP,
  EVIDENCE_DECISION_DROP,
  evidenceDecisionFor,
  buildEvidenceChanges,
} = await import("../common/api-v3.js?s6-phase2-summary-authority")

const documentSummary = read("pages/v3-summary/v3-summary.vue")
const questionnaireSummary = read("pages/v3-confirm/v3-confirm.vue")
const apiSource = read("common/api-v3.js")
const documentMarkup = stripStyles(documentSummary)
const questionnaireMarkup = stripStyles(questionnaireSummary)

function understandingItem(overrides = {}) {
  return {
    item_id: "fact_a",
    fact_id: "fact_a",
    fact_code: "sleep_unrefreshing",
    claim_code: "sleep_unrefreshing",
    display_name: "睡眠恢复不足",
    confirmation_status: "unconfirmed",
    direction: "supporting",
    source_refs: [{ source_type: "document", source_id: "doc_1" }],
    ...overrides,
  }
}

function assessmentItem(overrides = {}) {
  return {
    item_id: "fev_a",
    fact_evidence_id: "fev_a",
    claim_code: "low_energy",
    display_name: "精力不足",
    confirmation_status: "confirmed",
    direction: "supporting",
    source_refs: [{ source_type: "questionnaire", source_id: "qsub_1" }],
    ...overrides,
  }
}

// ---------------------------------------------------------------- 运行时：纯函数

test("两态默认值：只有后端 rejected 的条目默认“不采用”", () => {
  assert.equal(evidenceDecisionFor(assessmentItem()), EVIDENCE_DECISION_KEEP)
  assert.equal(
    evidenceDecisionFor(assessmentItem({ confirmation_status: "unconfirmed" })),
    EVIDENCE_DECISION_KEEP,
  )
  assert.equal(
    evidenceDecisionFor(assessmentItem({ confirmation_status: "rejected" })),
    EVIDENCE_DECISION_DROP,
  )
  assert.equal(evidenceDecisionFor(null), EVIDENCE_DECISION_KEEP)
})

test("changes[] 只用稳定 id，绝不使用显示名或数组下标", () => {
  const items = [assessmentItem(), assessmentItem({ item_id: "fev_b", fact_evidence_id: "fev_b", display_name: "腰膝酸软" })]
  const changes = buildEvidenceChanges(
    items,
    { fev_a: EVIDENCE_DECISION_DROP, fev_b: EVIDENCE_DECISION_KEEP },
    "fact_evidence",
  )
  assert.equal(changes.length, 1)
  assert.deepEqual(changes[0], {
    target_type: "fact_evidence",
    target_id: "fev_a",
    field: "confirmation_status",
    old_value: "confirmed",
    new_value: "rejected",
  })
  const serialized = JSON.stringify(changes)
  assert.ok(!serialized.includes("精力不足"), "不得把显示名当作身份提交")
  assert.ok(!serialized.includes("腰膝酸软"), "未变化的条目不得出现在 changes[]")
})

test("文本编辑本身不产生任何结构化改动（D3）", () => {
  const items = [assessmentItem(), assessmentItem({ item_id: "fev_c", fact_evidence_id: "fev_c" })]
  // 用户只改了叙述文字：决定映射保持与后端状态一致 → 不发送任何条目
  const decisions = items.reduce((acc, item) => {
    acc[item.item_id] = evidenceDecisionFor(item)
    return acc
  }, {})
  assert.deepEqual(buildEvidenceChanges(items, decisions, "fact_evidence"), [])
})

test("切换单一条目只改变该稳定 id（D1）", () => {
  const items = [assessmentItem(), assessmentItem({ item_id: "fev_b", fact_evidence_id: "fev_b" })]
  const decisions = { fev_a: EVIDENCE_DECISION_KEEP, fev_b: EVIDENCE_DECISION_DROP }
  const changes = buildEvidenceChanges(items, decisions, "fact_evidence")
  assert.equal(changes.length, 1)
  assert.equal(changes[0].target_id, "fev_b")
  assert.equal(changes[0].new_value, "rejected")
})

test("重复 claim 的不同来源保有各自的稳定身份", () => {
  const items = [
    assessmentItem({ item_id: "fev_q", fact_evidence_id: "fev_q", claim_code: "flank_discomfort" }),
    assessmentItem({
      item_id: "fev_d",
      fact_evidence_id: "fev_d",
      claim_code: "flank_discomfort",
      confirmation_status: "confirmed",
      source_refs: [{ source_type: "document", source_id: "doc_9" }],
    }),
  ]
  const changes = buildEvidenceChanges(
    items,
    { fev_q: EVIDENCE_DECISION_KEEP, fev_d: EVIDENCE_DECISION_DROP },
    "fact_evidence",
  )
  assert.equal(changes.length, 1)
  assert.equal(changes[0].target_id, "fev_d")
})

test("Understanding 路径提交 normalized_fact 目标", () => {
  const items = [understandingItem()]
  const changes = buildEvidenceChanges(
    items,
    { fact_a: EVIDENCE_DECISION_KEEP },
    "normalized_fact",
  )
  assert.equal(changes.length, 1)
  assert.equal(changes[0].target_type, "normalized_fact")
  assert.equal(changes[0].target_id, "fact_a")
  assert.equal(changes[0].old_value, "unconfirmed")
  assert.equal(changes[0].new_value, "confirmed")
})

test("没有稳定身份的遗留条目永远不会被提交", () => {
  const items = [{ item_id: null, display_name: "遗留条目", confirmation_status: "unconfirmed" }]
  assert.deepEqual(
    buildEvidenceChanges(items, { null: EVIDENCE_DECISION_DROP }, "fact_evidence"),
    [],
  )
})

// ---------------------------------------------------------------- api-v3 投影

test("两个 read model 投影都暴露结构化条目与稳定身份", () => {
  assert.match(apiSource, /evidence_items:\s*understandingEvidenceItems\(data\)/)
  assert.match(apiSource, /evidence_items:\s*assessmentEvidenceItems\(data\)/)
  assert.match(
    apiSource,
    /item_id:\s*fact\.fact_id[\s\S]{0,220}confirmation_status:\s*fact\.confirmation_status/,
    "Understanding 条目携带 fact_id + confirmation_status",
  )
  assert.match(
    apiSource,
    /item_id:\s*item\.fact_evidence_id[\s\S]{0,220}confirmation_status:\s*item\.confirmation_status/,
    "Assessment 条目携带 fact_evidence_id + confirmation_status",
  )
  assert.match(apiSource, /direction:\s*fact\.negated \? "contradicting" : "supporting"/, "方向来自后端 negated 字段")
  assert.match(apiSource, /direction:\s*item\.direction/, "方向直接取后端 direction")
})

test("前端不存在显示名子串匹配或否定解析", () => {
  for (const [name, source] of [["api-v3.js", apiSource], ["v3-summary.vue", documentSummary], ["v3-confirm.vue", questionnaireSummary]]) {
    assert.doesNotMatch(source, /display_name[^\n]{0,40}\.includes\(/, `${name} 不得用显示名做包含判断`)
    assert.doesNotMatch(source, /display_name[^\n]{0,40}\bin\b[^\n]{0,40}(summary|text|narrative)/, `${name} 不得用显示名做子串匹配`)
    assert.doesNotMatch(source, /\bnegation|negate\(|nlp|semantic/i, `${name} 不得引入否定解析 / NLU`)
  }
})

// ---------------------------------------------------------------- 页面静态契约

test("PR-006: 资料摘要页只提交摘要确认或全文编辑", () => {
  assert.doesNotMatch(documentMarkup, /保留|不采用|evidence-block|evidence-list/)
  assert.doesNotMatch(documentSummary, /buildEvidenceChanges|structuredChanges|setEvidence/)
  assert.match(documentSummary, /decision:\s*"confirm"[\s\S]{0,120}changes:\s*\[\]/)
  assert.match(documentSummary, /edited_summary_text:\s*text/)
})

test("PR-007: 评估确认页只提交摘要确认或全文编辑", () => {
  assert.doesNotMatch(questionnaireMarkup, /保留|不采用|summaryItems|summary-facts-list/)
  assert.doesNotMatch(questionnaireSummary, /buildEvidenceChanges|structuredChanges|setEvidence/)
  assert.match(questionnaireSummary, /decision:\s*"confirm"[\s\S]{0,120}changes:\s*\[\]/)
  assert.match(questionnaireSummary, /edited_summary_text:\s*editedSummaryText/)
})

test("PR-022: pages do not create a second user-facing evidence authority", () => {
  for (const markup of [documentMarkup, questionnaireMarkup]) {
    assert.doesNotMatch(markup, /evidence-item|evidence-choice|summary-fact/)
  }
})
