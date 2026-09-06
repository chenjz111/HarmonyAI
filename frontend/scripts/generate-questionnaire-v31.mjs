import { readFileSync, writeFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const sourcePath = resolve(here, "../../knowledge/v3/questionnaire-v3.0.1.json")
const outputPath = resolve(here, "../common/questionnaire-v3-generated.js")
const questionnaire = JSON.parse(readFileSync(sourcePath, "utf8"))
const output = `// GENERATED FROM knowledge/v3/questionnaire-v3.0.1.json\n// DO NOT EDIT MANUALLY. Run: node frontend/scripts/generate-questionnaire-v31.mjs\n// content_checksum: ${questionnaire.content_checksum}\n\nexport const QUESTIONNAIRE_MANIFEST = ${JSON.stringify(questionnaire, null, 2)}\n\nexport default QUESTIONNAIRE_MANIFEST\n`

if (process.argv.includes("--check")) {
  let current = ""
  try {
    current = readFileSync(outputPath, "utf8")
  } catch {
    // A missing generated file is a consistency failure.
  }
  if (current !== output) {
    console.error("questionnaire-v3-generated.js is not synchronized with canonical JSON")
    process.exit(1)
  }
} else {
  writeFileSync(outputPath, output, "utf8")
}
