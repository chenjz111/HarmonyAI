"""Protected pytest child. No install/network fallback; unknown denials are fatal.

Port of the reviewed checkpoint guard plus its SQLite sandbox. Python audit
hooks protect this cooperative test process, not hostile native/ctypes code.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import socket
import sqlite3
import sys
import sysconfig

HERE = Path(__file__).resolve().parent
SELFTEST_FILE = HERE/'tests/test_guard.py'
EXPECTED = {
    'test_external_tcp_blocked': 'socket.connect',
    'test_local_service_blocked': 'socket.connect',
    'test_dns_blocked': 'socket.getaddrinfo',
    'test_host_name_lookup_blocked': 'socket.gethostbyname',
    'test_reverse_lookup_blocked': 'socket.gethostbyaddr',
    'test_getnameinfo_blocked': 'socket.getnameinfo',
    'test_bind_blocked': 'socket.bind',
    'test_datagram_blocked': 'socket.sendto',
    'test_subprocess_blocked': 'subprocess.Popen',
    'test_shell_blocked': 'os.system',
    'test_database_outside_sandbox_blocked': 'sqlite3.connect',
    'test_database_uri_blocked': 'sqlite3.connect',
    'test_database_empty_blocked': 'sqlite3.connect',
    'test_database_attach_empty_blocked': 'sqlite3.attach',
    'test_database_attach_outside_blocked': 'sqlite3.attach',
    'test_database_vacuum_outside_blocked': 'sqlite3.attach',
    'test_enable_extension_blocked': 'sqlite3.enable_load_extension',
    'test_load_extension_blocked': 'sqlite3.load_extension',
    'test_sql_load_extension_blocked': 'sqlite3.load_extension',
}
SOCKET_PROCESS_EVENTS = {
    'socket.connect', 'socket.bind', 'socket.getaddrinfo', 'socket.gethostbyname',
    'socket.gethostbyaddr', 'socket.getnameinfo', 'socket.sendto', 'socket.sendmsg', 'subprocess.Popen',
    'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn', 'os.startfile',
    '_winapi.CreateProcess', 'os.fork',
}
ALLOWED_WINDOWS_SKIPS = {
    'tests/api/v3/test_s7_music_library.py::test_symlink_escape_is_not_read',
    'tests/api/v3/test_int2_stream_gate.py::test_symlink_escape_is_denied_without_opening_target',
}


class OfflineGuard:
    def __init__(self, sandbox, selftest):
        self.sandbox, self.selftest = sandbox, selftest
        self.denials, self.internal_events = [], []
        fallback = getattr(socket, '_fallback_socketpair', None)
        self.fallback_code = getattr(fallback, '__code__', None)
        if self.fallback_code is not None:
            expected = Path(sysconfig.get_path('stdlib'))/'socket.py'
            if Path(self.fallback_code.co_filename).resolve() != expected.resolve():
                raise RuntimeError('Unverified standard-library socketpair implementation')

    def internal_socketpair(self, event, args, caller):
        # On Unix the native socketpair needs no bind/connect exception.
        if self.fallback_code is None or caller.f_code is not self.fallback_code:
            return False
        if event not in {'socket.bind', 'socket.connect'}:
            return False
        local = caller.f_locals
        listener = local.get('lsock')
        if listener is None or listener.family not in {socket.AF_INET, socket.AF_INET6}:
            return False
        host = socket._LOCALHOST if listener.family == socket.AF_INET else socket._LOCALHOST_V6
        if event == 'socket.bind':
            return args[0] is listener and args[1] == (host, 0)
        destination = listener.getsockname()[:2]
        return (args[0] is local.get('csock') and tuple(args[1][:2]) == destination
                and destination[0] == host and destination[1] != 0)

    def classification(self, event, args, caller):
        module = sys.modules.get('urllib3.util.connection')
        probe = getattr(module, '_has_ipv6', None)
        installed = {Path(sysconfig.get_path(key)).resolve()/'urllib3/util/connection.py'
                     for key in ('purelib', 'platlib')}
        if (event == 'socket.bind' and probe is not None
                and caller.f_code is probe.__code__
                and Path(caller.f_code.co_filename).resolve() in installed
                and args[0] is caller.f_locals.get('sock')
                and args[0].family == socket.AF_INET6
                and args[0].type == socket.SOCK_STREAM and args[1] == ('::1', 0)):
            # Still BLOCKED; classification only prevents this known import
            # capability probe from invalidating otherwise offline tests.
            return 'blocked_verified_urllib3_ipv6_probe'
        if self.selftest:
            frame = caller
            for _ in range(8):
                if frame is None:
                    break
                if (Path(frame.f_code.co_filename).resolve() == SELFTEST_FILE.resolve()
                        and EXPECTED.get(frame.f_code.co_name) == event):
                    return 'blocked_selftest:' + frame.f_code.co_name
                frame = frame.f_back
        return 'blocked_unrecognized'

    def audit(self, event, args):
        if event == 'sqlite3.connect':
            if self.allowed_sqlite_target(args[0]):
                return
        elif event in {'sqlite3.enable_load_extension', 'sqlite3.load_extension'}:
            pass  # Explicitly denied; never permit native extension loading.
        elif event in SOCKET_PROCESS_EVENTS:
            if self.internal_socketpair(event, args, sys._getframe(1)):
                self.internal_events.append({'api': event, 'scope': 'verified_stdlib_socketpair'})
                return
        else:
            return
        label = self.classification(event, args, sys._getframe(1))
        # Never retain addresses, DB locators, subprocess argv or credentials.
        self.denials.append({'api': event, 'action': 'blocked_before_system_call',
                             'classification': label})
        raise RuntimeError('CI offline guard blocked operation')

    def protect_sqlite_constructors(self):
        # CPython emits connect/handle BEFORE Connection.__init__ completes;
        # set_authorizer is not legal in that audit callback. Install it in a
        # forced factory immediately after the real constructor returns instead.
        base, original, guard = sqlite3.Connection, sqlite3.connect, self

        class GuardedConnection(base):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                base.set_authorizer(self, guard.authorize_sqlite)

            def set_authorizer(self, callback):
                guard.denials.append({'api': 'ci.sqlite_authorizer',
                                      'action': 'blocked_before_system_call',
                                      'classification': 'blocked_unrecognized'})
                raise RuntimeError('CI offline guard blocked operation')

        def connect(database, *args, **kwargs):
            positional = list(args)
            factory = positional[4] if len(positional) > 4 else kwargs.get('factory', GuardedConnection)
            if factory not in (base, GuardedConnection):
                guard.denials.append({'api': 'ci.sqlite_factory',
                                      'action': 'blocked_before_system_call',
                                      'classification': 'blocked_unrecognized'})
                raise RuntimeError('CI offline guard blocked operation')
            if len(positional) > 4:
                positional[4] = GuardedConnection
            else:
                kwargs['factory'] = GuardedConnection
            return original(database, *positional, **kwargs)

        sqlite3.connect = sqlite3.dbapi2.connect = connect
        sqlite3.Connection = sqlite3.dbapi2.Connection = GuardedConnection

    def allowed_sqlite_target(self, value):
        try:
            target = os.fsdecode(value)
            # Empty SQLite names create temporary databases outside our path
            # authority; do not let Path('') normalize them into an allowed cwd.
            if not target:
                return False
            return (target == ':memory:' or
                    (not target.startswith('file:')
                     and Path(target).resolve().is_relative_to(self.sandbox)))
        except (TypeError, ValueError, OSError):
            return False

    def authorize_sqlite(self, action, first, second, database, trigger):
        event = None
        # SQLite also requests SQLITE_ATTACH for VACUUM INTO destinations.
        if action == sqlite3.SQLITE_ATTACH and not self.allowed_sqlite_target(first):
            event = 'sqlite3.attach'
        elif action == sqlite3.SQLITE_FUNCTION and str(second).lower() == 'load_extension':
            event = 'sqlite3.load_extension'
        if event is not None:
            self.denials.append({'api': event, 'action': 'blocked_before_system_call',
                                 'classification': self.classification(event, (), sys._getframe(1))})
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK


class Results:
    def __init__(self):
        self.rows, self.unexpected_skips = [], []

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed or report.skipped:
            self.rows.append({'nodeid': report.nodeid, 'phase': report.when,
                              'outcome': report.outcome, 'duration': report.duration})
        if report.skipped:
            node = report.nodeid.replace('\\', '/')
            if not (sys.platform == 'win32' and node in ALLOWED_WINDOWS_SKIPS
                    and 'symlink' in str(report.longrepr).lower()):
                self.unexpected_skips.append(node)

    def pytest_collectreport(self, report):
        # Collection-level skips can otherwise hide a whole module while the
        # remaining selected modules pass. No collection skip is approved.
        if report.failed or report.skipped:
            self.rows.append({'nodeid': report.nodeid, 'phase': 'collect',
                              'outcome': report.outcome, 'duration': getattr(report, 'duration', 0.0)})
        if report.skipped:
            self.unexpected_skips.append(report.nodeid.replace('\\', '/'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--sandbox-root', required=True, type=Path)
    parser.add_argument('--telemetry', required=True, type=Path)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    source, sandbox = args.source_root.resolve(strict=True), args.sandbox_root.resolve(strict=True)
    if (not source.is_dir() or not sandbox.is_dir() or sandbox.is_relative_to(source)
            or source.is_relative_to(sandbox)):
        parser.error('Source and isolated sandbox must be separate directories')
    pytest_args = args.pytest_args[1:] if args.pytest_args[:1] == ['--'] else args.pytest_args
    if args.selftest and str(SELFTEST_FILE) not in pytest_args:
        parser.error('Selftest classification requires the exact guard selftest file')
    # Match the prior Windows OS-metadata adapter, without authorizing any
    # subprocess exception for WMI or shell version probes.
    if sys.platform == 'win32':
        def no_wmi(*unused, **kwargs):
            raise OSError('WMI unavailable in offline tests')
        platform._wmi_query = no_wmi
        native = sys.getwindowsversion()
        version = '.'.join(map(str, native.platform_version or native[:3]))
        platform._syscmd_ver = lambda *unused, **kwargs: ('Windows', '', version)
    os.chdir(source)
    sys.path.insert(0, str(source))
    guard = OfflineGuard(sandbox, args.selftest)
    sys.addaudithook(guard.audit)
    guard.protect_sqlite_constructors()
    global ACTIVE_GUARD
    ACTIVE_GUARD = guard
    results, code = Results(), 2
    try:
        import pytest
        code = int(pytest.main(pytest_args, plugins=[results]))
    finally:
        unknown = [r for r in guard.denials if r['classification'] == 'blocked_unrecognized']
        observed = {r['classification'].split(':', 1)[1] for r in guard.denials
                    if r['classification'].startswith('blocked_selftest:')}
        complete = not args.selftest or observed == set(EXPECTED)
        final = 90 if unknown or not complete else 91 if results.unexpected_skips else code
        record = {'pytest_exit_code': code, 'exit_code': final,
                  'denials': guard.denials, 'unrecognized_denials': unknown,
                  'selftest_complete': complete, 'unexpected_skips': results.unexpected_skips,
                  'permitted_internal_socketpair_events': guard.internal_events,
                  'real_network_connections': 0, 'tests': results.rows}
        args.telemetry.write_text(json.dumps(record, indent=2), encoding='utf-8')
    return final


if __name__ == '__main__':
    raise SystemExit(main())
