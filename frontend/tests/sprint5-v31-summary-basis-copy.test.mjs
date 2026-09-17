/**
 * V3.1 近期状态总结页 + 五音解析页文案回归测试
 *
 * 覆盖本轮 4 个问题中的前 3 个（第 4 个 Player 真实时长见
 * sprint5-v31-player-duration.test.mjs）：
 *
 *  1. 状态总结页不再只展示固定 generic 文案，而是渲染 read model 的真实内容
 *  2. 五音解析页受控证型名称走 canonical 中文；用户可见"状态解读/调适依据"
 *     不得含已知英文 fixture（英文源头在 Agent2 生成侧，由 backend 测试锁定；
 *     此处锁定前端不硬编码、不逐句翻译英文）
 *  3. 音乐设计四张卡片删除重复行 / "由服务端处方生成。"辅助文案，并重新居中
 *
 * 说明：本测试为静态源码断言（前端无 DOM 运行时）。运行方式与仓库其它测试一致：
 *   cd frontend && node --test "tests/*.test.mjs"
 */

import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

const confirmPage = read("pages/v3-confirm/v3-confirm.vue")
const basisPage = read("pages/v3-basis/v3-basis.vue")

// 去掉 <style> 块，只对模板 + 脚本做文案/逻辑断言（避免死 CSS 干扰）
const stripStyles = (source) => source.replace(/<style[\s\S]*?<\/style>/g, "")
const confirmMarkup = stripStyles(confirmPage)
const basisMarkup = stripStyles(basisPage)

const GENERIC_SUMMARY = "已根据你本次提供并确认的信息完成状态评估。"

// ---------------------------------------------------------------- 问题 1

test("近期状态总结页是确认页语义：确认近期状态总结 + 近期状态总结卡片", () => {
  assert.ok(confirmMarkup.includes("最后一步 · 确认"), "badge 保持冻结文案")
  assert.ok(confirmMarkup.includes("确认近期状态总结"), "主标题为确认语义")
  assert.ok(!confirmMarkup.includes("综合分析"), "旧卡片标题“综合分析”必须移除")
  assert.ok(confirmMarkup.includes("近期状态总结"), "卡片标题改为“近期状态总结”")
  assert.ok(
    confirmMarkup.includes("请确认下面的内容是否基本符合你最近的状态。确认后，我们会以此作为本次五音调适分析的基础。"),
    "说明文案冻结为确认语义",
  )
})

test("状态总结页不再用固定 generic 文案冒充个性化总结", () => {
  assert.ok(
    !confirmMarkup.includes(GENERIC_SUMMARY),
    "页面不得硬编码后端 generic 总结文案",
  )
  // 卡片正文必须绑定由 read model 推导的 summaryText，而不是直接回退到固定串
  assert.match(confirmMarkup, /\{\{\s*summaryText\s*\}\}/)
  assert.ok(
    !/\{\{\s*model\.summary\s*\}\}/.test(confirmMarkup),
    "卡片正文不得直接渲染未归一化的 model.summary",
  )
})

test("状态总结页渲染后端 read model 的真实字段", () => {
  // presentation.summary → model.summary → model.state_summary 优先级
  assert.ok(confirmPage.includes("presentation.summary"), "优先使用 presentation.summary")
  assert.ok(confirmPage.includes("model.state_summary"), "回退使用 state_summary")
  // 真实条目：后端 fact_evidence 的 canonical 中文 display_name（mock 下为 sections.items）
  assert.ok(confirmPage.includes("model.fact_evidence"), "必须渲染本次评估真实形成的事实条目")
  assert.ok(confirmPage.includes("display_name"), "条目名称取后端 canonical display_name")
  assert.ok(confirmPage.includes("model.sections"), "mock/hybrid 下取 sections 条目")
  assert.match(confirmMarkup, /v-for="\(item, index\) in summaryItems"/, "条目需渲染到界面")
  // 前端不得在此推导证型 / 脏腑 / 调式（不做医学判断）
  assert.ok(!/claim_code\s*===/.test(confirmMarkup), "不得在前端按 claim_code 推导结论")
})

test("状态总结页保留原业务行为：全文编辑 + 两个冻结按钮", () => {
  assert.ok(confirmMarkup.includes("基本符合，继续"), "确认按钮保持")
  assert.ok(confirmMarkup.includes("有些地方不对，我要修改"), "修改入口保持")
  assert.ok(confirmPage.includes("edited_summary_text"), "V3.1 仍为完整文本 edited_summary_text")
  assert.ok(confirmPage.includes("decision: \"confirm_with_changes\""), "修改提交路径保持")
  assert.ok(confirmPage.includes("apiV3.confirmAssessment("), "仍作用于 Assessment")
  // 不得恢复结构化逐项 severity 编辑
  assert.ok(!confirmMarkup.includes("severity-row"), "不得恢复结构化 severity 编辑行")
  assert.ok(!confirmMarkup.includes("allowed_values"), "不得恢复结构化可选值编辑")
})

// ---------------------------------------------------------------- 问题 2

test("五音解析页受控证型名称使用 canonical 中文（含“倾向”语义）", () => {
  const whitelist = JSON.parse(read("../knowledge/v3/agent2-syndrome-whitelist-v3.1.json"))
  const names = whitelist.allowed_syndromes.map((item) => item.display_name)
  assert.equal(names.length, 8, "8 个 canonical 证型名称")
  for (const name of names) {
    assert.match(name, /倾向$/, `canonical 名称必须保持“倾向”语义: ${name}`)
    assert.match(name, /[\u4e00-\u9fa5]/, `canonical 名称必须为中文: ${name}`)
  }
  // 页面渲染受控名称必须来自 read model 字段，而不是前端字典；
  // Sprint 6：主音/辅音区块只能在 personalized + 真实主音时渲染（null 安全的 mode-aware guard）
  assert.match(basisMarkup, /v-if="hasPrimaryTone"[\s\S]*?\{\{\s*basis\.primary_tone\.display_name\s*\}\}/)
  assert.match(basisMarkup, /v-if="hasPrimaryTone && basis\.secondary_tone"[\s\S]*?\{\{\s*basis\.secondary_tone\.display_name\s*\}\}/)
})

test("五音解析页用户可见解释不含已知英文 fixture，且不做逐句字典翻译", () => {
  // 真机观测到的英文（来自 Agent2 生成侧）不得出现在前端源码/模板中
  for (const english of [
    "Spleen Deficiency",
    "Loose stool and postmeal heaviness",
    "Anger tendency maps to liver",
    "Night palpitations suggest",
  ]) {
    assert.ok(!basisPage.includes(english), `不得硬编码英文解释: ${english}`)
  }
  // 不得在模板/脚本内置成句英文（≥4 个英文单词的字符串字面量），
  // 既排除硬编码英文解释，也排除英→中字典键。只检查模板+脚本：
  // 样式块中的字体栈、以及 class 名列表不是用户可见文案。
  assert.doesNotMatch(
    basisMarkup,
    /["'`][A-Za-z][A-Za-z0-9,.'-]*(?: [A-Za-z][A-Za-z0-9,.'-]*){3,}["'`]/,
    "不得内置英文句子或英中字典（整段翻译属脆弱做法，应由生成侧输出中文）",
  )
  // 不得引入任何翻译/本地化辅助模块
  assert.ok(!/from\s+["'][^"']*(translat|i18n|locale)/i.test(basisPage), "不得引入翻译模块")
  // 用户可见解释文本必须直接来自 read model 字段
  assert.match(basisMarkup, /\{\{\s*basis\.state_tendency\s*\}\}/, "状态解读取 read model")
  assert.match(basisMarkup, /v-for="\(row, idx\) in rationaleRows"/, "调适依据取 read model 推导行")
  assert.ok(basisPage.includes("basis.analysis_rationales"), "调适依据来源为 analysis_rationales")
})

// ---------------------------------------------------------------- 问题 3

test("音乐设计：四张卡片各自只有 图标 + 数值 + 名称，无辅助重复文案", () => {
  const design = basisMarkup.slice(basisMarkup.indexOf("<!-- 音乐设计 -->"), basisMarkup.indexOf("<!-- 生成中"))
  const cards = [...design.matchAll(/<view class="design-card">([\s\S]*?)<\/view>/g)].map((m) => m[1])
  assert.equal(cards.length, 4, "音乐设计固定四张卡片")
  for (const card of cards) {
    assert.equal((card.match(/param-value/g) || []).length, 1, "每张卡一个数值")
    assert.equal((card.match(/param-label/g) || []).length, 1, "每张卡一个名称")
    assert.equal((card.match(/param-reason/g) || []).length, 0, "不得再有辅助说明行")
    assert.equal((card.match(/<image/g) || []).length, 1, "每张卡一个图标")
  }
  assert.ok(!basisPage.includes("param-reason"), "param-reason 样式与用法必须移除")
})

test("音乐设计：不存在重复的 BPM·乐器·时长行，也不存在“由服务端处方生成。”", () => {
  assert.ok(
    !/BPM\s*·/.test(basisMarkup),
    "第一张卡不得再出现“60 BPM · 古琴 · 180秒”这类拼接行",
  )
  assert.ok(!basisPage.includes("由服务端处方生成"), "2/3/4 张卡不得出现“由服务端处方生成。”")
  // 数值与名称保持不变（数据来源不变）
  assert.match(basisMarkup, /\{\{\s*basis\.bpm\.value\s*\}\}\s*BPM/)
  assert.ok(basisMarkup.includes("舒缓节奏"))
  assert.ok(basisMarkup.includes("时长"))
  assert.ok(basisMarkup.includes("主要乐器"))
  assert.ok(basisMarkup.includes("音乐氛围"))
})

test("音乐设计：删除辅助行后卡片内容垂直居中且无空洞", () => {
  // 卡片容器需垂直居中
  assert.match(
    basisPage,
    /\.design-card\s*\{[^}]*justify-content:center/,
    "卡片内容需垂直居中",
  )
  // 去除辅助行后不再保留 148px 的固定高度（会留下空洞）
  assert.ok(
    !/\.design-card\s*\{[^}]*min-height:148px/.test(basisPage),
    "不得保留删除文案前的 148px 固定高度",
  )
  assert.match(basisPage, /\.param-label\s*\{[^}]*margin:0/, "名称行下方不应再有留白")
})
