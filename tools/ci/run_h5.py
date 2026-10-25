"""Offline compiler orchestration; test/network Guard stays unchanged.

Compiler-only adapter permits the existing pinned local esbuild service. Optional
Windows discovery commands remain DENIED, with exact audit classification; all
unclassified denials fail acceptance. Build never runs the resulting application.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def validate_compiler_denials(denials,classified):
    kinds={'report_header':'child_process.spawnSync','network_drive_discovery':'child_process.exec'}
    if not isinstance(denials,list) or not isinstance(classified,list) or len(denials)!=len(classified):return False
    seen=set()
    for denial,entry in zip(denials,classified):
        if not isinstance(entry,dict) or set(entry)!={'api','kind'}:return False
        kind=entry['kind']
        if kind not in kinds or kind in seen or entry['api']!=kinds[kind]:return False
        if denial!={'api':entry['api'],'action':'blocked'}:return False
        seen.add(kind)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',required=True,type=Path)
    args=parser.parse_args()
    evidence=args.evidence_dir.resolve()
    if evidence.is_relative_to(ROOT) or ROOT.is_relative_to(evidence):parser.error('evidence must be outside source')
    evidence.mkdir(parents=True,exist_ok=False)
    source=ROOT/'frontend'
    if any((source/name).exists() for name in ['.env','.env.local','.env.production','.env.production.local']):
        parser.error('unreviewed local Vite environment file; refuse to compile private values')
    allowed={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','PATHEXT','LANG','LC_ALL','LC_CTYPE','TZ'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(CI='true',UNI_INPUT_DIR=str(source),UNI_OUTPUT_DIR=str(evidence/'output'),UNI_PLATFORM='h5',NODE_ENV='production')
    def lines(path):return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
    def run(name,guard,arguments):
        child_env={**env,'CHECKPOINT_NODE_EVIDENCE':str(evidence/(name+'.denials.jsonl')),
                   'CHECKPOINT_COMPILER_EVIDENCE':str(evidence/(name+'.classified.jsonl'))}
        result=subprocess.run(['node','--require',str(guard),*arguments],cwd=source,env=child_env,
            capture_output=True,text=True,encoding='utf8',errors='replace',timeout=240)
        (evidence/(name+'.log')).write_text(result.stdout+result.stderr,encoding='utf8')
        return result,lines(evidence/(name+'.denials.jsonl')),lines(evidence/(name+'.classified.jsonl'))
    guard=HERE/'offline_node.cjs'
    before=sha256(guard.read_bytes()).hexdigest()
    manifest=source/'common/questionnaire-v3-manifest.js'
    manifest_before=sha256(manifest.read_bytes()).hexdigest()
    probe,_,_=run('original-guard',guard,[str(HERE/'node_guard_selftest.cjs')])
    assert probe.returncode==0 and '"guard_selftests_passed":5' in probe.stdout
    probe,denials,classified=run('compiler-guard',HERE/'compiler_node.cjs',[str(HERE/'compiler_guard_selftest.cjs')])
    assert probe.returncode==0 and '"compiler_guard_selftests_passed":9' in probe.stdout
    assert len(denials)==9 and all(row['action']=='blocked' for row in denials)
    assert Counter(row['kind'] for row in classified)=={'report_header':1,'network_drive_discovery':1}
    assert validate_compiler_denials([denials[0],denials[-1]],classified)
    assert not validate_compiler_denials(denials,classified), 'unknown denials must fail build acceptance'
    result,denials,classified=run('build',HERE/'compiler_node.cjs',[
        str(source/'node_modules/@dcloudio/vite-plugin-uni/bin/uni.js'),'build','-p','h5','--minify','esbuild'])
    assets=json.loads((ROOT/'docs/sprint7/S6_ASSET_RESTORE_MANIFEST_20261025.json').read_text(encoding='utf8'))['restored_files']
    verified=[];missing=[]
    for entry in assets:
        if not entry['path'].startswith('frontend/static/'):continue
        output=evidence/'output'/Path(entry['path']).relative_to('frontend')
        if not output.is_file() or sha256(output.read_bytes()).hexdigest()!=entry['sha256']:missing.append(entry['path'])
        else:verified.append(entry['path'])
    record=dict(compiler_exit_code=result.returncode,guard_unchanged=before==sha256(guard.read_bytes()).hexdigest(),
        questionnaire_manifest_unchanged=manifest_before==sha256(manifest.read_bytes()).hexdigest(),
        index_generated=(evidence/'output/index.html').is_file(),expected_blocked_probes=classified,
        denial_audit_valid=validate_compiler_denials(denials,classified),verified_static_assets=len(verified),
        missing_or_changed_assets=missing,unresolved_resource_warning="didn't resolve at build time" in result.stdout+result.stderr)
    passed=(result.returncode==0 and record['guard_unchanged'] and record['questionnaire_manifest_unchanged']
        and record['index_generated'] and record['denial_audit_valid'] and not missing and not record['unresolved_resource_warning'])
    record['status']='PASSED' if passed else 'FAILED'
    (evidence/'result.json').write_text(json.dumps(record,indent=2),encoding='utf8')
    print(json.dumps(record))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
