"""Trusted launcher: fixed suites, clean synthetic env, guarded child, raw evidence."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HARDENING = 'tests/api/v3/test_runtime_auth_config_hardening.py'
BE2B = 'tests/api/v3/test_be2b_playback_proof_cas.py'
BE2B_EXPECTED_PASSED = 45
FEEDBACK_INVENTORY = {
    'tests/api/v3/test_0013_feedback_foundation.py': 13,
    'tests/api/v3/test_0013_mysql_contract.py': 22,
    'tests/api/v3/test_mysql_migration_statements.py': 11,
    'tests/api/v3/test_feedback_v31_transactions.py': 15,
    'tests/api/v3/test_feedback_clear_receipt.py': 5,
    'tests/api/v3/test_feedback_v31_api.py': 6,
}
ACCOUNT_INVENTORY = {
    'tests/api/v3/test_identity_continuity.py':2,
    'tests/api/v3/test_0014_account_security.py':13,
    'tests/api/v3/test_account_password_r1.py':17,
    'tests/api/v3/test_account_security_r1.py':13,
    'tests/api/v3/test_account_session_r1.py':15,
    'tests/api/v3/test_account_router_r1.py':7,
    'tests/api/v3/test_account_browser_gate.py':7,
}
REGRESSION = ['tests/api/v3/' + name for name in (
    'test_s7_music_library_router_wiring.py', 'test_s7_music_library.py',
    'test_s7_music_library_api.py', 'test_int2_stream_gate.py', 'test_guest_auth.py',
    'test_int2_favorite_epoch.py', 'test_feedback.py', 'test_generation.py')]

# Load only the trusted guard module's public schema constants. Its audit hooks
# are installed by main(), never by import; no duplicate allow/skip policy here.
_schema_spec = importlib.util.spec_from_file_location('ci_guard_schema', HERE/'guarded_pytest.py')
_guard_schema = importlib.util.module_from_spec(_schema_spec)
_schema_spec.loader.exec_module(_guard_schema)


def environment(source, sandbox):
    # Inherit runtime essentials, not an open-ended credential-name blacklist.
    # No user profiles, cloud config paths, CI credentials or Python startup
    # settings are inherited. The child executable is an absolute trusted path.
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'PATHEXT', 'TEMP', 'TMP',
               'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ'}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(APP_ENV='development', DEBUG='false',
               DATABASE_URL='sqlite:///' + str(sandbox/'unused.sqlite'),
               JWT_SECRET_KEY='ci-synthetic-key-0123456789-0123456789',
               JWT_ALGORITHM='HS256', CORS_ORIGINS='["*"]',
               MUSIC_PROVIDER='not-configured', PYTHONDONTWRITEBYTECODE='1',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONPATH=str(source),
               CI_DB_SANDBOX=str(sandbox), HARMONY_MEDIA_ROOT=str(sandbox/'pytest'))
    return env


def read_telemetry(path):
    """Validate the child record before trusting counts or a successful exit."""
    if not path.is_file():
        return None, 'telemetry_missing'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('record shape')
        for key in ('pytest_exit_code', 'exit_code', 'real_network_connections'):
            if type(data.get(key)) is not int:
                raise ValueError('exit/network type')
        if data['pytest_exit_code'] not in range(6) or data['real_network_connections'] != 0:
            raise ValueError('exit/network value')
        if type(data.get('selftest_complete')) is not bool:
            raise ValueError('selftest type')
        for key in ('tests', 'denials', 'unrecognized_denials', 'unexpected_skips',
                    'permitted_internal_socketpair_events'):
            if not isinstance(data.get(key), list):
                raise ValueError('list shape')
        for row in data['denials']:
            if not isinstance(row, dict) or not all(
                    isinstance(row.get(key), str) and row[key]
                    for key in ('api', 'action', 'classification')):
                raise ValueError('denial shape')
            label, api = row['classification'], row['api']
            if row['action'] != 'blocked_before_system_call':
                raise ValueError('denial action')
            if label.startswith('blocked_selftest:'):
                if _guard_schema.EXPECTED.get(label.split(':', 1)[1]) != api:
                    raise ValueError('selftest classification')
            elif label == 'blocked_verified_urllib3_ipv6_probe':
                if api != 'socket.bind':
                    raise ValueError('import probe classification')
            elif label != 'blocked_unrecognized':
                raise ValueError('unknown classification')
        unknown = [row for row in data['denials']
                   if row['classification'] == 'blocked_unrecognized']
        if unknown != data['unrecognized_denials']:
            raise ValueError('denial disagreement')
        if not all(isinstance(node, str) and node for node in data['unexpected_skips']):
            raise ValueError('skip shape')
        for row in data['permitted_internal_socketpair_events']:
            if (not isinstance(row, dict) or row.get('api') not in {'socket.bind', 'socket.connect'}
                    or row.get('scope') != 'verified_stdlib_socketpair'):
                raise ValueError('socketpair shape')
        for row in data['tests']:
            if (not isinstance(row, dict) or not isinstance(row.get('nodeid'), str)
                    or not row['nodeid'] or row.get('phase') not in {'collect', 'setup', 'call', 'teardown'}
                    or row.get('outcome') not in {'passed', 'failed', 'skipped'}
                    or (row['outcome'] == 'passed' and row['phase'] != 'call')
                    or type(row.get('duration')) not in (int, float)
                    or not math.isfinite(row['duration']) or row['duration'] < 0):
                raise ValueError('test row shape')
        unexpected = {row['nodeid'].replace('\\', '/') for row in data['tests']
                      if row['outcome'] == 'skipped' and not (
                          sys.platform == 'win32' and row['phase'] != 'collect'
                          and row['nodeid'].replace('\\', '/') in _guard_schema.ALLOWED_WINDOWS_SKIPS)}
        if unexpected != set(data['unexpected_skips']):
            raise ValueError('skip ledger disagreement')
        if data['pytest_exit_code'] == 0 and (not data['tests'] or any(
                row['outcome'] == 'failed' for row in data['tests'])):
            raise ValueError('successful pytest/count disagreement')
        expected = (90 if unknown or not data['selftest_complete'] else
                    91 if data['unexpected_skips'] else data['pytest_exit_code'])
        if data['exit_code'] != expected:
            raise ValueError('guard exit disagreement')
        return data, None
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError):
        # Do not echo untrusted telemetry or exception values into public logs.
        return None, 'telemetry_invalid'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', required=True, choices=('guard', 'regression', 'hardening', 'be2b', 'feedback', 'account'))
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve(strict=True)
    evidence = args.evidence_dir.resolve()
    if evidence.is_relative_to(source) or source.is_relative_to(evidence):
        parser.error('Evidence must be outside the source tree')
    evidence.mkdir(parents=True, exist_ok=False)
    if args.suite == 'hardening' and not (source/HARDENING).is_file():
        record = {'status': 'NOT_INCLUDED', 'suite': args.suite, 'passed': None,
                  'failed': None, 'skipped': None, 'exit_code': 0,
                  'reason': 'This change does not include the runtime hardening specialty',
                  'child_exit_code': None, 'final_exit_code': 0, 'failure_reason': None}
    else:
        sandbox = evidence/'sandbox'
        sandbox.mkdir()
        inventory = ACCOUNT_INVENTORY if args.suite == 'account' else FEEDBACK_INVENTORY
        tests = ([str(HERE/'tests/test_guard.py')] if args.suite == 'guard'
                 else [HARDENING] if args.suite == 'hardening'
                 else list(inventory) if args.suite in {'feedback','account'}
                 else [BE2B] if args.suite == 'be2b' else REGRESSION)
        missing = [test for test in tests if not (source/test).is_file()]
        if missing:
            parser.error('Required suite files missing: ' + ', '.join(missing))
        command = [sys.executable, '-B', str(HERE/'guarded_pytest.py'),
                   '--source-root', str(source), '--sandbox-root', str(sandbox),
                   '--telemetry', str(evidence/'telemetry.json')]
        if args.suite == 'guard':
            command += ['--selftest']
        command += ['--', '-q', '-p', 'no:cacheprovider', '--basetemp',
                    str(sandbox/'pytest'), *tests, '-rs', '--tb=short']
        start = time.monotonic()
        child_code, timed_out = None, False
        try:
            result = subprocess.run(command, cwd=source, env=environment(source, sandbox),
                                    capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=240)
            child_code, output = result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            def decode(value):
                return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
            timed_out = True
            output = decode(error.stdout) + decode(error.stderr) + '\nTIMEOUT_240_SECONDS\n'
        output = re.sub(r'eyJ[A-Za-z0-9_.-]+', '[SYNTHETIC_JWT_REDACTED]', output)
        (evidence/'pytest.log').write_text(output, encoding='utf-8')
        details, telemetry_error = read_telemetry(evidence/'telemetry.json')
        if timed_out:
            code, reason = 124, 'timeout'
        elif child_code != 0:
            code, reason = child_code, 'child_nonzero'
        elif telemetry_error:
            code, reason = 92, telemetry_error
        elif details['unrecognized_denials'] or not details['selftest_complete']:
            code, reason = 90, 'guard_denial'
        elif details['unexpected_skips']:
            code, reason = 91, 'unexpected_skip'
        elif details['exit_code'] != child_code:
            code, reason = 92, 'telemetry_exit_mismatch'
        elif args.suite == 'be2b' and (
                len(details['tests']) != BE2B_EXPECTED_PASSED
                or len({row['nodeid'] for row in details['tests']
                        if row['phase'] == 'call' and row['outcome'] == 'passed'
                        and row['nodeid'].replace('\\', '/').split('::', 1)[0] == BE2B}) != BE2B_EXPECTED_PASSED):
            # Pin the reviewed R1 inventory: no partial/duplicate/foreign tests.
            code, reason = 93, 'be2b_acceptance_mismatch'
        elif args.suite in {'feedback','account'} and (
                len(details['tests']) != sum(inventory.values())
                or any(len({row['nodeid'] for row in details['tests']
                            if row['phase'] == 'call' and row['outcome'] == 'passed'
                            and row['nodeid'].replace('\\', '/').split('::', 1)[0] == path}) != count
                       for path, count in inventory.items())):
            code, reason = 93, args.suite+'_acceptance_mismatch'
        else:
            code, reason = 0, None
        exits = {'child_exit_code': child_code, 'final_exit_code': code,
                 'exit_code': code, 'failure_reason': reason}
        metadata = {'command': command, 'cwd': str(source), **exits,
                    'timed_out': timed_out, 'telemetry_error': telemetry_error,
                    'duration_seconds': round(time.monotonic()-start, 3)}
        (evidence/'command.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        rows = details['tests'] if details else []
        record = {'status': 'PASSED' if code == 0 else 'FAILED', 'suite': args.suite,
                  **exits, 'timed_out': timed_out, 'telemetry_error': telemetry_error,
                  'passed': sum(r['outcome'] == 'passed' for r in rows) if details else None,
                  'failed': sum(r['outcome'] == 'failed' for r in rows) if details else None,
                  'skipped': sum(r['outcome'] == 'skipped' for r in rows) if details else None}
        print(output)
    (evidence/'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('\n### ' + args.suite + '\n\n```json\n' + json.dumps(record) + '\n```\n')
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
