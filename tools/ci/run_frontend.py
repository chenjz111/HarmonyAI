"""Trusted parent; no credentials inherited, all tests under unchanged Node offline guard."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import argparse
root = Path(__file__).resolve().parent
source = root.parents[1]/'frontend'
parser = argparse.ArgumentParser(description='Offline frontend specialty; full suite retains existing material failures.')
parser.add_argument('--evidence-dir',required=True,type=Path)
parser.add_argument('--suite',choices=('feedback','full'),default='feedback')
args = parser.parse_args()
evidence = args.evidence_dir.resolve()
if evidence.is_relative_to(source.parent) or source.parent.is_relative_to(evidence):
    parser.error('evidence must be outside source')
evidence.mkdir(parents=True,exist_ok=False)
inventory = {
 'tests/s7-auth-runtime.test.mjs':11,
 'tests/s7-player-product-controls.test.mjs':12,
 'tests/sprint6-phase6-player-wiring.test.mjs':3,
 'tests/s7-guest-continuity.test.mjs':10,
 'tests/sprint6-player-seek-interaction.test.mjs':5,
 'tests/s7-account-security.test.mjs':12,
 'tests/s7-fe2b-history-isolation.test.mjs':27,
 'tests/s7-fe2b-player.test.mjs':11,
 'tests/s7-fe2b-profile-auth.test.mjs':21,
 'tests/s7-fe2b-transport.test.mjs':8,
 'tests/s7-feedback-page.test.mjs':8,
 'tests/s7-feedback-v31.test.mjs':5,
 'tests/sprint6-product-recovery-player-explanation.test.mjs':15,
}
files = list(inventory) if args.suite == 'feedback' else [str(p.relative_to(source)) for p in sorted((source/'tests').glob('*.test.mjs'))]
if not files or any(not (source/name).is_file() for name in files):
    parser.error('Required frontend suite files missing')
allowed = {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','PATHEXT','LANG','LC_ALL','LC_CTYPE','TZ'}
env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
env['CHECKPOINT_NODE_EVIDENCE'] = str(evidence/'blocked.jsonl')
guard = root/'offline_node.cjs'
probe = subprocess.run(['node','--require',str(guard),str(root/'node_guard_selftest.cjs')],
    cwd=source, env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
(evidence/'guard.log').write_text(probe.stdout+probe.stderr,encoding='utf-8')
assert probe.returncode == 0 and '"guard_selftests_passed":5' in probe.stdout
baseline = (evidence/'blocked.jsonl').read_text(encoding='utf-8')
records = []
for index, name in enumerate(files):
    result = subprocess.run(['node','--require',str(guard),'--test','--test-isolation=none','--test-reporter=tap',name],
        cwd=source, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    output = result.stdout+result.stderr
    (evidence/f'{index:03d}.log').write_text(output,encoding='utf-8')
    row = {'file':name,'exit_code':result.returncode}
    for key in ('pass','fail','skipped'):
        match = re.findall(r'^# '+key+r' (\d+)',output,re.M)
        row[key] = int(match[-1]) if match else None
    if row['fail'] or result.returncode:
        print(output[-6000:],flush=True)
    records.append(row)
    print(json.dumps(row),flush=True)
unchanged = (evidence/'blocked.jsonl').read_text(encoding='utf-8') == baseline
(evidence/'results.json').write_text(json.dumps({'guard_unchanged':unchanged,'records':records},indent=2),encoding='utf-8')
mismatch = args.suite == 'feedback' and any(row['pass'] != inventory[row['file']] for row in records)
raise SystemExit(int(not unchanged or mismatch or any(row['exit_code'] or row['skipped'] or row['pass'] is None or row['fail'] != 0 for row in records)))
