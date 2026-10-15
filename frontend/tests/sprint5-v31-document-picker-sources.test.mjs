/**
 * Android 上传资料：图片来源回归测试（相册 + 相机）
 *
 * Owner 真机验收要求点击“点击上传文件”后同时提供「拍摄 / 从相册选择」。
 * 当前 Android HBuilder 基座已包含并授权 camera 能力，因此页面显式声明两个来源，
 * 避免再次被历史 album-only 配置收窄。
 *
 * 本测试只锁定“图片来源”这一处最小改动，并确认上传/OCR 链路未被改动：
 *   1. sourceType 必须恰好是 ['album', 'camera']
 *   2. 两种来源共用同一个 success 文件归一化逻辑
 *   3. 最多 3 张的 count 行为保持不变
 *   4. 上传链路（startUpload / apiV3.uploadDocument / 异常分流）保持不变
 */

import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import test from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

// 首页「我有就诊资料」在真机上进入的就是本页（pages/entry/entry.vue 的 route）
const materialPage = read("pages/v3-material/v3-material.vue")

function chooseFilesBody() {
  const start = materialPage.indexOf("chooseFiles()")
  assert.notEqual(start, -1, "v3-material.vue must still define chooseFiles()")
  const end = materialPage.indexOf("defaultName(path)", start)
  assert.notEqual(end, -1, "chooseFiles() must be followed by defaultName()")
  return materialPage.slice(start, end)
}

test("document picker offers both album and camera sources", () => {
  const body = chooseFilesBody()

  assert.ok(body.includes("uni.chooseImage({"), "picker must still use uni.chooseImage")
  assert.match(
    body,
    /sourceType:\s*\[\s*["']album["']\s*,\s*["']camera["']\s*\]/,
    "sourceType must be exactly ['album', 'camera']",
  )
  // A single picker exposes both sources through one shared success callback.
  assert.equal(
    [...materialPage.matchAll(/sourceType/g)].length,
    1,
    "sourceType must be declared exactly once",
  )
  assert.match(body, /success:\s*\(res\) => \{[\s\S]*const paths = res\.tempFilePaths \|\| \[\]/)
})

test("picker still fills the remaining 1-3 document slots", () => {
  const body = chooseFilesBody()

  assert.match(materialPage, /const MAX_FILES = 3/, "the 3-image ceiling is unchanged")
  assert.match(body, /const remain = MAX_FILES - this\.files\.length/)
  assert.match(body, /count:\s*remain/, "count must still request only the remaining slots")
  assert.match(
    body,
    /if \(!this\.isPicking \|\| !this\.canAdd\) return/,
    "PR-002 single-page phase guard blocks selection outside PICKING",
  )
})

test("selected images and the upload chain are unchanged", () => {
  const body = chooseFilesBody()

  // Selection handling keeps the existing shape (path/name/isImage/document_id).
  assert.match(body, /this\.files\.push\(\{/)
  assert.match(body, /path: p,/)
  assert.match(body, /name: f\.name \|\| this\.defaultName\(p\)/)
  assert.match(body, /document_id: null,/)
  assert.match(body, /success: \(res\) => \{/)
  assert.match(body, /fail: \(\) => \{/)

  // Upload / OCR / session flow untouched.
  assert.match(materialPage, /async startUpload\(\)/)
  assert.match(materialPage, /apiV3\.uploadDocument\(f\.path, f\.name\)/)
  assert.match(materialPage, /removeFile\(index\)/)
  assert.match(materialPage, /\/pages\/v3-material-error\/v3-material-error\?type=ocr/)
  assert.match(materialPage, /\/pages\/v3-material-error\/v3-material-error\?type=network/)
})
