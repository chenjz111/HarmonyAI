import { spawnSync } from "node:child_process"
import { resolve } from "node:path"


const cli = resolve("node_modules", "@dcloudio", "vite-plugin-uni", "bin", "uni.js")
const result = spawnSync(process.execPath, [cli, ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env: { ...process.env, UNI_INPUT_DIR: process.cwd() },
  stdio: "inherit",
})

process.exit(result.status ?? 1)
