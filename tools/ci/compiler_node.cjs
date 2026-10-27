// Compiler-only adapter. offline_node.cjs remains unchanged and still denies
// every network API and discovery subprocess. Only the pinned esbuild service
// used by the existing offline build is allowed to start.
const cp = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const realSpawn = cp.spawn;
require('./offline_node.cjs');
const target = `${process.platform}-${process.arch}`;
const binary = {'win32-x64':'@esbuild/win32-x64/esbuild.exe','linux-x64':'@esbuild/linux-x64/bin/esbuild'}[target];
if (!binary) throw new Error('Unreviewed compiler platform');
const expected = path.resolve('node_modules', binary);
const version = require(path.resolve('node_modules/esbuild/package.json')).version;
const blockedSpawn = cp.spawn;
function isAllowedEsbuildSpawn(command,args,options) {
  return typeof command === 'string' && path.resolve(command) === expected &&
      Array.isArray(args) && args.length === 2 && args[0] === '--service='+version && args[1] === '--ping' &&
      options && Object.getPrototypeOf(options) === Object.prototype &&
      Object.keys(options).sort().join(',') === 'cwd,stdio,windowsHide' && options.shell === undefined &&
      options.windowsHide === true && typeof options.cwd === 'string' && path.resolve(options.cwd) === process.cwd() &&
      Array.isArray(options.stdio) && options.stdio.join(',') === 'pipe,pipe,inherit';
}
cp.spawn = function(command, args, options) {
  if (isAllowedEsbuildSpawn(command,args,options)) {
    return realSpawn.call(this, expected, ['--service='+version,'--ping'], {
      cwd:process.cwd(), windowsHide:true, stdio:['pipe','pipe','inherit'], shell:false,
    });
  }
  return blockedSpawn.apply(this, arguments);
};

function classify(api, kind) {
  fs.appendFileSync(process.env.CHECKPOINT_COMPILER_EVIDENCE, JSON.stringify({api,kind})+'\n');
}
// Exact Rollup Windows report probe. It remains blocked before spawnSync.
const reportScript = "const r=require('node:process').report;r.excludeNetwork=true;console.log(JSON.stringify(r.getReport().header));";
const blockedSync = cp.spawnSync;
cp.spawnSync = function(command,args,options) {
  if (command === process.execPath && Array.isArray(args) && args.length === 2 && args[0] === '-p' && args[1] === reportScript &&
      options && Object.keys(options).sort().join(',') === 'encoding,timeout,windowsHide' &&
      options.encoding === 'utf8' && options.timeout === 3000 && options.windowsHide === true) {
    classify('child_process.spawnSync','report_header');
  }
  return blockedSync.apply(this, arguments);
};
// Vite may handle its optional network-drive discovery as an async error.
// NEVER execute `net use`; return the original Guard's denial to that callback.
const blockedExec = cp.exec;
cp.exec = function(command,callback) {
  if (arguments.length === 2 && command === 'net use' && typeof callback === 'function') {
    classify('child_process.exec','network_drive_discovery');
    try { blockedExec.apply(this, arguments); } catch (error) {
      process.nextTick(()=>callback(error,'',''));
      return {kill(){return false;}};
    }
  }
  return blockedExec.apply(this, arguments);
};
require('node:module').syncBuiltinESMExports();
module.exports={isAllowedEsbuildSpawn};
