"""Trusted orchestration tests: all generated pytest probes run under the guard."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import sqlite3
import contextlib
import importlib.util
import io
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harmonyai-guard-check-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def invoke(self, script, *args):
        # This prerequisite fails safely during RED, before any probe can run.
        self.assertTrue((TOOLS / script).is_file(), 'portable guarded runner not implemented')
        env = {k: v for k, v in os.environ.items()
               if not any(word in k.upper() for word in
                          ('TOKEN', 'SECRET', 'PASSWORD', 'KEY', 'PROXY', 'DATABASE', 'MYSQL'))}
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        return subprocess.run([sys.executable, str(TOOLS/script), *map(str, args)],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)

    def probe(self, body, extra=()):
        test = self.folder / 'test_probe.py'
        test.write_text(body, encoding='utf-8')
        sandbox = self.folder / 'sandbox'
        sandbox.mkdir()
        telemetry = self.folder / 'telemetry.json'
        result = self.invoke('guarded_pytest.py', '--source-root', ROOT,
                             '--sandbox-root', sandbox, '--telemetry', telemetry,
                             '--', '-q', '-p', 'no:cacheprovider', str(test), *extra)
        return result, json.loads(telemetry.read_text(encoding='utf-8'))

    def test_guard_suite_runs_and_records_expected_denials(self):
        evidence = self.folder/'evidence'
        result = self.invoke('run.py', '--suite', 'guard', '--evidence-dir', evidence)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'PASSED')
        self.assertGreaterEqual(record['passed'], 10)
        self.assertEqual(record['failed'], 0)

    def test_guard_selftests_refuse_unguarded_execution(self):
        result = self.invoke('tests/test_guard.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('guarded runner', result.stderr)

    def test_caught_unknown_socket_attempt_still_fails_process(self):
        result, record = self.probe('''import socket, sys
def test_caught():
    sock = socket.socket()
    try:
        try: sys.audit('socket.connect', sock, ('192.0.2.1', 443))
        except RuntimeError: pass
    finally: sock.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)
        self.assertEqual(record['pytest_exit_code'], 0)
        self.assertTrue(record['unrecognized_denials'])

    def test_caught_unknown_database_attempt_still_fails_process(self):
        result, record = self.probe('''import sys
def test_caught():
    try: sys.audit('sqlite3.connect', '/unapproved/synthetic.sqlite')
    except RuntimeError: pass
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)
        self.assertTrue(record['unrecognized_denials'])

    def test_empty_database_connect_is_denied_and_fatal_even_if_caught(self):
        result, record = self.probe('''import sqlite3
def test_empty():
    try: db = sqlite3.connect('')
    except RuntimeError: pass
    else: db.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)
        self.assertEqual(record['pytest_exit_code'], 0)
        self.assertTrue(any(row['api'] == 'sqlite3.connect'
                            for row in record['unrecognized_denials']))

    def test_empty_database_attach_is_denied_and_fatal_even_if_caught(self):
        result, record = self.probe('''import sqlite3
def test_empty():
    db = sqlite3.connect(':memory:')
    try:
        try: db.execute("ATTACH DATABASE '' AS external")
        except sqlite3.DatabaseError: pass
    finally: db.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)
        self.assertEqual(record['pytest_exit_code'], 0)
        self.assertTrue(any(row['api'] == 'sqlite3.attach'
                            for row in record['unrecognized_denials']))

    def test_credential_paths_do_not_reach_protected_child(self):
        names = ('GOOGLE_APPLICATION_CREDENTIALS', 'AWS_SHARED_CREDENTIALS_FILE',
                 'AWS_CONFIG_FILE', 'AZURE_CONFIG_DIR', 'KUBECONFIG',
                 'BOTO_CONFIG', 'NETRC', 'SYNTHETIC_UNAPPROVED_SETTING')
        source = self.folder/'source'
        test = source/'tests/api/v3/test_runtime_auth_config_hardening.py'
        test.parent.mkdir(parents=True)
        test.write_text('import os\ndef test_environment():\n'
                        '    present = [name for name in ' + repr(names) + ' if name in os.environ]\n'
                        '    assert present == [], "inherited variable names: " + repr(present)\n'
                        '    assert os.environ["APP_ENV"] == "development"\n'
                        '    assert os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"\n',
                        encoding='utf-8')
        evidence = self.folder/'environment'
        with patch.dict(os.environ, {name: 'synthetic-not-a-real-credential' for name in names}):
            result = self.invoke('run.py', '--suite', 'hardening', '--source-root', source,
                                 '--evidence-dir', evidence)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['passed'], 1)
        self.assertEqual(record['failed'], 0)

    def test_pytest_failure_is_not_swallowed(self):
        result, record = self.probe('def test_failure():\n    assert False, "synthetic failure"\n')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(record['pytest_exit_code'], 1)

    def test_collection_skip_is_not_hidden_by_a_passing_module(self):
        skipped = self.folder/'test_collection_skip.py'
        skipped.write_text('import pytest\npytest.skip("module skipped", allow_module_level=True)\n', encoding='utf-8')
        result, record = self.probe('def test_healthy():\n    assert True\n', [str(skipped)])
        self.assertEqual(result.returncode, 91, result.stdout + result.stderr)
        self.assertTrue(record['unexpected_skips'])

    def test_unexpected_runtime_skip_is_nonzero(self):
        result, record = self.probe('import pytest\ndef test_skip():\n    pytest.skip("unexpected skip")\n')
        self.assertEqual(result.returncode, 91, result.stdout + result.stderr)

    def test_readonly_attach_cannot_escape_database_scope(self):
        target = self.folder/'synthetic-source.sqlite'
        connection = sqlite3.connect(target)
        connection.execute('CREATE TABLE proof(value INTEGER)')
        connection.execute('INSERT INTO proof VALUES(42)')
        connection.commit()
        connection.close()
        # Existing, synthetic fixture only; RED is a read-only scope probe.
        uri = 'file:' + target.as_posix() + '?mode=ro'
        result, record = self.probe('''import sqlite3
def test_attach():
    db = sqlite3.connect(':memory:')
    try:
        try: db.execute('ATTACH DATABASE ? AS external', (''' + repr(uri) + ''',))
        except sqlite3.DatabaseError: pass
        else: assert db.execute('SELECT value FROM external.proof').fetchone() == (42,)
    finally: db.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)
        self.assertTrue(record['unrecognized_denials'])

    def test_vacuum_cannot_write_outside_database_scope(self):
        target = self.folder/'not-created.sqlite'
        result, record = self.probe('''import sqlite3
def test_vacuum():
    db = sqlite3.connect(':memory:')
    try:
        try: db.execute('VACUUM INTO ?', (''' + repr(str(target)) + ''',))
        except sqlite3.DatabaseError: pass
    finally: db.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)
        self.assertFalse(target.exists())

    def test_reverse_dns_audit_is_blocked_without_actual_dns(self):
        result, record = self.probe('''import sys
def test_lookup():
    try: sys.audit('socket.getnameinfo', ('192.0.2.1', 443))
    except RuntimeError: pass
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)

    def test_sqlite_enable_extension_audit_is_blocked(self):
        result, record = self.probe('''import sys, sqlite3
def test_extension():
    db = sqlite3.connect(':memory:')
    try:
        try: sys.audit('sqlite3.enable_load_extension', db, True)
        except RuntimeError: pass
    finally: db.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)

    def test_sqlite_load_extension_audit_is_blocked(self):
        result, record = self.probe('''import sys, sqlite3
def test_extension():
    db = sqlite3.connect(':memory:')
    try:
        try: sys.audit('sqlite3.load_extension', db, 'synthetic-unavailable')
        except RuntimeError: pass
    finally: db.close()
''')
        self.assertEqual(result.returncode, 90, result.stdout + result.stderr)

    def test_guard_rejects_missing_or_unsafe_roots(self):
        result = self.invoke('guarded_pytest.py', '--source-root', ROOT,
                             '--sandbox-root', ROOT, '--telemetry', self.folder/'unused.json', '--', '-q')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.folder/'unused.json').exists())

    def test_absent_specialty_is_not_reported_as_passed(self):
        source = self.folder/'source'
        source.mkdir()
        evidence = self.folder/'absent'
        result = self.invoke('run.py', '--suite', 'hardening', '--source-root', source,
                             '--evidence-dir', evidence)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'NOT_INCLUDED')
        self.assertIsNone(record['passed'])
        self.assertIn('NOT_INCLUDED', result.stdout)

    def test_present_specialty_cannot_be_skipped(self):
        source = self.folder/'source'
        test = source/'tests/api/v3/test_runtime_auth_config_hardening.py'
        test.parent.mkdir(parents=True)
        test.write_text('def test_specialty():\n    assert False, "must execute"\n', encoding='utf-8')
        evidence = self.folder/'present'
        result = self.invoke('run.py', '--suite', 'hardening', '--source-root', source,
                             '--evidence-dir', evidence)
        self.assertNotEqual(result.returncode, 0)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['failed'], 1)

    def be2b_probe(self, body):
        """Synthetic launcher contract probes, not the 45 real BE-2B tests."""
        source = self.folder/'be2b-source'
        source.mkdir()
        (source/'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
        if body is not None:
            test = source/'tests/api/v3/test_be2b_playback_proof_cas.py'
            test.parent.mkdir(parents=True)
            test.write_text(body, encoding='utf-8')
        evidence = self.folder/'be2b-evidence'
        result = self.invoke('run.py', '--suite', 'be2b', '--source-root', source,
                             '--evidence-dir', evidence)
        return result, evidence

    def test_be2b_missing_test_fails_instead_of_not_included(self):
        result, evidence = self.be2b_probe(None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Required suite files missing', result.stderr)
        self.assertNotIn('NOT_INCLUDED', result.stdout)
        self.assertFalse((evidence/'result.json').exists())

    def test_feedback_missing_suite_refuses_instead_of_silent_success(self):
        source = self.folder/'feedback-source'
        source.mkdir()
        evidence = self.folder/'feedback-evidence'
        result = self.invoke('run.py', '--suite', 'feedback', '--source-root', source,
                             '--evidence-dir', evidence)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Required suite files missing', result.stderr)
        self.assertNotIn('NOT_INCLUDED', result.stdout)

    def test_be2b_runs_fixed_path_under_guard_and_requires_45_passes(self):
        body = 'import pytest\n@pytest.mark.parametrize("case", range(45))\ndef test_case(case):\n    assert case >= 0\n'
        result, evidence = self.be2b_probe(body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual((record['passed'], record['failed'], record['skipped']), (45, 0, 0))
        self.assertEqual(record['status'], 'PASSED')
        command = json.loads((evidence/'command.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(command['command'][2]), TOOLS/'guarded_pytest.py')
        self.assertIn('tests/api/v3/test_be2b_playback_proof_cas.py', command['command'])

    def test_be2b_reduced_test_count_is_nonzero_even_when_child_passes(self):
        body = 'import pytest\n@pytest.mark.parametrize("case", range(44))\ndef test_case(case):\n    assert case >= 0\n'
        result, evidence = self.be2b_probe(body)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((evidence/'result.json').is_file(), result.stdout + result.stderr)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['child_exit_code'], 0)
        self.assertEqual(record['passed'], 44)
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['failure_reason'], 'be2b_acceptance_mismatch')

    def test_be2b_test_failure_propagates(self):
        result, evidence = self.be2b_probe('def test_failure():\n    assert False, "synthetic BE-2B failure"\n')
        self.assertEqual(result.returncode, 1)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual((record['child_exit_code'], record['final_exit_code']), (1, 1))
        self.assertEqual(record['failed'], 1)

    def test_be2b_collection_failure_propagates(self):
        result, evidence = self.be2b_probe('raise RuntimeError("synthetic collection failure")\n')
        self.assertEqual(result.returncode, 2)
        self.assertTrue((evidence/'result.json').is_file(), result.stdout + result.stderr)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['failure_reason'], 'child_nonzero')
        self.assertEqual(record['failed'], 1)

    def test_be2b_runtime_skip_is_not_a_green_specialty(self):
        result, evidence = self.be2b_probe('import pytest\ndef test_skip():\n    pytest.skip("synthetic unexpected skip")\n')
        self.assertEqual(result.returncode, 91)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['skipped'], 1)

    def test_be2b_caught_guard_denial_is_still_nonzero(self):
        result, evidence = self.be2b_probe('import socket, sys\ndef test_caught():\n'
            '    sock = socket.socket()\n    try:\n'
            '        try: sys.audit("socket.connect", sock, ("192.0.2.1", 443))\n'
            '        except RuntimeError: pass\n    finally: sock.close()\n')
        self.assertEqual(result.returncode, 90)
        record = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['passed'], 1)
        telemetry = json.loads((evidence/'telemetry.json').read_text(encoding='utf-8'))
        self.assertEqual(telemetry['pytest_exit_code'], 0)
        self.assertTrue(telemetry['unrecognized_denials'])


class ReliabilityTests(unittest.TestCase):
    """Injected transport/filesystem outcomes, not real network/timeout evidence."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harmonyai-ci-fault-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder/'source'
        test = self.source/'tests/api/v3/test_runtime_auth_config_hardening.py'
        test.parent.mkdir(parents=True)
        test.write_text('def test_synthetic():\n    assert True\n', encoding='utf-8')
        spec = importlib.util.spec_from_file_location('reliability_launcher', TOOLS/'run.py')
        self.launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.launcher)

    def telemetry(self):
        return {'pytest_exit_code': 0, 'exit_code': 0, 'denials': [],
                'unrecognized_denials': [], 'selftest_complete': True,
                'unexpected_skips': [], 'permitted_internal_socketpair_events': [],
                'real_network_connections': 0,
                'tests': [{'nodeid': 'test_synthetic.py::test_ok', 'phase': 'call',
                           'outcome': 'passed', 'duration': 0.01}]}

    def inject(self, payload, child=0, timeout=False):
        evidence = self.folder/'evidence'
        def fake_child(command, **kwargs):
            self.assertEqual(Path(command[2]), TOOLS/'guarded_pytest.py')
            self.assertEqual(kwargs['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'], '1')
            if payload is not None:
                (evidence/'telemetry.json').write_text(
                    payload if isinstance(payload, str) else json.dumps(payload), encoding='utf-8')
            if timeout:
                raise subprocess.TimeoutExpired(command, 240, output=b'synthetic partial output')
            return subprocess.CompletedProcess(command, child, 'synthetic child output', '')
        argv = ['run.py', '--suite', 'hardening', '--source-root', str(self.source),
                '--evidence-dir', str(evidence)]
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, {}, clear=True), \
                patch.object(self.launcher.subprocess, 'run', side_effect=fake_child), \
                contextlib.redirect_stdout(io.StringIO()):
            code = self.launcher.main()
        metadata = json.loads((evidence/'command.json').read_text(encoding='utf-8'))
        result = json.loads((evidence/'result.json').read_text(encoding='utf-8'))
        return code, metadata, result

    def assert_codes(self, observed, child, final, reason):
        code, metadata, result = observed
        self.assertEqual(code, final)
        for record in (metadata, result):
            self.assertEqual(record['child_exit_code'], child)
            self.assertEqual(record['final_exit_code'], final)
            self.assertEqual(record['exit_code'], final)
            self.assertEqual(record['failure_reason'], reason)
        self.assertEqual(result['status'], 'PASSED' if final == 0 else 'FAILED')

    def test_valid_telemetry_records_both_exit_codes(self):
        self.assert_codes(self.inject(self.telemetry()), 0, 0, None)

    def test_nonzero_child_is_preserved_without_telemetry(self):
        self.assert_codes(self.inject(None, child=7), 7, 7, 'child_nonzero')

    def test_timeout_has_no_confirmed_child_exit_and_final_124(self):
        self.assert_codes(self.inject(None, timeout=True), None, 124, 'timeout')

    def test_timeout_cannot_be_overridden_by_passing_telemetry(self):
        self.assert_codes(self.inject(self.telemetry(), timeout=True), None, 124, 'timeout')

    def test_missing_telemetry_cannot_record_success(self):
        self.assert_codes(self.inject(None), 0, 92, 'telemetry_missing')

    def test_corrupt_json_is_recorded_not_an_unhandled_exception(self):
        self.assert_codes(self.inject('{invalid'), 0, 92, 'telemetry_invalid')

    def test_wrong_telemetry_shape_is_rejected(self):
        self.assert_codes(self.inject([]), 0, 92, 'telemetry_invalid')

    def test_telemetry_exit_mismatch_is_rejected(self):
        data = self.telemetry()
        data['pytest_exit_code'] = data['exit_code'] = 1
        data['tests'][0]['outcome'] = 'failed'
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_exit_mismatch')

    def test_unknown_denial_overrides_claimed_success(self):
        data = self.telemetry()
        denial = {'api': 'socket.connect', 'action': 'blocked_before_system_call',
                  'classification': 'blocked_unrecognized'}
        data['denials'] = data['unrecognized_denials'] = [denial]
        data['exit_code'] = 90
        self.assert_codes(self.inject(data), 0, 90, 'guard_denial')

    def test_incomplete_selftest_cannot_record_success(self):
        data = self.telemetry()
        data['selftest_complete'] = False
        data['exit_code'] = 90
        self.assert_codes(self.inject(data), 0, 90, 'guard_denial')

    def test_unexpected_skip_cannot_record_success(self):
        data = self.telemetry()
        data['tests'][0]['outcome'] = 'skipped'
        data['tests'][0]['nodeid'] = 'test_synthetic.py::test_skip'
        data['unexpected_skips'] = ['test_synthetic.py::test_skip']
        data['exit_code'] = 91
        self.assert_codes(self.inject(data), 0, 91, 'unexpected_skip')

    def test_failed_row_cannot_hide_behind_zero_pytest_exit(self):
        data = self.telemetry()
        data['tests'][0]['outcome'] = 'failed'
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')

    def test_missing_tests_cannot_be_reported_as_passed(self):
        data = self.telemetry()
        data['tests'] = []
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')

    def test_inconsistent_denial_list_is_rejected(self):
        data = self.telemetry()
        data['denials'] = [{'api': 'socket.connect', 'action': 'blocked_before_system_call',
                           'classification': 'blocked_unrecognized'}]
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')

    def test_unknown_denial_classification_is_corrupt_telemetry(self):
        data = self.telemetry()
        data['denials'] = [{'api': 'socket.connect', 'action': 'blocked_before_system_call',
                           'classification': 'blocked_typo'}]
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')

    def test_oversized_duration_is_recorded_as_corrupt_telemetry(self):
        data = self.telemetry()
        data['tests'][0]['duration'] = 10**400
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')

    def test_setup_only_record_cannot_claim_test_execution(self):
        data = self.telemetry()
        data['tests'][0]['phase'] = 'setup'
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')

    def test_unapproved_skip_cannot_hide_from_skip_ledger(self):
        data = self.telemetry()
        data['tests'][0]['outcome'] = 'skipped'
        self.assert_codes(self.inject(data), 0, 92, 'telemetry_invalid')


if __name__ == '__main__':
    unittest.main()
