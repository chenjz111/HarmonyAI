const assert=require('node:assert/strict');
const net=require('node:net'),dns=require('node:dns'),cp=require('node:child_process');
let verified=0;
for(const attempt of [
 ()=>new net.Socket().connect(443,'192.0.2.1'),
 ()=>new net.Socket().connect(1,'127.0.0.1'),
 ()=>dns.lookup('example.invalid',()=>{}),
 ()=>cp.spawn(process.execPath,['-e','process.exit(0)']),
 ()=>globalThis.fetch('https://example.invalid'),
]){assert.throws(attempt,/Checkpoint offline guard blocked/);verified++;}
console.log(JSON.stringify({guard_selftests_passed:verified,real_network_requests:0}));
