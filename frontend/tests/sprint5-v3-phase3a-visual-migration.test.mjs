import assert from "node:assert/strict"
import crypto from "node:crypto"
import fs from "node:fs"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(here, "..")
const pages = ["welcome", "v3-material", "v3-summary", "v3-narrative", "v3-confirm", "v3-basis", "v3-feedback", "v3-player"]
const scriptHashes = {
  welcome: "64f5e372eec60d78b2ae1144990ddbdb9a5698a3b3746a33f5076e6b8c667f4d",
  "v3-material": "47fd4f994ac8db0fbf5834c4345590e7ee7e9e2990d86dda9ab085fb2c21a1d9",
  "v3-summary": "f119138dc39cce19658f342f263f831ef7af05a3c697ffd436753e2c30574299",
  "v3-narrative": "9e86d60b3797422021e7e6951ab49c55c6b0fb1564291f33cb1dc6df0db6266d",
  "v3-confirm": "dab725d0d46a9ca0ff6578371a48cac196563181c751b4b3e928fa32687dcead",
  "v3-basis": "b03646d0f063e3afcb89272b43a8512dd6f1631f7a169b800bf939fa1cca319e",
  "v3-feedback": "2778da79484888c09e6f489d8b5802c5e4b8e2ec3051231f711c0da1c6686816",
  "v3-player": "f2c47f06ce4acb425a12f35a164304ce8d522e475cf7b7347cd66712545593fe",
}

function readPage(name) {
  return fs.readFileSync(path.join(root, "pages", name, `${name}.vue`), "utf8")
}

test("Phase 3A keeps every target page script byte-for-byte unchanged", () => {
  for (const name of pages) {
    const source = readPage(name)
    const script = source.match(/<script[^>]*>[\s\S]*?<\/script>/)?.[0] || ""
    assert.equal(crypto.createHash("sha256").update(script).digest("hex"), scriptHashes[name], name)
  }
})

test("Phase 3A pages share tokens, safe areas, and compact-height density", () => {
  const tokens = fs.readFileSync(path.join(root, "styles", "v3-visual-tokens.scss"), "utf8")
  assert.match(tokens, /v3-one-screen/)
  assert.match(tokens, /v3-scroll-page/)
  assert.match(tokens, /max-height:\s*760px/)
  assert.match(tokens, /safe-area-inset-top/)
  assert.match(tokens, /safe-area-inset-bottom/)
  for (const name of pages) assert.match(readPage(name), /v3-visual-tokens\.scss/, name)
})

test("one-screen-first pages remain scroll-safe and variable pages remain naturally scrollable", () => {
  for (const name of ["welcome", "v3-material", "v3-summary", "v3-confirm", "v3-player"])
    assert.match(readPage(name), /v3-one-screen-page/, name)
  for (const name of ["v3-narrative", "v3-basis", "v3-feedback"])
    assert.match(readPage(name), /v3-scroll-page/, name)
  for (const name of pages) assert.doesNotMatch(readPage(name), /\.v3-one-screen-page\s*\{[^}]*overflow:\s*hidden/s, name)
})

test("Basis exposes a visual explanation chain without invented fields", () => {
  const basis = readPage("v3-basis")
  for (const label of ["状态依据", "五脏与五行相关解释", "五音方案", "音乐参数"])
    assert.match(basis, new RegExp(label))
  assert.doesNotMatch(basis, /basis\.(organ_profile|five_elements|organ_evidence)/)
})

test("Player uses CSS play and pause marks and a smaller artwork", () => {
  const player = readPage("v3-player")
  assert.doesNotMatch(player, /⏸|▶/)
  assert.match(player, /control-icon--pause/)
  assert.match(player, /control-icon--play/)
  assert.match(player, /min\(255px,\s*62vw\)/)
})

test("Welcome no longer uses emoji or symbol glyphs as functional icons", () => {
  const welcome = readPage("welcome")
  assert.doesNotMatch(welcome, /⏱|✎|♪/)
  assert.match(welcome, /meta-mark/)
})
