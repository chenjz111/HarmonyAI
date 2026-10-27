const assert=require('node:assert/strict');
const cp=require('node:child_process');
const path=require('node:path');
let passed=0;
function denied(fn){assert.throws(fn,/offline guard blocked/);passed++;}
const script="const r=require('node:process').report;r.excludeNetwork=true;console.log(JSON.stringify(r.getReport().header));";
denied(()=>cp.spawnSync(process.execPath,['-p',script],{encoding:'utf8',timeout:3000,windowsHide:true}));
denied(()=>cp.spawnSync(process.execPath,['-p',script+'extra'],{encoding:'utf8',timeout:3000,windowsHide:true}));
denied(()=>cp.exec('whoami'));
const binary=process.platform==='win32'?'@esbuild/win32-x64/esbuild.exe':'@esbuild/linux-x64/bin/esbuild';
const {isAllowedEsbuildSpawn}=require('./compiler_node.cjs');
const version=require(path.resolve('node_modules/esbuild/package.json')).version;
const serviceArgs=['--service='+version,'--ping'];
for(const shell of [true,'unreviewed-shell']){
  // Check the predicate BEFORE the actual call: a regression must never launch a shell in this test.
  assert.equal(isAllowedEsbuildSpawn(path.resolve('node_modules',binary),serviceArgs,{cwd:process.cwd(),windowsHide:true,stdio:['pipe','pipe','inherit'],shell}),false);
  denied(()=>cp.spawn(path.resolve('node_modules',binary),serviceArgs,{cwd:process.cwd(),windowsHide:true,stdio:['pipe','pipe','inherit'],shell}));
}
denied(()=>cp.spawn(path.resolve('node_modules',binary),['--service=wrong','--ping']));
denied(()=>fetch('https://example.invalid'));
denied(()=>cp.spawn(process.execPath,['--version']));
cp.exec('net use',error=>{assert.ok(error);passed++;assert.equal(passed,9);process.stdout.write(JSON.stringify({compiler_guard_selftests_passed:passed})+'\n');});
