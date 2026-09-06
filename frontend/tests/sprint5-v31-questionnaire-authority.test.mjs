import test from "node:test"
import assert from "node:assert/strict"
import crypto from "node:crypto"
import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { spawnSync } from "node:child_process"

import generated from "../common/questionnaire-v3-generated.js"

const here = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(here, "..")
const repoRoot = resolve(frontendRoot, "..")
const canonicalPath = resolve(repoRoot, "knowledge/v3/questionnaire-v3.0.1.json")
const questionnaire = JSON.parse(readFileSync(canonicalPath, "utf8"))
const byId = Object.fromEntries(questionnaire.questions.map((item) => [item.question_id, item]))

const canonicalize = (value) => {
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]))
  }
  return value
}
const optionTriples = (id) => byId[id].options.map(({ option_code, label, score }) => [option_code, label, score])

test("01 schema identity and canonical checksum are V3.0.1", () => {
  const withoutChecksum = structuredClone(questionnaire)
  delete withoutChecksum.content_checksum
  const actual = "sha256:" + crypto.createHash("sha256").update(JSON.stringify(canonicalize(withoutChecksum))).digest("hex")
  assert.equal(questionnaire.schema_id, "questionnaire_v3")
  assert.equal(questionnaire.schema_version, "3.0.1")
  assert.equal(questionnaire.manifest_version, "medical_v3.0.1")
  assert.equal(questionnaire.content_checksum, actual)
})

test("02 Q1-Q10 count and order are exact", () => {
  assert.equal(questionnaire.question_count, 10)
  assert.deepEqual(questionnaire.questions.map((item) => item.question_id), ["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09", "q10"])
  assert.deepEqual(questionnaire.questions.map((item) => item.position), [1,2,3,4,5,6,7,8,9,10])
})

test("03 Q1-Q10 are all required", () => {
  assert.ok(questionnaire.questions.every((item) => item.required === true))
})

test("04 answer types are five single-frequency then five multi-choice", () => {
  assert.deepEqual(questionnaire.questions.map((item) => item.answer_type), [
    "frequency_0_4", "frequency_0_4", "frequency_0_4", "frequency_0_4", "frequency_0_4",
    "multi_choice_evidence", "multi_choice_evidence", "multi_choice_evidence", "multi_choice_evidence", "multi_choice_evidence",
  ])
})

test("05 Q1-Q5 prompts are exact", () => {
  assert.deepEqual(questionnaire.questions.slice(0, 5).map((item) => item.prompt), [
    "最近一周，你会不会比较容易着急、烦躁？",
    "最近一周，你会不会觉得心里静不下来、容易兴奋或紧张？",
    "最近一周，你会不会想事情比较多、脑子里停不下来？",
    "最近一周，你会不会觉得心情有点低落、想叹气？",
    "最近一周，你会不会觉得心里不太踏实、有点害怕？",
  ])
})

test("06 Q1 option text, codes and scores are exact", () => {
  assert.deepEqual(optionTriples("q01"), [["0","平静如水",0],["1","偶尔有一丝火气",1],["2","像温水在翻滚",2],["3","像是个火药桶",3],["4","已经快爆发了",4]])
})
test("07 Q2 option text, codes and scores are exact", () => {
  assert.deepEqual(optionTriples("q02"), [["0","心如止水",0],["1","偶尔有点小涟漪",1],["2","心里七上八下",2],["3","坐立难安",3],["4","心都要跳出来了",4]])
})
test("08 Q3 option text, codes and scores are exact", () => {
  assert.deepEqual(optionTriples("q03"), [["0","脑子很清爽",0],["1","偶尔想点事",1],["2","有点放不下",2],["3","事情一件接一件",3],["4","脑子里像在刷弹幕",4]])
})
test("09 Q4 option text, codes and scores are exact", () => {
  assert.deepEqual(optionTriples("q04"), [["0","心情不错",0],["1","偶尔有点小低落",1],["2","心里闷闷的",2],["3","像压了块小石头",3],["4","感觉天都是灰蒙蒙的",4]])
})
test("10 Q5 option text, codes and scores are exact", () => {
  assert.deepEqual(optionTriples("q05"), [["0","心里很踏实",0],["1","偶尔有点小忐忑",1],["2","心里有点不踏实",2],["3","心里直打鼓",3],["4","总觉得要有什么事",4]])
})

const bodyPrompt = "下面这些感觉，最近一周有没有出现过？"
test("11 Q6 prompt and option text are exact", () => {
  assert.equal(byId.q06.prompt, bodyPrompt)
  assert.deepEqual(byId.q06.options.map((item) => [item.option_code, item.label]), [
    ["flank_discomfort","胸口附近有时会觉得闷闷的，想长舒一口气"],
    ["tendon_stiffness","身体某些部位会觉得紧绷、伸展不开"],
    ["muscle_cramp","小腿或脚有时会突然抽一下"],
    ["eye_discomfort","眼睛有时会觉得干、看久了容易累"],
    ["none","都很少出现，很轻松"],
  ])
})
test("12 Q7 prompt and option text are exact", () => {
  assert.equal(byId.q07.prompt, bodyPrompt)
  assert.deepEqual(byId.q07.options.map((item) => [item.option_code, item.label]), [
    ["palpitation_at_rest","安静坐着或躺着时，有时能感觉到自己的心跳"],
    ["palpitation_after_activity","稍微活动一下，心跳就变得比较明显"],
    ["palpitation_night","晚上躺下时，会因为心跳的感觉而不太舒服"],
    ["tongue_tip_discomfort","舌尖有时候会觉得有点疼或有点红"],
    ["none","都很少出现，很轻松"],
  ])
})
test("13 Q8 prompt and option text are exact", () => {
  assert.equal(byId.q08.prompt, bodyPrompt)
  assert.deepEqual(byId.q08.options.map((item) => [item.option_code, item.label]), [
    ["poor_appetite","胃口一般，到饭点也不太想吃"],
    ["postmeal_bloating","吃一点就觉得胀胀的、撑撑的"],
    ["loose_stool","上厕所时，大便有时候会比较稀、不太成形"],
    ["postmeal_heaviness","饭后觉得身体沉沉的、没什么精神，想休息"],
    ["none","都很少出现，很轻松"],
  ])
})
test("14 Q9 prompt and option text are exact", () => {
  assert.equal(byId.q09.prompt, bodyPrompt)
  assert.deepEqual(byId.q09.options.map((item) => [item.option_code, item.label]), [
    ["throat_cough","嗓子有时会觉得干，或有点想清一清"],
    ["exertional_breathlessness","走路、爬楼时，呼吸会比平时快一点"],
    ["nasal_discomfort","鼻子有时会觉得不通气"],
    ["voice_change","说话久了会觉得嗓子累、声音变哑"],
    ["none","都很少出现，很轻松"],
  ])
})
test("15 Q10 prompt and option text are exact", () => {
  assert.equal(byId.q10.prompt, bodyPrompt)
  assert.deepEqual(byId.q10.options.map((item) => [item.option_code, item.label]), [
    ["lower_back_knee_weakness","腰或腿有时会觉得酸酸的、没什么劲"],
    ["tinnitus","耳朵有时会有嗡嗡声"],
    ["nocturia","夜里有时会起来上厕所"],
    ["none","都很少出现，很轻松"],
  ])
})

test("16 every evidence claim resolves through Claim Dictionary and Organ Mapping", () => {
  const claims = JSON.parse(readFileSync(resolve(repoRoot, "knowledge/v3/claim-dictionary-v3.0.json"), "utf8"))
  const organs = JSON.parse(readFileSync(resolve(repoRoot, "knowledge/v3/organ-mapping-v3.0.json"), "utf8"))
  const claimCodes = new Set(claims.entries.map((item) => item.claim_code))
  const organCodes = new Set(organs.single_mappings.map((item) => item.claim_code))
  for (const question of questionnaire.questions) {
    for (const option of question.options) {
      if (option.claim_code === null) continue
      assert.ok(claimCodes.has(option.claim_code), option.claim_code)
      assert.ok(organCodes.has(option.claim_code), option.claim_code)
      assert.equal(option.evidence_semantic_ref, "claim-dictionary-v3.0.json#" + option.claim_code)
    }
  }
})

test("17 frontend pagination is exactly five pages of Q1-Q2 through Q9-Q10", () => {
  const displayPages = Array.from({ length: 5 }, (_, index) => questionnaire.questions.slice(index * 2, index * 2 + 2).map((item) => item.question_id))
  assert.deepEqual(displayPages, [
    ["q01","q02"], ["q03","q04"], ["q05","q06"], ["q07","q08"], ["q09","q10"],
  ])
  const page = readFileSync(resolve(frontendRoot, "pages/v3-questionnaire/v3-questionnaire.vue"), "utf8")
  assert.ok(page.includes("PAGE_SIZE = 2"))
  assert.ok(page.includes("v-for=\"opt in q.options\""))
  assert.ok(!page.includes("FREQUENCY_OPTIONS"))
})

test("18 UserGoal is an independent optional preference and generated frontend source is deterministic", () => {
  assert.deepEqual(questionnaire.user_goal, {
    title: "疗愈诉求",
    page_kind: "optional_supplement",
    is_question: false,
    required: false,
    skippable: true,
    max_selections: 2,
    options: [
      { code: "sleep", label: "帮我睡得安稳一点" },
      { code: "relaxation", label: "让我放松、静下来" },
      { code: "emotion_regulation", label: "帮我把情绪释放出来" },
      { code: "focus", label: "让我更容易专注" },
      { code: "energy", label: "帮我恢复点精力" },
      { code: "stress_relief", label: "让我减轻点压力" },
      { code: "other", label: "其他" },
    ],
    custom_goal_text: { required: false, max_length: 200, independent: true },
    empty_semantics: "user_goal_null",
    evidence_role: "music_design_preference_only",
  })
  assert.deepEqual(generated, questionnaire)
  assert.equal(existsSync(resolve(frontendRoot, "common/questionnaire-v3-manifest.js")), false)
  const check = spawnSync(process.execPath, ["scripts/generate-questionnaire-v31.mjs", "--check"], {
    cwd: frontendRoot,
    encoding: "utf8",
  })
  assert.equal(check.status, 0, check.stderr || check.stdout)
})
