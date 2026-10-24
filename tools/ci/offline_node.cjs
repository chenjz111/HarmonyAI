const fs = require('node:fs');
function deny(api) {
  return function () {
    fs.appendFileSync(process.env.CHECKPOINT_NODE_EVIDENCE,
      JSON.stringify({api, action: 'blocked'}) + '\n');
    throw new Error('Checkpoint offline guard blocked network access');
  };
}
require('node:net').Socket.prototype.connect = deny('net.connect');
require('node:tls').connect = deny('tls.connect');
for (const name of ['node:http', 'node:https']) {
  const mod = require(name);
  mod.request = deny(name + '.request');
  mod.get = deny(name + '.get');
}
const dns = require('node:dns');
for (const key of ['lookup', 'resolve', 'resolve4', 'resolve6']) dns[key] = deny('dns.' + key);
globalThis.fetch = deny('fetch');
const cp = require('node:child_process');
for (const key of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) {
  cp[key] = deny('child_process.' + key);
}
const workers = require('node:worker_threads');
workers.Worker = class { constructor() { deny('worker_threads.Worker')(); } };
const dgram = require('node:dgram');
dgram.Socket.prototype.send = deny('dgram.send');
dgram.Socket.prototype.bind = deny('dgram.bind');
require('node:net').Server.prototype.listen = deny('net.listen');
require('node:http2').connect = deny('http2.connect');
for (const api of [dns, dns.promises]) {
  for (const key of Object.keys(api)) {
    if (/^(lookup|resolve|reverse)/.test(key) && typeof api[key] === 'function') {
      api[key] = deny('dns.' + key);
    }
  }
}
if (globalThis.WebSocket) globalThis.WebSocket = class { constructor() { deny('WebSocket')(); } };
require('node:module').syncBuiltinESMExports();
