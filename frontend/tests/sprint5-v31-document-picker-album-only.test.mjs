/**
 * Android 上传资料：图片来源回归测试（Issue：仅允许相册）
 *
 * 真机问题：V3.1 资料上传页的 uni.chooseImage 未声明 sourceType，uni-app 默认
 * 使用 ['album', 'camera']，因此真机点“点击上传文件”会弹出「拍摄 / 从相册选择」，
 * 并在未集成 camera 模块的 App 包上弹出“打包时未添加camera模块”。
 *
 * 本测试只锁定“图片来源”这一处最小改动，并确认上传/OCR 链路未被改动：
 *   1. sourceType 必须恰好是 ['album']
 *   2. 页面不得出现 camera 选项（也不引入 camera 模块依赖）
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

test("document picker offers the album only, never the camera", () => {
  const body = chooseFilesBody()

  assert.ok(body.includes("uni.chooseImage({"), "picker must still use uni.chooseImage")
  assert.match(
    body,
    /sourceType:\s*\[\s*["']album["']\s*\]/,
    "sourceType must be exactly ['album']",
  )
  // Only one sourceType in the whole page, and it is the album-only one above.
  assert.equal(
    [...materialPage.matchAll(/sourceType/g)].length,
    1,
    "sourceType must be declared exactly once",
  )
  // No camera as a selectable source anywhere on the page.
  assert.doesNotMatch(materialPage, /["']camera["']/, "camera must not appear as an option")
})

test("picker still fills the remaining 1-3 document slots", () => {
  const body = chooseFilesBody()

  assert.match(materialPage, /const MAX_FILES = 3/, "the 3-image ceiling is unchanged")
  assert.match(body, /const remain = MAX_FILES - this\.files\.length/)
  assert.match(body, /count:\s*remain/, "count must still request only the remaining slots")
  assert.match(
    body,
    /if \(this\.state === "uploading" \|\| !this\.canAdd\) return/,
    "in-flight/limit guard is unchanged",
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
  assert.match(materialPage, /removeFile\(idx\)/)
  assert.match(materialPage, /\/pages\/v3-material-error\/v3-material-error\?type=ocr/)
  assert.match(materialPage, /\/pages\/v3-material-error\/v3-material-error\?type=network/)
})
