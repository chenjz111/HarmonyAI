"""Account R1 independent process refresh, bind and limit races on synthetic SQLite.

The trusted parent only orchestrates children. Every DB operation runs inside
the unchanged guard with its clean environment and per-scenario sandbox.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from run import ROOT, HERE, environment, read_telemetry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', required=True, type=Path)
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    if evidence.is_relative_to(ROOT) or ROOT.is_relative_to(evidence):
        parser.error('evidence must be outside source')
    evidence.mkdir(parents=True, exist_ok=False)
    records = []
    for scenario in ('refresh','bind','limit'):
        sandbox = evidence/scenario
        sandbox.mkdir()
        def launch(role):
            env = environment(ROOT, sandbox)
            env.update(HARMONY_FEEDBACK_ROLE=role, HARMONY_FEEDBACK_SCENARIO=scenario)
            command = [sys.executable,'-B',str(HERE/'guarded_pytest.py'),
                '--source-root',str(ROOT),'--sandbox-root',str(sandbox),
                '--telemetry',str(sandbox/f'{role}.telemetry.json'),'--',
                '-q','-p','no:cacheprovider','--basetemp',str(sandbox/f'pytest-{role}'),
                str(HERE/'probes/account_process.py'),'--tb=short']
            return subprocess.Popen(command, cwd=ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def finish(role, child):
            output, _ = child.communicate(timeout=90)
            (evidence/f'{scenario}-{role}.log').write_bytes(output)
            telemetry, error = read_telemetry(sandbox/f'{role}.telemetry.json')
            if child.returncode or error or telemetry['exit_code'] or len(telemetry['tests']) != 1:
                raise RuntimeError(f'guarded {scenario}/{role} failed; inspect evidence')
        finish('setup', launch('setup'))
        workers = [(role, launch(role)) for role in ('a','b')]
        try:
            for role, child in workers:
                finish(role, child)
        finally:
            for _, child in workers:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
        rows = [json.loads((sandbox/f'{role}.result.json').read_text(encoding='utf-8')) for role in ('a','b')]
        assert sorted(row['status'] for row in rows)==['denied','success']
        finish('verify',launch('verify'))
        records.append(dict(scenario=scenario, results=rows, guarded_processes=4))
    (evidence/'result.json').write_text(json.dumps(dict(status='PASSED', scenarios=records), indent=2), encoding='utf-8')
    print(json.dumps(dict(status='PASSED', scenarios=len(records), guarded_processes=4*len(records))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
