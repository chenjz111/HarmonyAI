import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import test from "node:test"

const readFrontend = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8")
const readRepo = path => readFileSync(new URL(`../../${path}`, import.meta.url), "utf8")
const readRepoBytes = path => readFileSync(new URL(`../../${path}`, import.meta.url))

const requirementIds = text => [...new Set(text.match(/PR-\d{3}/g) || [])].sort()

test("Phase A contract and matrix expose the same PR-001 through PR-031 identity set", () => {
  const contract = readRepo("docs/product/sprint6-product-recovery-contract.md")
  const matrix = readRepo("docs/sprint6/product-recovery-requirements-matrix.md")
  const expected = Array.from({ length: 31 }, (_, index) => `PR-${String(index + 1).padStart(3, "0")}`)
  const matrixRows = matrix.split(/\r?\n/).filter(line => /^\| PR-\d{3} \|/.test(line))

  assert.deepEqual(requirementIds(contract), expected)
  assert.deepEqual(requirementIds(matrix), expected)
  assert.deepEqual(matrixRows.map(line => line.split("|")[1].trim()), expected)
  assert.ok(matrixRows.every(line => {
    const cells = line.split("|").slice(1, -1).map(cell => cell.trim())
    return cells.length === 10 && cells[7] && cells[8] && cells[9] === "YES"
  }), "every requirement row must include automated, manual, and merge-blocking entries")
})

test("PR-001 keeps exactly the two Owner entries and Home/My primary tabs", () => {
  const entry = readFrontend("pages/entry/entry.vue")
  const pages = JSON.parse(readFrontend("pages.json"))

  assert.match(entry, /我有就诊资料/)
  assert.match(entry, /我没有就诊资料/)
  assert.match(entry, /上传资料/)
  assert.match(entry, /填写问卷/)
  assert.deepEqual(
    pages.tabBar.list.map(item => ({ pagePath: item.pagePath, text: item.text })),
    [
      { pagePath: "pages/entry/entry", text: "首页" },
      { pagePath: "pages/v3-profile/v3-profile", text: "我的" },
    ],
  )
})

test("PR-008 canonical questionnaire remains Q1-Q10, required, five pages of two", () => {
  const questionnaire = JSON.parse(readRepo("knowledge/v3/questionnaire-v3.0.1.json"))
  const page = readFrontend("pages/v3-questionnaire/v3-questionnaire.vue")

  assert.equal(questionnaire.question_count, 10)
  assert.equal(questionnaire.questions.length, 10)
  assert.deepEqual(questionnaire.questions.map(item => item.question_id),
    Array.from({ length: 10 }, (_, index) => `q${String(index + 1).padStart(2, "0")}`))
  assert.ok(questionnaire.questions.every(item => item.required === true))
  assert.match(page, /const\s+PAGE_SIZE\s*=\s*2/)
})

test("PR-019 feedback keeps Q1 required, Q2-Q5 optional, skip, and approved Q4", () => {
  const feedback = readFrontend("pages/v3-feedback/v3-feedback.vue")

  assert.match(feedback, /Q1\s*\/\s*post_state\s*必填/)
  assert.match(feedback, /Q2–Q5\s*选填/)
  assert.match(feedback, /暂时跳过/)
  for (const label of ["节奏再慢一点", "氛围再安静一点", "自然声音更多一点", "旋律更明显一点"]) {
    assert.match(feedback, new RegExp(label))
  }
})

test("PR-023 and PR-024 retain presentation/session/controller authority boundaries", () => {
  const basis = readFrontend("pages/v3-basis/v3-basis.vue")
  const player = readFrontend("pages/v3-player/v3-player.vue")
  const toneTheme = readFrontend("common/v31-tone-theme.js")

  assert.match(basis, /createMusicGenerationSession/)
  assert.match(basis, /buildAnalysisViewModel/)
  assert.doesNotMatch(basis, /v31-tone-theme/)
  assert.match(player, /createPlayerController/)
  assert.match(player, /buildMusicPresentation/)
  assert.doesNotMatch(player, /v31-tone-theme/)
  assert.match(player, /playerController\.toggle\(/)
  assert.match(player, /playerController\.seek\(/)
  assert.match(player, /playerController\.dispose\(/)
  assert.doesNotMatch(player, /\b(?:audio|audioCtx|innerAudioContext)\.(?:play|pause|seek|destroy)\s*\(/)
  for (const forbidden of ["traits", "instruments", "ambience", "title"]) {
    assert.doesNotMatch(toneTheme, new RegExp(`\\b${forbidden}\\s*:`))
  }
})

test("PR-025 freezes approved RAG score and embedding identities", () => {
  const policy = JSON.parse(readRepo("knowledge/v3/rag-query-policy-v3.2-approved.json"))
  const manifest = JSON.parse(readRepo("knowledge/v3/rag-ingestion-manifest-v3.1-approved.json"))

  assert.equal(policy.asset_version, "rag-query-policy-v3.2-r1")
  assert.equal(policy.query_builder_version, "diagnosis_query_v3.2")
  assert.equal(policy.source_cosine_threshold, 0.65)
  assert.equal(policy.minimum_score, 0.740741)
  assert.equal(manifest.embedding_model, "text-embedding-v4")
  assert.equal(manifest.embedding_dimension, 1024)
  assert.equal(manifest.embedding_version, "text-embedding-v4@1024")
  assert.equal(manifest.chunk_count, 13)
})

test("canonical Owner design assets are byte-identical to the approved hashes", () => {
  const assets = new Map([
    ["HarmonyAI就诊资料智能摘要.png", "b0a423f64d7e36cf3f02c17458bb4cac94a595cf233a071e002243694da33770"],
    ["HarmonyAI山水疗愈音乐界面.png", "b7b3bf818ab87c9ea19509640472c1def3bea6648c65912b8e8d5987959a80e1"],
    ["HarmonyAI聆听反馈界面(3).png", "0716cbda5457965b092e57d439138f9901d47620635bdad43c878fd0e5cd6f53"],
  ])
  const registries = [
    readRepo("docs/product/sprint6-product-recovery-contract.md"),
    readRepo("docs/sprint6/product-recovery-requirements-matrix.md"),
    readRepo("docs/superpowers/plans/2026-09-26-sprint6-product-recovery.md"),
  ]

  for (const [filename, expected] of assets) {
    const canonicalPath = `docs/product/assets/sprint6-recovery/${filename}`
    const bytes = readRepoBytes(`docs/product/assets/sprint6-recovery/${filename}`)
    assert.ok(bytes.length > 0, `${filename} must not be empty`)
    assert.equal(createHash("sha256").update(bytes).digest("hex"), expected, filename)
    for (const registry of registries) {
      assert.match(registry, new RegExp(canonicalPath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
      assert.match(registry, new RegExp(expected))
    }
  }
})
