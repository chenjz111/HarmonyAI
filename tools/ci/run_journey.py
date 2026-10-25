"""Bounded stdio integration; unchanged Guards, no listening HTTP server."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

from run import environment, read_telemetry

ROOT=Path(__file__).resolve().parents[2]


@contextmanager
def child_deadline(children, seconds):
    expired=threading.Event()
    def terminate():
        expired.set()
        for child in tuple(children):
            if child.poll() is None:
                try:child.kill()
                except ProcessLookupError:pass
    timer=threading.Timer(seconds,terminate)
    timer.daemon=True
    timer.start()
    try:yield expired
    finally:timer.cancel()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',required=True,type=Path)
    args=parser.parse_args()
    evidence=args.evidence_dir.resolve()
    if evidence.is_relative_to(ROOT) or ROOT.is_relative_to(evidence):parser.error('evidence outside source required')
    evidence.mkdir(parents=True,exist_ok=False)
    sandbox=evidence/'sandbox';sandbox.mkdir()
    env=environment(ROOT,sandbox)
    env.update(CHECKPOINT_NODE_EVIDENCE=str(evidence/'node-denials.jsonl'),HARMONYAI_V3_MODE='real')
    events=queue.Queue();children=[];logs={'backend':[],'frontend':[]};trace=[]
    def launch(name,command,cwd):
        child=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',bufsize=1)
        children.append(child)
        if expired.is_set():
            child.kill();raise TimeoutError("integration deadline expired during child launch")
        def read():
            for line in child.stdout:events.put((name,line))
            events.put((name,None))
        threading.Thread(target=read,daemon=True).start()
        return child
    verified=set();passed=False
    with child_deadline(children,120) as expired:
        try:
            backend=launch('backend',[sys.executable,'-B',str(ROOT/'tools/ci/guarded_pytest.py'),
                '--source-root',str(ROOT),'--sandbox-root',str(sandbox),'--telemetry',str(evidence/'telemetry.json'),
                '--','-q','-s','-p','no:cacheprovider','--basetemp',str(sandbox/'pytest'),
                'tests/integration/s7_backend_stdio.py'],ROOT)
            frontend=None;deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                name,line=events.get(timeout=max(0.1,deadline-time.monotonic()))
                if line is None:
                    if name=='frontend' and 'S7_FRONTEND_VERIFIED' in verified:
                        backend.stdin.write('{"done":true}\n');backend.stdin.flush()
                    elif name=='backend' and 'S7_BACKEND_VERIFIED' in verified:break
                    else:raise RuntimeError(name+' exited before verification')
                    continue
                if line.startswith('S7_REQUEST '):
                    assert name=='frontend' and backend.poll() is None
                    value=json.loads(line[len('S7_REQUEST '):])
                    # Never retain credentials or response bodies in logs/artifacts.
                    trace.append({'method':value['method'],'path':value['path']})
                    print(json.dumps(trace[-1]),flush=True)
                    backend.stdin.write(json.dumps(value)+'\n');backend.stdin.flush()
                elif line.startswith('S7_RESPONSE '):
                    assert name=='backend' and frontend is not None
                    frontend.stdin.write(line[len('S7_RESPONSE '):]);frontend.stdin.flush()
                elif line.strip()=='S7_READY':
                    assert frontend is None
                    frontend=launch('frontend',['node','--require',str(ROOT/'tools/ci/offline_node.cjs'),
                        str(ROOT/'frontend/integration/s7-journey.mjs')],ROOT/'frontend')
                elif line.strip() in {'S7_FRONTEND_VERIFIED','S7_BACKEND_VERIFIED'}:verified.add(line.strip())
                else:
                    logs[name].append(re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED_JWT]',line))
                    (evidence/(name+'.log')).write_text(''.join(logs[name]),encoding='utf8')
            else:raise TimeoutError('integration exceeded120s')
            assert verified=={'S7_FRONTEND_VERIFIED','S7_BACKEND_VERIFIED'}
            assert all(child.wait(timeout=10)==0 for child in children)
            telemetry,error=read_telemetry(evidence/'telemetry.json')
            assert telemetry is not None and not error, error
            assert telemetry['exit_code']==0 and len(telemetry['tests'])==1
            assert not (evidence/'node-denials.jsonl').exists()
            assert not expired.is_set(),'integration watchdog expired'
            passed=True
        finally:
            for child in children:
                if child.poll() is None:child.kill()
                child.wait(timeout=10)
            for name,lines in logs.items():(evidence/(name+'.log')).write_text(''.join(lines),encoding='utf8')
            result={'status':'PASSED' if passed else 'FAILED','verified':sorted(verified),'requests':trace,
                    'transport':'stdio to actual ASGI; no HTTP sockets','device_audio':'NOT RUN',
                    'default_library_enabled':False,'registered_account_enabled':False}
            (evidence/'result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
            print(json.dumps({k:v for k,v in result.items() if k!='requests'}))


if __name__=='__main__':main()
